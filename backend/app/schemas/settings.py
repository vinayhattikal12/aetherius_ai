from typing import Dict, Any, Optional
from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime


class UserSettingsBase(BaseModel):
    theme: str = "dark" # dark, light, system
    privacy_mode: str = "LOCAL_ONLY" # LOCAL_ONLY, HYBRID, CLOUD
    default_workspace_slug: str = "general"
    auto_routing_enabled: bool = True
    telemetry_enabled: bool = False
    onboarding_completed: bool = False
    custom_settings: Dict[str, Any] = Field(default_factory=dict)


class UserSettingsUpdate(BaseModel):
    theme: Optional[str] = None
    privacy_mode: Optional[str] = None
    default_workspace_slug: Optional[str] = None
    auto_routing_enabled: Optional[bool] = None
    telemetry_enabled: Optional[bool] = None
    onboarding_completed: Optional[bool] = None
    custom_settings: Optional[Dict[str, Any]] = None


class UserSettingsResponse(UserSettingsBase):
    id: str
    user_id: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
