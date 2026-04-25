"""Audit log persistence helper for team-scoped events."""

from sqlalchemy.orm import Session

from app.models import AuditLog


def record_audit_log(
    db: Session,
    team_id: int | None,
    actor_user_id: int | None,
    action: str,
    target_type: str,
    target_id: int | None,
) -> None:
    db.add(
        AuditLog(
            team_id=team_id,
            actor_user_id=actor_user_id,
            action=action,
            target_type=target_type,
            target_id=target_id,
        )
    )
