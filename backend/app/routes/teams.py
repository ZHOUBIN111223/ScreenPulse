"""User-facing team endpoints for creation, joining, listing, and current-team selection."""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.dependencies import get_current_team, get_current_user, is_global_admin, require_team_membership
from app.models import InviteCode, Team, TeamMember, TeamSetting, User
from app.schemas import CurrentTeamUpdate, TeamCreateRequest, TeamJoinRequest, TeamOut
from app.services.audit import record_audit_log

settings = get_settings()
router = APIRouter(tags=["teams"])

AUTH_RESPONSE = {401: {"description": "Missing, invalid, or expired bearer token."}}
TEAM_MEMBER_RESPONSES = {
    **AUTH_RESPONSE,
    404: {"description": "Current team was not found or caller is not an active member."},
}


def _team_out(team: Team, membership: TeamMember) -> TeamOut:
    return TeamOut(
        id=team.id,
        name=team.name,
        created_by_user_id=team.created_by_user_id,
        created_at=team.created_at,
        updated_at=team.updated_at,
        my_role=membership.role,
    )


@router.post(
    "/teams",
    response_model=TeamOut,
    summary="Create team",
    description=(
        "Creates a team for the authenticated user. Authenticated users can call this endpoint. "
        "On success it stores a team, makes the caller a team admin, creates default settings, sets the team current, "
        "and writes an audit log."
    ),
    tags=["teams"],
    responses=AUTH_RESPONSE,
)
def create_team(
    payload: TeamCreateRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TeamOut:
    team = Team(name=payload.name.strip(), created_by_user_id=user.id)
    db.add(team)
    db.flush()

    membership = TeamMember(team_id=team.id, user_id=user.id, role="admin", status="active")
    setting = TeamSetting(
        team_id=team.id,
        frame_interval_seconds=settings.default_sampling_interval_seconds,
        frame_interval_minutes=settings.default_sampling_interval_minutes,
    )
    user.current_team_id = team.id
    db.add(membership)
    db.add(setting)
    record_audit_log(db, team.id, user.id, "team.created", "team", team.id)
    db.commit()
    db.refresh(team)
    db.refresh(membership)
    return _team_out(team, membership)


@router.get(
    "/teams",
    response_model=list[TeamOut],
    summary="List my teams",
    description=(
        "Lists active teams for the authenticated user. Authenticated users can call this endpoint. "
        "It does not change stored application state."
    ),
    tags=["teams"],
    responses=AUTH_RESPONSE,
)
def list_teams(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[TeamOut]:
    rows = db.execute(
        select(Team, TeamMember)
        .join(TeamMember, TeamMember.team_id == Team.id)
        .where(TeamMember.user_id == user.id, TeamMember.status == "active")
        .order_by(TeamMember.joined_at.asc())
    ).all()
    return [_team_out(team, membership) for team, membership in rows]


@router.get(
    "/teams/current",
    response_model=TeamOut,
    summary="Get current team",
    description=(
        "Returns the authenticated user's current team. Active team members can call this endpoint. "
        "It does not change stored application state."
    ),
    tags=["teams"],
    responses=TEAM_MEMBER_RESPONSES,
)
def current_team(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> TeamOut:
    team = get_current_team(db, user)
    membership = require_team_membership(db, user, team.id)
    return _team_out(team, membership)


@router.put(
    "/teams/current",
    response_model=TeamOut,
    summary="Set current team",
    description=(
        "Sets the authenticated user's current team. Active team members can call this endpoint. "
        "On success it updates the user's current team pointer."
    ),
    tags=["teams"],
    responses=TEAM_MEMBER_RESPONSES,
)
def set_current_team(
    payload: CurrentTeamUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TeamOut:
    team = db.get(Team, payload.team_id)
    if team is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Team not found")
    if is_global_admin(user):
        membership = db.scalar(
            select(TeamMember).where(
                TeamMember.team_id == team.id,
                TeamMember.user_id == user.id,
                TeamMember.status == "active",
            )
        ) or TeamMember(team_id=team.id, user_id=user.id, role="admin", status="active")
    else:
        membership = require_team_membership(db, user, payload.team_id)
    user.current_team_id = team.id
    db.commit()
    db.refresh(user)
    return _team_out(team, membership)


@router.post(
    "/teams/join",
    response_model=TeamOut,
    summary="Join team by invite code",
    description=(
        "Adds or reactivates the authenticated user as a team member using an invite code. "
        "Authenticated users can call this endpoint. On success it may update invite usage, membership status, "
        "audit logs, and the user's current team."
    ),
    tags=["teams"],
    responses={
        **AUTH_RESPONSE,
        400: {"description": "Invite code expired or reached its usage limit."},
        404: {"description": "Invite code or target team was not found."},
    },
)
def join_team(
    payload: TeamJoinRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TeamOut:
    invite_code = db.scalar(select(InviteCode).where(InviteCode.code == payload.code.strip().upper()))
    if invite_code is None or invite_code.status != "active":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invite code not found")
    if invite_code.expires_at is not None and invite_code.expires_at < datetime.utcnow():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invite code has expired")

    existing_membership = db.scalar(
        select(TeamMember).where(TeamMember.team_id == invite_code.team_id, TeamMember.user_id == user.id)
    )
    if existing_membership is None:
        if invite_code.max_uses is not None and invite_code.used_count >= invite_code.max_uses:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invite code usage limit reached")
        existing_membership = TeamMember(team_id=invite_code.team_id, user_id=user.id, role="member", status="active")
        db.add(existing_membership)
        invite_code.used_count += 1
        record_audit_log(db, invite_code.team_id, user.id, "team.joined", "team", invite_code.team_id)
    else:
        if existing_membership.status != "active":
            if invite_code.max_uses is not None and invite_code.used_count >= invite_code.max_uses:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invite code usage limit reached")
            existing_membership.status = "active"
            invite_code.used_count += 1
            record_audit_log(db, invite_code.team_id, user.id, "team.joined", "team", invite_code.team_id)

    team = db.get(Team, invite_code.team_id)
    if team is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Team not found")
    user.current_team_id = team.id
    db.commit()
    db.refresh(existing_membership)
    return _team_out(team, existing_membership)
