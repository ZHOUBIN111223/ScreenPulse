"""Audit log persistence helper for research-group-scoped events."""

from sqlalchemy.orm import Session

from app.models import AuditLog


def record_audit_log(
    db: Session,
    research_group_id: int | None,
    actor_user_id: int | None,
    action: str,
    target_type: str,
    target_id: int | None,
) -> None:
    db.add(
        AuditLog(
            research_group_id=research_group_id,
            actor_user_id=actor_user_id,
            action=action,
            target_type=target_type,
            target_id=target_id,
        )
    )
