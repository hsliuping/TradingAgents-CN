# ============================================================================
# Complete Pro Version Compilation Strategy
# ============================================================================
# 完整的Pro版编译策略：
# 1. tradingagents/     → 源码发布（开源部分）
# 2. core/licensing/    → Cython编译（最关键）
# 3. core/其他目录      → 字节码编译
# 4. app/               → 字节码编译
# 5. frontend/          → Vite构建（已编译）
# ============================================================================

# UTF-8编码设置
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
[Console]::InputEncoding = [System.Text.Encoding]::UTF8
$PSDefaultParameterValues['*:Encoding'] = 'utf8'
$OutputEncoding = [System.Text.Encoding]::UTF8

param(
    [string]$PortableDir = ""
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)

Write-Host "============================================================================" -ForegroundColor Cyan
Write-Host "  Complete Pro Version Compilation" -ForegroundColor Cyan
Write-Host "============================================================================" -ForegroundColor Cyan
Write-Host ""

# ============================================================================
# 设置路径
# ============================================================================

if (-not $PortableDir) {
    $PortableDir = Join-Path $root "release\TradingAgentsCN-portable"
}

if (-not (Test-Path $PortableDir)) {
    Write-Host "ERROR: Portable directory not found: $PortableDir" -ForegroundColor Red
    exit 1
}

Write-Host "Portable directory: $PortableDir" -ForegroundColor White
Write-Host ""

# ============================================================================
# Step 0: 清理所有旧的缓存和编译文件（编译前清理）
# ============================================================================

Write-Host "[0/4] Cleaning old cache and compiled files before compilation..." -ForegroundColor Yellow
Write-Host ""

$cleanedCacheDirs = 0
$cleanedPycFiles = 0
$cleanedPydFiles = 0
$cleanedPyoFiles = 0

# 清理所有 __pycache__ 目录
$cacheDirs = Get-ChildItem -Path $PortableDir -Recurse -Directory -Filter "__pycache__" -ErrorAction SilentlyContinue
if ($cacheDirs) {
    $cleanedCacheDirs = ($cacheDirs | Measure-Object).Count
    $cacheDirs | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
    Write-Host "  ✅ Cleaned $cleanedCacheDirs __pycache__ directories" -ForegroundColor Green
}

# 清理所有旧的 .pyc 文件（编译前，所有 .pyc 都是旧的缓存）
$pycFiles = Get-ChildItem -Path $PortableDir -Recurse -Filter "*.pyc" -ErrorAction SilentlyContinue
if ($pycFiles) {
    $cleanedPycFiles = ($pycFiles | Measure-Object).Count
    $pycFiles | Remove-Item -Force -ErrorAction SilentlyContinue
    Write-Host "  ✅ Cleaned $cleanedPycFiles old .pyc files" -ForegroundColor Green
}

# 清理 core/licensing 目录下的旧 .pyd 文件（Cython 编译生成的）
# 🔥 重要：只清理项目生成的 .pyd 文件，不清理外部依赖的 .pyd 文件
$coreLicensingDir = Join-Path $PortableDir "core\licensing"
if (Test-Path $coreLicensingDir) {
    $pydFiles = Get-ChildItem -Path $coreLicensingDir -Recurse -Filter "*.pyd" -ErrorAction SilentlyContinue
    if ($pydFiles) {
        $cleanedPydFiles = ($pydFiles | Measure-Object).Count
        $pydFiles | Remove-Item -Force -ErrorAction SilentlyContinue
        Write-Host "  ✅ Cleaned $cleanedPydFiles old .pyd files in core/licensing" -ForegroundColor Green
    }
}

# 清理所有 .pyo 文件
$pyoFiles = Get-ChildItem -Path $PortableDir -Recurse -Filter "*.pyo" -ErrorAction SilentlyContinue
if ($pyoFiles) {
    $cleanedPyoFiles = ($pyoFiles | Measure-Object).Count
    $pyoFiles | Remove-Item -Force -ErrorAction SilentlyContinue
    Write-Host "  ✅ Cleaned $cleanedPyoFiles .pyo files" -ForegroundColor Green
}

if ($cleanedCacheDirs -eq 0 -and $cleanedPycFiles -eq 0 -and $cleanedPydFiles -eq 0 -and $cleanedPyoFiles -eq 0) {
    Write-Host "  ✅ No old cache/compiled files found" -ForegroundColor Green
}

Write-Host ""

# ============================================================================
# Step 1: 编译 core/ 目录（混合编译）
# ============================================================================

Write-Host "[1/3] Compiling core/ directory..." -ForegroundColor Yellow
Write-Host ""

$compileScript = Join-Path $PSScriptRoot "compile_core_hybrid.ps1"
& powershell -ExecutionPolicy Bypass -File $compileScript -OutputDir (Join-Path $PortableDir "core")

if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Core compilation failed" -ForegroundColor Red
    exit 1
}

Write-Host "  ✅ Core compilation completed" -ForegroundColor Green
Write-Host ""

# ============================================================================
# Step 2: 编译 app/ 目录（字节码）
# ============================================================================

Write-Host "[2/4] Compiling app/ directory..." -ForegroundColor Yellow
Write-Host ""

$appDir = Join-Path $PortableDir "app"
if (Test-Path $appDir) {
    # 🔥 编译前：清理 app/ 目录中的旧缓存和编译文件
    Write-Host "  Cleaning old cache in app/ directory..." -ForegroundColor Gray
    $appCacheDirs = Get-ChildItem -Path $appDir -Recurse -Directory -Filter "__pycache__" -ErrorAction SilentlyContinue
    if ($appCacheDirs) {
        $appCacheDirs | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
    }
    $appOldPyc = Get-ChildItem -Path $appDir -Recurse -Filter "*.pyc" -ErrorAction SilentlyContinue
    if ($appOldPyc) {
        $appOldPyc | Remove-Item -Force -ErrorAction SilentlyContinue
    }
    
    Write-Host "  Compiling app/ to bytecode..." -ForegroundColor Gray
    
    & python -OO -m compileall -b $appDir
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  Removing source files (keeping __init__.py and __main__.py)..." -ForegroundColor Gray
        $removedCount = 0
        Get-ChildItem -Path $appDir -Filter "*.py" -Recurse | ForEach-Object {
            # 保留 __init__.py 和 __main__.py
            if ($_.Name -notin @("__init__.py", "__main__.py")) {
                Remove-Item $_.FullName -Force
                $removedCount++
            }
        }
        Write-Host "  ✅ Removed $removedCount source files, kept compiled bytecode" -ForegroundColor Green
        Write-Host "  ✅ App compilation completed" -ForegroundColor Green
    } else {
        Write-Host "  ⚠️  App compilation failed, keeping source files" -ForegroundColor Yellow
    }
} else {
    Write-Host "  ⚠️  app/ directory not found, skipping" -ForegroundColor Yellow
}

Write-Host ""

# ============================================================================
# Step 3: 验证编译结果
# ============================================================================

Write-Host "[3/4] Verifying compilation results..." -ForegroundColor Yellow
Write-Host ""

# 验证 core/other/ 中的编译文件
$coreOtherPyc = Get-ChildItem -Path (Join-Path $PortableDir "core\other") -Recurse -Filter "*.pyc" -ErrorAction SilentlyContinue
if ($coreOtherPyc) {
    Write-Host "  ✅ core/other/ bytecode: $($coreOtherPyc.Count) .pyc files" -ForegroundColor Green
}

# 验证 core/licensing/ 中的编译文件
$coreLicensingPyd = Get-ChildItem -Path (Join-Path $PortableDir "core\licensing") -Recurse -Filter "*.pyd" -ErrorAction SilentlyContinue
if ($coreLicensingPyd) {
    Write-Host "  ✅ core/licensing/ Cython: $($coreLicensingPyd.Count) .pyd files" -ForegroundColor Green
}

# 验证 app/ 中的编译文件
$appPyc = Get-ChildItem -Path (Join-Path $PortableDir "app") -Recurse -Filter "*.pyc" -ErrorAction SilentlyContinue
if ($appPyc) {
    Write-Host "  ✅ app/ bytecode: $($appPyc.Count) .pyc files" -ForegroundColor Green
}

Write-Host ""

# ============================================================================
# Step 4: 验证 tradingagents/ 保持源码
# ============================================================================

Write-Host "[4/4] Verifying tradingagents/ source code..." -ForegroundColor Yellow
Write-Host ""

$tradingagentsDir = Join-Path $PortableDir "tradingagents"
if (Test-Path $tradingagentsDir) {
    $pyFiles = Get-ChildItem -Path $tradingagentsDir -Filter "*.py" -Recurse
    Write-Host "  ✅ tradingagents/ kept as source code ($($pyFiles.Count) .py files)" -ForegroundColor Green
} else {
    Write-Host "  ⚠️  tradingagents/ directory not found" -ForegroundColor Yellow
}

Write-Host ""

# ============================================================================
# 完成总结
# ============================================================================

Write-Host "============================================================================" -ForegroundColor Green
Write-Host "  Pro Version Compilation Completed!" -ForegroundColor Green
Write-Host "============================================================================" -ForegroundColor Green
Write-Host ""

Write-Host "Compilation Summary:" -ForegroundColor White
Write-Host "  📂 tradingagents/     → Source code (open source)" -ForegroundColor Cyan
Write-Host "  🔐 core/licensing/    → Cython compiled (.pyd)" -ForegroundColor Green
Write-Host "  📦 core/other/        → Bytecode compiled (.pyc)" -ForegroundColor Green
Write-Host "  📦 app/               → Bytecode compiled (.pyc)" -ForegroundColor Green
Write-Host "  ✨ frontend/dist/     → Vite built (production)" -ForegroundColor Green
Write-Host ""

