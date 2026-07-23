#!/usr/bin/env bash
# 采集 agent-environment docker 容器里 /data 的真实文件/目录清单，
# 供阶段 1 生成"本地环境类"任务时注入（这些任务只能在真实存在的文件上换参数，不能编路径）。
#
# 输出：eval_scripts/synth/env_inventory.txt
#
# 用法（docker 需先 make run-docker 起好）：
#   cd services/mcp_eval && bash eval_scripts/synth/0_dump_env_inventory.sh

set -euo pipefail

OUT="${1:-eval_scripts/synth/env_inventory.txt}"
cid=$(docker ps -q --filter ancestor=agent-environment:latest | head -1)

if [ -z "$cid" ]; then
  echo "Error: agent-environment container not running. Run 'make run-docker' first." >&2
  exit 1
fi

docker exec "$cid" find /data -maxdepth 3 \
  -not -path '*/.git/*' -not -path '*/.venv/*' -not -path '*/node_modules/*' \
  -not -path '*/.git' -not -path '*/.venv' 2>/dev/null | sort > "$OUT"

echo "Wrote $(wc -l < "$OUT") lines -> $OUT"
