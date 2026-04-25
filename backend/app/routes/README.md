# Route Layer

This directory contains FastAPI route modules for auth, team management,
invite-code joins, team-scoped screen sessions, and summary reporting.

## Modules

- `auth.py`: registration, login, current-user, and logout endpoints.
- `teams.py`: teams, members, invite codes, team settings, and summary endpoints.
- `sessions.py`: team-scoped session lifecycle, frame uploads, and LiveKit token endpoints.

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
