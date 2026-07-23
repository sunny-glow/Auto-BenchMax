#!/bin/bash

# Array of popular YouTube channel IDs
youtube_channels=(
  "UCBJycsmduvYEL83R_U4JriQ"
  "UCqmugCqELzhIMNYnsjScXXw"
  "UCvmINlrza7JHB1zkIOuXEbw"
  "UCJ24N4O0bP7LGLBDvye7oCA"
  "UCHnyfMqiRRG1u-2MsSQLbXA"
  "UCGaVdbSav8xWuFWTadK6loA"
  "UCBR8-60-B28hp2BmDPdntcQ"
  "UCddiUEpeqJcYeBxX1IVBKvQ"
)

# Select random channel
random_index=$((RANDOM % ${#youtube_channels[@]}))
selected_channel="${youtube_channels[$random_index]}"

curl -w " HTTP_STATUS:%{http_code}\n" -X POST http://localhost:1984/call-tool \
  -H 'Content-Type: application/json' \
  -d '{
    "tool_name": "youtube_getChannelTopVideos",
    "tool_args": {
      "channelId": "'"$selected_channel"'",
      "maxResults": 10
    }
  }' 