param([switch]$Initialize)
$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)

function Invoke-Docker {
    & docker @args
    if ($LASTEXITCODE -ne 0) { throw "Docker command failed: $args" }
}

Invoke-Docker desktop start
$composeArgs = @('--context', 'desktop-linux', 'compose', '-f', 'docker-compose.hub.nginx.yml', '-f', 'docker-compose.desktop.yml')
Invoke-Docker @composeArgs up -d --no-build --wait --wait-timeout 180
if ($Initialize) {
    Invoke-Docker --context desktop-linux cp scripts/init_desktop.py tradingagents-backend:/app/scripts/init_desktop.py
    Invoke-Docker --context desktop-linux exec tradingagents-backend python scripts/init_desktop.py --incremental
    Invoke-Docker @composeArgs restart backend
    Invoke-Docker @composeArgs up -d --no-build --wait --wait-timeout 180
}
$health = Invoke-RestMethod 'http://localhost/api/health' -TimeoutSec 20
if (-not $health.success) { throw 'Backend health check failed' }
Invoke-Docker @composeArgs ps
Write-Host 'TradingAgents-CN: http://localhost'
