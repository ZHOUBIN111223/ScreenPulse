"""Authentication and team-membership helpers shared across backend route modules."""

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.config import get_settings
from app.models import Team, TeamMember, User
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


def require_team_membership(db: Session, user: User, team_id: int) -> TeamMember:
    membership = db.scalar(
        select(TeamMember).where(
            TeamMember.team_id == team_id,
            TeamMember.user_id == user.id,
            TeamMember.status == "active",
        )
    )
    if membership is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Team not found")
    return membership


def require_team_admin_membership(db: Session, user: User, team_id: int) -> TeamMember:
    membership = require_team_membership(db, user, team_id)
    if membership.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return membership


def is_global_admin(user: User) -> bool:
    return user.email.lower() in settings.admin_email_set


def require_global_admin(user: User = Depends(get_current_user)) -> User:
    if not is_global_admin(user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Global admin access required")
    return user


def get_current_team(db: Session, user: User) -> Team:
    if user.current_team_id is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Current team not set")
    team = db.get(Team, user.current_team_id)
    if team is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Current team not found")
    return team


def require_current_team_membership(db: Session, user: User) -> TeamMember:
    team = get_current_team(db, user)
    return require_team_membership(db, user, team.id)
