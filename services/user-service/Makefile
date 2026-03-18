SHELL := /bin/bash
.PHONY: help install-deps dev test test-unit test-integration lint format format-check check migrate migrate-down freeze clean

help: ## Show available targets
	@printf 'Available targets:\n'
	@printf '  install-deps        Install all dependencies\n'
	@printf '  dev                 Start service with hot-reload on port 8001\n'
	@printf '  test                Run all tests\n'
	@printf '  test-unit           Run unit tests only\n'
	@printf '  test-integration    Run integration tests only\n'
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

dev: ## Start service with hot-reload on port 8001
	uv run uvicorn app.main:app --reload --port 8001

test: ## Run all tests
	uv run pytest tests/ -v

test-unit: ## Run unit tests only
	uv run pytest tests/unit/ -v

test-integration: ## Run integration tests only
	uv run pytest tests/integration/ -v

lint: ## Run ruff linter
	uv run ruff check .

format: ## Auto-format code with ruff
	uv run ruff format .
	uv run ruff check --fix .

format-check: ## Check code formatting without changes
	uv run ruff format --check .

check: lint format-check ## Run all quality checks (lint + format)

migrate: ## Run database migrations to latest
	uv run alembic upgrade head

migrate-down: ## Rollback last migration
	uv run alembic downgrade -1

freeze: ## Generate requirements.txt from pyproject.toml (for Docker builds)
	uv export --no-dev --no-hashes > requirements.txt

clean: ## Remove generated artifacts
	rm -rf .venv .pytest_cache .ruff_cache .coverage *.egg-info
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
