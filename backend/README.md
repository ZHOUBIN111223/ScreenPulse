# Backend Map

This directory contains the FastAPI backend for auth, current-research-group
membership, invite-code joins, current-research-group session lifecycle, frame
ingestion, screenshot analysis, hourly summary reporting, mentor management,
and global-admin API access.

## Read This In Order

1. `app/main.py` for application startup and router registration.
2. `app/models.py` for database tables.
3. `app/schemas.py` for request and response contracts.
4. `app/routes/README.md` before changing endpoints.
5. `app/services/README.md` before changing analysis, audit, or LiveKit helpers.
6. `tests/test_api.py` before changing auth, team, session, or summary behavior.

## Rules

- Treat this backend as synchronous today. Do not assume async DB access or background jobs.
- Keep HTTP concerns in `app/routes/`.
- Keep filesystem writes, model calls, summary refresh, and audit persistence in `app/services/`.
- Keep API contract changes mirrored in `frontend/lib/api.ts`.
- Keep `/api/research-groups` and `/api/mentor` as the primary business APIs; old `/api/teams` and selected `/api/admin` group-management paths are compatibility aliases only.
- Preserve the MVP boundary: screenshots, vision results, and summaries are stored, not full recordings.
