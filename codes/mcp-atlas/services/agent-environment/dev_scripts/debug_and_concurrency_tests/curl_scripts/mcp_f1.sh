#!/bin/bash

# Array of recent F1 seasons
years=(2023 2022 2021 2020 2019)

# Array of popular F1 events/races
events=(
  "Monaco"
  "Silverstone"
  "Monza"
  "Spa"
  "Suzuka"
  "Interlagos"
  "Abu Dhabi"
  "Bahrain"
  "Australia"
  "Netherlands"
)

# Array of F1 session types
sessions=(
  "Race"
  "Qualifying"
  "Sprint"
  "FP1"
  "FP2"
  "FP3"
)

# Array of 10 F1 drivers (codes)
drivers=(
  "HAM"  # Lewis Hamilton
  "VER"  # Max Verstappen
  "LEC"  # Charles Leclerc
  "RUS"  # George Russell
  "SAI"  # Carlos Sainz
  "NOR"  # Lando Norris
  "PER"  # Sergio Perez
  "ALO"  # Fernando Alonso
  "OCO"  # Esteban Ocon
  "GAS"  # Pierre Gasly
)

# Randomly choose between analyze_driver_performance (0) or compare_drivers (1)
operation=$((RANDOM % 2))

# Select random values for all parameters
year_index=$((RANDOM % ${#years[@]}))
selected_year="${years[$year_index]}"

event_index=$((RANDOM % ${#events[@]}))
selected_event="${events[$event_index]}"

session_index=$((RANDOM % ${#sessions[@]}))
selected_session="${sessions[$session_index]}"

if [ $operation -eq 0 ]; then
  # Analyze driver performance operation
  driver_index=$((RANDOM % ${#drivers[@]}))
  selected_driver="${drivers[$driver_index]}"
  
  curl -w " HTTP_STATUS:%{http_code}\n" -X POST http://localhost:1984/call-tool \
    -H "Content-Type: application/json" \
    -d '{
      "tool_name": "f1-mcp-server_analyze_driver_performance",
      "tool_args": {
        "year": '"$selected_year"',
        "event_identifier": "'"$selected_event"'",
        "session_name": "'"$selected_session"'",
        "driver_identifier": "'"$selected_driver"'"
      }
    }'
else
  # Compare drivers operation
  # Select 2-4 random drivers for comparison
  num_drivers=$((2 + RANDOM % 3))  # Random number between 2 and 4
  
  # Create array of selected drivers
  selected_drivers=()
  used_indices=()
  
  for ((i=0; i<num_drivers; i++)); do
    while true; do
      driver_index=$((RANDOM % ${#drivers[@]}))
      # Check if this index was already used
      if [[ ! " ${used_indices[@]} " =~ " ${driver_index} " ]]; then
        selected_drivers+=("${drivers[$driver_index]}")
        used_indices+=($driver_index)
        break
      fi
    done
  done
  
  # Join drivers with commas
  drivers_list=$(IFS=','; echo "${selected_drivers[*]}")
  
  curl -w " HTTP_STATUS:%{http_code}\n" -X POST http://localhost:1984/call-tool \
    -H "Content-Type: application/json" \
    -d '{
      "tool_name": "f1-mcp-server_compare_drivers",
      "tool_args": {
        "year": '"$selected_year"',
        "event_identifier": "'"$selected_event"'",
        "session_name": "'"$selected_session"'",
        "drivers": "'"$drivers_list"'"
      }
    }'
fi 