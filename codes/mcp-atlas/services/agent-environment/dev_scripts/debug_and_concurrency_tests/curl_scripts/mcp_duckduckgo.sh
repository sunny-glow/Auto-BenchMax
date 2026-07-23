#!/bin/bash

# Array of different DuckDuckGo API calls based on real usage patterns
duckduckgo_calls=(
  '{"tool_name": "ddg-search_search", "tool_args": {"query": "Blade Runner director"}}'
  '{"tool_name": "ddg-search_search", "tool_args": {"query": "Team that drafted Peyton Watson"}}'
  '{"tool_name": "ddg-search_search", "tool_args": {"query": "moonlight towers austin christmas"}}'
  '{"tool_name": "ddg-search_search", "tool_args": {"query": "Hulhule Island Hotel"}}'
  '{"tool_name": "ddg-search_search", "tool_args": {"query": "portfolio optimization by quantum computing"}}'
  '{"tool_name": "ddg-search_search", "tool_args": {"query": "Brazilian soldiers on WWI"}}'
  '{"tool_name": "ddg-search_search", "tool_args": {"query": "when the video baby by justin bieber reach 1 billlion views"}}'
  '{"tool_name": "ddg-search_search", "tool_args": {"query": "climate change impact on agriculture 2024"}}'
  '{"tool_name": "ddg-search_fetch_content", "tool_args": {"url": "https://www.nature.com/articles/s41598-023-45392-w"}}'
  '{"tool_name": "ddg-search_fetch_content", "tool_args": {"url": "https://www.aceshowbiz.com/news/view/00068707.html"}}'
)

# Select a random DuckDuckGo call
random_index=$((RANDOM % ${#duckduckgo_calls[@]}))
selected_call="${duckduckgo_calls[$random_index]}"

curl -w " HTTP_STATUS:%{http_code}\n" -X POST http://localhost:1984/call-tool \
  -H "Content-Type: application/json" \
  -d "$selected_call" 