# AI Workflow

This file tells future agents how to navigate this repo without loading the
entire codebase at once.

## Goals

- Search narrowly before reading deeply.
- Read anchor files in a fixed order.
- Keep anchor docs synchronized with real code changes.
- Split doc maintenance into a parallel sidecar only when scopes do not overlap.

## Read Order

Read only as far as needed.

1. `AGENTS.md`
   Primary project rules and change discipline.
2. `PROJECT_MAP.md`
   Global architecture, entry points, dependency direction, and change checklist.
3. Nearest module `README.md`
   Local directory rules and responsibility boundaries.
4. Target file top-level docstring or opening comment
   File purpose, inputs, outputs, and boundary.
5. Contract files before implementation changes
   - Backend API shape: `backend/app/schemas.py`
   - Backend persistence shape: `backend/app/models.py`
   - Frontend API contract: `frontend/lib/api.ts`
6. Relevant tests before edits that may change behavior
   - Read `backend/tests/test_api.py` before auth, session, or admin changes.

Do not read the whole repo by default. Pull the next layer only after the
current layer identifies the likely change area.

## Search Workflow

Prefer fast, narrow searches over broad file dumps.

1. Find the likely entry point from `PROJECT_MAP.md`.
2. Use `rg` to locate symbols, routes, types, or filenames.
3. Read the nearest module `README.md`.
4. Read only the files on the direct call path.
5. Read tests and contract files before editing behavior.

Suggested commands:

```powershell
rg --files
rg "symbol_name" backend frontend
rg "route_or_payload_name" backend/app frontend/lib
```

PowerShell fallback if `rg` is unavailable:

```powershell
Get-ChildItem -Recurse | Select-String -Pattern "symbol_name"
```

## Update Rules For Documentation Anchors

Update docs only when the code change makes them stale. Do not rewrite anchors
for unrelated cleanup.

Update `PROJECT_MAP.md` when:

- A top-level entry point is added, removed, or renamed.
- Dependency direction changes.
- Main data flow changes.
- Product boundary changes.

Update the nearest module `README.md` when:

- A directory gains or loses responsibility.
- Logic moves between sibling areas.
- A local rule changes.

Update a file's top-level docstring or opening comment when:

- The file's primary responsibility changes.
- The file becomes an entry point.
- The file stops being an entry point.

## Parallel Doc-Sync Pattern

Use doc-sync as a separate sidecar task when the work can proceed on disjoint
files.
This keeps the main agent focused on the critical code path instead of carrying
all documentation updates in active context.

Main agent owns:

- Code changes
- Tests and verification
- Final integration decisions

Doc-sync sidecar owns:

- `PROJECT_MAP.md`
- Module `README.md` files
- File top-level docstrings or opening comments
- Short change summaries if requested

Parallelize doc-sync only if these conditions hold:

- The code-editing agent and doc agent are not editing the same file.
- The implementation shape is stable enough to document.
- The main agent remains the owner of final factual correctness.

Recommended sequence:

1. Main agent identifies the intended code change and affected areas.
2. Main agent assigns doc-sync as a parallel sidecar with a narrow file list.
3. Doc agent updates anchors only for confirmed changes.
4. Main agent re-checks anchor accuracy before finishing.

If the implementation is still moving, delay doc-sync until the code path is
stable. Incorrect anchor docs are worse than missing updates.

## Concurrent Change Rules

You are not alone in this repo.

- Do not revert or overwrite unrelated edits from other agents.
- Assume the worktree may be dirty.
- Restrict your write scope to the files you own for the task.
- If another agent changed an anchor file you planned to edit, re-read it before
  writing.
- Prefer additive, factual updates over broad rewrites.
- If code and docs conflict during concurrent work, trust the current code only
  after verifying the implementation path.

## Minimal Execution Checklist

1. Read `AGENTS.md` and `PROJECT_MAP.md`.
2. Search narrowly with `rg`.
3. Read the nearest module `README.md`.
4. Read the target file and relevant contracts.
5. Read tests before behavior changes.
6. Make the smallest change that satisfies the task.
7. Update only the anchors made stale by your change.
8. If useful, split doc-sync into a parallel sidecar on disjoint files.
