#!/bin/bash

curl -w " HTTP_STATUS:%{http_code}\n" -X POST http://localhost:1984/call-tool \
  -H "Content-Type: application/json" \
  -d '{
    "tool_name": "lara-translate_translate",
    "tool_args": {
      "text": [
        {
          "text": "La Liberté éclairant le monde",
          "translatable": true
        }
      ],
      "target": "en",
      "source": "fr"
    }
  }' 