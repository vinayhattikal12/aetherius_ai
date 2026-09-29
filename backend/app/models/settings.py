from sqlalchemy import String, Boolean, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.app.models.base import BaseModel


class UserSettings(BaseModel):
    __tablename__ = "user_settings"

    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True)
    theme: Mapped[str] = mapped_column(String(20), default="dark", nullable=False) # dark, light, system
    privacy_mode: Mapped[str] = mapped_column(String(20), default="LOCAL_ONLY", nullable=False) # LOCAL_ONLY, HYBRID, CLOUD
    default_workspace_slug: Mapped[str] = mapped_column(String(50), default="general", nullable=False)
    auto_routing_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    telemetry_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    onboarding_completed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    custom_settings: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)

    # Relationships
    user = relationship("User", back_populates="settings")
