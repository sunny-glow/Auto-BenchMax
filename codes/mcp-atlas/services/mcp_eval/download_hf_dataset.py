#!/usr/bin/env python3
import os

# Proxy (set before importing datasets/huggingface libs)
os.environ.setdefault("HTTP_PROXY", "http://127.0.0.1:7890")
os.environ.setdefault("HTTPS_PROXY", "http://127.0.0.1:7890")

import argparse
from pathlib import Path

from datasets import load_dataset


def main():
    parser = argparse.ArgumentParser(
        description="Download a HuggingFace dataset and save it as local CSV."
    )
    parser.add_argument(
        "--dataset",
        default="ScaleAI/MCP-Atlas",
        help='HuggingFace dataset name, e.g. "ScaleAI/MCP-Atlas"',
    )
    parser.add_argument(
        "--split",
        default=None,
        help='Dataset split to load (e.g. "train"). If omitted, downloads all splits.',
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Output CSV file path (single split mode) or output directory (all-splits mode)",
    )
    parser.add_argument(
        "--cache-dir",
        default=None,
        help="Optional HuggingFace datasets cache directory",
    )
    args = parser.parse_args()

    dataset_slug = args.dataset.replace("/", "-")

    if args.split:
        print(f"Loading dataset: {args.dataset} (split={args.split})")
        dataset = load_dataset(args.dataset, split=args.split, cache_dir=args.cache_dir)
        df = dataset.to_pandas()

        default_name = (
            f"{dataset_slug}.csv"
            if args.split == "train"
            else f"{dataset_slug}-{args.split}.csv"
        )
        if args.output:
            output_path = Path(args.output)
            if output_path.exists() and output_path.is_dir():
                output_path = output_path / default_name
        else:
            output_path = Path("completion_results") / default_name

        output_path.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(output_path, index=False)

        print(f"Saved {len(df)} rows to: {output_path}")
    else:
        print(f"Loading dataset: {args.dataset} (all splits)")
        dataset_dict = load_dataset(args.dataset, cache_dir=args.cache_dir)
        split_items = list(dataset_dict.items())
        total_rows = 0

        # If dataset has only one split (e.g. train), save as "<dataset>.csv" (no "-train" suffix).
        if len(split_items) == 1:
            split_name, split_dataset = split_items[0]
            df = split_dataset.to_pandas()

            if args.output:
                output_arg = Path(args.output)
                if output_arg.exists() and output_arg.is_dir():
                    output_path = output_arg / f"{dataset_slug}.csv"
                elif output_arg.suffix.lower() == ".csv":
                    output_path = output_arg
                else:
                    output_path = output_arg / f"{dataset_slug}.csv"
            else:
                output_path = Path("completion_results") / f"{dataset_slug}.csv"

            output_path.parent.mkdir(parents=True, exist_ok=True)
            df.to_csv(output_path, index=False)
            total_rows += len(df)
            print(f"Saved {len(df)} rows ({split_name}) to: {output_path}")
        else:
            output_dir = Path(args.output) if args.output else Path("completion_results")
            if output_dir.suffix.lower() == ".csv":
                raise ValueError(
                    "Dataset has multiple splits. Please pass --output as a directory path."
                )
            output_dir.mkdir(parents=True, exist_ok=True)

            for split_name, split_dataset in split_items:
                df = split_dataset.to_pandas()
                split_output = output_dir / f"{dataset_slug}-{split_name}.csv"
                df.to_csv(split_output, index=False)
                total_rows += len(df)
                print(f"Saved {len(df)} rows to: {split_output}")

        print(f"Done. Total rows across all splits: {total_rows}")


if __name__ == "__main__":
    main()
