# ScreenPulse Project Map

## Purpose

ScreenPulse is a browser-based MVP for research-group study process management.
Users create research groups, join by invite code, choose a current research group,
voluntarily share a full display, and the backend turns periodic screenshots
into text observations and hourly summaries. Students can submit daily goals and
daily reports, and group mentors can review student status and leave feedback.

## Read This In Order

1. Read this file for the global map and dependency rules.
2. Read the nearest `README.md` in the area you want to change.
3. Read the target file's top-level docstring or comment.
4. Read `backend/tests/test_api.py` before changing auth, team, session, or summary flows.
5. Verify changes with `pytest` in `backend/` and `npm run build` in `frontend/`.

## Top-Level Architecture

- `frontend/`
  - Next.js App Router UI.
  - `app/` contains thin route entries, including the main `/research-groups` workspace route, legacy `/teams` redirect, and the `/admin` console route.
  - `components/` contains login, registration, research-group workspace, admin console, and browser screen-share behavior.
  - `lib/api.ts` is the frontend's API contract and fetch wrapper.
- `backend/`
  - FastAPI application with synchronous SQLAlchemy sessions over SQLite.
  - `app/routes/` owns auth, current-research-group user endpoints, mentor endpoints, settings, audit-log, summary, screen-session, and daily learning endpoints.
  - `app/services/` owns screenshot persistence, model calls, summary refresh, and audit-log helpers.
  - `app/models.py` and `app/schemas.py` are the database and API contract layers.
- `docker-compose.yml`
  - Local multi-service startup for the MVP stack.
- `scripts/`
  - Local PowerShell helpers that start and stop the dev stack, and a Linux helper that initializes server `.env` values for Docker deployment.

## Current Facts, Not Aspirations

- Backend persistence is synchronous `SQLAlchemy + SQLite`.
- Multimodal analysis currently uses `requests` against an OpenAI-compatible
  `/chat/completions` endpoint.
- The main product path stores screenshots, vision results, hourly summaries,
  daily goals, daily reports, mentor feedback, and audit logs, not raw video or audio.
- LiveKit remains an optional token endpoint, not the current primary capture path.

## Dependency Direction

- Frontend pages may import from `frontend/components/`.
- Frontend components should use `frontend/lib/api.ts` for backend access.
- Backend routes may depend on `config`, `database`, `dependencies`, `models`, `schemas`, and `services`.
- Backend services must not import route modules.
- `models.py` defines persistence shape.
- `schemas.py` defines request and response shape.
- If an API payload changes, update backend schemas, frontend API types, and tests together.

## Key Entry Points

- Frontend landing page: `frontend/app/page.tsx`
- Frontend research-group workspace: `frontend/components/team-workspace.tsx`
- Frontend admin console: `frontend/components/admin-panel.tsx`
- Backend application: `backend/app/main.py`
- Local dev startup helper: `scripts/start-dev.ps1`
- Server env initialization helper: `scripts/init-server-env.sh`
- Auth flow: `backend/app/routes/auth.py`
- Research-group flow: `backend/app/routes/teams.py`
- Capture flow: `backend/app/routes/sessions.py`
- Daily learning flow: `backend/app/routes/learning.py`
- Global admin flow: `backend/app/routes/admin.py`
- Analysis pipeline: `backend/app/services/analysis.py`
- Integration test covering the main backend path: `backend/tests/test_api.py`

## Core Data Flow

1. The user registers or logs in through `frontend/components/login-form.tsx`.
2. The user creates a research group or joins one by invite code, which sets the backend current research group.
3. The user selects a research group in `frontend/components/team-workspace.tsx`, which updates the backend current research group.
4. The browser uses `getDisplayMedia`, captures PNG frames locally, and uploads them into the current research-group session.
5. Backend saves the screenshot, stores the vision result, and refreshes the research-group-scoped hourly summary.
6. Students submit daily goals and daily reports in the current research group.
7. Mentors review student status, summaries, reports, and feedback; students can review only their own learning records.

## Persistence Model

- `users`
  - Login identity, profile metadata, and current research group pointer.
- `research_groups`
  - Research group container and creator metadata.
- `research_group_members`
  - Research group membership and role (`mentor` or `student`).
- `invite_codes`
  - Research group invite codes with mentor-controlled expiry, usage count, max uses, and status.
- `research_group_settings`
  - Research-group-scoped screenshot sampling interval and screen-share enforcement flag, with legacy minute fields kept for compatibility.
- `screen_sessions`
  - Research-group-scoped screen sharing sessions with start, stop, and active status.
- `frame_captures`
  - Uploaded screenshots with capture metadata.
- `vision_results`
  - Text extracted from screenshots plus the detected activity description.
- `hourly_summaries`
  - Research-group-scoped hourly summaries derived from vision results.
- `daily_goals`
  - Research-group- and student-scoped daily goals submitted by students.
- `daily_reports`
  - Research-group- and student-scoped daily learning records submitted by students.
- `mentor_feedback`
  - Research-group-scoped mentor feedback for one student on one report date.
- `audit_logs`
  - Research-group-scoped audit trail for key actions such as research group creation, invite generation, settings changes, and session lifecycle.

## Change Checklist

- Do not add new architecture layers unless the task requires them.
- Preserve the separation between route coordination and service side effects.
- Preserve the separation between frontend view components and `lib/api.ts` request logic.
- Prefer explicit typed contracts over ad hoc dictionaries or undocumented payloads.
