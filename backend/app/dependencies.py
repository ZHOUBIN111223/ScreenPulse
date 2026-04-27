"""Authentication and research-group membership helpers shared across backend route modules."""

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.config import get_settings
from app.models import ResearchGroup, ResearchGroupMember, User
from app.security import decode_access_token

security_scheme = HTTPBearer(auto_error=False)
settings = get_settings()


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security_scheme),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing credentials")

    try:
        payload = decode_access_token(credentials.credentials)
        user_id = int(payload["sub"])
    except Exception as exc:  # pragma: no cover - token parsing errors collapse here
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid access token") from exc

    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user


def _normalize_role(role: str) -> str:
    return {"admin": "mentor", "member": "student"}.get(role, role)


def require_research_group_membership(db: Session, user: User, research_group_id: int) -> ResearchGroupMember:
    membership = db.scalar(
        select(ResearchGroupMember).where(
            ResearchGroupMember.research_group_id == research_group_id,
            ResearchGroupMember.user_id == user.id,
            ResearchGroupMember.status == "active",
        )
    )
    if membership is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Research group not found")
    membership.role = _normalize_role(membership.role)
    return membership


def require_research_group_mentor_membership(db: Session, user: User, research_group_id: int) -> ResearchGroupMember:
    membership = require_research_group_membership(db, user, research_group_id)
    if membership.role != "mentor":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Mentor access required")
    return membership


def is_global_admin(user: User) -> bool:
    return user.email.lower() in settings.admin_email_set


def require_global_admin(user: User = Depends(get_current_user)) -> User:
    if not is_global_admin(user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Global admin access required")
    return user


def get_current_research_group(db: Session, user: User) -> ResearchGroup:
    if user.current_research_group_id is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Current research group not set")
    research_group = db.get(ResearchGroup, user.current_research_group_id)
    if research_group is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Current research group not found")
    return research_group


def require_current_research_group_membership(db: Session, user: User) -> ResearchGroupMember:
    research_group = get_current_research_group(db, user)
    return require_research_group_membership(db, user, research_group.id)


def require_current_research_group_mentor_membership(db: Session, user: User) -> ResearchGroupMember:
    research_group = get_current_research_group(db, user)
    return require_research_group_mentor_membership(db, user, research_group.id)


get_current_team = get_current_research_group
require_team_membership = require_research_group_membership
require_team_admin_membership = require_research_group_mentor_membership
require_current_team_membership = require_current_research_group_membership
require_current_team_admin_membership = require_current_research_group_mentor_membership
