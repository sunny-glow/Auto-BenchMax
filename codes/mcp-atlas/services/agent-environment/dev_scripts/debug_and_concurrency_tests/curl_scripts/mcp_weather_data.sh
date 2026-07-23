#!/bin/bash

# 1. Get weather astronomy data for Planet Earth on 2024-02-28
curl -w " HTTP_STATUS:%{http_code}\n" -X POST http://localhost:1984/call-tool \
  -H "Content-Type: application/json" \
  -d '{
    "tool_name": "weather-data_weather_astronomy",
    "tool_args": {
      "dt": "2024-02-28",
      "q": "Planet Earth"
    }
  }' 