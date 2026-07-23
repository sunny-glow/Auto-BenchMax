# mcp_eval_scores.py
#
# Description:
# This script processes, evaluates, and analyzes model performance based on ground truth data.
# Uses LiteLLM for all providers (Gemini, OpenAI, Claude, etc.) - unified interface.
#
# Example Usage from command line:
#
# uv run mcp_evals_scores.py \
#   --input-file="completion_results/sample_4o_results.csv" \
#   --model-label="gpt4o" \
#   --evaluator-model="gemini/gemini-2.5-pro" \  # optional
#   --num-tasks=10  # optional

import pandas as pd
import numpy as np
import asyncio
import os
import json
import ast
import json
import logging
import argparse
from typing import List, Dict, Any, Optional, Tuple, Set
from dataclasses import dataclass
from enum import Enum
from datetime import datetime
from collections import defaultdict, Counter
from abc import ABC, abstractmethod

# Third-party libraries
import litellm
from tenacity import retry, wait_random_exponential, stop_after_attempt
from tqdm.asyncio import tqdm as async_tqdm
from tqdm import tqdm
import matplotlib.pyplot as plt
import nest_asyncio
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Apply nest_asyncio to allow nested event loops
nest_asyncio.apply()

# Configure LiteLLM - suppress verbose logging
litellm.set_verbose = False
logging.getLogger("LiteLLM").setLevel(logging.ERROR)


# =========================================================================
# 1. CONFIGURATION AND SETUP
# =========================================================================


@dataclass
class EvaluatorConfig:
    """Configuration for the evaluator and analyzer."""

    evaluator_model: str
    semaphore_limit: int
    request_delay: float = 0.2
    verbose: bool = True
    save_partial_on_error: bool = True
    strict_evaluation: bool = True
    num_tasks: Optional[int] = None


def setup_logging(verbose: bool = True):
    """Set up the logging configuration."""
    level = logging.INFO if verbose else logging.WARNING
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    return logging.getLogger(__name__)


def get_litellm_config():
    """Get LiteLLM configuration from environment variables."""
    api_key = os.getenv("EVAL_LLM_API_KEY") or os.getenv("LLM_API_KEY")
    if not api_key:
        raise ValueError(
            "LiteLLM API key not found. Set EVAL_LLM_API_KEY or LLM_API_KEY env var."
        )

    api_base = os.getenv("EVAL_LLM_BASE_URL", "")
    return api_key, api_base


# =========================================================================
# 2. CORE EVALUATION FRAMEWORK (SCORING) - GEMINI VERSION
# =========================================================================

import json
import ast
import re
from typing import List, Union


def extract_claims(claim_blob: Union[str, List, None]) -> List[str]:
    """
    Extracts and cleans individual claims from various input formats.

    Args:
        claim_blob: Can be:
            - A list of strings (direct claims)
            - A list of dicts with 'claim' key (e.g., [{"claim": "text", "essential": "yes"}])
            - A JSON string representing a list
            - A multi-line text with various separators
            - None or empty input

    Returns:
        A list of cleaned claim strings
    """

    # Handle None or empty inputs
    if claim_blob is None:
        return []

    # If it's already a list, process based on content type
    if isinstance(claim_blob, list):
        cleaned_claims = []
        for item in claim_blob:
            # Handle object format: {"claim": "text", "essential": "yes"}
            if isinstance(item, dict) and "claim" in item:
                claim_text = item["claim"]
                cleaned = clean_claim_text(str(claim_text))
                if cleaned and len(cleaned) > 3:
                    cleaned_claims.append(cleaned)
            # Handle string format
            else:
                cleaned = clean_claim_text(str(item))
                if cleaned and len(cleaned) > 3:
                    cleaned_claims.append(cleaned)
        return cleaned_claims

    # Convert to string if not already
    if not isinstance(claim_blob, str):
        claim_blob = str(claim_blob)

    # Remove any leading/trailing whitespace
    claim_blob = claim_blob.strip()

    # Return empty list for empty strings
    if not claim_blob:
        return []

    # Try to parse as JSON/Python list first
    # This handles cases like: '["claim1", "claim2"]' or '[{"claim": "text", "essential": "yes"}]'
    if claim_blob.startswith("[") and claim_blob.endswith("]"):
        try:
            parsed_list = json.loads(claim_blob)
            if isinstance(parsed_list, list):
                # Clean and filter the parsed claims
                cleaned_claims = []
                for item in parsed_list:
                    # Handle object format: {"claim": "text", "essential": "yes"}
                    if isinstance(item, dict) and "claim" in item:
                        claim_text = item["claim"]
                        cleaned = clean_claim_text(str(claim_text))
                        if cleaned and len(cleaned) > 3:
                            cleaned_claims.append(cleaned)
                    # Handle string format
                    else:
                        cleaned = clean_claim_text(str(item))
                        if cleaned and len(cleaned) > 3:
                            cleaned_claims.append(cleaned)
                return cleaned_claims
        except (json.JSONDecodeError, ValueError) as json_error:
            # If JSON parsing fails, try ast.literal_eval as fallback
            # ast.literal_eval is more forgiving with Python string literals
            try:
                parsed_list = ast.literal_eval(claim_blob)
                if isinstance(parsed_list, list):
                    cleaned_claims = []
                    for item in parsed_list:
                        # Handle object format: {"claim": "text", "essential": "yes"}
                        if isinstance(item, dict) and "claim" in item:
                            claim_text = item["claim"]
                            cleaned = clean_claim_text(str(claim_text))
                            if cleaned and len(cleaned) > 3:
                                cleaned_claims.append(cleaned)
                        # Handle string format
                        else:
                            cleaned = clean_claim_text(str(item))
                            if cleaned and len(cleaned) > 3:
                                cleaned_claims.append(cleaned)
                    return cleaned_claims
            except (ValueError, SyntaxError):
                # If both parsing methods fail, log the issue and continue to text-splitting logic
                # This might happen with malformed JSON like '["text "inner" text"]'
                # where CSV double-quotes were converted incorrectly
                import logging

                logging.debug(
                    f"Failed to parse claim_blob as JSON or Python literal: {claim_blob[:100]}"
                )
                pass

    # Try to detect numbered list pattern (1. 2. 3. etc.) using regex
    # This handles patterns like "1. claim\n2. claim\n3. claim"
    numbered_pattern = r"(?:^|\n)(\d+)\.\s+"
    if re.search(numbered_pattern, claim_blob):
        # Split by numbered pattern
        parts = re.split(numbered_pattern, claim_blob)

        # parts will be like: ['', '1', 'claim text', '2', 'claim text', ...]
        # We need to pair up the numbers with their text
        claims = []
        i = 1
        while i < len(parts):
            # Skip the number itself, take the text
            if i + 1 < len(parts):
                claim_text = parts[i + 1].strip()
                if claim_text and len(claim_text) > 3:
                    # Clean up the claim text
                    claim_text = claim_text.rstrip("\n").strip()
                    claims.append(claim_text)
                i += 2
            else:
                break

        if claims:
            return claims

    # Fallback to original text-splitting logic for backward compatibility
    # This handles plain text with various separators
    separators = ["\n•", "\n-", "\n*", ";", "||"]
    for sep in separators:
        if sep in claim_blob:
            parts = claim_blob.split(sep)
            claims = []
            for p in parts:
                cleaned = clean_claim_text(p)
                if cleaned and len(cleaned) > 3:
                    claims.append(cleaned)
            if claims:
                return claims

    # Try splitting by newlines as last resort
    lines = claim_blob.strip().split("\n")
    claims = []
    for line in lines:
        cleaned = clean_claim_text(line)
        if cleaned and len(cleaned) > 3:
            claims.append(cleaned)
    return claims


def clean_claim_text(text: str) -> str:
    """
    Cleans individual claim text by removing unwanted characters and formatting.

    Args:
        text: Raw claim text

    Returns:
        Cleaned claim text
    """
    # Strip whitespace
    text = text.strip()

    # Remove common bullet point markers and numbering from the start
    text = re.sub(r"^[-*•·◦‣⁃]\s*", "", text)  # Bullet points
    text = re.sub(r"^\d+[.)]\s*", "", text)  # Numbered lists

    # Replace Unicode quotes with standard quotes
    text = text.replace("\u201c", '"')  # Left double quote
    text = re.sub(r'[\u201d"]', '"', text)  # Right double quote
    text = text.replace("\u2018", "'")  # Left single quote
    text = text.replace("\u2019", "'")  # Right single quote

    # Remove other problematic Unicode characters
    text = text.replace("\u2013", "-")  # En dash
    text = text.replace("\u2014", "-")  # Em dash
    text = text.replace("\u2026", "...")  # Ellipsis

    # Clean up any trailing punctuation issues (like ." or .")
    text = re.sub(r'[.\s]*["\']+$', "", text)  # Remove trailing quotes with dots
    text = re.sub(r'["\']+\.*$', "", text)  # Remove trailing quotes and dots

    # Final strip of whitespace and basic punctuation
    text = text.strip(" \t\n\r")

    return text


# Define Gemini schemas - Modified for single claim evaluation
def get_single_claim_evaluation_schema():
    """Define the response schema for single claim evaluation"""
    return {
        "type": "object",
        "properties": {
            "claim_text": {"type": "string"},
            "coverage_outcome": {
                "type": "string",
                "enum": ["fulfilled", "partially_fulfilled", "not_fulfilled"],
            },
            "justification": {"type": "string"},
            "confidence_level": {"type": "number"},
        },
        "required": [
            "claim_text",
            "coverage_outcome",
            "justification",
            "confidence_level",
        ],
    }


# =========================================================================
# 3. LITELLM CLIENT (Unified Interface for All Providers)
# =========================================================================


class AsyncLLMClient(ABC):
    """Abstract base class for LLM clients"""

    @abstractmethod
    async def generate_structured_content(
        self, prompt: str, response_schema: Dict, temperature: float = 0.0
    ) -> Dict:
        """Generate structured content with retry logic."""
        pass

    @abstractmethod
    def get_stats(self) -> Dict[str, int]:
        """Get request statistics"""
        pass


class AsyncLiteLLMClient(AsyncLLMClient):
    """Manages async LiteLLM requests with rate limiting - supports all providers via LiteLLM"""

    def __init__(self, config: EvaluatorConfig):
        self.config = config
        self.semaphore = asyncio.Semaphore(config.semaphore_limit)
        self.logger = logging.getLogger(__name__)
        self.request_count = 0
        self.error_count = 0

        # Initialize LiteLLM configuration from environment
        api_key, api_base = get_litellm_config()
        litellm.api_key = api_key
        if api_base:
            litellm.api_base = api_base

    def _effective_temperature(self, requested_temperature: float) -> float:
        """
        Return a temperature value compatible with the configured evaluator model.

        Note: LiteLLM/OpenAI gpt-5* models currently reject temperature=0.0 and only
        accept temperature=1. We normalize here so callers can keep using 0.0 by default.
        """
        # Model strings may be like "gpt-5", "gpt-5.2", or provider-prefixed like "openai/gpt-5.2".
        model_name = (self.config.evaluator_model or "").lower()
        if "gpt-5" in model_name:
            return 1.0
        return requested_temperature

    @retry(
        wait=wait_random_exponential(min=1, max=60),
        stop=stop_after_attempt(6),
        reraise=True,
    )
    async def generate_structured_content(
        self, prompt: str, response_schema: Dict, temperature: float = 0.0
    ) -> Dict:
        """Generate structured content using LiteLLM with retry logic."""
        async with self.semaphore:
            try:
                self.request_count += 1

                # LiteLLM uses OpenAI-compatible format
                # Pass response_schema for structured output (Gemini supports this natively)
                response = await litellm.acompletion(
                    model=self.config.evaluator_model,
                    # OpenAI JSON mode requires that the word "json" appears in the messages
                    # when using response_format={"type":"json_object"}.
                    messages=[
                        {
                            "role": "system",
                            "content": "Return only valid json that matches the requested schema.",
                        },
                        {"role": "user", "content": prompt},
                    ],
                    response_format={
                        "type": "json_object",
                        "response_schema": response_schema,
                    },
                    temperature=self._effective_temperature(temperature),
                    api_key=litellm.api_key,
                    api_base=(
                        litellm.api_base
                        if hasattr(litellm, "api_base") and litellm.api_base
                        else None
                    ),
                )

                # Rate limiting delay
                await asyncio.sleep(self.config.request_delay)

                # Parse JSON response
                content = response.choices[0].message.content
                return json.loads(content)

            except Exception as e:
                self.error_count += 1
                self.logger.error(f"LiteLLM API error: {e}")
                raise

    def get_stats(self) -> Dict[str, int]:
        """Get request statistics"""
        return {
            "total_requests": self.request_count,
            "errors": self.error_count,
            "success_rate": (self.request_count - self.error_count)
            / max(self.request_count, 1),
        }


# =========================================================================
# 4. COVERAGE EVALUATOR
# =========================================================================


class CoverageEvaluator:
    """Evaluates claim coverage with continuous scoring (0-1) - one claim at a time."""

    def __init__(self, client: AsyncLLMClient, config: EvaluatorConfig):
        self.client = client
        self.config = config
        self.logger = logging.getLogger(__name__)

    def _get_single_claim_evaluation_prompt(self, claim: str, response: str) -> str:
        """Generate prompt for evaluating a single claim"""
        return f"""You are evaluating how well a model's response addresses a specific expert-defined claim.
SCORING CRITERIA:
- fulfilled: Claim is completely and accurately addressed. The response covers all key details.
- partially_fulfilled: Claim is partially addressed. The response covers some but not all key details.
- not_fulfilled: Claim is not addressed. The response does not include any key details.
NUMERICAL COMPARISON GUIDELINES:
- For numerical values, use reasonable approximation thresholds:
  * Exact match NOT required for decimals
  * Values within 5% of the claimed number are considered matching
  * For percentages, ±1 percentage points is acceptable
  * Round to appropriate significant figures based on context
- Consider the precision appropriate to the domain:
  * Scientific measurements may need higher precision
  * General statistics/estimates can have looser matching
  * Financial figures should match to reasonable business precision (e.g., millions/billions don't need exact cents)
- If a number is expressed differently but mathematically equivalent (e.g., "0.5" vs "50%" vs "half"), consider it a match
CLAIM TO EVALUATE:
{claim}
MODEL RESPONSE TO ANALYZE:
{response}
INSTRUCTIONS:
1. Determine if the core requirement of the claim is met in the response
2. Check if all key components from the claim appear substantively in the response
   - For numerical values, apply the flexible matching guidelines above
   - Focus on whether the same magnitude and meaning are conveyed
3. Assign the appropriate coverage_outcome
4. Provide specific justification referencing what was/wasn't covered
   - When numbers differ slightly, note if they're within acceptable range
5. Provide a confidence level (0.0-1.0) for your assessment
Be rigorous but fair in your assessment. Focus on whether the response conveys the same information as the claim, not on exact numerical precision unless precision is critical to the claim's meaning."""

    async def evaluate_single_claim(self, claim: str, response: str) -> Dict[str, Any]:
        """Evaluate a single claim against the response"""
        prompt = self._get_single_claim_evaluation_prompt(claim, response)

        try:
            result = await self.client.generate_structured_content(
                prompt=prompt,
                response_schema=get_single_claim_evaluation_schema(),
                temperature=0.0,
            )
            return result
        except Exception as e:
            self.logger.warning(f"Single claim evaluation failed: {e}")
            return {
                "claim_text": claim,
                "coverage_outcome": "not_fulfilled",
                "justification": f"Evaluation failed: {e}",
                "confidence_level": 0.1,
            }

    async def evaluate(self, claims: List[str], response: str) -> Dict[str, Any]:
        """Evaluate all claims by making individual API calls for each claim"""
        if not claims:
            return {
                "per_claim": [],
                "coverage_score": None,
                "explanation": "No claims provided",
                "confidence": 1.0,
            }

        # Define coverage outcome to score mapping
        coverage_to_score = {
            "fulfilled": 1.0,
            "partially_fulfilled": 0.5,
            "not_fulfilled": 0.0,
        }

        # Evaluate each claim individually
        tasks = [self.evaluate_single_claim(claim, response) for claim in claims]
        claim_results = await asyncio.gather(*tasks)

        # Aggregate results
        per_claim = []
        total_score = 0
        fulfilled_count = 0
        partially_fulfilled_count = 0
        total_confidence = 0

        for result in claim_results:
            coverage_outcome = result.get("coverage_outcome", "not_fulfilled")
            score = coverage_to_score.get(coverage_outcome, 0.0)
            total_score += score
            total_confidence += result.get("confidence_level", 0.5)

            if score >= 1.0:
                fulfilled_count += 1
                covered = True
            elif score >= 0.5:
                partially_fulfilled_count += 1
                covered = "partial"
            else:
                covered = False

            per_claim.append(
                {
                    "claim": result.get("claim_text", ""),
                    "score": score,
                    "covered": covered,
                    "reason": result.get("justification", ""),
                }
            )

        coverage_score = round(total_score / len(claims), 3) if claims else 0.0
        avg_confidence = total_confidence / len(claims) if claims else 0.5

        return {
            "per_claim": per_claim,
            "coverage_score": coverage_score,
            "total_claims": len(claims),
            "fully_covered_claims": fulfilled_count,
            "partially_covered_claims": partially_fulfilled_count,
            "explanation": "Evaluation complete",
            "confidence": avg_confidence,
        }

    def _create_fallback_result(
        self, claims: List[str], response: str, error_msg: str
    ) -> Dict[str, Any]:
        """Simple heuristic fallback"""
        return {
            "per_claim": [
                {
                    "claim": c,
                    "covered": False,
                    "score": 0.0,
                    "reason": "Fallback due to error",
                }
                for c in claims
            ],
            "coverage_score": 0.0,
            "total_claims": len(claims),
            "fully_covered_claims": 0,
            "partially_covered_claims": 0,
            "explanation": f"Fallback evaluation used: {error_msg}",
            "confidence": 0.1,
        }


async def evaluate_dataframe_async(
    df: pd.DataFrame, evaluator: CoverageEvaluator
) -> pd.DataFrame:
    """Asynchronously evaluates all rows in a dataframe."""
    logger = logging.getLogger(__name__)

    async def safe_evaluate(row_idx, row):
        try:
            claims = extract_claims(row.get("GTFA_CLAIMS", ""))
            # Determine the correct response column
            response_col = next(
                (
                    col
                    for col in ["script_model_response", "response"]
                    if col in row and pd.notna(row[col])
                ),
                None,
            )
            response = row.get(response_col, "") if response_col else ""
            result = await evaluator.evaluate(claims, response)
            return row_idx, result
        except Exception as e:
            logger.error(f"Error processing row {row_idx}: {e}")
            return row_idx, {"coverage_score": None, "explanation": f"Failed: {e}"}

    tasks = [safe_evaluate(idx, row) for idx, row in df.iterrows()]
    results_list = [
        await f
        for f in tqdm(
            asyncio.as_completed(tasks), total=len(tasks), desc="Scoring Rows"
        )
    ]

    results_dict = {idx: res for idx, res in results_list}

    out_df = df.copy()
    result_cols = {
        "coverage_score": [],
        "fully_covered_claims": [],
        "partially_covered_claims": [],
        "total_claims": [],
        "coverage_details_json": [],
        "evaluation_confidence": [],
    }

    for idx in df.index:
        result = results_dict.get(idx, {})
        result_cols["coverage_score"].append(result.get("coverage_score"))
        result_cols["fully_covered_claims"].append(
            result.get("fully_covered_claims", 0)
        )
        result_cols["partially_covered_claims"].append(
            result.get("partially_covered_claims", 0)
        )
        result_cols["total_claims"].append(result.get("total_claims", 0))
        result_cols["coverage_details_json"].append(json.dumps(result))
        result_cols["evaluation_confidence"].append(result.get("confidence", 0.0))

    for col, data in result_cols.items():
        out_df[col] = data

    return out_df


# =========================================================================
# 3. STATISTICAL ANALYSIS AND PLOTTING
# =========================================================================


def generate_statistics_and_plots(
    scored_csv_path: str,
    model_label: str,
    output_dir: str,
    pass_threshold: float = 0.75,
):
    """Generates a summary stats CSV and a histogram plot of coverage scores."""
    logger = logging.getLogger(__name__)
    logger.info(f"Step 4: Generating statistics and plots for '{scored_csv_path}'...")

    try:
        df = pd.read_csv(scored_csv_path)
        if "coverage_score" not in df.columns:
            raise KeyError("'coverage_score' column missing.")

        # --- Generate and save statistics ---
        stats_df = (
            df["coverage_score"]
            .describe()
            .to_frame(name="value")
            .reset_index()
            .rename(columns={"index": "stat"})
        )

        # Rename "mean" to "mean coverage score"
        stats_df.loc[stats_df["stat"] == "mean", "stat"] = "mean coverage score"

        # Calculate pass rate (% of tasks where coverage_score >= pass_threshold)
        valid_scores = df["coverage_score"].dropna()
        pass_count = (valid_scores >= pass_threshold).sum()
        total_count = len(valid_scores)
        pass_rate = pass_count / total_count if total_count > 0 else 0.0

        # Insert pass rate row right after "mean coverage score"
        mean_idx = stats_df[stats_df["stat"] == "mean coverage score"].index[0]
        pass_rate_row = pd.DataFrame({"stat": ["pass rate"], "value": [pass_rate]})
        stats_df = pd.concat(
            [
                stats_df.iloc[: mean_idx + 1],
                pass_rate_row,
                stats_df.iloc[mean_idx + 1 :],
            ]
        ).reset_index(drop=True)

        stats_path = os.path.join(output_dir, f"coverage_stats_{model_label}.csv")
        stats_df.to_csv(stats_path, index=False)
        logger.info(f"Saved summary statistics to '{stats_path}'")
        print("\nCoverage Score Summary:")
        print(stats_df)

        # --- Generate and save histogram plot ---
        scores = df["coverage_score"].dropna().to_numpy()

        # Only create plot if we have data
        if len(scores) > 0:
            fig, ax = plt.subplots(figsize=(8, 5))
            ax.hist(scores, bins=min(50, len(scores)), edgecolor="black", alpha=0.7)
            ax.set_title(f"Coverage Score Distribution ({model_label})")
            ax.set_xlabel("Coverage Score")
            ax.set_ylabel("Frequency")
            ax.axvline(
                scores.mean(),
                color="red",
                linestyle="--",
                label=f"Mean: {scores.mean():.3f}",
            )
            ax.legend()
            plt.tight_layout()

            plot_path = os.path.join(
                output_dir, f"coverage_histogram_{model_label}.png"
            )
            plt.savefig(plot_path)
            logger.info(f"Saved histogram plot to '{plot_path}'")
            plt.close(fig)
        else:
            logger.warning("No valid scores to plot")

    except FileNotFoundError:
        logger.error(f"Scored file not found at '{scored_csv_path}'")
        raise
    except Exception as e:
        logger.error(f"Failed to generate statistics and plots: {e}")
        raise


# =========================================================================
# 4. MAIN EXECUTION
# =========================================================================


async def main(args):
    """Main function to run the entire pipeline."""
    setup_logging()
    logger = logging.getLogger(__name__)

    # Log if running on limited tasks
    if args.num_tasks:
        logger.info(f"🔬 Running evaluation on first {args.num_tasks} tasks only")

    # Create output directory if it doesn't exist
    output_dir = args.output_dir
    os.makedirs(output_dir, exist_ok=True)

    # Define file path for scored results
    scored_path = os.path.join(output_dir, f"scored_{args.model_label}.csv")

    try:
        # --- Create Evaluator Configuration ---
        logger.info(f"Using evaluator model: {args.evaluator_model}")
        config = EvaluatorConfig(
            evaluator_model=args.evaluator_model,
            semaphore_limit=args.concurrency,
            strict_evaluation=True,
            num_tasks=args.num_tasks,
        )

        # --- Pipeline Execution ---
        # 1. Load input file (already contains both ground truth and completion data)
        logger.info(f"Loading input file: {args.input_file}")
        df_input = pd.read_csv(args.input_file)

        # Apply task limit if specified
        if args.num_tasks is not None and args.num_tasks > 0:
            original_size = len(df_input)
            df_input = df_input.head(args.num_tasks)
            logger.info(
                f"Limited dataset from {original_size} to {len(df_input)} tasks"
            )

        # Verify required columns exist
        required_cols = ["TASK", "PROMPT", "TRAJECTORY", "GTFA_CLAIMS"]
        missing_cols = [col for col in required_cols if col not in df_input.columns]
        if missing_cols:
            logger.error(
                f"Missing required columns in {args.input_file}: {missing_cols}"
            )
            raise KeyError(f"Missing required columns: {missing_cols}")

        logger.info(f"Successfully loaded {len(df_input)} tasks")

        # 2. Run scoring evaluation
        client = AsyncLiteLLMClient(config)
        evaluator = CoverageEvaluator(client, config)
        df_scored = await evaluate_dataframe_async(df_input, evaluator)
        df_scored.to_csv(scored_path, index=False)

        logger.info(f"✅ Saved scored file to '{scored_path}'")
        valid_scores = df_scored["coverage_score"].dropna()
        logger.info(f"Evaluation complete. Average coverage: {valid_scores.mean():.3f}")

        # 3. Generate statistics and plots
        generate_statistics_and_plots(
            scored_path, args.model_label, output_dir, args.pass_threshold
        )

        logger.info(f"\n🚀 Pipeline finished successfully!")
        logger.info(f"Results available in: {output_dir}")

        if args.num_tasks:
            logger.info(f"📊 Note: Results are based on {args.num_tasks} tasks only")

    except (FileNotFoundError, KeyError) as e:
        logger.error(f"Pipeline stopped due to an error: {e}")
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}", exc_info=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Run model evaluation pipeline with coverage scoring."
    )

    parser.add_argument(
        "--input-file",
        type=str,
        required=True,
        help="Path to the completion results CSV file containing both ground truth and model outputs.",
    )
    parser.add_argument(
        "--model-label",
        type=str,
        required=True,
        help="Short identifier for the model being evaluated (e.g., 'gpt51'). Used in output filenames.",
    )
    parser.add_argument(
        "--evaluator-model",
        type=str,
        default=os.getenv("EVAL_LLM_MODEL", "gemini/gemini-2.5-pro"),
        help="Model name in LiteLLM format. Default: EVAL_LLM_MODEL env var or 'gemini/gemini-2.5-pro'",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="evaluation_results",
        help="Directory to save all output files.",
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=5,
        help="Number of concurrent requests to the LLM API.",
    )
    parser.add_argument(
        "--num-tasks",
        type=int,
        default=None,
        help="Limit evaluation to first N tasks (useful for testing). If not specified, processes all tasks.",
    )
    parser.add_argument(
        "--pass-threshold",
        type=float,
        default=0.75,
        help="Coverage score threshold for pass rate calculation (default: 0.75)",
    )

    args = parser.parse_args()

    # Run the main async function
    asyncio.run(main(args))
