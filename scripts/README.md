# Scripts Map

This directory owns the local development startup helpers for ScreenPulse.

## Files

- `start-dev.ps1`
  - Starts the backend on `127.0.0.1:8011` and the frontend on `127.0.0.1:3001`.
  - Writes logs and tracked process metadata into `.codex-run/`.
- `frontend/package.json`
  - Provides `dev:admin` and `start:admin` scripts for running the Next.js admin console on port `3011` with an isolated `.next-admin` build directory.
- `stop-dev.ps1`
  - Stops the tracked backend, frontend, and admin frontend dev processes recorded in `.codex-run/dev-state.json`.
- `init-server-env.sh`
  - Creates a server `.env` for Docker deployment, or refreshes browser-facing
    URL and CORS entries in an existing one.
  - Defaults public browser-facing URLs to `47.104.158.30` and generates a runtime secret for new env files.

## Local State

- `.codex-run/dev-state.json`
  - Saved runtime state for the current machine, including ports, PIDs, and log paths.
- `.codex-run/*.log`
  - Backend and frontend startup logs for the current run.
