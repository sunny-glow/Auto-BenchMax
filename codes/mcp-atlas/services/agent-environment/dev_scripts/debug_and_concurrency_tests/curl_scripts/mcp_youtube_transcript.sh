#!/bin/bash

# Array of real English YouTube video URLs (5 minutes or less)
youtube_urls=(
  "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
  "https://www.youtube.com/watch?v=_OBlgSz8sSM"
  "https://www.youtube.com/watch?v=txqiwrbYGrs"
  "https://www.youtube.com/watch?v=J---aiyznGQ"
  "https://www.youtube.com/watch?v=2yJgwwDcgV8"
  "https://www.youtube.com/watch?v=MyklAHZHd24"
  "https://www.youtube.com/watch?v=YVkUvmDQ3HY"
  "https://www.youtube.com/watch?v=qWbIXekZocI"
  "https://www.youtube.com/watch?v=kffacxfA7G4"
  "https://www.youtube.com/watch?v=jfVp3PnRgrs"
)


# Select random video URL
random_url_index=$((RANDOM % ${#youtube_urls[@]}))
selected_url="${youtube_urls[$random_url_index]}"

curl -w " HTTP_STATUS:%{http_code}\n" -X POST http://localhost:1984/call-tool \
  -H 'Content-Type: application/json' \
  -d '{
    "tool_name": "youtube-transcript_get_transcript",
    "tool_args": {
      "url": "'"$selected_url"'",
      "lang": "en"
    }
  }' 