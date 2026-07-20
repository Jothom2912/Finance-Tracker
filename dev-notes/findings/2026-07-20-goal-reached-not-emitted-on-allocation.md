---
id: F-2026-07-20-goal-reached-allocation
title: "Surplus allocation completing a goal emits no event → no goal-reached notification on the auto path"
date: 2026-07-20
severity: MEDIUM
status: open
area: goal-service, notification-service
discovered-by: F1-01 e2e prep
---

# Goal-reached notification does not fire on the automatic surplus→goal path

## Symptom / gap

F1-01's notification consumer produces a "Mål nået! 🎉" notification from
`goal.updated` events where `current_amount >= target_amount`. That works for
**manual** goal edits (verified live 2026-07-20). But the flagship ADR-0003
flow — month-close surplus auto-allocated to the default goal — can complete a
goal **without emitting any `goal.updated` event**, so no notification fires on
the path that matters most.

## Root cause

goal-service has two write paths:

- **CRUD update** (`GoalService.update_goal`, `service.py`) — emits
  `GoalUpdatedEvent` via the outbox. ✅ observable.
- **Allocation** (`BudgetMonthClosedHandler` + `IBudgetMonthClosedUnitOfWork`)
  — calls `increment_current_amount` directly. Its UoW
  (`SQLAlchemyBudgetMonthClosedUnitOfWork`) has **no outbox**, so incrementing a
  goal to/over its target emits nothing. ❌ silent.

Also note `GoalUpdatedEvent.status` carries the *stored* status (active/paused),
never `"completed"` — completion is a computed property (`effective_status`).
That's why the notification consumer detects reached by amount, not by status
(see [decisions/2026-07-17-manual-month-close-button](../decisions/2026-07-17-manual-month-close-button.md)
context and goal-service `domain/entities.py`).

## Impact

The automatic "your surplus became savings and hit your goal" moment — the exact
story F1-04/05/07 automated — produces no notification. Only manual goal edits
that cross the target notify. MEDIUM: feature-incomplete, not incorrect.

## Fix options (follow-up, not done here)

1. **Preferred**: emit an event from the allocation path when an allocation
   makes `current_amount >= target_amount` — either a `GoalUpdatedEvent` (add
   outbox to the month-closed UoW) or a dedicated `goal.reached` event. The
   notification consumer already dedupes on `goal.reached:{goal_id}`, so a
   `goal.reached` event would map 1:1.
2. Have the allocation handler flip the stored status to `completed` and emit
   `goal.updated` — but that overloads stored status with computed state
   (against the computed-property convention). Not preferred.

Tracked as backlog item **F1-08**.
