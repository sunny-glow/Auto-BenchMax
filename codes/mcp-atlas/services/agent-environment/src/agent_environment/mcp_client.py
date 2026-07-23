from fastmcp import Client
from fastmcp.client.logging import LogMessage
from .logger import create_logger
import json
import random
import os
import re
from pathlib import Path

logger = create_logger(__name__)

# Load template to check for API key requirements
template_path = Path(__file__).parent / "mcp_server_template.json"
with open(template_path) as f:
    template_config = json.load(f)

# Load actual config (after envsubst) for server execution
config_path = Path(__file__).parent / "mcp_server_config.json"
with open(config_path) as f:
    config = json.load(f)

# Default servers that don't require API keys (used when ENABLED_SERVERS is empty)
DEFAULT_SERVERS = [
    "arxiv",
    "calculator",
    "cli-mcp-server",
    "clinicaltrialsgov-mcp-server",
    "context7",
    "ddg-search",
    "desktop-commander",
    "fetch",
    "filesystem",
    "git",
    "mcp-code-executor",
    "mcp-server-code-runner",
    "memory",
    "met-museum",
    "open-library",
    "osm-mcp-server",
    "pubmed",
    "weather",
    "whois",
    "wikipedia",
]

# Filter servers based on ENABLED_SERVERS environment variable
enabled_servers = os.getenv("ENABLED_SERVERS", "").strip()

if "mcpServers" in config:
    if enabled_servers:
        # Explicit mode: use exactly what's in ENABLED_SERVERS (no auto-detection)
        enabled_list = [s.strip() for s in enabled_servers.split(",")]
        enabled_set = set(enabled_list)
        logger.info(f"Using explicit ENABLED_SERVERS: {', '.join(sorted(enabled_set))}")
    else:
        # Auto mode: use DEFAULT_SERVERS + auto-detect servers with API keys
        enabled_set = set(DEFAULT_SERVERS)
        logger.info(f"Using {len(DEFAULT_SERVERS)} default servers")

        # Auto-detect servers with all required API keys configured
        api_key_enabled = []
        for name in template_config.get("mcpServers", {}).keys():
            if name in enabled_set:
                continue  # Already in default list

            server_template = template_config["mcpServers"][name]
            required_vars = set()

            # Check env section for ${VAR} patterns
            if "env" in server_template and server_template["env"]:
                env_config = server_template["env"]
                if isinstance(env_config, list):
                    env_config = env_config[0] if env_config else {}

                for env_key, env_value in env_config.items():
                    if isinstance(env_value, str) and "${" in env_value:
                        # Extract all ${VAR} patterns from the string
                        var_names = re.findall(r"\$\{([^}]+)\}", env_value)
                        required_vars.update(var_names)

            # Check args array for ${VAR} patterns
            if "args" in server_template:
                args_list = server_template["args"]
                for arg in args_list:
                    if isinstance(arg, str) and "${" in arg:
                        # Extract all ${VAR} patterns from the arg
                        var_names = re.findall(r"\$\{([^}]+)\}", arg)
                        required_vars.update(var_names)

            # Check if all required variables are set
            if required_vars:
                all_keys_present = True
                for var_name in required_vars:
                    if not os.getenv(var_name, "").strip():
                        all_keys_present = False
                        break

                if all_keys_present:
                    enabled_set.add(name)
                    api_key_enabled.append(name)

        if api_key_enabled:
            logger.info(
                f"Auto-detected {len(api_key_enabled)} servers with API keys: {', '.join(sorted(api_key_enabled))}"
            )

    # Filter config to only enabled servers
    config["mcpServers"] = {
        name: server_config
        for name, server_config in config["mcpServers"].items()
        if name in enabled_set
    }
    logger.info(f"Total enabled: {len(enabled_set)} servers")

# Process env randomization for API key load balancing. If "env" is a list, pick a random one.
if "mcpServers" in config:
    for server_name, server_config in config["mcpServers"].items():
        if "env" in server_config and isinstance(server_config["env"], list):
            # Pick a random env from the list for load balancing
            env_list = server_config["env"]
            random_env = random.choice(env_list)
            server_config["env"] = random_env
            logger.info(
                f"Randomized env for server '{server_name}': selected from {len(env_list)} options"
            )


async def log_handler(message: LogMessage) -> None:
    level = message.level.upper()
    data = message.data
    match level:
        case "debug":
            logger.debug(data)
        case "info":
            logger.info(data)
        case "warning":
            logger.warning(data)
        case "error":
            logger.error(data)
        case "alert":
            logger.critical(data)
        case "emergency":
            logger.critical(data)
        case "critical":
            logger.critical(data)
        case _:
            logger.info(data)


client: Client = Client(
    config,
    log_handler=log_handler,
)
