---
date: 2026-07-17
topic: F1-04 — manual close-month button in UI; scheduled day-7 close deferred to backlog
status: active
---

# F1-04: manual "Luk måned" button supersedes ADR-0003's out-of-scope line

**Context.** ADR-0003 (2026-05-01) listed "Manual 'close month' button" as out of scope
and planned a scheduled day-7 close job as the v1 trigger. Reality inverted: the day-7
job was never built (the monolith that was to host it is gone; budget-service has no
scheduler), while `POST /api/v1/monthly-budgets/close` exists, is JWT-authenticated,
fail-closed (P1-01) and 409-guarded against re-close. Until F1-04, *nothing* could
trigger a close except a hand-crafted API call — the flagship surplus→goal flow was
undemoable.

## Decision

1. **Build the button** (BudgetPage, wave 3): pure UI over the existing endpoint, no new
   backend trigger surface. ConfirmDialog carries ADR-0003's day-7 rationale ("bank-
   transaktioner kan være 1-3 dage forsinkede") so the user closes deliberately.
   Danish error mapping: 409 "allerede lukket", 503 "måneden er IKKE lukket, prøv igen".
2. **Scheduled day-7 close stays deferred** — recorded as feature-backlog item F1-07,
   naturally paired with F1-05's scheduler work (same infra decision: worker loop vs
   KEDA cron). When it lands, the button remains as manual override.
3. **`closed_at` exposed on `MonthlyBudgetResponse`** (additive) so the UI shows a
   "Måned lukket"-badge instead of discovering closure via 409.

## Trade-off accepted

A user can close a month early on incomplete numbers. Accepted because: the action is
explicit and behind a warning dialog; re-close is blocked (409) so the mistake is
visible, not silent; and goals never decrement (ADR-0003), so the damage is bounded to
an early-but-real surplus snapshot. The systematic fix is F1-07.
