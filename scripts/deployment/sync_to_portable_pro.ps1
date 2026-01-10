# ============================================================================
# Sync Code to Portable Release (Pro Version)
# ============================================================================
# 专业版打包脚本 - 排除课程源码和敏感内容
# ============================================================================

param(
    [switch]$SkipDependencies,
    [switch]$DryRun,
    [switch]$Force
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
Write-Host "  Sync Code to Portable Release (Pro Version)" -ForegroundColor Cyan
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
    "core",          # 🔥 v2.0 核心代码（必须同步！）
    "app",
    "tradingagents",
    "web",
    "tests",
    "examples",
    "prompts",
    "config",
    "install"  # 🔥 包含数据库配置文件
)

# 🔥 注意：docs 目录不再完整同步，改为选择性同步

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

# 🔥 新增：排除课程源码和敏感内容
$excludeDirs = @(
    "docs\courses\advanced\expanded",  # 排除24节课程扩写内容
    "docs\courses\advanced\ppt",       # 排除PPT源文件
    "docs\design",                     # 排除设计文档
    "docs\email-to-tradingagents-team.txt"  # 排除邮件模板
)

$portableSpecific = @(
    ".env",
    "data",
    "logs",
    "temp",
    "runtime",
    "vendors",
    # "venv",  # 排除 venv，使用嵌入式 Python
    "frontend",
    "scripts\import_config_and_create_user.py",
    "scripts\init_mongodb_user.py",
    "start_all.ps1",
    "start_services_clean.ps1",
    "stop_all.ps1",
    "README_STARTUP.txt"
)

# 排除大文件和数据目录（安装时创建）
$excludeDataDirs = @(
    "data\mongodb",
    "data\redis",
    "logs",
    "temp"
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
    
    # 🔥 检查是否在排除目录中
    foreach ($excludeDir in $excludeDirs) {
        $normalized = $excludeDir -replace '\\', '/'
        $pathNormalized = $Path -replace '\\', '/'
        if ($pathNormalized -like "*$normalized*") {
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

Write-Host "Syncing directories..." -ForegroundColor Yellow
Write-Host ""

foreach ($dir in $syncDirs) {
    $sourcePath = Join-Path $root $dir
    $destPath = Join-Path $portableDir $dir

    if (-not (Test-Path $sourcePath)) {
        Write-Host "  SKIP: $dir (not found)" -ForegroundColor Yellow
        continue
    }

    Write-Host "Processing: $dir" -ForegroundColor Cyan

    Get-ChildItem -Path $sourcePath -Recurse -File | ForEach-Object {
        $relativePath = $_.FullName.Substring($root.Length + 1)

        if (Test-ShouldExclude $_.FullName) {
            $skipCount++
            return
        }

        if (Test-IsPortableSpecific $relativePath) {
            $skipCount++
            return
        }

        $destFile = Join-Path $portableDir $relativePath
        Copy-WithProgress -Source $_.FullName -Destination $destFile -Description $relativePath
        $syncCount++
    }

    Write-Host ""
}

# ============================================================================
# Sync individual files
# ============================================================================

Write-Host "Syncing individual files..." -ForegroundColor Yellow
Write-Host ""

foreach ($file in $syncFiles) {
    $sourcePath = Join-Path $root $file
    $destPath = Join-Path $portableDir $file

    if (Test-Path $sourcePath) {
        Copy-WithProgress -Source $sourcePath -Destination $destPath -Description $file
        $syncCount++
    } else {
        Write-Host "  SKIP: $file (not found)" -ForegroundColor Yellow
    }
}

Write-Host ""

# ============================================================================
# 🔥 选择性同步 docs 目录（排除课程源码）
# ============================================================================

Write-Host "Syncing docs (excluding course source)..." -ForegroundColor Yellow
Write-Host ""

$docsSource = Join-Path $root "docs"
$docsDest = Join-Path $portableDir "docs"

if (Test-Path $docsSource) {
    # 只同步基础文档，排除课程扩写内容
    Get-ChildItem -Path $docsSource -Recurse -File | ForEach-Object {
        $relativePath = $_.FullName.Substring($root.Length + 1)

        if (Test-ShouldExclude $_.FullName) {
            $skipCount++
            return
        }

        $destFile = Join-Path $portableDir $relativePath
        Copy-WithProgress -Source $_.FullName -Destination $destFile -Description $relativePath
        $syncCount++
    }
}

Write-Host ""

# ============================================================================
# Summary
# ============================================================================

Write-Host "============================================================================" -ForegroundColor Green
Write-Host "  Sync Completed!" -ForegroundColor Green
Write-Host "============================================================================" -ForegroundColor Green
Write-Host ""
Write-Host "Files synced: $syncCount" -ForegroundColor Cyan
Write-Host "Files skipped: $skipCount" -ForegroundColor Yellow
Write-Host ""
Write-Host "Excluded content:" -ForegroundColor White
Write-Host "  - docs/courses/advanced/expanded/ (24节课程源码)" -ForegroundColor Gray
Write-Host "  - docs/courses/advanced/ppt/ (PPT源文件)" -ForegroundColor Gray
Write-Host "  - docs/design/ (设计文档)" -ForegroundColor Gray
Write-Host ""
Write-Host "Next: Run build_portable_package.ps1 to package" -ForegroundColor Cyan
Write-Host ""

