import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.pool import NullPool

from backend.app.main import app
from backend.app.core.config import settings
from backend.app.core.database import Base, get_db
from backend.app.services.model_registry_service import ModelRegistryService
from backend.app.services.workspace_service import WorkspaceService

# Create test engine with NullPool to prevent connection pool loop detachment between tests
test_engine = create_async_engine(
    settings.ASYNC_DATABASE_URI,
    poolclass=NullPool,
    echo=False,
)

TestAsyncSessionLocal = async_sessionmaker(
    bind=test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def override_get_db():
    async with TestAsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


app.dependency_overrides[get_db] = override_get_db


@pytest_asyncio.fixture(scope="function", autouse=False)
async def setup_test_db():
    """Ensure schema is initialized and default data is seeded for integration tests."""
    try:
        async with test_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        
        async with TestAsyncSessionLocal() as session:
            await ModelRegistryService.seed_default_models(session)
            await WorkspaceService.seed_default_workspaces(session)
    except Exception as e:
        pytest.skip(f"Database not available for integration test: {e}")


@pytest_asyncio.fixture(scope="function")
async def async_client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test", timeout=60.0) as client:
        yield client


@pytest_asyncio.fixture(scope="function")
async def test_db():
    async with TestAsyncSessionLocal() as session:
        yield session
