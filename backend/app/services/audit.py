"""Audit logging service for persisting immutable operations and security events."""

from typing import Any, Dict, Optional
import uuid
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.audit import AuditEvent
from backend.app.services.interfaces import IAuditService


class AuditService(IAuditService):
    """Persists structured audit events to PostgreSQL."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def log_audit_event(
        self,
        action: str,
        resource_type: str,
        resource_id: Optional[str] = None,
        user_id: Optional[uuid.UUID] = None,
        case_id: Optional[uuid.UUID] = None,
        details: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None,
    ) -> None:
        audit_event = AuditEvent(
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            user_id=user_id,
            case_id=case_id,
            details=details or {},
            ip_address=ip_address,
        )
        self.session.add(audit_event)
        await self.session.commit()

    async def get_audit_events(
        self,
        case_id: Optional[uuid.UUID] = None,
        user_id: Optional[uuid.UUID] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[AuditEvent]:
        from sqlalchemy import select
        query = select(AuditEvent).order_by(AuditEvent.timestamp.desc())
        if case_id:
            query = query.where(AuditEvent.case_id == case_id)
        if user_id:
            query = query.where(AuditEvent.user_id == user_id)
        query = query.offset(offset).limit(min(limit, 100))
        result = await self.session.execute(query)
        return list(result.scalars().all())
