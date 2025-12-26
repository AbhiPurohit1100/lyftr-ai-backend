.PHONY: help up down logs test build clean dev

help: ## Show this help message
	@echo 'Usage: make [target]'
	@echo ''
	@echo 'Available targets:'
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  %-15s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

up: ## Start all services in detached mode
	docker compose up -d --build

down: ## Stop and remove all containers and volumes
	docker compose down -v

logs: ## Follow logs from API service
	docker compose logs -f api

test: ## Run tests
	pytest tests/ -v --cov=app --cov-report=term-missing

build: ## Build Docker image
	docker compose build

clean: ## Remove all containers, volumes, and images
	docker compose down -v --rmi all

dev: ## Run development server locally
	uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

install: ## Install dependencies locally
	pip install -r requirements.txt

format: ## Format code with black
	black app/ tests/

lint: ## Lint code with flake8
	flake8 app/ tests/

type-check: ## Run type checking with mypy
	mypy app/

check: format lint type-check test ## Run all checks
