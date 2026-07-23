#!/bin/bash

# Array of 10 possible search queries
queries=(
  "latest AI developments 2024"
  "best programming languages for beginners"
  "climate change renewable energy solutions"
  "space exploration recent discoveries"
  "machine learning applications in healthcare"
  "cybersecurity best practices 2024"
  "sustainable agriculture innovations"
  "quantum computing breakthrough news"
  "remote work productivity tips"
  "blockchain technology real world uses"
)

# Select a random query
random_index=$((RANDOM % ${#queries[@]}))
selected_query="${queries[$random_index]}"

curl -w " HTTP_STATUS:%{http_code}\n" -X POST http://localhost:1984/call-tool \
  -H "Content-Type: application/json" \
  -d '{
    "tool_name": "brave-search_brave_web_search",
    "tool_args": {
      "query": "'"$selected_query"'"
    }
  }'
