#!/bin/bash

# Pick a random number 0, 1, or 2
choice=$((RANDOM % 3))

if [ "$choice" -eq 0 ]; then
  # 1. Git status for mcp-server-calculator repo
  curl -w " HTTP_STATUS:%{http_code}\n" -X POST http://localhost:1984/call-tool \
    -H "Content-Type: application/json" \
    -d '{
      "tool_name": "git_git_status",
      "tool_args": {
        "repo_path": "/data/repos/mcp-server-calculator"
      }
    }'
elif [ "$choice" -eq 1 ]; then
  # 2. Git log for mcp-server-calculator repo
  curl -w " HTTP_STATUS:%{http_code}\n" -X POST http://localhost:1984/call-tool \
    -H "Content-Type: application/json" \
    -d '{
      "tool_name": "git_git_log",
      "tool_args": {
        "repo_path": "/data/repos/mcp-server-calculator"
      }
    }'
else
  # 3. Git show specific revision
  curl -w " HTTP_STATUS:%{http_code}\n" -X POST http://localhost:1984/call-tool \
    -H "Content-Type: application/json" \
    -d '{
      "tool_name": "git_git_show",
      "tool_args": {
        "repo_path": "/data/repos/mcp-server-calculator",
        "revision": "5b828b921e5f187c2de0a8d6c597885fce3b3b86"
      }
    }'
fi