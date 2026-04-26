# Frontend Components

This directory contains client-side UI behavior.

## Modules

- `login-form.tsx`: login, registration, token restore, and redirect into the team workspace.
- `team-workspace.tsx`: team selection, invite generation, team settings, member review, screen-share controls, and summary views.
- `admin-panel.tsx`: admin-only console for team status, summaries, settings, invite codes, audit logs, frame history, data deletion, and member management.

## Rules

- Keep `"use client"` as the first line in client components.
- Use `frontend/lib/api.ts` for backend calls instead of ad hoc `fetch` logic.
- Keep browser-specific APIs such as `getDisplayMedia` inside the component layer.
- If a component becomes hard to read, split it by behavior, not by arbitrary styling fragments.
