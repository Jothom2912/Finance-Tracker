SHELL := /bin/bash
.PHONY: help install-deps dev test test-unit test-integration lint typecheck format format-check check migrate migrate-down clean
help:
	@printf 'Available targets:\n'
	@printf '  install-deps     Install all dependencies\n'
	@printf '  dev              Start service with hot-reload on port 8003\n'
	@printf '  test             Run unit + integration tests\n'
	@printf '  test-unit        Run unit tests only\n'
	@printf '  test-integration Run integration tests only\n'
	@printf '  lint             Run ruff linter\n'
	@printf '  typecheck        Run mypy (P2-31 gate)\n'
	@printf '  format           Auto-format code with ruff\n'
	@printf '  check            Run lint + format checks\n'
	@printf '  migrate          Run database migrations to latest\n'
	@printf '  migrate-down     Rollback last migration\n'
	@printf '  clean            Remove generated artifacts\n'

install-deps:
	uv sync --dev

dev:
	uv run uvicorn app.main:app --reload --port 8003

lint:
	uv run ruff check .

# P2-31: config lives in pyproject's [tool.mypy]. No MYPYPATH — shared/* resolve
# as installed packages via py.typed; pointing mypy at their source as well is
# what produces "Source file found twice". The venv is the single source of truth.
typecheck:
	uv run mypy

format:
	uv run ruff check . --fix
	uv run ruff format .

format-check:
	uv run ruff format . --check

check: lint format-check typecheck

# The PYTHONPATH=../../services/shared/contracts prefix these targets used to carry
# is gone: contracts is now a declared path-dependency, so it is in the venv like
# the other three shared packages. Keeping both would give tests the source tree and
# mypy the installed copy — two sources of truth for one package.
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
