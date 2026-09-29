from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field


class ResolvedEntity(BaseModel):
    name: str
    entity_type: str = "named_entity"  # "model", "technology", "library", "company", "concept", "person"
    recency_index: int = 0
    aliases: List[str] = []
    attributes: Dict[str, Any] = {}


class InformationRequirement(BaseModel):
    requirement_type: str  # "model_reasoning", "web_search", "rag_retrieval", "tool_execution", "code_execution"
    query_or_instruction: str
    priority: int = 1
    parameters: Dict[str, Any] = {}


class TaskPlan(BaseModel):
    requires_direct_model: bool = True
    requires_web_search: bool = False
    requires_rag: bool = False
    requires_tools: List[str] = []
    requires_code_execution: bool = False
    requires_agent_react: bool = False
    search_queries: List[str] = []
    rag_target_slugs: List[str] = []
    information_requirements: List[InformationRequirement] = []


class ExecutionContext(BaseModel):
    """
    Authoritative single representation of the understood user request,
    conversational state, task plan, constraints, and runtime context.
    """
    request_id: str
    conversation_id: Optional[int] = None
    raw_message: str
    canonical_query: str
    turn_type: str = "NEW_TOPIC"
    intent: str = "general_question"
    domain: str = "general"
    complexity: float = 0.3
    confidence: float = 0.9
    is_visual: bool = False
    visual_prompt: Optional[str] = None
    active_subject: Optional[str] = None
    entities: List[ResolvedEntity] = []
    resolved_references: Dict[str, str] = {}
    accumulated_constraints: Dict[str, Any] = {}
    temporal_context: Optional[str] = None
    location_context: Optional[str] = None
    plan: TaskPlan = Field(default_factory=TaskPlan)
    privacy_mode: str = "HYBRID"
    workspace_slug: str = "general"
    active_project: Optional[str] = None
    active_task: Optional[str] = None


# Alias for compatibility with various architectural naming conventions
ResolvedTask = ExecutionContext
