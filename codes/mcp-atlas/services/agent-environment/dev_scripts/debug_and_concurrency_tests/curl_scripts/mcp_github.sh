#!/bin/bash

curl -w " HTTP_STATUS:%{http_code}\n" -X POST http://localhost:1984/call-tool \
  -H "Content-Type: application/json" \
  -d '{
    "tool_name": "github_list_commits",
    "tool_args": {
      "owner": "torvalds",
      "repo": "subsurface"
    }
  }'
