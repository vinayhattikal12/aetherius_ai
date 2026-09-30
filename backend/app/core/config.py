import os
from typing import List
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "Aetherius AI"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"
    
    # Environment
    ENVIRONMENT: str = Field(default="development")
    DEBUG: bool = Field(default=True)
    
    # Database - STRICT POSTGRESQL ONLY
    POSTGRES_SERVER: str = Field(default="localhost")
    POSTGRES_PORT: int = Field(default=54329) # Default dedicated Aetherius cluster or standard 5432
    POSTGRES_USER: str = Field(default="postgres")
    POSTGRES_PASSWORD: str = Field(default="postgrespassword")
    POSTGRES_DB: str = Field(default="aetherius")
    
    # Custom DATABASE_URL override if provided
    DATABASE_URL: str | None = None
    
    @property
    def ASYNC_DATABASE_URI(self) -> str:
        if self.DATABASE_URL:
            if self.DATABASE_URL.startswith("postgresql://"):
                return self.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)
            return self.DATABASE_URL
        auth = f"{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@" if self.POSTGRES_PASSWORD else (f"{self.POSTGRES_USER}@" if self.POSTGRES_USER else "")
        return f"postgresql+asyncpg://{auth}{self.POSTGRES_SERVER}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
    
    @property
    def SYNC_DATABASE_URI(self) -> str:
        if self.DATABASE_URL:
            if self.DATABASE_URL.startswith("postgresql+asyncpg://"):
                return self.DATABASE_URL.replace("postgresql+asyncpg://", "postgresql+psycopg://", 1)
            return self.DATABASE_URL
        auth = f"{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@" if self.POSTGRES_PASSWORD else (f"{self.POSTGRES_USER}@" if self.POSTGRES_USER else "")
        return f"postgresql+psycopg://{auth}{self.POSTGRES_SERVER}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"

    # Storage
    UPLOAD_DIR: str = "data/storage/uploads"

    # Security
    SECRET_KEY: str = Field(default=os.getenv("AETHERIUS_SECRET_KEY", "aetherius-secure-default-key-change-in-prod-2026"))
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days
    
    # CORS - Explicit whitelisted origins
    CORS_ORIGINS: List[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
        "electron://localhost",
        "tauri://localhost"
    ]

    # Sandboxing & Execution Security
    ENABLE_PYTHON_SANDBOX: bool = Field(default=False)
    LOCAL_ONLY: bool = Field(default=False)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"
    )


settings = Settings()
