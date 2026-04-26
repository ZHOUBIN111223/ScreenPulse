"""Global-admin endpoints for users, teams, sessions, summaries, settings, and team operations."""

from datetime import datetime, timedelta
from secrets import token_urlsafe
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.dependencies import get_current_team, is_global_admin, require_global_admin
from app.models import AuditLog, FrameCapture, HourlySummary, InviteCode, ScreenSession, Team, TeamMember, TeamSetting, User, VisionResult
from app.schemas import (
    AdminFrameOut,
    AdminUserOut,
    AuditLogOut,
    CaptureIntervalUpdate,
    HourlySummaryOut,
    InviteCodeCreateRequest,
    InviteCodeOut,
    InviteCodeStatusUpdate,
    SessionOut,
    TeamMemberAddRequest,
    TeamMemberOut,
    TeamMemberUpdate,
    TeamOut,
    TeamSettingOut,
    TeamSettingUpdate,
)
from app.services.analysis import delete_frame_file, get_team_setting, refresh_hourly_summary
from app.services.audit import record_audit_log

settings = get_settings()
router = APIRouter(prefix="/admin", tags=["admin"])

ADMIN_RESPONSES = {
    401: {"description": "Missing, invalid, or expired bearer token."},
    403: {"description": "Caller is not a global administrator."},
}
USER_ID_PATH = Path(..., description="User ID for a team member.")
FRAME_ID_PATH = Path(..., description="Stored screenshot frame ID.")
SUMMARY_ID_PATH = Path(..., description="Hourly summary ID.")
INVITE_ID_PATH = Path(..., description="Invite code record ID.")


def _admin_user_out(user: User) -> AdminUserOut:
    return AdminUserOut(
        id=user.id,
        email=user.email,
        name=user.name,
        current_team_id=user.current_team_id,
        is_admin=is_global_admin(user),
    )


def _team_out(team: Team) -> TeamOut:
    return TeamOut(
        id=team.id,
        name=team.name,
        created_by_user_id=team.created_by_user_id,
        created_at=team.created_at,
        updated_at=team.updated_at,
        my_role="admin",
    )


def _team_setting_out(setting: TeamSetting) -> TeamSettingOut:
    interval_seconds = setting.frame_interval_seconds
    return TeamSettingOut(
        frame_interval_seconds=interval_seconds,
        frame_interval_minutes=max(1, (interval_seconds + 59) // 60),
        force_screen_share=setting.force_screen_share,
    )


def _build_session_out(session: ScreenSession, db: Session) -> SessionOut:
    frame_count = db.query(FrameCapture).filter(FrameCapture.session_id == session.id).count()
    return SessionOut.model_validate(session).model_copy(update={"frame_count": frame_count})


def _current_admin_team(user: User, db: Session) -> Team:
    return get_current_team(db, user)


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


def _active_admin_count(db: Session, team_id: int) -> int:
    return db.scalar(
        select(func.count())
        .select_from(TeamMember)
        .where(TeamMember.team_id == team_id, TeamMember.role == "admin", TeamMember.status == "active")
    ) or 0


def _load_invite_code_or_404(db: Session, team_id: int, invite_code_id: int) -> InviteCode:
    invite_code = db.get(InviteCode, invite_code_id)
    if invite_code is None or invite_code.team_id != team_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invite code not found")
    return invite_code


def _generate_unique_invite_code(db: Session) -> str:
    for _ in range(10):
        code = token_urlsafe(6).replace("-", "").replace("_", "").upper()[:8]
        existing = db.scalar(select(InviteCode).where(InviteCode.code == code))
        if existing is None:
            return code
    raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to generate invite code")


@router.get("/users", response_model=list[AdminUserOut], responses=ADMIN_RESPONSES)
def list_users(_: User = Depends(require_global_admin), db: Session = Depends(get_db)) -> list[AdminUserOut]:
    users = db.scalars(select(User).order_by(User.created_at.asc())).all()
    return [_admin_user_out(user) for user in users]


@router.get("/teams", response_model=list[TeamOut], responses=ADMIN_RESPONSES)
def list_admin_teams(_: User = Depends(require_global_admin), db: Session = Depends(get_db)) -> list[TeamOut]:
    teams = db.scalars(select(Team).order_by(Team.created_at.asc())).all()
    return [_team_out(team) for team in teams]


@router.get("/sessions", response_model=list[SessionOut], responses=ADMIN_RESPONSES)
def list_sessions(
    team_id: int | None = Query(default=None, description="Optional team filter."),
    user_id: int | None = Query(default=None, description="Optional user filter."),
    session_status: str | None = Query(default=None, alias="status", description="Optional session status filter."),
    _: User = Depends(require_global_admin),
    db: Session = Depends(get_db),
) -> list[SessionOut]:
    query = select(ScreenSession)
    if team_id is not None:
        query = query.where(ScreenSession.team_id == team_id)
    if user_id is not None:
        query = query.where(ScreenSession.user_id == user_id)
    if session_status:
        query = query.where(ScreenSession.status == session_status)
    sessions = db.scalars(query.order_by(ScreenSession.started_at.desc())).all()
    return [_build_session_out(session, db) for session in sessions]


@router.get("/summaries", response_model=list[HourlySummaryOut], responses=ADMIN_RESPONSES)
def list_summaries(
    team_id: int | None = Query(default=None, description="Optional team filter."),
    user_id: int | None = Query(default=None, description="Optional user filter."),
    _: User = Depends(require_global_admin),
    db: Session = Depends(get_db),
) -> list[HourlySummaryOut]:
    query = select(HourlySummary)
    if team_id is not None:
        query = query.where(HourlySummary.team_id == team_id)
    if user_id is not None:
        query = query.where(HourlySummary.user_id == user_id)
    summaries = db.scalars(query.order_by(HourlySummary.hour_start.desc())).all()
    return [HourlySummaryOut.model_validate(summary) for summary in summaries]


@router.get("/settings", response_model=TeamSettingOut, responses=ADMIN_RESPONSES)
def get_settings_endpoint(user: User = Depends(require_global_admin), db: Session = Depends(get_db)) -> TeamSettingOut:
    team = _current_admin_team(user, db)
    return _team_setting_out(get_team_setting(db, team.id))


@router.put("/settings/capture-interval", response_model=TeamSettingOut, responses=ADMIN_RESPONSES)
def update_capture_interval(
    payload: CaptureIntervalUpdate,
    user: User = Depends(require_global_admin),
    db: Session = Depends(get_db),
) -> TeamSettingOut:
    team = _current_admin_team(user, db)
    setting = get_team_setting(db, team.id)
    setting.frame_interval_seconds = payload.frame_interval_seconds
    setting.frame_interval_minutes = max(1, (payload.frame_interval_seconds + 59) // 60)
    record_audit_log(db, team.id, user.id, "team_settings.updated", "team_setting", setting.id)
    db.commit()
    db.refresh(setting)
    return _team_setting_out(setting)


@router.put("/settings", response_model=TeamSettingOut, responses=ADMIN_RESPONSES)
def update_admin_settings(
    payload: TeamSettingUpdate,
    user: User = Depends(require_global_admin),
    db: Session = Depends(get_db),
) -> TeamSettingOut:
    team = _current_admin_team(user, db)
    setting = get_team_setting(db, team.id)
    if payload.frame_interval_seconds is not None:
        setting.frame_interval_seconds = payload.frame_interval_seconds
        setting.frame_interval_minutes = max(1, (payload.frame_interval_seconds + 59) // 60)
    if payload.force_screen_share is not None:
        setting.force_screen_share = payload.force_screen_share
    record_audit_log(db, team.id, user.id, "team_settings.updated", "team_setting", setting.id)
    db.commit()
    db.refresh(setting)
    return _team_setting_out(setting)


@router.get("/members", response_model=list[TeamMemberOut], responses=ADMIN_RESPONSES)
def team_members(user: User = Depends(require_global_admin), db: Session = Depends(get_db)) -> list[TeamMemberOut]:
    team = _current_admin_team(user, db)
    memberships = db.scalars(
        select(TeamMember).where(TeamMember.team_id == team.id, TeamMember.status == "active").order_by(TeamMember.joined_at.asc())
    ).all()
    result: list[TeamMemberOut] = []
    for membership in memberships:
        member_user = db.get(User, membership.user_id)
        if member_user is None:
            continue
        active_session = db.scalar(
            select(ScreenSession)
            .where(
                ScreenSession.team_id == team.id,
                ScreenSession.user_id == member_user.id,
                ScreenSession.status == "active",
            )
            .order_by(ScreenSession.started_at.desc())
        )
        latest_summary = db.scalar(
            select(HourlySummary.summary_text)
            .where(HourlySummary.team_id == team.id, HourlySummary.user_id == member_user.id)
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


@router.post("/members", response_model=TeamMemberOut, responses=ADMIN_RESPONSES)
def add_team_member(
    payload: TeamMemberAddRequest,
    user: User = Depends(require_global_admin),
    db: Session = Depends(get_db),
) -> TeamMemberOut:
    team = _current_admin_team(user, db)
    target_user = db.scalar(select(User).where(User.email == payload.email.strip().lower()))
    if target_user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    membership = db.scalar(select(TeamMember).where(TeamMember.team_id == team.id, TeamMember.user_id == target_user.id))
    if membership is None:
        membership = TeamMember(team_id=team.id, user_id=target_user.id, role=payload.role, status="active")
        db.add(membership)
    else:
        membership.role = payload.role
        membership.status = "active"
    if target_user.current_team_id is None:
        target_user.current_team_id = team.id
    record_audit_log(db, team.id, user.id, "team_member.added", "user", target_user.id)
    db.commit()
    db.refresh(membership)
    return TeamMemberOut(
        user_id=target_user.id,
        email=target_user.email,
        name=target_user.name,
        role=membership.role,
        status=membership.status,
        joined_at=membership.joined_at,
        active_session=None,
        latest_summary=None,
    )


@router.patch("/members/{user_id}", response_model=TeamMemberOut, responses=ADMIN_RESPONSES)
def update_team_member(
    user_id: Annotated[int, USER_ID_PATH],
    payload: TeamMemberUpdate,
    user: User = Depends(require_global_admin),
    db: Session = Depends(get_db),
) -> TeamMemberOut:
    team = _current_admin_team(user, db)
    membership = _load_team_membership_or_404(db, team.id, user_id)
    if membership.role == "admin" and payload.role != "admin" and _active_admin_count(db, team.id) <= 1:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Team must keep at least one admin")
    membership.role = payload.role
    target_user = db.get(User, user_id)
    if target_user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Team member not found")
    record_audit_log(db, team.id, user.id, "team_member.role_updated", "user", user_id)
    db.commit()
    db.refresh(membership)
    return TeamMemberOut(
        user_id=target_user.id,
        email=target_user.email,
        name=target_user.name,
        role=membership.role,
        status=membership.status,
        joined_at=membership.joined_at,
        active_session=None,
        latest_summary=None,
    )


@router.delete("/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT, responses=ADMIN_RESPONSES)
def remove_team_member(
    user_id: Annotated[int, USER_ID_PATH],
    user: User = Depends(require_global_admin),
    db: Session = Depends(get_db),
) -> None:
    team = _current_admin_team(user, db)
    membership = _load_team_membership_or_404(db, team.id, user_id)
    if membership.role == "admin" and _active_admin_count(db, team.id) <= 1:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Team must keep at least one admin")
    membership.status = "removed"
    active_sessions = db.scalars(
        select(ScreenSession).where(
            ScreenSession.team_id == team.id,
            ScreenSession.user_id == user_id,
            ScreenSession.status == "active",
        )
    ).all()
    for session in active_sessions:
        session.status = "stopped"
        session.ended_at = datetime.utcnow()
    record_audit_log(db, team.id, user.id, "team_member.removed", "user", user_id)
    db.commit()


@router.post("/invite-codes", response_model=InviteCodeOut, responses=ADMIN_RESPONSES)
def create_invite_code(
    payload: InviteCodeCreateRequest | None = None,
    user: User = Depends(require_global_admin),
    db: Session = Depends(get_db),
) -> InviteCodeOut:
    team = _current_admin_team(user, db)
    invite_settings = payload or InviteCodeCreateRequest()
    invite_code = InviteCode(
        team_id=team.id,
        code=_generate_unique_invite_code(db),
        created_by_user_id=user.id,
        expires_at=datetime.utcnow() + timedelta(hours=invite_settings.expires_in_hours)
        if invite_settings.expires_in_hours is not None
        else None,
        used_count=0,
        max_uses=invite_settings.max_uses if invite_settings.max_uses is not None else settings.invite_code_max_uses,
        status="active",
    )
    db.add(invite_code)
    db.flush()
    record_audit_log(db, team.id, user.id, "invite_code.created", "invite_code", invite_code.id)
    db.commit()
    db.refresh(invite_code)
    return InviteCodeOut.model_validate(invite_code)


@router.get("/invite-codes", response_model=list[InviteCodeOut], responses=ADMIN_RESPONSES)
def list_invite_codes(user: User = Depends(require_global_admin), db: Session = Depends(get_db)) -> list[InviteCodeOut]:
    team = _current_admin_team(user, db)
    invite_codes = db.scalars(
        select(InviteCode).where(InviteCode.team_id == team.id).order_by(InviteCode.created_at.desc())
    ).all()
    return [InviteCodeOut.model_validate(invite_code) for invite_code in invite_codes]


@router.patch("/invite-codes/{invite_code_id}", response_model=InviteCodeOut, responses=ADMIN_RESPONSES)
def update_invite_code_status(
    invite_code_id: Annotated[int, INVITE_ID_PATH],
    payload: InviteCodeStatusUpdate,
    user: User = Depends(require_global_admin),
    db: Session = Depends(get_db),
) -> InviteCodeOut:
    team = _current_admin_team(user, db)
    invite_code = _load_invite_code_or_404(db, team.id, invite_code_id)
    invite_code.status = payload.status
    record_audit_log(db, team.id, user.id, "invite_code.status_updated", "invite_code", invite_code.id)
    db.commit()
    db.refresh(invite_code)
    return InviteCodeOut.model_validate(invite_code)


@router.get("/audit-logs", response_model=list[AuditLogOut], responses=ADMIN_RESPONSES)
def list_audit_logs(
    action: str | None = Query(default=None, description="Optional exact audit action filter."),
    start_date: datetime | None = Query(default=None, description="Optional inclusive start timestamp."),
    end_date: datetime | None = Query(default=None, description="Optional inclusive end timestamp."),
    user: User = Depends(require_global_admin),
    db: Session = Depends(get_db),
) -> list[AuditLogOut]:
    team = _current_admin_team(user, db)
    query = select(AuditLog, User).outerjoin(User, User.id == AuditLog.actor_user_id).where(AuditLog.team_id == team.id)
    if action:
        query = query.where(AuditLog.action == action)
    if start_date:
        query = query.where(AuditLog.created_at >= start_date)
    if end_date:
        query = query.where(AuditLog.created_at <= end_date)
    rows = db.execute(query.order_by(AuditLog.created_at.desc()).limit(200)).all()
    return [
        AuditLogOut(
            id=audit_log.id,
            team_id=audit_log.team_id,
            actor_user_id=audit_log.actor_user_id,
            actor_name=actor.name if actor else None,
            actor_email=actor.email if actor else None,
            action=audit_log.action,
            target_type=audit_log.target_type,
            target_id=audit_log.target_id,
            created_at=audit_log.created_at,
        )
        for audit_log, actor in rows
    ]


@router.get("/frames", response_model=list[AdminFrameOut], responses=ADMIN_RESPONSES)
def list_frame_history(user: User = Depends(require_global_admin), db: Session = Depends(get_db)) -> list[AdminFrameOut]:
    team = _current_admin_team(user, db)
    rows = db.execute(
        select(FrameCapture, User, VisionResult)
        .join(User, User.id == FrameCapture.user_id)
        .outerjoin(VisionResult, VisionResult.frame_id == FrameCapture.id)
        .where(FrameCapture.team_id == team.id)
        .order_by(FrameCapture.captured_at.desc())
    ).all()
    return [
        AdminFrameOut(
            frame_id=frame.id,
            team_id=frame.team_id,
            session_id=frame.session_id,
            user_id=frame.user_id,
            user_name=member_user.name,
            user_email=member_user.email,
            captured_at=frame.captured_at,
            width=frame.width,
            height=frame.height,
            created_at=frame.created_at,
            recognized_content=vision.recognized_content if vision else None,
            activity_description=vision.activity_description if vision else None,
            model_name=vision.model_name if vision else None,
        )
        for frame, member_user, vision in rows
    ]


@router.delete("/frames/{frame_id}", status_code=status.HTTP_204_NO_CONTENT, responses=ADMIN_RESPONSES)
def delete_frame_history_item(
    frame_id: Annotated[int, FRAME_ID_PATH],
    user: User = Depends(require_global_admin),
    db: Session = Depends(get_db),
) -> None:
    team = _current_admin_team(user, db)
    frame = db.get(FrameCapture, frame_id)
    if frame is None or frame.team_id != team.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Frame not found")
    frame_user_id = frame.user_id
    hour_start = frame.captured_at.replace(minute=0, second=0, microsecond=0)
    delete_frame_file(frame)
    db.delete(frame)
    record_audit_log(db, team.id, user.id, "frame_capture.deleted", "frame_capture", frame_id)
    db.commit()
    refresh_hourly_summary(db, team.id, frame_user_id, hour_start)


@router.get("/members/{user_id}/summaries", response_model=list[HourlySummaryOut], responses=ADMIN_RESPONSES)
def member_summaries(
    user_id: Annotated[int, USER_ID_PATH],
    user: User = Depends(require_global_admin),
    db: Session = Depends(get_db),
) -> list[HourlySummaryOut]:
    team = _current_admin_team(user, db)
    _load_team_membership_or_404(db, team.id, user_id)
    summaries = db.scalars(
        select(HourlySummary)
        .where(HourlySummary.team_id == team.id, HourlySummary.user_id == user_id)
        .order_by(HourlySummary.hour_start.desc())
    ).all()
    return [HourlySummaryOut.model_validate(summary) for summary in summaries]


@router.delete("/summaries/{summary_id}", status_code=status.HTTP_204_NO_CONTENT, responses=ADMIN_RESPONSES)
def delete_hourly_summary(
    summary_id: Annotated[int, SUMMARY_ID_PATH],
    user: User = Depends(require_global_admin),
    db: Session = Depends(get_db),
) -> None:
    team = _current_admin_team(user, db)
    summary = db.get(HourlySummary, summary_id)
    if summary is None or summary.team_id != team.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Summary not found")
    db.delete(summary)
    record_audit_log(db, team.id, user.id, "hourly_summary.deleted", "hourly_summary", summary_id)
    db.commit()
