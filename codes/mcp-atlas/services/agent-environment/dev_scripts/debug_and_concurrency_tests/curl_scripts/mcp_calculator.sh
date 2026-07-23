#!/bin/bash

# Array of 8 mathematical expressions
expressions=(
  "2 + 3 * 4"
  "sqrt(16) + 5"
  "sin(pi/4) * cos(pi/4)"
  "log(100) / log(10)"
  "pow(2, 8) - 1"
  "(15 + 25) / (2 * 5)"
  "floor(9.7) * ceil(3.2)"
  "factorial(5) / 12"
)

# Select a random expression
random_index=$((RANDOM % ${#expressions[@]}))
selected_expression="${expressions[$random_index]}"

curl -w " HTTP_STATUS:%{http_code}\n" -X POST http://localhost:1984/call-tool \
  -H "Content-Type: application/json" \
  -d '{
    "tool_name": "calculator_calculate",
    "tool_args": {
      "expression": "'"$selected_expression"'"
    }
  }' 