---
title: F1-04 — complete the goal-allocation flow (ADR-0003): surplus → goal, end-to-end incl. UI
date: 2026-07-17
status: draft
backlog-items: [F1-04]
related:
  - ../backlog/FEATURES.md
  - ../../docs/adr/0003-goal-allocation-from-budget-surplus.md
  - ../architecture/services/account-budget-goal-services.md
  - ../findings/2026-07-12-goal-migration-004-sqlite.md
---

# F1-04 — goal allocation completion

## Goal

The flagship "dit overskud bliver opsparing" story is demoable end-to-end from the UI:
a user marks a goal as their default savings goal, closes a budget month from
BudgetPage, and sees the goal's balance grow with a visible allocation-history entry.
Months closed *without* a default goal surface as an "uallokeret overskud" card so the
money is never silently invisible.

## Context (code survey 2026-07-17, two Explore agents)

**Already built and solid** (ADR-0003 steps 1, 3-schema, 4, 5 + budget extraction):
- `BudgetMonthClosedEvent` contract; `POST /api/v1/monthly-budgets/close` (JWT,
  fail-closed 503 per P1-01, re-close → 409, `source_key =
  budget.month_closed:{account_id}:{year}:{month}`, outbox in same commit).
- goal-service consumer on shared `ConsumerBase` (queue
  `goal_service.budget_month_closed`, DLQ+retry, IntegrityError-as-duplicate-ack) →
  `BudgetMonthClosedHandler` with statuses `ignored_zero_surplus / duplicate /
  unallocated_no_default_goal / unallocated_goal_already_complete / allocated`.
- Schema (migration 003): `is_default_savings_goal` + one-default-per-account partial
  index, `goal_allocation_history` (unique `(source_key, goal_id)`),
  `unallocated_budget_surplus` (unique `source_key`). Good unit+integration coverage.
- Audit-bug "goal events publish account_id as user_id" is **already fixed** on master
  (events built with `user_id=owner_id` from account-service lookup) — arch doc still
  flags it; update when closing this plan.

**Missing — the feature is built but unreachable** (memory note
`default-savings-goal-gap` confirmed still true):
1. No API sets `is_default_savings_goal` (no route, no DTO field, not in `GoalResponse`,
   not on the domain entity) → the allocated path is dead for real users; every surplus
   lands in `unallocated_budget_surplus`.
2. No read API for `goal_allocation_history` or `unallocated_budget_surplus` — both
   tables are write-only.
3. Frontend has **no close-month call at all** (`api/monthlyBudgets.jsx` lacks it) and
   no allocation/default-goal UI. Goals are fetched directly from goal-service (8006),
   not via gateway — keep that pattern.
4. No scheduled day-7 close job exists anywhere (ADR's v1 trigger was never built;
   the monolith that was supposed to host it is gone).

## Key decision — manual close button, day-7 job deferred

ADR-0003 listed "manual close-month button" as out of scope and planned a scheduled
day-7 close. Reality inverted: the close endpoint is manual-only and JWT-authenticated,
and no scheduler exists in budget-service. A UI button over the *existing* endpoint is
the honest completion of the flow (zero new backend surface); a scheduler is real infra
that belongs with F1-05's scheduling work. → Build the button now (confirm-dialog warns
about the day-7 rationale: bank transactions settle 1-3 days late), record a decision
note superseding the ADR's out-of-scope line, and add a backlog item for the scheduled
close (pairs with F1-05).

## Non-goals (behavior preserved)

- **No money-semantics changes**: handler still allocates the FULL surplus even past
  `target_amount` (overshoot allowed; "already complete" pre-check unchanged), goals
  never decrement, zero surplus stays row-less. Consumer/handler code untouched.
- No UI for *reassigning* unallocated surplus (ADR out-of-scope stands) — display only.
- No allocation outbox event (`goal.allocation_applied`) — noted as F1-01 follow-up;
  frontend freshness via query invalidation is enough for now.
- No gateway exposure of goals (frontend keeps calling goal-service directly).
- No split allocations, no Decimal-DTO refactor (goal DTOs stay float — pre-existing),
  no changes to budget-service beyond nothing (close endpoint is used as-is).
- `POST /close` semantics unchanged (404/409/503 mapping stays).

## Steps

### Wave 0 — drive-by: goal migration tests green again

1. [ ] Fix finding F-2026-07-12-01: rewrite migration
   `004_widen_correlation_id_to_varchar.py` with `op.batch_alter_table` (sqlite-safe,
   same result on Postgres). Verify `tests/migrations/` green on sqlite AND
   `alembic upgrade head` against compose Postgres. Own commit; set finding resolved.

### Wave 1 — goal-service: default-goal write + allocation read APIs

2. [ ] **Expose the flag**: `is_default_savings_goal` on `GoalResponse`
   (`app/application/dto.py`) + `_to_dto` mapping (`service.py`). NOT settable via
   create/update DTOs — only via the dedicated endpoint (the partial unique index makes
   a DTO-flag toggle a 500-trap on the second default).
3. [ ] **Set/unset default**: `PUT /api/v1/goals/{goal_id}/default` +
   `DELETE /api/v1/goals/{goal_id}/default` in `app/main.py` (house pattern: routes in
   main.py, ownership via account-service owner lookup like existing routes). Repo
   method `set_default_savings_goal(goal_id, account_id)` — one transaction: clear
   existing default for the account, set the new one; IntegrityError from the partial
   index → 409. Emits `goal.updated` (existing event, full state).
4. [ ] **Read APIs**: `GET /api/v1/goals/{goal_id}/allocation-history` (per ADR) →
   `[{amount, source_key, applied_at}]` newest-first; `GET
   /api/v1/goals/unallocated-surplus?account_id=` (declared BEFORE `/{goal_id}` routes —
   int path converter 422s otherwise) → `{total, entries: [{amount, reason,
   observed_at}]}`. New read methods on `postgres_goal_allocation_repository.py`.
5. [ ] Tests: unit (set-default switches atomically, second default impossible,
   ownership denied 403/404, response includes flag) + integration router tests on
   sqlite UoW (mirror existing `test_goal_api*.py`); allocation-history/unallocated
   read tests seeded via the existing handler (reuses its fixtures).

### Wave 2 — frontend: goals UI

6. [ ] `api/goals.jsx`: `setDefaultGoal(goalId)` / `clearDefaultGoal(goalId)`,
   `fetchAllocationHistory(goalId)`, `fetchUnallocatedSurplus()` (account fra
   `getAccountId()`). `useGoals`: map `is_default_savings_goal`; `setDefault` mutation
   invalidating `['goals']`.
7. [ ] `GoalItem`: "Standard opsparingsmål"-badge + "Sæt som standard"-handling
   (star-toggle); allocation-history som udvidbar sektion/modal med lazy
   `useAllocationHistory(goalId)` (enabled-on-open). `GoalOverview`: "Uallokeret
   overskud"-kort (total + rækker med reason på dansk) + hint "Vælg et standardmål for
   at fremtidigt overskud opspares automatisk" når intet default findes.
8. [ ] Component/hook tests (mirror `useGoals.test.jsx` + GoalItem tests).

### Wave 3 — frontend: close month from BudgetPage

9. [ ] `api/monthlyBudgets.jsx`: `closeMonthlyBudget({month, year})` → `POST
   /monthly-budgets/close`. BudgetPage: "Luk måned"-knap for den valgte måned med
   ConfirmDialog (ADR-0002 imperative API; teksten forklarer at banktransaktioner kan
   være 1-3 dage forsinkede), `useMutation` med pending-state; danske fejlbeskeder for
   404 (intet budget) / 409 (allerede lukket) / 503 (prøv igen senere); succes →
   invalider budget-, summary- og goals-queries + toast der peger på GoalPage.
10. [ ] Tests: mutation-hook + knap-flow (confirm → kald → invalidation), fejl-mapning.

### Wave 4 — verification + bookkeeping

11. [ ] `make -C services/goal-service test` (+ migrations-suiten nu grøn), frontend
    `npm test` + lint, ruff. Live e2e på compose (goal-service image family rebuild!):
    opret mål → sæt som standard (stjerne synlig) → luk måned med overskud fra UI →
    målbalance vokser + historik-række synlig; luk en måned uden default-goal (andet
    account/mål-opsætning) → uallokeret-kort viser beløbet; gen-luk → 409-besked.
    Syntetisk testdata, ryd op bagefter.
12. [ ] dev-notes: decision note (manual close supersedes ADR-0003 out-of-scope-linjen;
    day-7 job → nyt backlog-item koblet til F1-05), FEATURES F1-04 → done, arch doc
    opdateres (goal-service ruter, fjern stale ⚠ user_id-bug-linje, budget close-UI),
    session log, opdater memory-noten `default-savings-goal-gap` → resolved.
    Commit per wave (~5 commits).

## Risks & rollback

- **Set-default race** (to samtidige PUT'er): partial unique index er backstop;
  IntegrityError → 409, klienten refetcher. Rollback: endpoints er additive.
- **Route-skygge**: `unallocated-surplus` skal deklareres før `/{goal_id}`-ruter
  (int-converter giver ellers 422). Testes eksplicit i router-testen.
- **Bruger lukker måneden for tidligt** → surplus på ufuldstændige tal. Mitigeret af
  confirm-dialog med day-7-rationalet; gen-luk er blokeret (409), så fejlen er synlig
  og bevidst. Den rigtige løsning (scheduled close) er backlog-item'et.
- **Migration 004-fix rører en shipped migration**: batch-rewrite ændrer kun
  sqlite-eksekverbarhed; verificeres mod ægte Postgres før commit (finding'ens eget krav).
- Alt nyt er additivt (ingen konsumer/handler/skema-ændringer) — rollback = revert af
  vave-commits enkeltvist.

## Outcome (fill in when done)

—
