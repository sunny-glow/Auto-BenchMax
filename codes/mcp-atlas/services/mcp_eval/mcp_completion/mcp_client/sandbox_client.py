"""Sandbox MCP client implementation."""

import asyncio
import json
import logging
from typing import Any, Dict, List, Optional

import httpx

from .base_client import MCPClient
from ..errors import MCPClientToolExecutionError
from ..schema import ToolDefinition, CallToolResponse, TextContent
from ..config import config

logger = logging.getLogger(__name__)


class SandboxMCPClient(MCPClient):
    """MCP client that connects to pre-running sandbox environments."""

    def __init__(
        self,
        sandbox_url: str,
        enabled_tools: Optional[List[str]] = None,  # if None, all tools are enabled
    ):
        self.sandbox_url = sandbox_url
        self.enabled_tools = enabled_tools
        self.tool_call_timeout = config.TOOL_CALL_TIMEOUT
        self.list_tools_timeout = config.LIST_TOOLS_TIMEOUT

    async def list_tools(self) -> List[ToolDefinition]:
        """List available tools from the sandbox."""
        try:
            async with httpx.AsyncClient(timeout=self.list_tools_timeout) as client:
                response = await client.post(
                    f"{self.sandbox_url}/list-tools",
                    headers={"Content-Type": "application/json"},
                )
                response.raise_for_status()

                tools_data = response.json()
                tools = [ToolDefinition(**tool) for tool in tools_data]

                # Filter by enabled tools if specified
                if self.enabled_tools:
                    tools = [tool for tool in tools if tool.name in self.enabled_tools]

                return tools

        except Exception as error:
            logger.error(f"Failed to list tools from sandbox: {error}")
            raise

    async def call_tool(self, tool_name: str, args: Any) -> CallToolResponse:
        """Call a tool in the sandbox."""
        try:
            body = {
                "tool_name": tool_name,
                "tool_args": args,
            }

            async with httpx.AsyncClient(timeout=self.tool_call_timeout) as client:
                response = await client.post(
                    f"{self.sandbox_url}/call-tool",
                    json=body,
                    headers={"Content-Type": "application/json"},
                )

                if response.status_code != 200:
                    error_text = response.text
                    return CallToolResponse(
                        content=[TextContent(type="text", text=error_text)],
                        is_error=True,
                    )

                response_data = response.json()
                return CallToolResponse(
                    content=response_data,
                    is_error=False,
                )

        except httpx.ReadTimeout:
            logger.error(f"Tool {tool_name} timed out after {self.tool_call_timeout}s")
            raise MCPClientToolExecutionError(
                f"Tool {tool_name} timed out after {self.tool_call_timeout}s"
            )
        except Exception as error:
            logger.error(f"Failed to call tool {tool_name} in sandbox: {error}")
            raise MCPClientToolExecutionError(
                f"Failed to call tool {tool_name}: {error}"
            )

    @property
    def sandbox_info(self) -> Dict[str, Any]:
        """Get sandbox information."""
        return {
            "sandbox_url": self.sandbox_url,
        }
