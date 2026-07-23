#!/bin/bash

# Array of cities to search for Airbnb listings
cities=(
  "New York, NY"
  "Los Angeles, CA"
  "San Francisco, CA"
  "Miami, FL"
  "Austin, TX"
  "Seattle, WA"
  "Chicago, IL"
  "Boston, MA"
  "Denver, CO"
  "Nashville, TN"
)

# Select random city
random_index=$((RANDOM % ${#cities[@]}))
selected_city="${cities[$random_index]}"

curl -w " HTTP_STATUS:%{http_code}\n" -X POST http://localhost:1984/call-tool \
  -H 'Content-Type: application/json' \
  -d '{
    "tool_name": "airbnb_airbnb_search",
    "tool_args": {
      "location": "'"$selected_city"'",
      "checkin": "2026-02-15",
      "checkout": "2026-02-18",
      "adults": 2,
      "ignoreRobotsText": true
    }
  }' 