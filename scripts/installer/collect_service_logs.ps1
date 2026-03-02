<#
.SYNOPSIS
    Collect MongoDB, Redis, Nginx startup errors and logs
.DESCRIPTION
    When services fail to start, run this script to pack logs, configs and process state
    into logs/diagnostics_YYYYMMDD_HHmmss.zip for troubleshooting.
.PARAMETER OutputDir
    Output directory, default logs
.EXAMPLE
    .\scripts\installer\collect_service_logs.ps1
#>

param(
    [string]$OutputDir = ""
)

$ErrorActionPreference = "Continue"
$root = if ($PSScriptRoot) {
    (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
} else {
    (Get-Location).Path
}

if (-not $OutputDir) {
    $OutputDir = Join-Path $root "logs"
}
$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"

# Load port config from .env
function Load-Env($path) {
    $map = @{}
    if (Test-Path -LiteralPath $path) {
        foreach ($line in Get-Content -LiteralPath $path) {
            if ($line -match '^\s*#' -or $line -match '^\s*$') { continue }
            $idx = $line.IndexOf('=')
            if ($idx -gt 0) {
                $key = $line.Substring(0, $idx).Trim()
                $val = $line.Substring($idx + 1).Trim()
                $map[$key] = $val
            }
        }
    }
    return $map
}
$envMap = Load-Env (Join-Path $root ".env")
$outZip = Join-Path $OutputDir "diagnostics_$timestamp.zip"
$tempDir = Join-Path $env:TEMP "TradingAgentsCN_diag_$timestamp"

Write-Host "============================================================================" -ForegroundColor Cyan
Write-Host "  Collecting service diagnostics" -ForegroundColor Cyan
Write-Host "============================================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Root: $root" -ForegroundColor Gray
Write-Host "  Output: $outZip" -ForegroundColor Gray
Write-Host ""

New-Item -ItemType Directory -Path $tempDir -Force | Out-Null

# 1. Log files
$logFiles = @(
    "logs\nginx_error.log",
    "logs\nginx_access.log",
    "logs\backend_startup.log",
    "logs\backend_error.log",
    "logs\start_all.log",
    "logs\process_monitor.log",
    "logs\tray_monitor.log",
    "logs\restart_all.log",
    "logs\updater.log",
    "logs\mongodb_startup.log",
    "logs\redis_startup.log",
    "runtime\mongodb.log"
)
foreach ($f in $logFiles) {
    $src = Join-Path $root $f
    if (-not (Test-Path $src) -and $f -like "logs\*") {
        $altSrc = Join-Path $PSScriptRoot $f
        if (Test-Path $altSrc) { $src = $altSrc }
    }
    if (Test-Path $src) {
        $dst = Join-Path $tempDir $f
        $dstDir = Split-Path -Parent $dst
        if (-not (Test-Path $dstDir)) { New-Item -ItemType Directory -Path $dstDir -Force | Out-Null }
        Copy-Item -Path $src -Destination $dst -Force -ErrorAction SilentlyContinue
        Write-Host "  [OK] $f" -ForegroundColor Green
    }
}

# 2. Config files (no passwords)
$configFiles = @(
    "runtime\nginx.conf",
    "runtime\redis.conf",
    "runtime\mongodb.conf"
)
foreach ($f in $configFiles) {
    $src = Join-Path $root $f
    if (Test-Path $src) {
        $dst = Join-Path $tempDir $f
        $dstDir = Split-Path -Parent $dst
        if (-not (Test-Path $dstDir)) { New-Item -ItemType Directory -Path $dstDir -Force | Out-Null }
        Copy-Item -Path $src -Destination $dst -Force -ErrorAction SilentlyContinue
        Write-Host "  [OK] $f" -ForegroundColor Green
    }
}

# 3. Process state
$pidsFile = Join-Path $tempDir "runtime\pids.json"
if (Test-Path (Join-Path $root "runtime\pids.json")) {
    $pidsDir = Split-Path -Parent $pidsFile
    if (-not (Test-Path $pidsDir)) { New-Item -ItemType Directory -Path $pidsDir -Force | Out-Null }
    Copy-Item -Path (Join-Path $root "runtime\pids.json") -Destination $pidsFile -Force
    Write-Host "  [OK] runtime\pids.json" -ForegroundColor Green
}

# 4. System summary
$summaryFile = Join-Path $tempDir "system_summary.txt"
$summary = @()
$summary += "=== TradingAgents-CN Diagnostics ==="
$summary += "Collected: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
$summary += ""

# Process state
$summary += "--- Process State ---"
foreach ($procName in @("mongod", "redis-server", "nginx", "python")) {
    $procs = Get-Process -Name $procName -ErrorAction SilentlyContinue
    if ($procs) {
        foreach ($p in $procs) {
            $summary += "  $procName PID=$($p.Id) Mem=$([math]::Round($p.WorkingSet64/1MB, 2))MB"
        }
    } else {
        $summary += "  ${procName}: not running"
    }
}
$summary += ""

# Port listening (from .env or defaults)
$summary += "--- Port Listening ---"
$mongoPort = if ($envMap.ContainsKey('MONGODB_PORT')) { [int]$envMap['MONGODB_PORT'] } else { 27017 }
$redisPort = if ($envMap.ContainsKey('REDIS_PORT')) { [int]$envMap['REDIS_PORT'] } else { 6379 }
$nginxPort = if ($envMap.ContainsKey('NGINX_PORT')) { [int]$envMap['NGINX_PORT'] } else { 80 }
$backendPort = if ($envMap.ContainsKey('PORT')) { [int]$envMap['PORT'] } else { 8000 }
$ports = @($mongoPort, $redisPort, $nginxPort, $backendPort)
foreach ($port in $ports) {
    $conn = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($conn) {
        $proc = Get-Process -Id $conn.OwningProcess -ErrorAction SilentlyContinue
        $summary += "  Port $port : $($proc.ProcessName) (PID $($conn.OwningProcess))"
    } else {
        $summary += "  Port $port : not listening"
    }
}
$summary += ""

# Port config from .env (sanitized)
$envPath = Join-Path $root ".env"
if (Test-Path $envPath) {
    $summary += "--- .env port config (sanitized) ---"
    $envContent = Get-Content $envPath -ErrorAction SilentlyContinue
    foreach ($line in $envContent) {
        if ($line -match '^(PORT|MONGODB_PORT|REDIS_PORT|NGINX_PORT)\s*=') {
            $summary += "  $line"
        }
    }
}
$summary | Out-File -FilePath $summaryFile -Encoding UTF8
Write-Host "  [OK] system_summary.txt" -ForegroundColor Green

# 4.5 Feedback instructions for users
$readmeFile = Join-Path $tempDir "HOW_TO_REPORT_ISSUES.txt"
$readmeContent = @"
================================================================================
TradingAgents-CN Issue Reporting
================================================================================

This diagnostics package contains logs, configs and system status for troubleshooting.

[When reporting issues, please provide]
1. This diagnostics package (diagnostics_*.zip) in full
2. Problem description: startup failure / runtime error / specific symptoms
3. Steps to reproduce: what you did before the issue occurred
4. Environment: Windows version, whether running as administrator

[Feedback channels]
- GitHub Issues: submit an Issue with this package attached
- Or contact support through your software distribution channel

[Notes]
- Package is sanitized, no passwords or sensitive data
- Do not share logs containing personal info in public

Thank you for your feedback!
================================================================================
"@
$readmeContent | Out-File -FilePath $readmeFile -Encoding UTF8
Write-Host "  [OK] HOW_TO_REPORT_ISSUES.txt" -ForegroundColor Green

# 5. Pack
Write-Host ""
Write-Host "  Packing..." -ForegroundColor Yellow
if (Test-Path $outZip) { Remove-Item $outZip -Force }
Compress-Archive -Path "$tempDir\*" -DestinationPath $outZip -CompressionLevel Optimal
Remove-Item -Path $tempDir -Recurse -Force -ErrorAction SilentlyContinue

Write-Host ""
Write-Host "============================================================================" -ForegroundColor Green
Write-Host "  Diagnostics package created" -ForegroundColor Green
Write-Host "============================================================================" -ForegroundColor Green
Write-Host ""
Write-Host "  File: $outZip" -ForegroundColor White
Write-Host "  Size: $([math]::Round((Get-Item $outZip).Length / 1KB, 2)) KB" -ForegroundColor White
Write-Host ""
Write-Host "  Contents: Nginx/Backend logs, MongoDB/Redis configs, process/port summary" -ForegroundColor Cyan
Write-Host "  Provide this file to support for troubleshooting." -ForegroundColor Gray
Write-Host ""
