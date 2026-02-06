.PHONY: help up down logs ps build shell api-shell worker-shell clean migrate

help:
	@echo "PMIS monorepo — available commands:"
	@echo ""
	@echo "Docker Compose:"
	@echo "  make up              Start dev stack (api, worker, postgres, redis, minio)"
	@echo "  make down            Stop dev stack"
	@echo "  make build           Rebuild images"
	@echo "  make ps              Show running containers"
	@echo "  make logs            Tail logs (all services)"
	@echo "  make clean           Remove containers and volumes"
	@echo ""
	@echo "Shells:"
	@echo "  make api-shell       Open /bin/bash in api container"
	@echo "  make worker-shell    Open /bin/bash in worker container"
	@echo "  makeup shell api-db       Open psql in postgres container"
	@echo ""
	@echo "Dev:"
	@echo "  make migrate         Run database migrations (placeholder)"
	@echo "  make lint            Run linters (python + js)"
	@echo "  make format          Auto-format code (python + js)"
	@echo ""

up:
	cd infra && docker compose up --build

down:
	cd infra && docker compose down

build:
	cd infra && docker compose build --no-cache

ps:
	cd infra && docker compose ps

logs:
	cd infra && docker compose logs -f

clean:
	cd infra && docker compose down -v

api-shell:
	cd infra && docker compose exec api /bin/bash

worker-shell:
	cd infra && docker compose exec worker /bin/bash

api-db:
	cd infra && docker compose exec postgres psql -U postgres -d pmis

migrate:
	@echo "placeholder: run alembic migrations here"
	cd apps/api && poetry run alembic upgrade head || echo "alembic not configured yet"

lint:
	@echo "Linting Python (api + worker)..."
	cd apps/api && poetry run ruff check . || true
	cd apps/worker && poetry run ruff check . || true
	@echo "Linting JS (web)..."
	cd apps/web && npm run lint || true

format:
	@echo "Formatting Python (api + worker)..."
	cd apps/api && poetry run black . || true
	cd apps/api && poetry run ruff check --fix . || true
	cd apps/worker && poetry run black . || true
	cd apps/worker && poetry run ruff check --fix . || true
	@echo "Formatting JS (web)..."
	cd apps/web && npm run format || true
