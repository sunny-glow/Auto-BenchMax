#!/bin/bash

# Array of CSV files in /data directory
data_files=(
  "/data/Barber Shop.csv"
  "/data/Covid 19 impacts on hospitals.csv"
  "/data/fantasy sports.csv"
  "/data/Pet Care 2023 Weekly Financials.csv"
  "/data/Top Movies.csv"
)

# Array of directories to list
directories=(
  "/data"
  "/data/repos"
)

# Randomly choose between read_file (0) and list_directory (1)
operation=$((RANDOM % 2))

if [ $operation -eq 0 ]; then
  # Read file operation
  random_file_index=$((RANDOM % ${#data_files[@]}))
  selected_file="${data_files[$random_file_index]}"
  
  curl -w " HTTP_STATUS:%{http_code}\n" -X POST http://localhost:1984/call-tool \
    -H 'Content-Type: application/json' \
    -d '{
      "tool_name": "desktop-commander_read_file",
      "tool_args": {
        "path": "'"$selected_file"'"
      }
    }'
else
  # List directory operation
  random_dir_index=$((RANDOM % ${#directories[@]}))
  selected_directory="${directories[$random_dir_index]}"
  
  curl -w " HTTP_STATUS:%{http_code}\n" -X POST http://localhost:1984/call-tool \
    -H 'Content-Type: application/json' \
    -d '{
      "tool_name": "desktop-commander_list_directory",
      "tool_args": {
        "path": "'"$selected_directory"'"
      }
    }'
fi 
