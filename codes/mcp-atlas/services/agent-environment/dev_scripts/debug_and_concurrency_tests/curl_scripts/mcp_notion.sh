#!/bin/bash

curl -w " HTTP_STATUS:%{http_code}\n" -X POST http://localhost:1984/call-tool \
  -H "Content-Type: application/json" \
  -d '{
    "tool_name": "notion_API-get-users",
    "tool_args": {}
  }' 

# Array of pages to search for
pages=(
  "deadbeef844e8093b976e9cfeca3665a"
  "deadbeef844e8090b48dd33c1c2be7f8"
  "deadbeef844e8068b387fe7a56b04348"
  "deadbeef844e808da0c5ed2d08f39729"
  "deadbeef844e817d8ecac2ea93e6d250"
  "deadbeef844e8152ac0ce8cc8cd445d3"
  "deadbeef844e81ef8a11c2cdd3a975bd"
  "deadbeef844e81828485d2e4e59a12b7"
  "deadbeef844e81aab722dbe0193aa8d0"
)

# Select a random customer ID
random_index=$((RANDOM % ${#pages[@]}))
selected_customer="${pages[$random_index]}"

curl -w " HTTP_STATUS:%{http_code}\n" -X POST http://localhost:1984/call-tool \
  -H "Content-Type: application/json" \
  -d '{
    "tool_name": "notion_API-post-search",
    "tool_args": {
      "query": "'"$selected_customer"'",
      "page_size": 1
    }
  }' 