# Copy updated scripts to installed directory for quick update without reinstall
# Usage: .\copy_tray_fix_to_install.ps1 [-InstallDir "D:\TradingAgentsCN"]

param(
    [string]$InstallDir = ""
)

$ErrorActionPreference = "Stop"

# Project root (two levels up from script)
$scriptDir = Split-Path -Parent $PSScriptRoot
$root = Split-Path -Parent $scriptDir

if ([string]::IsNullOrWhiteSpace($InstallDir)) {
    Write-Host "Usage: .\copy_tray_fix_to_install.ps1 -InstallDir `"<install_dir>`"" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Example:" -ForegroundColor Cyan
    Write-Host "  .\copy_tray_fix_to_install.ps1 -InstallDir `"D:\TradingAgentsCNccc`"" -ForegroundColor Gray
    Write-Host ""
    $InstallDir = Read-Host "Enter install directory path"
    if ([string]::IsNullOrWhiteSpace($InstallDir)) {
        Write-Host "Install directory not specified, exiting." -ForegroundColor Red
        exit 1
    }
}

$InstallDir = $InstallDir.Trim('"')
if (-not (Test-Path $InstallDir)) {
    Write-Host "Error: Install directory not found: $InstallDir" -ForegroundColor Red
    exit 1
}

# Scripts to copy (aligned with sync_to_portable_pro)
$filesToCopy = @(
    # installer scripts
    @{ Source = "scripts\installer\start_all.ps1"; Dest = "start_all.ps1"; Desc = "start_all.ps1 (root)" },
    @{ Source = "scripts\installer\start_all.ps1"; Dest = "scripts\installer\start_all.ps1"; Desc = "start_all.ps1 (installer)" },
    @{ Source = "scripts\installer\stop_all.ps1"; Dest = "stop_all.ps1"; Desc = "stop_all.ps1 (root)" },
    @{ Source = "scripts\installer\stop_all.ps1"; Dest = "scripts\installer\stop_all.ps1"; Desc = "stop_all.ps1 (installer)" },
    @{ Source = "scripts\installer\start_services_clean.ps1"; Dest = "start_services_clean.ps1"; Desc = "start_services_clean.ps1 (root)" },
    @{ Source = "scripts\installer\start_services_clean.ps1"; Dest = "scripts\installer\start_services_clean.ps1"; Desc = "start_services_clean.ps1 (installer)" },
    @{ Source = "scripts\installer\collect_service_logs.ps1"; Dest = "scripts\installer\collect_service_logs.ps1"; Desc = "collect_service_logs.ps1" },
    @{ Source = "scripts\installer\restart_all.ps1"; Dest = "restart_all.ps1"; Desc = "restart_all.ps1 (root)" },
    @{ Source = "scripts\installer\restart_all.ps1"; Dest = "scripts\installer\restart_all.ps1"; Desc = "restart_all.ps1 (installer)" },
    # monitor scripts
    @{ Source = "scripts\monitor\tray_monitor.py"; Dest = "scripts\monitor\tray_monitor.py"; Desc = "tray_monitor.py" },
    @{ Source = "scripts\monitor\tray_start.ps1"; Dest = "scripts\monitor\tray_start.ps1"; Desc = "tray_start.ps1" },
    @{ Source = "scripts\monitor\process_monitor.py"; Dest = "scripts\monitor\process_monitor.py"; Desc = "process_monitor.py" },
    @{ Source = "scripts\monitor\start_monitor.ps1"; Dest = "scripts\monitor\start_monitor.ps1"; Desc = "start_monitor.ps1" },
    @{ Source = "scripts\monitor\stop_monitor.ps1"; Dest = "scripts\monitor\stop_monitor.ps1"; Desc = "stop_monitor.ps1" },
    @{ Source = "scripts\monitor\view_monitor.ps1"; Dest = "scripts\monitor\view_monitor.ps1"; Desc = "view_monitor.ps1" },
    @{ Source = "scripts\monitor\monitor_status.ps1"; Dest = "scripts\monitor\monitor_status.ps1"; Desc = "monitor_status.ps1" },
    # diagnostic script (if exists)
    @{ Source = "debug_services.ps1"; Dest = "debug_services.ps1"; Desc = "debug_services.ps1" }
)

Write-Host "Copying updated scripts to: $InstallDir" -ForegroundColor Cyan
Write-Host ""

$okCount = 0
$skipCount = 0

foreach ($item in $filesToCopy) {
    $sourcePath = Join-Path $root $item.Source
    $destPath = Join-Path $InstallDir $item.Dest
    if (Test-Path $sourcePath) {
        $destDir = Split-Path -Parent $destPath
        if (-not (Test-Path $destDir)) {
            New-Item -ItemType Directory -Path $destDir -Force | Out-Null
        }
        Copy-Item -Path $sourcePath -Destination $destPath -Force
        Write-Host "  [OK] $($item.Desc)" -ForegroundColor Green
        $okCount++
    } else {
        Write-Host "  [SKIP] $($item.Desc) (source not found)" -ForegroundColor Yellow
        $skipCount++
    }
}

Write-Host ""
Write-Host "Done: $okCount copied, $skipCount skipped" -ForegroundColor Green
Write-Host "Restart services via menu to test." -ForegroundColor Gray
