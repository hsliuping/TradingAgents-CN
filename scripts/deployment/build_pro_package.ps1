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
    [string]$PythonVersion = "3.10.11",
    [switch]$Interactive = $false  # 🔥 交互模式：每步后确认
)

# 设置控制台和文件编码为UTF-8
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
[Console]::InputEncoding = [System.Text.Encoding]::UTF8
$PSDefaultParameterValues['*:Encoding'] = 'utf8'
$OutputEncoding = [System.Text.Encoding]::UTF8

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$portableDir = Join-Path $root "release\TradingAgentsCN-portable"
$setFrontendVersionScript = Join-Path $PSScriptRoot "set_frontend_version_env.ps1"

# ============================================================================
# 辅助函数：交互式确认
# ============================================================================

function Confirm-NextStep {
    param([string]$StepName)

    if (-not $Interactive) {
        return $true
    }

    Write-Host ""
    Write-Host "============================================================================" -ForegroundColor Yellow
    Write-Host "  Step completed: $StepName" -ForegroundColor Yellow
    Write-Host "============================================================================" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Please verify the results above." -ForegroundColor Cyan
    Write-Host ""

    $response = Read-Host "Continue to next step? (Y/n)"

    if ($response -eq "" -or $response -eq "Y" -or $response -eq "y") {
        Write-Host ""
        return $true
    } else {
        Write-Host ""
        Write-Host "Build stopped by user." -ForegroundColor Yellow
        exit 0
    }
}

Write-Host "============================================================================" -ForegroundColor Cyan
Write-Host "  Build TradingAgents-CN Pro Package" -ForegroundColor Cyan
Write-Host "============================================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "⚠️  Pro版打包 - 将排除课程源码和敏感内容" -ForegroundColor Yellow

if ($Interactive) {
    Write-Host "🔧 Interactive mode enabled - will prompt after each step" -ForegroundColor Cyan
}

Write-Host ""

# ============================================================================
# Step 0: Clean old compiled files (确保使用最新源码)
# ============================================================================

Write-Host "[0/5] Cleaning old compiled files in portable directory..." -ForegroundColor Yellow
Write-Host ""

$cleanDirs = @(
    "core",
    "app",
    "tradingagents"
)

$cleanedCount = 0

foreach ($dir in $cleanDirs) {
    $targetDir = Join-Path $portableDir $dir

    if (Test-Path $targetDir) {
        Write-Host "  Cleaning $dir..." -ForegroundColor Gray

        # 删除所有 __pycache__ 目录
        $cacheDirs = Get-ChildItem -Path $targetDir -Recurse -Directory -Filter "__pycache__" -ErrorAction SilentlyContinue
        if ($cacheDirs) {
            $cacheDirs | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
            $cleanedCount += $cacheDirs.Count
        }

        # 删除所有 .pyc 文件
        $pycFiles = Get-ChildItem -Path $targetDir -Recurse -Filter "*.pyc" -ErrorAction SilentlyContinue
        if ($pycFiles) {
            $pycFiles | Remove-Item -Force -ErrorAction SilentlyContinue
            $cleanedCount += $pycFiles.Count
        }

        # 删除所有 .pyd 文件（Cython编译的扩展）
        $pydFiles = Get-ChildItem -Path $targetDir -Recurse -Filter "*.pyd" -ErrorAction SilentlyContinue
        if ($pydFiles) {
            $pydFiles | Remove-Item -Force -ErrorAction SilentlyContinue
            $cleanedCount += $pydFiles.Count
        }

        # 删除所有 .pyo 文件
        $pyoFiles = Get-ChildItem -Path $targetDir -Recurse -Filter "*.pyo" -ErrorAction SilentlyContinue
        if ($pyoFiles) {
            $pyoFiles | Remove-Item -Force -ErrorAction SilentlyContinue
            $cleanedCount += $pyoFiles.Count
        }

        Write-Host "    ✅ Cleaned $dir" -ForegroundColor Green
    }
}

if ($cleanedCount -gt 0) {
    Write-Host ""
    Write-Host "  ✅ Cleaned $cleanedCount compiled files" -ForegroundColor Green
} else {
    Write-Host "  ℹ️  No compiled files found (first build or already clean)" -ForegroundColor Cyan
}

Write-Host ""

# 🔧 交互式确认
Confirm-NextStep "Clean old compiled files" | Out-Null

# ============================================================================
# Step 1: Sync Code (使用Pro版同步脚本)
# ============================================================================

if (-not $SkipSync) {
    Write-Host "[1/5] Syncing code to portable directory (Pro version)..." -ForegroundColor Yellow
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
    Write-Host "[1/4] Skipping sync (using existing files)..." -ForegroundColor Yellow
    Write-Host ""
}

# 🔧 交互式确认
Confirm-NextStep "Sync source code" | Out-Null

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
        Write-Host "[2/4] Embedded Python already present, skipping..." -ForegroundColor Gray
        Write-Host ""
    }
} else {
    Write-Host "[2/4] Skipping embedded Python setup..." -ForegroundColor Gray
    Write-Host ""
}

# 🔧 交互式确认
Confirm-NextStep "Setup embedded Python" | Out-Null

# ============================================================================
# Step 3: Build Frontend
# ============================================================================

Write-Host "[3/4] Building frontend..." -ForegroundColor Yellow
Write-Host ""

$frontendDir = Join-Path $root "frontend"
$frontendDistSrc = Join-Path $frontendDir "dist"
$frontendDistDest = Join-Path $portableDir "frontend\dist"
$viteCacheDir = Join-Path $frontendDir ".vite"

if (Test-Path $frontendDir) {
    try {
        if (Test-Path $setFrontendVersionScript) {
            Write-Host "  Injecting frontend version from VERSION..." -ForegroundColor Gray
            & $setFrontendVersionScript -RootPath $root
        }

        # 清理旧的构建产物
        Write-Host "  Cleaning old build artifacts..." -ForegroundColor Gray
        if (Test-Path $frontendDistSrc) {
            Remove-Item -Path $frontendDistSrc -Recurse -Force -ErrorAction SilentlyContinue
            Write-Host "    ✅ Removed old dist directory" -ForegroundColor Green
        }
        
        # 清理 Vite 缓存
        if (Test-Path $viteCacheDir) {
            Remove-Item -Path $viteCacheDir -Recurse -Force -ErrorAction SilentlyContinue
            Write-Host "    ✅ Removed Vite cache" -ForegroundColor Green
        }
        
        # 安装依赖
        Write-Host "  Installing dependencies with Yarn..." -ForegroundColor Gray
        $installProcess = Start-Process -FilePath "cmd.exe" -ArgumentList "/c", "cd /d `"$frontendDir`" && yarn install --frozen-lockfile" -Wait -PassThru -NoNewWindow

        if ($installProcess.ExitCode -ne 0) {
            Write-Host "  ❌ ERROR: Yarn install failed with exit code $($installProcess.ExitCode)" -ForegroundColor Red
            throw "Frontend dependencies installation failed"
        }
        Write-Host "  ✅ Dependencies installed" -ForegroundColor Green

        # 构建前端
        Write-Host "  Building frontend..." -ForegroundColor Gray
        $buildProcess = Start-Process -FilePath "cmd.exe" -ArgumentList "/c", "cd /d `"$frontendDir`" && yarn vite build" -Wait -PassThru -NoNewWindow

        if ($buildProcess.ExitCode -ne 0) {
            Write-Host "  ❌ ERROR: Frontend build failed with exit code $($buildProcess.ExitCode)" -ForegroundColor Red
            throw "Frontend build failed"
        }
        
        Write-Host "  ✅ Frontend build completed" -ForegroundColor Green

        # 检查构建产物是否存在
        if (-not (Test-Path $frontendDistSrc)) {
            Write-Host "  ❌ ERROR: Frontend dist directory not found after build: $frontendDistSrc" -ForegroundColor Red
            throw "Frontend dist directory not found"
        }
        
        # 复制构建产物到便携版目录
        Write-Host "  Copying frontend dist to portable directory..." -ForegroundColor Gray
        if (Test-Path $frontendDistDest) {
            Remove-Item -Path $frontendDistDest -Recurse -Force
        }
        Copy-Item -Path $frontendDistSrc -Destination $frontendDistDest -Recurse -Force
        Write-Host "  ✅ Frontend dist copied" -ForegroundColor Green
        
    } catch {
        Write-Host "  ❌ Frontend build failed: $_" -ForegroundColor Red
        Write-Host "  Please check the error above and fix the frontend build issues." -ForegroundColor Yellow
        throw
    }
} else {
    Write-Host "  ⚠️ Frontend directory not found: $frontendDir" -ForegroundColor Yellow
    throw "Frontend directory not found"
}

Write-Host ""

# 🔧 交互式确认
Confirm-NextStep "Build frontend" | Out-Null

# ============================================================================
# Step 4: Compile Python Code (Pro Version)
# ============================================================================

Write-Host "[4/4] Compiling Python code (Pro Version)..." -ForegroundColor Yellow
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

# 🔧 交互式确认
Confirm-NextStep "Compile Python code" | Out-Null

# ============================================================================
# 完成提示（打包由 build_portable_package.ps1 处理）
# ============================================================================

Write-Host "============================================================================" -ForegroundColor Green
Write-Host "  Pro Package Build Completed!" -ForegroundColor Green
Write-Host "============================================================================" -ForegroundColor Green
Write-Host ""
Write-Host "Portable directory ready at:" -ForegroundColor Cyan
Write-Host "  $portableDir" -ForegroundColor White
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host "  1. Test the portable version locally" -ForegroundColor Gray
Write-Host "  2. Build installer: .\scripts\windows-installer\build\build_installer.ps1" -ForegroundColor Gray
Write-Host ""

