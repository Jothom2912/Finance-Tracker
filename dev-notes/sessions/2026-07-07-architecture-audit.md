---
date: 2026-07-07
topic: Full-codebase architecture audit + knowledge base bootstrap
---

# Session 2026-07-07 — architecture audit & dev-notes bootstrap

## Done
- Reverse-engineered the whole system via 8 parallel deep-dive reviews (every service, frontend, infra/CI/k8s, cross-service duplication measured with md5/diff).
- Wrote the knowledge base: architecture overview + 8 per-area breakdowns, consolidated findings (10 CRITICAL / 27 HIGH / ~45 MEDIUM / ~40 LOW), prioritized backlog (P1/P2/P3), 4-phase refactoring roadmap.
- Set up dev-notes as a structured KB (README, index, templates) and three agent skills: `dev-notes`, `dev-notes-plan`, `dev-notes-decision` (in `.claude/skills/`).
- Added root `CLAUDE.md` pointing future agents at the KB and ground rules.
- **No production code was changed** — audit was read-only by design; fixes are staged as backlog items.

## Learned / surprised
- The architecture documentation (README) is accurate and honest — the debt is almost all *below* the pattern level: copy-paste infrastructure (outbox ×8, auth ×9), fail-open trust boundaries, and unbounded hot-path reads.
- Three separate CRITICAL IDOR/auth holes (monthly-budgets, bank disconnect/list, saga status) and one money-corruption bug (fail-open month close) exist today.
- Real personal transaction data is committed in `scripts/backups/`, and the production EB PEM key sits in the working tree.
- Frontend has no Redux despite docs; 3.5k lines of dead hexagonal Budget module.
- The categorization rules DB is entirely dead — hardcoded seed dict is the live rule source.

## Open ends
- Execute Phase 1 of [plans/2026-07-07-refactoring-roadmap.md](../plans/2026-07-07-refactoring-roadmap.md) (P1-01…P1-12) — each item small and testable; start with P1-01/P1-02 (money + IDOR in budget-service).
- P1-08 (secrets/PII purge) needs a user decision on git history rewrite (filter-repo) if the repo is ever shared.
- Consider committing dev-notes/ and .claude/skills/ (currently untracked).

## Notes updated
- Everything under dev-notes/ created this session (see 00-INDEX.md).
