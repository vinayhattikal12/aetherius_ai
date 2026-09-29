from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime


class MemoryBase(BaseModel):
    workspace_slug: str = "general"
    memory_type: str = "fact"  # fact, preference, episodic, semantic, summary
    content: str
    confidence_score: float = 1.0
    importance_weight: float = 1.0
    memory_metadata: Dict[str, Any] = Field(default_factory=dict)


class MemoryCreate(MemoryBase):
    user_id: Optional[str] = None
    source_conversation_id: Optional[str] = None


class MemoryUpdate(BaseModel):
    content: Optional[str] = None
    memory_type: Optional[str] = None
    confidence_score: Optional[float] = None
    importance_weight: Optional[float] = None
    memory_metadata: Optional[Dict[str, Any]] = None


class MemoryResponse(MemoryBase):
    id: str
    user_id: Optional[str] = None
    source_conversation_id: Optional[str] = None
    access_count: int = 0
    last_accessed_at: Optional[datetime] = None
    similarity_score: Optional[float] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class MemorySearchRequest(BaseModel):
    query: str
    workspace_slug: Optional[str] = None
    memory_type: Optional[str] = None
    top_k: int = 5
    min_similarity: float = 0.05


class MemorySearchResult(BaseModel):
    query: str
    memories: List[MemoryResponse] = Field(default_factory=list)
