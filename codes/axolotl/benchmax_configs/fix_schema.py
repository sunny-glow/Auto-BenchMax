#!/usr/bin/env python3
"""
Fix schema inconsistencies in parquet files by:
1. Loading all parquet files
2. Removing function_calls and functions fields from messages
3. Saving with consistent schema
"""

import json
import os
from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from tqdm import tqdm


def clean_message(msg):
    """Remove function_calls and functions fields from message."""
    return {
        "role": msg.get("role", ""),
        "content": msg.get("content") or ""
    }


def clean_messages(messages):
    """Clean all messages in a conversation."""
    if isinstance(messages, str):
        messages = json.loads(messages)
    return [clean_message(m) for m in messages]


def process_dataset(input_dir: Path, output_dir: Path):
    """Process all parquet files and save with consistent schema."""
    input_data_dir = input_dir / "data"
    output_data_dir = output_dir / "data"
    output_data_dir.mkdir(parents=True, exist_ok=True)

    parquet_files = sorted(input_data_dir.glob("*.parquet"))
    print(f"Found {len(parquet_files)} parquet files")

    all_rows = []

    # Load all data
    for pf in tqdm(parquet_files, desc="Loading parquet files"):
        df = pd.read_parquet(pf)
        for idx in range(len(df)):
            row = df.iloc[idx]
            messages = row["messages"]

            # Clean messages
            cleaned_messages = clean_messages(messages)

            all_rows.append({
                "id": row.get("id", ""),
                "source": row.get("source") or "",
                "messages": json.dumps(cleaned_messages, ensure_ascii=False)
            })

    print(f"Total rows: {len(all_rows)}")

    # Save in chunks
    chunk_size = len(all_rows) // 8
    for i in range(8):
        start = i * chunk_size
        end = start + chunk_size if i < 7 else len(all_rows)
        chunk = all_rows[start:end]

        df = pd.DataFrame(chunk)
        output_file = output_data_dir / f"train-{i:05d}-of-00008.parquet"
        df.to_parquet(output_file, index=False)
        print(f"Saved {output_file} with {len(chunk)} rows")


def main():
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--input_dir", type=str, required=True)
    parser.add_argument("--output_dir", type=str, required=True)
    args = parser.parse_args()

    input_dir = Path(args.input_dir)
    output_dir = Path(args.output_dir)

    process_dataset(input_dir, output_dir)
    print(f"\nDone! Fixed dataset saved to: {output_dir}")


if __name__ == "__main__":
    main()
