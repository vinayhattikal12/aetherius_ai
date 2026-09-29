from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from backend.app.core.database import get_db
from backend.app.schemas.workspace import (
    WorkspaceResponse,
    WorkspaceCreate,
    WorkspaceUpdate
)
from backend.app.models.workspace import Workspace
from backend.app.services.workspace_service import WorkspaceService

router = APIRouter()


@router.get("/", response_model=List[WorkspaceResponse])
async def list_workspaces(
    db: AsyncSession = Depends(get_db)
):
    """List all available workspaces."""
    return await WorkspaceService.get_all(db)


@router.get("/{slug}", response_model=WorkspaceResponse)
async def get_workspace(
    slug: str,
    db: AsyncSession = Depends(get_db)
):
    """Retrieve workspace details by slug."""
    ws = await WorkspaceService.get_by_slug(db, slug)
    if not ws:
        raise HTTPException(status_code=404, detail="Workspace not found")
    return ws


@router.post("/", response_model=WorkspaceResponse)
async def create_workspace(
    data: WorkspaceCreate,
    db: AsyncSession = Depends(get_db)
):
    """Create a new custom workspace."""
    existing = await WorkspaceService.get_by_slug(db, data.slug)
    if existing:
        raise HTTPException(status_code=400, detail="Workspace slug already exists")
    
    ws = Workspace(**data.model_dump())
    db.add(ws)
    await db.commit()
    await db.refresh(ws)
    return ws
