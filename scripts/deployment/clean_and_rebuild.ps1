# ============================================================================
# Clean and Rebuild Portable Package
# ============================================================================
# 清理旧的便携版目录并重新构建
# 用于解决缓存问题和确保使用最新代码
# ============================================================================

param(
    [string]$Version = "",
    [switch]$SkipClean = $false,
    [switch]$SkipVerify = $false
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$portableDir = Join-Path $root "release\TradingAgentsCN-portable"

Write-Host "============================================================================" -ForegroundColor Cyan
Write-Host "  Clean and Rebuild Portable Package" -ForegroundColor Cyan
Write-Host "============================================================================" -ForegroundColor Cyan
Write-Host ""

# ============================================================================
# Step 0: Check for running Python processes
# ============================================================================

Write-Host "[0/3] Checking for running Python processes..." -ForegroundColor Yellow
Write-Host ""

$checkScript = Join-Path $root "scripts\deployment\check_python_processes.ps1"
if (Test-Path $checkScript) {
    try {
        & powershell -ExecutionPolicy Bypass -File $checkScript -Force
        if ($LASTEXITCODE -ne 0) {
            Write-Host ""
            Write-Host "⚠️  Python processes detected, but continuing anyway..." -ForegroundColor Yellow
            Write-Host "Build may hang if files are locked!" -ForegroundColor Red
            Write-Host ""
        }
    } catch {
        Write-Host "⚠️  Process check failed: $_" -ForegroundColor Yellow
        Write-Host "Continuing anyway..." -ForegroundColor Gray
    }
} else {
    Write-Host "⚠️  Process check script not found, skipping..." -ForegroundColor Yellow
}

Write-Host ""

# ============================================================================
# Step 1: Clean old portable directory
# ============================================================================

if (-not $SkipClean) {
    if (Test-Path $portableDir) {
        Write-Host "[1/3] Cleaning old portable directory..." -ForegroundColor Yellow
        Write-Host ""
        Write-Host "  Removing: $portableDir" -ForegroundColor Gray
        
        try {
            Remove-Item -Path $portableDir -Recurse -Force
            Write-Host "  ✅ Old directory removed" -ForegroundColor Green
        } catch {
            Write-Host "  ❌ Failed to remove directory: $_" -ForegroundColor Red
            Write-Host ""
            Write-Host "Please close any programs using files in this directory and try again." -ForegroundColor Yellow
            exit 1
        }
        
        Write-Host ""
    } else {
        Write-Host "[1/3] No old portable directory found, skipping clean..." -ForegroundColor Gray
        Write-Host ""
    }
} else {
    Write-Host "[1/3] Skipping clean (--SkipClean)..." -ForegroundColor Gray
    Write-Host ""
}

# ============================================================================
# Step 2: Rebuild portable package
# ============================================================================

Write-Host "[2/3] Rebuilding portable package..." -ForegroundColor Yellow
Write-Host ""

$buildScript = Join-Path $root "scripts\deployment\build_pro_package.ps1"

if (-not (Test-Path $buildScript)) {
    Write-Host "❌ Build script not found: $buildScript" -ForegroundColor Red
    exit 1
}

$buildArgs = @()
if ($Version) {
    $buildArgs += "-Version", $Version
}

try {
    & powershell -ExecutionPolicy Bypass -File $buildScript @buildArgs
    if ($LASTEXITCODE -ne 0) {
        Write-Host "❌ Build failed with exit code $LASTEXITCODE" -ForegroundColor Red
        exit 1
    }
    Write-Host ""
    Write-Host "✅ Build completed successfully!" -ForegroundColor Green
} catch {
    Write-Host "❌ Build failed: $_" -ForegroundColor Red
    exit 1
}

Write-Host ""

# ============================================================================
# Step 3: Verify prompts files
# ============================================================================

if (-not $SkipVerify) {
    Write-Host "[3/3] Verifying prompts files..." -ForegroundColor Yellow
    Write-Host ""
    
    $verifyScript = Join-Path $root "scripts\deployment\verify_prompts_in_portable.ps1"
    
    if (Test-Path $verifyScript) {
        try {
            & powershell -ExecutionPolicy Bypass -File $verifyScript
            if ($LASTEXITCODE -ne 0) {
                Write-Host ""
                Write-Host "❌ Verification failed!" -ForegroundColor Red
                exit 1
            }
        } catch {
            Write-Host "❌ Verification error: $_" -ForegroundColor Red
            exit 1
        }
    } else {
        Write-Host "⚠️  Verify script not found, skipping verification" -ForegroundColor Yellow
    }
} else {
    Write-Host "[3/3] Skipping verification (--SkipVerify)..." -ForegroundColor Gray
}

Write-Host ""
Write-Host "============================================================================" -ForegroundColor Cyan
Write-Host "✅ Clean and rebuild completed successfully!" -ForegroundColor Green
Write-Host "============================================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Next steps:" -ForegroundColor White
Write-Host "  1. Build Windows installer:" -ForegroundColor Yellow
Write-Host "     .\scripts\windows-installer\build\build_installer.ps1 -SkipPortablePackage" -ForegroundColor Gray
Write-Host ""
Write-Host "  2. Or package as 7z for manual distribution:" -ForegroundColor Yellow
Write-Host "     Already done! Check release\packages\ directory" -ForegroundColor Gray
Write-Host ""

