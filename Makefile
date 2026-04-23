SHELL := /bin/bash
.PHONY: help install-deps dev dev-docker dev-backend dev-user-service dev-transaction-service dev-frontend down logs build test test-e2e lint format format-check check clean clean-test-containers cleanup-mysql-duplicates-once

INFRA_SERVICES = mysql postgres postgres-transactions rabbitmq
BACKEND_DIR = services/monolith
USER_SERVICE_DIR = services/user-service
TX_SERVICE_DIR = services/transaction-service
FRONTEND_DIR = services/frontend

help: ## Show available targets
	@printf '\nAvailable targets:\n\n'
	@printf '  [Setup]\n'
	@printf '    install-deps              Install deps for all services\n\n'
	@printf '  [Development]\n'
	@printf '    dev                       Start infra and print instructions\n'
	@printf '    dev-docker                Start everything in Docker containers\n'
	@printf '    dev-backend               Start backend locally (port 8000)\n'
	@printf '    dev-user-service          Start user-service locally (port 8001)\n'
	@printf '    dev-transaction-service   Start transaction-service locally (port 8002)\n'
	@printf '    dev-frontend              Start frontend locally (port 5173)\n'
	@printf '    down                      Stop all Docker containers\n'
	@printf '    logs                      Tail Docker container logs\n'
	@printf '    build                     Build all Docker images\n\n'
	@printf '  [Quality]\n'
	@printf '    test                      Run all tests\n'
	@printf '    test-e2e                  Run E2E tests (requires Docker)\n'
	@printf '    lint                      Run ruff linter on all Python services\n'
	@printf '    format                    Auto-format all Python services\n'
	@printf '    format-check              Check formatting without changes\n'
	@printf '    check                     Run all quality checks\n'
	@printf '    clean                     Remove generated artifacts\n'
	@printf '    clean-test-containers     Remove orphaned Testcontainers\n\n'

# === Setup ===

install-deps: ## Install dependencies for all services
	$(MAKE) -C $(BACKEND_DIR) install-deps
	$(MAKE) -C $(USER_SERVICE_DIR) install-deps
	$(MAKE) -C $(TX_SERVICE_DIR) install-deps
	$(MAKE) -C $(FRONTEND_DIR) install-deps

# === Development ===

dev: ## Start infrastructure and print service start instructions
	docker compose up -d --wait $(INFRA_SERVICES)
	@printf '\nInfrastructure ready. Start services in separate terminals:\n'
	@printf '  make dev-backend                (port 8000)\n'
	@printf '  make dev-user-service           (port 8001)\n'
	@printf '  make dev-transaction-service    (port 8002)\n'
	@printf '  make dev-frontend               (port 5173)\n\n'

dev-docker: ## Start everything in Docker (infra + all services)
	docker compose up -d --build

dev-backend: ## Start backend locally with hot-reload
	$(MAKE) -C $(BACKEND_DIR) dev

dev-user-service: ## Start user-service locally with hot-reload
	$(MAKE) -C $(USER_SERVICE_DIR) dev

dev-transaction-service: ## Start transaction-service locally with hot-reload
	$(MAKE) -C $(TX_SERVICE_DIR) dev

dev-frontend: ## Start frontend locally with hot-reload
	$(MAKE) -C $(FRONTEND_DIR) dev

down: ## Stop all Docker containers
	docker compose down

logs: ## Tail Docker container logs
	docker compose logs -f

build: ## Build all Docker images
	docker compose build

# === Quality ===

test: ## Run tests for all services
	$(MAKE) -C $(BACKEND_DIR) test
	$(MAKE) -C $(USER_SERVICE_DIR) test
	$(MAKE) -C $(TX_SERVICE_DIR) test
	$(MAKE) -C $(FRONTEND_DIR) test

test-e2e: ## Run E2E tests (requires Docker services running)
	uv run pytest tests/e2e/ -v -m e2e

lint: ## Run ruff linter on all Python services
	$(MAKE) -C $(BACKEND_DIR) lint
	$(MAKE) -C $(USER_SERVICE_DIR) lint
	$(MAKE) -C $(TX_SERVICE_DIR) lint

format: ## Auto-format all Python services
	$(MAKE) -C $(BACKEND_DIR) format
	$(MAKE) -C $(USER_SERVICE_DIR) format
	$(MAKE) -C $(TX_SERVICE_DIR) format

format-check: ## Check code formatting without changes
	$(MAKE) -C $(BACKEND_DIR) format-check
	$(MAKE) -C $(USER_SERVICE_DIR) format-check
	$(MAKE) -C $(TX_SERVICE_DIR) format-check

check: ## Run all quality checks (lint + format + tests)
	$(MAKE) -C $(BACKEND_DIR) check
	$(MAKE) -C $(USER_SERVICE_DIR) check
	$(MAKE) -C $(TX_SERVICE_DIR) check
	$(MAKE) -C $(FRONTEND_DIR) check

# === Cleanup ===

# ONE-OFF: Remove this target after running successfully.
cleanup-mysql-duplicates-once: ## Reconcile MySQL Transaction duplicates against PostgreSQL
	@echo "Running in dry-run mode by default. Pass EXECUTE=1 for actual deletion."
	@if [ "$(EXECUTE)" = "1" ]; then \
		uv run python scripts/cleanup_mysql_duplicates.py --execute; \
	else \
		uv run python scripts/cleanup_mysql_duplicates.py; \
	fi

clean-test-containers: ## Remove orphaned Testcontainers (Windows/Docker Desktop workaround)
	@echo "Removing containers with org.testcontainers=true label..."
	docker rm -f $$(docker ps -aq --filter "label=org.testcontainers=true") 2>/dev/null || echo "No orphaned test containers found."

clean: ## Remove all generated artifacts
	$(MAKE) -C $(BACKEND_DIR) clean
	$(MAKE) -C $(USER_SERVICE_DIR) clean
	$(MAKE) -C $(TX_SERVICE_DIR) clean
	$(MAKE) -C $(FRONTEND_DIR) clean
