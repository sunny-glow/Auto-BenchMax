#!/usr/bin/env python3
"""Merge multiple JSONL files into one JSONL file.

Usage:
    python merge_jsonl.py \
        --inputs services/mcp_eval/training_data/a.jsonl services/mcp_eval/training_data/b.jsonl \
        --output services/mcp_eval/training_data/merged.jsonl
"""

import argparse
import json
import sys
from pathlib import Path


def merge_jsonl(inputs: list[Path], output: Path) -> tuple[int, int]:
    total_lines = 0
    total_written = 0

    output.parent.mkdir(parents=True, exist_ok=True)

    with output.open("w", encoding="utf-8") as out_f:
        for input_path in inputs:
            with input_path.open("r", encoding="utf-8") as in_f:
                for line_no, raw_line in enumerate(in_f, start=1):
                    total_lines += 1
                    line = raw_line.strip()
                    if not line:
                        continue

                    try:
                        json.loads(line)
                    except json.JSONDecodeError as exc:
                        raise ValueError(
                            f"Invalid JSON in {input_path} at line {line_no}: {exc}"
                        ) from exc

                    out_f.write(line + "\n")
                    total_written += 1

    return total_lines, total_written


def main() -> None:
    parser = argparse.ArgumentParser(description="Merge JSONL files into one.")
    parser.add_argument(
        "--inputs",
        nargs="+",
        required=True,
        help="Input JSONL file paths (merge order follows this list).",
    )
    parser.add_argument(
        "--output",
        required=True,
        help="Output merged JSONL file path.",
    )
    args = parser.parse_args()

    input_paths = [Path(p) for p in args.inputs]
    missing = [str(p) for p in input_paths if not p.exists()]
    if missing:
        print(f"Error: input file(s) not found: {', '.join(missing)}", file=sys.stderr)
        sys.exit(1)

    try:
        total_lines, total_written = merge_jsonl(input_paths, Path(args.output))
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)

    print(
        f"Merged {len(input_paths)} files. "
        f"Read {total_lines} lines, wrote {total_written} JSONL rows to {args.output}."
    )


if __name__ == "__main__":
    main()
