# ============================================================================
# Clean Compiled Files in Portable Directory
# ============================================================================
# 清理便携版目录中的所有编译文件，确保下次打包使用最新源码
#
# 使用方法：
#   .\scripts\deployment\clean_portable_compiled.ps1
#   .\scripts\deployment\clean_portable_compiled.ps1 -Verbose
# ============================================================================

param(
    [string]$PortableDir = "",
    [switch]$Verbose = $false
)

# 设置控制台和文件编码为UTF-8
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
[Console]::InputEncoding = [System.Text.Encoding]::UTF8
$PSDefaultParameterValues['*:Encoding'] = 'utf8'
$OutputEncoding = [System.Text.Encoding]::UTF8

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)

if (-not $PortableDir) {
    $PortableDir = Join-Path $root "release\TradingAgentsCN-portable"
}

Write-Host "============================================================================" -ForegroundColor Cyan
Write-Host "  Clean Compiled Files in Portable Directory" -ForegroundColor Cyan
Write-Host "============================================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Portable Directory: $PortableDir" -ForegroundColor Green
Write-Host ""

if (-not (Test-Path $PortableDir)) {
    Write-Host "⚠️  Portable directory not found: $PortableDir" -ForegroundColor Yellow
    Write-Host "Nothing to clean." -ForegroundColor Gray
    exit 0
}

# ============================================================================
# 定义要清理的目录
# ============================================================================

$cleanDirs = @(
    "core",
    "app",
    "tradingagents"
)

Write-Host "Directories to clean:" -ForegroundColor Yellow
foreach ($dir in $cleanDirs) {
    Write-Host "  - $dir" -ForegroundColor Gray
}
Write-Host ""

# ============================================================================
# 开始清理
# ============================================================================

$totalCleaned = 0
$stats = @{
    "__pycache__" = 0
    ".pyc" = 0
    ".pyd" = 0
    ".pyo" = 0
}

foreach ($dir in $cleanDirs) {
    $targetDir = Join-Path $PortableDir $dir
    
    if (-not (Test-Path $targetDir)) {
        Write-Host "[$dir] Directory not found, skipping..." -ForegroundColor Gray
        continue
    }
    
    Write-Host "[$dir] Cleaning..." -ForegroundColor Cyan
    $dirCleaned = 0
    
    # 1. 删除所有 __pycache__ 目录
    Write-Host "  Searching for __pycache__ directories..." -ForegroundColor Gray
    $cacheDirs = Get-ChildItem -Path $targetDir -Recurse -Directory -Filter "__pycache__" -ErrorAction SilentlyContinue
    if ($cacheDirs) {
        foreach ($cacheDir in $cacheDirs) {
            if ($Verbose) {
                Write-Host "    Removing: $($cacheDir.FullName.Substring($PortableDir.Length + 1))" -ForegroundColor DarkGray
            }
            Remove-Item -Path $cacheDir.FullName -Recurse -Force -ErrorAction SilentlyContinue
            $stats["__pycache__"]++
            $dirCleaned++
        }
        Write-Host "    ✅ Removed $($cacheDirs.Count) __pycache__ directories" -ForegroundColor Green
    } else {
        Write-Host "    ℹ️  No __pycache__ directories found" -ForegroundColor DarkGray
    }
    
    # 2. 删除所有 .pyc 文件
    Write-Host "  Searching for .pyc files..." -ForegroundColor Gray
    $pycFiles = Get-ChildItem -Path $targetDir -Recurse -Filter "*.pyc" -ErrorAction SilentlyContinue
    if ($pycFiles) {
        foreach ($pycFile in $pycFiles) {
            if ($Verbose) {
                Write-Host "    Removing: $($pycFile.FullName.Substring($PortableDir.Length + 1))" -ForegroundColor DarkGray
            }
            Remove-Item -Path $pycFile.FullName -Force -ErrorAction SilentlyContinue
            $stats[".pyc"]++
            $dirCleaned++
        }
        Write-Host "    ✅ Removed $($pycFiles.Count) .pyc files" -ForegroundColor Green
    } else {
        Write-Host "    ℹ️  No .pyc files found" -ForegroundColor DarkGray
    }
    
    # 3. 删除所有 .pyd 文件（Cython编译的扩展）
    Write-Host "  Searching for .pyd files..." -ForegroundColor Gray
    $pydFiles = Get-ChildItem -Path $targetDir -Recurse -Filter "*.pyd" -ErrorAction SilentlyContinue
    if ($pydFiles) {
        foreach ($pydFile in $pydFiles) {
            if ($Verbose) {
                Write-Host "    Removing: $($pydFile.FullName.Substring($PortableDir.Length + 1))" -ForegroundColor DarkGray
            }
            Remove-Item -Path $pydFile.FullName -Force -ErrorAction SilentlyContinue
            $stats[".pyd"]++
            $dirCleaned++
        }
        Write-Host "    ✅ Removed $($pydFiles.Count) .pyd files" -ForegroundColor Green
    } else {
        Write-Host "    ℹ️  No .pyd files found" -ForegroundColor DarkGray
    }
    
    # 4. 删除所有 .pyo 文件
    Write-Host "  Searching for .pyo files..." -ForegroundColor Gray
    $pyoFiles = Get-ChildItem -Path $targetDir -Recurse -Filter "*.pyo" -ErrorAction SilentlyContinue
    if ($pyoFiles) {
        foreach ($pyoFile in $pyoFiles) {
            if ($Verbose) {
                Write-Host "    Removing: $($pyoFile.FullName.Substring($PortableDir.Length + 1))" -ForegroundColor DarkGray
            }
            Remove-Item -Path $pyoFile.FullName -Force -ErrorAction SilentlyContinue
            $stats[".pyo"]++
            $dirCleaned++
        }
        Write-Host "    ✅ Removed $($pyoFiles.Count) .pyo files" -ForegroundColor Green
    } else {
        Write-Host "    ℹ️  No .pyo files found" -ForegroundColor DarkGray
    }
    
    $totalCleaned += $dirCleaned
    Write-Host "  [$dir] Total cleaned: $dirCleaned items" -ForegroundColor Cyan
    Write-Host ""
}

# ============================================================================
# 总结
# ============================================================================

Write-Host "============================================================================" -ForegroundColor Cyan
Write-Host "  Cleaning Summary" -ForegroundColor Cyan
Write-Host "============================================================================" -ForegroundColor Cyan
Write-Host ""

Write-Host "Cleaned items by type:" -ForegroundColor Yellow
Write-Host "  __pycache__ directories: $($stats['__pycache__'])" -ForegroundColor White
Write-Host "  .pyc files:              $($stats['.pyc'])" -ForegroundColor White
Write-Host "  .pyd files:              $($stats['.pyd'])" -ForegroundColor White
Write-Host "  .pyo files:              $($stats['.pyo'])" -ForegroundColor White
Write-Host ""
Write-Host "Total items cleaned: $totalCleaned" -ForegroundColor Cyan
Write-Host ""

if ($totalCleaned -gt 0) {
    Write-Host "✅ Cleaning completed successfully!" -ForegroundColor Green
    Write-Host "Next build will use fresh source code." -ForegroundColor Gray
} else {
    Write-Host "ℹ️  No compiled files found (already clean or first build)" -ForegroundColor Cyan
}

Write-Host ""

