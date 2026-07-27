---
name: dev-notes
description: Read and maintain the dev-notes/ knowledge base (architecture docs, findings, backlog, plans, decisions, session logs). Use BEFORE planning or implementing any non-trivial change (to load context), and AFTER completing work (to record what changed). Triggers - "check the notes", "what do we know about X", starting a feature/refactor, finishing a session, resolving a finding or backlog item.
---

# dev-notes knowledge base

`dev-notes/` is the engineering knowledge base for this repo (an Obsidian vault of plain
Markdown). It holds what the code cannot tell you: audit findings, plans, backlog,
decisions and their reasons.

## Reading (do this BEFORE planning/implementing)

**If you have an ID, grep first.** Backlog/feature IDs (`P1-15`, `F2-03`) are the primary
key of this vault, and every document that touches an item carries the ID — in a
`backlog:` frontmatter field, a row, a heading, or prose:

```
grep -rn "P1-15" dev-notes/          # the whole story: item, finding, plan, decision, session
grep -n "### P1-15" dev-notes/backlog/BACKLOG.md   # the item's own detail section
```

That is cheaper and more complete than reading index files, so do it before anything else.

**Otherwise work outside-in — do not load everything.**

1. `dev-notes/STATUS.md` — where the work currently stands (2 minutes old, ~20 lines).
2. `dev-notes/00-INDEX.md` — one clause per document. Its job is to help you *choose*;
   open only the files whose hook matched. Session logs are indexed separately in
   `sessions/00-SESSIONS.md` and are not part of loading context.
3. Then, scoped to what you are actually touching:
   - `architecture/overview.md` + the per-service file for the services in scope
   - `findings/` — grep the area (`grep -rln "budget" dev-notes/findings/`) for open
     findings; you may be about to fix — or worsen — one
   - `backlog/BACKLOG.md` — read the **tables**; the work may already be an item
   - `decisions/` + `docs/adr/` — do not re-litigate settled decisions; if you must
     deviate, write a new decision that supersedes the old one

Reading all of the above unconditionally costs ~10k tokens before a line of code, most of
it about services you are not touching. Scope it.

4. Treat notes as *claims with a date* — verify against current code before relying on
   details (file paths, line numbers drift).

## Writing (do this AFTER meaningful work)

- **Rules that always apply**
  - Add one line to `00-INDEX.md` for every new file: `- [Title](path.md) — hook`
    (session logs go in `sessions/00-SESSIONS.md` instead). Keep it to one clause.
  - Run `make notes-check` — it fails on a missing index line, a dead link, bad
    frontmatter, or a `resolved` finding with no `resolved-by`. The pre-commit hook runs
    it whenever a note is staged.
  - Put the backlog/feature ID in `backlog:` frontmatter on findings, plans and decisions.
    It is how the work is retrieved later; a document without it is invisible to
    `grep -rn P1-15 dev-notes/`.
  - Use templates from `dev-notes/templates/` (plan.md, decision.md, finding.md, session.md).
  - Dated files are named `YYYY-MM-DD-short-slug.md`. Never invent dates — use today's.
  - Never delete findings/decisions; set `status: resolved | superseded` with a link to
    what resolved/replaced them.
  - Danish or English per document, not mixed inside one; English preferred for
    `architecture/` and `patterns/`. Keep frontmatter fields intact — they are queried.

- **What goes where**
  - Fixed a finding → set its `status: resolved`, fill `resolved-by`, update backlog item.
  - Architecture changed (new service/event/flow, removed component) → update
    `architecture/overview.md` and the owning `architecture/services/<svc>.md`. There is no
    central event catalog — each event is documented in the service that *publishes* it.
  - Discovered a problem you are not fixing now → new finding in `findings/` + backlog item.
  - Made a non-obvious choice → decision in `decisions/` (promote to `docs/adr/NNNN-slug.md`
    only for long-term structural decisions; follow the `docs/adr/0001…` numbering scheme).
  - End of a significant session → session log in `sessions/` (done / learned / open ends),
    with its line added to `sessions/00-SESSIONS.md`.
  - Updated `STATUS.md`? Do it when the active plan changes, an item is finished, or a
    session ends — it is the first thing read next time.

## dev-notes vs. agent memory

Both stores are written after work, and putting a fact in the wrong one means either
nobody finds it or two copies drift apart. The split:

| | goes in `dev-notes/` | goes in agent memory |
|---|---|---|
| **What** | facts about *this system* | transferable lessons about *how to work* |
| **Examples** | "budget-service reads spend from analytics"; a finding; an ADR | "never pipe a verification command through `tail`"; "these two services can only be tested in CI" |
| **Shape** | dated, status-tracked, linked by ID | one fact + **Why** + **How to apply** |
| **Test** | would a new developer reading the repo need it? | would I repeat the mistake without it? |

Rules for keeping them from drifting:

- **Do not restate a fix in both.** A memory that duplicates a finding's measurements has
  to be updated twice and will eventually contradict it. The memory should carry the
  *lesson* and point at the finding for the numbers.
- The generalisable half of a finding often belongs in memory even when the finding is
  `resolved` — the fix closes the finding, not the class of mistake.
- Repo conventions belong in `CLAUDE.md`, not memory: memory is per-user, `CLAUDE.md` is
  checked in and applies to anyone working here.

## Related skills

- `dev-notes-plan` — creating implementation plans and backlog items
- `dev-notes-decision` — recording decisions

## Quality bar

A note is useful only if a future agent with zero context can act on it: include file
paths, concrete symptoms, and the *why* — not just the *what*.
