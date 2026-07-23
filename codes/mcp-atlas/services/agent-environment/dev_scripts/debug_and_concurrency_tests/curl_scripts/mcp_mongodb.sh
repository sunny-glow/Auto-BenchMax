#!/bin/bash
# Note that you'll have to customize this for your own database.

# Pick a random number 0, 1, 2, or 3
choice=$((RANDOM % 4))

if [ "$choice" -eq 0 ]; then
  # 1. List databases
  curl -w " HTTP_STATUS:%{http_code}\n" -X POST http://localhost:1984/call-tool \
    -H "Content-Type: application/json" \
    -d '{
      "tool_name": "mongodb_list-databases",
      "tool_args": {}
    }'
elif [ "$choice" -eq 1 ]; then
  # 2. List collections in video_game_store database
  curl -w " HTTP_STATUS:%{http_code}\n" -X POST http://localhost:1984/call-tool \
    -H "Content-Type: application/json" \
    -d '{
      "tool_name": "mongodb_list-collections",
      "tool_args": {
        "database": "video_game_store"
      }
    }'
elif [ "$choice" -eq 2 ]; then
  # 3. Find documents in Purchase History collection
  curl -w " HTTP_STATUS:%{http_code}\n" -X POST http://localhost:1984/call-tool \
    -H "Content-Type: application/json" \
    -d '{
      "tool_name": "mongodb_find",
      "tool_args": {
        "database": "video_game_store",
        "collection": "Purchase History",
        "limit": 10
      }
    }'
else
  # 4. Aggregate first-time customers from 2015
  curl -w " HTTP_STATUS:%{http_code}\n" -X POST http://localhost:1984/call-tool \
    -H "Content-Type: application/json" \
    -d '{
      "tool_name": "mongodb_aggregate",
      "tool_args": {
        "database": "video_game_store",
        "collection": "Purchase History",
        "pipeline": [
          {
            "$match": {
              "Customer Segment": "First-time",
              "Transaction Date": {
                "$gte": {
                  "$date": "2015-01-01T00:00:00Z"
                },
                "$lt": {
                  "$date": "2016-01-01T00:00:00Z"
                }
              }
            }
          },
          {
            "$group": {
              "_id": "$Product Category",
              "count": {
                "$sum": 1
              }
            }
          }
        ]
      }
    }'
fi 
