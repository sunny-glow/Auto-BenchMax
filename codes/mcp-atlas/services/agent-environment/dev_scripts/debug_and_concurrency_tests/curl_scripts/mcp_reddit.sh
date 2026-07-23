#!/bin/bash

# Array of sports/outdoor activity search queries
queries=(
  '{"subreddit_name": "skiing", "query": "powder conditions"}'
  '{"subreddit_name": "hiking", "query": "trail recommendations"}'
  '{"subreddit_name": "camping", "query": "gear review"}'
  '{"subreddit_name": "climbing", "query": "route beta"}'
  '{"subreddit_name": "surfing", "query": "wave forecast"}'
  '{"subreddit_name": "cycling", "query": "bike maintenance"}'
  '{"subreddit_name": "running", "query": "marathon training"}'
  '{"subreddit_name": "fishing", "query": "best lures"}'
  '{"subreddit_name": "snowboarding", "query": "mountain conditions"}'
  '{"subreddit_name": "kayaking", "query": "river guide"}'
)

# Select a random query
random_index=$((RANDOM % ${#queries[@]}))
selected_query="${queries[$random_index]}"

curl -w " HTTP_STATUS:%{http_code}\n" -X POST http://localhost:1984/call-tool \
  -H "Content-Type: application/json" \
  -d '{
    "tool_name": "reddit_search_posts",
    "tool_args": {
      "params": '"$selected_query"'
    }
  }' 
