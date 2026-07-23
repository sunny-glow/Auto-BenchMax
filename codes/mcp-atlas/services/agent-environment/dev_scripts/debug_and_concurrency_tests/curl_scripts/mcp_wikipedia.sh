#!/bin/bash

# Array of 20 search queries
search_queries=(
  "artificial intelligence"
  "climate change"
  "quantum computing"
  "renewable energy"
  "space exploration"
  "machine learning"
  "cryptocurrency"
  "sustainable development"
  "genetic engineering"
  "virtual reality"
  "blockchain technology"
  "neural networks"
  "cybersecurity threats"
  "biomedical engineering"
  "autonomous vehicles"
  "nanotechnology applications"
  "cloud computing"
  "data science methods"
  "robotics engineering"
  "3D printing technology"
)

# Array of 20 known Wikipedia article titles
article_titles=(
  "Gongxianosaurus"
  "Velocity_made_good"
  "Shark cage diving"
  "Aberthaw Cement Works"
  "Joseph Pease (railway pioneer)"
  "Monogononta"
  "Monophyly"
  "Acetabulum"
  "Adiantum vivesii"
  "Major Gilbert Field Airport"
  "La Pointe, Wisconsin"
  "Apostle Islands"
  "Soil organic matter"
  "Trace element"
  "Economic methodology"
)

# Randomly choose between search (0) or get_article (1)
operation=$((RANDOM % 2))

if [ $operation -eq 0 ]; then
  # Search operation
  random_index=$((RANDOM % ${#search_queries[@]}))
  selected_query="${search_queries[$random_index]}"
  
  curl -w " HTTP_STATUS:%{http_code}\n" -X POST http://localhost:1984/call-tool \
    -H "Content-Type: application/json" \
    -d '{
      "tool_name": "wikipedia_search_wikipedia",
      "tool_args": {
        "query": "'"$selected_query"'",
        "limit": 5
      }
    }'
else
  # Get article operation
  random_index=$((RANDOM % ${#article_titles[@]}))
  selected_title="${article_titles[$random_index]}"
  
  curl -w " HTTP_STATUS:%{http_code}\n" -X POST http://localhost:1984/call-tool \
    -H "Content-Type: application/json" \
    -d '{
      "tool_name": "wikipedia_get_article",
      "tool_args": {
        "title": "'"$selected_title"'"
      }
    }'
fi 