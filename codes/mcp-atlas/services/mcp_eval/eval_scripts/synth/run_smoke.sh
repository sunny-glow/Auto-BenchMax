#!/usr/bin/env bash
# 小批冒烟：串起合成 pipeline 的全部 4 阶段（2 template × 5 候选）。
# 前置：make run-docker（:1984）与 make run-mcp-completion（:3000）都已在跑。
#
# 重要：阶段 2 的 roll 用强模型，需要 mcp_completion 服务（:3000）的 LLM 指向你的推理端点。
# 若当前 .env 的 LLM_BASE_URL 不对，请先改 .env 并重启 make run-mcp-completion：
#   LLM_BASE_URL=https://your-endpoint/v1
#   LLM_API_KEY=<your key>
# 然后阶段 2 的 --model 用 "openai/GPT-5.5"。
#
# 用法：
#   cd services/mcp_eval
#   export LLM_API_KEY=sk-xxx
#   bash eval_scripts/synth/run_smoke.sh

set -euo pipefail
cd "$(dirname "$0")/../.."   # -> services/mcp_eval

: "${LLM_API_KEY:?set LLM_API_KEY first}"
ROLL_MODEL="${ROLL_MODEL:-openai/GPT-5.5}"
SYNTH=eval_scripts/synth

echo "=== [0/4] dump env inventory from docker ==="
bash $SYNTH/0_dump_env_inventory.sh

echo "=== [1/4] extract templates ==="
uv run python $SYNTH/1_extract_templates.py

echo "=== [2/4] generate candidate tasks (2 templates x 5) ==="
uv run python $SYNTH/2_generate_tasks.py \
  --limit 2 --per-template 5 \
  --output $SYNTH/candidates_smoke.csv

echo "=== [3/4] roll trajectories with $ROLL_MODEL (via mcp_completion :3000) ==="
uv run python mcp_completion_script.py \
  --model "$ROLL_MODEL" \
  --input "$SYNTH/candidates_smoke.csv" \
  --no-filter \
  --output "synth_roll_smoke.csv"

echo "=== [4/4] extract claims + filter -> synth_tasks_smoke.csv ==="
uv run python $SYNTH/3_build_dataset.py \
  --roll-result completion_results/synth_roll_smoke.csv \
  --output $SYNTH/synth_tasks_smoke.csv \
  --report $SYNTH/discarded_smoke.txt

echo ""
echo "Done. Inspect:"
echo "  candidates : $SYNTH/candidates_smoke.csv"
echo "  roll result: completion_results/synth_roll_smoke.csv"
echo "  final tasks: $SYNTH/synth_tasks_smoke.csv"
echo "  discarded  : $SYNTH/discarded_smoke.txt"
