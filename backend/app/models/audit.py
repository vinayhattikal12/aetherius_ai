from sqlalchemy import String, JSON, Text
from sqlalchemy.orm import Mapped, mapped_column
from backend.app.models.base import BaseModel


class AuditLog(BaseModel):
    __tablename__ = "audit_logs"

    event_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(String(36), nullable=True, index=True)
    actor: Mapped[str] = mapped_column(String(100), default="system")
    details: Mapped[dict] = mapped_column(JSON, default=dict)
    ip_address: Mapped[str] = mapped_column(String(45), nullable=True)
