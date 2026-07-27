---
title: "/api/v1/categorize is S2S-only, and user_id was removed from the DTO rather than fenced"
date: 2026-07-27
status: accepted
backlog-items: [P1-15]
supersedes: null
promoted-to-adr: null
---

# `/api/v1/categorize` is S2S-only, and `user_id` was removed from the DTO

Written 2026-07-27 to close a dangling reference: the P1-15 plan links to this decision,
but the file was never created when the work shipped. Content is taken from that plan and
re-verified against the code as it stands.

## Decision

The sync categorization router is guarded by `require_internal_api_key` at **router**
level, and `user_id` is **deleted** from `CategorizeRequestDTO` rather than merely
protected by the new auth check.

## Context

`categorize_api.py` had no auth and read `user_id` from the request body, layering that
user's private F1-02 rules onto the engine. The response's `tier` field therefore
distinguished "this user has a rule for this merchant" from "no rule" — an oracle over
another user's spending habits, demonstrated live without credentials on 2026-07-26 (see
[findings/2026-07-26-categorize-endpoint-unauthenticated.md](../findings/2026-07-26-categorize-endpoint-unauthenticated.md)).

The decisive fact is that no legitimate caller uses the field:
`transaction-service/app/adapters/outbound/categorization_client.py` sends only
`{description, amount}`, and per-user rule layering happens on the **async** consumer
path, which takes `user_id` from the event and never goes through HTTP.
transaction-service is the only caller in the repo.

## Alternatives considered

- **Keep `user_id`, just require the internal key.** Rejected: the field's only remaining
  consumer would be an attacker who obtained the key. Auth reduces the blast radius of the
  oracle; it does not remove it. A field that exists solely as an attack surface should not
  exist.
- **Take `user_id` from a JWT instead of the body.** Rejected as scope inversion — this is
  a service-to-service endpoint, so there is no end-user token on the path. Introducing one
  would mean giving transaction-service a user context it does not need.
- **Per-endpoint `dependencies=`.** Rejected in favour of router-level: an endpoint added
  to this router later is then guarded by default instead of by remembering to opt in.

## Consequences

- The sync path runs **global rules only**. This is not a behavior change — transaction
  service never sent `user_id` — but it is now a documented property rather than an
  accident, and anyone wanting per-user rules synchronously must add them deliberately.
- Both services needed `INTERNAL_API_KEY` added to config; contrary to the original
  backlog row, neither side had S2S config already.
- Missing key config yields **503**, not 401: an unconfigured service is broken, not the
  caller's fault, and it fails closed either way.
- `compare_digest` rather than `!=`, copied from user-service, so a wrong key costs the
  same time regardless of how many leading bytes matched.
- `/batch` gained a `MAX_BATCH_ITEMS = 500` ceiling, matching transaction-service's
  `BulkCreateTransactionDTO` — the only producer of batches.
