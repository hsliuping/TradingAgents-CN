# ============================================================================
# Sync Code to Portable Release
# ============================================================================
# Features:
# 1. Sync core files from main codebase to release/TradingAgentsCN-portable
# 2. Preserve portable-specific configs and scripts
# 3. Auto-handle dependency updates
# 4. Generate sync report
# ============================================================================

param(
    [switch]$SkipDependencies,
    [switch]$DryRun,
    [switch]$Force
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$portableDir = Join-Path $root "release\TradingAgentsCN-portable"

Write-Host "============================================================================" -ForegroundColor Cyan
Write-Host "  Sync Code to Portable Release" -ForegroundColor Cyan
Write-Host "============================================================================" -ForegroundColor Cyan
Write-Host ""

if (-not (Test-Path $portableDir)) {
    Write-Host "ERROR: Portable directory not found: $portableDir" -ForegroundColor Red
    exit 1
}

Write-Host "Source: $root" -ForegroundColor Green
Write-Host "Target: $portableDir" -ForegroundColor Green
Write-Host ""

# ============================================================================
# Define directories and files to sync
# ============================================================================

$syncDirs = @(
    "app",
    "tradingagents",
    "web",
    "docs",
    "tests",
    "examples",
    "prompts",
    "config",
    "install"
)

$syncFiles = @(
    "requirements.txt",
    "README.md",
    ".env.example",
    "start_api.py"
)

$excludePatterns = @(
    "__pycache__",
    "*.pyc",
    "*.pyo",
    ".pytest_cache",
    ".mypy_cache",
    "*.log",
    ".DS_Store",
    "Thumbs.db",
    "node_modules",
    ".git",
    ".vscode",
    ".idea",
    "*.egg-info",
    "dist",
    "build"
)

$portableSpecific = @(
    ".env",
    "data",
    "logs",
    "temp",
    "runtime",
    "vendors",
    "venv",  # venv is created separately in portable directory
    "frontend",
    "scripts\import_config_and_create_user.py",
    "scripts\init_mongodb_user.py",
    "start_all.ps1",
    "start_services_clean.ps1",
    "stop_all.ps1",
    "README_STARTUP.txt"
)

# ============================================================================
# Helper Functions
# ============================================================================

function Test-ShouldExclude {
    param([string]$Path)

    foreach ($pattern in $excludePatterns) {
        if ($Path -like "*$pattern*") {
            return $true
        }
    }
    return $false
}

function Test-IsPortableSpecific {
    param([string]$RelativePath)

    foreach ($specific in $portableSpecific) {
        $normalized = $specific -replace '\\', '/'
        $relNormalized = $RelativePath -replace '\\', '/'

        if ($relNormalized -eq $normalized -or $relNormalized -like "$normalized/*") {
            return $true
        }
    }
    return $false
}

function Copy-WithProgress {
    param(
        [string]$Source,
        [string]$Destination,
        [string]$Description
    )

    if ($DryRun) {
        Write-Host "  [DRY RUN] Will copy: $Description" -ForegroundColor Yellow
        return
    }

    try {
        $destDir = Split-Path -Parent $Destination
        if (-not (Test-Path $destDir)) {
            New-Item -ItemType Directory -Path $destDir -Force | Out-Null
        }

        Copy-Item -Path $Source -Destination $Destination -Force
        Write-Host "  OK: $Description" -ForegroundColor Green
    } catch {
        Write-Host "  FAILED: $Description - $_" -ForegroundColor Red
    }
}

# ============================================================================
# Start Sync
# ============================================================================

$syncCount = 0
$skipCount = 0
$errorCount = 0

Write-Host "Syncing files..." -ForegroundColor Cyan
Write-Host ""

# 1. Sync directories
foreach ($dir in $syncDirs) {
    $sourceDir = Join-Path $root $dir
    $destDir = Join-Path $portableDir $dir

    if (-not (Test-Path $sourceDir)) {
        Write-Host "SKIP: Directory not found: $dir" -ForegroundColor Yellow
        continue
    }

    Write-Host "Syncing directory: $dir" -ForegroundColor Cyan

    $files = Get-ChildItem -Path $sourceDir -Recurse -File

    foreach ($file in $files) {
        $relativePath = $file.FullName.Substring($sourceDir.Length + 1)
        $destFile = Join-Path $destDir $relativePath
        $relativeFromRoot = Join-Path $dir $relativePath

        if (Test-ShouldExclude $file.FullName) {
            continue
        }

        if (Test-IsPortableSpecific $relativeFromRoot) {
            Write-Host "  SKIP: Portable-specific file: $relativeFromRoot" -ForegroundColor DarkGray
            $skipCount++
            continue
        }

        Copy-WithProgress -Source $file.FullName -Destination $destFile -Description $relativeFromRoot
        $syncCount++
    }

    Write-Host ""
}

# 2. Sync individual files
Write-Host "Syncing root files..." -ForegroundColor Cyan
foreach ($file in $syncFiles) {
    $sourceFile = Join-Path $root $file
    $destFile = Join-Path $portableDir $file

    if (-not (Test-Path $sourceFile)) {
        Write-Host "  SKIP: File not found: $file" -ForegroundColor Yellow
        continue
    }

    if (Test-IsPortableSpecific $file) {
        Write-Host "  SKIP: Portable-specific file: $file" -ForegroundColor DarkGray
        $skipCount++
        continue
    }

    Copy-WithProgress -Source $sourceFile -Destination $destFile -Description $file
    $syncCount++
}

Write-Host ""

# ============================================================================
# Stage startup and initialization files
# ============================================================================
# These files are intentionally excluded from the normal source sync because
# the portable release has its own startup layout. Always copy the tracked
# versions so an old generated script cannot remain in the distributable.

function Copy-RequiredFile {
    param(
        [string]$SourceRelativePath,
        [string]$DestinationRelativePath
    )

    if ($DryRun) {
        Write-Host "  [DRY RUN] Will copy: $DestinationRelativePath" -ForegroundColor Yellow
        return
    }

    $source = Join-Path $root $SourceRelativePath
    $destination = Join-Path $portableDir $DestinationRelativePath
    if (-not (Test-Path -LiteralPath $source -PathType Leaf)) {
        throw "Required portable file not found: $source"
    }

    $destinationDir = Split-Path -Parent $destination
    if (-not (Test-Path -LiteralPath $destinationDir)) {
        New-Item -ItemType Directory -Path $destinationDir -Force | Out-Null
    }
    Copy-Item -LiteralPath $source -Destination $destination -Force
    Write-Host "  OK: $DestinationRelativePath" -ForegroundColor Green
}

$portableStartupFiles = @(
    @{ Source = "scripts\installer\setup.ps1"; Destination = "scripts\installer\setup.ps1" },
    @{ Source = "scripts\installer\start_all.ps1"; Destination = "scripts\installer\start_all.ps1" },
    @{ Source = "scripts\installer\start_services_clean.ps1"; Destination = "scripts\installer\start_services_clean.ps1" },
    @{ Source = "scripts\installer\stop_all.ps1"; Destination = "scripts\installer\stop_all.ps1" },
    @{ Source = "scripts\installer\start_all.ps1"; Destination = "start_all.ps1" },
    @{ Source = "scripts\installer\start_services_clean.ps1"; Destination = "start_services_clean.ps1" },
    @{ Source = "scripts\installer\stop_all.ps1"; Destination = "stop_all.ps1" },
    @{ Source = "scripts\import_config_and_create_user.py"; Destination = "scripts\import_config_and_create_user.py" },
    @{ Source = "scripts\init_mongodb_user.py"; Destination = "scripts\init_mongodb_user.py" }
)

Write-Host "Staging portable startup files..." -ForegroundColor Cyan
foreach ($file in $portableStartupFiles) {
    try {
        Copy-RequiredFile -SourceRelativePath $file.Source -DestinationRelativePath $file.Destination
        $syncCount++
    } catch {
        Write-Host "  FAILED: $($file.Destination) - $_" -ForegroundColor Red
        $errorCount++
    }
}

if ($errorCount -gt 0) {
    Write-Host "ERROR: Required portable files could not be staged." -ForegroundColor Red
    exit 1
}

Write-Host ""

# ============================================================================
# Check Dependency Updates
# ============================================================================

if (-not $SkipDependencies) {
    Write-Host "Checking dependency updates..." -ForegroundColor Cyan

    $sourceReq = Join-Path $root "requirements.txt"
    $destReq = Join-Path $portableDir "requirements.txt"

    if ((Test-Path $sourceReq) -and (Test-Path $destReq)) {
        $sourceHash = (Get-FileHash $sourceReq -Algorithm MD5).Hash
        $destHash = (Get-FileHash $destReq -Algorithm MD5).Hash

        if ($sourceHash -ne $destHash) {
            Write-Host "  WARNING: requirements.txt updated, please reinstall dependencies" -ForegroundColor Yellow
            Write-Host "  Command: cd release\TradingAgentsCN-portable; venv\Scripts\pip install -r requirements.txt" -ForegroundColor Yellow
        } else {
            Write-Host "  OK: Dependencies file unchanged" -ForegroundColor Green
        }
    }

    Write-Host ""
}

# ============================================================================
# Generate Sync Report
# ============================================================================

Write-Host "============================================================================" -ForegroundColor Cyan
Write-Host "  Sync Complete" -ForegroundColor Cyan
Write-Host "============================================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Statistics:" -ForegroundColor Green
Write-Host "  Synced: $syncCount files" -ForegroundColor Green
Write-Host "  Skipped: $skipCount files (portable-specific)" -ForegroundColor Yellow
if ($errorCount -gt 0) {
    Write-Host "  Failed: $errorCount files" -ForegroundColor Red
}
Write-Host ""

if ($DryRun) {
    Write-Host "NOTE: This was a dry run, no files were actually copied" -ForegroundColor Yellow
    Write-Host "      Remove -DryRun parameter to perform actual sync" -ForegroundColor Yellow
    Write-Host ""
}

Write-Host "Sync completed successfully!" -ForegroundColor Green
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Cyan
Write-Host "  1. Update dependencies: cd release\TradingAgentsCN-portable; venv\Scripts\pip install -r requirements.txt" -ForegroundColor White
Write-Host "  2. Test portable version: cd release\TradingAgentsCN-portable; powershell -ExecutionPolicy Bypass -File start_all.ps1" -ForegroundColor White
Write-Host "  3. Verify functionality: visit http://localhost" -ForegroundColor White
Write-Host ""

# Exit with success code
exit 0
