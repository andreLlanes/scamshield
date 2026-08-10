.DEFAULT_GOAL := help
PY  := backend/.venv/bin/python
PIP := backend/.venv/bin/pip
ifeq ($(OS),Windows_NT)
	PY  := backend/.venv/Scripts/python.exe
	PIP := backend/.venv/Scripts/pip.exe
endif

.PHONY: help setup setup-backend setup-frontend setup-full train seed \
        dev-backend dev-frontend test test-backend test-frontend lint format \
        docker-up docker-down clean

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
	 awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'

setup: setup-backend setup-frontend ## Install everything and prepare the models

setup-backend: ## Create the venv, install deps, train the classifier, seed the KB
	cd backend && python -m venv .venv
	$(PIP) install --upgrade pip
	$(PIP) install -e "backend[ml,dev]"
	cd backend && ../$(PY) -m scripts.train_classifier
	cd backend && ../$(PY) -m scripts.seed_knowledge_base

setup-frontend: ## Install frontend dependencies
	cd frontend && npm install

setup-full: ## Install every optional extra (Whisper, ChromaDB, CrewAI)
	$(PIP) install -e "backend[ml,asr,rag,agents,dev]"

train: ## Retrain the scam classifier
	cd backend && ../$(PY) -m scripts.train_classifier

seed: ## Rebuild the knowledge-base index
	cd backend && ../$(PY) -m scripts.seed_knowledge_base

dev-backend: ## Run the API with reload on :8000
	cd backend && ../$(PY) -m uvicorn app.main:app --reload --port 8000

dev-frontend: ## Run the Next.js dev server on :3000
	cd frontend && npm run dev

test: test-backend test-frontend ## Run all checks

test-backend: ## pytest
	cd backend && ../$(PY) -m pytest -q

test-frontend: ## typecheck, lint and build
	cd frontend && npm run typecheck && npm run lint && npm run build

lint: ## ruff + mypy
	cd backend && ../$(PY) -m ruff check .
	cd backend && ../$(PY) -m mypy app

format: ## ruff format + import sort
	cd backend && ../$(PY) -m ruff format .
	cd backend && ../$(PY) -m ruff check --fix .

docker-up: ## Build and start the full stack
	docker compose up --build

docker-down: ## Stop the stack
	docker compose down

clean: ## Remove build artifacts and caches
	rm -rf backend/.pytest_cache backend/.ruff_cache backend/.mypy_cache
	rm -rf frontend/.next frontend/out
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
