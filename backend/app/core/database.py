from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import declarative_base
from sqlalchemy import text
from backend.app.core.config import settings
from backend.app.core.logging import logger

# Create async engine
engine_kwargs = {"echo": False, "future": True}
if "sqlite" in settings.ASYNC_DATABASE_URI:
    engine = create_async_engine(settings.ASYNC_DATABASE_URI, **engine_kwargs)
else:
    engine = create_async_engine(
        settings.ASYNC_DATABASE_URI,
        pool_size=10,
        max_overflow=20,
        pool_pre_ping=True,
        connect_args={"server_settings": {"client_encoding": "utf8"}},
        **engine_kwargs,
    )

# Async session factory
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

Base = declarative_base()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency for obtaining database sessions."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db() -> None:
    """Initialize database extensions and tables."""
    # 1. Attempt vector extension in isolated connection
    try:
        async with engine.connect() as conn:
            try:
                await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
                await conn.commit()
                logger.info("pgvector extension verified.")
            except Exception as ext_err:
                logger.warning(f"pgvector extension notice (will be available via Docker container): {ext_err}")
                await conn.rollback()
    except Exception as e:
        logger.warning(f"Extension check notice: {e}")

    # 2. Create all registered tables
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            logger.info("PostgreSQL database tables created and verified.")
    except Exception as e:
        logger.error(f"Failed to create PostgreSQL tables: {e}")
        raise
