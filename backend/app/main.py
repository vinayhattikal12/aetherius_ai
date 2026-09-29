from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.app.core.config import settings
from backend.app.core.database import init_db, AsyncSessionLocal
from backend.app.core.logging import logger
from backend.app.services.model_registry_service import ModelRegistryService
from backend.app.services.workspace_service import WorkspaceService
from backend.app.api.v1.api import api_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting Aetherius AI Core Engine...")
    try:
        # Initialize PostgreSQL Database schema
        await init_db()
        
        # Seed initial models and workspaces
        async with AsyncSessionLocal() as session:
            await ModelRegistryService.seed_default_models(session)
            await WorkspaceService.seed_default_workspaces(session)
            
        logger.info("Aetherius AI Core initialized successfully.")
    except Exception as e:
        logger.error(f"Startup initialization notice: {e}")
    yield
    logger.info("Shutting down Aetherius AI Core Engine...")


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    lifespan=lifespan
)

# CORS middleware configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health_check():
    return {
        "status": "online",
        "app": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "environment": settings.ENVIRONMENT
    }


@app.get("/")
async def root():
    return {
        "message": "Welcome to Aetherius AI Core Platform",
        "version": settings.VERSION,
        "docs": "/docs"
    }


# Include v1 API routes
app.include_router(api_router, prefix=settings.API_V1_STR)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.app.main:app", host="127.0.0.1", port=8000, reload=True)
