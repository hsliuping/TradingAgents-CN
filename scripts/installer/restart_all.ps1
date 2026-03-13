<#
.SYNOPSIS
    Stop all services then start them (for tray restart menu)
.DESCRIPTION
    Runs stop_all.ps1 then start_all.ps1. Logs to logs/restart_all.log for debugging.
#>

$ErrorActionPreference = "Continue"
$root = $PSScriptRoot
if (-not (Test-Path (Join-Path $root '.env'))) {
    $root = (Resolve-Path (Join-Path $PSScriptRoot "..\..") -ErrorAction SilentlyContinue).Path
}

$logsDir = Join-Path $root "logs"
if (-not (Test-Path $logsDir)) { New-Item -ItemType Directory -Path $logsDir -Force | Out-Null }
$logFile = Join-Path $logsDir "restart_all.log"

function Write-RestartLog {
    param([string]$Msg, [string]$Level = "INFO")
    $ts = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $line = "[$ts] [$Level] $Msg"
    Add-Content -Path $logFile -Value $line -Encoding UTF8 -ErrorAction SilentlyContinue
    Write-Host $Msg
}

Write-RestartLog "=== restart_all.ps1 started ==="
Write-RestartLog "root=$root"
Write-RestartLog "PSScriptRoot=$PSScriptRoot"

$stopScript = Join-Path $root "scripts\installer\stop_all.ps1"
if (-not (Test-Path $stopScript)) { $stopScript = Join-Path $root "stop_all.ps1" }
$startScript = Join-Path $root "start_all.ps1"
if (-not (Test-Path $startScript)) { $startScript = Join-Path $root "scripts\installer\start_all.ps1" }

Write-RestartLog "stopScript=$stopScript exists=$(Test-Path $stopScript)"
Write-RestartLog "startScript=$startScript exists=$(Test-Path $startScript)"

if (-not (Test-Path $stopScript) -or -not (Test-Path $startScript)) {
    Write-RestartLog "ERROR: stop_all.ps1 or start_all.ps1 not found" "ERROR"
    exit 1
}

Write-RestartLog "Step 1: Running stop_all -SkipTray (same process to avoid being killed)..."
Set-Location $root
try {
    & $stopScript -SkipTray 2>&1 | ForEach-Object { Write-RestartLog "  stop: $_" }
    Write-RestartLog "Step 1 done"
} catch {
    Write-RestartLog "Step 1 exception: $_" "ERROR"
}

Write-RestartLog "Step 2: Closing old start_all window..."
try {
    $startAllProcs = Get-Process powershell -ErrorAction SilentlyContinue | Where-Object {
        $_.Id -ne $PID -and (try {
            $cmdLine = (Get-WmiObject Win32_Process -Filter "ProcessId = $($_.Id)" -ErrorAction SilentlyContinue).CommandLine
            $cmdLine -and $cmdLine -like "*start_all*" -and $cmdLine -notlike "*restart_all*" -and $cmdLine -like "*$root*"
        } catch { $false })
    }
    foreach ($p in $startAllProcs) {
        Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue
        Write-RestartLog "  Closed PID $($p.Id)"
    }
} catch { Write-RestartLog "  $($_.Exception.Message)" "WARN" }

Write-RestartLog "Step 3: Sleeping 2 seconds..."
Start-Sleep -Seconds 2

Write-RestartLog "Step 4: Launching start_all -SkipTray..."
$startArgs = "-ExecutionPolicy Bypass -NoExit -File `"$startScript`" -SkipTray"
Write-RestartLog "  Start-Process powershell -ArgumentList $startArgs -WorkingDirectory $root"
try {
    $proc = Start-Process -FilePath "powershell" -ArgumentList $startArgs -WorkingDirectory $root -WindowStyle Normal -PassThru
    Write-RestartLog "Step 4 done, start_all PID=$($proc.Id)"
} catch {
    Write-RestartLog "Step 4 exception: $_" "ERROR"
    Write-RestartLog $_.ScriptStackTrace "ERROR"
}

Write-RestartLog "=== restart_all.ps1 finished ==="
