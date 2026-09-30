from sqlalchemy import String, Integer, Float, Text, JSON, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime
from backend.app.models.base import BaseModel


class Memory(BaseModel):
    __tablename__ = "memories"

    user_id: Mapped[str] = mapped_column(String(36), nullable=True, index=True)
    workspace_slug: Mapped[str] = mapped_column(String(50), default="general", nullable=False, index=True)
    memory_type: Mapped[str] = mapped_column(String(30), default="fact", nullable=False, index=True)  # fact, preference, episodic, semantic, summary
    content: Mapped[str] = mapped_column(Text, nullable=False)
    source_conversation_id: Mapped[str] = mapped_column(String(36), nullable=True, index=True)
    confidence_score: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    importance_weight: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)  # 1.0 (low) to 5.0 (critical)
    access_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_accessed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    
    from pgvector.sqlalchemy import Vector
    embedding_vector = mapped_column(Vector(384), nullable=True)
    
    memory_metadata: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
