#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Convert part*.json conversation files into the SFT format used by "
            "sft_traj_9k_metadata_readable_clean_remove_reasoning_trainable_first3.json, "
            "keeping only messages and tools."
        )
    )
    parser.add_argument("input_path", help="Input directory or a single part*.json file.")
    parser.add_argument(
        "--output-dir",
        default="converted_sft_parts",
        help="Directory where converted files will be written.",
    )
    parser.add_argument(
        "--input-glob",
        default="part*.json",
        help="Glob used when input_path is a directory.",
    )
    parser.add_argument(
        "--max-bytes-per-file",
        type=int,
        default=200 * 1024 * 1024,
        help="Split output when a converted file would exceed this many bytes.",
    )
    parser.add_argument(
        "--indent",
        type=int,
        default=2,
        help="JSON indent for output files.",
    )
    return parser.parse_args()


def ensure_json_string(value: Any) -> str:
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False)


def transform_tool_call(tool_call: dict[str, Any], stats: dict[str, int]) -> dict[str, Any]:
    function = tool_call.get("function", {}) if isinstance(tool_call, dict) else {}
    arguments = function.get("arguments")
    stats["assistant_tool_call_arguments_converted"] += 1
    return {
        "function": {
            "name": function.get("name", ""),
            "arguments": ensure_json_string(arguments),
        }
    }


def transform_tool_definition(tool: dict[str, Any], stats: dict[str, int]) -> dict[str, Any]:
    function = tool.get("function", {}) if isinstance(tool, dict) else {}
    stats["tool_parameters_converted"] += 1
    return {
        "type": tool.get("type", "function"),
        "function": {
            "name": function.get("name", ""),
            "description": function.get("description", ""),
            "parameters": ensure_json_string(function.get("parameters")),
        },
    }


def transform_message(message: dict[str, Any], stats: dict[str, int]) -> dict[str, Any]:
    role = message.get("role", "")
    transformed: dict[str, Any] = {
        "role": role,
        "content": ensure_json_string(message.get("content")) if role == "tool" else message.get("content", ""),
    }

    if role == "tool":
        stats["tool_content_converted"] += 1

    tool_calls = message.get("tool_calls")
    if role == "assistant" and isinstance(tool_calls, list) and tool_calls:
        transformed["tool_calls"] = [
            transform_tool_call(tool_call, stats)
            for tool_call in tool_calls
            if isinstance(tool_call, dict)
        ]

    return transformed


def dedupe_tools(tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    deduped: list[dict[str, Any]] = []

    for tool in tools:
        signature = json.dumps(tool, ensure_ascii=False, sort_keys=True)
        if signature in seen:
            continue
        seen.add(signature)
        deduped.append(tool)

    return deduped


def transform_record(record: Any, stats: dict[str, int]) -> dict[str, Any]:
    conversations = record.get("conversations", []) if isinstance(record, dict) else []

    messages: list[dict[str, Any]] = []
    tools: list[dict[str, Any]] = []

    for message in conversations:
        if not isinstance(message, dict):
            continue

        messages.append(transform_message(message, stats))

        raw_tools = message.get("tools")
        if isinstance(raw_tools, list):
            for tool in raw_tools:
                if isinstance(tool, dict):
                    tools.append(transform_tool_definition(tool, stats))

    return {
        "messages": messages,
        "tools": dedupe_tools(tools),
    }


def serialized_size_bytes(value: Any, indent: int) -> int:
    rendered = json.dumps(value, ensure_ascii=False, indent=indent)
    return len(rendered.encode("utf-8"))


def write_chunk(
    records: list[dict[str, Any]],
    output_path: Path,
    indent: int,
) -> None:
    with output_path.open("w", encoding="utf-8") as handle:
        json.dump(records, handle, ensure_ascii=False, indent=indent)
        handle.write("\n")


def chunk_records(
    records: list[dict[str, Any]],
    max_bytes_per_file: int,
    indent: int,
) -> list[list[dict[str, Any]]]:
    if not records:
        return [[]]

    chunks: list[list[dict[str, Any]]] = []
    current_chunk: list[dict[str, Any]] = []

    for record in records:
        if not current_chunk:
            current_chunk.append(record)
            continue

        candidate = current_chunk + [record]
        if serialized_size_bytes(candidate, indent) <= max_bytes_per_file:
            current_chunk.append(record)
            continue

        chunks.append(current_chunk)
        current_chunk = [record]

    if current_chunk:
        chunks.append(current_chunk)

    return chunks


def iter_input_files(input_path: Path, input_glob: str) -> list[Path]:
    if input_path.is_file():
        return [input_path]
    return sorted(input_path.glob(input_glob))


def main() -> None:
    args = parse_args()
    input_path = Path(args.input_path).expanduser().resolve()
    output_dir = Path(args.output_dir).expanduser().resolve()

    if not input_path.exists():
        raise SystemExit(f"Input path does not exist: {input_path}")
    if args.max_bytes_per_file <= 0:
        raise SystemExit("--max-bytes-per-file must be greater than 0")

    input_files = iter_input_files(input_path, args.input_glob)
    if not input_files:
        raise SystemExit("No input files matched.")

    output_dir.mkdir(parents=True, exist_ok=True)

    manifest: dict[str, Any] = {
        "input_path": str(input_path),
        "output_dir": str(output_dir),
        "input_files": [],
        "summary": {
            "files_processed": 0,
            "records_processed": 0,
            "assistant_tool_call_arguments_converted": 0,
            "tool_content_converted": 0,
            "tool_parameters_converted": 0,
            "output_files_written": 0,
        },
    }

    for file_path in input_files:
        payload = json.loads(file_path.read_text(encoding="utf-8"))
        if not isinstance(payload, list):
            raise SystemExit(f"Expected list root in {file_path}, got {type(payload).__name__}")

        stats = {
            "assistant_tool_call_arguments_converted": 0,
            "tool_content_converted": 0,
            "tool_parameters_converted": 0,
        }

        converted_records = [transform_record(record, stats) for record in payload]
        chunks = chunk_records(converted_records, args.max_bytes_per_file, args.indent)

        written_files: list[str] = []
        if len(chunks) == 1:
            output_path = output_dir / file_path.name
            write_chunk(chunks[0], output_path, args.indent)
            written_files.append(str(output_path))
        else:
            for index, chunk in enumerate(chunks):
                output_path = output_dir / f"{file_path.stem}__{index:03d}.json"
                write_chunk(chunk, output_path, args.indent)
                written_files.append(str(output_path))

        manifest["input_files"].append(
            {
                "source_file": str(file_path),
                "records_processed": len(payload),
                "assistant_tool_call_arguments_converted": stats["assistant_tool_call_arguments_converted"],
                "tool_content_converted": stats["tool_content_converted"],
                "tool_parameters_converted": stats["tool_parameters_converted"],
                "output_files": written_files,
            }
        )

        manifest["summary"]["files_processed"] += 1
        manifest["summary"]["records_processed"] += len(payload)
        manifest["summary"]["assistant_tool_call_arguments_converted"] += stats[
            "assistant_tool_call_arguments_converted"
        ]
        manifest["summary"]["tool_content_converted"] += stats["tool_content_converted"]
        manifest["summary"]["tool_parameters_converted"] += stats["tool_parameters_converted"]
        manifest["summary"]["output_files_written"] += len(written_files)

    manifest_path = output_dir / "manifest.json"
    with manifest_path.open("w", encoding="utf-8") as handle:
        json.dump(manifest, handle, ensure_ascii=False, indent=2)
        handle.write("\n")

    print(f"Files processed: {manifest['summary']['files_processed']}")
    print(f"Records processed: {manifest['summary']['records_processed']}")
    print(
        "assistant tool_call arguments converted: "
        f"{manifest['summary']['assistant_tool_call_arguments_converted']}"
    )
    print(f"tool content converted: {manifest['summary']['tool_content_converted']}")
    print(f"tool parameters converted: {manifest['summary']['tool_parameters_converted']}")
    print(f"Output files written: {manifest['summary']['output_files_written']}")
    print(f"Manifest: {manifest_path}")


if __name__ == "__main__":
    import debugpy
    debugpy.listen(("0.0.0.0", 5678))
    print("Waiting for debugger attach...")
    debugpy.wait_for_client()
    debugpy.breakpoint()
    main()
