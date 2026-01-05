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

Write-Host "[2/3] Compiling app/ directory..." -ForegroundColor Yellow
Write-Host ""

$appDir = Join-Path $PortableDir "app"
if (Test-Path $appDir) {
    Write-Host "  Compiling app/ to bytecode..." -ForegroundColor Gray
    
    & python -OO -m compileall -b $appDir
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  Removing source files..." -ForegroundColor Gray
        Get-ChildItem -Path $appDir -Filter "*.py" -Recurse | ForEach-Object {
            # 保留 __init__.py 和 __main__.py
            if ($_.Name -notin @("__init__.py", "__main__.py")) {
                Remove-Item $_.FullName -Force
                Write-Host "    Removed: $($_.Name)" -ForegroundColor DarkGray
            }
        }
        Write-Host "  ✅ App compilation completed" -ForegroundColor Green
    } else {
        Write-Host "  ⚠️  App compilation failed, keeping source files" -ForegroundColor Yellow
    }
} else {
    Write-Host "  ⚠️  app/ directory not found, skipping" -ForegroundColor Yellow
}

Write-Host ""

# ============================================================================
# Step 3: 验证 tradingagents/ 保持源码
# ============================================================================

Write-Host "[3/3] Verifying tradingagents/ source code..." -ForegroundColor Yellow
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

