from typing import List, Optional
from fastapi import APIRouter
from backend.app.schemas.tool import (
    ToolDefinition,
    ToolExecutionRequest,
    ToolExecutionResponse
)
from backend.app.services.tool_service import ToolExecutionEngine

router = APIRouter()


@router.get("/", response_model=List[ToolDefinition])
async def list_workspace_tools(workspace_slug: Optional[str] = None):
    """List available sandboxed tools for the active workspace."""
    return ToolExecutionEngine.list_tools(workspace_slug=workspace_slug)


@router.post("/execute", response_model=ToolExecutionResponse)
async def execute_tool(request: ToolExecutionRequest):
    """Execute a tool safely within sandboxed boundaries."""
    return ToolExecutionEngine.execute_tool(request=request)
