"""Convert MCP eval CSV results + tool definitions into SFT training JSON format.

Usage:
    python convert_csv_to_sft.py \
        --input evaluation_results/scored_gpt52_system_prompt.csv \
        --tools ../../list-tools.json \
        --output sft_training_data.json \
        --system-prompt \
        --min-coverage 0.75
"""

import argparse
import json
import logging
import sys
from pathlib import Path

import pandas as pd

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "Role: You are a factual, tool-aware assistant connected to a variety of tools. "
    "Use the available tools to answer the user query. Do not ask the user for "
    "clarification; fully complete the task using the information provided in the prompt."
)

SCHEMA_KEEP_KEYS = {"type", "properties", "required"}


def clean_schema(schema: dict) -> dict:
    """Keep only type, properties, and required (recursively)."""
    cleaned = {}
    for key in SCHEMA_KEEP_KEYS:
        if key in schema:
            value = schema[key]
            if key == "properties" and isinstance(value, dict):
                cleaned[key] = {
                    prop_name: clean_schema(prop_val) if isinstance(prop_val, dict) else prop_val
                    for prop_name, prop_val in value.items()
                }
            else:
                cleaned[key] = value
    return cleaned


def load_tool_definitions(tools_path: str) -> dict[str, dict]:
    """Load list-tools.json and build a name -> definition mapping."""
    with open(tools_path) as f:
        tools = json.load(f)

    tool_map: dict[str, dict] = {}
    for tool in tools:
        name = tool["name"]
        raw_schema = tool.get("inputSchema", {})
        filtered_schema = clean_schema(raw_schema)
        tool_map[name] = {
            "type": "function",
            "function": {
                "name": name,
                "description": tool.get("description", ""),
                "parameters": json.dumps(filtered_schema, ensure_ascii=False),
            },
        }
    return tool_map


def transform_assistant_message(msg: dict) -> dict:
    """Transform a raw assistant message to SFT format.

    - Remove `original_message`
    - Strip `id` and `type` from each tool_call (keep only `function`)
    - Replace null content with ""
    - Remove `tool_calls` key entirely when absent
    """
    result: dict = {"role": "assistant"}

    result["content"] = msg.get("content") or ""

    raw_tool_calls = msg.get("tool_calls")
    if raw_tool_calls:
        cleaned_calls = []
        for tc in raw_tool_calls:
            fn = tc.get("function", {})
            cleaned_calls.append({
                "function": {
                    "name": fn.get("name", ""),
                    "arguments": fn.get("arguments", "{}"),
                }
            })
        result["tool_calls"] = cleaned_calls

    return result


def transform_tool_message(msg: dict) -> dict:
    """Transform a raw tool message to SFT format.

    - Remove `tool_call_id`
    - Keep content as-is (already a string)
    """
    return {
        "role": "tool",
        "content": msg.get("content", ""),
    }


def convert_row(
    row: pd.Series,
    tool_map: dict[str, dict],
    use_system_prompt: bool,
) -> dict | None:
    """Convert a single CSV row to an SFT training sample."""
    task_id = str(row.get("TASK", ""))
    prompt = row.get("PROMPT", "")
    raw_hist = row.get("raw_conversation_history")
    enabled_tools_str = row.get("ENABLED_TOOLS", "[]")

    if pd.isna(raw_hist) or not raw_hist:
        logger.warning(f"Skipping task {task_id}: no conversation history")
        return None

    response_str = str(row.get("script_model_response", ""))
    if response_str.startswith("ERROR:"):
        logger.warning(f"Skipping task {task_id}: error response")
        return None

    # --- messages ---
    messages = []
    if use_system_prompt:
        messages.append({"role": "system", "content": SYSTEM_PROMPT})
    messages.append({"role": "user", "content": prompt})

    conversation = json.loads(raw_hist)
    for msg in conversation:
        role = msg.get("role")
        if role == "assistant":
            messages.append(transform_assistant_message(msg))
        elif role == "tool":
            messages.append(transform_tool_message(msg))
        else:
            messages.append(msg)

    # --- tools ---
    try:
        enabled_names = json.loads(enabled_tools_str)
    except (json.JSONDecodeError, TypeError):
        enabled_names = []

    tools = []
    missing_tools = []
    for name in enabled_names:
        if name in tool_map:
            tools.append(tool_map[name])
        else:
            missing_tools.append(name)

    if missing_tools:
        logger.warning(
            f"Task {task_id}: {len(missing_tools)} tools not found in "
            f"tool definitions: {missing_tools}"
        )

    return {
        "id": task_id,
        "dataset_source": "",
        "messages": messages,
        "tools": tools,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Convert MCP eval CSV results to SFT training JSON"
    )
    parser.add_argument(
        "--input", required=True, help="Input CSV file path"
    )
    parser.add_argument(
        "--tools", required=True, help="Path to list-tools.json"
    )
    parser.add_argument(
        "--output", required=True, help="Output JSON file path"
    )
    parser.add_argument(
        "--system-prompt",
        action="store_true",
        default=False,
        help="Prepend the default system prompt to messages",
    )
    parser.add_argument(
        "--min-coverage",
        type=float,
        default=None,
        help="Only include rows with coverage_score >= this value (e.g. 0.75)",
    )
    args = parser.parse_args()

    if not Path(args.input).exists():
        logger.error(f"Input file not found: {args.input}")
        sys.exit(1)
    if not Path(args.tools).exists():
        logger.error(f"Tools file not found: {args.tools}")
        sys.exit(1)

    logger.info(f"Loading tool definitions from {args.tools}")
    tool_map = load_tool_definitions(args.tools)
    logger.info(f"Loaded {len(tool_map)} tool definitions")

    logger.info(f"Loading CSV from {args.input}")
    df = pd.read_csv(args.input)
    logger.info(f"Loaded {len(df)} rows")

    if args.min_coverage is not None:
        if "coverage_score" not in df.columns:
            logger.error("CSV does not have a 'coverage_score' column")
            sys.exit(1)
        before = len(df)
        df = df[df["coverage_score"] >= args.min_coverage].copy()
        logger.info(
            f"Filtered by coverage_score >= {args.min_coverage}: "
            f"{len(df)}/{before} rows kept"
        )

    samples = []
    skipped = 0
    for _, row in df.iterrows():
        sample = convert_row(row, tool_map, args.system_prompt)
        if sample is not None:
            samples.append(sample)
        else:
            skipped += 1

    logger.info(f"Converted {len(samples)} samples, skipped {skipped}")

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(samples, f, indent=2, ensure_ascii=False)

    logger.info(f"Wrote output to {args.output}")


if __name__ == "__main__":
    main()
