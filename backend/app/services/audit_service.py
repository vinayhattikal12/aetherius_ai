from typing import List, Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from backend.app.models.audit import AuditLog
from backend.app.core.logging import logger


class AuditService:
    """Records and queries compliance and security audit logs in PostgreSQL."""

    @staticmethod
    async def log_event(
        db: AsyncSession,
        event_type: str,
        actor: str = "system",
        user_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None
    ) -> AuditLog:
        log = AuditLog(
            event_type=event_type,
            user_id=user_id,
            actor=actor,
            details=details or {},
            ip_address=ip_address
        )
        db.add(log)
        await db.commit()
        await db.refresh(log)
        logger.info(f"Audit log recorded: [{event_type}] by {actor}")
        return log

    @staticmethod
    async def list_logs(
        db: AsyncSession,
        event_type: Optional[str] = None,
        limit: int = 50
    ) -> List[AuditLog]:
        stmt = select(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit)
        if event_type:
            stmt = stmt.where(AuditLog.event_type == event_type)
        result = await db.execute(stmt)
        return result.scalars().all()
