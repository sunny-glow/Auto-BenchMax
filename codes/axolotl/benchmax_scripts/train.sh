#!/bin/bash

# Change to the repo root (this script lives under benchmax_scripts/)
cd "$(dirname "$0")/.."
source .venv/bin/activate

# Use the current time as the log folder name (format: 01-01_14-30-52)
TIMESTAMP=$(date +"%m-%d_%H-%M-%S")

# Create the log folder
LOG_DIR="./temp_log/${TIMESTAMP}"
mkdir -p "${LOG_DIR}"

# Config file path (override by passing it as the first argument)
CONFIG_FILE="${1:-./benchmax_configs/qwen3_exp0.yaml}"

# Copy the config file into the log folder for reproducibility
cp "${CONFIG_FILE}" "${LOG_DIR}/"

# Run training; tee all output (stdout + stderr) to output.log while still showing it in the terminal
export AXOLOTL_DO_NOT_TRACK=1
torchrun \
  --nnodes=1 \
  --nproc_per_node=8 \
  --rdzv_backend=c10d \
  --rdzv_endpoint=localhost:29500 \
  -m axolotl.cli.train \
  "${CONFIG_FILE}" \
  2>&1 | tee "${LOG_DIR}/output.log"
