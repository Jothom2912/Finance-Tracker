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

## Notes

- `tests/conftest.py` sets safe defaults for local test execution.
- The service expects `JWT_SECRET` and `DATABASE_URL` in real deployments.
