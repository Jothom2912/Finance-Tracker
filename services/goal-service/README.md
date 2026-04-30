# Goal Service

Goal Service is a FastAPI microservice for managing savings goals.

## What it does

- CRUD for goals
- Validates accounts through the user service
- Writes goal events into an outbox table
- Publishes outbox events through a background worker

## Run locally

From the repository root:

```bash
docker compose up -d postgres-goals rabbitmq user-service goal-service goal-outbox-worker
```

## Test locally

From `services/goal-service`:

```bash
python run_tests.py
```

Or:

```bash
make test
```

## Tests

- `tests/unit/test_goal_service.py`: service-layer behavior and outbox writing
- `tests/unit/test_goal_repository.py`: repository CRUD against an in-memory database
- `tests/unit/test_goal_api.py`: FastAPI route behavior with dependency overrides
- `tests/integration/test_goal_api_integration.py`: API -> service -> repository round trip
- `tests/integration/test_goal_service_outbox_integration.py`: outbox rows for create, update, delete
- `tests/integration/test_outbox_worker_integration.py`: worker publishes pending outbox events
- `tests/integration/test_outbox_worker_retry_integration.py`: worker marks failures and retries
- `tests/integration/test_outbox_worker_multiattempt_integration.py`: repeated retry flow until success

## Notes

- `tests/conftest.py` sets safe defaults for local test execution.
- The service expects `JWT_SECRET` and `DATABASE_URL` in real deployments.
