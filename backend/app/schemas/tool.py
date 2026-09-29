from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field


class ToolParameter(BaseModel):
    name: str
    type: str
    description: str
    required: bool = True
    default: Optional[Any] = None


class ToolDefinition(BaseModel):
    name: str
    display_name: str
    category: str  # workspace, math, system, code, finance, research
    description: str
    parameters: List[ToolParameter] = Field(default_factory=list)
    is_safe: bool = True
    workspace_types: List[str] = Field(default_factory=lambda: ["general"])


class ToolExecutionRequest(BaseModel):
    tool_name: str
    arguments: Dict[str, Any] = Field(default_factory=dict)
    workspace_slug: str = "general"


class ToolExecutionResponse(BaseModel):
    tool_name: str
    status: str  # success, error
    result: Any
    error_message: Optional[str] = None
    execution_time_ms: float
