#!/usr/bin/env python3
"""阶段 1：为每个 template 用 LLM(强模型) 生成候选任务。

只产 prompt（不产 claims —— claims 由阶段 3 从真实执行结果提取）。
关键约束：换实体/参数 + 换措辞，保持工具骨架和难度；实体必须是该领域真实存在、
能被给定工具查到的（真假交给阶段 2 实际执行兜底）；prompt 必须自包含、不向用户追问。

输出：eval_scripts/synth/candidates.csv （列：synth_id, ref_task_id, ENABLED_TOOLS, PROMPT）

Usage:
    cd services/mcp_eval
    export LLM_API_KEY=sk-xxx
    export LLM_BASE_URL=https://your-endpoint/v1
    uv run python eval_scripts/synth/2_generate_tasks.py \
        --templates eval_scripts/synth/templates.json \
        --output eval_scripts/synth/candidates.csv \
        --limit 2 --per-template 5      # 冒烟；全量则去掉这两个参数
"""

import argparse
import csv
import json
import os
import re
import sys
import time
from pathlib import Path

from openai import OpenAI

csv.field_size_limit(10**9)

LLM_BASE_URL = os.getenv("LLM_BASE_URL")
LLM_MODEL = os.getenv("LLM_GEN_MODEL", "GPT-5.5")

# 操作本地固定文件系统的 server：其"实体"是 docker /data 里的固定文件，不能编造路径。
# 这类 template 生成时必须把 env_inventory 注入 prompt，只允许在真实文件上换参数。
LOCAL_FS_SERVERS = {
    "filesystem", "cli-mcp-server", "git", "desktop-commander",
    "memory", "mcp-code-executor", "mcp-server-code-runner",
}

SYSTEM_PROMPT = """You are a data-synthesis assistant that creates NEW tool-use tasks by \
analogy to a reference task. You are given a reference task's user prompt, the ordered \
sequence of tool calls its expert solution used (the "skeleton"), and the reference \
answer's factual claims (as examples of what a good answer looks like).

Your job: produce N NEW user prompts that are SIMILAR IN STRUCTURE but about DIFFERENT \
real-world entities.

Hard rules:
1. Keep the same tool skeleton and difficulty — the new task must be solvable with the \
SAME set of tools/servers as the reference. Do not require any tool not implied by the reference.
2. SWAP the concrete entities/parameters (a different repository, book, museum artwork, \
city, paper, package, gene, etc.) and rephrase the wording/backstory. Do NOT just restate \
the reference with trivial edits.
3. CRITICAL — entities must be REAL and discoverable by these tools. Only use entities that \
genuinely exist in the real world and can be looked up via the given tools (e.g. a real \
published book, a real GitHub repo, a real Met Museum object, a real city). Never invent \
fictional names. When unsure an entity exists, pick a well-known one.
4. The prompt must be SELF-CONTAINED: include every detail needed to complete the task. \
The solver is instructed never to ask the user for clarification.
5. Ask for a concrete, checkable final answer (a number, date, name, difference, etc.), \
matching the style of the reference claims.
6. Maximize diversity across the N prompts — different entities, different domains where \
the tools allow it.

Return ONLY a JSON object: {"prompts": ["<prompt 1>", "<prompt 2>", ...]} with exactly N strings."""

# 追加给本地文件系统类任务的额外约束：只能用 env inventory 里真实存在的文件/目录。
LOCAL_FS_CONSTRAINT = """

IMPORTANT — this task operates on a FIXED local filesystem sandbox. You are given below the \
COMPLETE inventory of files and directories that actually exist under /data. You MUST NOT \
invent file paths, repository names, or directories. Every path you reference in a prompt \
MUST appear in (or be directly under) this inventory. To create variety, vary the QUESTION \
instead of the files: change which existing file/repo you ask about, which sub-directory, \
which metric/threshold/field, the phrasing and backstory — but keep every path real.

ENVIRONMENT INVENTORY (/data):
{inventory}"""


def build_user_prompt(template, n):
    actions = template.get("atomic_actions", [])
    skeleton_lines = []
    for a in actions:
        args = a.get("arguments", "")
        args_preview = args if len(args) <= 160 else args[:160] + "…"
        skeleton_lines.append(f"- {a['tool']}  args={args_preview}")
    skeleton = "\n".join(skeleton_lines) if skeleton_lines else "(no tool calls recorded)"

    claims = template.get("gtfa_claims", "")
    return f"""REFERENCE TASK
================
Servers available: {", ".join(template["servers"])}

User prompt:
{template["prompt"]}

Expert solution tool-call skeleton (in order):
{skeleton}

Reference answer claims (examples of a good final answer):
{claims}

================
Generate exactly {n} NEW self-contained prompts by analogy, following all hard rules. \
Return only the JSON object with a "prompts" array of {n} strings."""


def parse_prompts(content, n):
    """从模型返回里稳健地取出 prompts 列表。"""
    if not content:
        return []
    # 优先直接 JSON 解析
    text = content.strip()
    # 去掉 ```json ... ``` 包裹
    fence = re.match(r"^```(?:json)?\s*(.*?)\s*```$", text, re.DOTALL)
    if fence:
        text = fence.group(1).strip()
    try:
        obj = json.loads(text)
        prompts = obj.get("prompts") if isinstance(obj, dict) else obj
        if isinstance(prompts, list):
            return [str(p).strip() for p in prompts if str(p).strip()]
    except json.JSONDecodeError:
        pass
    # 兜底：抓第一个 {...} 块
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if m:
        try:
            obj = json.loads(m.group(0))
            prompts = obj.get("prompts") if isinstance(obj, dict) else None
            if isinstance(prompts, list):
                return [str(p).strip() for p in prompts if str(p).strip()]
        except json.JSONDecodeError:
            pass
    return []


def generate_for_template(client, template, n, inventory=None, max_retries=4):
    system = SYSTEM_PROMPT
    # 本地文件系统类：注入真实 /data 清单并加"禁止编路径"约束。
    if inventory and (set(template["servers"]) & LOCAL_FS_SERVERS):
        system = SYSTEM_PROMPT + LOCAL_FS_CONSTRAINT.format(inventory=inventory)
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": build_user_prompt(template, n)},
    ]
    for attempt in range(max_retries):
        try:
            resp = client.chat.completions.create(
                model=LLM_MODEL,
                messages=messages,
                stream=False,
            )
            content = resp.choices[0].message.content
            prompts = parse_prompts(content, n)
            if prompts:
                return prompts[:n]
            print(f"  [warn] empty/unparsable response (attempt {attempt+1}) for "
                  f"{template['ref_task_id']}", file=sys.stderr)
        except Exception as e:
            print(f"  [warn] API error (attempt {attempt+1}) for "
                  f"{template['ref_task_id']}: {e}", file=sys.stderr)
        time.sleep(min(2 ** attempt, 30))
    return []


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--templates", default="eval_scripts/synth/templates.json")
    ap.add_argument("--output", default="eval_scripts/synth/candidates.csv")
    ap.add_argument("--inventory", default="eval_scripts/synth/env_inventory.txt",
                    help="docker /data 真实文件清单，供本地文件系统类任务注入")
    ap.add_argument("--limit", type=int, default=None,
                    help="只处理前 N 个 template（冒烟用）")
    ap.add_argument("--per-template", type=int, default=None,
                    help="覆盖每个 template 的生成数量（默认用 template.quota）")
    ap.add_argument("--resume", action="store_true", default=True,
                    help="断点续跑：跳过已达配额的 template，未达的补齐（默认开启）")
    ap.add_argument("--no-resume", dest="resume", action="store_false",
                    help="关闭续跑，覆盖重写输出文件")
    args = ap.parse_args()

    api_key = os.getenv("LLM_API_KEY")
    if not api_key:
        print("Error: set LLM_API_KEY in env.", file=sys.stderr)
        sys.exit(1)

    templates = json.load(open(args.templates))
    if args.limit is not None:
        templates = templates[: args.limit]

    inventory = None
    if Path(args.inventory).exists():
        inventory = Path(args.inventory).read_text(encoding="utf-8").strip()
    else:
        print(f"[warn] inventory file not found: {args.inventory} — local-fs tasks "
              f"may invent paths. Run 0_dump_env_inventory.sh first.", file=sys.stderr)

    client = OpenAI(api_key=api_key, base_url=LLM_BASE_URL)

    Path(args.output).parent.mkdir(parents=True, exist_ok=True)

    # Resume：统计输出文件里每个 ref_task_id 已生成的数量，已达配额的 template 跳过，
    # 未达的从断点续生成。默认开启（若输出文件已存在则追加，否则新建）。
    done_counts = {}
    file_exists = Path(args.output).exists() and Path(args.output).stat().st_size > 0
    if args.resume and file_exists:
        with open(args.output, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                ref = row.get("ref_task_id", "")
                done_counts[ref] = done_counts.get(ref, 0) + 1
        print(f"[resume] found {sum(done_counts.values())} existing candidates "
              f"across {len(done_counts)} templates")

    total = sum(done_counts.values())
    mode = "a" if (args.resume and file_exists) else "w"
    with open(args.output, mode, newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f, fieldnames=["TASK", "ref_task_id", "ENABLED_TOOLS", "PROMPT"]
        )
        if mode == "w":
            writer.writeheader()
        for i, t in enumerate(templates):
            n = args.per_template if args.per_template is not None else t["quota"]
            already = done_counts.get(t["ref_task_id"], 0)
            remaining = n - already
            if remaining <= 0:
                print(f"[{i+1}/{len(templates)}] {t['ref_task_id']} -> skip "
                      f"(already {already}/{n})")
                continue
            print(f"[{i+1}/{len(templates)}] {t['ref_task_id']} "
                  f"({','.join(t['servers'])}) -> generating {remaining} "
                  f"(have {already}/{n})")
            prompts = generate_for_template(client, t, remaining, inventory=inventory)
            for j, p in enumerate(prompts):
                writer.writerow({
                    "TASK": f"{t['ref_task_id']}_syn{already + j:03d}",
                    "ref_task_id": t["ref_task_id"],
                    "ENABLED_TOOLS": t["enabled_tools"],
                    "PROMPT": p,
                })
                total += 1
            f.flush()

    print(f"\nTotal candidate tasks in {args.output}: {total}")


if __name__ == "__main__":
    main()
