---
title: Async categorization overwrites a caller-supplied category that the sync path protects
date: 2026-08-03
severity: MEDIUM
area: transaction-service, categorization-service
status: open
backlog: [TAX-16]
resolved-by: null
---

# Async categorization overwrites a caller-supplied category that the sync path protects

**Where**: `services/categorization-service/app/workers/transaction_consumer.py` versus
`services/transaction-service/app/application/service.py:80-95`.

**Defect**: The two categorization paths disagree about who owns an explicitly chosen category.
`create_transaction` is careful — "the caller's parent category always wins", and a conflicting
suggestion is logged and its subcategory skipped. The async consumer has no such rule: it
categorizes from the event and the resulting `transaction.categorized` rewrites the row regardless of
what the caller asked for. A client that posts `category_id` therefore gets its choice honoured
synchronously and silently replaced a second later.

**Why it matters**: when the rule tier cannot match, the async rewrite lands on the absolute fallback,
so a deliberately categorized transaction ends up in the unspecified bucket. Budget lines are
per-category, so the spend moves off the budgeted category and per-line alerts stop firing. That is
not hypothetical: it is the failure mode
`tests/e2e/test_budget_threshold_alert_e2e.py` was built around, and it broke twice —
first as the [alert categorization race](2026-07-27-e2e-alert-categorization-race.md), then again on
2026-08-03 when the TAX-06 activation made the seed rule unreachable and CI went red with
`dedup failed: expected 2 rows, found 0`.

The E2E works around it by choosing a description whose keyword a *reachable* rule matches, so the
async rewrite lands on the same category the fixture budgeted. That keeps the suite honest about
current behaviour, but it means an end-to-end budget test depends on global rule coverage — a
coupling that will break again the next time the seed set changes.

**Suggested fix**: decide explicitly who owns the category on the async path, and make both paths say
the same thing. The likely answer mirrors the sync rule: an explicit caller category is authoritative,
and async categorization may refine the subcategory beneath it but not move the parent. A fallback-tier
result should never overwrite a category a caller chose — the fallback means "unknown", which is
strictly less information than the caller already supplied. Once the paths agree, the E2E can budget
against the category it created and stop depending on rule coverage.

This changes domain behaviour across two services and needs an approved plan.
