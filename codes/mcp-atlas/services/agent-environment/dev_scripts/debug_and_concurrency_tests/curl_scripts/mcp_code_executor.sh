#!/bin/bash

curl -w " HTTP_STATUS:%{http_code}\n" -X POST http://localhost:1984/call-tool \
  -H "Content-Type: application/json" \
  -d '{
    "tool_name": "mcp-code-executor_execute_code",
    "tool_args": {
      "code": "print(123123)"
    }
  }'
