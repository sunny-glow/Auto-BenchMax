#!/bin/bash

# Array of different balldontlie API calls based on real usage patterns
balldontlie_calls=(
  '{"tool_name": "balldontlie_get_teams", "tool_args": {"league": "NBA"}}'
  '{"tool_name": "balldontlie_get_teams", "tool_args": {"league": "NFL"}}'
  '{"tool_name": "balldontlie_get_teams", "tool_args": {"league": "MLB"}}'
  '{"tool_name": "balldontlie_get_games", "tool_args": {"league": "NBA", "seasons": [2020], "teamIds": [8]}}'
  '{"tool_name": "balldontlie_get_games", "tool_args": {"league": "NFL", "dates": [], "teamIds": [18], "seasons": [2025]}}'
  '{"tool_name": "balldontlie_get_games", "tool_args": {"league": "MLB", "dates": ["2025-06-24"], "teamIds": [3]}}'
  '{"tool_name": "balldontlie_get_games", "tool_args": {"league": "NBA", "teamIds": [27]}}'
  '{"tool_name": "balldontlie_get_games", "tool_args": {"league": "NBA", "seasons": [2024]}}'
  '{"tool_name": "balldontlie_get_games", "tool_args": {"league": "NFL", "teamIds": [12], "seasons": [2024]}}'
  '{"tool_name": "balldontlie_get_games", "tool_args": {"league": "MLB", "teamIds": [15], "seasons": [2025]}}'
)

# Select a random balldontlie call
random_index=$((RANDOM % ${#balldontlie_calls[@]}))
selected_call="${balldontlie_calls[$random_index]}"

curl -w " HTTP_STATUS:%{http_code}\n" -X POST http://localhost:1984/call-tool \
  -H "Content-Type: application/json" \
  -d "$selected_call" 