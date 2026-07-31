---
title: "Pattern: hexagonal architecture (ports & adapters)"
updated: 2026-07-17
source: architecture audit 2026-07-07; ai-service port hardening 2026-07-12
---

# Hexagonal architecture

Every service is layered so the **domain has zero infrastructure imports** (no DB, MQ,
HTTP). Dependencies point inward; infrastructure is swappable behind ports.

## Canonical layout (user-service — cleanest exemplar)

See [architecture/services/user-service.md](../architecture/services/user-service.md).

```
app/
  domain/              # frozen dataclasses, domain exceptions — no imports outward
  application/
    service.py         # use cases
    dto.py             # pydantic v2 DTOs
    ports/             # IUserRepository, IOutboxRepository, IEventPublisher, IUnitOfWork
  adapters/
    inbound/rest_api.py    # HTTP → application; domain exceptions → HTTP status mapping
    outbound/              # Postgres repos, rabbitmq_publisher, unit_of_work
  workers/             # separate processes (outbox publisher, consumers)
  main.py              # composition root / DI
```

## House rules (CLAUDE.md)

- Domain entities are **frozen dataclasses**; computed properties over stored state.
- **Domain exceptions** map to HTTP explicitly in the inbound adapter. Real 503+WARNING
  examples: `BankConfigError` (`banking/app/main.py:94-99`), `ReadStoreUnavailableError`
  (`analytics/app/main.py:54-58`). This line previously cited `BankConnectionInactive` → 503 +
  WARNING; it is **409 with no log** (`banking/app/main.py:48`, `bank_api.py:237`) — corrected
  under P3-59, 2026-07-31.
- **Whether a rejection gets a log line follows one admission rule** (P3-59): a rejection
  deserves a line *iff the status code alone is ambiguous about the cause*. The access line
  already says what happened, so a line that only repeats it is a second access log. 422s and
  ordinary unambiguous 404s get nothing — deliberately, and written down as such.
- Repository pattern for persistence; UoW owns the transaction boundary (critical for
  [transactional-outbox](transactional-outbox.md)).
- Inject clocks — no `datetime.now()` in domain logic.

## Enforcement status (honest picture)

- **pytest-archon runs only in ai-service and analytics-service**
  (`tests/test_architecture.py` in each). Other services rely on discipline. Extending
  archon tests is cheap when touching a service — copy from ai-service.
- ai-service ports were **decorative** until 2026-07-12; now `@runtime_checkable` with
  conformance + signature-drift tests — that's the template for making ports real
  ([sessions/2026-07-12-ai-es-chat-wave1.md](../sessions/2026-07-12-ai-es-chat-wave1.md)).
- `execute_with_logging` exists in **analytics-service only** (`app/shared/logging.py:17`),
  bound to `AnalyticsDomainError` and logging to `"analytics.usecase"` — outside `app.*`, so a
  `grep '\[app\.'` misses every line it emits. CLAUDE.md called it a convention; it is one
  service's helper. P3-59 declined to promote it: it emits an `info` line per completed use
  case, which is exactly what the admission rule rejects. Per-use-case duration is P3-11.
- **Request-path logging is in place in all 12 API processes** (P3-57 config, P3-59 call sites).
  Before P3-59, five services — `account`, `user`, `goal`, `notification`, `saga` — emitted
  **zero** lines from the request path; `goal` had no logging statements at all. A log-based
  check of the platform had five holes it could not see.

## Known deviations

- account-service: sync stack, monolith residue, dead `SyncUnitOfWork`, 240-line auth
  module ([account-budget-goal-services](../architecture/services/account-budget-goal-services.md)).
- goal-service: routes defined directly in `app/main.py` (no inbound adapter module).
- transaction-service: `categorization_client.py` is duck-typed, no port interface;
  `TransactionService` is a 625-line god-ish application service
  ([transaction-service](../architecture/services/transaction-service.md)).
