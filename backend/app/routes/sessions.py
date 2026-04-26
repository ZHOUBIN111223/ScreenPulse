"""Current-team screen-session lifecycle and screenshot upload endpoints."""

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user, require_current_team_membership
from app.models import FrameCapture, HourlySummary, ScreenSession, User, VisionResult
from app.schemas import FrameUploadResult, HourlySummaryOut, LivekitTokenResponse, SessionOut, SessionStartRequest, TeamSettingOut
from app.services.analysis import analyze_screenshot, get_team_setting, refresh_hourly_summary, save_frame_file
from app.services.audit import record_audit_log
from app.services.livekit import create_livekit_token

router = APIRouter(tags=["screen-sessions"])

AUTH_RESPONSE = {401: {"description": "Missing, invalid, or expired bearer token."}}
CURRENT_TEAM_RESPONSES = {
    **AUTH_RESPONSE,
    404: {"description": "Current team was not found or caller is not an active member."},
}


def _serialize_session(session: ScreenSession, db: Session) -> SessionOut:
    frame_count = db.scalar(select(func.count()).select_from(FrameCapture).where(FrameCapture.session_id == session.id)) or 0
    return SessionOut.model_validate(session).model_copy(update={"frame_count": frame_count})


def _current_active_session(db: Session, team_id: int, user_id: int) -> ScreenSession | None:
    return db.scalar(
        select(ScreenSession)
        .where(
            ScreenSession.team_id == team_id,
            ScreenSession.user_id == user_id,
            ScreenSession.status == "active",
        )
        .order_by(ScreenSession.started_at.desc())
    )


def _team_setting_out(setting) -> TeamSettingOut:
    interval_seconds = setting.frame_interval_seconds
    return TeamSettingOut(
        frame_interval_seconds=interval_seconds,
        frame_interval_minutes=max(1, (interval_seconds + 59) // 60),
        force_screen_share=setting.force_screen_share,
    )


@router.get(
    "/settings/current",
    response_model=TeamSettingOut,
    summary="Get current-team settings",
    description=(
        "Returns screenshot sampling settings for the authenticated user's current team. "
        "Active current-team members can call this endpoint. It does not change stored application state."
    ),
    tags=["team-settings"],
    responses=CURRENT_TEAM_RESPONSES,
)
def current_team_settings(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> TeamSettingOut:
    membership = require_current_team_membership(db, user)
    return _team_setting_out(get_team_setting(db, membership.team_id))


@router.get(
    "/sessions/current",
    response_model=SessionOut | None,
    summary="Get current screen session",
    description=(
        "Returns the authenticated user's active screen session in their current team, or null. "
        "Active current-team members can call this endpoint. It does not change stored application state."
    ),
    tags=["screen-sessions"],
    responses=CURRENT_TEAM_RESPONSES,
)
def current_session(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> SessionOut | None:
    membership = require_current_team_membership(db, user)
    session = _current_active_session(db, membership.team_id, user.id)
    if session is None:
        return None
    return _serialize_session(session, db)


@router.post(
    "/sessions/start",
    response_model=SessionOut,
    summary="Start screen session",
    description=(
        "Starts or returns the authenticated user's active screen session in their current team. "
        "Active current-team members can call this endpoint. On success it may store a new session and write an audit log."
    ),
    tags=["screen-sessions"],
    responses={
        **CURRENT_TEAM_RESPONSES,
        400: {"description": "Caller already has an active sharing session in another team."},
    },
)
def start(
    payload: SessionStartRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SessionOut:
    membership = require_current_team_membership(db, user)
    team_id = membership.team_id

    existing_same_team = _current_active_session(db, team_id, user.id)
    if existing_same_team is not None:
        return _serialize_session(existing_same_team, db)

    active_other_team = db.scalar(
        select(ScreenSession).where(
            ScreenSession.team_id != team_id,
            ScreenSession.user_id == user.id,
            ScreenSession.status == "active",
        )
    )
    if active_other_team is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="An active sharing session already exists in another team",
        )

    session = ScreenSession(
        team_id=team_id,
        user_id=user.id,
        status="active",
        source_label=payload.source_label,
        source_type=payload.source_type,
    )
    db.add(session)
    db.flush()
    record_audit_log(db, team_id, user.id, "screen_session.started", "screen_session", session.id)
    db.commit()
    db.refresh(session)
    return _serialize_session(session, db)


@router.post(
    "/screenshots/upload",
    response_model=FrameUploadResult,
    summary="Upload screenshot",
    description=(
        "Uploads one screenshot for the authenticated user's active session in their current team. "
        "The session owner can call this endpoint. On success it stores the image, analysis result, and refreshed summary."
    ),
    tags=["screenshots"],
    responses={
        **CURRENT_TEAM_RESPONSES,
        400: {"description": "No active session exists, session is stopped, or captured_at is invalid."},
    },
)
def upload_screenshot(
    captured_at: Annotated[str, Form(description="ISO timestamp when the frame was captured by the browser.")],
    file: Annotated[UploadFile, File(description="PNG screenshot frame uploaded from the browser.")],
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> FrameUploadResult:
    membership = require_current_team_membership(db, user)
    team_id = membership.team_id
    session = _current_active_session(db, team_id, user.id)
    if session is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No active session")

    timestamp = datetime.fromisoformat(captured_at.replace("Z", "+00:00")).replace(tzinfo=None)
    path, width, height = save_frame_file(file, team_id, session.id)
    analysis = analyze_screenshot(path, width, height)

    frame = FrameCapture(
        team_id=team_id,
        session_id=session.id,
        user_id=user.id,
        captured_at=timestamp,
        image_path=str(path),
        width=width,
        height=height,
    )
    db.add(frame)
    db.flush()

    vision_result = VisionResult(
        team_id=team_id,
        frame_id=frame.id,
        user_id=user.id,
        recognized_content=analysis.recognized_content,
        activity_description=analysis.activity_description,
        model_name=analysis.model_name,
    )
    db.add(vision_result)
    db.commit()
    db.refresh(frame)

    hour_start = timestamp.replace(minute=0, second=0, microsecond=0)
    summary = refresh_hourly_summary(db, team_id, user.id, hour_start)
    setting = get_team_setting(db, team_id)

    return FrameUploadResult(
        frame_id=frame.id,
        recognized_content=analysis.recognized_content,
        activity_description=analysis.activity_description,
        summary_text=summary.summary_text,
        frame_interval_seconds=setting.frame_interval_seconds,
        frame_interval_minutes=max(1, (setting.frame_interval_seconds + 59) // 60),
    )


@router.post(
    "/sessions/stop",
    response_model=SessionOut,
    summary="Stop screen session",
    description=(
        "Stops the authenticated user's active screen session in their current team. "
        "The session owner can call this endpoint. On success it marks the session stopped, stores the end time, "
        "and writes an audit log."
    ),
    tags=["screen-sessions"],
    responses=CURRENT_TEAM_RESPONSES,
)
def stop(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> SessionOut:
    membership = require_current_team_membership(db, user)
    session = _current_active_session(db, membership.team_id, user.id)
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    session.status = "stopped"
    session.ended_at = datetime.utcnow()
    record_audit_log(db, membership.team_id, user.id, "screen_session.stopped", "screen_session", session.id)
    db.commit()
    db.refresh(session)
    return _serialize_session(session, db)


@router.get(
    "/summaries/my-team",
    response_model=list[HourlySummaryOut],
    summary="List my current-team summaries",
    description=(
        "Lists hourly summaries for the authenticated user in their current team. "
        "Active current-team members can call this endpoint. It does not change stored application state."
    ),
    tags=["summaries"],
    responses=CURRENT_TEAM_RESPONSES,
)
def my_team_summaries(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[HourlySummaryOut]:
    membership = require_current_team_membership(db, user)
    summaries = db.scalars(
        select(HourlySummary)
        .where(HourlySummary.team_id == membership.team_id, HourlySummary.user_id == user.id)
        .order_by(HourlySummary.hour_start.desc())
    ).all()
    return [HourlySummaryOut.model_validate(summary) for summary in summaries]


@router.post(
    "/livekit/token",
    response_model=LivekitTokenResponse,
    summary="Create LiveKit token",
    description=(
        "Creates a LiveKit room token for the authenticated user's current team. "
        "Active current-team members can call this endpoint. It does not change stored ScreenPulse application state."
    ),
    tags=["livekit"],
    responses={
        **CURRENT_TEAM_RESPONSES,
        503: {"description": "LiveKit is not configured or token creation failed."},
    },
)
def livekit_token(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> LivekitTokenResponse:
    membership = require_current_team_membership(db, user)
    try:
        url, token = create_livekit_token(identity=str(user.id), room_name=f"screenpulse-team-{membership.team_id}")
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    return LivekitTokenResponse(livekit_url=url, token=token)
