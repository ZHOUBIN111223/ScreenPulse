# Backend App Layer

This package contains the executable backend application and its core layers.

## Files

- `config.py`: environment-backed settings and derived paths.
- `database.py`: SQLAlchemy engine, session factory, and request-scoped DB dependency.
- `models.py`: SQLAlchemy persistence models.
- `schemas.py`: Pydantic request and response schemas.
- `dependencies.py`: auth and role guards for FastAPI dependencies.
- `security.py`: password hashing and JWT helpers.
- `routes/`: HTTP entrypoints.
- `services/`: side-effecting domain helpers.

## Rules

- `models.py` is the persistence source of truth.
- `schemas.py` is the HTTP contract source of truth.
- `routes/` may call `services/`, but `services/` must not import `routes/`.
- Keep cross-layer behavior explicit; avoid hidden imports or dynamic dispatch.
