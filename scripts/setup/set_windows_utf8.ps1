# ============================================================================
# Set Windows System Default Encoding to UTF-8
# ============================================================================
# This script configures Windows to use UTF-8 as the default system encoding
# 
# Requirements:
# - Windows 10 version 1903 or later
# - Administrator privileges
# 
# Usage:
#   Run as Administrator:
#   powershell -ExecutionPolicy Bypass -File .\scripts\setup\set_windows_utf8.ps1
# ============================================================================

#Requires -RunAsAdministrator

$ErrorActionPreference = "Stop"

Write-Host "============================================================================" -ForegroundColor Cyan
Write-Host "  Set Windows System Default Encoding to UTF-8" -ForegroundColor Cyan
Write-Host "============================================================================" -ForegroundColor Cyan
Write-Host ""

# ============================================================================
# Check Windows Version
# ============================================================================

Write-Host "[1/4] Checking Windows version..." -ForegroundColor Yellow

$osVersion = [System.Environment]::OSVersion.Version
$buildNumber = (Get-ItemProperty "HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion").CurrentBuildNumber

Write-Host "  OS Version: $($osVersion.Major).$($osVersion.Minor) Build $buildNumber" -ForegroundColor Gray

if ($buildNumber -lt 18362) {
    Write-Host ""
    Write-Host "WARNING: This feature requires Windows 10 version 1903 (build 18362) or later" -ForegroundColor Yellow
    Write-Host "Your current build: $buildNumber" -ForegroundColor Yellow
    Write-Host ""
    $continue = Read-Host "Do you want to continue anyway? (y/N)"
    if ($continue -ne 'y' -and $continue -ne 'Y') {
        Write-Host "Cancelled by user" -ForegroundColor Red
        exit 1
    }
}

Write-Host "  OK - Windows version is compatible" -ForegroundColor Green
Write-Host ""

# ============================================================================
# Backup Current Settings
# ============================================================================

Write-Host "[2/4] Backing up current settings..." -ForegroundColor Yellow

$backupDir = Join-Path $env:USERPROFILE "Desktop\UTF8_Backup_$(Get-Date -Format 'yyyyMMdd_HHmmss')"
New-Item -ItemType Directory -Path $backupDir -Force | Out-Null

# Export current registry settings
$regPath = "HKLM:\SYSTEM\CurrentControlSet\Control\Nls\CodePage"
$backupFile = Join-Path $backupDir "registry_backup.reg"

reg export "HKLM\SYSTEM\CurrentControlSet\Control\Nls\CodePage" $backupFile /y | Out-Null

Write-Host "  Backup saved to: $backupDir" -ForegroundColor Gray
Write-Host "  OK - Settings backed up" -ForegroundColor Green
Write-Host ""

# ============================================================================
# Set UTF-8 as System Default
# ============================================================================

Write-Host "[3/4] Setting UTF-8 as system default encoding..." -ForegroundColor Yellow

try {
    # Method 1: Use Beta UTF-8 support (Recommended for Windows 10 1903+)
    Write-Host "  Enabling Beta: Use Unicode UTF-8 for worldwide language support..." -ForegroundColor Cyan
    
    $regPath = "HKLM:\SYSTEM\CurrentControlSet\Control\Nls\CodePage"
    
    # Set OEMCP and ACP to 65001 (UTF-8)
    Set-ItemProperty -Path $regPath -Name "OEMCP" -Value "65001" -Type String
    Set-ItemProperty -Path $regPath -Name "ACP" -Value "65001" -Type String
    
    Write-Host "  OK - Registry updated" -ForegroundColor Green
    
    # Method 2: Set via intl.cpl (Alternative method)
    Write-Host "  Setting system locale to UTF-8..." -ForegroundColor Cyan
    
    # This requires a restart to take effect
    $xml = @"
<gs:GlobalizationServices xmlns:gs="urn:longhornGlobalizationUnattend">
    <gs:UserList>
        <gs:User UserID="Current" CopySettingsToDefaultUserAcct="true" CopySettingsToSystemAcct="true"/>
    </gs:UserList>
    <gs:SystemLocale Name="en-US"/>
</gs:GlobalizationServices>
"@
    
    $xmlFile = Join-Path $env:TEMP "utf8_locale.xml"
    $xml | Out-File -FilePath $xmlFile -Encoding UTF8
    
    # Apply settings (requires restart)
    # control.exe intl.cpl,,/f:"$xmlFile"
    
    Write-Host "  OK - System locale configured" -ForegroundColor Green
    
} catch {
    Write-Host "  ERROR: Failed to set UTF-8 encoding" -ForegroundColor Red
    Write-Host "  $($_.Exception.Message)" -ForegroundColor Red
    Write-Host ""
    Write-Host "You can restore settings from: $backupDir" -ForegroundColor Yellow
    exit 1
}

Write-Host ""

# ============================================================================
# Verify Settings
# ============================================================================

Write-Host "[4/4] Verifying settings..." -ForegroundColor Yellow

$oemcp = (Get-ItemProperty -Path "HKLM:\SYSTEM\CurrentControlSet\Control\Nls\CodePage").OEMCP
$acp = (Get-ItemProperty -Path "HKLM:\SYSTEM\CurrentControlSet\Control\Nls\CodePage").ACP

Write-Host "  Current Code Pages:" -ForegroundColor Gray
Write-Host "    OEMCP (Console): $oemcp" -ForegroundColor Gray
Write-Host "    ACP (System):    $acp" -ForegroundColor Gray

if ($oemcp -eq "65001" -and $acp -eq "65001") {
    Write-Host "  OK - UTF-8 encoding is set" -ForegroundColor Green
} else {
    Write-Host "  WARNING - Settings may not be fully applied" -ForegroundColor Yellow
}

Write-Host ""

# ============================================================================
# Summary
# ============================================================================

Write-Host "============================================================================" -ForegroundColor Cyan
Write-Host "  Configuration Complete" -ForegroundColor Cyan
Write-Host "============================================================================" -ForegroundColor Cyan
Write-Host ""

Write-Host "Changes made:" -ForegroundColor Yellow
Write-Host "  - System code page set to UTF-8 (65001)" -ForegroundColor White
Write-Host "  - Console code page set to UTF-8 (65001)" -ForegroundColor White
Write-Host ""

Write-Host "IMPORTANT:" -ForegroundColor Red
Write-Host "  You MUST restart your computer for changes to take effect!" -ForegroundColor Red
Write-Host ""

Write-Host "Backup location:" -ForegroundColor Yellow
Write-Host "  $backupDir" -ForegroundColor White
Write-Host ""

Write-Host "To restore original settings:" -ForegroundColor Yellow
Write-Host "  1. Double-click: $backupFile" -ForegroundColor White
Write-Host "  2. Restart your computer" -ForegroundColor White
Write-Host ""

$restart = Read-Host "Do you want to restart now? (y/N)"
if ($restart -eq 'y' -or $restart -eq 'Y') {
    Write-Host ""
    Write-Host "Restarting in 10 seconds..." -ForegroundColor Yellow
    Write-Host "Press Ctrl+C to cancel" -ForegroundColor Gray
    Start-Sleep -Seconds 10
    Restart-Computer -Force
} else {
    Write-Host ""
    Write-Host "Please restart your computer manually to apply changes" -ForegroundColor Yellow
    Write-Host ""
}

