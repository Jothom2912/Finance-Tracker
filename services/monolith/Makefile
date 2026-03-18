SHELL := /bin/bash
.PHONY: help install-deps dev test test-unit test-integration lint format format-check check clean

help: ## Show available targets
	@printf 'Available targets:\n'
	@printf '  install-deps        Install all dependencies\n'
	@printf '  dev                 Start monolith with hot-reload on port 8000\n'
	@printf '  test                Run all tests\n'
	@printf '  test-unit           Run unit tests only\n'
	@printf '  test-integration    Run integration tests only\n'
	@printf '  lint                Run ruff linter\n'
	@printf '  format              Auto-format code with ruff\n'
	@printf '  format-check        Check code formatting\n'
	@printf '  check               Run all quality checks\n'
	@printf '  clean               Remove generated artifacts\n'

install-deps: ## Install all dependencies (prod + dev)
	uv sync --dev

dev: ## Start monolith with hot-reload on port 8000
	uv run uvicorn backend.main:app --reload --port 8000

test: ## Run all tests
	uv run pytest tests/ -v

test-unit: ## Run unit tests only
	uv run pytest tests/unittests/ -v

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

clean: ## Remove generated artifacts
	rm -rf .venv .pytest_cache .ruff_cache .coverage *.egg-info
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
