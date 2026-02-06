# PMIS monorepo (pmis-agent)

Scaffolding for PMIS monorepo. Contains three apps and basic infra for local development.

## Structure

- **apps/api** — FastAPI (Python 3.11, Poetry)
- **apps/worker** — Celery worker (shares `apps/common` code)
- **apps/web** — Next.js + TypeScript
- **infra/docker-compose.yml** — Postgres, Redis, MinIO (with healthchecks & dev overrides)

## Quick start

### Using Make (Linux/macOS/WSL)

```bash
make help          # Show all commands
make up            # Start docker compose stack (builds images)
make logs          # Tail service logs
make api-shell     # Enter api container
make down          # Stop services
```

### Using PowerShell (Windows)

```powershell
.\scripts\dev.ps1 help         # Show all commands
.\scripts\dev.ps1 up           # Start docker compose stack
.\scripts\dev.ps1 logs         # Tail service logs
.\scripts\dev.ps1 api-shell    # Enter api container
.\scripts\dev.ps1 down         # Stop services
```

### Manual (no Make/scripts)

```bash
cd infra
docker compose up --build
```

Then in separate terminals:
- API at http://localhost:8000 (auto-reload with `--reload`)
- Worker logs via `docker compose logs worker`
- Postgres on port 5432
- Redis on port 6379
- MinIO on port 9000

## Lint & format

```bash
make lint          # or .\scripts\dev.ps1 lint
make format        # or .\scripts\dev.ps1 format
```

Or install pre-commit:

```bash
pip install pre-commit
pre-commit install
pre-commit run --all-files
```

## Architecture

- **Healthchecks**: postgres (pg_isready), redis (redis-cli ping), api (GET /health)
- **Docker Compose**: Base `infra/docker-compose.yml` has production-like settings; `docker-compose.override.yml` adds dev bind-mounts & hot-reload
- **Dev Mount**: api + worker source code mounted into containers for live reload
- **Service Health**: api/worker wait for postgres & redis to be healthy before starting

## Notes

- This repo contains scaffolding and "hello world" endpoints only.
- Add business logic to `apps/api/app/routes.py`, `apps/worker/worker.py`, and `apps/web/pages/`.
