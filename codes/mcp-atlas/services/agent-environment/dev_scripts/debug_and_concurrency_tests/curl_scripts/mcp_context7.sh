#!/bin/bash

# Array of popular library names for resolve-library-id (all tested working)
library_names=(
  "react"
  "next.js"
  "express"
  "mongodb"
  "supabase"
  "tailwindcss"
  "typescript"
  "vue"
  "angular"
  "node.js"
)

# Array of known working Context7-compatible library IDs for get-library-docs
library_ids=(
  "/vercel/next.js"
  "/nodejs/node"
  "/expressjs/express"
)

# Array of broader topics that should work with various libraries (all tested working)
topics=(
  "getting started"
  "installation"
  "configuration"
  "examples"
  "api reference"
  "best practices"
  "troubleshooting"
  "performance"
  "security"
  "documentation"
)

# Randomly choose between resolve-library-id (0) and get-library-docs (1)
operation=$((RANDOM % 2))

if [ $operation -eq 0 ]; then
  # Resolve library ID operation
  random_lib_index=$((RANDOM % ${#library_names[@]}))
  selected_library="${library_names[$random_lib_index]}"
  
  curl -w " HTTP_STATUS:%{http_code}\n" -X POST http://localhost:1984/call-tool \
    -H 'Content-Type: application/json' \
    -d '{
      "tool_name": "context7_resolve-library-id",
      "tool_args": {
        "libraryName": "'"$selected_library"'"
      }
    }'
else
  # Get library docs operation
  random_id_index=$((RANDOM % ${#library_ids[@]}))
  selected_library_id="${library_ids[$random_id_index]}"
  
  random_topic_index=$((RANDOM % ${#topics[@]}))
  selected_topic="${topics[$random_topic_index]}"
  
  curl -w " HTTP_STATUS:%{http_code}\n" -X POST http://localhost:1984/call-tool \
    -H 'Content-Type: application/json' \
    -d '{
      "tool_name": "context7_get-library-docs",
      "tool_args": {
        "context7CompatibleLibraryID": "'"$selected_library_id"'",
        "topic": "'"$selected_topic"'",
        "tokens": 5000
      }
    }'
fi 