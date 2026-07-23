#!/bin/bash

# Array of book titles for open-library searches
book_titles=(
  "Numerology and the Divine Triangle"
  "How to Change Your Mind"
  "the body keeps the score"
  "neuropsychedelia"
  "Eichmann in Jerusalem"
  "Halo: Mortal Dictata"
  "To Kill a Mockingbird"
  "1984"
  "The Great Gatsby"
  "Dune"
)

# Select a random book title
random_index=$((RANDOM % ${#book_titles[@]}))
selected_title="${book_titles[$random_index]}"

curl -w " HTTP_STATUS:%{http_code}\n" -X POST http://localhost:1984/call-tool \
  -H "Content-Type: application/json" \
  -d '{
    "tool_name": "open-library_get_book_by_title",
    "tool_args": {
      "title": "'"$selected_title"'"
    }
  }'
