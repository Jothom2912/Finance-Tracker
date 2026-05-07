SHELL := /bin/bash
.PHONY: help install-deps dev test test-unit test-integration lint format migrate migrate-down clean

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
	pip install -r requirements.txt

dev:
	uvicorn app.main:app --reload --port 8003

test:
	pytest tests/unit/ -v
	pytest tests/integration/ -v

test-unit:
	pytest tests/unit/ -v

test-integration:
	pytest tests/integration/ -v

lint:
	ruff check .

format:
	ruff format .
	ruff check --fix .

migrate:
	alembic upgrade head

migrate-down:
	alembic downgrade -1

clean:
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
