---
name: dev-notes-plan
description: Create or update an implementation plan and backlog items in dev-notes/. Use when starting non-trivial work (feature, refactor, migration), when the user asks to "plan" something, or when new work is identified that should be queued rather than done now. Also use to close out a plan when the work ships.
---

# Planning workflow

## Before writing a plan

1. Load context per the `dev-notes` skill: `00-INDEX.md`, relevant `architecture/` docs,
   open `findings/`, `backlog/BACKLOG.md`, `decisions/`.
2. Check whether a plan or backlog item for this work already exists — update it instead
   of creating a duplicate.

## Creating a plan

1. Copy `dev-notes/templates/plan.md` → `dev-notes/plans/YYYY-MM-DD-<slug>.md`.
2. Fill every section. Non-negotiables:
   - **Non-goals** must state what functionality/behavior is preserved.
   - **Steps** name the files to touch and the expected diff shape.
   - **Verification** names the exact commands/flows that prove it works
     (service tests via `make -C services/<svc> test`, e2e via `make test-e2e`).
3. Link the plan to the findings/backlog items it addresses (and vice versa).
4. Add the plan to `00-INDEX.md`.

## Backlog items

Two backlog files, same conventions:
- `backlog/BACKLOG.md` — technical work (debt, fixes, refactors); IDs `P1/P2/P3-xx`.
- `backlog/FEATURES.md` — product features & improvements; IDs `F1/F2/F3-xx`; each item records *Builds on* (existing scaffolding) and *Needs first* (technical prerequisites from BACKLOG.md).

`backlog/BACKLOG.md` format:

- Priorities: **P1** (critical/blocking), **P2** (important), **P3** (nice-to-have).
- Item format: `ID | title | area | effort (S/M/L) | status | links`.
- IDs are stable and sequential within priority (`P1-01`, `P2-07`, …) — never renumber.
- Move items between priority sections rather than editing IDs; status field tracks
  `open | in-progress | done | wont-do`.

## Closing a plan

When the work ships: set `status: done`, fill the **Outcome** section (deviations,
follow-ups spawned), mark linked backlog items/findings, and write a session log
(`dev-notes/sessions/`).
