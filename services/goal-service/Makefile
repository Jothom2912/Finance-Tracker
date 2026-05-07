SHELL := /bin/bash

.PHONY: help install-deps dev test lint format format-check check migrate migrate-down clean

help:
	@printf 'Available targets:\n'
	@printf '  install-deps     Install dependencies with uv\n'
	@printf '  dev              Start service with hot-reload on port 8006\n'
	@printf '  test             Run unit and integration tests\n'
	@printf '  lint             Run ruff linter\n'
	@printf '  format           Auto-format code with ruff\n'
	@printf '  format-check     Check formatting with ruff\n'
	@printf '  check            Run formatting and lint checks\n'
	@printf '  migrate          Run database migrations\n'
	@printf '  migrate-down     Roll back one migration\n'
	@printf '  clean            Remove generated artifacts\n'

install-deps:
	uv sync --dev

dev:
	uv run uvicorn app.main:app --reload --port 8006

test:
	uv run pytest tests/ -q

lint:
	uv run ruff check app/ tests/

format:
	uv run ruff format app/ tests/
	uv run ruff check --fix app/ tests/

format-check:
	uv run ruff format --check app/ tests/

check: format-check lint

migrate:
	uv run alembic upgrade head

migrate-down:
	uv run alembic downgrade -1

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name '*.pyc' -delete
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .ruff_cache -exec rm -rf {} + 2>/dev/null || true
	rm -rf .coverage htmlcov/ dist/ build/ *.egg-info/
