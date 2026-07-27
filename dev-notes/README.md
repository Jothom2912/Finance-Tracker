# dev-notes — Knowledge Base

This folder is the **single source of truth for engineering knowledge that is not code**:
architecture understanding, audit findings, implementation plans, backlog, decisions, and
session notes. It is an Obsidian vault, but every file is plain Markdown and must stay
readable without Obsidian.

Both humans and AI agents read and write here. Agents: follow the `dev-notes` skill
(`.claude/skills/dev-notes/`) for the rules on reading and updating this vault.

## Structure

| Folder | Contents | When to write here |
|--------|----------|--------------------|
| `STATUS.md` | Where the work stands: active plan, next up, open findings, standing traps | When the active plan changes, an item finishes, or a session ends |
| `architecture/` | System overview, per-service breakdowns, data flows (events are documented in the publishing service, not centrally) | When the architecture *changes* or understanding deepens |
| `patterns/` | One file per recurring pattern: what, why, canonical implementation, gotchas | When a pattern is introduced, changes shape, or its gotchas grow |
| `findings/` | Audit findings: problems, risks, tech debt (severity-tagged) | After any audit/review; mark items `resolved` when fixed |
| `plans/` | Implementation plans for features/refactors (one file per plan) | Before starting non-trivial work |
| `backlog/` | Prioritized backlog (`BACKLOG.md`) | When work is identified but not scheduled |
| `decisions/` | Decision log (lightweight ADRs) | When an architectural/implementation decision is made |
| `sessions/` | Session logs: what was done, what surprised us, open ends | End of significant working sessions |
| `templates/` | Templates for all the above | — |

## Conventions

- **File naming**: `YYYY-MM-DD-short-slug.md` for dated items (plans, sessions, decisions);
  stable topic names for living documents (`architecture/overview.md`).
- **Status field**: every plan/backlog item/finding carries a status:
  `open | in-progress | done | resolved | superseded | wont-do`.
- **Never delete** a finding/decision — mark it `resolved`/`superseded` with a pointer to
  what replaced it. History is the point.
- **Update the index**: `00-INDEX.md` lists every document with a one-clause hook — enough
  to decide whether to open it, no more. Session logs are indexed in
  `sessions/00-SESSIONS.md` instead. `make notes-check` fails on a file that is in neither.
- **Retrieval is by ID**: backlog/feature IDs are this vault's primary key. Put the ID in
  `backlog:` frontmatter so `grep -rn P1-15 dev-notes/` returns the whole story — finding,
  item, plan, decision, session.
- **Formal ADRs** live in `docs/adr/` (repo docs, numbered `NNNN-slug.md`). `decisions/`
  here is the lightweight day-to-day log; promote a decision to `docs/adr/` when it shapes
  the system long-term. ⚠ There are still two ADR numbering schemes in `docs/`
  (`docs/adr/0001…` and `docs/ADR-002/003-*.md`); `docs/adr/NNNN-slug.md` is the surviving
  one — never add to the other. Recorded under repo hygiene in
  [findings/2026-07-07-architecture-audit.md](findings/2026-07-07-architecture-audit.md);
  there is no `MAINT-ADR-numbering` finding, despite what this line used to claim.
- **Language**: Danish or English, per document — write in whichever makes the reasoning
  clearest, and do not mix them inside one file. English is *preferred* for
  `architecture/` and `patterns/`, which are read as reference rather than narrative.
  (This rule used to say "English for durable docs, Danish only in session notes"; roughly
  40% of findings and plans are Danish, so it described an intention nobody followed.
  Corrected 2026-07-27 to describe practice — an unenforced convention is worse than none,
  because it makes every other rule here look optional.)
- **Cross-link** liberally: `[text](relative/path.md)` — keeps the graph navigable in
  Obsidian and in plain editors.

## Start here

- [00-INDEX.md](00-INDEX.md) — map of everything
- [architecture/overview.md](architecture/overview.md) — system architecture
- [findings/2026-07-07-architecture-audit.md](findings/2026-07-07-architecture-audit.md) — full codebase audit
- [backlog/BACKLOG.md](backlog/BACKLOG.md) — prioritized work queue
