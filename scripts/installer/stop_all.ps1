<#
TradingAgents-CN Windows Portable Stopper
Stops MongoDB, Redis, backend, optional Nginx based on runtime\pids.json.
Encoding-safe version: ASCII-only output.
.PARAMETER SkipTray
    When set, do not stop tray monitor (used by restart_all.ps1 so it can continue)
#>

param([switch]$SkipTray)

$ErrorActionPreference = 'Stop'

function Stop-ByPid {
    param([int]$ProcessId, [string]$Name)
    try {
        Write-Host "Stopping $Name (PID $ProcessId) ..."
        Stop-Process -Id $ProcessId -Force -ErrorAction Stop
        Write-Host "$Name stopped"
    } catch {
        Write-Host "Failed to stop $Name by PID; it may have exited already"
    }
}

$scriptDir = Split-Path $PSScriptRoot -Parent
$root = Split-Path $scriptDir -Parent
$pidFile = [System.IO.Path]::Combine($root, 'runtime', 'pids.json')
$monitorPidFile = [System.IO.Path]::Combine($root, 'logs', 'process_monitor.pid')

function Test-IsStartAllProcess {
    param([int]$ProcId, [string]$RootPath)
    if ($ProcId -eq $PID) { return $false }
    try {
        $cmdLine = (Get-WmiObject Win32_Process -Filter "ProcessId = $ProcId" -ErrorAction SilentlyContinue).CommandLine
        if (-not $cmdLine) { return $false }
        if ($cmdLine -like "*restart_all*") { return $false }
        return ($cmdLine -like "*start_all.ps1*" -or $cmdLine -like "*start_all*") -and $cmdLine -like "*$RootPath*"
    } catch { return $false }
}

# Stop start_all.ps1 PowerShell process first (if running)
try {
    $startAllProcs = Get-Process powershell -ErrorAction SilentlyContinue | Where-Object { Test-IsStartAllProcess -ProcId $_.Id -RootPath $root }
    foreach ($proc in $startAllProcs) { Stop-ByPid -ProcessId $proc.Id -Name 'start_all.ps1 PowerShell' }
} catch { }

function Stop-TrayMonitor {
    Get-Process -Name 'pythonw' -ErrorAction SilentlyContinue | ForEach-Object {
        try { $cmdLine = (Get-WmiObject Win32_Process -Filter "ProcessId = $($_.Id)" -ErrorAction SilentlyContinue).CommandLine } catch { $cmdLine = $null }
        if ($cmdLine -and $cmdLine -like "*tray_monitor*" -and $cmdLine -like "*$root*") { Stop-ByPid -ProcessId $_.Id -Name 'Tray Monitor' }
    }
}
# Stop Tray Monitor - skip when called from restart_all
if (-not $SkipTray) { Stop-TrayMonitor }

# Stop Process Monitor daemon
if (Test-Path -LiteralPath $monitorPidFile) {
    try {
        $pidVal = (Get-Content -LiteralPath $monitorPidFile -Raw).Trim()
        if ($pidVal -match '^\d+$') { Stop-ByPid -ProcessId ([int]$pidVal) -Name 'Process Monitor' }
    } catch { Write-Host "Failed to stop Process Monitor from PID file" }
    Remove-Item -LiteralPath $monitorPidFile -Force -ErrorAction SilentlyContinue
}

# Stop main services
if (Test-Path -LiteralPath $pidFile) {
    $content = Get-Content -LiteralPath $pidFile -Raw
    $pids = $null
    try { $pids = $content | ConvertFrom-Json } catch {}
    if ($pids -ne $null) {
        if ($pids.mongodb) { Stop-ByPid -ProcessId ([int]$pids.mongodb) -Name 'MongoDB' }
        if ($pids.redis) { Stop-ByPid -ProcessId ([int]$pids.redis) -Name 'Redis' }
        if ($pids.backend) { Stop-ByPid -ProcessId ([int]$pids.backend) -Name 'Backend' }
        if ($pids.worker) { Stop-ByPid -ProcessId ([int]$pids.worker) -Name 'Worker' }
        if ($pids.nginx) { Stop-ByPid -ProcessId ([int]$pids.nginx) -Name 'Nginx' }
    }
    Remove-Item -LiteralPath $pidFile -Force -ErrorAction SilentlyContinue
    Write-Host "PID file removed"
} else {
    Write-Host "PID file not found; trying to stop by process name"
}

# Stop any remaining Python processes (including multiprocessing child processes)
Write-Host "Stopping any remaining Python processes..."
$pythonProcs = Get-Process -Name 'python' -ErrorAction SilentlyContinue
if ($pythonProcs) {
    foreach ($proc in $pythonProcs) {
        $cmdLine = $null
        try { $cmdLine = (Get-WmiObject Win32_Process -Filter "ProcessId = $($proc.Id)" -ErrorAction SilentlyContinue).CommandLine } catch { }
        $shouldStop = (-not $cmdLine) -or ($cmdLine -like "*$root*")
        if ($shouldStop) {
            try {
                Stop-Process -Id $proc.Id -Force -ErrorAction Stop
                Write-Host "  Stopped Python process (PID: $($proc.Id))"
            } catch { Write-Host "  Failed to stop Python process (PID: $($proc.Id)) - may require admin rights" }
        }
    }
}

# Stop any remaining service processes by name (fallback)
Get-Process -Name 'mongod' -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
Get-Process -Name 'redis-server' -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
Get-Process -Name 'nginx' -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue

Write-Host "All stop operations completed"