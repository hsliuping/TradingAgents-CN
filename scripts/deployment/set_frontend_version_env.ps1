[CmdletBinding()]
param(
    [string]$RootPath = (Split-Path -Parent (Split-Path -Parent $PSScriptRoot))
)

$ErrorActionPreference = 'Stop'

$versionFile = Join-Path $RootPath 'VERSION'
$frontendDir = Join-Path $RootPath 'frontend'
$productionEnvFile = Join-Path $frontendDir '.env.production.local'
$developmentEnvFile = Join-Path $frontendDir '.env.development.local'

if (-not (Test-Path $versionFile)) {
    throw "VERSION file not found: $versionFile"
}

if (-not (Test-Path $frontendDir)) {
    throw "Frontend directory not found: $frontendDir"
}

$version = (Get-Content -Path $versionFile -Encoding UTF8 | Select-Object -First 1).Trim()
if ([string]::IsNullOrWhiteSpace($version)) {
    throw "VERSION file is empty: $versionFile"
}

"VITE_APP_VERSION=$version" | Out-File -FilePath $productionEnvFile -Encoding ascii -Force
"VITE_APP_VERSION=$version" | Out-File -FilePath $developmentEnvFile -Encoding ascii -Force

Write-Host "  Frontend version injected: $version" -ForegroundColor Green
Write-Host "  Env file updated: $productionEnvFile" -ForegroundColor Gray
Write-Host "  Env file updated: $developmentEnvFile" -ForegroundColor Gray