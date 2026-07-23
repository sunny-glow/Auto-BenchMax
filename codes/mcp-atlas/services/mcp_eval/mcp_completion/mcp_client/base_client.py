"""Base MCP client interface."""

from abc import ABC, abstractmethod
from typing import Any, List

from ..schema import ToolDefinition, CallToolResponse


class MCPClient(ABC):
    """Abstract base class for MCP clients."""

    @abstractmethod
    async def list_tools(self) -> List[ToolDefinition]:
        """List available tools."""
        pass

    @abstractmethod
    async def call_tool(self, tool_name: str, args: Any) -> CallToolResponse:
        """Call a tool with given arguments."""
        pass
