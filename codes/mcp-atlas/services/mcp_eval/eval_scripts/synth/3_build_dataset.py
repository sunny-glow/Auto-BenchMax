#!/usr/bin/env python3
"""阶段 3：从阶段 2 的 roll 结果提取 GTFA_CLAIMS + 有效性过滤，落最终 CSV。

对每个成功 roll 的候选任务，用 LLM(强模型) 从"prompt + 最终答案"里提取 3-6 条
原子事实 claim（对齐现有 GTFA_CLAIMS 风格）。答不出明确结论 / 声称查不到的任务丢弃。

输出：
  - eval_scripts/synth/synth_tasks.csv  （与 89 任务同 schema：TASK,ENABLED_TOOLS,PROMPT,GTFA_CLAIMS,TRAJECTORY）
  - eval_scripts/synth/discarded_report.txt （被丢弃任务及原因）

Usage:
    cd services/mcp_eval
    export LLM_API_KEY=sk-xxx
    export LLM_BASE_URL=https://your-endpoint/v1
    uv run python eval_scripts/synth/3_build_dataset.py \
        --roll-result completion_results/synth_roll_smoke.csv \
        --output eval_scripts/synth/synth_tasks.csv
"""

import argparse
import csv
import json
import os
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import pandas as pd
from openai import OpenAI

csv.field_size_limit(10**9)

LLM_BASE_URL = os.getenv("LLM_BASE_URL")
LLM_MODEL = os.getenv("LLM_GEN_MODEL", "GPT-5.5")

# 答案里出现这些短语，说明任务没查到实体 / 没得出结论 → 丢弃。
FAILURE_MARKERS = [
    "i couldn't find", "i could not find", "unable to find", "not found",
    "no results", "couldn't locate", "could not locate", "i don't have",
    "i do not have", "cannot determine", "can't determine", "no information",
    "unable to determine", "does not exist", "doesn't exist", "查无", "无法找到",
    "未找到", "无法确定",
]

CLAIM_SYSTEM = """You extract atomic, checkable factual claims from a model's final answer \
to a tool-use task. Each claim is a single self-contained fact stated as a declarative \
sentence (e.g. "The AssaultCube GitHub repository was created in 2013."). Include the key \
numbers/dates/names. These claims will be used as ground-truth to grade other models' answers.

Rules:
- Only extract facts that the answer actually asserts. Do NOT invent or infer beyond it.
- 3 to 6 claims. Prefer the most load-bearing facts (the ones the user asked for).
- Each claim must be independently verifiable and unambiguous.
- If the answer does NOT contain a concrete conclusion (it's vague, hedged, or says the \
information couldn't be found), return an empty list.

Return ONLY a JSON object: {"claims": ["...", "..."]}"""


def extract_final_answer(row):
    """取候选任务 roll 出的最终答案文本。"""
    resp = str(row.get("script_model_response", "") or "")
    return resp.strip()


def is_failure_answer(answer):
    if not answer or len(answer.strip()) < 20:
        return True, "empty/too-short answer"
    if answer.startswith("ERROR"):
        return True, "roll error"
    low = answer.lower()
    for marker in FAILURE_MARKERS:
        if marker in low:
            return True, f"failure marker: '{marker}'"
    return False, ""


def parse_claims(content):
    if not content:
        return []
    text = content.strip()
    fence = re.match(r"^```(?:json)?\s*(.*?)\s*```$", text, re.DOTALL)
    if fence:
        text = fence.group(1).strip()
    for candidate in (text, (re.search(r"\{.*\}", text, re.DOTALL) or [None])[0]):
        if not candidate:
            continue
        try:
            obj = json.loads(candidate)
            claims = obj.get("claims") if isinstance(obj, dict) else obj
            if isinstance(claims, list):
                return [str(c).strip() for c in claims if str(c).strip()]
        except (json.JSONDecodeError, TypeError):
            continue
    return []


def extract_claims(client, prompt, answer, max_retries=4):
    user = f"""TASK PROMPT:
{prompt}

MODEL'S FINAL ANSWER:
{answer}

Extract the atomic factual claims from the answer per the rules. Return only the JSON object."""
    messages = [
        {"role": "system", "content": CLAIM_SYSTEM},
        {"role": "user", "content": user},
    ]
    for attempt in range(max_retries):
        try:
            resp = client.chat.completions.create(
                model=LLM_MODEL, messages=messages, stream=False
            )
            return parse_claims(resp.choices[0].message.content)
        except Exception as e:
            print(f"  [warn] claim extraction error (attempt {attempt+1}): {e}",
                  file=sys.stderr)
            time.sleep(min(2 ** attempt, 30))
    return []


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--roll-result", required=True,
                    help="阶段 2 的 completion 结果 CSV（含 script_model_response, raw_conversation_history）")
    ap.add_argument("--output", default="eval_scripts/synth/synth_tasks.csv")
    ap.add_argument("--report", default="eval_scripts/synth/discarded_report.txt")
    ap.add_argument("--min-claims", type=int, default=3)
    ap.add_argument("--resume", action="store_true", default=True,
                    help="断点续跑：跳过输出文件中已处理的 TASK（默认开启）")
    ap.add_argument("--no-resume", dest="resume", action="store_false",
                    help="关闭续跑，覆盖重写输出文件")
    ap.add_argument("--concurrency", type=int, default=8,
                    help="并发提取 claim 的线程数")
    args = ap.parse_args()

    api_key = os.getenv("LLM_API_KEY")
    if not api_key:
        print("Error: set LLM_API_KEY in env.", file=sys.stderr)
        sys.exit(1)
    if not Path(args.roll_result).exists():
        print(f"Error: roll result not found: {args.roll_result}", file=sys.stderr)
        sys.exit(1)

    df = pd.read_csv(args.roll_result)
    client = OpenAI(api_key=api_key, base_url=LLM_BASE_URL)

    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    kept, discarded = 0, []
    # Resume：跳过输出文件里已处理过的 TASK（claim 提取是逐行 flush 的，可安全续跑）。
    processed = set()
    file_exists = Path(args.output).exists() and Path(args.output).stat().st_size > 0
    if args.resume and file_exists:
        with open(args.output, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                processed.add(str(row.get("TASK", "")))
        print(f"[resume] skipping {len(processed)} already-processed tasks")

    mode = "a" if (args.resume and file_exists) else "w"

    # 待处理任务（跳过已完成的）
    pending = []
    for idx, row in df.iterrows():
        task_id = str(row.get("TASK", idx))
        if task_id in processed:
            continue
        pending.append((idx, task_id, row))
    print(f"[info] {len(pending)} tasks to process with {args.concurrency} threads")

    def process_one(item):
        """返回 (task_id, result_row_or_None, discard_reason_or_None)"""
        _idx, task_id, row = item
        prompt = str(row.get("PROMPT", "") or "")
        answer = extract_final_answer(row)
        failed, reason = is_failure_answer(answer)
        if failed:
            return task_id, None, reason
        claims = extract_claims(client, prompt, answer)
        if len(claims) < args.min_claims:
            return task_id, None, f"only {len(claims)} claims extracted"
        trajectory = row.get("raw_conversation_history")
        if pd.isna(trajectory) or not trajectory:
            trajectory = row.get("trajectory", "")
        result_row = {
            "TASK": task_id,
            "ENABLED_TOOLS": row.get("ENABLED_TOOLS", "[]"),
            "PROMPT": prompt,
            "GTFA_CLAIMS": json.dumps(claims, ensure_ascii=False),
            "TRAJECTORY": trajectory if not pd.isna(trajectory) else "",
            "_n_claims": len(claims),
        }
        return task_id, result_row, None

    with open(args.output, mode, newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f, fieldnames=["TASK", "ENABLED_TOOLS", "PROMPT", "GTFA_CLAIMS", "TRAJECTORY"]
        )
        if mode == "w":
            writer.writeheader()

        done = 0
        with ThreadPoolExecutor(max_workers=args.concurrency) as ex:
            futures = {ex.submit(process_one, item): item for item in pending}
            for fut in as_completed(futures):
                task_id, result_row, reason = fut.result()
                done += 1
                if result_row is None:
                    discarded.append((task_id, reason))
                    continue
                n_claims = result_row.pop("_n_claims")
                writer.writerow(result_row)
                f.flush()
                kept += 1
                if done % 20 == 0 or kept <= 5:
                    print(f"[{done}/{len(pending)}] kept {task_id} ({n_claims} claims) | total kept {kept}")

    with open(args.report, "w", encoding="utf-8") as f:
        f.write("=" * 60 + "\n")
        f.write("DISCARDED SYNTHETIC TASKS\n")
        f.write("=" * 60 + "\n\n")
        f.write(f"Input: {args.roll_result}\n")
        f.write(f"Kept: {kept}   Discarded: {len(discarded)}\n\n")
        for tid, reason in discarded:
            f.write(f"Task {tid}\n  Reason: {reason}\n")

    print(f"\nKept {kept} tasks -> {args.output}")
    print(f"Discarded {len(discarded)} -> {args.report}")


if __name__ == "__main__":
    main()
