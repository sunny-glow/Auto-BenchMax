FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

RUN apt-get update && apt-get install -y npm bash git procps curl gettext-base && rm -rf /var/lib/apt/lists/*

# Need to install nodejs from elsewhere, because bookworm-slim is based on debian, and the available version of nodejs is 18, which is too old
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - && apt-get update
RUN apt-get install -y nodejs && rm -rf /var/lib/apt/lists/*

# Pre-install all MCP server packages (NPX and UVX), saves approx 1 minute of startup time
COPY dev_scripts/install_mcp_packages.sh /
RUN /install_mcp_packages.sh && rm /install_mcp_packages.sh

# Copy project files and set up workspace
WORKDIR /agent-environment
COPY . .
RUN uv venv --python 3.12

# Move /agent-environment/data to /data
RUN mkdir -p /data
RUN mv /agent-environment/data/* /data/ 2>/dev/null || true
RUN rm -rf /agent-environment/data

# Install git submodules from CSV to specified directories
RUN while IFS=',' read -r url sha path; do \
    echo "Installing $url at $sha to $path"; \
    rm -rf "$path" 2>/dev/null || true; \
    git clone "$url" "$path"; \
    cd "$path" && git checkout "$sha"; \
done < /data/repos/git_submodule_info.csv

# Set up MCP code executor workspace (depends on copied repo structure)
WORKDIR /data/repos/mcp_code_executor_workspace
RUN uv sync
WORKDIR /agent-environment

RUN rm -rf /agent-environment/dev_scripts

# Sync project dependencies (requires pyproject.toml and uv.lock from COPY)
RUN uv sync

EXPOSE 1984

# Set the entrypoint (this always runs to generate mcp_server_config.json from template)
ENTRYPOINT ["/agent-environment/entrypoint.sh"]

# Set the default command (users can override this)
CMD ["uv", "run", "python", "-m", "uvicorn", "agent_environment.main:app", "--host", "0.0.0.0", "--port", "1984"]
