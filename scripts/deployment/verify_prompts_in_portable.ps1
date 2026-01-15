# ============================================================================
# Verify Prompts in Portable Package
# ============================================================================
# 验证便携版中是否包含 core/prompts/ 目录的所有文件
# ============================================================================

param(
    [string]$PortableDir = "release\TradingAgentsCN-portable"
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$portableDir = Join-Path $root $PortableDir

Write-Host "============================================================================" -ForegroundColor Cyan
Write-Host "  Verify Prompts in Portable Package" -ForegroundColor Cyan
Write-Host "============================================================================" -ForegroundColor Cyan
Write-Host ""

# 检查便携版目录是否存在
if (-not (Test-Path $portableDir)) {
    Write-Host "❌ Portable directory not found: $portableDir" -ForegroundColor Red
    Write-Host ""
    Write-Host "Please run the build script first:" -ForegroundColor Yellow
    Write-Host "  .\scripts\deployment\build_pro_package.ps1" -ForegroundColor White
    exit 1
}

Write-Host "Portable directory: $portableDir" -ForegroundColor Green
Write-Host ""

# 检查 core/prompts/ 目录
$corePromptsDir = Join-Path $portableDir "core\prompts"

if (-not (Test-Path $corePromptsDir)) {
    Write-Host "❌ core/prompts/ directory not found!" -ForegroundColor Red
    exit 1
}

Write-Host "✅ core/prompts/ directory exists" -ForegroundColor Green
Write-Host ""

# 列出所有 .py 文件
Write-Host "Checking Python files in core/prompts/..." -ForegroundColor Yellow
Write-Host ""

$pyFiles = Get-ChildItem -Path $corePromptsDir -Filter "*.py" -Recurse
$pycFiles = Get-ChildItem -Path $corePromptsDir -Filter "*.pyc" -Recurse

Write-Host "Python source files (.py): $($pyFiles.Count)" -ForegroundColor Cyan
foreach ($file in $pyFiles) {
    $relativePath = $file.FullName.Substring($portableDir.Length + 1)
    Write-Host "  ✅ $relativePath" -ForegroundColor Green
}

Write-Host ""
Write-Host "Compiled files (.pyc): $($pycFiles.Count)" -ForegroundColor Cyan
foreach ($file in $pycFiles) {
    $relativePath = $file.FullName.Substring($portableDir.Length + 1)
    Write-Host "  📦 $relativePath" -ForegroundColor Gray
}

Write-Host ""

# 检查关键文件（提示词管理模块，不是具体提示词内容）
$criticalFiles = @(
    "core\prompts\__init__.py",
    "core\prompts\loader.py",
    "core\prompts\manager.py",
    "core\prompts\template.py"
)

$allPresent = $true
Write-Host "Checking critical files..." -ForegroundColor Yellow
Write-Host ""

foreach ($file in $criticalFiles) {
    $fullPath = Join-Path $portableDir $file
    if (Test-Path $fullPath) {
        Write-Host "  ✅ $file" -ForegroundColor Green
    } else {
        Write-Host "  ❌ $file (MISSING!)" -ForegroundColor Red
        $allPresent = $false
    }
}

Write-Host ""
Write-Host "============================================================================" -ForegroundColor Cyan

if ($allPresent -and $pyFiles.Count -gt 0) {
    Write-Host "✅ All prompts files are present!" -ForegroundColor Green
    Write-Host ""
    Write-Host "The portable package is ready for installation." -ForegroundColor White
    exit 0
} else {
    Write-Host "❌ Some prompts files are missing!" -ForegroundColor Red
    Write-Host ""
    Write-Host "Please rebuild the portable package:" -ForegroundColor Yellow
    Write-Host "  1. Clean the portable directory:" -ForegroundColor White
    Write-Host "     Remove-Item -Path '$portableDir' -Recurse -Force" -ForegroundColor Gray
    Write-Host ""
    Write-Host "  2. Rebuild the package:" -ForegroundColor White
    Write-Host "     .\scripts\deployment\build_pro_package.ps1" -ForegroundColor Gray
    exit 1
}

