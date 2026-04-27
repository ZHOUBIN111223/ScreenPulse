"""User-facing research-group endpoints for creation, joining, listing, and current-group selection."""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.dependencies import get_current_research_group, get_current_user, is_global_admin, require_research_group_membership
from app.models import InviteCode, ResearchGroup, ResearchGroupMember, ResearchGroupSetting, User
from app.schemas import CurrentResearchGroupUpdate, ResearchGroupCreateRequest, ResearchGroupJoinRequest, ResearchGroupOut
from app.services.audit import record_audit_log

settings = get_settings()
router = APIRouter(tags=["research-groups"])

AUTH_RESPONSE = {401: {"description": "Missing, invalid, or expired bearer token."}}
TEAM_MEMBER_RESPONSES = {
    **AUTH_RESPONSE,
    404: {"description": "Current team was not found or caller is not an active member."},
}


def _normalize_role(role: str) -> str:
    return {"admin": "mentor", "member": "student"}.get(role, role)


def _legacy_role(role: str) -> str:
    return {"mentor": "admin", "student": "member"}.get(role, role)


def _research_group_out(group: ResearchGroup, membership: ResearchGroupMember, legacy: bool = False) -> ResearchGroupOut:
    role = _legacy_role(membership.role) if legacy else _normalize_role(membership.role)
    return ResearchGroupOut(
        id=group.id,
        name=group.name,
        created_by_user_id=group.created_by_user_id,
        created_at=group.created_at,
        updated_at=group.updated_at,
        my_role=role,
    )


@router.post(
    "/research-groups",
    response_model=ResearchGroupOut,
    summary="Create research group",
    description=(
        "Creates a research group for the authenticated user. Authenticated users can call this endpoint. "
        "On success it stores a research group, makes the caller a mentor, creates default settings, sets the group current, "
        "and writes an audit log."
    ),
    tags=["research-groups"],
    responses=AUTH_RESPONSE,
)
def create_team(
    payload: ResearchGroupCreateRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ResearchGroupOut:
    group = ResearchGroup(name=payload.name.strip(), created_by_user_id=user.id)
    db.add(group)
    db.flush()

    membership = ResearchGroupMember(research_group_id=group.id, user_id=user.id, role="mentor", status="active")
    setting = ResearchGroupSetting(
        research_group_id=group.id,
        frame_interval_seconds=settings.default_sampling_interval_seconds,
        frame_interval_minutes=settings.default_sampling_interval_minutes,
    )
    user.current_research_group_id = group.id
    db.add(membership)
    db.add(setting)
    record_audit_log(db, group.id, user.id, "research_group.created", "research_group", group.id)
    db.commit()
    db.refresh(group)
    db.refresh(membership)
    return _research_group_out(group, membership)


@router.post("/teams", response_model=ResearchGroupOut, include_in_schema=False)
def create_team_legacy(
    payload: ResearchGroupCreateRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ResearchGroupOut:
    result = create_team(payload, user, db)
    return result.model_copy(update={"my_role": _legacy_role(result.my_role)})


@router.get(
    "/research-groups",
    response_model=list[ResearchGroupOut],
    summary="List my research groups",
    description=(
        "Lists active research groups for the authenticated user. Authenticated users can call this endpoint. "
        "It does not change stored application state."
    ),
    tags=["research-groups"],
    responses=AUTH_RESPONSE,
)
def list_research_groups(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[ResearchGroupOut]:
    rows = db.execute(
        select(ResearchGroup, ResearchGroupMember)
        .join(ResearchGroupMember, ResearchGroupMember.research_group_id == ResearchGroup.id)
        .where(ResearchGroupMember.user_id == user.id, ResearchGroupMember.status == "active")
        .order_by(ResearchGroupMember.joined_at.asc())
    ).all()
    return [_research_group_out(group, membership) for group, membership in rows]


@router.get("/teams", response_model=list[ResearchGroupOut], include_in_schema=False)
def list_teams(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[ResearchGroupOut]:
    return [item.model_copy(update={"my_role": _legacy_role(item.my_role)}) for item in list_research_groups(user, db)]


@router.get(
    "/research-groups/current",
    response_model=ResearchGroupOut,
    summary="Get current research group",
    description=(
        "Returns the authenticated user's current research group. Active group members can call this endpoint. "
        "It does not change stored application state."
    ),
    tags=["research-groups"],
    responses=TEAM_MEMBER_RESPONSES,
)
def current_research_group(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> ResearchGroupOut:
    group = get_current_research_group(db, user)
    membership = require_research_group_membership(db, user, group.id)
    return _research_group_out(group, membership)


@router.get("/teams/current", response_model=ResearchGroupOut, include_in_schema=False)
def current_team(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> ResearchGroupOut:
    result = current_research_group(user, db)
    return result.model_copy(update={"my_role": _legacy_role(result.my_role)})


@router.put(
    "/research-groups/current",
    response_model=ResearchGroupOut,
    summary="Set current research group",
    description=(
        "Sets the authenticated user's current research group. Active group members can call this endpoint. "
        "On success it updates the user's current team pointer."
    ),
    tags=["research-groups"],
    responses=TEAM_MEMBER_RESPONSES,
)
def set_current_team(
    payload: CurrentResearchGroupUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ResearchGroupOut:
    group = db.get(ResearchGroup, payload.research_group_id)
    if group is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Research group not found")
    if is_global_admin(user):
        membership = db.scalar(
            select(ResearchGroupMember).where(
                ResearchGroupMember.research_group_id == group.id,
                ResearchGroupMember.user_id == user.id,
                ResearchGroupMember.status == "active",
            )
        ) or ResearchGroupMember(research_group_id=group.id, user_id=user.id, role="mentor", status="active")
    else:
        membership = require_research_group_membership(db, user, payload.research_group_id)
    user.current_research_group_id = group.id
    db.commit()
    db.refresh(user)
    return _research_group_out(group, membership)


@router.put("/teams/current", response_model=ResearchGroupOut, include_in_schema=False)
def set_current_team_legacy(
    payload: CurrentResearchGroupUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ResearchGroupOut:
    result = set_current_team(payload, user, db)
    return result.model_copy(update={"my_role": _legacy_role(result.my_role)})


@router.post(
    "/research-groups/join",
    response_model=ResearchGroupOut,
    summary="Join research group by invite code",
    description=(
        "Adds or reactivates the authenticated user as a research-group member using an invite code. "
        "Authenticated users can call this endpoint. On success it may update invite usage, membership status, "
        "audit logs, and the user's current team."
    ),
    tags=["research-groups"],
    responses={
        **AUTH_RESPONSE,
        400: {"description": "Invite code expired or reached its usage limit."},
        404: {"description": "Invite code or target team was not found."},
    },
)
def join_team(
    payload: ResearchGroupJoinRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ResearchGroupOut:
    invite_code = db.scalar(select(InviteCode).where(InviteCode.code == payload.code.strip().upper()))
    if invite_code is None or invite_code.status != "active":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invite code not found")
    if invite_code.expires_at is not None and invite_code.expires_at < datetime.utcnow():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invite code has expired")

    existing_membership = db.scalar(
        select(ResearchGroupMember).where(
            ResearchGroupMember.research_group_id == invite_code.research_group_id,
            ResearchGroupMember.user_id == user.id,
        )
    )
    if existing_membership is None:
        if invite_code.max_uses is not None and invite_code.used_count >= invite_code.max_uses:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invite code usage limit reached")
        existing_membership = ResearchGroupMember(
            research_group_id=invite_code.research_group_id,
            user_id=user.id,
            role="student",
            status="active",
        )
        db.add(existing_membership)
        invite_code.used_count += 1
        record_audit_log(db, invite_code.research_group_id, user.id, "research_group.joined", "research_group", invite_code.research_group_id)
    else:
        if existing_membership.status != "active":
            if invite_code.max_uses is not None and invite_code.used_count >= invite_code.max_uses:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invite code usage limit reached")
            existing_membership.status = "active"
            invite_code.used_count += 1
            record_audit_log(db, invite_code.research_group_id, user.id, "research_group.joined", "research_group", invite_code.research_group_id)

    group = db.get(ResearchGroup, invite_code.research_group_id)
    if group is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Research group not found")
    user.current_research_group_id = group.id
    db.commit()
    db.refresh(existing_membership)
    return _research_group_out(group, existing_membership)


@router.post("/teams/join", response_model=ResearchGroupOut, include_in_schema=False)
def join_team_legacy(
    payload: ResearchGroupJoinRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ResearchGroupOut:
    result = join_team(payload, user, db)
    return result.model_copy(update={"my_role": _legacy_role(result.my_role)})
