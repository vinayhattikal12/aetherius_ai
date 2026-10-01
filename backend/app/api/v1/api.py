from fastapi import APIRouter
from backend.app.api.v1.endpoints import (
    system,
    models,
    workspaces,
    settings,
    auth,
    conversations,
    chat,
    knowledge,
    web_search,
    memory,
    router as router_endpoint,
    tools,
    agents,
    audit,
    export,
    diagnostics,
    artifacts,
)

api_router = APIRouter()

api_router.include_router(system.router, prefix="/system", tags=["System & Hardware"])
api_router.include_router(models.router, prefix="/models", tags=["Model Registry & Compatibility"])
api_router.include_router(workspaces.router, prefix="/workspaces", tags=["Workspaces"])
api_router.include_router(settings.router, prefix="/settings", tags=["Settings"])
api_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
api_router.include_router(conversations.router, prefix="/conversations", tags=["Conversations"])
api_router.include_router(chat.router, prefix="/chat", tags=["Chat & Completions"])
api_router.include_router(knowledge.router, prefix="/knowledge", tags=["Knowledge & RAG"])
api_router.include_router(web_search.router, prefix="/web-search", tags=["Web Search"])
api_router.include_router(memory.router, prefix="/memory", tags=["Memory Engine"])
api_router.include_router(router_endpoint.router, prefix="/router", tags=["Model Router"])
api_router.include_router(tools.router, prefix="/tools", tags=["Workspace Tools"])
api_router.include_router(agents.router, prefix="/agents", tags=["Autonomous Agents"])
api_router.include_router(audit.router, prefix="/audit", tags=["Audit & Compliance"])
api_router.include_router(export.router, prefix="/export", tags=["Export & Data Portability"])
api_router.include_router(diagnostics.router, prefix="/diagnostics", tags=["System Diagnostics"])
api_router.include_router(artifacts.router, prefix="/artifacts", tags=["Generated Document & Visual Artifacts"])
