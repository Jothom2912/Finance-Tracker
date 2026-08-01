---
name: dev-notes-plan
description: Create, update or close an implementation plan and its backlog linkage in dev-notes. Use for multi-step features, refactors, migrations, cross-service changes, explicit planning requests, queued work needing execution detail, or closing an implemented plan. Do not use for a trivial single-file change with no design choice.
---

# Planning workflow

1. Load context with `dev-notes`; search the ID and likely duplicate plans/items first.
2. Create a plan only for genuinely multi-step, cross-service, risky or design-bearing work.
3. Copy `dev-notes/templates/plan.md` to a file named with today's actual date.
4. Fill every section. Link existing context instead of retelling architecture; name preserved
   behavior in Non-goals; name files and diff shape in Steps; give exact verification commands
   and negative controls; describe detection and rollback in Risks.
5. Put related IDs in `backlog:` frontmatter. Link plan and work item both ways, add one short
   index line, and update `STATUS.md` when active work changes.
6. Wait for approval before implementing when `AGENTS.md` requires it.

Keep backlog rows to one physical line. Rows route to work; long context belongs in an item
detail or finding, while completion measurements and deviations belong only in plan Outcome.

To close a plan, set `status: done`, check completed steps, fill Outcome, update linked
findings/items and `STATUS.md`, then run `make notes-check`. Write a session only when resumable
or cross-item context remains outside Outcome.
