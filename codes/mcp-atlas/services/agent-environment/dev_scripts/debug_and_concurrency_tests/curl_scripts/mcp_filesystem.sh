#!/bin/bash

# 1. List allowed directories
curl -w " HTTP_STATUS:%{http_code}\n" -X POST http://localhost:1984/call-tool \
  -H "Content-Type: application/json" \
  -d '{
    "tool_name": "filesystem_list_allowed_directories",
    "tool_args": {}
  }' 

# 2. Search for files matching "storyteller" pattern in /data
curl -w " HTTP_STATUS:%{http_code}\n" -X POST http://localhost:1984/call-tool \
  -H "Content-Type: application/json" \
  -d '{
    "tool_name": "filesystem_search_files",
    "tool_args": {
      "path": "/data",
      "pattern": "storyteller"
    }
  }' 