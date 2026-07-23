#!/bin/bash

# Script to extract git submodule URL, SHA and path information
# Output format: CSV with columns: URL,SHA,PATH

# Function to get URL for a given submodule path from .gitmodules
get_submodule_url() {
    local submodule_path="$1"
    # Use grep to find the submodule section and the next url line
    grep -A 2 "\\[submodule \"$submodule_path\"\\]" .gitmodules | grep "url" | sed 's/.*url = //'
}

# Run git submodule status and process the output
git submodule status | while read -r line; do
    # Remove leading space/status character and extract SHA and path
    # git submodule status format: " <sha> <path> (<description>)" or "-<sha> <path> (<description>)"

    # Remove leading space or status character (-, +, U, etc.)
    clean_line=$(echo "$line" | sed 's/^[-+ U]*//')

    # Extract SHA (first field) and path (second field)
    sha=$(echo "$clean_line" | awk '{print $1}')
    path=$(echo "$clean_line" | awk '{print $2}')

    # Get the URL for this submodule path
    url=$(get_submodule_url "$path")

    # Remove "services/agent-environment/" prefix from path for display
    display_path=$(echo "$path" | sed 's|^services/agent-environment||')

    # Output in CSV format: URL,SHA,PATH
    echo "$url,$sha,$display_path"
done
