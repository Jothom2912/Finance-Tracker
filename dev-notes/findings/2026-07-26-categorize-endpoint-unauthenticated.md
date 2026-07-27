---
title: "/api/v1/categorize is unauthenticated and takes user_id from the request body — private rules are readable by anyone on the network"
date: 2026-07-26
severity: CRITICAL
area: categorization
status: resolved
backlog: [P1-15]
resolved-by: P1-15 (2026-07-27) — see plans/2026-07-27-p115-categorize-auth-and-secret-rotation.md and decisions/2026-07-27-categorize-internal-only.md
---

# `/api/v1/categorize` is unauthenticated and takes `user_id` from the request body

**Where**: `services/categorization-service/app/adapters/inbound/categorize_api.py:29-46`,
registered at `app/main.py:104`. The app is constructed with no global dependency
(`app/main.py:28-35`) and the service is published on the host at `8005:8005`
(`docker-compose.yml`, categorization-service `ports:`).

**Defect**: Neither `POST /api/v1/categorize/` nor `POST /api/v1/categorize/batch` has an
auth dependency of any kind — no JWT, and no `require_internal_api_key` of the sort
user-service (`rest_api.py:16-28`) and account-service (`internal_api.py:20`) use for
their S2S endpoints. The user scope is read straight from the request body and passed to
`build_categorization_service(user_id=body.user_id)` (`app/dependencies.py:16-24`), which
layers that user's private F1-02 rules on top of the global engine.

The docstring at the top of the file states the design intent honestly — the service is
built per request precisely *because* the user scope lives in the body. What is missing is
the guard that makes that safe: the endpoint is S2S-intended but not S2S-restricted.

## Demonstrated live (2026-07-26, running dev stack, no credentials of any kind)

User 1 has three private rules in `categorization_rules`, including
`merchant → "shop n play" → subcategory 5`.

```
POST http://localhost:8005/api/v1/categorize/   (no Authorization header)
{"description":"SHOP N PLAY","amount":-199.0,"transaction_id":999998,"user_id":<X>}
```

| `user_id` | Response |
|---|---|
| `null` | `category_id:8, subcategory_id:32, tier:"fallback", confidence:"low"` |
| **`1`** | **`category_id:1, subcategory_id:5, tier:"rule", confidence:"high"`** |
| `2` | `category_id:8, subcategory_id:32, tier:"fallback", confidence:"low"` |

HTTP 200 in all three cases. `/docs` on the same port also returns 200, so the request
shape does not have to be guessed.

**Why it matters**: the differing `tier` field turns the endpoint into an oracle over
other users' private rule sets. An unauthenticated caller can probe arbitrary strings
against an arbitrary `user_id` and learn, one query at a time, which merchants that user
has taught the system and which subcategory they assigned — i.e. reconstruct a meaningful
slice of a stranger's spending habits without ever touching a transaction endpoint. Under
F1-03 these rules are *auto-generated from the user's manual corrections*, so the rule set
is a direct projection of real behaviour, not a configuration the user thinks of as public.

`user_id` is a small integer, so enumeration is trivial.

Secondary: `categorize_batch` accepts a bare `list[CategorizeRequestDTO]` with no
`max_items` bound (`categorize_api.py:36`), so the same unauthenticated surface accepts an
arbitrarily large request body — an availability problem independent of the disclosure.

## Suggested fix

1. Put `require_internal_api_key` on `categorize_router`, matching the pattern already
   used in user-service and account-service. transaction-service is the only real caller
   and already has S2S config, so this is a config addition, not a redesign.
2. Bound the batch: `Annotated[list[CategorizeRequestDTO], Field(max_length=...)]`, or wrap
   it in a DTO with the bound declared, mirroring `BulkCreateTransactionDTO`'s 1..500.
3. Stop publishing 8005 on the host — see `SEC-3` in
   [2026-07-26-product-surface-sweep.md](2026-07-26-product-surface-sweep.md); the endpoint
   should not be reachable from outside the compose network at all. This is defence in
   depth, not a substitute for (1).

Note that account-service's key check uses `!=` rather than `compare_digest`
(`internal_api.py:20`) — copy user-service's version (`rest_api.py:24`), not that one.

## Not covered by this finding

`categorization-service`'s taxonomy CRUD (`category_api.py:45,63,73,97,122,132`) *is*
authenticated but not authorised: the identity is fetched and discarded (the parameter is
literally named `_user_id`), so any logged-in user can `DELETE` a category out of the
global ADR-003 taxonomy that every other user's transactions reference. Different defect,
different fix (there is no role concept anywhere in the codebase) — filed separately as
`SEC-5` in the sweep.
