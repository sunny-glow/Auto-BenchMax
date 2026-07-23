#!/bin/bash

# 1. List Slack channels (public and private)
curl -w " HTTP_STATUS:%{http_code}\n" -X POST http://localhost:1984/call-tool \
  -H "Content-Type: application/json" \
  -d '{
    "tool_name": "slack_channels_list",
    "tool_args": {
      "channel_types": "public_channel,private_channel"
    }
  }' 

# 2. Get conversation history from #movie-suggestions channel
curl -w " HTTP_STATUS:%{http_code}\n" -X POST http://localhost:1984/call-tool \
  -H "Content-Type: application/json" \
  -d '{
    "tool_name": "slack_conversations_history",
    "tool_args": {
      "channel_id": "#movie-suggestions",
      "limit": "30d",
      "include_activity_messages": false
    }
  }' 