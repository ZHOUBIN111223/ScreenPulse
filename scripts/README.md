# Scripts Map

This directory owns the local development startup helpers for ScreenPulse.

## Files

- `start-dev.ps1`
  - Starts the backend on `127.0.0.1:8011` and the frontend on `127.0.0.1:3001`.
  - Writes logs and tracked process metadata into `.codex-run/`.
- `stop-dev.ps1`
  - Stops the tracked dev processes recorded by `start-dev.ps1`.
- `init-server-env.sh`
  - Creates a server `.env` for Docker deployment if one does not already exist.
  - Defaults public browser-facing URLs to `47.104.158.30` and generates a runtime secret.

## Local State

- `.codex-run/dev-state.json`
  - Saved runtime state for the current machine, including ports, PIDs, and log paths.
- `.codex-run/*.log`
  - Backend and frontend startup logs for the current run.
