#!/bin/bash

# 1. Search for museum objects - "Reproduction of the Seal of Wolfhagen (Hessen), 1335"
curl -w " HTTP_STATUS:%{http_code}\n" -X POST http://localhost:1984/call-tool \
  -H "Content-Type: application/json" \
  -d '{
    "tool_name": "met-museum_search-museum-objects",
    "tool_args": {
      "q": "Reproduction of the Seal of Wolfhagen (Hessen), 1335",
      "departmentId": 0,
      "title": true
    }
  }'

# 2. Get specific museum object details by ID
curl -w " HTTP_STATUS:%{http_code}\n" -X POST http://localhost:1984/call-tool \
  -H "Content-Type: application/json" \
  -d '{
    "tool_name": "met-museum_get-museum-object",
    "tool_args": {
      "objectId": 32907
    }
  }'
