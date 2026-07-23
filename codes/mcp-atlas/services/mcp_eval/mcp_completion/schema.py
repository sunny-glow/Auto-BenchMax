"""Schema definitions for MCP evaluation."""

from litellm.types.utils import Message as MessageType
from typing import Dict, List, Literal, Optional, Union, Any
from pydantic import BaseModel, Field


class ToolCallSchema(BaseModel):
    """OpenAI Function Calling Schema."""

    type: Literal["function"]
    function: Dict[str, Any]


class ToolCall(BaseModel):
    """Tool call representation."""

    id: str
    type: Literal["function"]
    function: Dict[str, str]


class SystemMessage(BaseModel):
    """System message."""

    role: Literal["system"]
    content: str


class UserMessage(BaseModel):
    """User message."""

    role: Literal["user"]
    content: str


class AssistantMessage(BaseModel):
    """Assistant message."""

    role: Literal["assistant"]
    original_message: MessageType
    content: Optional[str] = None
    tool_calls: Optional[List[ToolCall]] = None


class TextContent(BaseModel):
    """Text content for tool outputs."""

    type: Literal["text"]
    text: str


class ImageContent(BaseModel):
    """Image content for tool outputs."""

    type: Literal["image"]
    data: str
    mimeType: str


class ResourceContent(BaseModel):
    """Resource content for tool outputs."""

    type: Literal["resource"]
    resource: Dict[str, Any]


# Union type for all content types
Content = Union[TextContent, ImageContent, ResourceContent]


class ToolCallOutputMessage(BaseModel):
    """Tool call output message."""

    role: Literal["tool"]
    tool_call_id: str
    content: List[Content] = Field(default_factory=list)

    def model_dump(self, **kwargs) -> Dict[str, Any]:
        """
        Custom serialization for OpenAI API compatibility.
        OpenAI expects tool message content as a string, not a list.
        """
        # Serialize content list to a string
        content_parts = []
        for item in self.content:
            if isinstance(item, TextContent):
                content_parts.append(item.text)
            elif isinstance(item, ImageContent):
                # Describe the image since OpenAI tool messages don't support raw images
                content_parts.append(
                    f"[Image: {item.mimeType}, data length: {len(item.data)} bytes]"
                )
            elif isinstance(item, ResourceContent):
                # Serialize resource data
                import json

                content_parts.append(f"[Resource: {json.dumps(item.resource)}]")

        content_str = "\n\n".join(content_parts) if content_parts else ""

        return {
            "role": self.role,
            "tool_call_id": self.tool_call_id,
            "content": content_str,
        }


Message = Union[SystemMessage, UserMessage, AssistantMessage, ToolCallOutputMessage]


class RunAgentAPIRequestBody(BaseModel):
    """Request body for running MCP eval."""

    model: str
    messages: List[Message]
    enabled_tools: List[str] = Field(alias="enabledTools")
    max_turns: int = Field(20, alias="maxTurns")

    class Config:
        populate_by_name = True


class CallToolResponse(BaseModel):
    """Response from calling a tool."""

    content: List[Content] = Field(default_factory=list)
    is_error: bool = Field(False, alias="isError")

    class Config:
        populate_by_name = True


class ToolDefinition(BaseModel):
    """MCP tool definition."""

    name: str
    description: Optional[str] = None
    input_schema: Dict[str, Any] = Field(alias="inputSchema")
    server: Optional[str] = None
    disabled: Optional[bool] = None

    class Config:
        populate_by_name = True


class MCPTool(BaseModel):
    """MCP Tool schema."""

    name: str
    description: str
    input_schema: Dict[str, Any] = Field(alias="inputSchema")

    class Config:
        populate_by_name = True
