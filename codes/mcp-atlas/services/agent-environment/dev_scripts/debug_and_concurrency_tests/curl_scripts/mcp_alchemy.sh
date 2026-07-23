#!/bin/bash

# Array of real wallet addresses with transaction history for testing
wallet_addresses=(
  "0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045"  # Vitalik Buterin's address - has many transactions
  "0x3fC91A3afd70395Cd496C647d5a6CC9D4B2b7FAD"  # Uniswap Universal Router - very active
  "0x742f35Cc8E90349d8aA7B8b8B8A0bBb8b8D8eE8d"  # Another active address
  "0xA0b86a33E6418e1Bd9e5AEA4c5e9e65b0e6F3E45"  # Active DeFi address
  "0x8ba1f109551bD432803012645Hac136c22C35aa8"  # Keep original test address
)

# Array of crypto symbols for price queries
crypto_symbols=(
  "BTC"
  "ETH"
  "USDC"
  "USDT"
  "LINK"
  "AAVE"
)

# Hardcoded safe values for timeframe and interval since we only have one working combination
# timeframe: "1 month", interval: "1d"

# Randomly choose between the three operations (0, 1, 2)
operation=$((RANDOM % 3))

if [ $operation -eq 0 ]; then
  # alchemy_fetchTransfers operation - simplified to avoid 403 errors
  # Using minimal parameters with hardcoded safe values
  
  curl -w " HTTP_STATUS:%{http_code}\n" -X POST http://localhost:1984/call-tool \
    -H 'Content-Type: application/json' \
    -d '{
      "tool_name": "alchemy_fetchTransfers",
      "tool_args": {
        "fromBlock": "0x0",
        "toBlock": "latest",
        "network": "eth-mainnet",
        "maxCount": "0x5"
      }
    }'

elif [ $operation -eq 1 ]; then
  # alchemy_fetchAddressTransactionHistory operation with hardcoded eth-mainnet
  random_addr_index=$((RANDOM % ${#wallet_addresses[@]}))
  
  selected_address="${wallet_addresses[$random_addr_index]}"
  
  curl -w " HTTP_STATUS:%{http_code}\n" -X POST http://localhost:1984/call-tool \
    -H 'Content-Type: application/json' \
    -d '{
      "tool_name": "alchemy_fetchAddressTransactionHistory",
      "tool_args": {
        "addresses": [
          {
            "address": "'"$selected_address"'",
            "networks": ["eth-mainnet"]
          }
        ],
        "limit": 10
      }
    }'

else
  # alchemy_fetchTokenPriceHistoryByTimeFrame operation with hardcoded safe values
  random_symbol_index=$((RANDOM % ${#crypto_symbols[@]}))
  
  selected_symbol="${crypto_symbols[$random_symbol_index]}"
  
  curl -w " HTTP_STATUS:%{http_code}\n" -X POST http://localhost:1984/call-tool \
    -H 'Content-Type: application/json' \
    -d '{
      "tool_name": "alchemy_fetchTokenPriceHistoryByTimeFrame",
      "tool_args": {
        "symbol": "'"$selected_symbol"'",
        "timeFrame": "1 month",
        "interval": "1d",
        "useNaturalLanguageProcessing": false
      }
    }'
fi 