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
- **Domain exceptions** map to HTTP explicitly in the inbound adapter (e.g.
  `BankConnectionInactive` → 503 + WARNING log).
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
- `execute_with_logging` (CLAUDE.md) exists in analytics-service
  (`app/shared/logging.py`) — not yet repo-wide.

## Known deviations

- account-service: sync stack, monolith residue, dead `SyncUnitOfWork`, 240-line auth
  module ([account-budget-goal-services](../architecture/services/account-budget-goal-services.md)).
- goal-service: routes defined directly in `app/main.py` (no inbound adapter module).
- transaction-service: `categorization_client.py` is duck-typed, no port interface;
  `TransactionService` is a 625-line god-ish application service
  ([transaction-service](../architecture/services/transaction-service.md)).
