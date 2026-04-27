import io
import os
from pathlib import Path

from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import inspect, select

TEST_DB_PATH = Path("storage/test_screenpulse.db")
if TEST_DB_PATH.exists():
    TEST_DB_PATH.unlink()

os.environ["SCREENPULSE_DATABASE_URL"] = f"sqlite:///./{TEST_DB_PATH.as_posix()}"
os.environ["SCREENPULSE_STORAGE_DIR"] = "storage"
os.environ["SCREENPULSE_SECRET_KEY"] = "test-secret-key-that-is-long-enough-for-jwt"
os.environ["SCREENPULSE_INVITE_CODE_MAX_USES"] = "1"
os.environ["SCREENPULSE_AUTH_RATE_LIMIT_ATTEMPTS"] = "3"
os.environ["SCREENPULSE_AUTH_RATE_LIMIT_WINDOW_SECONDS"] = "60"
os.environ["SCREENPULSE_ADMIN_EMAILS"] = ",".join(
    [
        "admin@example.com",
        "owner@example.com",
        "limit-owner@example.com",
        "manage-admin@example.com",
        "solo-admin@example.com",
    ]
)

from app.main import app  # noqa: E402
from app.database import SessionLocal, engine  # noqa: E402
from app.config import LEGACY_DEV_SECRET_KEY, Settings  # noqa: E402
from app.models import AuditLog, DailyGoal, DailyReport, FrameCapture, HourlySummary, InviteCode, MentorFeedback, ScreenSession, ResearchGroup, ResearchGroupMember, ResearchGroupSetting, VisionResult  # noqa: E402


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
    assert "is_admin" in register_response.json()["user"]
    token = register_response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_team_based_mvp_flow():
    with TestClient(app) as client:
        admin_headers = register_and_auth_headers(client, "admin@example.com", "Admin", "secret123")
        member_headers = register_and_auth_headers(client, "member@example.com", "Member", "secret123")

        create_team_response = client.post("/api/research-groups", json={"name": "Alpha Team"}, headers=admin_headers)
        assert create_team_response.status_code == 200
        team_id = create_team_response.json()["id"]
        assert create_team_response.json()["my_role"] == "mentor"

        settings_response = client.get("/api/settings/current", headers=admin_headers)
        assert settings_response.status_code == 200
        assert settings_response.json()["frame_interval_seconds"] == 300
        assert settings_response.json()["frame_interval_minutes"] == 5
        assert settings_response.json()["force_screen_share"] is False

        update_settings_response = client.put(
            "/api/mentor/settings",
            json={"frame_interval_seconds": 30, "force_screen_share": True},
            headers=admin_headers,
        )
        assert update_settings_response.status_code == 200
        assert update_settings_response.json()["frame_interval_seconds"] == 30
        assert update_settings_response.json()["frame_interval_minutes"] == 1
        assert update_settings_response.json()["force_screen_share"] is True

        member_cannot_update = client.put(
            "/api/mentor/settings/capture-interval",
            json={"frame_interval_seconds": 120},
            headers=member_headers,
        )
        assert member_cannot_update.status_code == 404

        invite_response = client.post(
            "/api/mentor/invite-codes",
            json={"expires_in_hours": 24, "max_uses": 1},
            headers=admin_headers,
        )
        assert invite_response.status_code == 200
        assert invite_response.json()["max_uses"] == 1
        assert invite_response.json()["expires_at"] is not None
        code = invite_response.json()["code"]

        join_response = client.post("/api/research-groups/join", json={"code": code}, headers=member_headers)
        assert join_response.status_code == 200
        assert join_response.json()["my_role"] == "student"

        joined_member_cannot_update = client.put(
            "/api/mentor/settings/capture-interval",
            json={"frame_interval_seconds": 120},
            headers=member_headers,
        )
        assert joined_member_cannot_update.status_code == 403

        members_response = client.get("/api/mentor/members", headers=admin_headers)
        assert members_response.status_code == 200
        assert len(members_response.json()) == 2

        member_cannot_list_members = client.get("/api/mentor/members", headers=member_headers)
        assert member_cannot_list_members.status_code == 403

        start_response = client.post(
            "/api/sessions/start",
            json={"source_label": "Screen 1", "source_type": "monitor"},
            headers=member_headers,
        )
        assert start_response.status_code == 200
        session_id = start_response.json()["id"]
        assert start_response.json()["status"] == "active"

        frame_response = client.post(
            "/api/screenshots/upload",
            headers=member_headers,
            data={"captured_at": "2026-04-24T10:00:00Z"},
            files={"file": ("frame.png", make_png_bytes(), "image/png")},
        )
        assert frame_response.status_code == 200
        assert "frame_id" in frame_response.json()
        assert frame_response.json()["frame_interval_seconds"] == 30
        assert frame_response.json()["frame_interval_minutes"] == 1

        invalid_frame_response = client.post(
            "/api/screenshots/upload",
            headers=member_headers,
            data={"captured_at": "2026-04-24T10:01:00Z"},
            files={"file": ("frame.txt", b"not an image", "text/plain")},
        )
        assert invalid_frame_response.status_code == 400

        members_response = client.get("/api/mentor/members", headers=admin_headers)
        member = next(item for item in members_response.json() if item["email"] == "member@example.com")
        assert member["active_session"]["id"] == session_id

        admin_summary_response = client.get(
            f"/api/mentor/members/{member['user_id']}/summaries",
            headers=admin_headers,
        )
        assert admin_summary_response.status_code == 200
        assert len(admin_summary_response.json()) == 1

        my_summary_response = client.get("/api/summaries/my-research-group", headers=member_headers)
        assert my_summary_response.status_code == 200
        assert len(my_summary_response.json()) == 1

        other_member_summary_response = client.get(
            f"/api/mentor/summaries?research_group_id={team_id}",
            headers=member_headers,
        )
        assert other_member_summary_response.status_code == 403

        stop_response = client.post(
            "/api/sessions/stop",
            headers=member_headers,
        )
        assert stop_response.status_code == 200
        assert stop_response.json()["status"] == "stopped"

        audit_response = client.get(
            "/api/mentor/audit-logs?action=research_group_settings.updated",
            headers=admin_headers,
        )
        assert audit_response.status_code == 200
        assert audit_response.json()[0]["action"] == "research_group_settings.updated"
        assert audit_response.json()[0]["actor_email"] == "admin@example.com"


def test_database_integrity_and_cascade_cleanup():
    with TestClient(app) as client:
        owner_headers = register_and_auth_headers(client, "owner@example.com", "Owner", "secret123")
        teammate_headers = register_and_auth_headers(client, "teammate@example.com", "Teammate", "secret123")

        team_response = client.post("/api/research-groups", json={"name": "Beta Team"}, headers=owner_headers)
        assert team_response.status_code == 200
        team_id = team_response.json()["id"]

        invite_response = client.post("/api/mentor/invite-codes", headers=owner_headers)
        assert invite_response.status_code == 200
        invite_code = invite_response.json()["code"]

        first_join = client.post("/api/research-groups/join", json={"code": invite_code}, headers=teammate_headers)
        assert first_join.status_code == 200

        second_join = client.post("/api/research-groups/join", json={"code": invite_code}, headers=teammate_headers)
        assert second_join.status_code == 200

        start_response = client.post(
            "/api/sessions/start",
            json={"source_label": "Screen 2", "source_type": "monitor"},
            headers=teammate_headers,
        )
        assert start_response.status_code == 200

        frame_response = client.post(
            "/api/screenshots/upload",
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

        team = db.get(ResearchGroup, team_id)
        assert team is not None
        db.delete(team)
        db.commit()

        assert db.get(ResearchGroup, team_id) is None
        assert db.scalar(select(ResearchGroupMember).where(ResearchGroupMember.team_id == team_id)) is None
        assert db.scalar(select(ResearchGroupSetting).where(ResearchGroupSetting.team_id == team_id)) is None
        assert db.scalar(select(InviteCode).where(InviteCode.team_id == team_id)) is None
        assert db.scalar(select(ScreenSession).where(ScreenSession.team_id == team_id)) is None
        assert db.scalar(select(FrameCapture).where(FrameCapture.team_id == team_id)) is None
        assert db.scalar(select(VisionResult).where(VisionResult.team_id == team_id)) is None
        assert db.scalar(select(HourlySummary).where(HourlySummary.team_id == team_id)) is None
        assert db.scalar(select(DailyGoal).where(DailyGoal.team_id == team_id)) is None
        assert db.scalar(select(DailyReport).where(DailyReport.team_id == team_id)) is None
        assert db.scalar(select(MentorFeedback).where(MentorFeedback.team_id == team_id)) is None
        assert db.scalar(select(AuditLog).where(AuditLog.team_id == team_id)) is None
    finally:
        db.close()


def test_invite_code_usage_limit_blocks_new_members_after_first_use():
    with TestClient(app) as client:
        owner_headers = register_and_auth_headers(client, "limit-owner@example.com", "Owner", "secret123")
        first_headers = register_and_auth_headers(client, "limit-first@example.com", "First", "secret123")
        second_headers = register_and_auth_headers(client, "limit-second@example.com", "Second", "secret123")

        team_response = client.post("/api/research-groups", json={"name": "Limited Team"}, headers=owner_headers)
        assert team_response.status_code == 200

        invite_response = client.post("/api/mentor/invite-codes", headers=owner_headers)
        assert invite_response.status_code == 200
        invite_code = invite_response.json()["code"]

        first_join = client.post("/api/research-groups/join", json={"code": invite_code}, headers=first_headers)
        assert first_join.status_code == 200

        repeat_join = client.post("/api/research-groups/join", json={"code": invite_code}, headers=first_headers)
        assert repeat_join.status_code == 200

        blocked_join = client.post("/api/research-groups/join", json={"code": invite_code}, headers=second_headers)
        assert blocked_join.status_code == 400


def test_admin_can_manage_members_invites_and_frame_history():
    with TestClient(app) as client:
        admin_headers = register_and_auth_headers(client, "manage-admin@example.com", "Admin", "secret123")
        member_headers = register_and_auth_headers(client, "manage-member@example.com", "Member", "secret123")
        extra_headers = register_and_auth_headers(client, "manage-extra@example.com", "Extra", "secret123")

        team_response = client.post("/api/research-groups", json={"name": "Managed Team"}, headers=admin_headers)
        assert team_response.status_code == 200
        team_id = team_response.json()["id"]

        add_response = client.post(
            "/api/mentor/members",
            json={"email": "manage-member@example.com", "role": "student"},
            headers=admin_headers,
        )
        assert add_response.status_code == 200
        member_id = add_response.json()["user_id"]

        member_cannot_add = client.post(
            "/api/mentor/members",
            json={"email": "manage-extra@example.com", "role": "student"},
            headers=member_headers,
        )
        assert member_cannot_add.status_code == 403

        promote_response = client.patch(
            f"/api/mentor/members/{member_id}",
            json={"role": "mentor"},
            headers=admin_headers,
        )
        assert promote_response.status_code == 200
        assert promote_response.json()["role"] == "mentor"

        demote_response = client.patch(
            f"/api/mentor/members/{member_id}",
            json={"role": "student"},
            headers=admin_headers,
        )
        assert demote_response.status_code == 200
        assert demote_response.json()["role"] == "student"

        invite_response = client.post("/api/mentor/invite-codes", headers=admin_headers)
        assert invite_response.status_code == 200
        invite_id = invite_response.json()["id"]
        invite_code = invite_response.json()["code"]

        invite_list_response = client.get("/api/mentor/invite-codes", headers=admin_headers)
        assert invite_list_response.status_code == 200
        assert invite_list_response.json()[0]["id"] == invite_id

        disable_invite_response = client.patch(
            f"/api/mentor/invite-codes/{invite_id}",
            json={"status": "disabled"},
            headers=admin_headers,
        )
        assert disable_invite_response.status_code == 200
        assert disable_invite_response.json()["status"] == "disabled"

        disabled_join_response = client.post("/api/research-groups/join", json={"code": invite_code}, headers=extra_headers)
        assert disabled_join_response.status_code == 404

        start_response = client.post(
            "/api/sessions/start",
            json={"source_label": "Screen 3", "source_type": "monitor"},
            headers=member_headers,
        )
        assert start_response.status_code == 200

        frame_response = client.post(
            "/api/screenshots/upload",
            headers=member_headers,
            data={"captured_at": "2026-04-24T12:00:00Z"},
            files={"file": ("frame.png", make_png_bytes(), "image/png")},
        )
        assert frame_response.status_code == 200
        frame_id = frame_response.json()["frame_id"]

        member_cannot_list_frames = client.get("/api/mentor/frames", headers=member_headers)
        assert member_cannot_list_frames.status_code == 403

        frame_list_response = client.get("/api/mentor/frames", headers=admin_headers)
        assert frame_list_response.status_code == 200
        assert frame_list_response.json()[0]["frame_id"] == frame_id
        assert frame_list_response.json()[0]["recognized_content"]

        summary_list_response = client.get(f"/api/mentor/summaries?research_group_id={team_id}", headers=admin_headers)
        assert summary_list_response.status_code == 200
        summary_id = summary_list_response.json()[0]["id"]

        delete_summary_response = client.delete(f"/api/mentor/summaries/{summary_id}", headers=admin_headers)
        assert delete_summary_response.status_code == 204

        delete_frame_response = client.delete(f"/api/mentor/frames/{frame_id}", headers=admin_headers)
        assert delete_frame_response.status_code == 204

        db = SessionLocal()
        try:
            assert db.get(FrameCapture, frame_id) is None
            assert db.scalar(select(VisionResult).where(VisionResult.frame_id == frame_id)) is None
        finally:
            db.close()

        remove_response = client.delete(f"/api/mentor/members/{member_id}", headers=admin_headers)
        assert remove_response.status_code == 204

        removed_member_team_response = client.get("/api/research-groups/current", headers=member_headers)
        assert removed_member_team_response.status_code == 404


def test_daily_goal_report_and_mentor_feedback_flow():
    with TestClient(app) as client:
        mentor_headers = register_and_auth_headers(client, "mentor@example.com", "Mentor", "secret123")
        student_headers = register_and_auth_headers(client, "student@example.com", "Student", "secret123")
        outsider_headers = register_and_auth_headers(client, "outsider@example.com", "Outsider", "secret123")

        team_response = client.post("/api/research-groups", json={"name": "Research Group"}, headers=mentor_headers)
        assert team_response.status_code == 200
        team_id = team_response.json()["id"]
        assert team_response.json()["my_role"] == "mentor"

        invite_response = client.post("/api/mentor/invite-codes", headers=mentor_headers)
        assert invite_response.status_code == 200
        join_response = client.post("/api/research-groups/join", json={"code": invite_response.json()["code"]}, headers=student_headers)
        assert join_response.status_code == 200

        outsider_response = client.post("/api/research-groups", json={"name": "Other Group"}, headers=outsider_headers)
        assert outsider_response.status_code == 200

        goal_response = client.put(
            "/api/daily-goals/my",
            json={
                "goal_date": "2026-04-24",
                "main_goal": "Read transformer papers",
                "planned_tasks": "Read two papers and write notes",
                "expected_challenges": "Unclear ablation section",
                "needs_mentor_help": True,
            },
            headers=student_headers,
        )
        assert goal_response.status_code == 200
        assert goal_response.json()["research_group_id"] == team_id
        assert goal_response.json()["user_id"] != team_response.json()["created_by_user_id"]

        report_response = client.put(
            "/api/daily-reports/my",
            json={
                "report_date": "2026-04-24",
                "completed_work": "Finished reading one paper",
                "problems": "Need help comparing baselines",
                "next_plan": "Read the second paper tomorrow",
                "needs_mentor_help": True,
                "notes": "Prepared questions for meeting",
            },
            headers=student_headers,
        )
        assert report_response.status_code == 200
        student_id = report_response.json()["user_id"]

        student_cannot_review = client.post(
            f"/api/mentor/students/{student_id}/feedback",
            json={
                "report_date": "2026-04-24",
                "content": "Looks good",
                "status_mark": "normal",
                "next_step": "",
                "needs_meeting": False,
            },
            headers=student_headers,
        )
        assert student_cannot_review.status_code == 403

        outsider_cannot_read = client.get(
            f"/api/mentor/students/{student_id}/daily-report?report_date=2026-04-24",
            headers=outsider_headers,
        )
        assert outsider_cannot_read.status_code == 404

        mentor_detail = client.get(
            f"/api/mentor/students/{student_id}/daily-report?report_date=2026-04-24",
            headers=mentor_headers,
        )
        assert mentor_detail.status_code == 200
        assert mentor_detail.json()["goal"]["main_goal"] == "Read transformer papers"
        assert mentor_detail.json()["report"]["completed_work"] == "Finished reading one paper"

        feedback_response = client.post(
            f"/api/mentor/students/{student_id}/feedback",
            json={
                "report_date": "2026-04-24",
                "content": "Please focus on the baseline comparison next.",
                "score": 88,
                "status_mark": "needs_attention",
                "next_step": "Send a short baseline table.",
                "needs_meeting": True,
            },
            headers=mentor_headers,
        )
        assert feedback_response.status_code == 200
        assert feedback_response.json()["mentor_user_id"] == team_response.json()["created_by_user_id"]

        my_detail = client.get(
            "/api/daily-reports/my/detail?report_date=2026-04-24",
            headers=student_headers,
        )
        assert my_detail.status_code == 200
        assert my_detail.json()["feedback"][0]["content"] == "Please focus on the baseline comparison next."

        audit_response = client.get(
            "/api/mentor/audit-logs?action=mentor_feedback.created",
            headers=mentor_headers,
        )
        assert audit_response.status_code == 200
        assert audit_response.json()[0]["action"] == "mentor_feedback.created"


def test_global_admin_can_list_global_resources_without_group_membership():
    with TestClient(app) as client:
        mentor_headers = register_and_auth_headers(client, "global-mentor@example.com", "Mentor", "secret123")
        student_headers = register_and_auth_headers(client, "global-student@example.com", "Student", "secret123")
        solo_admin_headers = register_and_auth_headers(client, "solo-admin@example.com", "Solo Admin", "secret123")

        solo_me_response = client.get("/api/auth/me", headers=solo_admin_headers)
        assert solo_me_response.status_code == 200
        assert solo_me_response.json()["is_admin"] is True
        assert solo_me_response.json()["current_research_group_id"] is None

        team_response = client.post("/api/research-groups", json={"name": "Global Admin Summary Team"}, headers=mentor_headers)
        assert team_response.status_code == 200
        team_id = team_response.json()["id"]

        invite_response = client.post("/api/mentor/invite-codes", headers=mentor_headers)
        assert invite_response.status_code == 200
        join_response = client.post("/api/research-groups/join", json={"code": invite_response.json()["code"]}, headers=student_headers)
        assert join_response.status_code == 200

        start_response = client.post(
            "/api/sessions/start",
            json={"source_label": "Screen 4", "source_type": "monitor"},
            headers=student_headers,
        )
        assert start_response.status_code == 200

        frame_response = client.post(
            "/api/screenshots/upload",
            headers=student_headers,
            data={"captured_at": "2026-04-24T13:00:00Z"},
            files={"file": ("frame.png", make_png_bytes(), "image/png")},
        )
        assert frame_response.status_code == 200

        users_response = client.get("/api/admin/users", headers=solo_admin_headers)
        assert users_response.status_code == 200

        groups_response = client.get("/api/admin/research-groups", headers=solo_admin_headers)
        assert groups_response.status_code == 200
        assert any(group["id"] == team_id for group in groups_response.json())

        sessions_response = client.get("/api/admin/sessions", headers=solo_admin_headers)
        assert sessions_response.status_code == 200
        assert any(session["research_group_id"] == team_id for session in sessions_response.json())

        summaries_response = client.get("/api/admin/summaries", headers=solo_admin_headers)
        assert summaries_response.status_code == 200
        assert any(summary["research_group_id"] == team_id for summary in summaries_response.json())

        scoped_summaries_response = client.get(
            f"/api/admin/summaries?research_group_id={team_id}",
            headers=solo_admin_headers,
        )
        assert scoped_summaries_response.status_code == 200
        assert {summary["research_group_id"] for summary in scoped_summaries_response.json()} == {team_id}

        mentor_scope_response = client.get("/api/mentor/members", headers=solo_admin_headers)
        assert mentor_scope_response.status_code == 404


def test_legacy_team_aliases_return_legacy_contracts():
    with TestClient(app) as client:
        mentor_headers = register_and_auth_headers(client, "legacy-mentor@example.com", "Legacy Mentor", "secret123")
        student_headers = register_and_auth_headers(client, "legacy-student@example.com", "Legacy Student", "secret123")

        create_response = client.post("/api/teams", json={"name": "Legacy Group"}, headers=mentor_headers)
        assert create_response.status_code == 200
        assert create_response.json()["my_role"] == "admin"

        invite_response = client.post("/api/admin/invite-codes", headers=mentor_headers)
        assert invite_response.status_code == 200
        assert invite_response.json()["team_id"] == create_response.json()["id"]

        join_response = client.post(
            "/api/teams/join",
            json={"code": invite_response.json()["code"]},
            headers=student_headers,
        )
        assert join_response.status_code == 200
        assert join_response.json()["my_role"] == "member"

        members_response = client.get("/api/admin/members", headers=mentor_headers)
        assert members_response.status_code == 200
        assert {item["role"] for item in members_response.json()} == {"admin", "member"}

        audit_response = client.get("/api/admin/audit-logs?action=team.created", headers=mentor_headers)
        assert audit_response.status_code == 200
        assert audit_response.json()[0]["action"] == "team.created"


def test_sqlite_schema_uses_research_group_table_names():
    inspector = inspect(engine)
    table_names = set(inspector.get_table_names())
    assert "research_groups" in table_names
    assert "research_group_members" in table_names
    assert "research_group_settings" in table_names
    assert "teams" not in table_names
    assert "team_members" not in table_names
    assert "team_settings" not in table_names
    user_columns = {column["name"] for column in inspector.get_columns("users")}
    assert "current_research_group_id" in user_columns
    assert "current_team_id" not in user_columns


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


def test_request_id_is_returned_and_can_be_provided_by_client():
    with TestClient(app) as client:
        generated_response = client.get("/")
        assert generated_response.status_code == 200
        assert generated_response.headers["X-Request-ID"]

        provided_response = client.get("/", headers={"X-Request-ID": "debug-register-1"})
        assert provided_response.status_code == 200
        assert provided_response.headers["X-Request-ID"] == "debug-register-1"


def test_runtime_security_rejects_missing_or_legacy_secret():
    for secret_key in ("", LEGACY_DEV_SECRET_KEY, "short"):
        settings = Settings(secret_key=secret_key)
        try:
            settings.validate_runtime_security()
        except RuntimeError:
            pass
        else:
            raise AssertionError("insecure secret key was accepted")
