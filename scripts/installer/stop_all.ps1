<#
TradingAgents-CN Windows Portable Stopper
Stops MongoDB, Redis, backend, optional Nginx based on runtime\pids.json.
Encoding-safe version: ASCII-only output.
#>

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

$root = (Get-Location).Path
$pidFile = Join-Path $root 'runtime\pids.json'
$monitorPidFile = Join-Path $root 'logs\process_monitor.pid'

# Stop start_all.ps1 PowerShell process first (if running)
try {
    $startAllProcs = Get-Process powershell -ErrorAction SilentlyContinue | Where-Object {
        try {
            $cmdLine = (Get-WmiObject Win32_Process -Filter "ProcessId = $($_.Id)" -ErrorAction SilentlyContinue).CommandLine
            $cmdLine -and $cmdLine -like "*start_all.ps1*"
        } catch {
            $false
        }
    }

    foreach ($proc in $startAllProcs) {
        Stop-ByPid -ProcessId $proc.Id -Name 'start_all.ps1 PowerShell'
    }
} catch {
    # Ignore errors
}

# Stop Process Monitor daemon
if (Test-Path -LiteralPath $monitorPidFile) {
    try {
        $monitorPid = Get-Content -LiteralPath $monitorPidFile -Raw
        $monitorPid = $monitorPid.Trim()
        if ($monitorPid -match '^\d+$') {
            Stop-ByPid -ProcessId ([int]$monitorPid) -Name 'Process Monitor'
        }
    } catch {
        Write-Host "Failed to stop Process Monitor from PID file"
    }
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
        try {
            # Try to get command line to check if it's from this installation
            $cmdLine = $null
            try {
                $cmdLine = (Get-WmiObject Win32_Process -Filter "ProcessId = $($proc.Id)" -ErrorAction SilentlyContinue).CommandLine
            } catch {
                # WMI query failed, assume it's from this installation
            }

            # Stop if: 1) command line matches installation path, or 2) can't get command line (likely orphan)
            if ((-not $cmdLine) -or ($cmdLine -like "*$root*")) {
                try {
                    Stop-Process -Id $proc.Id -Force -ErrorAction Stop
                    Write-Host "  Stopped Python process (PID: $($proc.Id))"
                } catch {
                    Write-Host "  Failed to stop Python process (PID: $($proc.Id)) - may require admin rights"
                }
            }
        } catch {
            # Ignore errors
        }
    }
}

# Stop any remaining service processes by name (fallback)
Get-Process -Name 'mongod' -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
Get-Process -Name 'redis-server' -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
Get-Process -Name 'nginx' -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue

Write-Host "All stop operations completed"