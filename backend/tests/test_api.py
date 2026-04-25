import io
import os
from pathlib import Path

from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import select

TEST_DB_PATH = Path("storage/test_screenpulse.db")
if TEST_DB_PATH.exists():
    TEST_DB_PATH.unlink()

os.environ["SCREENPULSE_DATABASE_URL"] = f"sqlite:///./{TEST_DB_PATH.as_posix()}"
os.environ["SCREENPULSE_STORAGE_DIR"] = "storage"
os.environ["SCREENPULSE_SECRET_KEY"] = "test-secret-key-that-is-long-enough-for-jwt"
os.environ["SCREENPULSE_INVITE_CODE_MAX_USES"] = "1"
os.environ["SCREENPULSE_AUTH_RATE_LIMIT_ATTEMPTS"] = "3"
os.environ["SCREENPULSE_AUTH_RATE_LIMIT_WINDOW_SECONDS"] = "60"

from app.main import app  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.config import LEGACY_DEV_SECRET_KEY, Settings  # noqa: E402
from app.models import AuditLog, FrameCapture, HourlySummary, InviteCode, ScreenSession, Team, TeamMember, TeamSetting, VisionResult  # noqa: E402


def make_png_bytes() -> bytes:
    image = Image.new("RGB", (320, 200), color=(250, 250, 250))
    payload = io.BytesIO()
    image.save(payload, format="PNG")
    return payload.getvalue()


def register_and_auth_headers(client: TestClient, email: str, name: str, password: str) -> dict[str, str]:
    register_response = client.post(
        "/api/auth/register",
        json={"email": email, "name": name, "password": password},
    )
    assert register_response.status_code == 200
    token = register_response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_team_based_mvp_flow():
    with TestClient(app) as client:
        admin_headers = register_and_auth_headers(client, "admin@example.com", "Admin", "secret123")
        member_headers = register_and_auth_headers(client, "member@example.com", "Member", "secret123")

        create_team_response = client.post("/api/teams", json={"name": "Alpha Team"}, headers=admin_headers)
        assert create_team_response.status_code == 200
        team_id = create_team_response.json()["id"]
        assert create_team_response.json()["my_role"] == "admin"

        settings_response = client.get(f"/api/teams/{team_id}/settings", headers=admin_headers)
        assert settings_response.status_code == 200
        assert settings_response.json()["frame_interval_seconds"] == 300
        assert settings_response.json()["frame_interval_minutes"] == 5

        update_settings_response = client.patch(
            f"/api/teams/{team_id}/settings",
            json={"frame_interval_seconds": 30},
            headers=admin_headers,
        )
        assert update_settings_response.status_code == 200
        assert update_settings_response.json()["frame_interval_seconds"] == 30
        assert update_settings_response.json()["frame_interval_minutes"] == 1

        member_cannot_update = client.patch(
            f"/api/teams/{team_id}/settings",
            json={"frame_interval_seconds": 120},
            headers=member_headers,
        )
        assert member_cannot_update.status_code == 404

        invite_response = client.post(f"/api/teams/{team_id}/invite-codes", headers=admin_headers)
        assert invite_response.status_code == 200
        assert invite_response.json()["max_uses"] == 1
        code = invite_response.json()["code"]

        join_response = client.post(f"/api/invite-codes/{code}/join", headers=member_headers)
        assert join_response.status_code == 200
        assert join_response.json()["my_role"] == "member"

        members_response = client.get(f"/api/teams/{team_id}/members", headers=admin_headers)
        assert members_response.status_code == 200
        assert len(members_response.json()) == 2

        member_cannot_list_members = client.get(f"/api/teams/{team_id}/members", headers=member_headers)
        assert member_cannot_list_members.status_code == 403

        start_response = client.post(
            f"/api/teams/{team_id}/screen-sessions/start",
            json={"source_label": "Screen 1", "source_type": "monitor"},
            headers=member_headers,
        )
        assert start_response.status_code == 200
        session_id = start_response.json()["id"]
        assert start_response.json()["status"] == "active"

        frame_response = client.post(
            f"/api/teams/{team_id}/screen-sessions/{session_id}/frames",
            headers=member_headers,
            data={"captured_at": "2026-04-24T10:00:00Z"},
            files={"file": ("frame.png", make_png_bytes(), "image/png")},
        )
        assert frame_response.status_code == 200
        assert "frame_id" in frame_response.json()
        assert frame_response.json()["frame_interval_seconds"] == 30
        assert frame_response.json()["frame_interval_minutes"] == 1

        invalid_frame_response = client.post(
            f"/api/teams/{team_id}/screen-sessions/{session_id}/frames",
            headers=member_headers,
            data={"captured_at": "2026-04-24T10:01:00Z"},
            files={"file": ("frame.txt", b"not an image", "text/plain")},
        )
        assert invalid_frame_response.status_code == 400

        members_response = client.get(f"/api/teams/{team_id}/members", headers=admin_headers)
        member = next(item for item in members_response.json() if item["email"] == "member@example.com")
        assert member["active_session"]["id"] == session_id

        admin_summary_response = client.get(
            f"/api/teams/{team_id}/members/{member['user_id']}/summaries",
            headers=admin_headers,
        )
        assert admin_summary_response.status_code == 200
        assert len(admin_summary_response.json()) == 1

        my_summary_response = client.get(f"/api/teams/{team_id}/summaries/me", headers=member_headers)
        assert my_summary_response.status_code == 200
        assert len(my_summary_response.json()) == 1

        other_member_summary_response = client.get(
            f"/api/teams/{team_id}/summaries",
            headers=member_headers,
        )
        assert other_member_summary_response.status_code == 403

        stop_response = client.post(
            f"/api/teams/{team_id}/screen-sessions/{session_id}/stop",
            headers=member_headers,
        )
        assert stop_response.status_code == 200
        assert stop_response.json()["status"] == "stopped"


def test_database_integrity_and_cascade_cleanup():
    with TestClient(app) as client:
        owner_headers = register_and_auth_headers(client, "owner@example.com", "Owner", "secret123")
        teammate_headers = register_and_auth_headers(client, "teammate@example.com", "Teammate", "secret123")

        team_response = client.post("/api/teams", json={"name": "Beta Team"}, headers=owner_headers)
        assert team_response.status_code == 200
        team_id = team_response.json()["id"]

        invite_response = client.post(f"/api/teams/{team_id}/invite-codes", headers=owner_headers)
        assert invite_response.status_code == 200
        invite_code = invite_response.json()["code"]

        first_join = client.post(f"/api/invite-codes/{invite_code}/join", headers=teammate_headers)
        assert first_join.status_code == 200

        second_join = client.post(f"/api/invite-codes/{invite_code}/join", headers=teammate_headers)
        assert second_join.status_code == 200

        start_response = client.post(
            f"/api/teams/{team_id}/screen-sessions/start",
            json={"source_label": "Screen 2", "source_type": "monitor"},
            headers=teammate_headers,
        )
        assert start_response.status_code == 200
        session_id = start_response.json()["id"]

        frame_response = client.post(
            f"/api/teams/{team_id}/screen-sessions/{session_id}/frames",
            headers=teammate_headers,
            data={"captured_at": "2026-04-24T11:00:00Z"},
            files={"file": ("frame.png", make_png_bytes(), "image/png")},
        )
        assert frame_response.status_code == 200

    db = SessionLocal()
    try:
        invite = db.scalar(select(InviteCode).where(InviteCode.code == invite_code))
        assert invite is not None
        assert invite.used_count == 1

        team = db.get(Team, team_id)
        assert team is not None
        db.delete(team)
        db.commit()

        assert db.get(Team, team_id) is None
        assert db.scalar(select(TeamMember).where(TeamMember.team_id == team_id)) is None
        assert db.scalar(select(TeamSetting).where(TeamSetting.team_id == team_id)) is None
        assert db.scalar(select(InviteCode).where(InviteCode.team_id == team_id)) is None
        assert db.scalar(select(ScreenSession).where(ScreenSession.team_id == team_id)) is None
        assert db.scalar(select(FrameCapture).where(FrameCapture.team_id == team_id)) is None
        assert db.scalar(select(VisionResult).where(VisionResult.team_id == team_id)) is None
        assert db.scalar(select(HourlySummary).where(HourlySummary.team_id == team_id)) is None
        assert db.scalar(select(AuditLog).where(AuditLog.team_id == team_id)) is None
    finally:
        db.close()


def test_invite_code_usage_limit_blocks_new_members_after_first_use():
    with TestClient(app) as client:
        owner_headers = register_and_auth_headers(client, "limit-owner@example.com", "Owner", "secret123")
        first_headers = register_and_auth_headers(client, "limit-first@example.com", "First", "secret123")
        second_headers = register_and_auth_headers(client, "limit-second@example.com", "Second", "secret123")

        team_response = client.post("/api/teams", json={"name": "Limited Team"}, headers=owner_headers)
        assert team_response.status_code == 200
        team_id = team_response.json()["id"]

        invite_response = client.post(f"/api/teams/{team_id}/invite-codes", headers=owner_headers)
        assert invite_response.status_code == 200
        invite_code = invite_response.json()["code"]

        first_join = client.post(f"/api/invite-codes/{invite_code}/join", headers=first_headers)
        assert first_join.status_code == 200

        repeat_join = client.post(f"/api/invite-codes/{invite_code}/join", headers=first_headers)
        assert repeat_join.status_code == 200

        blocked_join = client.post(f"/api/invite-codes/{invite_code}/join", headers=second_headers)
        assert blocked_join.status_code == 400


def test_auth_rate_limit_blocks_repeated_login_attempts():
    with TestClient(app) as client:
        for _ in range(3):
            response = client.post(
                "/api/auth/login",
                json={"email": "missing@example.com", "password": "wrong"},
            )
            assert response.status_code == 401

        limited_response = client.post(
            "/api/auth/login",
            json={"email": "missing@example.com", "password": "wrong"},
        )
        assert limited_response.status_code == 429


def test_runtime_security_rejects_missing_or_legacy_secret():
    for secret_key in ("", LEGACY_DEV_SECRET_KEY, "short"):
        settings = Settings(secret_key=secret_key)
        try:
            settings.validate_runtime_security()
        except RuntimeError:
            pass
        else:
            raise AssertionError("insecure secret key was accepted")
