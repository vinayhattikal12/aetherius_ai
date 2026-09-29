from sqlalchemy import String, Integer, Float, Text, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.app.models.base import BaseModel


class KnowledgeBase(BaseModel):
    __tablename__ = "knowledge_bases"

    user_id: Mapped[str] = mapped_column(String(36), nullable=True, index=True)
    workspace_slug: Mapped[str] = mapped_column(String(50), default="general", nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    collection_type: Mapped[str] = mapped_column(String(50), default="General", nullable=False) # General, College, Company, Projects, Research, Personal, Custom
    description: Mapped[str] = mapped_column(Text, nullable=True)

    # Relationships
    documents = relationship("Document", back_populates="knowledge_base", cascade="all, delete-orphan")
    chunks = relationship("DocumentChunk", back_populates="knowledge_base", cascade="all, delete-orphan")


class Document(BaseModel):
    __tablename__ = "documents"

    knowledge_base_id: Mapped[str] = mapped_column(String(36), ForeignKey("knowledge_bases.id", ondelete="CASCADE"), nullable=False, index=True)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    file_type: Mapped[str] = mapped_column(String(20), nullable=False) # pdf, docx, txt, md, csv
    file_size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    storage_path: Mapped[str] = mapped_column(String(500), nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="pending") # pending, parsing, chunked, embedded, ready, error
    chunk_count: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[str] = mapped_column(Text, nullable=True)
    doc_metadata: Mapped[dict] = mapped_column(JSON, default=dict)

    # Relationships
    knowledge_base = relationship("KnowledgeBase", back_populates="documents")
    chunks = relationship("DocumentChunk", back_populates="document", cascade="all, delete-orphan")


class DocumentChunk(BaseModel):
    __tablename__ = "document_chunks"

    document_id: Mapped[str] = mapped_column(String(36), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    knowledge_base_id: Mapped[str] = mapped_column(String(36), ForeignKey("knowledge_bases.id", ondelete="CASCADE"), nullable=False, index=True)
    chunk_index: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    embedding_vector: Mapped[list] = mapped_column(JSON, default=list, nullable=False) # Vector array representation
    token_count: Mapped[int] = mapped_column(Integer, default=0)
    chunk_metadata: Mapped[dict] = mapped_column(JSON, default=dict) # page_number, heading, source_name

    # Relationships
    document = relationship("Document", back_populates="chunks")
    knowledge_base = relationship("KnowledgeBase", back_populates="chunks")
