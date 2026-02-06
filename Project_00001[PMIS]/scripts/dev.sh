#!/bin/bash
# PMIS monorepo dev helper — bash edition

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INFRA_DIR="$SCRIPT_DIR/../infra"
ROOT_DIR="$SCRIPT_DIR/.."

show_help() {
    cat <<EOF
PMIS Dev Commands (bash)

Docker Compose:
  up              Start dev stack (api, worker, postgres, redis, minio)
  down            Stop dev stack
  build           Rebuild images (no cache)
  ps              Show running containers
  logs            Tail logs (all services)
  clean           Remove containers and volumes

Shells:
  api-shell       Open /bin/bash in api container
  worker-shell    Open /bin/bash in worker container
  db-shell        Connect to postgres with psql

Dev:
  migrate         Run database migrations (placeholder)
  lint            Run linters (python + js)
  format          Auto-format code (python + js)

Usage:
  ./scripts/dev.sh <command>
EOF
}

case "${1:-help}" in
    up)
        echo "Starting dev stack..."
        cd "$INFRA_DIR"
        docker compose up --build
        ;;
    down)
        echo "Stopping dev stack..."
        cd "$INFRA_DIR"
        docker compose down
        ;;
    build)
        echo "Rebuilding images..."
        cd "$INFRA_DIR"
        docker compose build --no-cache
        ;;
    ps)
        cd "$INFRA_DIR"
        docker compose ps
        ;;
    logs)
        echo "Tailing logs (Ctrl+C to exit)..."
        cd "$INFRA_DIR"
        docker compose logs -f
        ;;
    clean)
        echo "Removing containers and volumes..."
        cd "$INFRA_DIR"
        docker compose down -v
        ;;
    api-shell)
        echo "Entering api container..."
        cd "$INFRA_DIR"
        docker compose exec api /bin/bash
        ;;
    worker-shell)
        echo "Entering worker container..."
        cd "$INFRA_DIR"
        docker compose exec worker /bin/bash
        ;;
    db-shell)
        echo "Connecting to postgres..."
        cd "$INFRA_DIR"
        docker compose exec postgres psql -U postgres -d pmis
        ;;
    migrate)
        echo "Running migrations (placeholder)..."
        cd "$ROOT_DIR/apps/api"
        poetry run alembic upgrade head || echo "alembic not configured yet"
        ;;
    lint)
        echo "Linting Python (api + worker)..."
        cd "$ROOT_DIR/apps/api"
        poetry run ruff check . || true
        cd "$ROOT_DIR/apps/worker"
        poetry run ruff check . || true
        echo "Linting JS (web)..."
        cd "$ROOT_DIR/apps/web"
        npm run lint || true
        ;;
    format)
        echo "Formatting Python (api + worker)..."
        cd "$ROOT_DIR/apps/api"
        poetry run black . || true
        poetry run ruff check --fix . || true
        cd "$ROOT_DIR/apps/worker"
        poetry run black . || true
        poetry run ruff check --fix . || true
        echo "Formatting JS (web)..."
        cd "$ROOT_DIR/apps/web"
        npm run format || true
        ;;
    *)
        show_help
        ;;
esac
