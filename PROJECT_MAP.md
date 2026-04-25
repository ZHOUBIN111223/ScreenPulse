# ScreenPulse Project Map

## Purpose

ScreenPulse is a browser-based MVP for team screen-sharing analysis.
Users create teams, join by invite code, voluntarily share a full display into a
selected team, and the backend turns periodic screenshots into text observations
and hourly summaries that team admins can review.

## Read This In Order

1. Read this file for the global map and dependency rules.
2. Read the nearest `README.md` in the area you want to change.
3. Read the target file's top-level docstring or comment.
4. Read `backend/tests/test_api.py` before changing auth, team, session, or summary flows.
5. Verify changes with `pytest` in `backend/` and `npm run build` in `frontend/`.

## Top-Level Architecture

- `frontend/`
  - Next.js App Router UI.
  - `app/` contains thin route entries, including the main `/teams` workspace route.
  - `components/` contains login, registration, team workspace, and browser screen-share behavior.
  - `lib/api.ts` is the frontend's API contract and fetch wrapper.
- `backend/`
  - FastAPI application with synchronous SQLAlchemy sessions over SQLite.
  - `app/routes/` owns auth, team, invite-code, settings, summary, and screen-session endpoints.
  - `app/services/` owns screenshot persistence, model calls, summary refresh, and audit-log helpers.
  - `app/models.py` and `app/schemas.py` are the database and API contract layers.
- `docker-compose.yml`
  - Local multi-service startup for the MVP stack.
- `scripts/`
  - Local PowerShell helpers that start and stop the dev stack, and save runtime state in `.codex-run/`.

## Current Facts, Not Aspirations

- Backend persistence is synchronous `SQLAlchemy + SQLite`.
- Multimodal analysis currently uses `requests` against an OpenAI-compatible
  `/chat/completions` endpoint.
- The main product path stores screenshots, vision results, and hourly summaries,
  not raw video or audio.
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
- Frontend team workspace: `frontend/components/team-workspace.tsx`
- Backend application: `backend/app/main.py`
- Local dev startup helper: `scripts/start-dev.ps1`
- Auth flow: `backend/app/routes/auth.py`
- Team flow: `backend/app/routes/teams.py`
- Capture flow: `backend/app/routes/sessions.py`
- Analysis pipeline: `backend/app/services/analysis.py`
- Integration test covering the main backend path: `backend/tests/test_api.py`

## Core Data Flow

1. The user registers or logs in through `frontend/components/login-form.tsx`.
2. The user creates a team or joins one by invite code.
3. The user selects a team in `frontend/components/team-workspace.tsx`.
4. The browser uses `getDisplayMedia`, captures PNG frames locally, and uploads them into the selected team session.
5. Backend saves the screenshot, stores the vision result, and refreshes the team-scoped hourly summary.
6. Team admins review member status and summaries; members can review only their own summaries.

## Persistence Model

- `users`
  - Login identity and profile metadata.
- `teams`
  - Team container and creator metadata.
- `team_members`
  - Team membership and role (`admin` or `member`).
- `invite_codes`
  - Team invite codes with expiry, usage count, and status.
- `team_settings`
  - Team-scoped screenshot sampling interval in seconds, with legacy minute fields kept for compatibility.
- `screen_sessions`
  - Team-scoped screen sharing sessions with start, stop, and active status.
- `frame_captures`
  - Uploaded screenshots with capture metadata.
- `vision_results`
  - Text extracted from screenshots plus the detected activity description.
- `hourly_summaries`
  - Team-scoped hourly summaries derived from vision results.
- `audit_logs`
  - Team-scoped audit trail for key actions such as team creation, invite generation, settings changes, and session lifecycle.

## Change Checklist

- Do not add new architecture layers unless the task requires them.
- Preserve the separation between route coordination and service side effects.
- Preserve the separation between frontend view components and `lib/api.ts` request logic.
- Prefer explicit typed contracts over ad hoc dictionaries or undocumented payloads.
