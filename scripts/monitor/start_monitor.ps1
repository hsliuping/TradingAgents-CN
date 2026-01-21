# TradingAgents-CN Process Monitor Daemon Startup Script

[CmdletBinding()]
param(
    [int]$Interval = 30,
    [string]$LogFile = "logs\process_monitor.log",
    [switch]$Background,
    [switch]$AutoRestart,
    [int]$RestartDelay = 5,
    [int]$MaxRestarts = 3,
    [int]$RestartWindow = 300
)

$ErrorActionPreference = "Continue"
$root = $PSScriptRoot
while (-not (Test-Path (Join-Path $root ".git")) -and $root.Length -gt 3) {
    $root = Split-Path $root
}
if (-not (Test-Path (Join-Path $root ".git"))) {
    $root = $PSScriptRoot
}

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "TradingAgents-CN Process Monitor" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Check Python
$pythonExe = Join-Path $root 'vendors\python\python.exe'
if (-not (Test-Path $pythonExe)) {
    $pythonExe = Join-Path $root 'venv\Scripts\python.exe'
}
if (-not (Test-Path $pythonExe)) {
    $pythonExe = Join-Path $root 'env\Scripts\python.exe'
}

if (-not (Test-Path $pythonExe)) {
    Write-Host "ERROR: Python not found" -ForegroundColor Red
    exit 1
}

# Check monitor script
$monitorScript = Join-Path $root 'scripts\monitor\process_monitor.py'
if (-not (Test-Path $monitorScript)) {
    Write-Host "ERROR: Monitor script not found: $monitorScript" -ForegroundColor Red
    exit 1
}

# Check if already running
$pidFile = Join-Path $root 'logs\process_monitor.pid'
if (Test-Path $pidFile) {
    $existingPid = Get-Content $pidFile -ErrorAction SilentlyContinue
    if ($existingPid) {
        $existingProcess = Get-Process -Id $existingPid -ErrorAction SilentlyContinue
        if ($existingProcess) {
            Write-Host "WARNING: Monitor already running (PID: $existingPid)" -ForegroundColor Yellow
            Write-Host "   To restart, stop existing process: Stop-Process -Id $existingPid" -ForegroundColor Gray
            exit 0
        } else {
            # PID file exists but process doesn't, remove stale file
            Remove-Item $pidFile -Force -ErrorAction SilentlyContinue
        }
    }
}

# Ensure log directory exists
$logDir = Split-Path $LogFile -Parent
if ($logDir) {
    New-Item -ItemType Directory -Path $logDir -Force | Out-Null
}

Write-Host "Starting Process Monitor Daemon..." -ForegroundColor Yellow
Write-Host "   Check interval: $Interval seconds" -ForegroundColor Gray
Write-Host "   Log file: $LogFile" -ForegroundColor Gray
Write-Host "   Auto restart: $(if ($AutoRestart) { 'ENABLED' } else { 'DISABLED' })" -ForegroundColor $(if ($AutoRestart) { 'Green' } else { 'Gray' })
if ($AutoRestart) {
    Write-Host "   Max restarts: $MaxRestarts in ${RestartWindow}s" -ForegroundColor Gray
    Write-Host "   Restart delay: ${RestartDelay}s" -ForegroundColor Gray
}
Write-Host ""

# Set UTF-8 encoding
$env:PYTHONIOENCODING = "utf-8"
$env:PYTHONUTF8 = "1"

# Build arguments
$monitorArgs = @(
    "`"$monitorScript`"",
    "--interval", $Interval,
    "--log-file", "`"$LogFile`""
)

if ($AutoRestart) {
    $monitorArgs += "--auto-restart"
    $monitorArgs += "--restart-delay"
    $monitorArgs += $RestartDelay
    $monitorArgs += "--max-restarts"
    $monitorArgs += $MaxRestarts
    $monitorArgs += "--restart-window"
    $monitorArgs += $RestartWindow
}

if ($Background) {
    # Run in background
    Write-Host "   Mode: Background" -ForegroundColor Gray
    $process = Start-Process -FilePath $pythonExe -ArgumentList $monitorArgs -WorkingDirectory $root -WindowStyle Hidden -PassThru

    if ($process) {
        Write-Host "Monitor daemon started (PID: $($process.Id))" -ForegroundColor Green
        Write-Host "   View logs: Get-Content $LogFile -Tail 50 -Wait" -ForegroundColor Cyan
    } else {
        Write-Host "Failed to start" -ForegroundColor Red
        exit 1
    }
} else {
    # Run in foreground
    Write-Host "   Mode: Foreground (Press Ctrl+C to stop)" -ForegroundColor Gray
    Write-Host ""
    & $pythonExe $monitorArgs
}
