from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from backend.app.core.database import get_db
from backend.app.schemas.settings import (
    UserSettingsResponse,
    UserSettingsUpdate
)
from backend.app.models.settings import UserSettings
from backend.app.models.user import User

router = APIRouter()


@router.get("/", response_model=UserSettingsResponse)
async def get_settings(
    db: AsyncSession = Depends(get_db)
):
    """Get active user settings or default settings."""
    result = await db.execute(select(UserSettings))
    settings = result.scalars().first()
    
    if not settings:
        # Create default system user and settings
        result_user = await db.execute(select(User).where(User.email == "local@aetherius.ai"))
        user = result_user.scalars().first()
        if not user:
            user = User(
                email="local@aetherius.ai",
                hashed_password="local_placeholder_hash",
                full_name="Aetherius Local User",
                role="developer",
                is_active=True
            )
            db.add(user)
            await db.commit()
            await db.refresh(user)
        
        settings = UserSettings(
            user_id=user.id,
            theme="dark",
            privacy_mode="LOCAL_ONLY",
            default_workspace_slug="general",
            auto_routing_enabled=True,
            onboarding_completed=False,
            telemetry_enabled=False
        )
        db.add(settings)
        await db.commit()
        await db.refresh(settings)

    return settings


@router.patch("/", response_model=UserSettingsResponse)
async def update_settings(
    updates: UserSettingsUpdate,
    db: AsyncSession = Depends(get_db)
):
    """Update active user settings (e.g. theme, privacy mode, onboarding completion)."""
    result = await db.execute(select(UserSettings))
    settings = result.scalars().first()
    
    if not settings:
        # If not found, fetch or create first
        await get_settings(db)
        result = await db.execute(select(UserSettings))
        settings = result.scalars().first()
    
    update_data = updates.model_dump(exclude_unset=True)
    if "custom_settings" in update_data and update_data["custom_settings"]:
        existing_custom = settings.custom_settings or {}
        merged_custom = {**existing_custom, **update_data["custom_settings"]}
        settings.custom_settings = merged_custom

        # Apply cloud API keys to environment variables and live provider instance
        import os
        from backend.app.services.providers.model_manager import model_manager

        if merged_custom.get("anthropic_api_key"):
            os.environ["ANTHROPIC_API_KEY"] = merged_custom["anthropic_api_key"]
            model_manager.cloud.anthropic_key = merged_custom["anthropic_api_key"]
        if merged_custom.get("openai_api_key"):
            os.environ["OPENAI_API_KEY"] = merged_custom["openai_api_key"]
            model_manager.cloud.openai_key = merged_custom["openai_api_key"]
        if merged_custom.get("groq_api_key"):
            os.environ["GROQ_API_KEY"] = merged_custom["groq_api_key"]
            model_manager.cloud.groq_key = merged_custom["groq_api_key"]
        if merged_custom.get("hf_token"):
            os.environ["HF_TOKEN"] = merged_custom["hf_token"]
            model_manager.cloud.hf_key = merged_custom["hf_token"]

        del update_data["custom_settings"]

    for key, val in update_data.items():
        setattr(settings, key, val)
    
    await db.commit()
    await db.refresh(settings)
    return settings
