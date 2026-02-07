<#
One-click starter for PMIS stack.
Usage: Run this in PowerShell (preferably elevated) from any location.
It detects Docker and offers to start the Docker Compose stack or run a local dev flow (API + Web + Celery).
#>

Set-StrictMode -Version Latest

function Test-CommandExists($name){
    return (Get-Command $name -ErrorAction SilentlyContinue) -ne $null
}

$RepoRoot = Split-Path -Parent $MyInvocation.MyCommand.Definition
if (-not (Test-Path $RepoRoot)){
    # fallback to current directory
    $RepoRoot = (Get-Location).Path
}

Write-Host "PMIS Starter Script" -ForegroundColor Cyan
Write-Host "Repository root: $RepoRoot`n"

$hasDocker = Test-CommandExists docker

if ($hasDocker) {
    Write-Host "Docker detected on this machine." -ForegroundColor Green
} else {
    Write-Host "Docker not found. You can run local dev flow instead." -ForegroundColor Yellow
}

# Present options
Write-Host "Choose startup mode:" -ForegroundColor Cyan
if ($hasDocker) {
    Write-Host "  1) Docker Compose (recommended)"
    Write-Host "  2) Local dev (uvicorn + next dev + optional celery)"
    $choice = Read-Host "Enter 1 or 2 (default 1)"
    if ($choice -eq '') { $choice = '1' }
} else {
    Write-Host "  1) Local dev (uvicorn + next dev + optional celery)"
    $choice = Read-Host "Enter 1 to start local dev (default 1)"
    if ($choice -eq '') { $choice = '1' }
}

function Start-DockerCompose {
    $compose = Join-Path $RepoRoot 'infra\docker-compose.prod.yml'
    if (-not (Test-Path $compose)){
        Write-Host "docker-compose file not found: $compose" -ForegroundColor Red
        return
    }

    $cmd = "cd `"$RepoRoot`"; docker compose -f `"$compose`" up --build"
    Write-Host "Starting Docker Compose in a new window..." -ForegroundColor Cyan
    Start-Process powershell -ArgumentList "-NoExit","-Command",$cmd -WorkingDirectory $RepoRoot

    Start-Sleep -Seconds 3
    Write-Host "Opening browser to http://localhost:3000 and http://localhost:8000/docs"
    Start-Process 'http://localhost:3000'
    Start-Process 'http://localhost:8000/docs'
}

function Start-LocalDev {
    Write-Host "Starting local dev servers in new windows..." -ForegroundColor Cyan

    # Attempt to ensure Redis/Postgres services are running when Docker is not available
    Ensure-LocalDependencies


    # Start API (uvicorn)
    $apiCmd = "cd `"$RepoRoot\apps\api`"; python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000"
    Start-Process powershell -ArgumentList "-NoExit","-Command",$apiCmd -WorkingDirectory (Join-Path $RepoRoot 'apps\api')

    Start-Sleep -Milliseconds 800

    # Start Web (Next.js)
    $webPath = Join-Path $RepoRoot 'apps\web'
    if (Test-Path $webPath) {
        $webCmd = "cd `"$webPath`"; if (Test-Path package.json) { npm install } ; npm run dev"
        Start-Process powershell -ArgumentList "-NoExit","-Command",$webCmd -WorkingDirectory $webPath
    } else {
        Write-Host "Web app not found at $webPath" -ForegroundColor Yellow
    }

    Start-Sleep -Milliseconds 800

    # Optional: Start Celery worker (requires Redis running)
    $celeryChoice = Read-Host "Start Celery worker + beat? (y/N)"
    if ($celeryChoice -match '^[Yy]'){
        $celCmd = "cd `"$RepoRoot`"; celery -A apps.worker.worker.celery_app worker --beat -l info"
        Start-Process powershell -ArgumentList "-NoExit","-Command",$celCmd -WorkingDirectory $RepoRoot
    }

    Start-Sleep -Seconds 2
    Write-Host "Opening browser to http://localhost:3000 and http://localhost:8000/docs"
    Start-Process 'http://localhost:3000'
    Start-Process 'http://localhost:8000/docs'
}

function Ensure-LocalDependencies {
    Write-Host "Checking local dependencies (Redis/Postgres)..." -ForegroundColor Cyan

    # Attempt to start Redis if installed as a Windows service
    $redisServiceNames = @('Redis', 'RedisServer', 'redis', 'redis-server')
    $redisStarted = $false
    foreach ($name in $redisServiceNames) {
        try {
            $svc = Get-Service -Name $name -ErrorAction SilentlyContinue
            if ($svc) {
                if ($svc.Status -ne 'Running') {
                    Write-Host "Starting Redis service '$name'..." -ForegroundColor Yellow
                    Start-Service -Name $name -ErrorAction SilentlyContinue
                }
                Write-Host "Redis service '$name' status: $((Get-Service -Name $name).Status)"
                $redisStarted = $true
                break
            }
        } catch {
            continue
        }
    }

    # If no service, try to find redis-server.exe on PATH
    if (-not $redisStarted) {
        $redisCmd = Get-Command redis-server -ErrorAction SilentlyContinue
        if ($redisCmd) {
            Write-Host "Found redis-server executable. Launching background process..." -ForegroundColor Yellow
            Start-Process -FilePath $redisCmd.Source -ArgumentList "" -WindowStyle Hidden -ErrorAction SilentlyContinue
            Start-Sleep -Seconds 2
            Write-Host "redis-server started (process launched)." -ForegroundColor Green
            $redisStarted = $true
        } else {
            Write-Host "Redis not found as service or executable. Using existing Redis if available, or the script will continue with SQLite fallback." -ForegroundColor DarkYellow
        }
    }

    # Attempt to start Postgres if installed as a Windows service (common names)
    $pgServiceNames = @('postgresql-x64-15','postgresql-x64-14','postgresql-x64-13','postgresql','pgsql')
    $pgStarted = $false
    foreach ($name in $pgServiceNames) {
        try {
            $svc = Get-Service -Name $name -ErrorAction SilentlyContinue
            if ($svc) {
                if ($svc.Status -ne 'Running') {
                    Write-Host "Starting Postgres service '$name'..." -ForegroundColor Yellow
                    Start-Service -Name $name -ErrorAction SilentlyContinue
                }
                Write-Host "Postgres service '$name' status: $((Get-Service -Name $name).Status)"
                $pgStarted = $true
                break
            }
        } catch {
            continue
        }
    }

    # If no service, check for postgres.exe or pg_ctl on PATH (best-effort)
    if (-not $pgStarted) {
        $pgCtl = Get-Command pg_ctl -ErrorAction SilentlyContinue
        $pgExe = Get-Command postgres -ErrorAction SilentlyContinue
        if ($pgCtl) {
            Write-Host "Found pg_ctl. Note: starting Postgres with pg_ctl requires a data directory; ensure your PGDATA is initialized." -ForegroundColor Yellow
        } elseif ($pgExe) {
            Write-Host "Found postgres executable. Attempting to start postgres process (may require proper data directory and permissions)." -ForegroundColor Yellow
            try {
                Start-Process -FilePath $pgExe.Source -ArgumentList "" -WindowStyle Hidden -ErrorAction SilentlyContinue
                Start-Sleep -Seconds 2
                Write-Host "postgres process launched (if configured)." -ForegroundColor Green
                $pgStarted = $true
            } catch {
                Write-Host "Could not start postgres process: $($_.Exception.Message)" -ForegroundColor Red
            }
        } else {
            Write-Host "Postgres not found as service or executable. The API will fallback to SQLite when DATABASE_URL is not set." -ForegroundColor DarkYellow
        }
    }

    # Summary
    if ($redisStarted) { Write-Host "Redis appears available." -ForegroundColor Green }
    if ($pgStarted) { Write-Host "Postgres appears available." -ForegroundColor Green }
}

if ($hasDocker -and $choice -eq '1'){
    Start-DockerCompose
} else {
    Start-LocalDev
}

Write-Host "Starter script launched. Check the new windows for logs." -ForegroundColor Green
Write-Host "If you need to seed demo telemetry after servers are running, run:`n  python apps/api/scripts/seed_telemetry.py`n  python apps/api/scripts/attach_demo_attachment.py" -ForegroundColor Cyan
