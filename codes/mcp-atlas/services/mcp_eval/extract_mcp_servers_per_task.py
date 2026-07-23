#!/usr/bin/env python3
"""
Unique Tools Extractor
Extracts unique tool names from CSV files and outputs task ID + list of unique tools used by that task.
Saves the output as [input]-tool-map.json

Usage:
python extract_mcp_servers_per_task.py --input input.csv
"""

import argparse
import csv
import json
import sys
from pathlib import Path
from collections import defaultdict

# Tool name mappings - if original tool name (key) is found, replace with new mapped name (value),
# because the ENABLED_SERVERS uses the new names.
# To match: services/agent-environment/src/agent_environment/main.py
TOOL_NAME_MAPPINGS = {
    "brave_brave_web_search": "brave-search_brave_web_search",
    "MongoDB_aggregate": "mongodb_aggregate",
    "MongoDB_collection-schema": "mongodb_collection-schema",
    "MongoDB_count": "mongodb_count",
    "MongoDB_find": "mongodb_find",
    "MongoDB_list-collections": "mongodb_list-collections",
    "MongoDB_list-databases": "mongodb_list-databases",
}

MCP_SERVER_NAME_ONLY = True  # if True, only extract the MCP server name from the tool name, not the full tool name


def extract_unique_tools_from_csv(csv_file_path):
    """
    Extract unique tool names from a CSV file and output task ID + unique tools used.

    Args:
        csv_file_path (str): Path to the input CSV file

    Returns:
        dict: Dictionary with task_id as key and list of unique tools as value
    """
    csv_path = Path(csv_file_path)

    # Always save to completion_results/ directory
    output_file_path = Path("completion_results") / f"{csv_path.stem}-tool-map.json"

    # Check if file exists
    if not csv_path.exists():
        raise FileNotFoundError(f"CSV file '{csv_file_path}' not found.")

    # Increase field size limit to handle large fields
    csv.field_size_limit(sys.maxsize)

    task_tools = defaultdict(set)  # Use set to automatically handle uniqueness

    try:
        with open(csv_path, "r", newline="", encoding="utf-8") as csvfile:
            reader = csv.DictReader(csvfile)

            for row in reader:
                task_id = row.get("TASK", "")
                trajectory_data = row.get("TRAJECTORY", "")

                if not task_id:
                    continue

                if trajectory_data:
                    try:
                        # Parse the JSON trajectory
                        trajectory_json = json.loads(trajectory_data)

                        # Extract tool_calls from each message in the trajectory
                        for message in trajectory_json:
                            if isinstance(message, dict) and "tool_calls" in message:
                                tool_calls = message["tool_calls"]
                                if tool_calls:  # Only process if not empty
                                    for tool_call in tool_calls:
                                        if (
                                            isinstance(tool_call, dict)
                                            and "function" in tool_call
                                        ):
                                            function_info = tool_call["function"]
                                            if (
                                                isinstance(function_info, dict)
                                                and "name" in function_info
                                            ):
                                                tool_name = function_info["name"]
                                                # Apply tool name mapping if exists
                                                mapped_tool_name = (
                                                    TOOL_NAME_MAPPINGS.get(
                                                        tool_name, tool_name
                                                    )
                                                )
                                                if MCP_SERVER_NAME_ONLY:
                                                    mapped_tool_name = (
                                                        mapped_tool_name.split("_")[0]
                                                    )
                                                task_tools[task_id].add(
                                                    mapped_tool_name
                                                )

                    except json.JSONDecodeError as e:
                        print(
                            f"Warning: Could not parse JSON in TRAJECTORY for task {task_id}: {e}",
                            file=sys.stderr,
                        )
                        continue

    except Exception as e:
        raise Exception(f"Error reading CSV file: {e}")

    # Convert sets to sorted lists for consistent output
    result = {}
    for task_id, tools_set in task_tools.items():
        result[task_id] = sorted(list(tools_set))

    # Always write to JSON file and also print summary to stdout
    with open(output_file_path, "w", encoding="utf-8") as output_file:
        json.dump(result, output_file, indent=2, ensure_ascii=False)

    print(f"Results written to: {output_file_path}")
    print(f"Processed {len(result)} tasks")
    total_unique_tools = len(set().union(*[tools for tools in result.values()]))
    print(f"Total unique tools across all tasks: {total_unique_tools}")

    return result


def main():
    """Main function for command line usage"""
    parser = argparse.ArgumentParser(
        description="Extract unique tool names from CSV files and output task ID + list of unique tools used by that task.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "--input", "-i", required=True, help="Path to the input CSV file"
    )

    args = parser.parse_args()

    try:
        result = extract_unique_tools_from_csv(args.input)

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
