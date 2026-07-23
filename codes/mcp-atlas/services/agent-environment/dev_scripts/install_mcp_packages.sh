#!/bin/bash
set -e

echo "Installing NPX MCP server packages globally..."

# Pre-install all NPX MCP server packages globally to eliminate download time during runtime
npm install -g \
    @felores/airtable-mcp-server@0.3.0 \
    @alchemy/mcp-server@0.1.8 \
    @modelcontextprotocol/server-brave-search@0.6.2 \
    clinicaltrialsgov-mcp-server@1.0.8 \
    @upstash/context7-mcp@1.0.14 \
    @wonderwhy-er/desktop-commander@0.2.7 \
    @e2b/mcp-server@0.2.0 \
    exa-mcp-server@0.3.10 \
    @modelcontextprotocol/server-filesystem@2025.11.25 \
    @modelcontextprotocol/server-google-maps@0.6.2 \
    @geobio/google-workspace-server@0.1.0 \
    @translated/lara-mcp@0.0.11 \
    @geobio/code_execution_server@0.2.1 \
    mcp-server-code-runner@0.1.7 \
    @modelcontextprotocol/server-memory@2025.8.4 \
    metmuseum-mcp@0.9.2 \
    mongodb-mcp-server@0.2.0 \
    mcp-server-nationalparks@1.0.1 \
    @notionhq/notion-mcp-server@1.8.1 \
    @geobio/mcp-open-library@0.1.6 \
    slack-mcp-server@1.1.23 \
    @bharathvaj/whois-mcp@1.0.1

echo "Installing UVX MCP server packages..."
# Pre-install all UVX MCP server packages to eliminate download time during runtime
uv tool install arxiv-mcp-server==0.2.11
uv tool install mcp-server-calculator==0.2.0
uv tool install cli-mcp-server==0.2.5
uv tool install duckduckgo-mcp-server==0.1.1
uv tool install mcp-server-fetch==2025.4.7
uv tool install mcp-server-git==2025.7.1
uv tool install osm-mcp-server==0.1.1
uv tool install oxylabs-mcp==0.4.1
uv tool install mcp-server-twelve-data==0.2.5

echo "All UVX/NPX MCP packages installation complete. Ignored any that install from github!" 