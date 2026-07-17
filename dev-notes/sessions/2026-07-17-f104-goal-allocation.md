---
date: 2026-07-17
topic: F1-04 shipped — goal-allocation flow reachable end-to-end (default-goal API, read APIs, UI, close button)
---

# F1-04: goal allocation completion

Plan: [plans/2026-07-17-f104-goal-allocation-completion.md](../plans/2026-07-17-f104-goal-allocation-completion.md).
4 code commits + docs; all waves same-day.

## Done

- **Wave 0** (`1a693117`): finding F-2026-07-12-01 resolved — migration 004
  batch_alter_table; PLUS two extra root causes: the migration-test fixture migrated a
  throwaway `:memory:` DB (env.py prefers `DATABASE_URL`, conftest sets it session-wide
  — fixed with monkeypatch), and 004's *downgrade* was broken on real Postgres too
  (varchar→uuid needs `postgresql_using`). Verified on sqlite (6/6) + throwaway
  postgres:16 up/down/up.
- **Wave 1** (`00431978`): goal-service — `PUT/DELETE /goals/{id}/default` (atomic
  clear-then-set, partial-index race backstop → 409, emits `goal.updated`),
  `GET /goals/{id}/allocation-history`, `GET /goals/unallocated-surplus` (static route
  before `/{goal_id}`), flag on `GoalResponse`. 82 tests + lint green.
- **Wave 2** (`1d436832`): frontend — star-toggle + "Standardmål"-badge on GoalItem,
  lazy "Automatiske opsparinger"-historik, uallokeret-overskud-kort med dansk
  reason-tekst + hint. 247 tests + lint green.
- **Wave 3** (`97953860`): "Luk måned"-knap på BudgetPage (ConfirmDialog med
  day-7-rationalet; danske 409/503-beskeder; goals-scope invalidation) +
  `closed_at` på `MonthlyBudgetResponse` → "Måned lukket"-badge. 250 tests + lint;
  budget-service 42 green.

## Live e2e (compose, image families rebuilt): PASSED

Synthetic data (goal 16, budgets 2025-05/06 på konto 1), cleaned up after:
1. Opret mål → `PUT /default` → luk måned (budget 150, forbrug 0) →
   **goal +150 kr på ~2s**, historik-række på det nye endpoint.
2. Gen-luk → **409**.
3. Fjern default → luk juni (75) → **unallocated-række** (`no_default_goal`) på det
   nye surplus-endpoint, total 75.

## Decisions & spawned work

- [decisions/2026-07-17-manual-month-close-button.md](../decisions/2026-07-17-manual-month-close-button.md)
  — manual close button supersedes ADR-0003's out-of-scope line; scheduled day-7 close
  → **F1-07** (pairs with F1-05 scheduler infra).
- **P3-16 + [finding](../findings/2026-07-17-goal-delete-fk-500.md)**: goal hard-delete
  with allocation history → FK 500 (found live during e2e cleanup — history row had to
  be deleted via psql first). Soft-delete er den rigtige retning (CLAUDE.md), egen plan.
- Audit's "goal events publish account_id as user_id" (HIGH) verified **fixed on
  master**; arch doc de-flagged.

## Operational notes

- goals-DB credentials i compose: `goal_service`/`goals` (ikke postgres/goals_db).
- Budget create/close/delete virker fint på syntetiske fortidsmåneder (2025-05) —
  praktisk e2e-mønster uden at røre rigtige data.
- Frontend-verifikation af de nye UI-flows: API-e2e + component-tests i sessionen;
  bruger gennemgik visuelt i browseren samme dag — godkendt.

## Open ends

- F1-07 (scheduled close) og P3-16 (goal soft-delete) i backlog.
- Næste spor-kandidater: F1-01 notifications (unblocked, consumer-base klar) eller
  F1-05 scheduled bank sync (P2-08 done; P3-14 mangler) eller AI-plan tail 13–21.
