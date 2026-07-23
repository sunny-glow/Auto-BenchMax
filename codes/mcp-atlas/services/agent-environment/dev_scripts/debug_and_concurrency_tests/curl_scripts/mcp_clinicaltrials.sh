#!/bin/bash

# Array of medical search terms for clinical trials
search_terms=(
  "cancer"
  "diabetes"
  "alzheimer"
  "covid-19"
  "hypertension"
  "depression"
  "asthma"
  "heart disease"
  "stroke"
  "arthritis"
  "parkinson"
  "obesity"
  "pneumonia"
  "migraine"
  "epilepsy"
  "osteoporosis"
  "kidney disease"
  "liver disease"
  "schizophrenia"
  "autism"
)

# Array of real NCT IDs for clinical trials
nct_ids=(
  "NCT04280588"
  "NCT03652454"
  "NCT04372602"
  "NCT03784300"
  "NCT04516746"
  "NCT03989440"
  "NCT04261907"
  "NCT04315948"
  "NCT04362137"
  "NCT04424316"
  "NCT04381936"
  "NCT04345601"
  "NCT04292899"
  "NCT04321096"
  "NCT04373044"
  "NCT04358068"
  "NCT04335305"
  "NCT04326920"
  "NCT04395170"
  "NCT04347681"
)

# Randomly choose between the two operations (0 = list_studies, 1 = get_study)
operation=$((RANDOM % 2))

if [ $operation -eq 0 ]; then
  # clinicaltrials_list_studies operation with search term only
  random_term_index=$((RANDOM % ${#search_terms[@]}))
  selected_term="${search_terms[$random_term_index]}"
  
  curl -w " HTTP_STATUS:%{http_code}\n" -X POST http://localhost:1984/call-tool \
    -H 'Content-Type: application/json' \
    -d '{
      "tool_name": "clinicaltrialsgov-mcp-server_clinicaltrials_list_studies",
      "tool_args": {
        "query": {
          "term": "'"$selected_term"'"
        },
        "pageSize": 5
      }
    }'

else
  # clinicaltrials_get_study operation with nctIds only
  random_nct_index=$((RANDOM % ${#nct_ids[@]}))
  selected_nct_id="${nct_ids[$random_nct_index]}"
  
  curl -w " HTTP_STATUS:%{http_code}\n" -X POST http://localhost:1984/call-tool \
    -H 'Content-Type: application/json' \
    -d '{
      "tool_name": "clinicaltrialsgov-mcp-server_clinicaltrials_get_study",
      "tool_args": {
        "nctIds": "'"$selected_nct_id"'"
      }
    }'
fi 