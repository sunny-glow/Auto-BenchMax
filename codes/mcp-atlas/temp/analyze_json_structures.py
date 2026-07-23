#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from statistics import mean
from pathlib import Path
from typing import Any, Iterable


def json_type_name(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, int) and not isinstance(value, bool):
        return "int"
    if isinstance(value, float):
        return "float"
    if isinstance(value, str):
        return "str"
    if isinstance(value, list):
        return "list"
    if isinstance(value, dict):
        return "object"
    return type(value).__name__


def truncate_text(value: Any, max_length: int = 120) -> str:
    rendered = json.dumps(value, ensure_ascii=False)
    if len(rendered) <= max_length:
        return rendered
    return rendered[: max_length - 3] + "..."


def canonicalize_keys(keys: Iterable[str]) -> str:
    return "|".join(sorted(keys))


def abbreviate_signature(signature: str, max_length: int = 220) -> str:
    if len(signature) <= max_length:
        return signature
    return signature[: max_length - 3] + "..."


def path_depth(path: str) -> int:
    return path.count(".") + path.count("[*]")


@dataclass
class PathStat:
    count: int = 0
    type_counts: Counter[str] = field(default_factory=Counter)
    examples: list[str] = field(default_factory=list)

    def add(self, value: Any, example_limit: int) -> None:
        self.count += 1
        self.type_counts[json_type_name(value)] += 1
        if len(self.examples) < example_limit:
            self.examples.append(truncate_text(value))


@dataclass
class SignatureStat:
    count: int = 0
    sample_files: list[str] = field(default_factory=list)

    def add(self, file_path: Path, sample_limit: int) -> None:
        self.count += 1
        if len(self.sample_files) < sample_limit:
            self.sample_files.append(str(file_path))


class StructureAnalyzer:
    def __init__(
        self,
        max_depth: int,
        array_sample_size: int,
        example_limit: int,
        sample_file_limit: int,
    ) -> None:
        self.max_depth = max_depth
        self.array_sample_size = array_sample_size
        self.example_limit = example_limit
        self.sample_file_limit = sample_file_limit

        self.path_stats: dict[str, PathStat] = defaultdict(PathStat)
        self.object_signatures: dict[str, SignatureStat] = defaultdict(SignatureStat)
        self.record_signatures: dict[str, SignatureStat] = defaultdict(SignatureStat)
        self.root_signatures: dict[str, SignatureStat] = defaultdict(SignatureStat)

        self.category_counts: Counter[str] = Counter()
        self.root_type_counts: Counter[str] = Counter()
        self.parse_errors: list[dict[str, str]] = []
        self.file_reports: list[dict[str, Any]] = []
        self.conversation_turn_counts: list[int] = []
        self.conversation_role_counts: Counter[str] = Counter()
        self.message_field_counts: Counter[str] = Counter()
        self.records_with_conversations = 0
        self.records_with_reasoning_content = 0
        self.messages_with_reasoning_content = 0

    def analyze_path(self, target: Path) -> dict[str, Any]:
        files = sorted(target.rglob("*.json"))
        for file_path in files:
            self._analyze_file(file_path)

        return self._build_report(target, files)

    def _analyze_file(self, file_path: Path) -> None:
        try:
            payload = self._load_json(file_path)
        except Exception as exc:  # pragma: no cover - surfaced in report
            self.parse_errors.append(
                {
                    "file": str(file_path),
                    "error_type": type(exc).__name__,
                    "message": str(exc),
                }
            )
            return

        category = self._classify_payload(payload)
        root_type = json_type_name(payload)
        root_signature = self._root_signature(payload)

        self.category_counts[category] += 1
        self.root_type_counts[root_type] += 1
        self.root_signatures[root_signature].add(file_path, self.sample_file_limit)

        self._walk(payload, "$", file_path, 0)
        self._collect_specialized_stats(payload)

        self.file_reports.append(
            {
                "file": str(file_path),
                "category": category,
                "root_type": root_type,
                "root_signature": root_signature,
                "top_level_keys": sorted(payload.keys()) if isinstance(payload, dict) else None,
                "list_length": len(payload) if isinstance(payload, list) else None,
            }
        )

    def _load_json(self, file_path: Path) -> Any:
        with file_path.open("r", encoding="utf-8") as handle:
            return json.load(handle)

    def _walk(self, value: Any, path: str, file_path: Path, depth: int) -> None:
        self.path_stats[path].add(value, self.example_limit)

        if depth >= self.max_depth:
            return

        if isinstance(value, dict):
            signature = canonicalize_keys(value.keys())
            self.object_signatures[signature].add(file_path, self.sample_file_limit)
            if path == "$":
                self.record_signatures[f"root_object::{signature}"].add(
                    file_path, self.sample_file_limit
                )
            for key, nested in value.items():
                self._walk(nested, f"{path}.{key}", file_path, depth + 1)
            return

        if isinstance(value, list):
            sampled = value[: self.array_sample_size]
            item_type_counter = Counter(json_type_name(item) for item in sampled)
            if item_type_counter:
                summary_path = f"{path}[]"
                self.path_stats[summary_path].type_counts.update(item_type_counter)
                self.path_stats[summary_path].count += len(sampled)
            for item in sampled:
                if isinstance(item, dict):
                    signature = canonicalize_keys(item.keys())
                    self.record_signatures[signature].add(file_path, self.sample_file_limit)
                self._walk(item, f"{path}[*]", file_path, depth + 1)

    def _root_signature(self, payload: Any) -> str:
        if isinstance(payload, dict):
            return f"object:{canonicalize_keys(payload.keys())}"
        if isinstance(payload, list):
            sampled = payload[: self.array_sample_size]
            item_types = sorted({json_type_name(item) for item in sampled})
            if sampled and all(isinstance(item, dict) for item in sampled):
                key_signatures = sorted(
                    {canonicalize_keys(item.keys()) for item in sampled if isinstance(item, dict)}
                )
                return f"list<object>:{' || '.join(key_signatures)}"
            return f"list<{','.join(item_types) or 'empty'}>"
        return json_type_name(payload)

    def _classify_payload(self, payload: Any) -> str:
        features = self._collect_features(payload)

        if features["has_conversations"]:
            if features["has_tool_calls"] or features["has_tool_results"]:
                return "conversation_with_tool_use"
            return "conversation"
        if features["has_chosen_rejected"]:
            return "preference_or_ranking"
        if features["has_tool_calls"] or features["has_tool_results"]:
            if features["has_messages"]:
                return "agent_tool_use_conversation"
            return "agent_tool_use"
        if features["has_messages"]:
            return "conversation"
        if features["has_prompt_completion"]:
            return "instruction_or_completion"
        if features["has_events"]:
            return "event_log"
        return "unknown"

    def _collect_features(self, payload: Any) -> dict[str, bool]:
        flags = {
            "has_conversations": False,
            "has_messages": False,
            "has_tool_calls": False,
            "has_tool_results": False,
            "has_prompt_completion": False,
            "has_chosen_rejected": False,
            "has_events": False,
        }

        def visit(node: Any, depth: int) -> None:
            if depth > 4:
                return
            if isinstance(node, dict):
                keys = set(node.keys())
                if {"conversations"} & keys:
                    conversations = node.get("conversations")
                    if isinstance(conversations, list):
                        flags["has_conversations"] = True
                if {"messages"} & keys:
                    messages = node.get("messages")
                    if isinstance(messages, list):
                        flags["has_messages"] = True
                if {"tool_calls", "function_call", "tool_use", "tool_name"} & keys:
                    flags["has_tool_calls"] = True
                if {"tool_result", "tool_results", "function_response", "tool_output"} & keys:
                    flags["has_tool_results"] = True
                if {"prompt", "completion"} <= keys or {"instruction", "output"} <= keys:
                    flags["has_prompt_completion"] = True
                if {"chosen", "rejected"} <= keys:
                    flags["has_chosen_rejected"] = True
                if {"events"} & keys:
                    flags["has_events"] = True
                role = node.get("role")
                if role in {"tool", "function"}:
                    flags["has_tool_results"] = True
                if role == "assistant" and (
                    "tool_calls" in node or "function_call" in node or "tool_use" in node
                ):
                    flags["has_tool_calls"] = True
                for nested in node.values():
                    visit(nested, depth + 1)
                return

            if isinstance(node, list):
                for item in node[: self.array_sample_size]:
                    visit(item, depth + 1)

        visit(payload, 0)
        return flags

    def _collect_specialized_stats(self, payload: Any) -> None:
        records = payload if isinstance(payload, list) else [payload]

        for record in records[: self.array_sample_size]:
            if not isinstance(record, dict):
                continue

            conversations = record.get("conversations")
            if not isinstance(conversations, list):
                continue

            self.records_with_conversations += 1
            self.conversation_turn_counts.append(len(conversations))

            record_has_reasoning = False
            for message in conversations[: self.array_sample_size]:
                if not isinstance(message, dict):
                    continue
                role = message.get("role")
                if isinstance(role, str):
                    self.conversation_role_counts[role] += 1
                self.message_field_counts.update(message.keys())
                if "reasoning_content" in message and message.get("reasoning_content") not in (
                    None,
                    "",
                ):
                    self.messages_with_reasoning_content += 1
                    record_has_reasoning = True

            if record_has_reasoning:
                self.records_with_reasoning_content += 1

    def _conversation_summary(self) -> dict[str, Any] | None:
        if not self.records_with_conversations:
            return None

        turn_counts = self.conversation_turn_counts
        return {
            "records_with_conversations": self.records_with_conversations,
            "records_with_reasoning_content": self.records_with_reasoning_content,
            "messages_with_reasoning_content": self.messages_with_reasoning_content,
            "role_counts": dict(self.conversation_role_counts.most_common()),
            "message_field_counts": dict(self.message_field_counts.most_common()),
            "turn_count": {
                "min": min(turn_counts),
                "max": max(turn_counts),
                "avg": round(mean(turn_counts), 2),
            },
        }

    def _build_report(self, target: Path, files: list[Path]) -> dict[str, Any]:
        path_summary = [
            {
                "path": path,
                "occurrences": stat.count,
                "types": dict(stat.type_counts.most_common()),
                "examples": stat.examples,
            }
            for path, stat in sorted(
                self.path_stats.items(),
                key=lambda item: (-item[1].count, path_depth(item[0]), item[0]),
            )
        ]

        object_signature_summary = [
            {
                "signature": signature,
                "display_signature": abbreviate_signature(signature),
                "count": stat.count,
                "sample_files": stat.sample_files,
            }
            for signature, stat in sorted(
                self.object_signatures.items(), key=lambda item: (-item[1].count, item[0])
            )
        ]

        record_signature_summary = [
            {
                "signature": signature,
                "display_signature": abbreviate_signature(signature),
                "count": stat.count,
                "sample_files": stat.sample_files,
            }
            for signature, stat in sorted(
                self.record_signatures.items(), key=lambda item: (-item[1].count, item[0])
            )
        ]

        root_signature_summary = [
            {
                "signature": signature,
                "display_signature": abbreviate_signature(signature),
                "count": stat.count,
                "sample_files": stat.sample_files,
            }
            for signature, stat in sorted(
                self.root_signatures.items(), key=lambda item: (-item[1].count, item[0])
            )
        ]

        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "target_directory": str(target.resolve()),
            "summary": {
                "json_files_found": len(files),
                "json_files_parsed": len(self.file_reports),
                "parse_errors": len(self.parse_errors),
                "category_counts": dict(self.category_counts.most_common()),
                "root_type_counts": dict(self.root_type_counts.most_common()),
            },
            "conversation_summary": self._conversation_summary(),
            "root_signatures": root_signature_summary,
            "record_signatures": record_signature_summary,
            "object_signatures": object_signature_summary,
            "path_summary": path_summary,
            "files": sorted(self.file_reports, key=lambda item: item["file"]),
            "parse_errors_detail": self.parse_errors,
        }


def build_markdown(report: dict[str, Any], top_n: int) -> str:
    summary = report["summary"]
    conversation_summary = report.get("conversation_summary")
    lines = [
        "# JSON Structure Analysis",
        "",
        f"- Target directory: `{report['target_directory']}`",
        f"- Generated at (UTC): `{report['generated_at']}`",
        f"- JSON files found: `{summary['json_files_found']}`",
        f"- JSON files parsed: `{summary['json_files_parsed']}`",
        f"- Parse errors: `{summary['parse_errors']}`",
        "",
        "## Category Counts",
        "",
    ]

    category_counts = summary["category_counts"] or {}
    if category_counts:
        for category, count in category_counts.items():
            lines.append(f"- `{category}`: {count}")
    else:
        lines.append("- None")

    if conversation_summary:
        lines.extend(["", "## Conversation Summary", ""])
        lines.append(
            f"- Records with `conversations`: {conversation_summary['records_with_conversations']}"
        )
        lines.append(
            f"- Records with `reasoning_content`: {conversation_summary['records_with_reasoning_content']}"
        )
        lines.append(
            f"- Messages with `reasoning_content`: {conversation_summary['messages_with_reasoning_content']}"
        )
        turn_count = conversation_summary["turn_count"]
        lines.append(
            f"- Turns per conversation: min={turn_count['min']} avg={turn_count['avg']} max={turn_count['max']}"
        )
        role_counts = ", ".join(
            f"{role}:{count}" for role, count in conversation_summary["role_counts"].items()
        )
        lines.append(f"- Role counts: {role_counts or 'None'}")

    lines.extend(["", "## Root Signatures", ""])
    for entry in report["root_signatures"][:top_n]:
        lines.append(f"- `{entry['display_signature']}`: {entry['count']}")

    lines.extend(["", "## Top Record Signatures", ""])
    for entry in report["record_signatures"][:top_n]:
        lines.append(f"- `{entry['display_signature']}`: {entry['count']}")

    lines.extend(["", "## High Frequency Paths", ""])
    for entry in report["path_summary"][:top_n]:
        type_summary = ", ".join(f"{key}:{value}" for key, value in entry["types"].items())
        lines.append(f"- `{entry['path']}`: {entry['occurrences']} ({type_summary})")

    parse_errors = report["parse_errors_detail"]
    if parse_errors:
        lines.extend(["", "## Parse Errors", ""])
        for entry in parse_errors[:top_n]:
            lines.append(
                f"- `{entry['file']}`: `{entry['error_type']}` - {entry['message']}"
            )

    return "\n".join(lines) + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Analyze the structure of a directory of JSON files."
    )
    parser.add_argument("target", help="Directory to scan recursively for *.json files.")
    parser.add_argument(
        "--output-dir",
        default="json_structure_report",
        help="Directory where analysis outputs will be written.",
    )
    parser.add_argument(
        "--max-depth",
        type=int,
        default=8,
        help="Maximum traversal depth when collecting field paths.",
    )
    parser.add_argument(
        "--array-sample-size",
        type=int,
        default=50,
        help="Maximum number of items sampled from each array.",
    )
    parser.add_argument(
        "--example-limit",
        type=int,
        default=3,
        help="Number of example values retained per path.",
    )
    parser.add_argument(
        "--sample-file-limit",
        type=int,
        default=5,
        help="Number of sample files retained per signature.",
    )
    parser.add_argument(
        "--top-n",
        type=int,
        default=30,
        help="Number of top entries shown in the markdown summary and console output.",
    )
    return parser.parse_args()


def print_console_summary(report: dict[str, Any], top_n: int) -> None:
    summary = report["summary"]
    conversation_summary = report.get("conversation_summary")
    print(f"Target: {report['target_directory']}")
    print(f"JSON files found: {summary['json_files_found']}")
    print(f"JSON files parsed: {summary['json_files_parsed']}")
    print(f"Parse errors: {summary['parse_errors']}")
    print("")

    print("Category counts:")
    if summary["category_counts"]:
        for category, count in summary["category_counts"].items():
            print(f"  - {category}: {count}")
    else:
        print("  - none")

    if conversation_summary:
        print("")
        print("Conversation summary:")
        print(
            "  - records with conversations: "
            f"{conversation_summary['records_with_conversations']}"
        )
        print(
            "  - records with reasoning_content: "
            f"{conversation_summary['records_with_reasoning_content']}"
        )
        print(
            "  - messages with reasoning_content: "
            f"{conversation_summary['messages_with_reasoning_content']}"
        )
        turn_count = conversation_summary["turn_count"]
        print(
            "  - turns per conversation: "
            f"min={turn_count['min']} avg={turn_count['avg']} max={turn_count['max']}"
        )
        role_counts = " ".join(
            f"{role}:{count}" for role, count in conversation_summary["role_counts"].items()
        )
        print(f"  - role counts: {role_counts or 'none'}")

    print("")
    print("Top root signatures:")
    for entry in report["root_signatures"][:top_n]:
        print(f"  - {entry['count']:>5}  {entry['display_signature']}")

    print("")
    print("Top record signatures:")
    for entry in report["record_signatures"][:top_n]:
        print(f"  - {entry['count']:>5}  {entry['display_signature']}")

    print("")
    print("Top paths:")
    for entry in report["path_summary"][:top_n]:
        type_summary = ", ".join(f"{key}:{value}" for key, value in entry["types"].items())
        print(f"  - {entry['occurrences']:>5}  {entry['path']} [{type_summary}]")


def main() -> None:
    args = parse_args()
    target = Path(args.target).expanduser().resolve()
    output_dir = Path(args.output_dir).expanduser().resolve()

    if not target.exists():
        raise SystemExit(f"Target directory does not exist: {target}")
    if not target.is_dir():
        raise SystemExit(f"Target path is not a directory: {target}")

    analyzer = StructureAnalyzer(
        max_depth=args.max_depth,
        array_sample_size=args.array_sample_size,
        example_limit=args.example_limit,
        sample_file_limit=args.sample_file_limit,
    )
    report = analyzer.analyze_path(target)

    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "report.json"
    markdown_path = output_dir / "report.md"

    with json_path.open("w", encoding="utf-8") as handle:
        json.dump(report, handle, ensure_ascii=False, indent=2)

    markdown = build_markdown(report, args.top_n)
    with markdown_path.open("w", encoding="utf-8") as handle:
        handle.write(markdown)

    print_console_summary(report, args.top_n)
    print("")
    print(f"Detailed JSON report written to: {json_path}")
    print(f"Markdown summary written to: {markdown_path}")


if __name__ == "__main__":
    main()
