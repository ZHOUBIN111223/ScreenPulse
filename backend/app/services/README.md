# Service Layer

This directory contains helpers that perform side effects for the backend.

## Modules

- `analysis.py`: save/delete uploaded screenshots, call the multimodal model, and refresh hourly summaries.
- `audit.py`: persist team-scoped audit log entries for key actions.
- `livekit.py`: create LiveKit access tokens when the optional integration is configured.

## Rules

- Services may depend on config, models, and the database session passed in from routes.
- Services must not import route modules.
- Keep side effects explicit: filesystem writes, outbound model calls, summary refreshes, and audit writes should be visible in the function body.
- Raise normal Python errors from this layer and translate them into HTTP behavior in routes when needed.
