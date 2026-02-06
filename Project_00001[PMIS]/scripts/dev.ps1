#!/usr/bin/env pwsh
<#
.SYNOPSIS
PMIS monorepo dev helper — PowerShell edition

.DESCRIPTION
Development convenience script for running Docker Compose commands and shell access.

.EXAMPLE
.\scripts\dev.ps1 up
.\scripts\dev.ps1 logs
.\scripts\dev.ps1 api-shell
#>

param(
    [Parameter(Mandatory=$false, Position=0)]
    [string]$Command = "help"
)

$infra_dir = Join-Path $PSScriptRoot ".." "infra"
$root_dir = Join-Path $PSScriptRoot ".."

function Show-Help {
    @"
PMIS Dev Commands (PowerShell)

Docker Compose:
  up              Start dev stack (api, worker, postgres, redis, minio)
  down            Stop dev stack
  build           Rebuild images (no cache)
  ps              Show running containers
  logs            Tail logs (all services)
  clean           Remove containers and volumes

Shells:
  api-shell       Open pwsh in api container
  worker-shell    Open pwsh in worker container
  db-shell        Connect to postgres with psql

Dev:
  migrate         Run database migrations (placeholder)
  lint            Run linters (python + js)
  format          Auto-format code (python + js)

Usage:
  .\scripts\dev.ps1 <command>
"@
}

switch ($Command) {
    "up" {
        Write-Host "Starting dev stack..." -ForegroundColor Green
        Push-Location $infra_dir
        docker compose up --build
        Pop-Location
    }
    "down" {
        Write-Host "Stopping dev stack..." -ForegroundColor Green
        Push-Location $infra_dir
        docker compose down
        Pop-Location
    }
    "build" {
        Write-Host "Rebuilding images..." -ForegroundColor Green
        Push-Location $infra_dir
        docker compose build --no-cache
        Pop-Location
    }
    "ps" {
        Push-Location $infra_dir
        docker compose ps
        Pop-Location
    }
    "logs" {
        Write-Host "Tailing logs (Ctrl+C to exit)..." -ForegroundColor Green
        Push-Location $infra_dir
        docker compose logs -f
        Pop-Location
    }
    "clean" {
        Write-Host "Removing containers and volumes..." -ForegroundColor Yellow
        Push-Location $infra_dir
        docker compose down -v
        Pop-Location
    }
    "api-shell" {
        Write-Host "Entering api container..." -ForegroundColor Green
        Push-Location $infra_dir
        docker compose exec api pwsh
        Pop-Location
    }
    "worker-shell" {
        Write-Host "Entering worker container..." -ForegroundColor Green
        Push-Location $infra_dir
        docker compose exec worker pwsh
        Pop-Location
    }
    "db-shell" {
        Write-Host "Connecting to postgres..." -ForegroundColor Green
        Push-Location $infra_dir
        docker compose exec postgres psql -U postgres -d pmis
        Pop-Location
    }
    "migrate" {
        Write-Host "Running migrations (placeholder)..." -ForegroundColor Cyan
        Push-Location (Join-Path $root_dir "apps" "api")
        poetry run alembic upgrade head 2>$null || Write-Host "alembic not configured yet"
        Pop-Location
    }
    "lint" {
        Write-Host "Linting Python (api + worker)..." -ForegroundColor Cyan
        Push-Location (Join-Path $root_dir "apps" "api")
        poetry run ruff check . 2>$null || $true
        Pop-Location
        
        Push-Location (Join-Path $root_dir "apps" "worker")
        poetry run ruff check . 2>$null || $true
        Pop-Location
        
        Write-Host "Linting JS (web)..." -ForegroundColor Cyan
        Push-Location (Join-Path $root_dir "apps" "web")
        npm run lint 2>$null || $true
        Pop-Location
    }
    "format" {
        Write-Host "Formatting Python (api + worker)..." -ForegroundColor Cyan
        Push-Location (Join-Path $root_dir "apps" "api")
        poetry run black . 2>$null || $true
        poetry run ruff check --fix . 2>$null || $true
        Pop-Location
        
        Push-Location (Join-Path $root_dir "apps" "worker")
        poetry run black . 2>$null || $true
        poetry run ruff check --fix . 2>$null || $true
        Pop-Location
        
        Write-Host "Formatting JS (web)..." -ForegroundColor Cyan
        Push-Location (Join-Path $root_dir "apps" "web")
        npm run format 2>$null || $true
        Pop-Location
    }
    default {
        Show-Help
    }
}
