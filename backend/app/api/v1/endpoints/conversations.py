from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from backend.app.core.database import get_db
from backend.app.schemas.chat import (
    ConversationResponse,
    ConversationCreate,
    ConversationUpdate,
    MessageResponse,
    SourceCitation,
    ChatAttachment
)
from backend.app.models.conversation import Conversation, Message

router = APIRouter()


@router.get("/", response_model=List[ConversationResponse])
async def list_conversations(
    workspace_slug: str = "general",
    db: AsyncSession = Depends(get_db)
):
    """List conversations for a specific workspace ordered by recency."""
    result = await db.execute(
        select(Conversation)
        .where(Conversation.workspace_slug == workspace_slug)
        .order_by(Conversation.is_pinned.desc(), Conversation.updated_at.desc())
    )
    conversations = result.scalars().all()
    
    responses = []
    for conv in conversations:
        resp = ConversationResponse(
            id=conv.id,
            user_id=conv.user_id,
            workspace_slug=conv.workspace_slug,
            title=conv.title,
            model_name=conv.model_name,
            is_pinned=conv.is_pinned,
            messages=[],
            created_at=conv.created_at,
            updated_at=conv.updated_at
        )
        responses.append(resp)
    return responses


@router.post("/", response_model=ConversationResponse)
async def create_conversation(
    data: ConversationCreate,
    db: AsyncSession = Depends(get_db)
):
    """Create a new chat conversation session."""
    conv = Conversation(**data.model_dump())
    db.add(conv)
    await db.commit()
    await db.refresh(conv)
    return ConversationResponse(
        id=conv.id,
        user_id=conv.user_id,
        workspace_slug=conv.workspace_slug,
        title=conv.title,
        model_name=conv.model_name,
        is_pinned=conv.is_pinned,
        messages=[],
        created_at=conv.created_at,
        updated_at=conv.updated_at
    )


@router.get("/{conversation_id}", response_model=ConversationResponse)
async def get_conversation(
    conversation_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Retrieve complete conversation with all messages and citations."""
    result = await db.execute(
        select(Conversation).where(Conversation.id == conversation_id)
    )
    conv = result.scalars().first()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    msg_res = await db.execute(
        select(Message).where(Message.conversation_id == conversation_id).order_by(Message.created_at.asc())
    )
    messages = msg_res.scalars().all()

    msg_responses = []
    for m in messages:
        citations = [SourceCitation(**c) if isinstance(c, dict) else c for c in m.citations]
        raw_att = m.extra_metadata.get("attachments", []) if m.extra_metadata else []
        attachments = [ChatAttachment(**a) if isinstance(a, dict) else a for a in raw_att]
        msg_responses.append(MessageResponse(
            id=m.id,
            conversation_id=m.conversation_id,
            role=m.role,
            content=m.content,
            model_name=m.model_name,
            citations=citations,
            attachments=attachments,
            token_count=m.token_count,
            extra_metadata=m.extra_metadata,
            created_at=m.created_at
        ))

    return ConversationResponse(
        id=conv.id,
        user_id=conv.user_id,
        workspace_slug=conv.workspace_slug,
        title=conv.title,
        model_name=conv.model_name,
        is_pinned=conv.is_pinned,
        messages=msg_responses,
        created_at=conv.created_at,
        updated_at=conv.updated_at
    )


@router.delete("/{conversation_id}")
async def delete_conversation(
    conversation_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Delete a conversation and its messages."""
    result = await db.execute(select(Conversation).where(Conversation.id == conversation_id))
    conv = result.scalars().first()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    await db.delete(conv)
    await db.commit()
    return {"status": "deleted", "id": conversation_id}
