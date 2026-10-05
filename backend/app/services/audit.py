from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.security import AuditLog


def record_audit(
    database: Session,
    *,
    actor_id: UUID | None,
    entity_type: str,
    entity_id: UUID | str,
    action: str,
    old_value: dict[str, Any] | None = None,
    new_value: dict[str, Any] | None = None,
    reason: str | None = None,
) -> None:
    """Append a change record to the same transaction as the business action."""
    database.add(
        AuditLog(
            actor_id=actor_id,
            entity_type=entity_type,
            entity_id=str(entity_id),
            action=action,
            old_value=old_value,
            new_value=new_value,
            reason=reason,
        )
    )
