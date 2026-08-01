# Finance Tracker — repository guidance

## Working agreement

- Read the `dev-notes` skill before planning or implementing non-trivial work. Search by work
  ID first; otherwise load only notes relevant to the files and services in scope.
- Create a plan before changes that affect domain behavior, architecture or multiple services.
  Wait for approval before implementing a newly proposed plan.
- Preserve unrelated working-tree changes and keep changes scoped to one logical concern.
- Explain non-obvious trade-offs and briefly explain why an implemented approach works.
- Treat dated notes as claims: verify paths, counts and behavior against current code.

## Architecture

- Keep bounded contexts hexagonal: domain code must not depend on databases, queues, HTTP or
  framework adapters. Use explicit ports and repository adapters.
- Communicate across services through APIs or events, never cross-service database access.
- Use transactional outbox for domain writes that publish events and DB-backed idempotency for
  consumers.
- Prefer computed properties to duplicated stored state. Use soft delete for domain entities
  unless a documented decision selects another lifecycle.
- Use UUIDv7 for new cross-service identifiers. Keep event payloads self-contained enough for
  consumers to repair missed projections.
- CQRS-lite is the house shape: REST writes and denormalized read models; check the relevant
  architecture and pattern notes before extending a flow.

## Python and services

- Use `uv` and one dependency source per service. Do not introduce both `uv.lock` and
  `requirements.txt`; `account-service` is the documented legacy exception.
- Add `py.typed` and bump the package version for changed `services/shared/*` packages; path
  dependencies are installed as copies.
- Add type hints to private and public functions. A `# type: ignore` needs a backlog reference.
- Keep domain exceptions independent of HTTP and map them explicitly in the adapter layer.
- Inject clocks into domain logic; do not call `datetime.now()` directly there.
- Configure API logging with `setup_logging()` from `shared/observability` at module import in
  `app/main.py`. Use lazy `%` arguments and never log credentials or full hostile input.
- Log an HTTP rejection only when its status code is ambiguous about the cause. Ordinary
  validation errors and unambiguous 404s do not need a duplicate access-log line.

## Verification

- Add deterministic unit tests for new domain behavior and relevant edge cases.
- Use service Makefiles: `make -C services/<service> test` and, where available,
  `make -C services/<service> check`.
- Run `make notes-check` after changing `dev-notes/`, plans or repository skills.
- Run `make compose-check` after Dockerfile, dependency or Compose changes.
- A static check does not prove an image starts. For container/dependency changes, start the
  affected API and workers and inspect their logs.
- Verify migrations against the intended database/schema, not only by exit code.
- Do not hide verification failures in pipelines that report a formatter/filter exit status.

## Frontend

- Follow existing React/Vite patterns. Forms use controlled `useState`, submit-time validation,
  global notifications and disabled saving state; do not introduce React Hook Form or Zod as a
  one-form side effect.
- Centralize server state and invalidation through the existing TanStack Query helpers.
- Normalize API shapes at the boundary and use shared formatters.

## Knowledge ownership

- `AGENTS.md` owns durable repository workflow and conventions.
- `dev-notes/architecture` and `patterns` own current system knowledge.
- Findings own unresolved defects; decisions own non-obvious choices; plan `Outcome` owns the
  shipping narrative; sessions only preserve resumable state, cross-item discoveries or open
  ends.
- Link to a canonical fact instead of restating it across surfaces.
