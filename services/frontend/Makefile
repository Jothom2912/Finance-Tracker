SHELL := /bin/bash
.PHONY: help install-deps dev build test test-run lint lint-fix check clean

help: ## Show available targets
	@printf 'Available targets:\n'
	@printf '  install-deps        Install all dependencies\n'
	@printf '  dev                 Start dev server with hot-reload\n'
	@printf '  build               Build for production\n'
	@printf '  test                Run all tests (watch mode)\n'
	@printf '  test-run            Run tests once (CI mode)\n'
	@printf '  lint                Run ESLint\n'
	@printf '  lint-fix            Auto-fix ESLint errors\n'
	@printf '  check               Run all quality checks\n'
	@printf '  clean               Remove generated artifacts\n'

install-deps: ## Install all dependencies
	npm install

dev: ## Start dev server with hot-reload
	npm run dev

build: ## Build for production
	npm run build

test: ## Run all tests
	npm test

test-run: ## Run tests once (non-watch)
	npx vitest run

lint: ## Run ESLint
	npx eslint src/

lint-fix: ## Auto-fix ESLint errors
	npx eslint src/ --fix

check: lint test-run ## Run all quality checks

clean: ## Remove generated artifacts
	rm -rf node_modules build
