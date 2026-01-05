# ============================================================================
# Build TradingAgents-CN Pro Package
# ============================================================================
# 专业版一键打包脚本
#
# 功能：
# 1. 使用Pro版同步脚本（排除课程源码）
# 2. 构建前端
# 3. 打包为压缩文件
#
# 使用方法：
#   .\scripts\deployment\build_pro_package.ps1
#   .\scripts\deployment\build_pro_package.ps1 -Version "v1.0.0"
# ============================================================================

param(
    [string]$Version = "",
    [switch]$SkipSync = $false,
    [switch]$SkipEmbeddedPython = $false,
    [string]$PythonVersion = "3.10.11"
)

# 设置控制台和文件编码为UTF-8
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
[Console]::InputEncoding = [System.Text.Encoding]::UTF8
$PSDefaultParameterValues['*:Encoding'] = 'utf8'
$OutputEncoding = [System.Text.Encoding]::UTF8

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$portableDir = Join-Path $root "release\TradingAgentsCN-portable"

Write-Host "============================================================================" -ForegroundColor Cyan
Write-Host "  Build TradingAgents-CN Pro Package" -ForegroundColor Cyan
Write-Host "============================================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "⚠️  Pro版打包 - 将排除课程源码和敏感内容" -ForegroundColor Yellow
Write-Host ""

# ============================================================================
# Step 1: Sync Code (使用Pro版同步脚本)
# ============================================================================

if (-not $SkipSync) {
    Write-Host "[1/4] Syncing code to portable directory (Pro version)..." -ForegroundColor Yellow
    Write-Host ""

    $syncScript = Join-Path $root "scripts\deployment\sync_to_portable_pro.ps1"
    if (-not (Test-Path $syncScript)) {
        Write-Host "ERROR: Pro sync script not found: $syncScript" -ForegroundColor Red
        Write-Host "Please ensure sync_to_portable_pro.ps1 exists" -ForegroundColor Yellow
        exit 1
    }

    try {
        & powershell -ExecutionPolicy Bypass -File $syncScript
        if ($LASTEXITCODE -ne 0) {
            Write-Host "ERROR: Sync failed with exit code $LASTEXITCODE" -ForegroundColor Red
            exit 1
        }
    } catch {
        Write-Host "ERROR: Sync failed: $_" -ForegroundColor Red
        exit 1
    }

    Write-Host ""
    Write-Host "✅ Sync completed (course source excluded)" -ForegroundColor Green
    Write-Host ""
} else {
    Write-Host "[1/5] Skipping sync (using existing files)..." -ForegroundColor Yellow
    Write-Host ""
}

# ============================================================================
# Step 1.5: Compile core/ directory (hybrid strategy)
# ============================================================================

Write-Host "[1.5/5] Compiling core/ directory..." -ForegroundColor Yellow
Write-Host ""

$compileScript = Join-Path $root "scripts\deployment\compile_core_hybrid.ps1"
if (Test-Path $compileScript) {
    try {
        & powershell -ExecutionPolicy Bypass -File $compileScript
        if ($LASTEXITCODE -eq 0) {
            Write-Host ""
            Write-Host "✅ Core compilation completed!" -ForegroundColor Green
        } else {
            Write-Host "⚠️  Core compilation failed, continuing with source code..." -ForegroundColor Yellow
        }
    } catch {
        Write-Host "⚠️  Core compilation error: $_" -ForegroundColor Yellow
        Write-Host "Continuing with source code..." -ForegroundColor Gray
    }
} else {
    Write-Host "⚠️  Compile script not found, skipping compilation" -ForegroundColor Yellow
}

Write-Host ""

# ============================================================================
# Step 2: Setup Embedded Python (if not present)
# ============================================================================

if (-not $SkipEmbeddedPython) {
    $pythonExe = Join-Path $portableDir "vendors\python\python.exe"

    if (-not (Test-Path $pythonExe)) {
        Write-Host "[2/4] Setting up embedded Python..." -ForegroundColor Yellow
        Write-Host ""

        $setupScript = Join-Path $root "scripts\deployment\setup_embedded_python.ps1"
        if (Test-Path $setupScript) {
            try {
                & powershell -ExecutionPolicy Bypass -File $setupScript -PythonVersion $PythonVersion -PortableDir $portableDir
                if ($LASTEXITCODE -eq 0) {
                    Write-Host ""
                    Write-Host "  ✅ Embedded Python setup completed!" -ForegroundColor Green
                }
            } catch {
                Write-Host "  ⚠️ Embedded Python setup error: $_" -ForegroundColor Yellow
            }
        }
        Write-Host ""
    } else {
        Write-Host "[2/5] Embedded Python already present, skipping..." -ForegroundColor Gray
        Write-Host ""
    }
} else {
    Write-Host "[2/4] Skipping embedded Python setup..." -ForegroundColor Gray
    Write-Host ""
}

# ============================================================================
# Step 3: Build Frontend
# ============================================================================

Write-Host "[3/5] Building frontend..." -ForegroundColor Yellow
Write-Host ""

$frontendDir = Join-Path $root "frontend"
$frontendDistSrc = Join-Path $frontendDir "dist"
$frontendDistDest = Join-Path $portableDir "frontend\dist"

if (Test-Path $frontendDir) {
    try {
        Write-Host "  Installing dependencies with Yarn..." -ForegroundColor Gray
        $installProcess = Start-Process -FilePath "cmd.exe" -ArgumentList "/c", "cd /d `"$frontendDir`" && yarn install --frozen-lockfile" -Wait -PassThru -NoNewWindow

        if ($installProcess.ExitCode -eq 0) {
            Write-Host "  ✅ Dependencies installed" -ForegroundColor Green
        }

        Write-Host "  Building frontend..." -ForegroundColor Gray
        $buildProcess = Start-Process -FilePath "cmd.exe" -ArgumentList "/c", "cd /d `"$frontendDir`" && yarn vite build" -Wait -PassThru -NoNewWindow

        if ($buildProcess.ExitCode -eq 0) {
            Write-Host "  ✅ Frontend build completed" -ForegroundColor Green

            if (Test-Path $frontendDistSrc) {
                if (Test-Path $frontendDistDest) {
                    Remove-Item -Path $frontendDistDest -Recurse -Force
                }
                Copy-Item -Path $frontendDistSrc -Destination $frontendDistDest -Recurse -Force
                Write-Host "  ✅ Frontend dist copied" -ForegroundColor Green
            }
        }
    } catch {
        Write-Host "  ⚠️ Frontend build failed: $_" -ForegroundColor Yellow
    }
}

Write-Host ""

# ============================================================================
# Step 3.5: Compile Python Code (Pro Version)
# ============================================================================

Write-Host "[3.5/5] Compiling Python code (Pro Version)..." -ForegroundColor Yellow
Write-Host ""

# 调用完整编译脚本
$compileScript = Join-Path $root "scripts\deployment\compile_pro_complete.ps1"

if (Test-Path $compileScript) {
    & powershell -ExecutionPolicy Bypass -File $compileScript -PortableDir $portableDir

    if ($LASTEXITCODE -ne 0) {
        Write-Host "ERROR: Compilation failed" -ForegroundColor Red
        exit 1
    }
} else {
    Write-Host "ERROR: Compile script not found: $compileScript" -ForegroundColor Red
    exit 1
}

Write-Host "  ✅ All Python code compiled" -ForegroundColor Green
Write-Host ""

# ============================================================================
# Step 4: Package
# ============================================================================

Write-Host "[4/5] Packaging..." -ForegroundColor Yellow
Write-Host ""

# 调用原有的打包脚本，但跳过同步步骤
$packageScript = Join-Path $root "scripts\deployment\build_portable_package.ps1"

if (Test-Path $packageScript) {
    if ($Version) {
        & powershell -ExecutionPolicy Bypass -File $packageScript -SkipSync -Version $Version
    } else {
        & powershell -ExecutionPolicy Bypass -File $packageScript -SkipSync
    }
} else {
    Write-Host "ERROR: Package script not found: $packageScript" -ForegroundColor Red
    exit 1
}

