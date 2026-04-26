# Route Layer

This directory contains FastAPI route modules for auth, current-team user flows,
global-admin management, current-team screen sessions, audit logs, and summary reporting.

## Modules

- `auth.py`: registration, login, current-user, and logout endpoints.
- `teams.py`: user-facing team creation, listing, invite-code joins, and current-team selection.
- `sessions.py`: current-team session lifecycle, screenshot uploads, current settings, and member summary endpoints.
- `admin.py`: global-admin users, teams, sessions, summaries, settings, members, invite codes, audit logs, and frame history.

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
