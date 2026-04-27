"""Authentication endpoints for registration, login, current-user lookup, and logout."""

from time import monotonic

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.dependencies import get_current_user, is_global_admin
from app.models import User
from app.schemas import AuthResponse, LoginRequest, MessageOut, RegisterRequest, UserOut
from app.security import create_access_token, hash_password, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])
settings = get_settings()
_auth_attempts: dict[str, list[float]] = {}

AUTH_RATE_LIMIT_RESPONSE = {429: {"description": "Too many authentication attempts from the same client and email."}}
AUTH_REQUIRED_RESPONSES = {
    401: {"description": "Missing, invalid, or expired bearer token."},
}


def _normalize_email(email: str) -> str:
    return email.strip().lower()


def _user_out(user: User) -> UserOut:
    return UserOut(
        id=user.id,
        email=user.email,
        name=user.name,
        current_research_group_id=user.current_research_group_id,
        current_team_id=user.current_research_group_id,
        is_admin=is_global_admin(user),
    )


def _client_key(request: Request, email: str, action: str) -> str:
    client_host = request.client.host if request.client else "unknown"
    return f"{action}:{client_host}:{email}"


def _enforce_auth_rate_limit(request: Request, email: str, action: str) -> None:
    now = monotonic()
    window_started = now - settings.auth_rate_limit_window_seconds
    key = _client_key(request, email, action)
    attempts = [seen_at for seen_at in _auth_attempts.get(key, []) if seen_at >= window_started]
    if len(attempts) >= settings.auth_rate_limit_attempts:
        _auth_attempts[key] = attempts
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Too many authentication attempts")
    attempts.append(now)
    _auth_attempts[key] = attempts


@router.post(
    "/register",
    response_model=AuthResponse,
    summary="Register user",
    description=(
        "Creates a user account and returns an access token. Anyone can call this endpoint. "
        "On success it stores a new user record."
    ),
    tags=["auth"],
    responses={
        400: {"description": "Email is invalid or already registered."},
        **AUTH_RATE_LIMIT_RESPONSE,
    },
)
def register(request: Request, payload: RegisterRequest, db: Session = Depends(get_db)) -> AuthResponse:
    email = _normalize_email(payload.email)
    _enforce_auth_rate_limit(request, email, "register")
    if "@" not in email:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid email address")

    existing = db.scalar(select(User).where(User.email == email))
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email is already registered")

    user = User(email=email, name=payload.name.strip(), password_hash=hash_password(payload.password))
    db.add(user)
    db.commit()
    db.refresh(user)

    return AuthResponse(access_token=create_access_token(user.id), user=_user_out(user))


@router.post(
    "/login",
    response_model=AuthResponse,
    summary="Log in",
    description=(
        "Authenticates an existing user and returns an access token. Anyone can call this endpoint. "
        "It does not change stored application state."
    ),
    tags=["auth"],
    responses={
        401: {"description": "Email or password is incorrect."},
        **AUTH_RATE_LIMIT_RESPONSE,
    },
)
def login(request: Request, payload: LoginRequest, db: Session = Depends(get_db)) -> AuthResponse:
    email = _normalize_email(payload.email)
    _enforce_auth_rate_limit(request, email, "login")
    user = db.scalar(select(User).where(User.email == email))
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")

    return AuthResponse(access_token=create_access_token(user.id), user=_user_out(user))


@router.get(
    "/me",
    response_model=UserOut,
    summary="Get current user",
    description=(
        "Returns the profile for the bearer token user. Authenticated users can call this endpoint. "
        "It does not change stored application state."
    ),
    tags=["auth"],
    responses=AUTH_REQUIRED_RESPONSES,
)
def me(user: User = Depends(get_current_user)) -> UserOut:
    return _user_out(user)


@router.post(
    "/logout",
    response_model=MessageOut,
    summary="Log out",
    description=(
        "Confirms client-side logout for the bearer token user. Authenticated users can call this endpoint. "
        "It does not revoke or mutate server-side token state."
    ),
    tags=["auth"],
    responses=AUTH_REQUIRED_RESPONSES,
)
def logout(_: User = Depends(get_current_user)) -> MessageOut:
    return MessageOut(message="Logged out")
