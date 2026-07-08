---
name: dev-notes
description: Read and maintain the dev-notes/ knowledge base (architecture docs, findings, backlog, plans, decisions, session logs). Use BEFORE planning or implementing any non-trivial change (to load context), and AFTER completing work (to record what changed). Triggers - "check the notes", "what do we know about X", starting a feature/refactor, finishing a session, resolving a finding or backlog item.
---

# dev-notes knowledge base

`dev-notes/` is the engineering knowledge base for this repo (an Obsidian vault of plain
Markdown). It holds what the code cannot tell you: audit findings, plans, backlog,
decisions and their reasons.

## Reading (do this BEFORE planning/implementing)

1. Read `dev-notes/00-INDEX.md` — one line per document; pick what is relevant.
2. For any change, always check:
   - `architecture/overview.md` + the per-service file for services you will touch
   - `findings/` for open findings in that area (you may be about to fix — or worsen — one)
   - `backlog/BACKLOG.md` — the work may already be a backlog item with context
   - `decisions/` + `docs/adr/` — do not re-litigate settled decisions; if you must
     deviate, write a new decision that supersedes the old one.
3. Treat notes as *claims with a date* — verify against current code before relying on
   details (file paths, line numbers drift).

## Writing (do this AFTER meaningful work)

- **Rules that always apply**
  - Add one line to `00-INDEX.md` for every new file: `- [Title](path.md) — hook`.
  - Use templates from `dev-notes/templates/` (plan.md, decision.md, finding.md, session.md).
  - Dated files are named `YYYY-MM-DD-short-slug.md`. Never invent dates — use today's.
  - Never delete findings/decisions; set `status: resolved | superseded` with a link to
    what resolved/replaced them.
  - English for durable docs; keep frontmatter fields intact (they are queried).

- **What goes where**
  - Fixed a finding → set its `status: resolved`, fill `resolved-by`, update backlog item.
  - Architecture changed (new service/event/flow, removed component) → update
    `architecture/overview.md` / `architecture/services/<svc>.md` / `architecture/event-catalog.md`.
  - Discovered a problem you are not fixing now → new finding in `findings/` + backlog item.
  - Made a non-obvious choice → decision in `decisions/` (promote to `docs/adr/NNNN-slug.md`
    only for long-term structural decisions; follow the `docs/adr/0001…` numbering scheme).
  - End of a significant session → session log in `sessions/` (done / learned / open ends).

## Related skills

- `dev-notes-plan` — creating implementation plans and backlog items
- `dev-notes-decision` — recording decisions

## Quality bar

A note is useful only if a future agent with zero context can act on it: include file
paths, concrete symptoms, and the *why* — not just the *what*.
