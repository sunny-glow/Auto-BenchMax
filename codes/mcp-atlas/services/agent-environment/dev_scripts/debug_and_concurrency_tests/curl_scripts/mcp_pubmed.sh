#!/bin/bash

# 1. Search PubMed for papers by keywords - "bessel van der kolk"
curl -w " HTTP_STATUS:%{http_code}\n" -X POST http://localhost:1984/call-tool \
  -H "Content-Type: application/json" \
  -d '{
    "tool_name": "pubmed_search_pubmed_key_words",
    "tool_args": {
      "key_words": "bessel van der kolk"
    }
  }' 