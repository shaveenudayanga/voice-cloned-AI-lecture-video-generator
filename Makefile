SHELL := /bin/bash
.DEFAULT_GOAL := help

COMPOSE := docker compose -f infra/docker-compose.yml
COMPOSE_GPU := $(COMPOSE) -f infra/docker-compose.gpu.yml
COMPOSE_PROD := $(COMPOSE) -f infra/docker-compose.prod.yml

.PHONY: help up down up-gpu test lint typecheck migrate license-audit check-env seed install first-run release

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

check-env: ## Warn if host environment does not meet recommendations
	@echo "--- Environment check ---"
	@python3 --version 2>&1 | grep -q "3\.13" \
		|| echo "WARNING: Host Python is not 3.13. Application runs in Docker (python:3.13-slim)." \
		         " Host Python is only needed for out-of-container scripts."
	@node --version 2>&1 | grep -q "v24" \
		|| echo "WARNING: Host Node.js is not v24 LTS. Frontend builds inside Docker."
	@docker info > /dev/null 2>&1 \
		|| (echo "ERROR: Docker is not running or not installed. See docs/runbook.md for setup instructions." && exit 1)
	@echo "Docker: OK"
	@echo "--- End environment check ---"

up: check-env ## Start all services (API, frontend, postgres, valkey, seaweedfs, worker-cpu)
	$(COMPOSE) up --build -d

down: ## Stop and remove all containers (data volumes are preserved)
	$(COMPOSE) down

up-gpu: check-env ## Start all services including GPU worker
	$(COMPOSE_GPU) up --build -d

up-prod: check-env ## Start production stack (adds nginx)
	$(COMPOSE_PROD) up --build -d

logs: ## Tail all service logs
	$(COMPOSE) logs -f

test: ## Run backend unit tests + frontend unit tests
	cd backend && \
		API_KEY=test-api-key DATABASE_URL=postgresql+asyncpg://test:test@localhost/test \
		uv run pytest tests/unit -v
	cd frontend && pnpm test:unit

test-all: ## Run all backend tests (requires running infra)
	cd backend && \
		API_KEY=test-api-key DATABASE_URL=postgresql+asyncpg://lecturevoice:lecturevoice@localhost/lecturevoice \
		uv run pytest -v

lint: ## Run ruff linter and ESLint
	@echo "--- Backend lint ---"
	cd backend && uv run ruff check app tests
	@echo "--- Frontend lint ---"
	cd frontend && pnpm lint

typecheck: ## Run mypy (backend) and tsc (frontend)
	@echo "--- Backend typecheck ---"
	cd backend && uv run mypy app
	@echo "--- Frontend typecheck ---"
	cd frontend && pnpm typecheck

format: ## Auto-format backend (ruff) and frontend (prettier)
	cd backend && uv run ruff format app tests
	cd frontend && pnpm format

migrate: ## Run Alembic migrations (requires running postgres)
	cd backend && DATABASE_URL=$$DATABASE_URL uv run alembic upgrade head

migrate-new: ## Create a new Alembic migration (usage: make migrate-new MSG="add users table")
	cd backend && DATABASE_URL=$$DATABASE_URL uv run alembic revision --autogenerate -m "$(MSG)"

license-audit: ## Regenerate docs/LICENSE_AUDIT.md and verify it matches committed version
	python3 scripts/license-audit.py

seed: ## Seed the database with sample data
	cd backend && python ../scripts/seed.py

install: check-env ## First-time setup: copy .env if missing, pull images, run migrations, start stack
	@if [ ! -f backend/.env ]; then \
		cp backend/.env.example backend/.env; \
		echo ""; \
		echo "✔ Created backend/.env from .env.example."; \
		echo "  Open backend/.env and set GEMINI_API_KEY and API_KEY before continuing."; \
		echo "  Then run: make first-run"; \
		echo ""; \
		exit 0; \
	fi
	@echo "--- Pulling images ---"
	$(COMPOSE) pull --ignore-pull-failures
	@echo "--- Building images ---"
	$(COMPOSE) build
	@echo "--- Starting services ---"
	$(COMPOSE) up -d
	@echo "--- Waiting for database to be ready ---"
	@for i in $$(seq 1 30); do \
		$(COMPOSE) exec -T postgres pg_isready -U lecturevoice > /dev/null 2>&1 && break; \
		echo "  Waiting for postgres ($$i/30)..."; \
		sleep 2; \
	done
	@echo "--- Running migrations ---"
	$(COMPOSE) exec -T api sh -c "cd /app && uv run alembic upgrade head"
	@echo ""
	@echo "✔ LectureVoice is ready at http://localhost:3000"
	@echo ""

first-run: ## First-time setup + open browser (run this after git clone)
	@$(MAKE) install
	@echo "--- Opening browser ---"
	@if [ "$$(uname)" = "Darwin" ]; then \
		open http://localhost:3000; \
	elif grep -qi microsoft /proc/version 2>/dev/null; then \
		cmd.exe /c start http://localhost:3000 2>/dev/null || true; \
	else \
		xdg-open http://localhost:3000 2>/dev/null || true; \
	fi

release: ## Tag Docker images with VERSION (does not push)
	@VERSION=$$(cat VERSION); \
	echo "--- Tagging images as lecturevoice-*:$$VERSION and :latest ---"; \
	$(COMPOSE) build; \
	docker tag lecturevoice-api:latest lecturevoice-api:$$VERSION; \
	docker tag lecturevoice-worker-cpu:latest lecturevoice-worker-cpu:$$VERSION; \
	docker tag lecturevoice-frontend:latest lecturevoice-frontend:$$VERSION; \
	echo "✔ Tagged: $$VERSION (run 'docker push' separately when ready)"
