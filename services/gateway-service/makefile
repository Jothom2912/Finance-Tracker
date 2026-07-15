SHELL := /bin/bash
.PHONY: install-deps test test-unit test-integration lint format format-check security check clean

install-deps:
	uv sync --dev

test:
	uv run pytest tests -v

test-unit:
	uv run pytest tests/unit -v

test-integration:
	uv run pytest tests/integration -v

lint:
	uv run ruff check .

format:
	uv run ruff format .

format-check:
	uv run ruff format --check .

security:
	uv run bandit -r app -x tests

check: lint format-check security test

clean:
	rm -rf .pytest_cache .ruff_cache htmlcov .coverage
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
