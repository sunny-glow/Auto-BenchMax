#!/bin/bash

# Array of different whois lookups based on real usage patterns
whois_calls=(
  '{"tool_name": "whois_whois_domain", "tool_args": {"domain": "crunchyroll.com"}}'
  '{"tool_name": "whois_whois_domain", "tool_args": {"domain": "tesla.com"}}'
  '{"tool_name": "whois_whois_domain", "tool_args": {"domain": "ethereum.org"}}'
  '{"tool_name": "whois_whois_domain", "tool_args": {"domain": "nba.com"}}'
  '{"tool_name": "whois_whois_domain", "tool_args": {"domain": "apple.com"}}'
  '{"tool_name": "whois_whois_domain", "tool_args": {"domain": "arxiv.org"}}'
  '{"tool_name": "whois_whois_ip", "tool_args": {"ip": "17.0.0.0"}}'
  '{"tool_name": "whois_whois_ip", "tool_args": {"ip": "8.8.8.8"}}'
  '{"tool_name": "whois_whois_as", "tool_args": {"asn": "AS16509"}}'
  '{"tool_name": "whois_whois_tld", "tool_args": {"tld": "www.universityofcalifornia.edu"}}'
)

# Select a random whois call
random_index=$((RANDOM % ${#whois_calls[@]}))
selected_call="${whois_calls[$random_index]}"

curl -w " HTTP_STATUS:%{http_code}\n" -X POST http://localhost:1984/call-tool \
  -H "Content-Type: application/json" \
  -d "$selected_call" 