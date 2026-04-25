"""Team, invite-code, settings, member, and summary endpoints for the team-based MVP."""

from datetime import datetime, timedelta
from secrets import token_urlsafe
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, status
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.dependencies import get_current_user, require_team_admin_membership, require_team_membership
from app.models import FrameCapture, HourlySummary, InviteCode, ScreenSession, Team, TeamMember, TeamSetting, User
from app.schemas import (
    HourlySummaryOut,
    InviteCodeOut,
    SessionOut,
    TeamCreateRequest,
    TeamMemberOut,
    TeamOut,
    TeamSettingOut,
    TeamSettingUpdate,
)
from app.services.analysis import get_team_setting
from app.services.audit import record_audit_log

settings = get_settings()
router = APIRouter(tags=["teams"])

AUTH_RESPONSE = {401: {"description": "Missing, invalid, or expired bearer token."}}
TEAM_MEMBER_RESPONSES = {
    **AUTH_RESPONSE,
    404: {"description": "Team was not found or caller is not an active member."},
}
TEAM_ADMIN_RESPONSES = {
    **TEAM_MEMBER_RESPONSES,
    403: {"description": "Caller is not an active team admin."},
}
TEAM_ID_PATH = Path(..., description="Team ID.")
USER_ID_PATH = Path(..., description="User ID for a team member.")
INVITE_CODE_PATH = Path(..., description="Invite code value.")


def _team_out(team: Team, membership: TeamMember) -> TeamOut:
    return TeamOut(
        id=team.id,
        name=team.name,
        created_by_user_id=team.created_by_user_id,
        created_at=team.created_at,
        updated_at=team.updated_at,
        my_role=membership.role,
    )


def _build_session_out(session: ScreenSession, db: Session) -> SessionOut:
    frame_count = db.query(FrameCapture).filter(FrameCapture.session_id == session.id).count()
    return SessionOut.model_validate(session).model_copy(update={"frame_count": frame_count})


def _load_team_membership_or_404(db: Session, team_id: int, user_id: int) -> TeamMember:
    membership = db.scalar(
        select(TeamMember).where(
            TeamMember.team_id == team_id,
            TeamMember.user_id == user_id,
            TeamMember.status == "active",
        )
    )
    if membership is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Team member not found")
    return membership


def _generate_unique_invite_code(db: Session) -> str:
    for _ in range(10):
        code = token_urlsafe(6).replace("-", "").replace("_", "").upper()[:8]
        existing = db.scalar(select(InviteCode).where(InviteCode.code == code))
        if existing is None:
            return code
    raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to generate invite code")


@router.post(
    "/teams",
    response_model=TeamOut,
    summary="Create team",
    description=(
        "Creates a team for the authenticated user. Authenticated users can call this endpoint. "
        "On success it stores a team, makes the caller an admin, creates default settings, and writes an audit log."
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
    db.add(membership)
    db.add(setting)
    record_audit_log(db, team.id, user.id, "team.created", "team", team.id)
    db.commit()
    db.refresh(team)
    db.refresh(membership)
    return _team_out(team, membership)


def _team_setting_out(setting: TeamSetting) -> TeamSettingOut:
    interval_seconds = setting.frame_interval_seconds
    return TeamSettingOut(
        frame_interval_seconds=interval_seconds,
        frame_interval_minutes=max(1, (interval_seconds + 59) // 60),
    )


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
    "/teams/{team_id}",
    response_model=TeamOut,
    summary="Get team",
    description=(
        "Returns one team visible to the authenticated user. Active team members can call this endpoint. "
        "It does not change stored application state."
    ),
    tags=["teams"],
    responses=TEAM_MEMBER_RESPONSES,
)
def get_team(
    team_id: Annotated[int, TEAM_ID_PATH],
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TeamOut:
    membership = require_team_membership(db, user, team_id)
    team = db.get(Team, team_id)
    if team is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Team not found")
    return _team_out(team, membership)


@router.get(
    "/teams/{team_id}/members",
    response_model=list[TeamMemberOut],
    summary="List team members",
    description=(
        "Lists active members, current sessions, and latest summaries for a team. "
        "Only active team admins can call this endpoint. It does not change stored application state."
    ),
    tags=["teams"],
    responses=TEAM_ADMIN_RESPONSES,
)
def team_members(
    team_id: Annotated[int, TEAM_ID_PATH],
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[TeamMemberOut]:
    require_team_admin_membership(db, user, team_id)
    memberships = db.scalars(
        select(TeamMember).where(TeamMember.team_id == team_id, TeamMember.status == "active").order_by(TeamMember.joined_at.asc())
    ).all()

    result: list[TeamMemberOut] = []
    for membership in memberships:
        member_user = db.get(User, membership.user_id)
        if member_user is None:
            continue

        active_session = db.scalar(
            select(ScreenSession)
            .where(
                ScreenSession.team_id == team_id,
                ScreenSession.user_id == member_user.id,
                ScreenSession.status == "active",
            )
            .order_by(ScreenSession.started_at.desc())
        )
        latest_summary = db.scalar(
            select(HourlySummary.summary_text)
            .where(HourlySummary.team_id == team_id, HourlySummary.user_id == member_user.id)
            .order_by(desc(HourlySummary.hour_start))
        )

        result.append(
            TeamMemberOut(
                user_id=member_user.id,
                email=member_user.email,
                name=member_user.name,
                role=membership.role,
                status=membership.status,
                joined_at=membership.joined_at,
                active_session=_build_session_out(active_session, db) if active_session else None,
                latest_summary=latest_summary,
            )
        )
    return result


@router.post(
    "/teams/{team_id}/invite-codes",
    response_model=InviteCodeOut,
    summary="Create invite code",
    description=(
        "Creates a join code for a team. Only active team admins can call this endpoint. "
        "On success it stores a new invite code and writes an audit log."
    ),
    tags=["invite-codes"],
    responses={
        **TEAM_ADMIN_RESPONSES,
        500: {"description": "Invite code generation failed."},
    },
)
def create_invite_code(
    team_id: Annotated[int, TEAM_ID_PATH],
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> InviteCodeOut:
    require_team_admin_membership(db, user, team_id)
    invite_code = InviteCode(
        team_id=team_id,
        code=_generate_unique_invite_code(db),
        created_by_user_id=user.id,
        expires_at=datetime.utcnow() + timedelta(days=7),
        used_count=0,
        max_uses=settings.invite_code_max_uses,
        status="active",
    )
    db.add(invite_code)
    db.flush()
    record_audit_log(db, team_id, user.id, "invite_code.created", "invite_code", invite_code.id)
    db.commit()
    db.refresh(invite_code)
    return InviteCodeOut.model_validate(invite_code)


@router.post(
    "/invite-codes/{code}/join",
    response_model=TeamOut,
    summary="Join team by invite code",
    description=(
        "Adds or reactivates the authenticated user as a team member using an invite code. "
        "Authenticated users can call this endpoint. On success it may update invite usage, membership status, and audit logs."
    ),
    tags=["invite-codes"],
    responses={
        **AUTH_RESPONSE,
        400: {"description": "Invite code expired or reached its usage limit."},
        404: {"description": "Invite code or target team was not found."},
    },
)
def join_team_by_invite_code(
    code: Annotated[str, INVITE_CODE_PATH],
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TeamOut:
    invite_code = db.scalar(select(InviteCode).where(InviteCode.code == code.upper()))
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
        if existing_membership.status == "active":
            team = db.get(Team, invite_code.team_id)
            if team is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Team not found")
            return _team_out(team, existing_membership)
        if invite_code.max_uses is not None and invite_code.used_count >= invite_code.max_uses:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invite code usage limit reached")
        existing_membership.status = "active"
        invite_code.used_count += 1
        record_audit_log(db, invite_code.team_id, user.id, "team.joined", "team", invite_code.team_id)
    db.commit()

    team = db.get(Team, invite_code.team_id)
    if team is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Team not found")
    db.refresh(existing_membership)
    return _team_out(team, existing_membership)


@router.get(
    "/teams/{team_id}/settings",
    response_model=TeamSettingOut,
    summary="Get team settings",
    description=(
        "Returns screenshot sampling settings for a team. Active team members can call this endpoint. "
        "It does not change stored application state."
    ),
    tags=["team-settings"],
    responses=TEAM_MEMBER_RESPONSES,
)
def get_settings(
    team_id: Annotated[int, TEAM_ID_PATH],
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TeamSettingOut:
    require_team_membership(db, user, team_id)
    setting = get_team_setting(db, team_id)
    return _team_setting_out(setting)


@router.patch(
    "/teams/{team_id}/settings",
    response_model=TeamSettingOut,
    summary="Update team settings",
    description=(
        "Updates screenshot sampling settings for a team. Only active team admins can call this endpoint. "
        "On success it updates team settings and writes an audit log."
    ),
    tags=["team-settings"],
    responses=TEAM_ADMIN_RESPONSES,
)
def update_settings(
    team_id: Annotated[int, TEAM_ID_PATH],
    payload: TeamSettingUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TeamSettingOut:
    require_team_admin_membership(db, user, team_id)
    setting = get_team_setting(db, team_id)
    interval_seconds = payload.frame_interval_seconds or 60
    setting.frame_interval_seconds = interval_seconds
    setting.frame_interval_minutes = max(1, (interval_seconds + 59) // 60)
    record_audit_log(db, team_id, user.id, "team_settings.updated", "team_setting", setting.id)
    db.commit()
    db.refresh(setting)
    return _team_setting_out(setting)


@router.get(
    "/teams/{team_id}/summaries/me",
    response_model=list[HourlySummaryOut],
    summary="List my summaries",
    description=(
        "Lists hourly summaries for the authenticated user in a team. Active team members can call this endpoint. "
        "It does not change stored application state."
    ),
    tags=["summaries"],
    responses=TEAM_MEMBER_RESPONSES,
)
def my_summaries(
    team_id: Annotated[int, TEAM_ID_PATH],
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[HourlySummaryOut]:
    require_team_membership(db, user, team_id)
    summaries = db.scalars(
        select(HourlySummary)
        .where(HourlySummary.team_id == team_id, HourlySummary.user_id == user.id)
        .order_by(HourlySummary.hour_start.desc())
    ).all()
    return [HourlySummaryOut.model_validate(summary) for summary in summaries]


@router.get(
    "/teams/{team_id}/summaries",
    response_model=list[HourlySummaryOut],
    summary="List team summaries",
    description=(
        "Lists hourly summaries for all members in a team. Only active team admins can call this endpoint. "
        "It does not change stored application state."
    ),
    tags=["summaries"],
    responses=TEAM_ADMIN_RESPONSES,
)
def team_summaries(
    team_id: Annotated[int, TEAM_ID_PATH],
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[HourlySummaryOut]:
    require_team_admin_membership(db, user, team_id)
    summaries = db.scalars(
        select(HourlySummary).where(HourlySummary.team_id == team_id).order_by(HourlySummary.hour_start.desc())
    ).all()
    return [HourlySummaryOut.model_validate(summary) for summary in summaries]


@router.get(
    "/teams/{team_id}/members/{user_id}/summaries",
    response_model=list[HourlySummaryOut],
    summary="List member summaries",
    description=(
        "Lists hourly summaries for one team member. The member can read their own summaries; "
        "team admins can read any member summaries. It does not change stored application state."
    ),
    tags=["summaries"],
    responses={
        **TEAM_MEMBER_RESPONSES,
        403: {"description": "Caller is not the requested member and is not a team admin."},
    },
)
def member_summaries(
    team_id: Annotated[int, TEAM_ID_PATH],
    user_id: Annotated[int, USER_ID_PATH],
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[HourlySummaryOut]:
    if user.id == user_id:
        require_team_membership(db, user, team_id)
    else:
        require_team_admin_membership(db, user, team_id)

    _load_team_membership_or_404(db, team_id, user_id)
    summaries = db.scalars(
        select(HourlySummary)
        .where(HourlySummary.team_id == team_id, HourlySummary.user_id == user_id)
        .order_by(HourlySummary.hour_start.desc())
    ).all()
    return [HourlySummaryOut.model_validate(summary) for summary in summaries]
