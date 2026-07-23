#!/bin/bash

# Array of different Rijksmuseum API calls based on real usage patterns
rijksmuseum_calls=(
  '{"tool_name": "rijksmuseum-server_search_artwork", "tool_args": {"q": "The Night Watch by Rembrandt van Rijn"}}'
  '{"tool_name": "rijksmuseum-server_search_artwork", "tool_args": {"q": "The Milkmaid by Johannes Vermeer"}}'
  '{"tool_name": "rijksmuseum-server_search_artwork", "tool_args": {"q": "The Little Street by Johannes Vermeer"}}'
  '{"tool_name": "rijksmuseum-server_search_artwork", "tool_args": {"q": "Self-Portrait by Rembrandt van Rijn"}}'
  '{"tool_name": "rijksmuseum-server_search_artwork", "tool_args": {"q": "The Merry Family by Jan Steen"}}'
  '{"tool_name": "rijksmuseum-server_search_artwork", "tool_args": {"q": "Still Life With Asparagus"}}'
  '{"tool_name": "rijksmuseum-server_get_artwork_details", "tool_args": {"objectNumber": "SK-C-5"}}'
  '{"tool_name": "rijksmuseum-server_get_artwork_details", "tool_args": {"objectNumber": "SK-A-1588"}}'
  '{"tool_name": "rijksmuseum-server_get_artwork_details", "tool_args": {"objectNumber": "SK-A-4"}}'
  '{"tool_name": "rijksmuseum-server_get_artwork_details", "tool_args": {"objectNumber": "SK-A-2344"}}'
)

# Select a random Rijksmuseum call
random_index=$((RANDOM % ${#rijksmuseum_calls[@]}))
selected_call="${rijksmuseum_calls[$random_index]}"

curl -w " HTTP_STATUS:%{http_code}\n" -X POST http://localhost:1984/call-tool \
  -H "Content-Type: application/json" \
  -d "$selected_call" 