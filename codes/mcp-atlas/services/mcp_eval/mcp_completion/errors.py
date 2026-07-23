"""Error classes for MCP evaluation."""


class MCPClientValidationError(Exception):
    """MCP client validation error."""

    pass


class MCPClientToolExecutionError(Exception):
    """MCP client tool execution error."""

    pass


class MCPClientInvalidToolError(Exception):
    """MCP client invalid tool error."""

    pass


class MCPClientTimeoutError(Exception):
    """MCP client timeout error."""

    pass
