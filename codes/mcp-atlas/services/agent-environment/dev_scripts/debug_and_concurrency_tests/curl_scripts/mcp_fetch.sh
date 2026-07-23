#!/bin/bash

# Array of real URLs extracted from tool-calls.json files
real_urls=(
  "https://www.statmuse.com/nba/ask/most-points-scored-in-a-single-game-in-the-playoffs"
  "https://www.espn.com/nba/player/stats/_/id/1035/michael-jordan"
  "https://www.archysport.com/2025/04/michael-jordans-last-shot-iconic-nba-finale/"
  "https://mseep.ai/app/mikechao-balldontlie-mcp"
  "http://api.quodb.com/search/the things you own end up owning you"
  "https://tessomewhere.com/trip-to-japan-costs/"
  "https://arxiv.org/html/2507.08386v1"
  "https://en.wikipedia.org/wiki/List_of_career_achievements_by_Stephen_Curry"
  "https://www.mongodb.com"
  "https://poets.org/poem/how-do-i-love-thee-sonnet-43"
  "https://artfulhaven.com/art-tools-and-materials-for-drawing-and-painting/"
)

# Select a random URL
random_index=$((RANDOM % ${#real_urls[@]}))
selected_url="${real_urls[$random_index]}"
curl -w " HTTP_STATUS:%{http_code}\n" -X POST http://localhost:1984/call-tool \
  -H "Content-Type: application/json" \
  -d '{
    "tool_name": "fetch_fetch",
    "tool_args": {
      "url": "'"$selected_url"'"
    }
  }'