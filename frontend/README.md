# Frontend Map

This directory contains the Next.js UI for login, registration, current-team selection,
current-team screen sharing, the dedicated global-admin console, and summary review.

## Read This In Order

1. `app/README.md` for route entry conventions.
2. `components/README.md` for client-side UI behavior.
3. `lib/README.md` for API contract rules.

## Rules

- Keep route files in `app/` thin.
- Keep browser APIs and interactive logic in `components/`.
- Keep backend request logic and shared response types in `lib/api.ts`.
- When backend payloads change, update `lib/api.ts` in the same change.
- Keep user-facing copy in simplified Chinese unless the file is already using another language.
