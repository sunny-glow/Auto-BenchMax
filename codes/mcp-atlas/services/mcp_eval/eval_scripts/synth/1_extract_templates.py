#!/usr/bin/env python3
"""阶段 0：从 89 个参考任务抽取"模版"。

重建 benchmark 中"ground-truth 轨迹所需 server 全部在线"的可运行子集，
为每个参考任务抽出一条 template 记录（prompt / enabled_tools / 原子动作序列 / claims），
并按 server 稀有度为每个 template 计算生成配额（per-template quota）。

输出：eval_scripts/synth/templates.json

Usage:
    cd services/mcp_eval
    uv run python eval_scripts/synth/1_extract_templates.py \
        --dataset completion_results/ScaleAI-MCP-Atlas-dataset.csv \
        --tool-map completion_results/ScaleAI-MCP-Atlas-dataset-tool-map.json \
        --target-total 2670 \
        --output eval_scripts/synth/templates.json
"""

import argparse
import csv
import json
import sys
from collections import Counter
from pathlib import Path

csv.field_size_limit(10**9)

# 当前在线的 20 个免 key server（来自 excluded_tasks.txt 顶部 / mcp_client.py DEFAULT_SERVERS）。
DEFAULT_ENABLED_SERVERS = [
    "arxiv", "calculator", "cli-mcp-server", "clinicaltrialsgov-mcp-server",
    "context7", "ddg-search", "desktop-commander", "fetch", "filesystem", "git",
    "mcp-code-executor", "mcp-server-code-runner", "memory", "met-museum",
    "open-library", "osm-mcp-server", "pubmed", "weather", "whois", "wikipedia",
]


def extract_atomic_actions(trajectory_str):
    """从 ground-truth TRAJECTORY 抽出有序的 (tool_name, arguments) 原子动作列表。

    逻辑对齐 extract_mcp_servers_per_task.py：遍历 assistant 消息里的 tool_calls。
    """
    actions = []
    try:
        trajectory = json.loads(trajectory_str)
    except (json.JSONDecodeError, TypeError):
        return actions
    for msg in trajectory:
        if not isinstance(msg, dict):
            continue
        for tc in msg.get("tool_calls") or []:
            fn = tc.get("function") if isinstance(tc, dict) else None
            if isinstance(fn, dict) and "name" in fn:
                actions.append({
                    "tool": fn["name"],
                    "arguments": fn.get("arguments", "{}"),
                })
    return actions


def compute_quotas(templates, target_total, quota_cap):
    """按 server 稀有度分配 per-template 配额。

    稀有 server（参考任务少）的 template 分到更高的单任务权重，
    使稀有环境不至于被淹没；常见 server 的 template 权重低（本就有很多参考）。
    每个 template 的权重 = 其涉及 server 的 (1/该 server 参考任务数) 之和，
    再把权重归一化到 target_total 并取整（下限 1，上限 quota_cap）。
    """
    server_freq = Counter()
    for t in templates:
        for s in t["servers"]:
            server_freq[s] += 1

    raw_weights = []
    for t in templates:
        w = sum(1.0 / server_freq[s] for s in t["servers"]) if t["servers"] else 1.0
        raw_weights.append(w)

    total_w = sum(raw_weights) or 1.0
    for t, w in zip(templates, raw_weights):
        t["quota"] = min(quota_cap, max(1, round(target_total * w / total_w)))
    return server_freq


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", default="completion_results/ScaleAI-MCP-Atlas-dataset.csv")
    ap.add_argument("--tool-map", default="completion_results/ScaleAI-MCP-Atlas-dataset-tool-map.json")
    ap.add_argument("--target-total", type=int, default=2670,
                    help="全部 template 生成的候选任务总数目标（按稀有度加权分配）")
    ap.add_argument("--quota-cap", type=int, default=45,
                    help="单个 template 配额上限，防止稀有 server 组合被过度加权导致同质化")
    ap.add_argument("--output", default="eval_scripts/synth/templates.json")
    args = ap.parse_args()

    if not Path(args.dataset).exists():
        print(f"Error: dataset not found: {args.dataset}", file=sys.stderr)
        sys.exit(1)
    if not Path(args.tool_map).exists():
        print(f"Error: tool-map not found: {args.tool_map}", file=sys.stderr)
        sys.exit(1)

    tool_map = json.load(open(args.tool_map))
    rows = {r["TASK"]: r for r in csv.DictReader(open(args.dataset))}

    enabled = set(DEFAULT_ENABLED_SERVERS)
    templates = []
    for task_id, servers in tool_map.items():
        if not servers or not all(s in enabled for s in servers):
            continue  # 复用已确认的过滤逻辑：所有 server 必须在线
        row = rows.get(task_id)
        if row is None:
            continue
        templates.append({
            "ref_task_id": task_id,
            "servers": sorted(servers),
            "enabled_tools": row.get("ENABLED_TOOLS", "[]"),
            "prompt": row.get("PROMPT", ""),
            "gtfa_claims": row.get("GTFA_CLAIMS", ""),
            "atomic_actions": extract_atomic_actions(row.get("TRAJECTORY", "[]")),
        })

    server_freq = compute_quotas(templates, args.target_total, args.quota_cap)

    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(templates, f, indent=2, ensure_ascii=False)

    print(f"Extracted {len(templates)} templates -> {args.output}")
    print(f"Total quota (candidates to generate): {sum(t['quota'] for t in templates)}")
    print(f"Quota range per template: "
          f"{min(t['quota'] for t in templates)}..{max(t['quota'] for t in templates)}")
    print(f"Server frequency (ref tasks): {dict(server_freq.most_common())}")


if __name__ == "__main__":
    main()
