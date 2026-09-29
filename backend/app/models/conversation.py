from sqlalchemy import String, Boolean, Integer, JSON, Text, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.app.models.base import BaseModel


class Conversation(BaseModel):
    __tablename__ = "conversations"

    user_id: Mapped[str] = mapped_column(String(36), nullable=True, index=True)
    workspace_slug: Mapped[str] = mapped_column(String(50), default="general", nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), default="New Conversation", nullable=False)
    model_name: Mapped[str] = mapped_column(String(100), default="llama3.2:3b", nullable=False)
    is_pinned: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Relationships
    messages = relationship("Message", back_populates="conversation", cascade="all, delete-orphan", order_by="Message.created_at")
    summary = relationship("ConversationSummary", back_populates="conversation", uselist=False, cascade="all, delete-orphan")


class Message(BaseModel):
    __tablename__ = "messages"

    conversation_id: Mapped[str] = mapped_column(String(36), ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(20), nullable=False) # user, assistant, system, tool
    content: Mapped[str] = mapped_column(Text, nullable=False)
    model_name: Mapped[str] = mapped_column(String(100), nullable=True)
    citations: Mapped[list] = mapped_column(JSON, default=list, nullable=False) # List of source chunks / web links
    token_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    extra_metadata: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)

    # Relationships
    conversation = relationship("Conversation", back_populates="messages")

    @property
    def attachments(self) -> list:
        if self.extra_metadata and isinstance(self.extra_metadata, dict):
            return self.extra_metadata.get("attachments", [])
        return []


class ConversationSummary(BaseModel):
    __tablename__ = "conversation_summaries"

    conversation_id: Mapped[str] = mapped_column(String(36), ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False, unique=True)
    summary_text: Mapped[str] = mapped_column(Text, nullable=False)
    last_summarized_message_id: Mapped[str] = mapped_column(String(36), nullable=True)

    # Relationships
    conversation = relationship("Conversation", back_populates="summary")
