---
name: dev-notes-decision
description: Record an architectural or implementation decision in dev-notes/decisions/ (and optionally promote to a formal ADR in docs/adr/). Use whenever a non-obvious choice is made - technology selection, pattern choice, trade-off accepted, something deliberately NOT done - so future agents do not re-litigate or accidentally reverse it.
---

# Decision logging

## When to log

Log a decision when a choice (a) was between real alternatives, (b) will be invisible in
the code six months from now, or (c) deliberately accepts a known cost. "We chose the
boring option" is still a decision worth one paragraph.

## How

1. Check `dev-notes/decisions/` and `docs/adr/` first — if the decision already exists,
   update/supersede it rather than duplicating.
2. Copy `dev-notes/templates/decision.md` → `dev-notes/decisions/YYYY-MM-DD-<slug>.md`.
   The **Alternatives considered** and **Consequences** sections are the valuable parts —
   don't skip them.
3. Add a line to `dev-notes/00-INDEX.md`.
4. Superseding: set the old file's `status: superseded` and point `supersedes:` from the
   new one. Never edit history to look consistent.

## Promotion to formal ADR

Promote to `docs/adr/` only for decisions that shape the system long-term (service
boundaries, data ownership, protocol choices). Rules:

- Follow the existing `docs/adr/NNNN-slug.md` scheme (next free number; zero-padded).
- Do NOT create `docs/ADR-NNN-*.md` files at the docs root — that legacy second scheme is
  deprecated (see finding on ADR numbering in `dev-notes/findings/`).
- Record the promotion in the dev-notes decision file (`promoted-to-adr:` field).
