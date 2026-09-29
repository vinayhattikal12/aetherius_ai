from sqlalchemy import String, Boolean, JSON, Text
from sqlalchemy.orm import Mapped, mapped_column
from backend.app.models.base import BaseModel


class Workspace(BaseModel):
    __tablename__ = "workspaces"

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    slug: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    icon: Mapped[str] = mapped_column(String(50), default="sparkles", nullable=False)
    color: Mapped[str] = mapped_column(String(20), default="#6366f1", nullable=False)
    is_system: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    instructions: Mapped[str] = mapped_column(Text, default="", nullable=False)
    preferred_model: Mapped[str] = mapped_column(String(100), nullable=True)
    enabled_tools: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    ui_capabilities: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
