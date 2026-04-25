# App Router Layer

This directory contains thin Next.js route entries.

## Rules

- Prefer simple route wrappers that render shared components.
- Keep significant UI behavior out of route files and in `frontend/components/`.
- Keep `"use client"` directives only in files that actually need browser APIs or hooks.
