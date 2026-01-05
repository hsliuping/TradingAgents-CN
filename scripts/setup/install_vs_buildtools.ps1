# ============================================================================
# Install Visual Studio Build Tools
# ============================================================================
# This script automates the download and installation of VS Build Tools
# Required for compiling Cython extensions (.pyd files)
# ============================================================================

param(
    [switch]$Silent = $false,
    [switch]$DownloadOnly = $false,
    [string]$InstallPath = "C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools"
)

$ErrorActionPreference = "Stop"

Write-Host "============================================================================" -ForegroundColor Cyan
Write-Host "  Visual Studio Build Tools Installer" -ForegroundColor Cyan
Write-Host "============================================================================" -ForegroundColor Cyan
Write-Host ""

# ============================================================================
# Check if already installed
# ============================================================================

Write-Host "[1/4] Checking existing installation..." -ForegroundColor Yellow

$clExe = Get-ChildItem -Path "C:\Program Files*" -Recurse -Filter "cl.exe" -ErrorAction SilentlyContinue | 
         Where-Object { $_.FullName -like "*Microsoft Visual Studio*" } | 
         Select-Object -First 1

if ($clExe) {
    Write-Host "  ✅ Visual Studio Build Tools already installed!" -ForegroundColor Green
    Write-Host "  Location: $($clExe.DirectoryName)" -ForegroundColor Gray
    Write-Host ""
    
    $continue = Read-Host "Do you want to reinstall? (y/N)"
    if ($continue -ne 'y' -and $continue -ne 'Y') {
        Write-Host "Installation cancelled." -ForegroundColor Yellow
        exit 0
    }
} else {
    Write-Host "  ℹ️ Visual Studio Build Tools not found" -ForegroundColor Cyan
}

Write-Host ""

# ============================================================================
# Download installer
# ============================================================================

Write-Host "[2/4] Downloading installer..." -ForegroundColor Yellow

$installerUrl = "https://aka.ms/vs/17/release/vs_buildtools.exe"
$installerPath = Join-Path $env:TEMP "vs_buildtools.exe"

if (Test-Path $installerPath) {
    Write-Host "  ℹ️ Installer already exists: $installerPath" -ForegroundColor Cyan
    $redownload = Read-Host "Re-download? (y/N)"
    if ($redownload -eq 'y' -or $redownload -eq 'Y') {
        Remove-Item $installerPath -Force
    }
}

if (-not (Test-Path $installerPath)) {
    Write-Host "  Downloading from: $installerUrl" -ForegroundColor Gray
    Write-Host "  Saving to: $installerPath" -ForegroundColor Gray
    
    try {
        # Use BITS for better download performance
        Import-Module BitsTransfer
        Start-BitsTransfer -Source $installerUrl -Destination $installerPath -Description "Downloading VS Build Tools"
        Write-Host "  ✅ Download completed!" -ForegroundColor Green
    } catch {
        Write-Host "  ⚠️ BITS transfer failed, trying WebClient..." -ForegroundColor Yellow
        $webClient = New-Object System.Net.WebClient
        $webClient.DownloadFile($installerUrl, $installerPath)
        Write-Host "  ✅ Download completed!" -ForegroundColor Green
    }
} else {
    Write-Host "  ✅ Using existing installer" -ForegroundColor Green
}

Write-Host ""

if ($DownloadOnly) {
    Write-Host "Download-only mode. Installer saved to: $installerPath" -ForegroundColor Cyan
    exit 0
}

# ============================================================================
# Install Build Tools
# ============================================================================

Write-Host "[3/4] Installing Build Tools..." -ForegroundColor Yellow
Write-Host ""
Write-Host "  This will install:" -ForegroundColor Cyan
Write-Host "    - MSVC C++ compiler" -ForegroundColor Gray
Write-Host "    - Windows SDK" -ForegroundColor Gray
Write-Host "    - CMake tools" -ForegroundColor Gray
Write-Host ""
Write-Host "  Installation size: ~6-8 GB" -ForegroundColor Yellow
Write-Host "  Estimated time: 10-30 minutes (depending on network speed)" -ForegroundColor Yellow
Write-Host ""

if (-not $Silent) {
    $confirm = Read-Host "Continue with installation? (Y/n)"
    if ($confirm -eq 'n' -or $confirm -eq 'N') {
        Write-Host "Installation cancelled." -ForegroundColor Yellow
        exit 0
    }
}

Write-Host "  Starting installation..." -ForegroundColor Cyan
Write-Host ""

$installArgs = @(
    "--quiet",
    "--wait",
    "--norestart",
    "--nocache",
    "--add", "Microsoft.VisualStudio.Workload.VCTools",
    "--add", "Microsoft.VisualStudio.Component.VC.Tools.x86.x64",
    "--add", "Microsoft.VisualStudio.Component.Windows11SDK.22000"
)

if (-not $Silent) {
    # Interactive installation with UI
    $installArgs = @(
        "--add", "Microsoft.VisualStudio.Workload.VCTools"
    )
}

try {
    $process = Start-Process -FilePath $installerPath -ArgumentList $installArgs -Wait -PassThru
    
    if ($process.ExitCode -eq 0) {
        Write-Host "  ✅ Installation completed successfully!" -ForegroundColor Green
    } elseif ($process.ExitCode -eq 3010) {
        Write-Host "  ✅ Installation completed (reboot required)" -ForegroundColor Yellow
    } else {
        Write-Host "  ❌ Installation failed with exit code: $($process.ExitCode)" -ForegroundColor Red
        exit 1
    }
} catch {
    Write-Host "  ❌ Installation error: $_" -ForegroundColor Red
    exit 1
}

Write-Host ""

# ============================================================================
# Verify installation
# ============================================================================

Write-Host "[4/4] Verifying installation..." -ForegroundColor Yellow

Start-Sleep -Seconds 2

$clExe = Get-ChildItem -Path "C:\Program Files*" -Recurse -Filter "cl.exe" -ErrorAction SilentlyContinue | 
         Where-Object { $_.FullName -like "*Microsoft Visual Studio*" } | 
         Select-Object -First 1

if ($clExe) {
    Write-Host "  ✅ C++ compiler found!" -ForegroundColor Green
    Write-Host "  Location: $($clExe.FullName)" -ForegroundColor Gray
} else {
    Write-Host "  ⚠️ C++ compiler not found. You may need to restart your computer." -ForegroundColor Yellow
}

Write-Host ""
Write-Host "============================================================================" -ForegroundColor Cyan
Write-Host "  Installation Summary" -ForegroundColor Cyan
Write-Host "============================================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host "  1. Restart your computer (recommended)" -ForegroundColor White
Write-Host "  2. Open a new PowerShell window" -ForegroundColor White
Write-Host "  3. Run: .\scripts\deployment\compile_licensing.ps1" -ForegroundColor White
Write-Host ""

