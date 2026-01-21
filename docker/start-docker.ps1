# ============================================================================
# Docker Compose Startup Script for Windows
# ============================================================================
# This script starts all TradingAgents-CN services using Docker Compose
# ============================================================================

param(
    [switch]$EnableManagement = $false,
    [switch]$Build = $false,
    [switch]$Logs = $false
)

$ErrorActionPreference = "Stop"

Write-Host "============================================================================" -ForegroundColor Cyan
Write-Host "  TradingAgents-CN Docker Startup" -ForegroundColor Cyan
Write-Host "============================================================================" -ForegroundColor Cyan
Write-Host ""

# Check if docker-compose is installed
try {
    $null = docker-compose --version
} catch {
    Write-Host "ERROR: docker-compose is not installed" -ForegroundColor Red
    exit 1
}

# Create necessary directories
Write-Host "Creating necessary directories..." -ForegroundColor Yellow
$dirs = @("logs", "data", "config", "runtime")
foreach ($dir in $dirs) {
    if (-not (Test-Path $dir)) {
        New-Item -ItemType Directory -Path $dir -Force | Out-Null
        Write-Host "  Created: $dir" -ForegroundColor Green
    }
}

# Check if .env file exists
if (-not (Test-Path ".env")) {
    Write-Host "WARNING: .env file not found" -ForegroundColor Yellow
    if (Test-Path ".env.docker") {
        Write-Host "Copying .env.docker to .env..." -ForegroundColor Yellow
        Copy-Item ".env.docker" ".env"
    } else {
        Write-Host "ERROR: Neither .env nor .env.docker found" -ForegroundColor Red
        exit 1
    }
}

# Build profile arguments
$profileArgs = @()
if ($EnableManagement) {
    $profileArgs += "--profile", "management"
    Write-Host "Management tools enabled (Redis Commander, Mongo Express)" -ForegroundColor Green
}

# Stop existing containers
Write-Host ""
Write-Host "Stopping existing containers..." -ForegroundColor Yellow
docker-compose down

# Build images if requested
if ($Build) {
    Write-Host ""
    Write-Host "Building Docker images..." -ForegroundColor Yellow
    docker-compose build
}

# Start services
Write-Host ""
Write-Host "Starting services..." -ForegroundColor Yellow
if ($profileArgs.Count -gt 0) {
    docker-compose up -d @profileArgs
} else {
    docker-compose up -d
}

# Wait for services to be healthy
Write-Host ""
Write-Host "Waiting for services to be healthy..." -ForegroundColor Yellow
Start-Sleep -Seconds 10

# Check service status
Write-Host ""
Write-Host "Service Status:" -ForegroundColor Cyan
docker-compose ps

# Show logs if requested
if ($Logs) {
    Write-Host ""
    Write-Host "Showing logs (Ctrl+C to exit)..." -ForegroundColor Cyan
    docker-compose logs -f
} else {
    # Show recent logs
    Write-Host ""
    Write-Host "Recent logs:" -ForegroundColor Cyan
    docker-compose logs --tail=20
}

Write-Host ""
Write-Host "============================================================================" -ForegroundColor Green
Write-Host "  All Services Started Successfully!" -ForegroundColor Green
Write-Host "============================================================================" -ForegroundColor Green
Write-Host ""
Write-Host "Service URLs:" -ForegroundColor Cyan
Write-Host "  Backend API:  http://localhost:8000" -ForegroundColor Green
Write-Host "  Frontend:     http://localhost:3000" -ForegroundColor Green
Write-Host "  MongoDB:      mongodb://localhost:27017" -ForegroundColor Green
Write-Host "  Redis:        redis://localhost:6379" -ForegroundColor Green

if ($EnableManagement) {
    Write-Host ""
    Write-Host "Management Tools:" -ForegroundColor Cyan
    Write-Host "  Redis Commander:  http://localhost:8081" -ForegroundColor Green
    Write-Host "  Mongo Express:    http://localhost:8082" -ForegroundColor Green
}

Write-Host ""
Write-Host "Useful Commands:" -ForegroundColor Cyan
Write-Host "  View logs:        docker-compose logs -f" -ForegroundColor Yellow
Write-Host "  Stop services:    docker-compose down" -ForegroundColor Yellow
Write-Host "  Restart service:  docker-compose restart <service>" -ForegroundColor Yellow
Write-Host ""

