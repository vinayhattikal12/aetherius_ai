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
    for key, val in update_data.items():
        setattr(settings, key, val)
    
    await db.commit()
    await db.refresh(settings)
    return settings
