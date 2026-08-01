---
name: dev-notes
description: Retrieve and maintain engineering knowledge in dev-notes. Use when work references a backlog or feature ID, needs repository architecture or decision context, changes a documented plan or finding, discovers durable system knowledge, or closes meaningful work.
---

# Dev-notes workflow

Treat `dev-notes/` as the repository knowledge base. Keep retrieval bounded and verify dated
claims against current code.

## Retrieve context

1. For an ID such as `P2-43` or `F2-08`, run
   `python3 .agents/skills/dev-notes/scripts/context.py --id P2-43`.
2. Otherwise use `--area account-service` or `--path services/account-service`.
3. Read only returned files relevant to the task: current status, the exact work item and its
   linked finding/plan/decision, then the owning architecture or pattern note.
4. Do not read the complete backlog or vault when a scoped excerpt is available. Use `rg -n`
   only when bounded output is insufficient.
5. Keep initial context to roughly three to five relevant files; expand only for a material
   link or contradiction.

## Maintain knowledge

- Use `dev-notes/templates/`; name dated files `YYYY-MM-DD-short-slug.md`.
- Add each non-session note to `00-INDEX.md` with one physical line and a short routing hook.
  Add sessions only to `sessions/00-SESSIONS.md`.
- Put related IDs in `backlog:` frontmatter on findings, plans and decisions.
- Never delete findings or decisions. Mark them resolved/superseded and link the replacement.
- Put deferred problems in a finding plus backlog item; do not bury them in a session.
- Put the final shipping narrative in the plan's `Outcome`. Write a session only for resumable
  state, cross-item discoveries or open ends not captured there.
- Keep `STATUS.md` to active work, recent work, next candidates, blockers and a small set of
  standing traps.
- Run `make notes-check` after any note or repository-skill change.

Repository facts belong in `dev-notes/`; durable conventions in `AGENTS.md`. Link to a
canonical fact instead of duplicating it. Use `dev-notes-plan` for implementation plans and
`dev-notes-decision` for non-obvious choices.
