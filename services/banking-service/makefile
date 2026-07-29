SHELL := /bin/bash
.PHONY: help install-deps dev test test-unit test-integration lint typecheck format format-check security check migrate migrate-down clean

help:
	@printf 'Available targets:\n'
	@printf '  install-deps     Install all dependencies (runtime + dev)\n'
	@printf '  dev              Start service with hot-reload on port 8009\n'
	@printf '  test             Run unit + integration tests\n'
	@printf '  test-unit        Run unit tests only\n'
	@printf '  test-integration Run integration tests only\n'
	@printf '  lint             Run ruff linter\n'
	@printf '  typecheck        Run mypy (P2-31 gate)\n'
	@printf '  format           Auto-format code with ruff\n'
	@printf '  security         Run bandit\n'
	@printf '  check            Run lint + format check + typecheck + security + tests\n'
	@printf '  migrate          Run database migrations to latest\n'
	@printf '  migrate-down     Rollback last migration\n'
	@printf '  clean            Remove generated artifacts\n'

install-deps:
	uv sync --dev

dev:
	uv run uvicorn app.main:app --reload --port 8009

# P3-23: the PYTHONPATH=../shared/contracts:../shared prefix these targets carried is
# gone. The three shared packages are declared path-dependencies now, so they are in
# the venv. Keeping both would give pytest the source tree and mypy the installed
# copy — two sources of truth for one package, which is the mistake budget-service's
# makefile documents from the other side.
test:
	uv run pytest tests/unit -v
	uv run pytest tests/integration -v

test-unit:
	uv run pytest tests/unit -v

test-integration:
	uv run pytest tests/integration -v

lint:
	uv run ruff check .

# P2-31/P3-23: config lives in pyproject's [tool.mypy]. No MYPYPATH — shared/* resolve
# as installed packages via py.typed; pointing mypy at their source as well is what
# produces "Source file found twice". The venv is the single source of truth.
typecheck:
	uv run mypy

format:
	uv run ruff check . --fix
	uv run ruff format .

format-check:
	uv run ruff format --check .

# -ll -ii skal matche ci.yml (jobbene `python-services` og `shared-packages`).
# Uden flagene er lokal bandit strengere end gaten, og `make check` er rød på
# Low-fund CI aldrig har håndhævet. P3-49.
security:
	uv run bandit -r app -x tests -ll -ii

check: lint format-check typecheck security test

migrate:
	uv run alembic upgrade head

migrate-down:
	uv run alembic downgrade -1

clean:
	rm -rf .pytest_cache .ruff_cache htmlcov .coverage
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
