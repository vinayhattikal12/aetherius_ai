from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from backend.app.core.database import get_db
from backend.app.models.agent import AgentDefinition, AgentTask, AgentTaskStep
from backend.app.schemas.agent import (
    AgentDefinitionResponse,
    AgentTaskCreate,
    AgentTaskResponse,
    AgentTaskStepResponse
)
from backend.app.services.agent_orchestrator import AgentOrchestrator

router = APIRouter()


@router.get("/", response_model=List[AgentDefinitionResponse])
async def list_agents(
    workspace_slug: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    """List available autonomous role agents."""
    await AgentOrchestrator.ensure_default_agents(db)
    stmt = select(AgentDefinition).where(AgentDefinition.is_active == True)
    if workspace_slug:
        stmt = stmt.where(
            (AgentDefinition.workspace_slug == workspace_slug) | (AgentDefinition.workspace_slug == "general")
        )
    result = await db.execute(stmt)
    agents = result.scalars().all()
    return [
        AgentDefinitionResponse(
            id=a.id,
            name=a.name,
            slug=a.slug,
            role_type=a.role_type,
            workspace_slug=a.workspace_slug,
            description=a.description,
            system_instructions=a.system_instructions,
            allowed_tools=a.allowed_tools,
            preferred_model_id=a.preferred_model_id,
            is_system=a.is_system,
            is_active=a.is_active,
            max_steps=a.max_steps,
            created_at=a.created_at,
            updated_at=a.updated_at
        )
        for a in agents
    ]


@router.post("/tasks", response_model=AgentTaskResponse)
async def create_and_run_task(
    data: AgentTaskCreate,
    db: AsyncSession = Depends(get_db)
):
    """Create and immediately execute an autonomous multi-step agent task."""
    task = await AgentOrchestrator.create_task(db=db, data=data)
    
    # Reload steps
    steps_res = await db.execute(select(AgentTaskStep).where(AgentTaskStep.task_id == task.id).order_by(AgentTaskStep.step_index.asc()))
    steps = steps_res.scalars().all()

    agent_res = await db.execute(select(AgentDefinition).where(AgentDefinition.id == task.agent_id))
    agent = agent_res.scalars().first()

    return AgentTaskResponse(
        id=task.id,
        agent_id=task.agent_id,
        agent_slug=agent.slug if agent else None,
        agent_name=agent.name if agent else None,
        workspace_slug=task.workspace_slug,
        title=task.title,
        goal_prompt=task.goal_prompt,
        status=task.status,
        result_output=task.result_output,
        error_message=task.error_message,
        execution_metadata=task.execution_metadata,
        steps=[
            AgentTaskStepResponse(
                id=s.id,
                task_id=s.task_id,
                step_index=s.step_index,
                step_type=s.step_type,
                content=s.content,
                tool_name=s.tool_name,
                tool_arguments=s.tool_arguments or {},
                tool_result=s.tool_result or {},
                duration_ms=s.duration_ms,
                created_at=s.created_at
            )
            for s in steps
        ],
        completed_at=task.completed_at,
        created_at=task.created_at,
        updated_at=task.updated_at
    )


@router.get("/tasks/{task_id}", response_model=AgentTaskResponse)
async def get_agent_task(
    task_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Get full agent task status, thought trace, and final output."""
    task_res = await db.execute(select(AgentTask).where(AgentTask.id == task_id))
    task = task_res.scalars().first()
    if not task:
        raise HTTPException(status_code=404, detail="Agent task not found")

    steps_res = await db.execute(select(AgentTaskStep).where(AgentTaskStep.task_id == task.id).order_by(AgentTaskStep.step_index.asc()))
    steps = steps_res.scalars().all()

    agent_res = await db.execute(select(AgentDefinition).where(AgentDefinition.id == task.agent_id))
    agent = agent_res.scalars().first()

    return AgentTaskResponse(
        id=task.id,
        agent_id=task.agent_id,
        agent_slug=agent.slug if agent else None,
        agent_name=agent.name if agent else None,
        workspace_slug=task.workspace_slug,
        title=task.title,
        goal_prompt=task.goal_prompt,
        status=task.status,
        result_output=task.result_output,
        error_message=task.error_message,
        execution_metadata=task.execution_metadata,
        steps=[
            AgentTaskStepResponse(
                id=s.id,
                task_id=s.task_id,
                step_index=s.step_index,
                step_type=s.step_type,
                content=s.content,
                tool_name=s.tool_name,
                tool_arguments=s.tool_arguments or {},
                tool_result=s.tool_result or {},
                duration_ms=s.duration_ms,
                created_at=s.created_at
            )
            for s in steps
        ],
        completed_at=task.completed_at,
        created_at=task.created_at,
        updated_at=task.updated_at
    )


@router.get("/tasks", response_model=List[AgentTaskResponse])
async def list_agent_tasks(
    workspace_slug: Optional[str] = None,
    limit: int = 20,
    db: AsyncSession = Depends(get_db)
):
    """List historical agent tasks."""
    stmt = select(AgentTask).order_by(AgentTask.created_at.desc()).limit(limit)
    if workspace_slug:
        stmt = stmt.where(AgentTask.workspace_slug == workspace_slug)

    result = await db.execute(stmt)
    tasks = result.scalars().all()

    responses = []
    for t in tasks:
        agent_res = await db.execute(select(AgentDefinition).where(AgentDefinition.id == t.agent_id))
        agent = agent_res.scalars().first()

        responses.append(AgentTaskResponse(
            id=t.id,
            agent_id=t.agent_id,
            agent_slug=agent.slug if agent else None,
            agent_name=agent.name if agent else None,
            workspace_slug=t.workspace_slug,
            title=t.title,
            goal_prompt=t.goal_prompt,
            status=t.status,
            result_output=t.result_output,
            error_message=t.error_message,
            execution_metadata=t.execution_metadata,
            steps=[],
            completed_at=t.completed_at,
            created_at=t.created_at,
            updated_at=t.updated_at
        ))
    return responses
