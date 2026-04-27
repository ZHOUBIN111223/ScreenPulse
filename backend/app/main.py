"""Application entrypoint that wires startup, middleware, and routers for the ScreenPulse API."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import inspect, text

from app.config import get_settings
from app.database import Base, engine
from app.observability import request_observability_middleware
from app.routes import auth, learning, sessions, teams
from app.routes import admin

settings = get_settings()

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")


def _ensure_sqlite_interval_seconds_column() -> None:
    if not settings.database_url.startswith("sqlite"):
        return

    inspector = inspect(engine)
    if "research_group_settings" not in inspector.get_table_names():
        return

    columns = {column["name"] for column in inspector.get_columns("research_group_settings")}
    if "frame_interval_seconds" in columns:
        return

    with engine.begin() as connection:
        connection.execute(text("ALTER TABLE research_group_settings ADD COLUMN frame_interval_seconds INTEGER"))
        connection.execute(
            text(
                "UPDATE research_group_settings "
                "SET frame_interval_seconds = COALESCE(frame_interval_minutes, :default_minutes) * 60"
            ),
            {"default_minutes": settings.default_sampling_interval_minutes},
        )


def _ensure_sqlite_force_screen_share_column() -> None:
    if not settings.database_url.startswith("sqlite"):
        return

    inspector = inspect(engine)
    if "research_group_settings" not in inspector.get_table_names():
        return

    columns = {column["name"] for column in inspector.get_columns("research_group_settings")}
    if "force_screen_share" in columns:
        return

    with engine.begin() as connection:
        connection.execute(text("ALTER TABLE research_group_settings ADD COLUMN force_screen_share BOOLEAN DEFAULT 0 NOT NULL"))


def _ensure_sqlite_invite_code_max_uses_column() -> None:
    if not settings.database_url.startswith("sqlite"):
        return

    inspector = inspect(engine)
    if "invite_codes" not in inspector.get_table_names():
        return

    columns = {column["name"] for column in inspector.get_columns("invite_codes")}
    if "max_uses" in columns:
        return

    with engine.begin() as connection:
        connection.execute(text("ALTER TABLE invite_codes ADD COLUMN max_uses INTEGER"))
        connection.execute(
            text("UPDATE invite_codes SET max_uses = :max_uses WHERE max_uses IS NULL"),
            {"max_uses": settings.invite_code_max_uses},
        )


def _ensure_sqlite_user_current_team_column() -> None:
    if not settings.database_url.startswith("sqlite"):
        return

    inspector = inspect(engine)
    if "users" not in inspector.get_table_names():
        return

    columns = {column["name"] for column in inspector.get_columns("users")}
    if "current_research_group_id" in columns:
        return

    with engine.begin() as connection:
        connection.execute(text("ALTER TABLE users ADD COLUMN current_research_group_id INTEGER"))


def _ensure_sqlite_research_group_schema() -> None:
    if not settings.database_url.startswith("sqlite"):
        return

    inspector = inspect(engine)
    table_names = set(inspector.get_table_names())
    table_renames = {
        "teams": "research_groups",
        "team_members": "research_group_members",
        "team_settings": "research_group_settings",
    }

    with engine.begin() as connection:
        for old_name, new_name in table_renames.items():
            if old_name in table_names and new_name not in table_names:
                connection.execute(text(f"ALTER TABLE {old_name} RENAME TO {new_name}"))

    inspector = inspect(engine)
    table_names = set(inspector.get_table_names())
    column_tables = [
        "invite_codes",
        "screen_sessions",
        "frame_captures",
        "vision_results",
        "hourly_summaries",
        "daily_goals",
        "daily_reports",
        "mentor_feedback",
        "audit_logs",
        "research_group_members",
        "research_group_settings",
    ]

    with engine.begin() as connection:
        for table_name in column_tables:
            if table_name not in table_names:
                continue
            columns = {column["name"] for column in inspector.get_columns(table_name)}
            if "team_id" in columns and "research_group_id" not in columns:
                connection.execute(text(f"ALTER TABLE {table_name} RENAME COLUMN team_id TO research_group_id"))

        if "users" in table_names:
            columns = {column["name"] for column in inspector.get_columns("users")}
            if "current_team_id" in columns and "current_research_group_id" not in columns:
                connection.execute(text("ALTER TABLE users RENAME COLUMN current_team_id TO current_research_group_id"))

        if "research_group_members" in table_names:
            connection.execute(text("UPDATE research_group_members SET role = 'mentor' WHERE role = 'admin'"))
            connection.execute(text("UPDATE research_group_members SET role = 'student' WHERE role = 'member'"))

        if "audit_logs" in table_names:
            connection.execute(text("UPDATE audit_logs SET action = 'research_group.created' WHERE action = 'team.created'"))
            connection.execute(text("UPDATE audit_logs SET action = 'research_group.joined' WHERE action = 'team.joined'"))
            connection.execute(text("UPDATE audit_logs SET action = 'research_group_member.added' WHERE action = 'team_member.added'"))
            connection.execute(
                text("UPDATE audit_logs SET action = 'research_group_member.role_updated' WHERE action = 'team_member.role_updated'")
            )
            connection.execute(text("UPDATE audit_logs SET action = 'research_group_member.removed' WHERE action = 'team_member.removed'"))
            connection.execute(text("UPDATE audit_logs SET action = 'research_group_settings.updated' WHERE action = 'team_settings.updated'"))


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings.validate_runtime_security()
    settings.storage_path.mkdir(parents=True, exist_ok=True)
    _ensure_sqlite_research_group_schema()
    Base.metadata.create_all(bind=engine)
    _ensure_sqlite_interval_seconds_column()
    _ensure_sqlite_force_screen_share_column()
    _ensure_sqlite_invite_code_max_uses_column()
    _ensure_sqlite_user_current_team_column()
    yield


app = FastAPI(title=settings.app_name, lifespan=lifespan)
app.middleware("http")(request_observability_middleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix=settings.api_prefix)
app.include_router(teams.router, prefix=settings.api_prefix)
app.include_router(sessions.router, prefix=settings.api_prefix)
app.include_router(learning.router, prefix=settings.api_prefix)
app.include_router(admin.router, prefix=settings.api_prefix)
app.include_router(admin.mentor_router, prefix=settings.api_prefix)


@app.get(
    "/",
    summary="Health check",
    description="Returns basic API health information. Anyone can call this endpoint. It does not change stored application state.",
    tags=["health"],
    responses={200: {"description": "API is running."}},
)
def root() -> dict[str, str]:
    return {"status": "ok", "service": settings.app_name}
