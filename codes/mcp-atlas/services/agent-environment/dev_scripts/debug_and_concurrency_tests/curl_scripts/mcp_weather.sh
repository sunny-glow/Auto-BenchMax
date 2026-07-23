#!/bin/bash

# 1. Find weather stations near coordinates (Victoria, BC area)
curl -w " HTTP_STATUS:%{http_code}\n" -X POST http://localhost:1984/call-tool \
  -H "Content-Type: application/json" \
  -d '{
    "tool_name": "weather_find_weather_stations",
    "tool_args": {
      "location": "48.0993244, -123.4256985"
    }
  }' 