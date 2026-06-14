SHELL := /bin/bash
.PHONY: help install-deps dev dev-docker dev-user-service dev-transaction-service dev-account-service dev-categorization-service dev-budget-service dev-goal-service dev-frontend down logs build test test-e2e lint format format-check check clean clean-test-containers

INFRA_SERVICES = postgres postgres-transactions postgres-categorization postgres-account postgres-budget postgres-goals postgres-banking rabbitmq redis
USER_SERVICE_DIR = services/user-service
TX_SERVICE_DIR = services/transaction-service
CAT_SERVICE_DIR = services/categorization-service
ACCOUNT_SERVICE_DIR = services/account-service
BUDGET_SERVICE_DIR = services/budget-service
GOAL_SERVICE_DIR = services/goal-service
FRONTEND_DIR = services/frontend

help: ## Show available targets
	@printf '\nAvailable targets:\n\n'
	@printf '  [Setup]\n'
	@printf '    install-deps              Install deps for all services\n\n'
	@printf '  [Development]\n'
	@printf '    dev                       Start infra and print instructions\n'
	@printf '    dev-docker                Start everything in Docker containers\n'
	@printf '    dev-user-service          Start user-service locally (port 8001)\n'
	@printf '    dev-transaction-service   Start transaction-service locally (port 8002)\n'
	@printf '    dev-budget-service        Start budget-service locally (port 8003)\n'
	@printf '    dev-account-service       Start account-service locally (port 8004)\n'
	@printf '    dev-categorization-service Start categorization-service locally (port 8005)\n'
	@printf '    dev-goal-service          Start goal-service locally (port 8006)\n'
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
	$(MAKE) -C $(USER_SERVICE_DIR) install-deps
	$(MAKE) -C $(TX_SERVICE_DIR) install-deps
	$(MAKE) -C $(CAT_SERVICE_DIR) install-deps
	$(MAKE) -C $(BUDGET_SERVICE_DIR) install-deps
	$(MAKE) -C $(GOAL_SERVICE_DIR) install-deps
	$(MAKE) -C $(FRONTEND_DIR) install-deps

# === Development ===

dev: ## Start infrastructure and print service start instructions
	docker compose up -d --wait $(INFRA_SERVICES)
	@printf '\nInfrastructure ready. Start services in separate terminals:\n'
	@printf '  make dev-user-service           (port 8001)\n'
	@printf '  make dev-transaction-service    (port 8002)\n'
	@printf '  make dev-budget-service         (port 8003)\n'
	@printf '  make dev-account-service        (port 8004)\n'
	@printf '  make dev-categorization-service (port 8005)\n'
	@printf '  make dev-goal-service           (port 8006)\n'
	@printf '  make dev-frontend               (port 5173)\n\n'

dev-docker: ## Start everything in Docker (infra + all services)
	docker compose up -d --build

dev-user-service: ## Start user-service locally with hot-reload
	$(MAKE) -C $(USER_SERVICE_DIR) dev

dev-transaction-service: ## Start transaction-service locally with hot-reload
	$(MAKE) -C $(TX_SERVICE_DIR) dev

dev-categorization-service: ## Start categorization-service locally with hot-reload
	$(MAKE) -C $(CAT_SERVICE_DIR) dev

dev-budget-service: ## Start budget-service locally with hot-reload
	$(MAKE) -C $(BUDGET_SERVICE_DIR) dev

dev-goal-service: ## Start goal-service locally with hot-reload
	$(MAKE) -C $(GOAL_SERVICE_DIR) dev

dev-account-service: ## Start account-service locally with hot-reload
	$(MAKE) -C $(ACCOUNT_SERVICE_DIR) dev

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
	$(MAKE) -C $(USER_SERVICE_DIR) test
	$(MAKE) -C $(TX_SERVICE_DIR) test
	$(MAKE) -C $(CAT_SERVICE_DIR) test
	$(MAKE) -C $(BUDGET_SERVICE_DIR) test
	$(MAKE) -C $(GOAL_SERVICE_DIR) test
	$(MAKE) -C $(FRONTEND_DIR) test

test-e2e: ## Run E2E tests (requires Docker services running)
	uv run pytest tests/e2e/ -v -m e2e

lint: ## Run ruff linter on all Python services
	$(MAKE) -C $(USER_SERVICE_DIR) lint
	$(MAKE) -C $(TX_SERVICE_DIR) lint
	$(MAKE) -C $(CAT_SERVICE_DIR) lint
	$(MAKE) -C $(BUDGET_SERVICE_DIR) lint
	$(MAKE) -C $(GOAL_SERVICE_DIR) lint

format: ## Auto-format all Python services
	$(MAKE) -C $(USER_SERVICE_DIR) format
	$(MAKE) -C $(TX_SERVICE_DIR) format
	$(MAKE) -C $(CAT_SERVICE_DIR) format
	$(MAKE) -C $(BUDGET_SERVICE_DIR) format
	$(MAKE) -C $(GOAL_SERVICE_DIR) format

format-check: ## Check code formatting without changes
	$(MAKE) -C $(USER_SERVICE_DIR) format-check
	$(MAKE) -C $(TX_SERVICE_DIR) format-check
	$(MAKE) -C $(CAT_SERVICE_DIR) format-check
	$(MAKE) -C $(BUDGET_SERVICE_DIR) format-check
	$(MAKE) -C $(GOAL_SERVICE_DIR) format-check

check: ## Run all quality checks (lint + format + tests)
	$(MAKE) -C $(USER_SERVICE_DIR) check
	$(MAKE) -C $(TX_SERVICE_DIR) check
	$(MAKE) -C $(CAT_SERVICE_DIR) check
	$(MAKE) -C $(BUDGET_SERVICE_DIR) check
	$(MAKE) -C $(GOAL_SERVICE_DIR) check
	$(MAKE) -C $(FRONTEND_DIR) check

# === Cleanup ===

clean-test-containers: ## Remove orphaned Testcontainers (Windows/Docker Desktop workaround)
	@echo "Removing containers with org.testcontainers=true label..."
	docker rm -f $$(docker ps -aq --filter "label=org.testcontainers=true") 2>/dev/null || echo "No orphaned test containers found."

clean: ## Remove all generated artifacts
	$(MAKE) -C $(USER_SERVICE_DIR) clean
	$(MAKE) -C $(TX_SERVICE_DIR) clean
	$(MAKE) -C $(CAT_SERVICE_DIR) clean
	$(MAKE) -C $(BUDGET_SERVICE_DIR) clean
	$(MAKE) -C $(GOAL_SERVICE_DIR) clean
	$(MAKE) -C $(FRONTEND_DIR) clean
