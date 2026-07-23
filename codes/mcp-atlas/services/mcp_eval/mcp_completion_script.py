# USAGE:
# From file:       uv run mcp_completion_script.py --model "openai/gpt-4o" --input "sample_tasks.csv" --output "sample_4o_results.csv"
# From HuggingFace: uv run mcp_completion_script.py --model "openai/gpt-4o" --input_huggingface "ScaleAI/mcp-eval" --output "results.csv"
#
# By default, tasks are filtered to only run those whose ground truth trajectories use MCP servers you have API keys for.
# Use --no-filter to disable this and run all tasks regardless of available servers.
#
# The filtering process:
# 1. Query the agent-environment service (MCP_SERVER_URL) to get the list of enabled servers
# 2. If no servers are returned, all servers are considered enabled
# 3. If servers are returned, run extract_mcp_servers_per_task.py to extract which servers are used in each task's ground truth TRAJECTORY
# 4. Filter out tasks whose ground truth trajectories used servers you don't have API keys for
# 5. Print summary of how many tasks are being run vs skipped

# Note that if rows exist in the output file, it'll skip re-evaluating those already-processed rows
# This script assumes that there's a local webserver running. You can start the webserver with: make run-mcp-completion

import json
import pandas as pd
import numpy as np
from typing import Dict, List, Set, Tuple, Any, Optional
from dataclasses import dataclass, field, asdict
from collections import defaultdict
import re
from difflib import SequenceMatcher
import warnings
import sys
import os
import time
import uuid
import asyncio
import aiohttp
import aiofiles
import aiocsv
import logging
import random
import argparse
import subprocess
import requests
from pathlib import Path
from dotenv import load_dotenv, find_dotenv
from datasets import load_dataset

warnings.filterwarnings("ignore")

# Load environment variables from .env file (searches up the directory tree)
load_dotenv(find_dotenv())

# Configure logging for async operations
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("completion_results/mcp_eval.log"),
    ],
)

# Configuration - load from environment variables with defaults
SERVER_URL = os.getenv("SERVER_URL", "http://localhost:3000")

# Retry configuration
MAX_RETRY_ATTEMPTS = int(os.getenv("MAX_RETRY_ATTEMPTS", "3"))


def get_retry_delay(attempt: int) -> float:
    """Calculate exponential backoff delay with jitter. Base: 5s, 10s, 20s..."""
    delay = 5 * (2**attempt)
    jitter = delay * random.uniform(0, 0.5)
    return delay + jitter


# System prompt for the model (only used if USE_SYSTEM_PROMPT_IN_COMPLETION=true)
SYSTEM_PROMPT = "Role: You are a factual, tool-aware assistant connected to a variety of tools. Use the available tools to answer the user query. Do not ask the user for clarification; fully complete the task using the information provided in the prompt."
USE_SYSTEM_PROMPT = os.getenv("USE_SYSTEM_PROMPT_IN_COMPLETION", "").lower() == "true"


@dataclass
class ToolCall:
    tool_name: str
    parameters: Dict[str, Any] = field(default_factory=dict)
    response: Optional[str] = None
    error: Optional[str] = None


@dataclass
class GenerationResult:
    task_id: str
    trajectory: Optional[List[Dict[str, Any]]] = None
    model_response: Optional[str] = None
    script_model_response: Optional[str] = None
    raw_conversation_history: Optional[str] = None
    trajectory_time: Optional[float] = None
    num_retry: Optional[int] = None


class AsyncMCPTrajectoryGenerator:
    """Fully async MCP trajectory generator - each task is independent"""

    def __init__(self, llm_model: str):
        self.llm_model = llm_model
        self.csv_lock = asyncio.Lock()  # For thread-safe CSV writing

    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if hasattr(self, "session"):
            await self.session.close()

    def parse_enabled_tools(self, enabled_tools_str: str) -> List[str]:
        """Parse the ENABLED_TOOLS field - supports both string list and object list formats"""
        try:
            if enabled_tools_str.startswith('"[') and enabled_tools_str.endswith(']"'):
                enabled_tools_str = enabled_tools_str[1:-1]
                enabled_tools_str = enabled_tools_str.replace('""', '"')

            parsed_tools = json.loads(enabled_tools_str)

            if not parsed_tools:
                return []

            # Support both: ["tool1", "tool2"] and [{"name": "tool1"}, {"name": "tool2"}]
            if isinstance(parsed_tools[0], str):
                return parsed_tools
            elif isinstance(parsed_tools[0], dict) and "name" in parsed_tools[0]:
                return [
                    tool["name"]
                    for tool in parsed_tools
                    if isinstance(tool, dict) and "name" in tool
                ]
            return []
        except:
            return []

    def parse_errors_from_trajectory(self, trajectory_str: str) -> List[Dict[str, Any]]:
        """Parse errors from the AgentOutput trajectory format"""
        if not trajectory_str or pd.isna(trajectory_str):
            return []

        try:
            trajectory_data = json.loads(trajectory_str)
            errors = []

            # Handle AgentOutput format with discriminated unions
            if isinstance(trajectory_data, list):
                for item in trajectory_data:
                    if isinstance(item, dict) and item.get("type") == "error":
                        error_data = item.get("data", {})
                        # Preserve complete error data as-is
                        errors.append(
                            error_data
                            if isinstance(error_data, dict)
                            else {"error": str(error_data)}
                        )

            return errors
        except (json.JSONDecodeError, TypeError) as e:
            logging.error(f"Error parsing errors from trajectory: {e}")
            return []

    def parse_trajectory(self, trajectory_str: str) -> List[ToolCall]:
        """Parse trajectory string from AgentOutput format"""
        if not trajectory_str or pd.isna(trajectory_str):
            return []

        try:
            trajectory_data = json.loads(trajectory_str)
            tool_calls = []

            # Handle AgentOutput format: array of {type: 'message'|'error', data: ...} objects
            for item in trajectory_data:
                if item.get("type") == "message":
                    entry = item.get("data", {})
                    if entry.get("tool_calls"):
                        # OpenAI format: tool_calls array
                        for call in entry["tool_calls"]:
                            function_info = call.get("function", {})
                            tool_name = function_info.get("name", "")
                            args_str = function_info.get("arguments", "{}")
                            try:
                                parameters = (
                                    json.loads(args_str)
                                    if isinstance(args_str, str)
                                    else args_str
                                )
                            except:
                                parameters = {}

                            tool_calls.append(
                                ToolCall(
                                    tool_name=tool_name,
                                    parameters=parameters,
                                    response=None,
                                    error=None,
                                )
                            )
                    elif (
                        entry.get("role") == "assistant"
                        and entry.get("content")
                        and "llama" in self.llm_model.lower()
                    ):
                        # Llama format: tool calls in content as JSON
                        content = entry["content"]
                        import re

                        json_match = re.search(
                            r'\[\s*{[^}]*"name"[^}]*}.*?\]', content, re.DOTALL
                        )
                        if json_match:
                            try:
                                tools_array = json.loads(json_match.group(0))
                                for tool_call in tools_array:
                                    if (
                                        isinstance(tool_call, dict)
                                        and "name" in tool_call
                                    ):
                                        tool_calls.append(
                                            ToolCall(
                                                tool_name=tool_call.get("name", ""),
                                                parameters=tool_call.get(
                                                    "parameters", {}
                                                ),
                                                response=None,
                                                error=None,
                                            )
                                        )
                            except json.JSONDecodeError:
                                continue

            return tool_calls
        except (json.JSONDecodeError, TypeError) as e:
            logging.error(f"Error parsing trajectory: {e}")
            return []

    async def run_live_task_async(
        self, enabled_tools: List[str], user_prompt: str, taskId: Optional[str]
    ) -> Tuple[Optional[str], int]:
        """Async API call to get live task response - returns (response, num_attempts)"""

        def uuid14():
            return str(uuid.uuid4()).replace("-", "")[-14:]

        messages = []
        if USE_SYSTEM_PROMPT:
            messages.append({"role": "system", "content": SYSTEM_PROMPT})
        messages.append({"role": "user", "content": user_prompt})

        payload = {
            "model": self.llm_model,
            "messages": messages,
            "enabledTools": enabled_tools,
            "enableThinkingTokens": False,
        }
        headers = {"Content-Type": "application/json"}

        url = f"{SERVER_URL}/v2/mcp_eval/run_agent"

        for attempt in range(MAX_RETRY_ATTEMPTS):
            try:
                async with self.session.post(
                    url, json=payload, headers=headers, timeout=600
                ) as resp:
                    if resp.status == 200:
                        try:
                            messages = await resp.json()
                        except aiohttp.ContentTypeError:
                            text = await resp.text()
                            messages = json.loads(text)

                        response = json.dumps(messages) if messages else None
                        return response, attempt + 1
                    else:
                        error_text = await resp.text()
                        logging.error(
                            f"HTTP {resp.status} error on attempt {attempt + 1}/{MAX_RETRY_ATTEMPTS} for task {taskId}: {error_text}"
                        )

            except Exception as e:
                logging.error(
                    f"Error on attempt {attempt + 1}/{MAX_RETRY_ATTEMPTS} for task {taskId}: {e}"
                )

            if attempt < MAX_RETRY_ATTEMPTS - 1:
                delay = get_retry_delay(attempt)
                logging.info(f"Retrying task {taskId} in {delay:.0f}s...")
                await asyncio.sleep(delay)

        return None, MAX_RETRY_ATTEMPTS

    async def write_result_to_csv(self, result_dict: Dict[str, Any], output_file: str):
        """Write a single result to CSV file (thread-safe)"""
        async with self.csv_lock:
            # Use a more robust approach - always append, but track if we need headers
            file_exists = (
                os.path.exists(output_file) and os.path.getsize(output_file) > 0
            )

            async with aiofiles.open(output_file, "a", newline="") as f:
                writer = aiocsv.AsyncDictWriter(f, fieldnames=result_dict.keys())
                if not file_exists:  # Write headers only if file is empty/doesn't exist
                    await writer.writeheader()
                await writer.writerow(result_dict)

    async def process_single_task(
        self,
        row_data: Dict[str, Any],
        output_file: str,
        task_index: int,
        total_tasks: int,
    ) -> Dict[str, Any]:
        """Complete pipeline: fetch → process → write for a single task"""
        task_id = row_data.get("TASK", task_index)
        prompt = row_data.get("PROMPT", "")
        num_attempts = 0

        try:
            # Stagger requests with random delay to avoid thundering herd
            random_sleep = random.uniform(0, 5)
            await asyncio.sleep(random_sleep)

            # Start timing after stagger delay
            start_time = time.time()
            logging.info(f"[{task_index + 1}/{total_tasks}] Processing task {task_id}")

            # 1. FETCH: Get live trajectory
            enabled_tools = self.parse_enabled_tools(
                row_data.get("ENABLED_TOOLS", "[]")
            )
            trajectory_response, num_attempts = await self.run_live_task_async(
                enabled_tools=enabled_tools,
                user_prompt=row_data.get("PROMPT", ""),
                taskId=task_id,
            )

            # 2. PROCESS: Evaluate the task
            result = GenerationResult(task_id=task_id)

            # Extract clean conversation history (without AgentOutput wrappers)
            clean_conversation = []
            if trajectory_response:
                try:
                    agent_outputs = json.loads(trajectory_response)
                    for item in agent_outputs:
                        if item.get("type") == "message":
                            clean_conversation.append(item.get("data", {}))
                except Exception:
                    pass

            result.raw_conversation_history = (
                json.dumps(clean_conversation) if clean_conversation else None
            )
            # Extract model response from AgentOutput format
            if trajectory_response:
                try:
                    conversation = json.loads(trajectory_response)

                    # Handle AgentOutput format: array of {type: 'message'|'error', data: ...} objects
                    for item in reversed(conversation):
                        if item.get("type") == "message":
                            msg = item.get("data", {})
                        if msg.get("role") == "assistant" and msg.get("content"):
                            result.script_model_response = msg["content"]
                            break
                        elif msg.get("role") == "tool" and msg.get("content"):
                            result.script_model_response = (
                                msg["content"][0]["text"]
                                if isinstance(msg["content"], list)
                                and len(msg["content"]) > 0
                                else str(msg["content"])
                            )
                            break
                        elif msg.get("role") == "assistant" and not msg.get("content"):
                            result.script_model_response = str(
                                msg.get("tool_calls", "")
                            )
                            break
                except Exception:
                    pass

            # Parse trajectories and errors
            gt_trajectory = self.parse_trajectory(row_data.get("TRAJECTORY", "[]"))
            model_trajectory = (
                self.parse_trajectory(trajectory_response)
                if trajectory_response
                else []
            )
            trajectory_errors = (
                self.parse_errors_from_trajectory(trajectory_response)
                if trajectory_response
                else []
            )

            result.trajectory = model_trajectory
            result.model_response = row_data.get("MODEL_RESPONSE", "")

            # End timing
            end_time = time.time()
            result.trajectory_time = end_time - start_time
            result.num_retry = num_attempts

            # Create result dictionary with BOTH ground truth and completion data
            result_dict = {
                # Ground truth columns (from input dataset) - all CAPS
                "TASK": task_id,
                "PROMPT": prompt,
                "TRAJECTORY": row_data.get("TRAJECTORY", ""),
                "GTFA_CLAIMS": row_data.get("GTFA_CLAIMS", ""),
                "ENABLED_TOOLS": row_data.get("ENABLED_TOOLS", ""),
                # Completion result columns (from script execution) - all lowercase
                "script_model_response": result.script_model_response,
                "raw_conversation_history": result.raw_conversation_history,
                "trajectory": (
                    json.dumps([asdict(tc) for tc in result.trajectory])
                    if result.trajectory
                    else "[]"
                ),
                "errors": trajectory_errors,
                "trajectory_time": result.trajectory_time,
                "num_retry": result.num_retry,
            }

            # 3. WRITE: Save to CSV
            await self.write_result_to_csv(result_dict, output_file)

            logging.info(
                f"[{task_index + 1}/{total_tasks}] ✅ Task {task_id} completed in {result.trajectory_time:.1f}s with {result.num_retry} attempts"
            )
            return result_dict

        except Exception as e:
            # End timing for error case
            end_time = time.time()
            trajectory_time = end_time - start_time

            logging.error(
                f"[{task_index + 1}/{total_tasks}] ❌ Task {task_id} failed: {e}"
            )
            # Parse enabled_tools for error case too
            enabled_tools = self.parse_enabled_tools(
                row_data.get("ENABLED_TOOLS", "[]")
            )

            # Write error result with ground truth columns
            error_result = {
                # Ground truth columns (from input dataset) - all CAPS
                "TASK": task_id,
                "PROMPT": prompt,
                "TRAJECTORY": row_data.get("TRAJECTORY", ""),
                "GTFA_CLAIMS": row_data.get("GTFA_CLAIMS", ""),
                "ENABLED_TOOLS": row_data.get("ENABLED_TOOLS", ""),
                # Completion result columns (from script execution) - all lowercase
                "script_model_response": f"ERROR: {str(e)}",
                "raw_conversation_history": None,
                "trajectory": None,
                "errors": [],
                "trajectory_time": trajectory_time,
                "num_retry": num_attempts,  # Use actual retry count even in error case
            }
            await self.write_result_to_csv(error_result, output_file)
            return error_result

    async def evaluate_dataset_async(
        self,
        df: pd.DataFrame,
        output_file: str,
        processed_task_ids: Optional[set] = None,
        max_concurrent_requests: int = 10,
    ) -> pd.DataFrame:
        """Evaluate entire dataset with max concurrency control"""
        semaphore = asyncio.Semaphore(max_concurrent_requests)

        async def controlled_task(row_data, task_index):
            async with semaphore:
                return await self.process_single_task(
                    row_data, output_file, task_index, len(df)
                )

        # Filter out already processed tasks
        tasks_to_process = []
        for idx, row in df.iterrows():
            task_id = row.get("TASK", idx)
            if processed_task_ids is None or task_id not in processed_task_ids:
                tasks_to_process.append((idx, row.to_dict()))

        if not tasks_to_process:
            logging.info("All tasks already processed!")
            return pd.DataFrame()

        logging.info(
            f"Processing {len(tasks_to_process)} tasks with max {max_concurrent_requests} concurrent requests..."
        )

        # Create async tasks
        async_tasks = []
        for i, (original_idx, row_data) in enumerate(tasks_to_process):
            task = controlled_task(row_data, i)
            async_tasks.append(task)

        # Execute all tasks concurrently
        start_time = time.time()
        results = await asyncio.gather(*async_tasks, return_exceptions=True)
        end_time = time.time()

        # Filter out exceptions and create DataFrame
        valid_results = [r for r in results if isinstance(r, dict)]

        logging.info(
            f"\n🎉 Completed {len(valid_results)} tasks in {end_time - start_time:.1f} seconds"
        )
        logging.info(
            f"⚡ Average time per task: {(end_time - start_time) / len(tasks_to_process):.1f} seconds"
        )

        return pd.DataFrame(valid_results)

        """Parse claims from string format"""
        if not claims_str or pd.isna(claims_str):
            return []

        try:
            # Try parsing as JSON list
            if claims_str.strip().startswith("["):
                return json.loads(claims_str)
            # Otherwise split by common delimiters
            else:
                # Split by semicolon or newline
                claims = []
                for delimiter in [";", "\n", ","]:
                    if delimiter in claims_str:
                        claims = [
                            claim.strip()
                            for claim in claims_str.split(delimiter)
                            if claim.strip()
                        ]
                        break

                if not claims:
                    claims = [claims_str.strip()]

                return claims
        except:
            return [claims_str.strip()] if claims_str.strip() else []


def run_extract_script(input_csv_path: str) -> str:
    """Run the extract_mcp_servers_per_task.py script and return the output JSON path"""
    script_path = Path(__file__).parent / "extract_mcp_servers_per_task.py"

    try:
        result = subprocess.run(
            [sys.executable, str(script_path), "--input", input_csv_path],
            capture_output=True,
            text=True,
            check=True,
        )

        logging.info(f"Extract script output: {result.stdout}")

        # Tool-map is always saved to completion_results/
        input_path = Path(input_csv_path)
        output_path = Path("completion_results") / f"{input_path.stem}-tool-map.json"
        return str(output_path)

    except subprocess.CalledProcessError as e:
        logging.error(f"Error running extract script: {e.stderr}")
        raise


def load_tool_map(tool_map_path: str) -> Dict[str, List[str]]:
    """Load the tool map JSON file"""
    try:
        with open(tool_map_path, "r") as f:
            return json.load(f)
    except Exception as e:
        logging.error(f"Error loading tool map from {tool_map_path}: {e}")
        raise


def filter_tasks_by_enabled_servers(
    df: pd.DataFrame, tool_map: Dict[str, List[str]], enabled_servers: List[str]
) -> tuple[pd.DataFrame, List[tuple[str, List[str]]]]:
    """Filter dataframe to only include tasks whose ground truth trajectories used servers you have enabled.

    Args:
        df: DataFrame with tasks
        tool_map: Dict mapping task_id -> list of servers used in that task's ground truth TRAJECTORY
        enabled_servers: List of servers you have API keys for (from /enabled-servers endpoint)

    Returns:
        Tuple of (filtered_df, excluded_tasks) where excluded_tasks is a list of (task_id, missing_servers)
    """
    filtered_indices = []
    excluded_tasks = []

    for idx, row in df.iterrows():
        task_id = str(row.get("TASK", idx))
        task_servers = tool_map.get(task_id, [])

        # Check if all required servers are enabled
        if all(server in enabled_servers for server in task_servers):
            filtered_indices.append(idx)
        else:
            # Track which servers are missing
            missing_servers = [s for s in task_servers if s not in enabled_servers]
            excluded_tasks.append((task_id, missing_servers))

    return df.iloc[filtered_indices].copy(), excluded_tasks


def write_exclusion_report(
    excluded_tasks: List[tuple[str, List[str]]],
    enabled_servers: List[str],
    input_source: str,
    output_file: str = "excluded_tasks.txt",
):
    """Write a detailed report of excluded tasks to a file.

    Args:
        excluded_tasks: List of (task_id, missing_servers) tuples
        enabled_servers: List of servers that were enabled
        input_source: Input file or HuggingFace dataset name
        output_file: Path to output file (default: excluded_tasks.txt)
    """
    from datetime import datetime

    with open(output_file, "w") as f:
        f.write("=" * 80 + "\n")
        f.write("EXCLUDED TASKS REPORT\n")
        f.write("=" * 80 + "\n\n")

        f.write(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"Input source: {input_source}\n")
        f.write(f"Filter enabled: --filter_for_enabled_servers\n\n")

        f.write("Reason for exclusion:\n")
        f.write(
            "Tasks were filtered out because their ground truth trajectories used MCP servers\n"
        )
        f.write("that are not currently enabled (missing API keys).\n\n")

        f.write(f"Available servers ({len(enabled_servers)}):\n")
        f.write(", ".join(sorted(enabled_servers)) + "\n\n")

        f.write("=" * 80 + "\n")
        f.write(f"EXCLUDED TASKS ({len(excluded_tasks)} total)\n")
        f.write("=" * 80 + "\n\n")

        if excluded_tasks:
            for task_id, missing_servers in excluded_tasks:
                f.write(f"Task {task_id}\n")
                f.write(f"  Missing servers: {', '.join(missing_servers)}\n\n")
        else:
            f.write("No tasks were excluded.\n")

        f.write("\n" + "=" * 80 + "\n")
        f.write("END OF REPORT\n")
        f.write("=" * 80 + "\n")

    logging.info(f"📄 Wrote exclusion report to {output_file}")


def get_enabled_servers() -> List[str]:
    """Get enabled servers by querying the agent-environment service.

    Supports both old and new response formats:
    - Old: {"enabled_servers": ["server1", "server2"], "count": 2}
    - New: {"servers": [["server1", "OK"], ["server2", "ERROR"]], "total": 2, ...}
    """
    mcp_server_url = os.getenv("MCP_SERVER_URL", "http://localhost:1984")

    try:
        response = requests.get(f"{mcp_server_url}/enabled-servers", timeout=10)
        response.raise_for_status()

        data = response.json()

        # New format: servers is list of [name, status] tuples
        if "servers" in data:
            enabled_servers = [
                name for name, status in data["servers"] if status == "OK"
            ]
        # Old format: enabled_servers is list of names
        else:
            enabled_servers = data.get("enabled_servers", [])

        logging.info(
            f"Retrieved {len(enabled_servers)} enabled servers from agent-environment service"
        )
        return enabled_servers

    except requests.exceptions.RequestException as e:
        logging.error(
            f"Failed to connect to agent-environment service at {mcp_server_url}: {e}"
        )
        raise RuntimeError(
            f"Cannot connect to agent-environment service at {mcp_server_url}. "
            f"Make sure the service is running before using --filter_for_enabled_servers"
        ) from e
    except Exception as e:
        logging.error(f"Error querying enabled servers: {e}")
        raise RuntimeError(
            f"Failed to get enabled servers from agent-environment service: {e}"
        ) from e


def parse_arguments():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description="MCP Evaluation Script",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "--model",
        required=True,
        help='LLM model to use for evaluation (e.g., "openai/gpt-4o")',
    )

    # Input source: exactly one of --input or --input_huggingface required
    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument(
        "--input", help="Input CSV file path containing tasks to evaluate"
    )
    input_group.add_argument(
        "--input_huggingface",
        help='HuggingFace dataset name (e.g., "ScaleAI/mcp-eval")',
    )

    parser.add_argument(
        "--output",
        required=True,
        help="Output CSV file name (will be saved to completion_results/ directory)",
    )
    parser.add_argument(
        "--no-filter",
        action="store_true",
        help="Disable filtering by enabled servers (by default, tasks requiring unavailable servers are skipped)",
    )
    parser.add_argument(
        "--num-tasks",
        type=int,
        default=None,
        help="Limit to first N tasks (useful for testing). If not specified, processes all tasks.",
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=10,
        help="Maximum concurrent API requests (default: 10, recommended range: 10-30)",
    )

    return parser.parse_args()


async def main():
    args = parse_arguments()

    # Prepend completion_results/ to output path
    output_csv = os.path.join("completion_results", args.output)

    # Load data from either CSV file or HuggingFace dataset
    if args.input:
        csv_filename = args.input
        if not os.path.exists(csv_filename):
            logging.error(f"Error: Could not find '{csv_filename}'")
            sys.exit(1)

        logging.info(f"Loading data from '{csv_filename}'...")
        df = pd.read_csv(csv_filename)
        if args.num_tasks:
            df = df.head(args.num_tasks)
    else:
        # Load from HuggingFace dataset
        logging.info(
            f"Loading data from HuggingFace dataset '{args.input_huggingface}'..."
        )
        dataset = load_dataset(args.input_huggingface, split="train")
        df = dataset.to_pandas()
        if args.num_tasks:
            df = df.head(args.num_tasks)

        # Set csv_filename for filtering logic (no need to save a separate GTFA file anymore)
        csv_filename = None  # Will be created as temp file if needed for filtering

    logging.info(f"Successfully loaded {len(df)} tasks")

    # Filter by enabled servers (default behavior, unless --no-filter is specified)
    filter_enabled = not args.no_filter

    if filter_enabled:
        # Get enabled servers from environment
        enabled_servers = get_enabled_servers()

        if not enabled_servers:
            logging.info(
                "🌐 No enabled servers returned from agent-environment service - all servers are enabled, skipping filter"
            )
        else:
            logging.info("🔍 Filtering tasks by enabled servers...")

            # Validate that TRAJECTORY column exists
            if "TRAJECTORY" not in df.columns:
                raise ValueError(
                    "❌ TRAJECTORY column is required when using --filter_for_enabled_servers.\n"
                    "   The filter works by checking which MCP servers were used in the ground truth trajectories.\n"
                    "   Your dataset is missing the TRAJECTORY column.\n"
                    "   Either add TRAJECTORY to your dataset or remove the --filter_for_enabled_servers flag."
                )

            # For HuggingFace datasets, save to a predictable CSV name for tool-map reuse
            if csv_filename is None:
                # Use HF dataset name as filename (e.g., "ScaleAI/mcp-eval" -> "ScaleAI-mcp-eval")
                hf_name = args.input_huggingface.replace("/", "-")
                csv_filename = f"completion_results/{hf_name}-dataset.csv"
                df.to_csv(csv_filename, index=False)
                logging.info(f"Saved HuggingFace dataset to: {csv_filename}")

            # Run extract script to generate tool map
            logging.info("Running extract_mcp_servers_per_task.py...")
            tool_map_path = run_extract_script(csv_filename)

            # Load tool map
            tool_map = load_tool_map(tool_map_path)

            logging.info(f"Enabled servers: {enabled_servers}")

            # Filter tasks
            original_count = len(df)
            df, excluded_tasks = filter_tasks_by_enabled_servers(
                df, tool_map, enabled_servers
            )
            filtered_count = len(df)

            logging.info(f"📊 Running {filtered_count} out of {original_count} tasks")

            # Only show skip warning if tasks were actually skipped
            skipped_count = original_count - filtered_count
            if skipped_count > 0:
                logging.info(
                    f"⚠️  Skipped {skipped_count} tasks because their ground truth trajectories used MCP servers you don't have API keys for"
                )

            # Write exclusion report
            if excluded_tasks:
                input_source = (
                    args.input_huggingface if args.input_huggingface else args.input
                )
                write_exclusion_report(excluded_tasks, enabled_servers, input_source)

            if filtered_count == 0:
                logging.error("No tasks remaining after filtering. Exiting.")
                sys.exit(1)

    # Check for existing results
    processed_ids = set()
    if os.path.exists(output_csv):
        try:
            existing_df = pd.read_csv(output_csv, usecols=["TASK"])
            processed_ids = set(existing_df["TASK"].astype(str))
            logging.info(
                f"Found {len(processed_ids)} already processed tasks. Skipping them."
            )
        except Exception as e:
            logging.warning(f"Warning: Could not read existing output: {e}")

    # Run evaluation
    async with AsyncMCPTrajectoryGenerator(args.model) as generator:
        results_df = await generator.evaluate_dataset_async(
            df, output_csv, processed_ids, args.concurrency
        )

    logging.info(f"\n📊 Results saved to: {output_csv}")
    if len(results_df) > 0:
        logging.info(f"📈 Total tasks processed: {len(results_df)}")
        script_responses = results_df["script_model_response"].notna().sum()
        logging.info(
            f"🎯 Tasks with script responses: {script_responses}/{len(results_df)}"
        )

    # Print column explanations
    print("\n" + "=" * 80)
    print("📋 OUTPUT FILE COLUMN DESCRIPTIONS")
    print("=" * 80)
    print("\n🔹 GROUND TRUTH COLUMNS (from input dataset - ALL CAPS):")
    print("  • TASK           - Unique task identifier")
    print("  • PROMPT         - The original task prompt/instruction")
    print("  • TRAJECTORY     - Expected tool calls (ground truth trajectory)")
    print("  • GTFA_CLAIMS    - Ground truth claims to evaluate against")
    print("  • ENABLED_TOOLS  - Tools that were available for this task")
    print("\n🔹 COMPLETION RESULT COLUMNS (from agent execution - lowercase):")
    print("  • script_model_response    - Response from the LLM in this run")
    print("  • raw_conversation_history - Full conversation history in JSON format")
    print("  • trajectory               - Tool calls made by the agent")
    print("  • errors                   - Any errors encountered during execution")
    print("  • trajectory_time          - Time taken to complete the task (seconds)")
    print("  • num_retry                - Number of retry attempts needed")
    print("\n💡 This file contains BOTH ground truth and completion data.")
    print("   Use it directly as input to the evaluation script (mcp_evals_scores.py)")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    # import debugpy
    # debugpy.listen(("0.0.0.0", 5678))
    # print("Waiting for debugger attach...")
    # debugpy.wait_for_client()
    # debugpy.breakpoint()
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("\nEvaluation interrupted by user.")
    except Exception as e:
        logging.error(f"Error: {e}")
        import traceback

        traceback.print_exc()
