---
title: F1-02 + F1-03 — user categorization rules (CRUD + UI) and the correction feedback loop
date: 2026-07-17
status: done
backlog-items: [F1-02, F1-03]
related:
  - ../backlog/FEATURES.md
  - ../plans/2026-07-07-feature-roadmap.md
  - ../architecture/services/categorization-and-ai-services.md
---

# F1-02 + F1-03 — user rules & feedback loop

## Goal

A user can (1) define their own categorization rules ("description contains X → category Y")
in a rules admin UI, ranked above seed rules, effective without a service restart; and
(2) have manual category corrections *teach* the system, so the same merchant is
auto-categorized correctly on the next import. Done when: correcting a transaction in the
UI creates a learned rule visible on the rules page, and re-importing a similar CSV row
lands in the corrected category.

## Context (code survey 2026-07-17)

- **Rules scaffolding is ¾ built**: `categorization_rules` has `user_id` (NULL = global
  seed), `priority` (seeds = 100), `active`, partial index `ix_rules_user`;
  `PostgresRuleRepository` has full CRUD incl. `find_active_rules(user_id=…)` with the
  OR-global query — **nothing calls the user-scoped variant**. No `RuleService`, no rules
  router. (`app/models.py:45-61`, `postgres_rule_repository.py`)
- **Provider/engine gaps**: `rule_engine_provider._reload` loads global rules only, into
  ONE cached engine (60s TTL); `RuleEngine` flattens priority to pure longest-match
  (`rule_engine.py:53`) — a user rule at priority 50 would NOT beat a longer seed keyword.
  Only `pattern_type=KEYWORD` is consumed; MERCHANT/REGEX/AMOUNT_RANGE are enum-only.
- **Feedback hooks exist but are dormant**: `merchants.is_user_confirmed` flag + repo are
  never used by the pipeline; `MappingSource` enum unused. transaction-service already
  pins manual corrections: `update_transaction` sets `categorization_tier="manual"` on
  any category-field change (`service.py:201-210`), and its categorized-consumer refuses
  to overwrite manual rows (`categorized_consumer.py:152-157`). What's missing is the
  event + the learning consumer.
- **`user_id` flows already**: `CategorizeRequestDTO.user_id` exists (optional);
  `transaction.created` carries `user_id`. No contract changes needed for scoping.
- **Frontend**: no RHF/Zod anywhere (CLAUDE.md's frontend section is aspirational —
  house pattern is controlled `useState` forms; follow it). CRUD-admin template to copy:
  `CategoryManagement.jsx`. API base for categorization-service exists
  (`CATEGORIZATION_SERVICE_URL` in `serviceUrls.js`). Key-factory + central
  `invalidateFinancialData` helper per P2-18.

## Key decision — learned corrections are RULES, not merchant rows

The original sketch said "upsert merchant mapping with `is_user_confirmed=true`", but the
merchants table is **global** (`normalized_name` UNIQUE, no `user_id`) — one user's
correction would rewrite another user's categorization, and merchants don't feed the
engine at all today. Instead, the correction consumer upserts an **auto-managed user
rule**: `pattern_type=MERCHANT`, `pattern_value=<normalized description>`,
`user_id=<owner>`, `priority=10`. One matching mechanism (the rule engine), one storage,
and learned rules appear in the F1-02 UI for free (visible + deletable = user stays in
control). The merchants table stays as global seed data; `is_user_confirmed` stays unused
(note in FEATURES that the original hook was superseded). Record as a decision note when
implemented.

Priority ladder: 10 = learned from corrections, 50 = user-created, 100 = seeds.
Engine match order becomes (priority asc, keyword-length desc) with first-tier-hit wins —
longest-match preserved *within* a tier, user intent beats seed length *across* tiers.

## Non-goals

- No ML/LLM tiers (F1-06), no REGEX/AMOUNT_RANGE rule authoring in the UI (KEYWORD +
  auto-managed MERCHANT only; enum stays for later).
- No change to taxonomy ownership (ADR-003) or the `transaction.categorized` contract.
- No rules admin for *global/seed* rules — they stay migration-managed; users only see
  and manage their own.
- Existing behavior preserved: unchanged categorization for users with zero rules
  (global engine path identical); manual-tier guard in transaction-service untouched;
  `POST /categorize` stays unauthenticated S2S (user_id in body, as today).
- No merchants-table changes.

## Steps

### Wave 1 — contracts + producer (transaction-service)

1. [x] *(2026-07-17, `83ce7769`)* **Contract**: `TransactionCategoryCorrectedEvent` in
   `services/shared/contracts/contracts/events/transaction.py` (v1,
   `event_type="transaction.category_corrected"`): `transaction_id, user_id, account_id,
   description, category_id, category_name, subcategory_id, subcategory_name,
   previous_category_id, previous_subcategory_id`. Export in `events/__init__.py`;
   AsyncAPI: channel + message + schema (`docs/asyncapi.yaml`); contracts tests.
2. [x] *(2026-07-17, `24d5a926`; also emits on subcategory-only refinement)* **Emit on manual correction**: in `update_transaction`
   (`transaction-service/app/application/service.py`), gated on the SAME condition that
   sets `categorization_tier="manual"` (:201), add a second `outbox.add(...)` with the
   corrected-event alongside `TransactionUpdatedEvent`. Skip when the correction *clears*
   the category (nothing to learn from category=None). Unit tests: emitted on category
   change, not on amount-only change, not on clear-to-None.

### Wave 2 — categorization-service: rules API + engine scoping

3. [x] *(2026-07-17, `4e9e25d4`)* **Migration 007**: partial unique index
   `(user_id, pattern_type, pattern_value) WHERE user_id IS NOT NULL` — upsert backstop
   for learned rules + duplicate guard for user CRUD. Migration test.
4. [x] *(2026-07-17, `4e9e25d4`)* **RuleService + router**: `application/rule_service.py` (list/create/update/delete,
   user-scoped from JWT, validates `subcategory_id` exists, pattern_value normalized +
   trimmed, KEYWORD only via API, priority default 50 clamped to [20,90] so users can't
   outrank learned rules or drop below seeds), `adapters/inbound/rules_api.py`
   (`/api/v1/rules`, JWT via shared auth — mirrors `category_api.py`), DI in
   `dependencies.py`, register in `main.py`. `IRuleService` port. Unit + router
   integration tests (mirror `test_category_router_crud.py`).
5. [x] *(2026-07-17, `4e9e25d4` — TieredRuleEngine i adapter-laget; overlay-cache med invalidate_user wiret fra RuleService)* **User-scoped matching**: extend `rule_engine_provider` with a per-user overlay —
   `get(user_id)` returns the cached global engine + a small TTL-cached per-user keyword
   map (from `find_active_rules(user_id=…)`); `RuleEngine.match` tries priority tiers in
   order (learned → user → global), longest-match within tier.
   `CategorizationService.categorize` passes `user_id` through (sync API: from
   `CategorizeRequestDTO.user_id`; consumer: from event payload). Unit tests: user rule
   beats longer seed keyword; user A's rule invisible to user B; zero-rules path
   byte-identical to today.

### Wave 3 — categorization-service: feedback consumer

6. [x] *(2026-07-17, `bb1a110f` — normalisering som ren domain-funktion; sqlite_where-krav: text(), ikke streng)* **Corrected-consumer**: new worker `category_corrected_consumer.py` on shared
   `ConsumerBase` (queue `categorization.category_corrected`, routing key
   `transaction.category_corrected`, own DLQ + retries — copy `transaction_consumer.py`
   wiring incl. `processed_events` inbox). Handler: normalize description (reuse engine's
   transliteration/normalization), upsert learned rule (`pattern_type=MERCHANT`,
   priority 10, `user_id`, target subcategory; ON CONFLICT update target). Skip
   unlearnable events (empty/whitespace description, missing subcategory_id → parent-only
   correction stores `matches_subcategory_id`? — **no**: schema requires subcategory;
   parent-only corrections are skipped with a debug log, documented limitation).
   Compose + k8s worker entries (own `build:` block → remember the image-family deploy
   gotcha). Idempotency + upsert tests; wiring test through real UoW on sqlite
   (lesson from wave-B).

### Wave 4 — frontend (F1-02/03 UI + bounded UX fixes)

7. [x] *(2026-07-17, `5b2bcc6d`)* **Rules page**: `src/api/rules.jsx` (`createCrudApi('/rules', {baseUrl:
   CATEGORIZATION_SERVICE_URL})`), `useRules` hook (key `['rules']`, mutations invalidate
   `['rules']` + scope `transactions`), `pages/RulesPage.jsx` copying
   `CategoryManagement.jsx`'s pattern: two sections — "Dine regler" (KEYWORD, editable)
   and "Lært af dine rettelser" (MERCHANT, delete-only, explanatory hint), create/edit
   form with keyword input + cascading category→subcategory selects (reuse
   `useSubcategories`). Route `/rules` in `App.jsx` + "Regler" NavLink.
8. [x] *(2026-07-17, `5b2bcc6d` — inline click-to-edit dropdown m. optgroups via ny flat useAllSubcategories)* **Quick-recategorize + create-rule shortcut**: inline category editing in
   `TransactionsList` rows (compact select or popover; calls existing
   `updateTransaction` → manual tier + corrected event fire server-side), success toast
   with "Opret regel for '<merchant>'" action linking to prefilled RulesPage form; same
   "Opret regel fra denne transaktion" button in the edit modal.
9. [x] *(2026-07-17, `5b2bcc6d`)* **Bounded UX fixes** (only what we touch anyway): submit pending/disabled state on
   `TransactionForm`, route create/update through a `useMutation` like delete/CSV
   (kills the manual-invalidate drift), de-dupe the double success toast. NOT in scope:
   pagination/virtualization (own backlog item), CSV input querySelector.

### Wave 5 — verification + bookkeeping

10. [x] *(2026-07-17)* Per-service: contracts 44 / transaction (unit+35 int) /
    categorization 109 / frontend 239 + lint — green; all other uv services `make check`
    green; account+banking linted via `uvx ruff` (pip-based Makefiles — root `make check`
    can't run locally as-is: bare `ruff` in those two + gateway bandit B105 false
    positive w/o CI's `-ll -ii` flags; both pre-existing, noted in session log).
11. [x] *(2026-07-17)* Live e2e on compose PASSED (images rebuilt 13:11 > last code
    commit 12:20): correction → learned rule visible on `/api/v1/rules/` in ~2s →
    re-import lands in corrected category (learned rule beat longer seed keyword);
    KEYWORD rule respected after TTL expiry, no restart (an import *seconds* after
    rule-creation hit the stale 60s consumer cache — expected, decision note §6).
    Synthetic data only, cleaned up after.
12. [x] *(2026-07-17)* dev-notes done: [decision](../decisions/2026-07-17-learned-corrections-as-rules.md),
    FEATURES F1-02/03 → done, architecture docs (categorization + transaction — no
    event-catalog.md exists; documented in service docs instead),
    [session log](../sessions/2026-07-17-f102-03-wave5-verification.md).

## Risks & rollback

- **Engine changes regress existing categorization** — guarded by existing
  `test_rule_engine.py` + new zero-rules-identical test; the global path is untouched
  when no user rules exist. Rollback: revert wave 2/3 commits; migration 007 is
  downgrade-clean (index only).
- **Correction-event storm / loops**: corrected-consumer only *writes rules*, never
  transactions — no event cycle possible (`transaction.categorized` → tx-service is
  guarded by the manual-tier check).
- **Learned rule surprises the user** ("why did this categorize weirdly?") — mitigated by
  making learned rules visible + deletable on the rules page from day one.
- **Per-user cache growth**: overlay cache is tiny (rules per user ≪ 100) with TTL;
  single-user reality caps it anyway.
- **New consumer = new compose/k8s service**: deploy gotcha from 2026-07-16 (own image
  tag) — wave 6 rebuild checklist covers it.

## Outcome

Shipped 2026-07-17 in 5 code commits (`83ce7769`, `24d5a926`, `4e9e25d4`, `bb1a110f`,
`5b2bcc6d`) + docs. Both features e2e-verified live on compose: correction → learned rule
in ~2s → re-import auto-categorizes to the corrected target (learned tier beats seed
longest-match); user KEYWORD rules effective within the 60s TTL without restart. Key
deviation from the original F1-03 sketch recorded in
[decisions/2026-07-17-learned-corrections-as-rules.md](../decisions/2026-07-17-learned-corrections-as-rules.md)
(rules, not merchant rows; `is_user_confirmed` superseded). Known limitation: consumer
cache is TTL-only (cross-process invalidation deliberately not built).
