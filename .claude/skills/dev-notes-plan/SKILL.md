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
- **One line per row.** The tables are the queue and must stay readable; a row is a
  pointer, not a document. A description that needs more than ~1 line goes in an
  `### P2-26` section under **Item details** at the bottom, and the row links to it as
  `[→ detail](#p2-26)`. Heading = the bare ID, so the anchor resolves and
  `grep -n '### P2-26'` lands on it.
- **Never put a completion report in a row.** How it went — commits, measurements,
  corrections, what it spawned — belongs in the shipping plan's **Outcome** section and
  the session log. The row gets `done YYYY-MM-DD` plus links. This is the rule that had
  to be applied retroactively on 2026-07-27, when single cells had reached 2 800
  characters and the file cost ~15k tokens to read.

## Closing a plan

When the work ships: set `status: done`, fill the **Outcome** section (deviations,
follow-ups spawned), mark linked backlog items/findings, and write a session log
(`dev-notes/sessions/`).

The plan's **Outcome** section is where the shipping narrative lives — measurements,
deviations, claims that turned out wrong. Do not duplicate it into the backlog row; the
row links here.
