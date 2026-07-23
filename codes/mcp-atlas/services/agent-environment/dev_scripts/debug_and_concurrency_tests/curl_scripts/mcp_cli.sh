#!/bin/bash

# Array of CLI commands for run_command
commands=(
  "ls /data"
  "ls -la /data"
  "find /data -name \"*.csv\""
  "find /data -type f"
  "cat /data/Top Movies.csv"
  "cat /data/Barber Shop.csv"
  "ls -l /data/*.csv"
  "find /data -name \"*.csv\" -exec ls -l {} \\;"
  "ls"
)

random_cmd_index=$((RANDOM % ${#commands[@]}))
selected_command="${commands[$random_cmd_index]}"

curl -w " HTTP_STATUS:%{http_code}\n" -X POST http://localhost:1984/call-tool \
  -H "Content-Type: application/json" \
  -d '{
    "tool_name": "cli-mcp-server_run_command",
    "tool_args": {
      "command": "'"$selected_command"'"
    }
  }'