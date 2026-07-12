SHELL := /bin/bash
.PHONY: help install-deps dev test test-unit lint format format-check check clean

help: ## Show available targets
	@printf 'Available targets:\n'
	@printf '  install-deps        Install all dependencies\n'
	@printf '  dev                 Start service with hot-reload on port 8004\n'
	@printf '  test                Run all tests\n'
	@printf '  test-unit           Run unit tests only\n'
	@printf '  lint                Run ruff linter\n'
	@printf '  format              Auto-format code with ruff\n'
	@printf '  format-check        Check code formatting\n'
	@printf '  check               Run all quality checks\n'
	@printf '  clean               Remove generated artifacts\n'

install-deps: ## Install all dependencies (prod + dev)
	uv sync --dev

dev: ## Start service with hot-reload on port 8004
	uv run uvicorn app.main:app --reload --port 8004

test: ## Run all tests (except live-Ollama eval — see test-eval)
	uv run pytest tests/ -v -m "not eval"

test-unit: ## Run unit tests only
	uv run pytest tests/unit/ -v

test-eval: ## Run the AI-01 quality eval (needs live Ollama with bge-m3 + qwen3:4b, e.g. OLLAMA_BASE_URL=http://localhost:11435)
	uv run pytest tests/eval/ -v -m eval -s

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
