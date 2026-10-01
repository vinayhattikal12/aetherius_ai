from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field, ConfigDict, model_validator
from datetime import datetime


class SourceCitation(BaseModel):
    source_type: str = "document" # "document" or "web"
    title: str
    snippet: str
    url: Optional[str] = None
    source_domain: Optional[str] = None
    page_number: Optional[int] = None
    chunk_index: Optional[int] = None
    similarity_score: Optional[float] = None


class ChatAttachment(BaseModel):
    id: str
    filename: str
    file_type: str # image/png, application/pdf, etc.
    file_size_bytes: int = 0
    storage_path: Optional[str] = None
    is_image: bool = False
    preview_url: Optional[str] = None
    extracted_text: Optional[str] = None


class MessageBase(BaseModel):
    role: str # user, assistant, system, tool
    content: str
    model_name: Optional[str] = None
    citations: List[SourceCitation] = Field(default_factory=list)
    attachments: List[ChatAttachment] = Field(default_factory=list)
    extra_metadata: Dict[str, Any] = Field(default_factory=dict)


class MessageCreate(MessageBase):
    pass


class MessageResponse(MessageBase):
    id: str
    conversation_id: str
    token_count: int = 0
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @model_validator(mode="before")
    @classmethod
    def populate_attachments(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if not data.get("attachments") and data.get("extra_metadata"):
                data["attachments"] = data["extra_metadata"].get("attachments", [])
        return data


class ConversationBase(BaseModel):
    workspace_slug: str = "general"
    title: str = "New Conversation"
    model_name: str = "llama3.2:3b"
    is_pinned: bool = False


class ConversationCreate(ConversationBase):
    pass


class ConversationUpdate(BaseModel):
    title: Optional[str] = None
    model_name: Optional[str] = None
    is_pinned: Optional[bool] = None


class ConversationResponse(ConversationBase):
    id: str
    user_id: Optional[str] = None
    messages: List[MessageResponse] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ChatCompletionRequest(BaseModel):
    conversation_id: Optional[str] = None
    workspace_slug: str = "general"
    model_name: Optional[str] = None
    model_id: Optional[str] = None
    message: str
    attachments: List[ChatAttachment] = Field(default_factory=list)
    enable_web_search: bool = False
    use_web_search: Optional[bool] = None
    enable_knowledge_rag: bool = True
    use_rag: Optional[bool] = None
    knowledge_base_slugs: List[str] = Field(default_factory=list)
    temperature: float = 0.7
    max_tokens: int = 2048

    @model_validator(mode="before")
    @classmethod
    def normalize_fields(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if not data.get("model_name") and data.get("model_id"):
                data["model_name"] = data["model_id"]
            if data.get("use_web_search") is not None:
                data["enable_web_search"] = data["use_web_search"]
            if data.get("use_rag") is not None:
                data["enable_knowledge_rag"] = data["use_rag"]
        return data


class ChatCompletionResponse(BaseModel):
    conversation_id: str
    user_message: MessageResponse
    assistant_message: MessageResponse
    model_used: str
    citations: List[SourceCitation] = Field(default_factory=list)
    web_searched: bool = False
    rag_applied: bool = False
