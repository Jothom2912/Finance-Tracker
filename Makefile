SHELL := /bin/bash
.PHONY: help install-deps install-hooks ci-status verify-typecheck-gate notes-check compose-check dev dev-docker dev-user-service dev-transaction-service dev-account-service dev-categorization-service dev-budget-service dev-goal-service dev-frontend down logs build test test-e2e lint lint-repo format format-check check clean clean-test-containers

INFRA_SERVICES = postgres postgres-transactions postgres-categorization postgres-account postgres-budget postgres-goals postgres-banking rabbitmq redis
USER_SERVICE_DIR = services/user-service
TX_SERVICE_DIR = services/transaction-service
CAT_SERVICE_DIR = services/categorization-service
ACCOUNT_SERVICE_DIR = services/account-service
BUDGET_SERVICE_DIR = services/budget-service
GOAL_SERVICE_DIR = services/goal-service
GATEWAY_SERVICE_DIR = services/gateway-service
AI_SERVICE_DIR = services/ai-service
BANKING_SERVICE_DIR = services/banking-service
SAGA_SERVICE_DIR = services/saga-service
ANALYTICS_SERVICE_DIR = services/analytics-service
NOTIFICATION_SERVICE_DIR = services/notification-service
FRONTEND_DIR = services/frontend

# All Python services with a Makefile — keep in sync with the CI matrix
# in .github/workflows/ci.yml.
PY_SERVICE_DIRS = \
	$(USER_SERVICE_DIR) \
	$(TX_SERVICE_DIR) \
	$(CAT_SERVICE_DIR) \
	$(ACCOUNT_SERVICE_DIR) \
	$(BUDGET_SERVICE_DIR) \
	$(GOAL_SERVICE_DIR) \
	$(GATEWAY_SERVICE_DIR) \
	$(AI_SERVICE_DIR) \
	$(BANKING_SERVICE_DIR) \
	$(SAGA_SERVICE_DIR) \
	$(ANALYTICS_SERVICE_DIR) \
	$(NOTIFICATION_SERVICE_DIR)

help: ## Show available targets
	@printf '\nAvailable targets:\n\n'
	@printf '  [Setup]\n'
	@printf '    install-deps              Install deps for all services\n'
	@printf '    install-hooks             Enable tracked git hooks (once per clone)\n\n'
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
	@printf '    lint-repo                 Lint+format-check whole repo (incl. scripts/, tests/)\n'
	@printf '    ci-status                 Latest CI run for this branch (exit 1 if red)\n'
	@printf '    verify-typecheck-gate     Prove the mypy gate covers exactly its allowlist\n'
	@printf '    notes-check               dev-notes index drift, dead links, frontmatter\n'
	@printf '    compose-check             build hygiene: worker image drift + install paths\n'
	@printf '    format                    Auto-format all Python services\n'
	@printf '    format-check              Check formatting without changes\n'
	@printf '    check                     Run all quality checks\n'
	@printf '    clean                     Remove generated artifacts\n'
	@printf '    clean-test-containers     Remove orphaned Testcontainers\n\n'

# === Setup ===

install-deps: ## Install dependencies for all services
	@set -e; for dir in $(PY_SERVICE_DIRS); do $(MAKE) -C $$dir install-deps; done
	$(MAKE) -C $(FRONTEND_DIR) install-deps

# Hooks live in .githooks/ so they are version-controlled; .git/hooks is not
# cloned, so this must be run once per clone.
install-hooks: ## Enable the tracked git hooks (run once per clone)
	git config core.hooksPath .githooks
	@echo "core.hooksPath -> .githooks (pre-commit: ruff check + format on staged .py)"

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
	@set -e; for dir in $(PY_SERVICE_DIRS); do $(MAKE) -C $$dir test; done
	$(MAKE) -C $(FRONTEND_DIR) test

# Loader .env så testene signerer med samme JWT_SECRET som compose
# interpolerer ind i stakken (P2-26). Uden det fejler de med en besked om
# den manglende variabel frem for et vildledende 401. CI sætter variablerne
# som job-env og har ingen .env — deraf `[ -f .env ]`.
# Der er ingen pyproject.toml i repo-roden, så `uv run pytest` fandt ingen
# pytest og målet har aldrig kunnet køre lokalt — kun CI virkede, fordi den
# pip-installerer pytest selv. --with giver et ephemeral env med samme
# afhængigheder som CI's e2e-job.
test-e2e: ## Run E2E tests (requires Docker services running)
	set -a; [ -f .env ] && . ./.env; set +a; \
	uv run --with pytest --with pytest-asyncio --with httpx \
	       --with python-jose --with requests \
	       pytest tests/e2e/ -v -m e2e

lint: ## Run ruff linter on all Python services
	@set -e; for dir in $(PY_SERVICE_DIRS); do $(MAKE) -C $$dir lint; done

format: ## Auto-format all Python services
	@set -e; for dir in $(PY_SERVICE_DIRS); do $(MAKE) -C $$dir format; done

format-check: ## Check code formatting without changes
	@set -e; for dir in $(PY_SERVICE_DIRS); do $(MAKE) -C $$dir format-check; done

# The per-service targets above iterate PY_SERVICE_DIRS, which leaves scripts/
# and the root tests/ unlinted — both had drifted unnoticed. No service defines
# its own [tool.ruff], so one invocation from the root is correct everywhere.
# Mirrored by the repo-lint job in .github/workflows/ci.yml.
lint-repo: ## Lint + format-check the WHOLE repo, incl. scripts/ and tests/
	uvx ruff check services scripts tests
	uvx ruff format --check services scripts tests

# Detection half of the CI feedback loop (the hook is the prevention half).
# Stdlib-only and unauthenticated — this repo is public, so run/job/step
# conclusions are readable without `gh`. GH_TOKEN lifts the 60/hour cap.
ci-status: ## Show the latest CI run for the current branch (exit 1 if red)
	@python3 scripts/ci_status.py

# P2-31 Kontrol C. The typecheck step runs for every python-service (the
# allowlist is a conditional inside the shell body), so its conclusion is
# `success` everywhere and proves nothing. This reads the run annotations
# instead: a ::notice for each non-gated service, none for the gated ones.
# Re-run it whenever a service joins the allowlist — both counts must move.
verify-typecheck-gate: ## Prove the mypy gate covers exactly its allowlist (P2-31 Kontrol C)
	@python3 scripts/verify_typecheck_gate.py

# The vault's index, links and frontmatter are maintained by hand, so they drift
# silently — a 2026-07-27 review found an open finding that had never been
# indexed. Stdlib-only, runs in well under a second.
notes-check: ## Check dev-notes/ for index drift, dead links and bad frontmatter
	@python3 scripts/notes_check.py

# Two build-hygiene rules with one symptom in common: a green run that proves
# nothing. P3-40 — workers must share their API service's image, not fork a second
# one off the same Dockerfile. P2-37 — a service must not carry both `uv.lock` and
# `requirements.txt`, or its tests and its image install different versions. Both
# regressions show up as a *passing* verification against code that isn't shipping,
# so neither can be left to review. Stdlib-only, sub-second.
compose-check: ## Build hygiene: worker image drift (P3-40) + one install path per service (P2-37)
	@python3 scripts/compose_check.py

check: ## Run all quality checks (lint + format + tests)
	@set -e; for dir in $(PY_SERVICE_DIRS); do $(MAKE) -C $$dir check; done
	$(MAKE) -C $(FRONTEND_DIR) check

# === Cleanup ===

clean-test-containers: ## Remove orphaned Testcontainers (Windows/Docker Desktop workaround)
	@echo "Removing containers with org.testcontainers=true label..."
	docker rm -f $$(docker ps -aq --filter "label=org.testcontainers=true") 2>/dev/null || echo "No orphaned test containers found."

clean: ## Remove all generated artifacts
	@set -e; for dir in $(PY_SERVICE_DIRS); do $(MAKE) -C $$dir clean; done
	$(MAKE) -C $(FRONTEND_DIR) clean
