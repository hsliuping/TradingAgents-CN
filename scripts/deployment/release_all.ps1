<#
.SYNOPSIS
    One-click release: prepare + build installer + build update package.
.DESCRIPTION
    After dev/test, run this to:
    1. Auto-prepare releases/{version}/, migrations if missing
    2. Generate BUILD_INFO
    3. Build Pro portable package
    4. Build NSIS installer
    5. Build update package (update-{version}.zip)
.PARAMETER Version
    Override version. Default: read from VERSION file.
.PARAMETER SkipInstaller
    Skip NSIS installer, only build portable + update package.
.PARAMETER SkipPrepare
    Skip auto-prepare (releases/, migrations/). Use when already prepared.
#>
param(
    [string]$Version = "",
    [switch]$SkipInstaller = $false,
    [switch]$SkipPrepare = $false
)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$PSDefaultParameterValues['*:Encoding'] = 'utf8'

$root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)

if (-not $Version) {
    $versionFile = Join-Path $root "VERSION"
    if (Test-Path $versionFile) {
        $Version = (Get-Content $versionFile -Raw).Trim()
    } else {
        Write-Host "ERROR: VERSION file not found" -ForegroundColor Red
        exit 1
    }
}

$versionUnderscore = $Version -replace '\.', '_'
$releasesDir = Join-Path $root "releases"
$versionDir = Join-Path $releasesDir $Version
$migrationFile = Join-Path $root "migrations\v$versionUnderscore.py"

Write-Host "============================================================================" -ForegroundColor Cyan
Write-Host "  One-Click Release: $Version" -ForegroundColor Cyan
Write-Host "============================================================================" -ForegroundColor Cyan
Write-Host ""

# ── Step 0: Auto-prepare ───────────────────────────────────────────────────────
if (-not $SkipPrepare) {
    Write-Host "[0/4] Auto-prepare release files..." -ForegroundColor Yellow

    if (-not (Test-Path $versionDir)) {
        New-Item -ItemType Directory -Path $versionDir -Force | Out-Null
        Write-Host "  Created releases/$Version/" -ForegroundColor Green
    }

    $manifestPath = Join-Path $versionDir "manifest.json"
    if (-not (Test-Path $manifestPath)) {
        $manifest = @{
            version        = $Version
            release_date   = (Get-Date).ToString("yyyy-MM-dd")
            migrations     = @("migrations/v$versionUnderscore.py")
            upgrade_config = "upgrade_config.json"
            features       = @()
            config_changes = @()
            env_changes    = @()
        } | ConvertTo-Json
        $manifest | Set-Content -Path $manifestPath -Encoding UTF8
        Write-Host "  Created releases/$Version/manifest.json" -ForegroundColor Green
    }

    $upgradePath = Join-Path $versionDir "upgrade_config.json"
    if (-not (Test-Path $upgradePath)) {
        $upgrade = @{
            export_info = @{
                created_at      = (Get-Date).ToString("yyyy-MM-ddTHH:mm:ssZ")
                target_version  = $Version
                description    = "Incremental upgrade config for v$Version. Add only NEW items."
                collections    = @("system_configs", "prompt_templates", "agent_configs", "workflow_definitions", "tool_configs")
                format         = "json"
            }
            data = @{
                system_configs     = @()
                prompt_templates   = @()
                agent_configs      = @()
                workflow_definitions = @()
                tool_configs       = @()
            }
        } | ConvertTo-Json -Depth 5
        $upgrade | Set-Content -Path $upgradePath -Encoding UTF8
        Write-Host "  Created releases/$Version/upgrade_config.json" -ForegroundColor Green
    }

    if (-not (Test-Path $migrationFile)) {
        $migrationTemplate = @"
"""
v$Version migration

Add schema changes, new indexes, or default values here.
All operations must be idempotent (safe to run multiple times).
"""

VERSION = "$Version"
DESCRIPTION = "v$Version migration"


async def upgrade(db):
    # Example: await db.migration_history.create_index([("status", 1)])
    pass


async def downgrade(db):
    pass


"@
        $migrationTemplate | Set-Content -Path $migrationFile -Encoding UTF8
        Write-Host "  Created migrations/v$versionUnderscore.py" -ForegroundColor Green
    }

    Write-Host ""
}

# ── Step 1: Generate BUILD_INFO ─────────────────────────────────────────────────
Write-Host "[1/4] Generating BUILD_INFO..." -ForegroundColor Yellow
$buildInfoScript = Join-Path $root "scripts\build\generate_build_info.ps1"
if (Test-Path $buildInfoScript) {
    & powershell -ExecutionPolicy Bypass -File $buildInfoScript -BuildType "installer" -ProjectRoot $root
} else {
    Write-Host "  Warning: generate_build_info.ps1 not found" -ForegroundColor Yellow
}
Write-Host ""

# ── Step 2: Build installer (includes portable + 7z + update package) ─────────
Write-Host "[2/4] Building installer (portable + 7z + NSIS + update package)..." -ForegroundColor Yellow
$installerScript = Join-Path $root "scripts\windows-installer\build\build_installer.ps1"
if ($SkipInstaller) {
    Write-Host "  Skipped (SkipInstaller)" -ForegroundColor Gray
    $proScript = Join-Path $root "scripts\deployment\build_pro_package.ps1"
    & powershell -ExecutionPolicy Bypass -File $proScript -Version $Version
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    $updateScript = Join-Path $root "scripts\deployment\build_update_package.ps1"
    & powershell -ExecutionPolicy Bypass -File $updateScript -Version $Version
} elseif (Test-Path $installerScript) {
    & powershell -ExecutionPolicy Bypass -File $installerScript -Version $Version
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
} else {
    Write-Host "  ERROR: build_installer.ps1 not found" -ForegroundColor Red
    exit 1
}
Write-Host ""

# ── Step 3: Summary ───────────────────────────────────────────────────────────
Write-Host "[3/4] Release complete" -ForegroundColor Green
$packagesDir = Join-Path $root "release\packages"
if (Test-Path $packagesDir) {
    Get-ChildItem -Path $packagesDir -Filter "*.exe" | ForEach-Object { Write-Host "  Installer: $($_.Name)" -ForegroundColor White }
    Get-ChildItem -Path $packagesDir -Filter "update-*.zip" | ForEach-Object { Write-Host "  Update: $($_.Name)" -ForegroundColor White }
}
Write-Host ""
Write-Host "============================================================================" -ForegroundColor Cyan
Write-Host "  Done. Version: $Version" -ForegroundColor Green
Write-Host "============================================================================" -ForegroundColor Cyan
