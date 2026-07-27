---
title: A non-UUID saga_id retries to the DLQ instead of being rejected as poison
date: 2026-07-25
severity: LOW
area: saga
status: open
backlog: [P3-19]
resolved-by: null
---

# A non-UUID saga_id retries to the DLQ instead of being rejected as poison

**Where**: `services/saga-service/app/workers/saga_reply_consumer.py:53-68`.

**Defect**: The reply handler validates that `saga_id` is *present* and maps domain errors
to poison, but never checks that the value is a well-formed UUID:

```python
if not saga_id or not step_name:
    raise PoisonMessageError("Invalid saga reply: missing saga_id or step_name")
try:
    ...
    await orchestrator.handle_reply(saga_id, step_name, ...)
except SagaAlreadyCompleted:
    return
except SagaDomainError as exc:
    raise PoisonMessageError(...) from exc
```

A malformed id passes the guard, reaches the `uuid` column in Postgres and raises
`asyncpg.DataError` — an infrastructure exception, so neither `except` clause catches it.
`ConsumerBase` sees an unclassified failure, assumes it is transient, and burns
`MAX_RETRIES` before dead-lettering. The classification is simply wrong: a malformed id is
never going to become well-formed on redelivery.

**Why it matters**: Low, and it should stay low — real saga ids *are* UUIDs, minted by
saga-service itself, so no production path produces this. It surfaced as noise from a
synthetic P2-22 smoke test that used `p222-smoke-<epoch>` as a saga id.

The value in fixing it is not the malformed id, it is the exception classification. The
handler's structure states an intent — "domain errors are poison, everything else is
transient" — and an infrastructure exception raised *by bad input* falsifies it. The same
shape will recur wherever a consumer parses untrusted-ish input straight into a typed
column, and each instance costs a retry storm plus a DLQ entry that looks like an outage.

Found as a side effect during P2-22 live verification and recorded only in that plan's
Outcome section; written up here because a paragraph inside a completed plan is not
somewhere a future reader will look.

**Suggested fix**: Parse the id at the guard rather than validating it by database
rejection — `uuid.UUID(saga_id)` inside the existing `if`, raising `PoisonMessageError` on
`ValueError`. One edit, immediate reject instead of `MAX_RETRIES`, and the handler's stated
classification becomes true. Same treatment applies to any other consumer that feeds a
string id straight into a typed column.

Tracked as P3-19.
