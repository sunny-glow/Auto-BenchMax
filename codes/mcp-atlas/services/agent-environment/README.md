# Agent Environment

A Docker container with ~40 pre-configured Model Context Protocol (MCP) servers for AI agents.

## Quick Start

1. **Set up environment variables:**
   This depends on `.env` that should be passed in from the root level directory of this repo (copied from env.template).

   Setup the API keys for the MCP servers you want to use. You'll have to get your own API keys.
   
   For quick start, modify `.env` to set a few servers that don't need API keys:
   `ENABLED_SERVERS=calculator,wikipedia,filesystem,git,fetch`

2. **Run the container:**

   The preferred way is with Docker (run these commands from the root level directory)
   ```bash
   make build
   make run-docker
   ```

   If you don't want to use docker, you can do `make run`, but you'll need to fix the configs that reference the `/data` dir in `src/agent_environment/mcp_server_template.json` and change that to the actual location of the ./data folder on your computer.
   ```bash
   # First, fix references to /data dir in mcp_server_template.json
   make run
   ```

   The container takes 1-3 minutes to start up depending on the number of MCP servers enabled. Once ready, it provides HTTP POST endpoints for `/call-tool` and `/list-tools` on port 1984.

3. **Test it's working:**
   ```bash
   ./dev_scripts/debug_and_concurrency_tests/curl_scripts/mcp__list_tools.sh
   ./dev_scripts/debug_and_concurrency_tests/curl_scripts/mcp_git.sh
   ```

## Available MCP Servers

This project includes 36 MCP servers as configured in `src/agent_environment/mcp_server_template.json`. Some require API keys. To see required API keys and notes on how to get them, see `env.template`

- **No API keys needed:** calculator, wikipedia, filesystem, git, fetch, arxiv, f1-mcp-server, etc.
- **API keys required:** GitHub, Google Maps, Slack, Reddit, Weather, YouTube, and others

See `env.template` for basic information about each API key and where to get it. And see `data_exports/README.md` for info on how to upload data to online services.

## Server Selection

To run only specific servers (useful for testing without API keys):

```bash
# In your .env file:
ENABLED_SERVERS=calculator,wikipedia,filesystem,git,fetch
```

## API Keys

Check `env.template` for all available API key configurations.

## Implementation details
This depends on https://github.com/jlowin/fastmcp

By default, caching is enabled. If a request is successful, it will be cached, and subsequent identical requests will return the cached value.

At high throughputs, some of the MCP servers may not perform as well or may freeze up. Replicas are recommended for high throughput.
