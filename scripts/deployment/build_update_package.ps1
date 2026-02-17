<#
.SYNOPSIS
    构建 TradingAgents-CN 更新包
.DESCRIPTION
    只打包代码文件（不包含 vendors/data/.env/logs 等），生成轻量更新包（~50-80MB）。
    供自动更新系统使用。
.PARAMETER Version
    版本号。留空则从 VERSION 文件读取。
.PARAMETER OutputDir
    输出目录。默认 release/packages/
.PARAMETER SourceDir
    源代码目录。默认为便携版目录（编译后的代码）。
    如果便携版不存在，使用项目根目录（源码）。
#>

param(
    [string]$Version = "",
    [string]$OutputDir = "",
    [string]$SourceDir = ""
)

$ErrorActionPreference = "Stop"

# 设置编码
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$PSDefaultParameterValues['*:Encoding'] = 'utf8'

$root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)

Write-Host "============================================================================" -ForegroundColor Cyan
Write-Host "  Build TradingAgents-CN Update Package" -ForegroundColor Cyan
Write-Host "============================================================================" -ForegroundColor Cyan
Write-Host ""

# ── 1. 确定版本号 ────────────────────────────────────────
if (-not $Version) {
    $versionFile = Join-Path $root "VERSION"
    if (Test-Path $versionFile) {
        $Version = (Get-Content $versionFile -Raw).Trim()
    } else {
        Write-Host "ERROR: VERSION file not found and -Version not specified" -ForegroundColor Red
        exit 1
    }
}
Write-Host "  Version: $Version" -ForegroundColor Cyan

# ── 2. 确定源目录 ────────────────────────────────────────
if (-not $SourceDir) {
    # 优先使用便携版目录（已编译）
    $portableDir = Join-Path $root "release\TradingAgentsCN-portable"
    if (Test-Path $portableDir) {
        $SourceDir = $portableDir
        Write-Host "  Source: Portable directory (compiled)" -ForegroundColor Cyan
    } else {
        $SourceDir = $root
        Write-Host "  Source: Project root (source code)" -ForegroundColor Yellow
    }
} else {
    Write-Host "  Source: $SourceDir" -ForegroundColor Cyan
}

# ── 3. 确定输出目录 ──────────────────────────────────────
if (-not $OutputDir) {
    $OutputDir = Join-Path $root "release\packages"
}
if (-not (Test-Path $OutputDir)) {
    New-Item -ItemType Directory -Path $OutputDir -Force | Out-Null
}
Write-Host "  Output: $OutputDir" -ForegroundColor Cyan
Write-Host ""

# ── 4. 需要打包的目录/文件 ───────────────────────────────
$includeItems = @(
    "app",
    "core",
    "frontend",
    "scripts",
    "tradingagents",
    "prompts",
    "migrations",
    "VERSION",
    "BUILD_INFO"
)

# 对于 frontend，只打包 dist 目录（构建产物）
# 如果源目录有 frontend/dist，打包 frontend/dist
# 如果没有，打包整个 frontend（用户需要自己构建）

# ── 5. 创建临时目录 ──────────────────────────────────────
$timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$tempDir = Join-Path $env:TEMP "update-package-$timestamp"
New-Item -ItemType Directory -Path $tempDir -Force | Out-Null

Write-Host "[1/3] Collecting files..." -ForegroundColor Yellow

$copiedCount = 0
foreach ($item in $includeItems) {
    $src = Join-Path $SourceDir $item
    if (Test-Path $src) {
        $dst = Join-Path $tempDir $item
        if ((Get-Item $src).PSIsContainer) {
            # 目录：递归复制
            Copy-Item -Path $src -Destination $dst -Recurse -Force
            $fileCount = (Get-ChildItem -Path $dst -Recurse -File).Count
            Write-Host "    ✅ $item ($fileCount files)" -ForegroundColor Green
        } else {
            # 文件：直接复制
            Copy-Item -Path $src -Destination $dst -Force
            Write-Host "    ✅ $item" -ForegroundColor Green
        }
        $copiedCount++
    } else {
        Write-Host "    ⚠️ $item (not found, skipped)" -ForegroundColor Yellow
    }
}

# 特殊处理 frontend：如果复制了整个 frontend，移除 node_modules
$frontendNodeModules = Join-Path $tempDir "frontend\node_modules"
if (Test-Path $frontendNodeModules) {
    Remove-Item -Path $frontendNodeModules -Recurse -Force
    Write-Host "    🗑️ Removed frontend/node_modules" -ForegroundColor Gray
}

# 移除 __pycache__ 目录
Get-ChildItem -Path $tempDir -Directory -Recurse -Filter "__pycache__" | ForEach-Object {
    Remove-Item -Path $_.FullName -Recurse -Force
}
Write-Host "    🗑️ Cleaned __pycache__ directories" -ForegroundColor Gray
Write-Host ""
Write-Host "  Collected $copiedCount items" -ForegroundColor Green
Write-Host ""

# ── 6. 打包为 zip ────────────────────────────────────────
Write-Host "[2/3] Creating update package..." -ForegroundColor Yellow

$packageName = "update-$Version.zip"
$packagePath = Join-Path $OutputDir $packageName

if (Test-Path $packagePath) { Remove-Item $packagePath -Force }

Compress-Archive -Path "$tempDir\*" -DestinationPath $packagePath -CompressionLevel Optimal
$packageSize = (Get-Item $packagePath).Length
$packageSizeMB = [math]::Round($packageSize / 1MB, 2)
Write-Host "    ✅ Package: $packageName ($packageSizeMB MB)" -ForegroundColor Green
Write-Host ""

# ── 7. 生成 SHA256 校验和 ────────────────────────────────
Write-Host "[3/3] Generating SHA256 checksum..." -ForegroundColor Yellow

$hash = (Get-FileHash -Path $packagePath -Algorithm SHA256).Hash.ToLower()
$checksumFile = Join-Path $OutputDir "update-$Version.sha256"
Set-Content -Path $checksumFile -Value "$hash  $packageName" -NoNewline
Write-Host "    ✅ SHA256: $hash" -ForegroundColor Green
Write-Host ""

# ── 8. 清理临时目录 ──────────────────────────────────────
Remove-Item -Path $tempDir -Recurse -Force

# ── 完成 ─────────────────────────────────────────────────
Write-Host "============================================================================" -ForegroundColor Cyan
Write-Host "  Update Package Built Successfully!" -ForegroundColor Green
Write-Host "============================================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Package: $packagePath" -ForegroundColor White
Write-Host "  Size:    $packageSizeMB MB" -ForegroundColor White
Write-Host "  SHA256:  $hash" -ForegroundColor White
Write-Host ""
Write-Host "  Upload this package to the update server:" -ForegroundColor Yellow
Write-Host "    https://www.tradingagentscn.com/downloads/$packageName" -ForegroundColor Gray
Write-Host ""

