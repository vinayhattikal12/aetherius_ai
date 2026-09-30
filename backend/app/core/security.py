import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional, Union, Any
import jwt
import bcrypt
from fastapi import HTTPException, Security, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from backend.app.core.config import settings

ALGORITHM = "HS256"
security_scheme = HTTPBearer(auto_error=False)
LAUNCH_TOKEN = os.getenv("AETHERIUS_LAUNCH_TOKEN") or secrets.token_hex(24)


async def verify_launch_token(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Security(security_scheme)
) -> str:
    """
    Validates per-launch desktop token and blocks unauthorized cross-origin requests from web browsers.
    """
    # 1. Check Origin Header (Protect local API against malicious website requests)
    origin = request.headers.get("origin")
    if origin:
        allowed_origins = [o.rstrip("/") for o in settings.CORS_ORIGINS]
        is_allowed = (
            origin.rstrip("/") in allowed_origins 
            or any(origin.startswith(prefix) for prefix in ["http://localhost", "http://127.0.0.1", "electron://", "tauri://", "app://"])
        )
        if not is_allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cross-origin access from unverified web origin is forbidden."
            )

    # 2. Token Authentication
    header_token = request.headers.get("X-Aetherius-Token")
    provided_token = credentials.credentials if credentials else header_token

    # In strict mode or when AETHERIUS_REQUIRE_AUTH / launch token is configured:
    require_auth = os.getenv("AETHERIUS_REQUIRE_AUTH", "false").lower() in ("true", "1") or settings.ENVIRONMENT == "production"
    if require_auth:
        expected = os.getenv("AETHERIUS_LAUNCH_TOKEN") or LAUNCH_TOKEN
        if not provided_token or provided_token != expected:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or missing Aetherius API authentication token."
            )

    return provided_token or LAUNCH_TOKEN


def create_access_token(subject: Union[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode = {"exp": expire, "sub": str(subject)}
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))
    except Exception:
        return False


def get_password_hash(password: str) -> str:
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")

