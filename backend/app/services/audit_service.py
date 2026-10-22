"""Audit trail service.

Records security relevant actions (sign-ins, profile changes, deletions,
administrative actions) so an administrator can review who did what.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from bson import ObjectId

from app.core.logging_config import get_logger

logger = get_logger(__name__)


class AuditService:
    """Writes and reads audit events."""

    def __init__(self, audit_events) -> None:
        self._events = audit_events

    async def record(
        self,
        *,
        action: str,
        actor_id: ObjectId | None = None,
        actor_email: str | None = None,
        target_type: str | None = None,
        target_id: str | None = None,
        metadata: dict[str, Any] | None = None,
        ip_address: str | None = None,
    ) -> None:
        """Persist an audit event.

        Failures are logged but never raised - an audit problem must not
        break the user-facing operation that triggered it.
        """
        document = {
            "actor_id": actor_id,
            "actor_email": actor_email,
            "action": action,
            "target_type": target_type,
            "target_id": target_id,
            "metadata": metadata or {},
            "ip_address": ip_address,
            "created_at": datetime.now(timezone.utc),
        }
        try:
            await self._events.record(document)
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("Could not write the audit event: %s", type(exc).__name__)

    async def recent(
        self, *, skip: int = 0, limit: int = 50, action: str | None = None
    ) -> tuple[list[dict[str, Any]], int]:
        """Return recent audit events (administrators only)."""
        return await self._events.list_recent(skip=skip, limit=limit, action=action)


__all__ = ["AuditService"]
