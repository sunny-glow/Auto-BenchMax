#!/bin/bash

# Array of 10 possible place search queries
queries=(
  "coffee shops"
  "restaurants"
  "gas stations"
  "pharmacies"
  "banks"
  "hospitals"
  "grocery stores"
  "parks"
  "hotels"
  "movie theaters"
)

# Select a random query
random_index=$((RANDOM % ${#queries[@]}))
selected_query="${queries[$random_index]}"

curl -w " HTTP_STATUS:%{http_code}\n" -X POST http://localhost:1984/call-tool \
  -H "Content-Type: application/json" \
  -d '{
    "tool_name": "google-maps_maps_search_places",
    "tool_args": {
      "query": "'"$selected_query"'",
      "location": {
        "latitude": 37.7616,
        "longitude": -122.4214
      },
      "radius": 1000
    }
  }' 