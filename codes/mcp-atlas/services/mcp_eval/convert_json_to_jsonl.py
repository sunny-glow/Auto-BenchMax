"""Convert a JSON array file to JSONL (one JSON object per line).

Usage:
    python convert_json_to_jsonl.py --input sft_training_data.json --output sft_training_data.jsonl
"""

import argparse
import json
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description="Convert JSON array to JSONL")
    parser.add_argument("--input", required=True, help="Input JSON file")
    parser.add_argument("--output", required=True, help="Output JSONL file")
    args = parser.parse_args()

    if not Path(args.input).exists():
        print(f"Error: {args.input} not found", file=sys.stderr)
        sys.exit(1)

    with open(args.input, encoding="utf-8") as f:
        data = json.load(f)

    with open(args.output, "w", encoding="utf-8") as f:
        for item in data:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")

    print(f"Wrote {len(data)} lines to {args.output}")


if __name__ == "__main__":
    main()
