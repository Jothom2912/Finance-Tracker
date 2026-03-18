SHELL := /bin/bash
.PHONY: help install-deps dev build test lint check clean

help: ## Show available targets
	@printf 'Available targets:\n'
	@printf '  install-deps        Install all dependencies\n'
	@printf '  dev                 Start dev server with hot-reload\n'
	@printf '  build               Build for production\n'
	@printf '  test                Run all tests\n'
	@printf '  lint                Run linter (TODO: add eslint)\n'
	@printf '  check               Run all quality checks\n'
	@printf '  clean               Remove generated artifacts\n'

install-deps: ## Install all dependencies
	yarn install

dev: ## Start dev server with hot-reload
	yarn dev

build: ## Build for production
	yarn build

test: ## Run all tests
	yarn test

lint: ## Run linter
	@printf 'TODO: add eslint - skipping for now\n'

check: test ## Run all quality checks

clean: ## Remove generated artifacts
	rm -rf node_modules dist
