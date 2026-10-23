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
