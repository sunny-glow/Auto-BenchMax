#!/bin/bash

curl -w " HTTP_STATUS:%{http_code}\n" -X POST http://localhost:1984/call-tool \
  -H "Content-Type: application/json" \
  -d '{
    "tool_name": "oxylabs_google_search_scraper",
    "tool_args": {
      "query": "When did the World Cup start in Qatar?"
    }
  }' 