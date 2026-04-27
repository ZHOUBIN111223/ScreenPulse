# Route Layer

This directory contains FastAPI route modules for auth, current-research-group
user flows, mentor management, current-research-group screen sessions, daily
learning records, audit logs, and summary reporting.

## Modules

- `auth.py`: registration, login, current-user, and logout endpoints.
- `teams.py`: user-facing research-group creation, listing, invite-code joins, and current-group selection; legacy `/teams` aliases live here.
- `sessions.py`: current-research-group session lifecycle, screenshot uploads, current settings, and member summary endpoints.
- `learning.py`: current-research-group daily goals, daily reports, and mentor feedback.
- `admin.py`: global-admin users and broad listings plus mentor settings, members, invite codes, audit logs, frame history, and summaries; selected legacy `/admin` aliases remain for compatibility.

## Rules

- Route modules own HTTP request parsing, dependency injection, and response serialization.
- Reuse `dependencies.py` for authentication and team-membership checks.
- Reuse `schemas.py` for request and response shapes; do not invent inline payload contracts.
- Keep side effects such as file persistence, audit writes, and model calls in `app/services/`.
- Before changing endpoint behavior, read `backend/tests/test_api.py`.

## API Documentation Rules

Add FastAPI `/docs` annotations only to explain endpoint contracts; do not
change business logic while doing documentation-only work.

Each endpoint should briefly state:

- What the endpoint does.
- Who can call it.
- What state changes after a successful call.
- Query and path parameter meanings.
- Request body field meanings.
- Response field meanings.
- Common error code meanings.

Use these FastAPI and Pydantic hooks:

- Routes: `summary`, `description`, `tags`, and `responses`.
- Parameters: `Query/Path(..., description="...")`.
- Request and response bodies: `Field(..., description="...")`.

Keep descriptions short, accurate, and useful for frontend integration and
tests.
