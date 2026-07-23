#!/bin/bash

# Array of search_category configurations
search_category_configs=(
  '{"category": "amenity", "min_latitude": 37.7749, "min_longitude": -122.4294, "max_latitude": 37.7849, "max_longitude": -122.4194, "subcategories": ["restaurant", "cafe"]}'
  '{"category": "shop", "min_latitude": 40.7589, "min_longitude": -73.9851, "max_latitude": 40.7689, "max_longitude": -73.9751}'
  '{"category": "tourism", "min_latitude": 51.5074, "min_longitude": -0.1278, "max_latitude": 51.5174, "max_longitude": -0.1178, "subcategories": ["attraction", "museum"]}'
  '{"category": "building", "min_latitude": 48.8566, "min_longitude": 2.3522, "max_latitude": 48.8666, "max_longitude": 2.3622}'
  '{"category": "leisure", "min_latitude": 34.0522, "min_longitude": -118.2537, "max_latitude": 34.0622, "max_longitude": -118.2437, "subcategories": ["park", "playground"]}'
  '{"category": "amenity", "min_latitude": 35.6762, "min_longitude": 139.6503, "max_latitude": 35.6862, "max_longitude": 139.6603, "subcategories": ["hospital", "pharmacy"]}'
  '{"category": "shop", "min_latitude": 52.5200, "min_longitude": 13.4050, "max_latitude": 52.5300, "max_longitude": 13.4150, "subcategories": ["supermarket", "convenience"]}'
  '{"category": "tourism", "min_latitude": 41.9028, "min_longitude": 12.4964, "max_latitude": 41.9128, "max_longitude": 12.5064}'
  '{"category": "amenity", "min_latitude": 55.7558, "min_longitude": 37.6176, "max_latitude": 55.7658, "max_longitude": 37.6276, "subcategories": ["bank", "atm"]}'
  '{"category": "leisure", "min_latitude": -33.8688, "min_longitude": 151.2093, "max_latitude": -33.8588, "max_longitude": 151.2193, "subcategories": ["sports_centre", "fitness_centre"]}'
)

# Array of explore_area configurations
explore_area_configs=(
  '{"latitude": 37.7749, "longitude": -122.4194, "radius": 1000}'
  '{"latitude": 40.7831, "longitude": -73.9712, "radius": 750}'
  '{"latitude": 51.5074, "longitude": -0.1278, "radius": 500}'
  '{"latitude": 48.8566, "longitude": 2.3522, "radius": 800}'
  '{"latitude": 34.0522, "longitude": -118.2437, "radius": 1200}'
  '{"latitude": 35.6762, "longitude": 139.6503, "radius": 600}'
  '{"latitude": 52.5200, "longitude": 13.4050, "radius": 900}'
  '{"latitude": 41.9028, "longitude": 12.4964, "radius": 700}'
  '{"latitude": 55.7558, "longitude": 37.6176, "radius": 1100}'
  '{"latitude": -33.8688, "longitude": 151.2093, "radius": 650}'
)

# Randomly choose between search_category (0) and explore_area (1)
operation=$((RANDOM % 2))

if [ $operation -eq 0 ]; then
  # Search category operation
  random_index=$((RANDOM % ${#search_category_configs[@]}))
  selected_config="${search_category_configs[$random_index]}"
  
  curl -w " HTTP_STATUS:%{http_code}\n" -X POST http://localhost:1984/call-tool \
    -H 'Content-Type: application/json' \
    -d '{
      "tool_name": "osm-mcp-server_search_category",
      "tool_args": '"$selected_config"'
    }'
else
  # Explore area operation
  random_index=$((RANDOM % ${#explore_area_configs[@]}))
  selected_config="${explore_area_configs[$random_index]}"
  
  curl -w " HTTP_STATUS:%{http_code}\n" -X POST http://localhost:1984/call-tool \
    -H 'Content-Type: application/json' \
    -d '{
      "tool_name": "osm-mcp-server_explore_area",
      "tool_args": '"$selected_config"'
    }'
fi 