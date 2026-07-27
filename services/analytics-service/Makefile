SHELL := /bin/bash

.PHONY: help install-deps test lint typecheck format format-check check clean

help:
	@printf 'Available targets:\n'
	@printf '  install-deps     Install dependencies with uv\n'
	@printf '  test             Run all tests (integration requires Docker for ES Testcontainer)\n'
	@printf '  lint             Run ruff linter\n'
	@printf '  typecheck        Run mypy (P2-31 pilot — this service is the gate)\n'
	@printf '  format           Auto-format code with ruff\n'
	@printf '  format-check     Check formatting with ruff\n'
	@printf '  check            Run formatting, lint and type checks\n'
	@printf '  clean            Remove generated artifacts\n'

install-deps:
	uv sync --dev

test:
	uv run pytest tests/ -q

lint:
	uv run ruff check app/ tests/

# P2-31: this is the pilot service for the typecheck gate. Config lives in
# pyproject's [tool.mypy]; no MYPYPATH here on purpose — shared/{contracts,domain}
# are resolved as *installed* packages via py.typed, and pointing mypy at their
# source as well is what produces goal-service's "Source file found twice under
# different module names". The venv is the single source of truth.
typecheck:
	uv run mypy

format:
	uv run ruff format app/ tests/
	uv run ruff check --fix app/ tests/

format-check:
	uv run ruff format --check app/ tests/

check: format-check lint typecheck

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name '*.pyc' -delete
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .ruff_cache -exec rm -rf {} + 2>/dev/null || true
	rm -rf .coverage htmlcov/ dist/ build/ *.egg-info/
