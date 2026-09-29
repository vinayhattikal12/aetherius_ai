from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime


class KnowledgeBaseBase(BaseModel):
    name: str
    slug: str
    collection_type: str = "General"
    description: Optional[str] = None
    workspace_slug: str = "general"


class KnowledgeBaseCreate(KnowledgeBaseBase):
    pass


class DocumentResponse(BaseModel):
    id: str
    knowledge_base_id: str
    filename: str
    file_type: str
    file_size_bytes: int
    status: str
    chunk_count: int
    error_message: Optional[str] = None
    doc_metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DocumentChunkResponse(BaseModel):
    id: str
    document_id: str
    knowledge_base_id: str
    chunk_index: int
    content: str
    token_count: int
    chunk_metadata: Dict[str, Any] = Field(default_factory=dict)
    similarity_score: Optional[float] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class KnowledgeBaseResponse(KnowledgeBaseBase):
    id: str
    user_id: Optional[str] = None
    documents: List[DocumentResponse] = Field(default_factory=list)
    document_count: int = 0
    total_chunks: int = 0
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class RAGSearchRequest(BaseModel):
    query: str
    knowledge_base_slugs: Optional[List[str]] = None
    workspace_slug: Optional[str] = None
    top_k: int = 4
    min_similarity: float = 0.05


class RAGSearchResult(BaseModel):
    query: str
    chunks: List[DocumentChunkResponse] = Field(default_factory=list)
    sources: List[Dict[str, Any]] = Field(default_factory=list)
