# Frontend API Contract Layer

This directory contains shared frontend helpers.

## Files

- `api.ts`: frontend-side request wrappers and TypeScript types that mirror backend contracts.

## Rules

- Treat `api.ts` as the single source of truth for frontend-backend request shapes.
- When backend schemas change, update this file in the same change.
- Components should import helpers from here instead of duplicating request code.
