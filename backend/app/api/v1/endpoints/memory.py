from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from backend.app.core.database import get_db
from backend.app.models.memory import Memory
from backend.app.schemas.memory import (
    MemoryCreate,
    MemoryResponse,
    MemorySearchRequest,
    MemorySearchResult,
    MemoryUpdate
)
from backend.app.services.memory_service import MemoryService

router = APIRouter()


@router.get("/", response_model=List[MemoryResponse])
async def list_memories(
    workspace_slug: Optional[str] = None,
    memory_type: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = 100,
    db: AsyncSession = Depends(get_db)
):
    """List persistent episodic and semantic memories stored in PostgreSQL."""
    memories = await MemoryService.list_memories(
        db=db,
        workspace_slug=workspace_slug,
        memory_type=memory_type,
        search_query=search,
        limit=limit
    )
    return [
        MemoryResponse(
            id=m.id,
            user_id=m.user_id,
            workspace_slug=m.workspace_slug,
            memory_type=m.memory_type,
            content=m.content,
            source_conversation_id=m.source_conversation_id,
            confidence_score=m.confidence_score,
            importance_weight=m.importance_weight,
            access_count=m.access_count,
            last_accessed_at=m.last_accessed_at,
            memory_metadata=m.memory_metadata,
            created_at=m.created_at,
            updated_at=m.updated_at
        )
        for m in memories
    ]


@router.post("/", response_model=MemoryResponse)
async def create_memory(
    data: MemoryCreate,
    db: AsyncSession = Depends(get_db)
):
    """Add a new memory record with computed vector embedding."""
    mem = await MemoryService.create_memory(db=db, data=data)
    return MemoryResponse(
        id=mem.id,
        user_id=mem.user_id,
        workspace_slug=mem.workspace_slug,
        memory_type=mem.memory_type,
        content=mem.content,
        source_conversation_id=mem.source_conversation_id,
        confidence_score=mem.confidence_score,
        importance_weight=mem.importance_weight,
        access_count=mem.access_count,
        last_accessed_at=mem.last_accessed_at,
        memory_metadata=mem.memory_metadata,
        created_at=mem.created_at,
        updated_at=mem.updated_at
    )


@router.put("/{memory_id}", response_model=MemoryResponse)
async def update_memory(
    memory_id: str,
    data: MemoryUpdate,
    db: AsyncSession = Depends(get_db)
):
    """Update an existing memory item."""
    mem = await MemoryService.update_memory(db=db, memory_id=memory_id, data=data)
    if not mem:
        raise HTTPException(status_code=404, detail="Memory not found")
    return MemoryResponse(
        id=mem.id,
        user_id=mem.user_id,
        workspace_slug=mem.workspace_slug,
        memory_type=mem.memory_type,
        content=mem.content,
        source_conversation_id=mem.source_conversation_id,
        confidence_score=mem.confidence_score,
        importance_weight=mem.importance_weight,
        access_count=mem.access_count,
        last_accessed_at=mem.last_accessed_at,
        memory_metadata=mem.memory_metadata,
        created_at=mem.created_at,
        updated_at=mem.updated_at
    )


@router.post("/search", response_model=MemorySearchResult)
async def search_memories(
    request: MemorySearchRequest,
    db: AsyncSession = Depends(get_db)
):
    """Execute semantic cosine similarity search across PostgreSQL memories."""
    scored_memories = await MemoryService.retrieve_relevant_memories(
        db=db,
        query=request.query,
        workspace_slug=request.workspace_slug,
        top_k=request.top_k,
        min_similarity=request.min_similarity
    )

    responses = [
        MemoryResponse(
            id=m.id,
            user_id=m.user_id,
            workspace_slug=m.workspace_slug,
            memory_type=m.memory_type,
            content=m.content,
            source_conversation_id=m.source_conversation_id,
            confidence_score=m.confidence_score,
            importance_weight=m.importance_weight,
            access_count=m.access_count,
            last_accessed_at=m.last_accessed_at,
            similarity_score=score,
            memory_metadata=m.memory_metadata,
            created_at=m.created_at,
            updated_at=m.updated_at
        )
        for m, score in scored_memories
    ]
    return MemorySearchResult(query=request.query, memories=responses)


@router.delete("/{memory_id}")
async def delete_memory(
    memory_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Delete a memory record from PostgreSQL."""
    deleted = await MemoryService.delete_memory(db=db, memory_id=memory_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Memory not found")
    return {"status": "deleted", "id": memory_id}


@router.delete("/")
async def clear_all_memories(
    workspace_slug: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    """Clear all memories or memories for a specific workspace."""
    count = await MemoryService.clear_memories(db=db, workspace_slug=workspace_slug)
    return {"status": "cleared", "deleted_count": count}
