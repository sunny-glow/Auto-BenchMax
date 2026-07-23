#!/bin/bash

# Generate the actual config from template by reading environment variables passed into `docker run --env-file .env`
envsubst < src/agent_environment/mcp_server_template.json > src/agent_environment/mcp_server_config.json

# Execute the original command
exec "$@"
