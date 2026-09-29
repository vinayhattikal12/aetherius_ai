from typing import List, Dict, Any, Optional
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from backend.app.core.database import get_db
from backend.app.services.audit_service import AuditService

router = APIRouter()


class AuditLogResponse(BaseModel):
    id: str
    event_type: str
    user_id: Optional[str] = None
    actor: str
    details: Dict[str, Any] = Field(default_factory=dict)
    ip_address: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AuditLogCreate(BaseModel):
    event_type: str
    actor: str = "user"
    user_id: Optional[str] = None
    details: Dict[str, Any] = Field(default_factory=dict)


@router.get("/", response_model=List[AuditLogResponse])
async def list_audit_logs(
    event_type: Optional[str] = None,
    limit: int = 50,
    db: AsyncSession = Depends(get_db)
):
    """List security and compliance audit events stored in PostgreSQL."""
    logs = await AuditService.list_logs(db=db, event_type=event_type, limit=limit)
    return [
        AuditLogResponse(
            id=l.id,
            event_type=l.event_type,
            user_id=l.user_id,
            actor=l.actor,
            details=l.details,
            ip_address=l.ip_address,
            created_at=l.created_at,
            updated_at=l.updated_at
        )
        for l in logs
    ]


@router.post("/", response_model=AuditLogResponse)
async def record_audit_log(
    data: AuditLogCreate,
    db: AsyncSession = Depends(get_db)
):
    """Record a new security or user audit event."""
    log = await AuditService.log_event(
        db=db,
        event_type=data.event_type,
        actor=data.actor,
        user_id=data.user_id,
        details=data.details
    )
    return AuditLogResponse(
        id=log.id,
        event_type=log.event_type,
        user_id=log.user_id,
        actor=log.actor,
        details=log.details,
        ip_address=log.ip_address,
        created_at=log.created_at,
        updated_at=log.updated_at
    )
