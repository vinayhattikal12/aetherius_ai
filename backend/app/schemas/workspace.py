from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime


class WorkspaceBase(BaseModel):
    name: str
    slug: str
    description: Optional[str] = None
    icon: str = "sparkles"
    color: str = "#6366f1"
    is_system: bool = False
    instructions: str = ""
    preferred_model: Optional[str] = None
    enabled_tools: List[str] = Field(default_factory=list)
    ui_capabilities: Dict[str, Any] = Field(default_factory=dict)


class WorkspaceCreate(WorkspaceBase):
    pass


class WorkspaceUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    icon: Optional[str] = None
    color: Optional[str] = None
    instructions: Optional[str] = None
    preferred_model: Optional[str] = None
    enabled_tools: Optional[List[str]] = None
    ui_capabilities: Optional[Dict[str, Any]] = None


class WorkspaceResponse(WorkspaceBase):
    id: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
