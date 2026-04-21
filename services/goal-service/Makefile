SHELL := /bin/bash
.PHONY: help install-deps dev test test-unit test-integration test-migrations test-all lint format format-check check migrate migrate-down freeze clean

help: ## Show available targets
	@printf 'Available targets:\n'
	@printf '  install-deps        Install all dependencies\n'
	@printf '  dev                 Start service with hot-reload on port 8003\n'
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
	@printf '  freeze              Generate requirements.txt from pyproject.toml\n'
	@printf '  clean               Remove generated artifacts\n'

install-deps: ## Install all dependencies (prod + dev)
	uv sync --dev

dev: ## Start service with hot-reload on port 8003
	uv run uvicorn app.main:app --reload --port 8003

test: ## Fast suite — unit + existing SQLite integration tests. Excludes migrations/ (Testcontainers, slow, requires Docker).
	uv run pytest tests/ -v --ignore=tests/migrations

test-unit: ## Run unit tests only
	uv run pytest tests/unit/ -v

test-integration: ## Run integration tests only
	uv run pytest tests/integration/ -v

test-migrations: ## Run migration tests (requires Docker + Postgres testcontainer)
	uv run pytest tests/migrations/ -v

test-all: test-unit test-integration test-migrations
	@echo "All tests completed!"

lint: ## Run ruff linter
	uv run ruff check app/ tests/

format: ## Auto-format code with ruff
	uv run ruff format app/ tests/

format-check: ## Check code formatting without changing files
	uv run ruff format --check app/ tests/

check: format-check lint ## Run all quality checks

migrate: ## Run database migrations to latest
	uv run alembic upgrade head

migrate-down: ## Rollback last migration
	uv run alembic downgrade -1

freeze: ## Generate requirements.txt from pyproject.toml
	uv pip compile pyproject.toml -o requirements.txt

clean: ## Remove generated artifacts
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name '*.pyc' -delete
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .ruff_cache -exec rm -rf {} + 2>/dev/null || true
	rm -rf .coverage htmlcov/ dist/ build/ *.egg-info/
