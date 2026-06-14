SHELL := /bin/bash
.PHONY: install-deps test test-unit test-integration lint format format-check security check clean

install-deps:
	python -m pip install --upgrade pip
	python -m pip install -r requirements.txt pytest ruff bandit

test:
	PYTHONPATH=../shared/contracts:../shared:. pytest tests -v

test-unit:
	PYTHONPATH=../shared/contracts:../shared:. pytest tests/unit -v

test-integration:
	PYTHONPATH=../shared/contracts:../shared:. pytest tests/integration -v

lint:
	ruff check .

format:
	ruff format .

format-check:
	ruff format --check .

security:
	bandit -r app -x tests

check: lint format-check security test

clean:
	rm -rf .pytest_cache .ruff_cache htmlcov .coverage
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
