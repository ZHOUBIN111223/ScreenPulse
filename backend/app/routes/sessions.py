"""Team-scoped screen-session lifecycle, frame upload, and LiveKit token endpoints."""

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, Path, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user, require_team_membership
from app.models import FrameCapture, ScreenSession, User, VisionResult
from app.schemas import FrameUploadResult, LivekitTokenResponse, SessionOut, SessionStartRequest
from app.services.analysis import analyze_screenshot, get_team_setting, refresh_hourly_summary, save_frame_file
from app.services.audit import record_audit_log
from app.services.livekit import create_livekit_token

router = APIRouter(tags=["screen-sessions"])

AUTH_RESPONSE = {401: {"description": "Missing, invalid, or expired bearer token."}}
TEAM_MEMBER_RESPONSES = {
    **AUTH_RESPONSE,
    404: {"description": "Team was not found or caller is not an active member."},
}
OWNED_SESSION_RESPONSES = {
    **TEAM_MEMBER_RESPONSES,
    404: {"description": "Team, membership, or owned session was not found."},
}
TEAM_ID_PATH = Path(..., description="Team ID.")
SESSION_ID_PATH = Path(..., description="Screen session ID owned by the authenticated user.")


def _serialize_session(session: ScreenSession, db: Session) -> SessionOut:
    frame_count = db.scalar(select(func.count()).select_from(FrameCapture).where(FrameCapture.session_id == session.id)) or 0
    return SessionOut.model_validate(session).model_copy(update={"frame_count": frame_count})


def _require_owned_session(db: Session, team_id: int, session_id: int, user_id: int) -> ScreenSession:
    session = db.get(ScreenSession, session_id)
    if session is None or session.team_id != team_id or session.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    return session


@router.get(
    "/teams/{team_id}/screen-sessions/current",
    response_model=SessionOut | None,
    summary="Get current screen session",
    description=(
        "Returns the authenticated user's active screen session in a team, or null. "
        "Active team members can call this endpoint. It does not change stored application state."
    ),
    tags=["screen-sessions"],
    responses=TEAM_MEMBER_RESPONSES,
)
def current_session(
    team_id: Annotated[int, TEAM_ID_PATH],
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_team_membership(db, user, team_id)
    session = db.scalar(
        select(ScreenSession)
        .where(
            ScreenSession.team_id == team_id,
            ScreenSession.user_id == user.id,
            ScreenSession.status == "active",
        )
        .order_by(ScreenSession.started_at.desc())
    )
    if session is None:
        return None
    return _serialize_session(session, db)


@router.post(
    "/teams/{team_id}/screen-sessions/start",
    response_model=SessionOut,
    summary="Start screen session",
    description=(
        "Starts or returns the authenticated user's active screen session in a team. "
        "Active team members can call this endpoint. On success it may store a new session and write an audit log."
    ),
    tags=["screen-sessions"],
    responses={
        **TEAM_MEMBER_RESPONSES,
        400: {"description": "Caller already has an active sharing session in another team."},
    },
)
def start(
    team_id: Annotated[int, TEAM_ID_PATH],
    payload: SessionStartRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SessionOut:
    require_team_membership(db, user, team_id)

    existing_same_team = db.scalar(
        select(ScreenSession).where(
            ScreenSession.team_id == team_id,
            ScreenSession.user_id == user.id,
            ScreenSession.status == "active",
        )
    )
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
    "/teams/{team_id}/screen-sessions/{session_id}/frames",
    response_model=FrameUploadResult,
    summary="Upload session frame",
    description=(
        "Uploads one screenshot frame for the authenticated user's active session. "
        "The session owner can call this endpoint. On success it stores the image, analysis result, and refreshed summary."
    ),
    tags=["screen-sessions"],
    responses={
        **OWNED_SESSION_RESPONSES,
        400: {"description": "Session is already stopped or captured_at is invalid."},
    },
)
def upload_session_frame(
    team_id: Annotated[int, TEAM_ID_PATH],
    session_id: Annotated[int, SESSION_ID_PATH],
    captured_at: Annotated[str, Form(description="ISO timestamp when the frame was captured by the browser.")],
    file: Annotated[UploadFile, File(description="PNG screenshot frame uploaded from the browser.")],
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> FrameUploadResult:
    require_team_membership(db, user, team_id)
    session = _require_owned_session(db, team_id, session_id, user.id)
    if session.status != "active":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Session already stopped")

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
    "/teams/{team_id}/screen-sessions/{session_id}/stop",
    response_model=SessionOut,
    summary="Stop screen session",
    description=(
        "Stops the authenticated user's screen session. The session owner can call this endpoint. "
        "On success it marks the session stopped, stores the end time, and writes an audit log."
    ),
    tags=["screen-sessions"],
    responses=OWNED_SESSION_RESPONSES,
)
def stop(
    team_id: Annotated[int, TEAM_ID_PATH],
    session_id: Annotated[int, SESSION_ID_PATH],
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SessionOut:
    require_team_membership(db, user, team_id)
    session = _require_owned_session(db, team_id, session_id, user.id)

    if session.status != "active":
        return _serialize_session(session, db)

    session.status = "stopped"
    session.ended_at = datetime.utcnow()
    record_audit_log(db, team_id, user.id, "screen_session.stopped", "screen_session", session.id)
    db.commit()
    db.refresh(session)
    return _serialize_session(session, db)


@router.post(
    "/teams/{team_id}/livekit/token",
    response_model=LivekitTokenResponse,
    summary="Create LiveKit token",
    description=(
        "Creates a LiveKit room token for the authenticated user and team. Active team members can call this endpoint. "
        "It does not change stored ScreenPulse application state."
    ),
    tags=["livekit"],
    responses={
        **TEAM_MEMBER_RESPONSES,
        503: {"description": "LiveKit is not configured or token creation failed."},
    },
)
def livekit_token(
    team_id: Annotated[int, TEAM_ID_PATH],
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> LivekitTokenResponse:
    require_team_membership(db, user, team_id)
    try:
        url, token = create_livekit_token(identity=str(user.id), room_name=f"screenpulse-team-{team_id}")
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc

    return LivekitTokenResponse(livekit_url=url, token=token)
