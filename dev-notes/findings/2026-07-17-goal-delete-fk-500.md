---
id: F-2026-07-17-01
date: 2026-07-17
severity: LOW
area: goal-service
status: resolved
resolved-by: P3-16 soft-delete, commit 5cd613e5 (2026-07-17) — see [plans/2026-07-17-p316-goal-soft-delete.md](../plans/2026-07-17-p316-goal-soft-delete.md)
---

# Deleting a goal with allocation history returns 500 (FK violation)

**Symptom:** `DELETE /api/v1/goals/{id}` on a goal that has `goal_allocation_history`
rows → 500. Observed live during the F1-04 e2e (2026-07-17): deleting the synthetic
default goal failed until its history row was removed manually.

**Cause:** goals are hard-deleted (`AsyncPostgresGoalRepository.delete` →
`session.delete`), but `goal_allocation_history.goal_id` has a plain FK to
`goals.idGoal` with no ON DELETE behavior and no application-level guard, so Postgres
rejects the delete and the unhandled `IntegrityError` bubbles as 500.

**Considerations for the fix (own change, not done now):**
- CLAUDE.md prefers soft-delete on domain entities; goals predate that rule. Soft-delete
  would also preserve the audit trail (the history documents where money went).
- Alternatives: map to 409 "mål med opsparingshistorik kan ikke slettes" (cheap,
  honest), or cascade-delete history (loses audit trail — probably wrong).
- Whatever the choice: the default-flag must be cleared/ignored for deleted goals so
  the allocation consumer never allocates to a dead goal.

**Not fixed now because:** F1-04's scope was making the existing flow reachable;
delete-semantics for goals with money history is a domain decision (soft-delete
migration) that deserves its own small plan. Tracked as backlog P3-16.
