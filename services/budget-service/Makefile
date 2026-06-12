SHELL := /bin/bash
.PHONY: help install-deps dev test test-unit test-integration lint format format-check migrate migrate-down clean
help:
	@printf 'Available targets:\n'
	@printf '  install-deps     Install all dependencies\n'
	@printf '  dev              Start service with hot-reload on port 8003\n'
	@printf '  test             Run unit + integration tests\n'
	@printf '  test-unit        Run unit tests only\n'
	@printf '  test-integration Run integration tests only\n'
	@printf '  lint             Run ruff linter\n'
	@printf '  format           Auto-format code with ruff\n'
	@printf '  migrate          Run database migrations to latest\n'
	@printf '  migrate-down     Rollback last migration\n'
	@printf '  clean            Remove generated artifacts\n'

install-deps:
	uv sync --dev

dev:
	uv run uvicorn app.main:app --reload --port 8003

lint:
	uv run ruff check .

format:
	uv run ruff check . --fix
	uv run ruff format .

format-check:
	uv run ruff format . --check

test:
	uv run pytest tests/unit/ -v
	uv run pytest tests/integration/ -v

test-unit:
	uv run pytest tests/unit/ -v

test-integration:
	uv run pytest tests/integration/ -v

migrate:
	uv run alembic upgrade head

migrate-down:
	uv run alembic downgrade -1

clean:
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
