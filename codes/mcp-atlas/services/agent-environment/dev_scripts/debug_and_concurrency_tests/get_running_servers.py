"""
Check what MCP servers are running via /list_tools and compare to what's configured in mcp_client.py
Useful as a quick check to see if some mcp servers errored during startup.
Does not check that they work tho (e.g. api key could be invalid and /call_tool will fail, but mcp server is running).

Usage (requires server to be running on port 1984, you can do "make run" or "make run-docker"):
uv run python get_running_servers.py
"""

import subprocess
import re
import os
import sys


def load_configured_servers():
    """Load the configured servers from mcp_client.py"""
    try:
        # Add the src directory to Python path so we can import the module
        src_path = os.path.join(os.path.dirname(__file__), "../../src")
        if src_path not in sys.path:
            sys.path.insert(0, src_path)

        # Import the mcp_client module directly
        from agent_environment.mcp_client import config

        # Extract server names from the config
        configured_servers = set(config["mcpServers"].keys())
        return configured_servers

    except ImportError as e:
        raise Exception(
            f'Could not import mcp_client module: {e}. Are you using "uv run ..."?'
        )
    except KeyError as e:
        raise Exception(f"Config structure error: {e}")
    except Exception as e:
        raise Exception(f"Error loading configured servers: {e}")


def main():
    load_configured_servers()  # to trigger the import warning at the top of this script

    try:
        # Step 1: Run the curl script and extract tool names
        print("Calling ./curl_scripts/mcp__list_tools.sh to get running mcp servers...")

        # Run the command: ./curl_scripts/mcp__list_tools.sh | jq | grep "^    \"name"
        curl_script_path = "./curl_scripts/mcp__list_tools.sh"

        if not os.path.exists(curl_script_path):
            print(f"Error: {curl_script_path} not found")
            sys.exit(1)

        # Run the command pipeline
        result = subprocess.run(
            ["bash", "-c", f"{curl_script_path} | jq | grep '^    \"name'"],
            capture_output=True,
            text=True,
            check=True,
        )

        tool_names_content = result.stdout

        # Write to temporary file
        with open("tool-names.txt", "w") as f:
            f.write(tool_names_content)

        # Step 2: Process with regex to extract server names
        pattern = r".*\"([a-zA-Z0-9\-]+)_.*"
        server_names = set()

        for line in tool_names_content.splitlines():
            line = line.strip()
            if line:
                match = re.search(pattern, line)
                if match:
                    server_name = match.group(1)
                    server_names.add(server_name)

        # Step 3: Remove duplicates (already done with set) and save
        print(f"\nFound {len(server_names)} unique running servers\n")

        # Sort for consistent output
        sorted_servers = sorted(server_names)

        print(f"Running servers: {sorted_servers}\n")

        # Step 3.5: Compare with configured servers

        configured_servers = load_configured_servers()
        not_running = configured_servers - server_names

        if not_running:
            print(f"⚠️  CONFIGURED BUT NOT RUNNING ({len(not_running)} servers):")
            for server in sorted(not_running):
                print(f"  ❌ {server}")
        else:
            print(
                f"✅ All {len(configured_servers)} mcp servers in mcp_client.py are running!"
            )

        # Step 4: Clean up temporary file
        if os.path.exists("tool-names.txt"):
            os.remove("tool-names.txt")

        print("\nDone!")

    except subprocess.CalledProcessError as e:
        print(f"Error running command: {e}")
        print(f"stdout: {e.stdout}")
        print(f"stderr: {e.stderr}")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
