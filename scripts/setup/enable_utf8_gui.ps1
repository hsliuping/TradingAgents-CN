# ============================================================================
# Enable UTF-8 via Windows Settings (GUI Method)
# ============================================================================
# This script opens the Windows Settings page where you can enable UTF-8
# 
# Requirements:
# - Windows 10 version 1903 or later
# - No administrator privileges required
# 
# Usage:
#   powershell -ExecutionPolicy Bypass -File .\scripts\setup\enable_utf8_gui.ps1
# ============================================================================

$ErrorActionPreference = "Stop"

Write-Host "============================================================================" -ForegroundColor Cyan
Write-Host "  Enable UTF-8 via Windows Settings" -ForegroundColor Cyan
Write-Host "============================================================================" -ForegroundColor Cyan
Write-Host ""

Write-Host "This script will guide you through enabling UTF-8 in Windows Settings" -ForegroundColor Yellow
Write-Host ""

# ============================================================================
# Check Windows Version
# ============================================================================

$buildNumber = (Get-ItemProperty "HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion").CurrentBuildNumber

if ($buildNumber -lt 18362) {
    Write-Host "ERROR: This feature requires Windows 10 version 1903 (build 18362) or later" -ForegroundColor Red
    Write-Host "Your current build: $buildNumber" -ForegroundColor Red
    Write-Host ""
    Write-Host "Please update Windows to use this feature" -ForegroundColor Yellow
    exit 1
}

Write-Host "Windows version: Build $buildNumber OK" -ForegroundColor Green
Write-Host ""

# ============================================================================
# Instructions
# ============================================================================

Write-Host "============================================================================" -ForegroundColor Cyan
Write-Host "  Manual Steps to Enable UTF-8" -ForegroundColor Cyan
Write-Host "============================================================================" -ForegroundColor Cyan
Write-Host ""

Write-Host "Please follow these steps:" -ForegroundColor Yellow
Write-Host ""

Write-Host "1. Click 'Start' menu" -ForegroundColor White
Write-Host "   (Or press Windows key)" -ForegroundColor Gray
Write-Host ""

Write-Host "2. Click 'Settings' (gear icon)" -ForegroundColor White
Write-Host "   (Or press Windows + I)" -ForegroundColor Gray
Write-Host ""

Write-Host "3. Click 'Time & Language'" -ForegroundColor White
Write-Host ""

Write-Host "4. Click 'Language' in the left sidebar" -ForegroundColor White
Write-Host ""

Write-Host "5. Click 'Administrative language settings'" -ForegroundColor White
Write-Host "   (Under 'Related settings')" -ForegroundColor Gray
Write-Host ""

Write-Host "6. Click 'Change system locale...' button" -ForegroundColor White
Write-Host ""

Write-Host "7. Check the box:" -ForegroundColor White
Write-Host "   'Beta: Use Unicode UTF-8 for worldwide language support'" -ForegroundColor Cyan
Write-Host ""

Write-Host "8. Click 'OK'" -ForegroundColor White
Write-Host ""

Write-Host "9. Click 'Restart now' to apply changes" -ForegroundColor White
Write-Host ""

Write-Host "============================================================================" -ForegroundColor Cyan
Write-Host ""

$openSettings = Read-Host "Do you want to open Settings now? (Y/n)"

if ($openSettings -ne 'n' -and $openSettings -ne 'N') {
    Write-Host ""
    Write-Host "Opening Windows Settings..." -ForegroundColor Green
    Write-Host ""
    
    # Open Language Settings
    Start-Process "ms-settings:regionlanguage"
    
    Write-Host "Settings opened. Please follow the steps above." -ForegroundColor Yellow
    Write-Host ""
} else {
    Write-Host ""
    Write-Host "You can open Settings manually later:" -ForegroundColor Yellow
    Write-Host "  Press Windows + I, then navigate to Time & Language > Language" -ForegroundColor Gray
    Write-Host ""
}

Write-Host "============================================================================" -ForegroundColor Cyan
Write-Host "  Alternative: Direct Registry Method" -ForegroundColor Cyan
Write-Host "============================================================================" -ForegroundColor Cyan
Write-Host ""

Write-Host "If you prefer to use the registry method (requires admin):" -ForegroundColor Yellow
Write-Host "  Run: .\scripts\setup\set_windows_utf8.ps1" -ForegroundColor White
Write-Host ""

Write-Host "============================================================================" -ForegroundColor Cyan
Write-Host "  After Enabling UTF-8" -ForegroundColor Cyan
Write-Host "============================================================================" -ForegroundColor Cyan
Write-Host ""

Write-Host "After restarting your computer:" -ForegroundColor Yellow
Write-Host ""

Write-Host "1. Verify UTF-8 is enabled:" -ForegroundColor White
Write-Host "   powershell -Command '[Console]::OutputEncoding'" -ForegroundColor Gray
Write-Host "   (Should show: Unicode (UTF-8))" -ForegroundColor Gray
Write-Host ""

Write-Host "2. Test with Chinese characters:" -ForegroundColor White
Write-Host "   powershell -Command 'Write-Host \"你好，世界！\"'" -ForegroundColor Gray
Write-Host ""

Write-Host "3. Run our test script:" -ForegroundColor White
Write-Host "   .\scripts\deployment\test_utf8_encoding.ps1" -ForegroundColor Gray
Write-Host ""

Write-Host "============================================================================" -ForegroundColor Cyan
Write-Host ""

Write-Host "Press any key to exit..." -ForegroundColor Gray
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")

