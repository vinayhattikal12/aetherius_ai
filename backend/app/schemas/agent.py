from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime


class AgentDefinitionBase(BaseModel):
    name: str
    slug: str
    role_type: str  # coder, researcher, analyst, executive, custom
    workspace_slug: str = "general"
    description: str
    system_instructions: str
    allowed_tools: List[str] = Field(default_factory=list)
    preferred_model_id: str = "llama3.2:3b"
    is_system: bool = True
    is_active: bool = True
    max_steps: int = 5


class AgentDefinitionCreate(AgentDefinitionBase):
    pass


class AgentDefinitionResponse(AgentDefinitionBase):
    id: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AgentTaskStepResponse(BaseModel):
    id: str
    task_id: str
    step_index: int
    step_type: str  # plan, tool_call, observation, reflection, final_output
    content: str
    tool_name: Optional[str] = None
    tool_arguments: Dict[str, Any] = Field(default_factory=dict)
    tool_result: Dict[str, Any] = Field(default_factory=dict)
    duration_ms: float
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AgentTaskCreate(BaseModel):
    agent_slug: str
    goal_prompt: str
    title: Optional[str] = None
    workspace_slug: str = "general"
    use_rag: bool = True
    use_web_search: bool = False


class AgentTaskResponse(BaseModel):
    id: str
    agent_id: str
    agent_slug: Optional[str] = None
    agent_name: Optional[str] = None
    workspace_slug: str
    title: str
    goal_prompt: str
    status: str  # pending, planning, running, completed, failed
    result_output: Optional[str] = None
    error_message: Optional[str] = None
    execution_metadata: Dict[str, Any] = Field(default_factory=dict)
    steps: List[AgentTaskStepResponse] = Field(default_factory=list)
    completed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
