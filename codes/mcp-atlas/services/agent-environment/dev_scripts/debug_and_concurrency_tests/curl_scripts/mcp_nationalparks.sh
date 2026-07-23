#!/bin/bash

# Array of different National Parks API calls based on real usage patterns
nationalparks_calls=(
  '{"tool_name": "national-parks_findParks", "tool_args": {"q": "Yellowstone National Park", "stateCode": "WY"}}'
  '{"tool_name": "national-parks_findParks", "tool_args": {"q": "yosemite", "stateCode": "CA"}}'
  '{"tool_name": "national-parks_findParks", "tool_args": {"q": "Grand Canyon", "stateCode": "AZ"}}'
  '{"tool_name": "national-parks_getParkDetails", "tool_args": {"parkCode": "yell"}}'
  '{"tool_name": "national-parks_getParkDetails", "tool_args": {"parkCode": "yose"}}'
  '{"tool_name": "national-parks_getParkDetails", "tool_args": {"parkCode": "grca"}}'
  '{"tool_name": "national-parks_getCampgrounds", "tool_args": {"parkCode": "yose"}}'
  '{"tool_name": "national-parks_getCampgrounds", "tool_args": {"parkCode": "yell"}}'
  '{"tool_name": "national-parks_getAlerts", "tool_args": {"parkCode": "grca"}}'
  '{"tool_name": "national-parks_getVisitorCenters", "tool_args": {"parkCode": "grsm"}}'
)

# Select a random National Parks call
random_index=$((RANDOM % ${#nationalparks_calls[@]}))
selected_call="${nationalparks_calls[$random_index]}"

curl -w " HTTP_STATUS:%{http_code}\n" -X POST http://localhost:1984/call-tool \
  -H "Content-Type: application/json" \
  -d "$selected_call" 