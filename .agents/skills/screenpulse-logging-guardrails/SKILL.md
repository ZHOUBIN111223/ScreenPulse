---
name: screenpulse-logging-guardrails
description: Use when Codex adds or changes ScreenPulse logging, audit events, request IDs, trace/context propagation, sensitive-data redaction, screenshot lifecycle observability, team-isolation security logs, AI job logs, or replaces print/ad hoc logger usage. Applies to the FastAPI backend and any frontend API contract changes needed to expose request IDs.
---

# ScreenPulse Logging Guardrails

## Overview

Treat logging as a stable event language, not scattered print statements or a logging platform. Business code states what happened; the logging layer owns shape, context, redaction, and stdout output.

## Read Order

Follow the project workflow before edits:

1. Read `PROJECT_MAP.md`.
2. Read `AI_WORKFLOW.md` if the task changes multiple layers or anchors.
3. Read the nearest `README.md`.
4. Read the target file's opening docstring/comment.
5. For backend behavior, read `backend/app/models.py`, `backend/app/schemas.py`, and `backend/tests/test_api.py` when auth, session, team, admin, or summary behavior may change.

## Architecture Boundary

- Keep the backend synchronous FastAPI + SQLAlchemy architecture.
- Do not add async DB access, queues, a plugin system, Loki, Elasticsearch, ClickHouse, OpenTelemetry SDK, or cloud logging clients unless explicitly requested.
- Prefer a lightweight module such as `backend/app/observability/`; do not create `backend/app/logging/`, which conflicts conceptually with Python's `logging` module.
- Output application logs as structured JSON to stdout. Let Docker, collectors, or cloud infrastructure handle collection and storage.
- Keep HTTP coordination in `backend/app/routes/`.
- Keep screenshot persistence, model calls, summary refresh, and side effects in `backend/app/services/`.

## Existing Audit Table

ScreenPulse already has `backend/app/services/audit.py` and an `audit_logs` table for product-visible team activity.

- Do not delete or silently replace this table-backed helper.
- Distinguish product audit records from stdout security audit logs.
- Use the existing table only for events the app needs to show or query as business data, such as team creation, invite creation, settings changes, and session lifecycle.
- Use the new audit logger for platform/security observability, such as login failures, permission denial, cross-team access denial, screenshot delete failure, and sensitive lifecycle violations.

## Event Split

Separate normal business events from security audit events.

Business events go through `event_logger`:

```text
team.created
team.invite.created
team.invite.used
team.member.joined
screen.share.started
screen.share.stopped
screenshot.captured
screenshot.analyzed
screenshot.deleted
ai.vision.started
ai.vision.finished
ai.vision.failed
ai.summary.started
ai.summary.finished
ai.summary.failed
job.started
job.finished
job.failed
job.retried
```

Security audit events go through `audit_logger`:

```text
auth.login.success
auth.login.failed
auth.permission.denied
team.cross_access.denied
screenshot.delete_failed
screenshot.retention_violation
admin.capture_interval.changed
```

Define event names centrally as constants or enums. Do not invent one-off event strings inside routes or services.

## Stable Fields

Emit a consistent JSON shape:

```text
timestamp
level
event
service
env
request_id
trace_id
user_id
team_id
resource_type
resource_id
result
reason
duration_ms
metadata
```

Use only stable result values such as `success`, `failed`, `denied`, and `skipped`. For failures, prefer stable `reason` values such as `team_mismatch`, `model_timeout`, `delete_failed`, or `invalid_credentials`.

## Semantic API

Do not scatter raw `logger.info(..., extra={...})` calls through business code. Prefer semantic wrappers:

```python
audit_logger.permission_denied(...)
audit_logger.cross_team_access_denied(...)
event_logger.screen_share_started(...)
event_logger.screenshot_deleted(...)
event_logger.ai_vision_failed(...)
```

Wrappers should fill event names, standard fields, redaction, and output formatting. Business code should pass only event-specific values.

## Context

Add automatic context when implementing the logging foundation:

- Use request middleware to create or validate `X-Request-ID`.
- Return `X-Request-ID` on every response.
- Use `contextvars` for `request_id`, `trace_id`, `user_id`, and `team_id`.
- Inject `user_id` and `team_id` from auth/team dependencies when available; avoid making every route manually pass repeated context.
- Do not log request or response bodies.

## Redaction

Centralize recursive redaction for dict/list metadata. Never log:

```text
password
token
cookie
authorization
session raw value
invite code raw value
screenshot content
screenshot base64
raw image path
OCR full text
model full input
model full output
complete email
complete phone number
```

Prefer IDs or hashes:

```text
user_id
team_id
invite_code_hash
email_hash
screenshot_id
model_name
model_version
duration_ms
```

ScreenPulse handles screenshots. Treat image bytes, base64, raw frame paths, OCR dumps, and full model prompts/responses as sensitive by default.

## Critical Coverage

When adding or changing related functionality, preserve auditability for:

- Screenshot lifecycle: `screenshot.captured`, `screenshot.analyzed`, `screenshot.deleted`, `screenshot.delete_failed`, `screenshot.retention_violation`.
- Team isolation: `team.cross_access.denied` with `user_id`, `user_team_id`, `target_team_id`, `resource_type`, `resource_id`, `result="denied"`, and `reason="team_mismatch"`.
- AI work: started, finished, failed, timeout/retry count, empty output, consistency failure if implemented.
- HTTP requests: optionally emit `http.request.finished` with method, path, status code, duration, request_id, user_id, and team_id, but never bodies or sensitive headers.

## Verification

For logging infrastructure changes, add focused tests where practical:

- JSON formatter emits valid JSON with stable fields.
- request middleware generates and returns `X-Request-ID`.
- redaction removes sensitive keys, including nested `metadata`.
- audit/event wrappers emit the expected event and result values.
- screenshot, auth, team isolation, and AI failure paths do not log screenshot bytes, base64, authorization, cookies, raw invite codes, or full model payloads.

Run backend tests for touched behavior. If frontend request-id exposure changes API behavior, update `frontend/lib/api.ts` and verify the frontend build if feasible.
