# TradingAgents-CN Development Startup Script
# Start Backend API and Worker for local development

[CmdletBinding(PositionalBinding=$false)]
param(
    [switch]$BackendOnly,
    [switch]$WorkerOnly,
    [switch]$NoWorker,
    [int]$BackendPort = 8000,
    [int]$WorkerPort = 8001,
    [switch]$Help,
    # Unified interface: start_dev.ps1 [command] [version]
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$RemainingArgs
)

# Parse unified interface: start_dev.ps1 backend|docker|frontend [version]
if ($RemainingArgs.Count -gt 0) {
    $cmd = $RemainingArgs[0].ToLower()
    $ver = if ($RemainingArgs.Count -gt 1) { $RemainingArgs[1] } else { $null }
    
    switch ($cmd) {
        "backend" {
            $BackendOnly = $true
            # Map version to port
            if ($ver) {
                $versionPorts = @{ "1.0" = 8000; "2.0" = 8000; "2.1" = 8000; "3.0" = 8002 }
                if ($versionPorts.ContainsKey($ver)) { $BackendPort = $versionPorts[$ver] }
                else { Write-Host "[WARN] Unknown version '$ver', using port $BackendPort" -ForegroundColor Yellow }
            }
        }
        "worker" { $WorkerOnly = $true }
        "docker" {
            # Start Docker services (forward remaining args)
            $dockerArgs = $RemainingArgs[1..($RemainingArgs.Count-1)]
            & "$PSScriptRoot\scripts\start_dev_docker.ps1" @dockerArgs
            exit $LASTEXITCODE
        }
        "frontend" {
            # Start Frontend dev server
            Push-Location "$PSScriptRoot\frontend"
            try { npm run dev } finally { Pop-Location }
            exit $LASTEXITCODE
        }
        "status" {
            Write-Host "Version: 3.0 (main)" -ForegroundColor Cyan
            Write-Host "  v1.0: MongoDB:27017 | Redis:6379 | Backend:8000" -ForegroundColor Gray
            Write-Host "  v2.0: MongoDB:27017 | Redis:6379 | Backend:8000" -ForegroundColor Gray
            Write-Host "  v2.1: MongoDB:27018 | Redis:6380 | Backend:8000" -ForegroundColor Gray
            Write-Host "  v3.0: MongoDB:27019 | Redis:6381 | Backend:8002" -ForegroundColor Cyan
            Write-Host ""
            docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" | Select-String "mongo|redis"
            exit 0
        }
        default {
            Write-Host "[ERROR] Unknown command: $cmd" -ForegroundColor Red
            Write-Host "Usage: start_dev.ps1 [backend|docker|frontend|status] [version]" -ForegroundColor Yellow
            exit 1
        }
    }
}

if ($Help) {
    Write-Host ""
    Write-Host "TradingAgents-CN Development Startup Script" -ForegroundColor Cyan
    Write-Host "============================================" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "Usage:" -ForegroundColor Yellow
    Write-Host "  .\start_dev.ps1 backend             # Start Backend only"
    Write-Host "  .\start_dev.ps1 backend 2.1         # Start Backend on port 8001"
    Write-Host "  .\start_dev.ps1 docker 2.1          # Start MongoDB + Redis"
    Write-Host "  .\start_dev.ps1 frontend            # Start Frontend dev server"
    Write-Host "  .\start_dev.ps1 status              # Show version/port info"
    Write-Host ""
    Write-Host "Legacy usage:" -ForegroundColor Gray
    Write-Host "  .\start_dev.ps1 -BackendOnly        # Start Backend only"
    Write-Host "  .\start_dev.ps1 -WorkerOnly         # Start Worker only"
    Write-Host "  .\start_dev.ps1 -BackendPort 8080   # Use custom Backend port"
    Write-Host ""
    exit 0
}

$ErrorActionPreference = "Stop"

# Get project root
$root = $PSScriptRoot

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "TradingAgents-CN Development Mode" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Detect Python executable
$pythonExe = $null
$venvPaths = @(
    (Join-Path $root "env\Scripts\python.exe"),      # 优先使用 env
    (Join-Path $root "venv\Scripts\python.exe"),
    (Join-Path $root "vendors\python\python.exe")
)

foreach ($path in $venvPaths) {
    if (Test-Path $path) {
        $pythonExe = $path
        Write-Host "[OK] Found Python: $path" -ForegroundColor Green
        break
    }
}

if (-not $pythonExe) {
    $pythonExe = "python"
    Write-Host "[WARN] Using system Python" -ForegroundColor Yellow
}

# Set UTF-8 encoding
$env:PYTHONIOENCODING = "utf-8"
$env:PYTHONUTF8 = "1"
$env:PYTHONUNBUFFERED = "1"  # Disable output buffering

Write-Host "[OK] UTF-8 encoding enabled" -ForegroundColor Green
Write-Host ""

# Check required files
$backendMain = Join-Path $root "app\main.py"
$workerApp = Join-Path $root "app\worker\worker_app.py"

if (-not $BackendOnly -and -not $WorkerOnly) {
    if (-not (Test-Path $backendMain)) {
        Write-Host "[ERROR] Backend not found: $backendMain" -ForegroundColor Red
        exit 1
    }
    if (-not $NoWorker -and -not (Test-Path $workerApp)) {
        Write-Host "[ERROR] Worker app not found: $workerApp" -ForegroundColor Red
        exit 1
    }
}

# Start processes
$jobs = @()

try {
    if (-not $WorkerOnly) {
        Write-Host "[1/2] Starting Backend API (FastAPI + Uvicorn)..." -ForegroundColor Yellow
        Write-Host "  Port: $BackendPort" -ForegroundColor Gray
        Write-Host "  URL: http://127.0.0.1:$BackendPort" -ForegroundColor Gray
        Write-Host "  Docs: http://127.0.0.1:$BackendPort/docs" -ForegroundColor Gray
        Write-Host ""

        # Start Backend using Uvicorn
        $backendJob = Start-Job -ScriptBlock {
            param($pythonExe, $backendPort, $root)
            Set-Location $root
            $env:PYTHONIOENCODING = "utf-8"
            $env:PYTHONUTF8 = "1"
            $env:PYTHONUNBUFFERED = "1"
            & $pythonExe -m uvicorn app.main:app --host 127.0.0.1 --port $backendPort --log-level info
        } -ArgumentList $pythonExe, $BackendPort, $root

        $jobs += $backendJob
        Write-Host "[OK] Backend started (Job ID: $($backendJob.Id))" -ForegroundColor Green
        Write-Host ""

        # Wait for backend to start
        Start-Sleep -Seconds 2
    }
    
    if (-not $BackendOnly -and -not $NoWorker) {
        Write-Host "[2/2] Starting Worker (FastAPI + Uvicorn)..." -ForegroundColor Yellow
        Write-Host "  Port: $WorkerPort" -ForegroundColor Gray
        Write-Host "  Health: http://127.0.0.1:$WorkerPort/health" -ForegroundColor Gray
        Write-Host ""

        # Start Worker using Uvicorn (same as Backend)
        $workerJob = Start-Job -ScriptBlock {
            param($pythonExe, $workerPort, $root)
            Set-Location $root
            $env:PYTHONIOENCODING = "utf-8"
            $env:PYTHONUTF8 = "1"
            $env:PYTHONUNBUFFERED = "1"
            & $pythonExe -m uvicorn app.worker.worker_app:app --host 127.0.0.1 --port $workerPort --log-level info
        } -ArgumentList $pythonExe, $WorkerPort, $root

        $jobs += $workerJob
        Write-Host "[OK] Worker started (Job ID: $($workerJob.Id))" -ForegroundColor Green
        Write-Host ""
    }
    
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host "Development server running!" -ForegroundColor Green
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "Press Ctrl+C to stop all processes" -ForegroundColor Yellow
    Write-Host ""
    
    # Monitor jobs and display output
    while ($true) {
        foreach ($job in $jobs) {
            $output = Receive-Job -Job $job -ErrorAction SilentlyContinue
            if ($output) {
                foreach ($line in $output) { Write-Host $line }
            }
            
            # Check if job failed
            if ($job.State -eq "Failed") {
                Write-Host ""
                Write-Host "[ERROR] Job $($job.Id) failed!" -ForegroundColor Red
                $jobError = Receive-Job -Job $job -ErrorAction SilentlyContinue
                Write-Host $jobError -ForegroundColor Red
            }
        }
        
        Start-Sleep -Milliseconds 100
    }
    
} catch {
    Write-Host ""
    Write-Host "[INFO] Shutting down..." -ForegroundColor Yellow
} finally {
    # Stop all jobs
    foreach ($job in $jobs) {
        if ($job.State -eq "Running") {
            Write-Host "Stopping Job $($job.Id)..." -ForegroundColor Gray
            Stop-Job -Job $job
            Remove-Job -Job $job -Force
        }
    }
    
    Write-Host ""
    Write-Host "[OK] All processes stopped" -ForegroundColor Green
    Write-Host ""
}

