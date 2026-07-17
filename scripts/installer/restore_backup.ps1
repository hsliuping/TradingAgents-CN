# 升级安装时恢复用户配置和数据
# 用法: powershell -File restore_backup.ps1 -InstallDir "C:\TradingAgentsCN"
param(
    [Parameter(Mandatory=$true)]
    [string]$InstallDir
)

$ErrorActionPreference = "Continue"

$backupRoot = Join-Path $InstallDir "backup"
if (-not (Test-Path $backupRoot)) {
    Write-Host "No backup directory found, skipping restore"
    exit 0
}

# Find the latest pre_install_* backup
$latest = Get-ChildItem -Path $backupRoot -Directory -Filter "pre_install_*" -ErrorAction SilentlyContinue |
    Sort-Object CreationTime -Descending |
    Select-Object -First 1

if (-not $latest) {
    Write-Host "No pre_install backup found, skipping restore"
    exit 0
}

Write-Host "Restoring from backup: $($latest.Name)"

# Restore .env FIRST (most critical - contains port settings)
$envSrc = Join-Path $latest.FullName ".env"
$envDst = Join-Path $InstallDir ".env"
if (Test-Path $envSrc) {
    Copy-Item -Path $envSrc -Destination $envDst -Force
    Write-Host "  Restored: .env"
} else {
    Write-Host "  WARNING: .env not found in backup"
}

# Restore runtime (nginx.conf, redis.conf, mongodb.conf with port settings)
$runtimeSrc = Join-Path $latest.FullName "runtime"
$runtimeDst = Join-Path $InstallDir "runtime"
if (Test-Path $runtimeSrc) {
    if (Test-Path $runtimeDst) {
        Remove-Item -Path $runtimeDst -Recurse -Force -ErrorAction SilentlyContinue
    }
    Copy-Item -Path $runtimeSrc -Destination $runtimeDst -Recurse -Force
    Write-Host "  Restored: runtime"
}

# Restore data (MongoDB, Redis data)
$dataSrc = Join-Path $latest.FullName "data"
$dataDst = Join-Path $InstallDir "data"
if (Test-Path $dataSrc) {
    if (Test-Path $dataDst) {
        Remove-Item -Path $dataDst -Recurse -Force -ErrorAction SilentlyContinue
    }
    Copy-Item -Path $dataSrc -Destination $dataDst -Recurse -Force -ErrorAction SilentlyContinue
    Write-Host "  Restored: data"
}

# Restore logs (optional, don't fail if copy fails)
$logsSrc = Join-Path $latest.FullName "logs"
$logsDst = Join-Path $InstallDir "logs"
if (Test-Path $logsSrc) {
    if (-not (Test-Path $logsDst)) {
        New-Item -ItemType Directory -Path $logsDst -Force | Out-Null
    }
    Copy-Item -Path "$logsSrc\*" -Destination $logsDst -Recurse -Force -ErrorAction SilentlyContinue
    Write-Host "  Restored: logs"
}

Write-Host "Restore completed from $($latest.Name)"
