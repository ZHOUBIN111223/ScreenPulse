## 5. ScreenPulse Project Rules

Read `PROJECT_MAP.md` before broad changes. Then read the nearest directory
`README.md`, then the target file itself.
Read `AI_WORKFLOW.md` for the detailed search and doc-maintenance procedure.

Current architecture facts:
- Backend is FastAPI with synchronous SQLAlchemy sessions over SQLite.
- Screenshot analysis uses `requests` against an OpenAI-compatible endpoint.
- Frontend uses Next.js App Router with thin route files and client components.
- `frontend/lib/api.ts` is the frontend contract layer for backend requests.

Project constraints:
- Do not invent a new async DB layer, queue system, or plugin architecture unless the task requires it.
- Preserve the current MVP boundary: store screenshots and summaries, not full recordings.
- Keep HTTP coordination in `backend/app/routes/`.
- Keep screenshot persistence, model calls, and summary refresh logic in `backend/app/services/`.
- Keep database shape in `backend/app/models.py` and HTTP shape in `backend/app/schemas.py`.
- Keep frontend pages thin and put browser behavior in `frontend/components/`.
- Keep `frontend/lib/api.ts` aligned with backend schema changes.
- Before changing auth, session, or admin behavior, read `backend/tests/test_api.py`.
- In client components, keep `"use client"` as the first line.

## 6. Search And Edit Workflow

When exploring or modifying code, follow this order instead of reading the repo blindly:

1. Read `PROJECT_MAP.md` for the global map and dependency direction.
2. Read the nearest module `README.md`.
3. Read the target file's top-level docstring or comment.
4. Read the relevant contract layer before implementation changes:
   - Backend HTTP contract: `backend/app/schemas.py`
   - Backend persistence shape: `backend/app/models.py`
   - Frontend API contract: `frontend/lib/api.ts`
5. Read `backend/tests/test_api.py` before changing auth, session, or admin behavior.

If a change touches multiple layers, trace the path in this order:
- Entry point
- Contract
- Service or component implementation
- Test

## 7. Anchor Maintenance Rules

These anchor files are part of the codebase and must stay synchronized with reality.

Update `PROJECT_MAP.md` when:
- A new top-level module or entry point is added.
- Dependency direction changes.
- The main data flow changes.
- The product boundary changes.

Update the nearest module `README.md` when:
- A directory gains a new responsibility.
- A module split or merge changes where logic lives.
- A local rule changes.

Update a file's top-level docstring or comment when:
- The file's primary responsibility changes.
- The file becomes an entry point or stops being one.

Do not rewrite anchor docs for unrelated refactors. Keep them short and factual.

## 8. Parallel Agent Pattern

For medium or large tasks, prefer this split:
- Main agent owns the code change, verification, and final integration.
- A parallel doc-sync agent owns only anchor files such as `PROJECT_MAP.md`, module `README.md`, and top-level docstrings.

Use a separate agent only when the write scope is disjoint.
Good parallel sidecar work:
- Updating `PROJECT_MAP.md`
- Updating module `README.md` files
- Drafting release notes or change summaries

Keep the main agent on the critical path.
Do not delegate the blocking implementation step if the next action depends on it.


Behavioral guidelines to reduce common LLM coding mistakes, derived from [Andrej Karpathy's observations](https://x.com/karpathy/status/2015883857489522876) on LLM coding pitfalls.

**Tradeoff:** These guidelines bias toward caution over speed. For trivial tasks, use judgment.

## 1. Think Before Coding

**Don't assume. Don't hide confusion. Surface tradeoffs.**

Before implementing:
- State your assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them - don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop. Name what's confusing. Ask.

## 2. Simplicity First

**Minimum code that solves the problem. Nothing speculative.**

- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- If you write 200 lines and it could be 50, rewrite it.

Ask yourself: "Would a senior engineer say this is overcomplicated?" If yes, simplify.

## 3. Surgical Changes

**Touch only what you must. Clean up only your own mess.**

When editing existing code:
- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- If you notice unrelated dead code, mention it - don't delete it.

When your changes create orphans:
- Remove imports/variables/functions that YOUR changes made unused.
- Don't remove pre-existing dead code unless asked.

The test: Every changed line should trace directly to the user's request.

## 4. Goal-Driven Execution

**Define success criteria. Loop until verified.**

Transform tasks into verifiable goals:
- "Add validation" → "Write tests for invalid inputs, then make them pass"
- "Fix the bug" → "Write a test that reproduces it, then make it pass"
- "Refactor X" → "Ensure tests pass before and after"

For multi-step tasks, state a brief plan:
```
1. [Step] → verify: [check]
2. [Step] → verify: [check]
3. [Step] → verify: [check]
```

Strong success criteria let you loop independently. Weak criteria ("make it work") require constant clarification.
