# ============================================================================
# Clean Python Cache Files
# ============================================================================
# 清理 Python 字节码缓存文件（__pycache__ 和 .pyc 文件）
# 用于确保程序使用最新的源代码，而不是旧的缓存
# ============================================================================

param(
    [string]$TargetDir = "",
    [switch]$Verbose = $false
)

$ErrorActionPreference = "Stop"

# 如果没有指定目标目录，使用脚本所在目录的父目录
if ([string]::IsNullOrEmpty($TargetDir)) {
    $TargetDir = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
}

Write-Host "============================================================================" -ForegroundColor Cyan
Write-Host "  Clean Python Cache Files" -ForegroundColor Cyan
Write-Host "============================================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Target directory: $TargetDir" -ForegroundColor Green
Write-Host ""

if (-not (Test-Path $TargetDir)) {
    Write-Host "❌ Error: Target directory not found: $TargetDir" -ForegroundColor Red
    exit 1
}

$cleanedCacheDirs = 0
$cleanedPycFiles = 0
$cleanedPyoFiles = 0

# 清理 __pycache__ 目录
Write-Host "Cleaning __pycache__ directories..." -ForegroundColor Yellow
$cacheDirs = Get-ChildItem -Path $TargetDir -Recurse -Directory -Filter "__pycache__" -ErrorAction SilentlyContinue
if ($cacheDirs) {
    $cleanedCacheDirs = ($cacheDirs | Measure-Object).Count
    foreach ($dir in $cacheDirs) {
        if ($Verbose) {
            Write-Host "  🗑️  Removing: $($dir.FullName)" -ForegroundColor Gray
        }
        Remove-Item -Path $dir.FullName -Recurse -Force -ErrorAction SilentlyContinue
    }
    Write-Host "  ✅ Cleaned $cleanedCacheDirs __pycache__ directories" -ForegroundColor Green
} else {
    Write-Host "  ✅ No __pycache__ directories found" -ForegroundColor Green
}

# 🔥 清理 .pyc 文件（只清理源文件的缓存，保留编译后的字节码）
Write-Host "Cleaning source cache .pyc files (preserving compiled bytecode)..." -ForegroundColor Yellow
Write-Host "  (保留 core/other/ 和 app/ 目录中的编译后字节码)" -ForegroundColor DarkGray

$pycFiles = Get-ChildItem -Path $TargetDir -Recurse -Filter "*.pyc" -ErrorAction SilentlyContinue | Where-Object {
    $fullPath = $_.FullName
    # 排除编译后的字节码目录
    $fullPath -notlike "*\core\other\*" -and
    $fullPath -notlike "*\app\*"
}
if ($pycFiles) {
    $cleanedPycFiles = ($pycFiles | Measure-Object).Count
    foreach ($file in $pycFiles) {
        if ($Verbose) {
            Write-Host "  🗑️  Removing: $($file.FullName)" -ForegroundColor Gray
        }
        Remove-Item -Path $file.FullName -Force -ErrorAction SilentlyContinue
    }
    Write-Host "  ✅ Cleaned $cleanedPycFiles source cache .pyc files" -ForegroundColor Green
    Write-Host "    ✅ Preserved compiled bytecode in core/other/ and app/" -ForegroundColor DarkGray
} else {
    Write-Host "  ✅ No source cache .pyc files found" -ForegroundColor Green
}

# 清理 .pyo 文件
Write-Host "Cleaning .pyo files..." -ForegroundColor Yellow
$pyoFiles = Get-ChildItem -Path $TargetDir -Recurse -Filter "*.pyo" -ErrorAction SilentlyContinue
if ($pyoFiles) {
    $cleanedPyoFiles = ($pyoFiles | Measure-Object).Count
    foreach ($file in $pyoFiles) {
        if ($Verbose) {
            Write-Host "  🗑️  Removing: $($file.FullName)" -ForegroundColor Gray
        }
        Remove-Item -Path $file.FullName -Force -ErrorAction SilentlyContinue
    }
    Write-Host "  ✅ Cleaned $cleanedPyoFiles .pyo files" -ForegroundColor Green
} else {
    Write-Host "  ✅ No .pyo files found" -ForegroundColor Green
}

Write-Host ""
Write-Host "============================================================================" -ForegroundColor Green
Write-Host "  Cleanup Completed!" -ForegroundColor Green
Write-Host "============================================================================" -ForegroundColor Green
Write-Host ""
Write-Host "Summary:" -ForegroundColor Cyan
Write-Host "  - __pycache__ directories: $cleanedCacheDirs" -ForegroundColor White
Write-Host "  - .pyc files: $cleanedPycFiles" -ForegroundColor White
Write-Host "  - .pyo files: $cleanedPyoFiles" -ForegroundColor White
Write-Host ""

if ($cleanedCacheDirs -gt 0 -or $cleanedPycFiles -gt 0 -or $cleanedPyoFiles -gt 0) {
    Write-Host "✅ Cache files cleaned successfully!" -ForegroundColor Green
    Write-Host "💡 The program will now use the latest source code." -ForegroundColor Cyan
} else {
    Write-Host "✅ No cache files found (already clean)" -ForegroundColor Green
}

Write-Host ""
