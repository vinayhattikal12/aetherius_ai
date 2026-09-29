from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from backend.app.core.database import get_db
from backend.app.schemas.user import UserCreate, UserLogin, UserResponse, Token
from backend.app.models.user import User
from backend.app.models.settings import UserSettings
from backend.app.core.security import create_access_token, get_password_hash, verify_password

router = APIRouter()


@router.post("/register", response_model=UserResponse)
async def register_user(
    data: UserCreate,
    db: AsyncSession = Depends(get_db)
):
    """Register a new user account."""
    existing = await db.execute(select(User).where(User.email == data.email))
    if existing.scalars().first():
        raise HTTPException(status_code=400, detail="User with this email already exists")
    
    hashed_pwd = get_password_hash(data.password)
    user = User(
        email=data.email,
        hashed_password=hashed_pwd,
        full_name=data.full_name,
        role=data.role
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    # Initialize user settings
    settings = UserSettings(
        user_id=user.id,
        theme="dark",
        privacy_mode="LOCAL_ONLY",
        default_workspace_slug="general"
    )
    db.add(settings)
    await db.commit()

    return user


@router.post("/login", response_model=Token)
async def login_user(
    data: UserLogin,
    db: AsyncSession = Depends(get_db)
):
    """Login and receive JWT authentication token."""
    result = await db.execute(select(User).where(User.email == data.email))
    user = result.scalars().first()
    if not user or not verify_password(data.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")
    
    token = create_access_token(subject=user.id)
    return Token(
        access_token=token,
        token_type="bearer",
        user=UserResponse.model_validate(user)
    )
