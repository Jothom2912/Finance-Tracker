SHELL := /bin/bash
.PHONY: help install-deps dev test test-unit test-integration test-migrations test-all lint typecheck format format-check check migrate migrate-down clean

help: ## Show available targets
	@printf 'Available targets:\n'
	@printf '  install-deps        Install all dependencies\n'
	@printf '  dev                 Start service with hot-reload on port 8002\n'
	@printf '  test                Run fast tests (unit + integration, excludes Testcontainers)\n'
	@printf '  test-unit           Run unit tests only\n'
	@printf '  test-integration    Run integration tests only\n'
	@printf '  test-migrations     Run Alembic migration tests against real Postgres (requires Docker)\n'
	@printf '  test-all            Run every test target including Testcontainers migration suite\n'
	@printf '  lint                Run ruff linter\n'
	@printf '  format              Auto-format code with ruff\n'
	@printf '  format-check        Check code formatting\n'
	@printf '  check               Run all quality checks\n'
	@printf '  migrate             Run database migrations to latest\n'
	@printf '  migrate-down        Rollback last migration\n'
	@printf '  clean               Remove generated artifacts\n'

install-deps: ## Install all dependencies (prod + dev)
	uv sync --dev

dev: ## Start service with hot-reload on port 8002
	uv run uvicorn app.main:app --reload --port 8002

test: ## Fast suite — unit + integration in separate pytest invocations to avoid module-import state pollution.
	uv run pytest tests/unit/ -v
	uv run pytest tests/integration/ -v

test-unit: ## Run unit tests only
	uv run pytest tests/unit/ -v

test-integration: ## Run integration tests only
	uv run pytest tests/integration/ -v

test-migrations: ## Run Alembic migration tests against a real Postgres via Testcontainers (requires Docker running).
	uv run pytest tests/migrations/ -v

test-all: ## Run the whole tree in ONE pytest process, exactly as CI does. Use before pushing.
	# Not `test test-migrations`: two invocations hide order-dependent failures,
	# because a test that only passes in isolation still passes when its
	# directory runs alone. CI runs `pytest tests`, so this must too.
	uv run pytest tests

lint: ## Run ruff linter
	uv run ruff check .

# P2-31: config lives in pyproject's [tool.mypy]. No MYPYPATH — shared/* resolve
# as installed packages via py.typed; pointing mypy at their source as well is
# what produces "Source file found twice". The venv is the single source of truth.
typecheck: ## Run mypy (P2-31 gate)
	uv run mypy

format: ## Auto-format code with ruff
	uv run ruff format .
	uv run ruff check --fix .

format-check: ## Check code formatting without changes
	uv run ruff format --check .

check: lint format-check typecheck ## Run all quality checks (lint + format + types)

migrate: ## Run database migrations to latest
	uv run alembic upgrade head

migrate-down: ## Rollback last migration
	uv run alembic downgrade -1

clean: ## Remove generated artifacts
	rm -rf .venv .pytest_cache .ruff_cache .coverage *.egg-info
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
