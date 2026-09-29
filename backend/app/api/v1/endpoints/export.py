from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import PlainTextResponse, JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from backend.app.core.database import get_db
from backend.app.models.conversation import Conversation, Message
from backend.app.models.workspace import Workspace
from backend.app.models.knowledge import KnowledgeBase, Document
from backend.app.models.memory import Memory
from backend.app.models.agent import AgentTask

router = APIRouter()


@router.get("/conversation/{conversation_id}")
async def export_conversation(
    conversation_id: str,
    format: str = Query("markdown", pattern="^(markdown|json|txt)$"),
    db: AsyncSession = Depends(get_db)
):
    """Export a chat conversation transcript as Markdown, JSON, or plain text."""
    conv_res = await db.execute(select(Conversation).where(Conversation.id == conversation_id))
    conv = conv_res.scalars().first()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    msg_res = await db.execute(
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.asc())
    )
    messages = msg_res.scalars().all()

    if format == "json":
        return JSONResponse(content={
            "id": conv.id,
            "title": conv.title,
            "workspace_slug": conv.workspace_slug,
            "model_name": conv.model_name,
            "created_at": conv.created_at.isoformat(),
            "messages": [
                {
                    "role": m.role,
                    "content": m.content,
                    "model_name": m.model_name,
                    "citations": m.citations,
                    "created_at": m.created_at.isoformat()
                }
                for m in messages
            ]
        })

    elif format == "markdown":
        lines = [
            f"# Aetherius AI Transcript: {conv.title}",
            f"**Workspace:** `{conv.workspace_slug}` | **Model:** `{conv.model_name}` | **Created:** {conv.created_at.strftime('%Y-%m-%d %H:%M:%S')}",
            "\n---\n"
        ]
        for m in messages:
            speaker = "User" if m.role == "user" else "Aetherius Intelligence"
            lines.append(f"### {speaker} ({m.created_at.strftime('%H:%M:%S')})")
            lines.append(f"{m.content}\n")
            if m.citations:
                lines.append("**Sources & Citations:**")
                for c in m.citations:
                    title = c.get("title", "Document")
                    lines.append(f"- {title}: {c.get('snippet', '')}")
                lines.append("")
            lines.append("---\n")

        content_str = "\n".join(lines)
        return PlainTextResponse(
            content=content_str,
            media_type="text/markdown",
            headers={"Content-Disposition": f'attachment; filename="aetherius_transcript_{conv.id[:8]}.md"'}
        )

    else:
        # Plain text
        lines = [f"=== AETHERIUS CHAT: {conv.title} ==="]
        for m in messages:
            lines.append(f"[{m.role.upper()}]: {m.content}\n")
        return PlainTextResponse(content="\n".join(lines), media_type="text/plain")


@router.get("/workspace/{workspace_slug}")
async def export_workspace_snapshot(
    workspace_slug: str,
    db: AsyncSession = Depends(get_db)
):
    """Export complete workspace configuration, knowledge collections, memories, and agent tasks."""
    ws_res = await db.execute(select(Workspace).where(Workspace.slug == workspace_slug))
    ws = ws_res.scalars().first()
    if not ws:
        raise HTTPException(status_code=404, detail="Workspace not found")

    # Knowledge bases
    kb_res = await db.execute(select(KnowledgeBase).where(KnowledgeBase.workspace_slug == workspace_slug))
    kbs = kb_res.scalars().all()

    # Memories
    mem_res = await db.execute(select(Memory).where(Memory.workspace_slug == workspace_slug))
    memories = mem_res.scalars().all()

    # Tasks
    task_res = await db.execute(select(AgentTask).where(AgentTask.workspace_slug == workspace_slug))
    tasks = task_res.scalars().all()

    return {
        "workspace": {
            "name": ws.name,
            "slug": ws.slug,
            "description": ws.description,
            "instructions": ws.instructions,
            "enabled_tools": ws.enabled_tools
        },
        "knowledge_collections": [
            {"name": k.name, "slug": k.slug, "collection_type": k.collection_type, "description": k.description}
            for k in kbs
        ],
        "memories": [
            {"memory_type": m.memory_type, "content": m.content, "importance_weight": m.importance_weight}
            for m in memories
        ],
        "agent_tasks_count": len(tasks),
        "exported_at": ws.updated_at.isoformat()
    }
