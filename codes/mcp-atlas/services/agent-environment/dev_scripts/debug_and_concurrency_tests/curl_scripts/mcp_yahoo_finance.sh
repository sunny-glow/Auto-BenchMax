#!/bin/bash

# Array of tech company tickers
tech_companies=(
  "AAPL"
  "MSFT"
  "GOOGL"
  "AMZN"
  "TSLA"
  "META"
  "NVDA"
  "NFLX"
  "ORCL"
  "CRM"
)

# Array of time periods for price history
periods=("1mo" "3mo")

# Randomly choose between search (0) and price_history (1)
operation=$((RANDOM % 2))

# Select random ticker
random_index=$((RANDOM % ${#tech_companies[@]}))
selected_ticker="${tech_companies[$random_index]}"

if [ $operation -eq 0 ]; then
  # Search operation
  
  curl -w " HTTP_STATUS:%{http_code}\n" -X POST http://localhost:1984/call-tool \
    -H 'Content-Type: application/json' \
    -d '{
      "tool_name": "yfmcp_search",
      "tool_args": {
        "query": "'"$selected_ticker"'",
        "search_type": "all"
      }
    }'
else
  # Price history operation
  random_period=$((RANDOM % ${#periods[@]}))
  selected_period="${periods[$random_period]}"
  
  curl -w " HTTP_STATUS:%{http_code}\n" -X POST http://localhost:1984/call-tool \
    -H 'Content-Type: application/json' \
    -d '{
      "tool_name": "yfmcp_get_price_history",
      "tool_args": {
        "symbol": "'"$selected_ticker"'",
        "period": "'"$selected_period"'",
        "interval": "1d"
      }
    }'
fi 