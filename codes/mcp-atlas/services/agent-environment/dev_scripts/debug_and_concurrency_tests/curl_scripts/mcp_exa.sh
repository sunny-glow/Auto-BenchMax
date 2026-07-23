#!/bin/bash

# Array of search queries
queries=(
  "Michael Pollan nationality"
  "Costume shop on W. Pecan St. in Denton, TX"
  "Palantir Technologies founders"
)

# Select a random query
random_index=$((RANDOM % ${#queries[@]}))
selected_query="${queries[$random_index]}"

curl -w " HTTP_STATUS:%{http_code}\n" -X POST http://localhost:1984/call-tool \
  -H "Content-Type: application/json" \
  -d '{
    "tool_name": "exa_web_search_exa",
    "tool_args": {
      "query": "'"$selected_query"'"
    }
  }'