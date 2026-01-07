# ============================================================================
# Build Portable Package - One-Click Solution
# ============================================================================
# This script combines sync and packaging into one step:
# 1. Sync code from main project to portable directory
# 2. Setup embedded Python (if not present)
# 3. Build frontend
# 4. Package portable directory into compressed archive
# ============================================================================

param(
    [string]$Version = "",
    [switch]$SkipSync = $false,
    [switch]$SkipEmbeddedPython = $false,
    [switch]$SkipFrontendBuild = $false,
    [switch]$SkipPackage = $false,
    [ValidateSet("zip", "7z", "both")]
    [string]$Format = "both",  # Package format: zip (for users), 7z (for NSIS), or both
    [string]$PythonVersion = "3.10.11"
)

# 设置控制台和文件编码为UTF-8
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
[Console]::InputEncoding = [System.Text.Encoding]::UTF8
$PSDefaultParameterValues['*:Encoding'] = 'utf8'
$OutputEncoding = [System.Text.Encoding]::UTF8

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$portableDir = Join-Path $root "release\TradingAgentsCN-portable"

Write-Host "============================================================================" -ForegroundColor Cyan
Write-Host "  Build TradingAgents-CN Portable Package" -ForegroundColor Cyan
Write-Host "============================================================================" -ForegroundColor Cyan
Write-Host ""

# ============================================================================
# Step 1: Sync Code (unless skipped)
# ============================================================================

if (-not $SkipSync) {
    Write-Host "[1/3] Syncing code to portable directory..." -ForegroundColor Yellow
    Write-Host ""

    $syncScript = Join-Path $root "scripts\deployment\sync_to_portable.ps1"
    if (-not (Test-Path $syncScript)) {
        Write-Host "ERROR: Sync script not found: $syncScript" -ForegroundColor Red
        exit 1
    }

    try {
        & powershell -ExecutionPolicy Bypass -File $syncScript
        if ($LASTEXITCODE -ne 0) {
            Write-Host "ERROR: Sync failed with exit code $LASTEXITCODE" -ForegroundColor Red
            exit 1
        }
    } catch {
        Write-Host "ERROR: Sync failed: $_" -ForegroundColor Red
        exit 1
    }

    Write-Host ""
    Write-Host "Sync completed successfully!" -ForegroundColor Green
    Write-Host ""
} else {
    Write-Host "[1/3] Skipping sync (using existing files)..." -ForegroundColor Yellow
    Write-Host ""
}

# ============================================================================
# Step 1.5: Setup Embedded Python (if not present)
# ============================================================================

if (-not $SkipEmbeddedPython) {
    $pythonExe = Join-Path $portableDir "vendors\python\python.exe"

    if (-not (Test-Path $pythonExe)) {
        Write-Host "[1.5/4] Setting up embedded Python..." -ForegroundColor Yellow
        Write-Host ""
        Write-Host "  Embedded Python not found, installing..." -ForegroundColor Cyan

        $setupScript = Join-Path $root "scripts\deployment\setup_embedded_python.ps1"
        if (-not (Test-Path $setupScript)) {
            Write-Host "  ERROR: Setup script not found: $setupScript" -ForegroundColor Red
            Write-Host "  Continuing without embedded Python..." -ForegroundColor Yellow
        } else {
            try {
                & powershell -ExecutionPolicy Bypass -File $setupScript -PythonVersion $PythonVersion -PortableDir $portableDir
                if ($LASTEXITCODE -eq 0) {
                    Write-Host ""
                    Write-Host "  ✅ Embedded Python setup completed!" -ForegroundColor Green

                    # Update scripts to use embedded Python
                    $updateScript = Join-Path $root "scripts\deployment\update_scripts_for_embedded_python.ps1"
                    if (Test-Path $updateScript) {
                        Write-Host "  Updating scripts..." -ForegroundColor Gray
                        & powershell -ExecutionPolicy Bypass -File $updateScript -PortableDir $portableDir | Out-Null
                    }

                    # 🔥 验证关键依赖是否安装
                    Write-Host ""
                    Write-Host "  🔍 Verifying critical dependencies..." -ForegroundColor Cyan
                    $verifyScript = Join-Path $root "scripts\deployment\verify_portable_dependencies.ps1"
                    if (Test-Path $verifyScript) {
                        & powershell -ExecutionPolicy Bypass -File $verifyScript -PortableDir $portableDir -Fix
                        if ($LASTEXITCODE -ne 0) {
                            Write-Host ""
                            Write-Host "  ❌ Dependency verification failed!" -ForegroundColor Red
                            Write-Host "  ⚠️ The portable version may not work correctly!" -ForegroundColor Yellow
                            Write-Host ""
                            $continue = Read-Host "  Continue packaging anyway? (y/N)"
                            if ($continue -ne 'y' -and $continue -ne 'Y') {
                                Write-Host "  Packaging cancelled." -ForegroundColor Yellow
                                exit 1
                            }
                        } else {
                            Write-Host "  ✅ All dependencies verified!" -ForegroundColor Green
                        }
                    }
                } else {
                    Write-Host "  ⚠️ Embedded Python setup failed, continuing..." -ForegroundColor Yellow
                }
            } catch {
                Write-Host "  ⚠️ Embedded Python setup error: $_" -ForegroundColor Yellow
                Write-Host "  Continuing with packaging..." -ForegroundColor Gray
            }
        }
        Write-Host ""
    } else {
        Write-Host "[1.5/4] Embedded Python already present, skipping..." -ForegroundColor Gray
        Write-Host "  Location: $pythonExe" -ForegroundColor DarkGray
        Write-Host ""
    }
} else {
    Write-Host "[1.5/4] Skipping embedded Python setup..." -ForegroundColor Gray
    Write-Host ""
}

# ============================================================================
# Step 2: Build Frontend
# ============================================================================

Write-Host "[2/4] Building frontend..." -ForegroundColor Yellow
Write-Host ""

$frontendDir = Join-Path $root "frontend"
$frontendDistSrc = Join-Path $frontendDir "dist"
$frontendDistDest = Join-Path $portableDir "frontend\dist"

if (Test-Path $frontendDir) {
    try {
        # Build in main project directory using Yarn (same as Dockerfile)
        Write-Host "  Building frontend in main project directory..." -ForegroundColor Cyan
        Write-Host "  Installing dependencies with Yarn..." -ForegroundColor Gray

        # Use cmd.exe to run yarn to avoid PowerShell parsing issues
        $installProcess = Start-Process -FilePath "cmd.exe" -ArgumentList "/c", "cd /d `"$frontendDir`" && yarn install --frozen-lockfile" -Wait -PassThru -NoNewWindow

        if ($installProcess.ExitCode -ne 0) {
            Write-Host "  WARNING: yarn install failed with exit code $($installProcess.ExitCode)" -ForegroundColor Yellow
        } else {
            Write-Host "  Dependencies installed successfully" -ForegroundColor Green
        }

        Write-Host "  Building frontend (skipping type check, this may take a few minutes)..." -ForegroundColor Gray
        # Use 'yarn vite build' to skip TypeScript type checking (same as Dockerfile)
        $buildProcess = Start-Process -FilePath "cmd.exe" -ArgumentList "/c", "cd /d `"$frontendDir`" && yarn vite build" -Wait -PassThru -NoNewWindow

        if ($buildProcess.ExitCode -ne 0) {
            Write-Host "  WARNING: Frontend build failed with exit code $($buildProcess.ExitCode)" -ForegroundColor Yellow
        } else {
            Write-Host "  Frontend build completed" -ForegroundColor Green

            # Copy dist to portable directory
            if (Test-Path $frontendDistSrc) {
                Write-Host "  Copying frontend dist to portable directory..." -ForegroundColor Gray

                # Remove old dist
                if (Test-Path $frontendDistDest) {
                    Remove-Item -Path $frontendDistDest -Recurse -Force
                }

                # Copy new dist
                Copy-Item -Path $frontendDistSrc -Destination $frontendDistDest -Recurse -Force
                Write-Host "  Frontend dist copied successfully" -ForegroundColor Green
            } else {
                Write-Host "  WARNING: Frontend dist not found: $frontendDistSrc" -ForegroundColor Yellow
            }
        }
    } catch {
        Write-Host "  ERROR: Frontend build failed: $_" -ForegroundColor Red
        Write-Host "  Continuing with packaging..." -ForegroundColor Yellow
    }
} else {
    Write-Host "  WARNING: Frontend directory not found: $frontendDir" -ForegroundColor Yellow
}

Write-Host ""

# ============================================================================
# Step 3: Package (unless skipped)
# ============================================================================

if ($SkipPackage) {
    Write-Host "[3/4] Packaging skipped (SkipPackage flag set)" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "============================================================================" -ForegroundColor Green
    Write-Host "  Sync and Build Completed Successfully!" -ForegroundColor Green
    Write-Host "============================================================================" -ForegroundColor Green
    Write-Host ""
    Write-Host "Files synced to: $portableDir" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "Next Steps:" -ForegroundColor White
    Write-Host "  1. Test the changes in release\TradingAgentsCN-portable" -ForegroundColor Gray
    Write-Host "  2. Run .\start_all.ps1 to start all services" -ForegroundColor Gray
    Write-Host "  3. Visit http://localhost to access the application" -ForegroundColor Gray
    Write-Host ""
    exit 0
}

Write-Host "[3/4] Packaging portable directory..." -ForegroundColor Yellow
Write-Host ""

$portableDir = Join-Path $root "release\TradingAgentsCN-portable"
if (-not (Test-Path $portableDir)) {
    Write-Host "ERROR: Portable directory not found: $portableDir" -ForegroundColor Red
    exit 1
}

# Determine version (priority: parameter > VERSION file > .env > default)
if (-not $Version) {
    # Try VERSION file in root
    $versionFile = Join-Path $root "VERSION"
    if (Test-Path $versionFile) {
        $Version = (Get-Content $versionFile -Raw).Trim()
        Write-Host "  Version from VERSION file: $Version" -ForegroundColor Cyan
    }

    # Fallback to .env file
    if (-not $Version) {
        $envFile = Join-Path $portableDir ".env"
        if (Test-Path $envFile) {
            $versionLine = Get-Content $envFile | Where-Object { $_ -match "^VERSION=" }
            if ($versionLine) {
                $Version = ($versionLine -split "=", 2)[1].Trim()
                Write-Host "  Version from .env file: $Version" -ForegroundColor Cyan
            }
        }
    }

    # Final fallback to default
    if (-not $Version) {
        $Version = "v0.1.13-preview"
        Write-Host "  Using default version: $Version" -ForegroundColor Yellow
    }
}

# Create packages directory
$packagesDir = Join-Path $root "release\packages"
if (-not (Test-Path $packagesDir)) {
    New-Item -ItemType Directory -Path $packagesDir -Force | Out-Null
}

$timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$packageName = "TradingAgentsCN-Portable-$Version-$timestamp"

Write-Host "  Package name: $packageName" -ForegroundColor Cyan
Write-Host "  Format: $Format" -ForegroundColor Cyan
Write-Host ""

# ============================================================================
# Create temporary directory and copy files (excluding database data)
# ============================================================================

Write-Host "  Creating temporary directory..." -ForegroundColor Gray
$tempDir = Join-Path $env:TEMP "TradingAgentsCN-Package-$timestamp"
New-Item -ItemType Directory -Path $tempDir -Force | Out-Null

Write-Host "  Copying all files to temporary directory..." -ForegroundColor Gray

# First, copy everything
$robocopyArgs = @(
    $portableDir,
    $tempDir,
    "/E",           # Copy subdirectories including empty ones
    "/NFL",         # No file list
    "/NDL",         # No directory list
    "/NJH",         # No job header
    "/NJS",         # No job summary
    "/NC",          # No class
    "/NS",          # No size
    "/NP"           # No progress
)

# Execute robocopy
Write-Host "  Source: $portableDir" -ForegroundColor DarkGray
Write-Host "  Destination: $tempDir" -ForegroundColor DarkGray
$robocopyOutput = & robocopy @robocopyArgs 2>&1

# robocopy exit codes: 0-7 success, 8+ failure
if ($LASTEXITCODE -ge 8) {
    Write-Host "  ERROR: Robocopy failed with exit code $LASTEXITCODE" -ForegroundColor Red
    Write-Host "  Output: $robocopyOutput" -ForegroundColor Gray
    Remove-Item -Path $tempDir -Recurse -Force -ErrorAction SilentlyContinue
    exit 1
}

Write-Host "  Robocopy exit code: $LASTEXITCODE" -ForegroundColor DarkGray

Write-Host "  Files copied successfully" -ForegroundColor Green

# Now remove directories we don't want to package (database data, logs, cache)
Write-Host "  Removing database data and logs from package..." -ForegroundColor Gray

$excludeDirs = @(
    (Join-Path $tempDir "data\mongodb"),
    (Join-Path $tempDir "data\redis"),
    (Join-Path $tempDir "logs"),
    (Join-Path $tempDir "data\cache")
)

foreach ($dir in $excludeDirs) {
    if (Test-Path $dir) {
        Remove-Item -Path $dir -Recurse -Force -ErrorAction SilentlyContinue
        Write-Host "    Removed: $($dir.Replace($tempDir, ''))" -ForegroundColor DarkGray
    }
}

Write-Host "  Cleanup completed" -ForegroundColor Green

# ============================================================================
# Remove MongoDB debug symbols and crash dumps (saves ~2GB)
# ============================================================================

Write-Host "  Removing MongoDB debug symbols and crash dumps..." -ForegroundColor Gray

$mongodbVendorDir = Join-Path $tempDir "vendors\mongodb"
if (Test-Path $mongodbVendorDir) {
    # Remove .pdb files (debug symbols)
    $pdbFiles = Get-ChildItem -Path $mongodbVendorDir -Filter "*.pdb" -Recurse -File
    foreach ($file in $pdbFiles) {
        Remove-Item -Path $file.FullName -Force -ErrorAction SilentlyContinue
        $sizeMB = [math]::Round($file.Length / 1MB, 2)
        Write-Host "    Removed: $($file.Name) ($sizeMB MB)" -ForegroundColor DarkGray
    }

    # Remove .mdmp files (crash dumps)
    $mdmpFiles = Get-ChildItem -Path $mongodbVendorDir -Filter "*.mdmp" -Recurse -File
    foreach ($file in $mdmpFiles) {
        Remove-Item -Path $file.FullName -Force -ErrorAction SilentlyContinue
        $sizeMB = [math]::Round($file.Length / 1MB, 2)
        Write-Host "    Removed: $($file.Name) ($sizeMB MB)" -ForegroundColor DarkGray
    }

    Write-Host "  MongoDB cleanup completed (saved ~2GB)" -ForegroundColor Green
}

# ============================================================================
# Clean up runtime directory (keep config files only)
# ============================================================================

Write-Host "  Cleaning runtime directory (keeping config files)..." -ForegroundColor Gray

$runtimeDir = Join-Path $tempDir "runtime"
if (Test-Path $runtimeDir) {
    # Keep only config files (.conf, .types)
    Get-ChildItem -Path $runtimeDir -File | Where-Object {
        $_.Extension -notin @('.conf', '.types')
    } | Remove-Item -Force -ErrorAction SilentlyContinue

    Write-Host "  Runtime directory cleaned" -ForegroundColor Green
}

# ============================================================================
# Remove venv if exists (we use embedded Python instead)
# ============================================================================

$venvDir = Join-Path $tempDir "venv"

if (Test-Path $venvDir) {
    Write-Host "  Removing venv (using embedded Python instead)..." -ForegroundColor Gray
    Remove-Item -Path $venvDir -Recurse -Force -ErrorAction SilentlyContinue
    Write-Host "  ✅ venv removed" -ForegroundColor Green
}

# ============================================================================
# Keep embedded Python (venv needs it as base installation)
# ============================================================================

$embeddedPythonDir = Join-Path $tempDir "vendors\python"

if ((Test-Path $venvDir) -and (Test-Path $embeddedPythonDir)) {
    Write-Host "  Keeping embedded Python (venv requires it as base installation)..." -ForegroundColor Gray
    $pythonSize = (Get-ChildItem $embeddedPythonDir -Recurse -ErrorAction SilentlyContinue | Measure-Object -Property Length -Sum).Sum / 1MB
    Write-Host "  Embedded Python size: $([math]::Round($pythonSize, 2)) MB" -ForegroundColor Green
}

# ============================================================================
# Compress files based on format
# ============================================================================

$createdPackages = @()

# Function to create 7z package (for NSIS installer)
function Create-7zPackage {
    param($TempDir, $OutputPath, $ExcludeVendors7zip = $false)

    Write-Host "  Creating 7z package..." -ForegroundColor Cyan

    # Check if 7z.exe exists
    $7zExe = Join-Path $root "vendors\7zip\7z.exe"
    if (-not (Test-Path $7zExe)) {
        throw "7z.exe not found at $7zExe. Please copy from C:\7-Zip"
    }

    # If excluding vendors/7zip, create a copy without it
    $sourcePath = $TempDir
    if ($ExcludeVendors7zip) {
        Write-Host "    Excluding vendors/7zip directory (for NSIS installer)..." -ForegroundColor Gray
        $tempDir7z = Join-Path $env:TEMP "TradingAgentsCN-7z-$timestamp"
        Copy-Item -Path $TempDir -Destination $tempDir7z -Recurse -Force
        $vendors7zipPath = Join-Path $tempDir7z "vendors\7zip"
        if (Test-Path $vendors7zipPath) {
            Remove-Item -Path $vendors7zipPath -Recurse -Force
            Write-Host "    Removed vendors/7zip from package" -ForegroundColor Gray
        }
        $sourcePath = $tempDir7z
    }

    Write-Host "    Compression level: Medium (mx=5)" -ForegroundColor Gray
    Write-Host "    Multi-threading: Enabled" -ForegroundColor Gray

    & $7zExe a -t7z -mx=5 -mmt=on -bsp1 "$OutputPath" "$sourcePath\*" | Out-Null

    if ($LASTEXITCODE -ne 0) {
        throw "7z.exe exited with code $LASTEXITCODE"
    }

    # Clean up temp directory if created
    if ($ExcludeVendors7zip -and (Test-Path $tempDir7z)) {
        Remove-Item -Path $tempDir7z -Recurse -Force
    }

    $fileInfo = Get-Item $OutputPath
    Write-Host "    7z package created: $([math]::Round($fileInfo.Length / 1MB, 2)) MB" -ForegroundColor Green
    return $fileInfo
}

# Function to create ZIP package (for users)
function Create-ZipPackage {
    param($TempDir, $OutputPath)

    Write-Host "  Creating ZIP package..." -ForegroundColor Cyan
    Write-Host "    Using .NET compression (Optimal level)" -ForegroundColor Gray

    Add-Type -AssemblyName System.IO.Compression.FileSystem
    [System.IO.Compression.ZipFile]::CreateFromDirectory($TempDir, $OutputPath, [System.IO.Compression.CompressionLevel]::Optimal, $false)

    $fileInfo = Get-Item $OutputPath
    Write-Host "    ZIP package created: $([math]::Round($fileInfo.Length / 1MB, 2)) MB" -ForegroundColor Green
    return $fileInfo
}

try {
    Write-Host ""
    Write-Host "  Compressing files (this may take several minutes)..." -ForegroundColor Gray
    Write-Host ""

    # Create packages based on format parameter
    if ($Format -eq "7z" -or $Format -eq "both") {
        $7zPath = Join-Path $packagesDir "$packageName-installer.7z"
        if (Test-Path $7zPath) { Remove-Item $7zPath -Force }
        $pkg = Create-7zPackage -TempDir $tempDir -OutputPath $7zPath -ExcludeVendors7zip $true
        $createdPackages += $pkg
    }

    if ($Format -eq "zip" -or $Format -eq "both") {
        $zipPath = Join-Path $packagesDir "$packageName.zip"
        if (Test-Path $zipPath) { Remove-Item $zipPath -Force }
        $pkg = Create-ZipPackage -TempDir $tempDir -OutputPath $zipPath
        $createdPackages += $pkg
    }

    Write-Host ""
    Write-Host "  Compression completed successfully!" -ForegroundColor Green
} catch {
    Write-Host "  ERROR: Compression failed: $_" -ForegroundColor Red
    Write-Host "  Error details: $($_.Exception.Message)" -ForegroundColor Gray
    Remove-Item -Path $tempDir -Recurse -Force -ErrorAction SilentlyContinue
    exit 1
}

# ============================================================================
# Clean up temporary directory
# ============================================================================

Write-Host "  Cleaning up temporary directory..." -ForegroundColor Gray
Write-Host "  DEBUG: Temp directory kept at: $tempDir" -ForegroundColor Yellow
# Remove-Item -Path $tempDir -Recurse -Force

# ============================================================================
# Display results
# ============================================================================

Write-Host ""
Write-Host "============================================================================" -ForegroundColor Green
Write-Host "  Package(s) Created Successfully!" -ForegroundColor Green
Write-Host "============================================================================" -ForegroundColor Green
Write-Host ""

Write-Host "Package Information:" -ForegroundColor White
foreach ($pkg in $createdPackages) {
    $fileSizeMB = [math]::Round($pkg.Length / 1MB, 2)
    $fileType = if ($pkg.Extension -eq ".7z") { "7z (for NSIS installer)" } else { "ZIP (for users)" }
    Write-Host "  File: $($pkg.Name)" -ForegroundColor Cyan
    Write-Host "  Type: $fileType" -ForegroundColor Cyan
    Write-Host "  Size: $fileSizeMB MB" -ForegroundColor Cyan
    Write-Host "  Path: $($pkg.FullName)" -ForegroundColor Cyan
    Write-Host ""
}

Write-Host "Next Steps:" -ForegroundColor White
if ($Format -eq "zip" -or $Format -eq "both") {
    Write-Host "  For ZIP package (users):" -ForegroundColor Yellow
    Write-Host "    1. Extract the ZIP file (Windows built-in)" -ForegroundColor Gray
    Write-Host "    2. Run start_all.ps1 to start all services" -ForegroundColor Gray
    Write-Host "    3. Visit http://localhost to access the application" -ForegroundColor Gray
    Write-Host ""
}
if ($Format -eq "7z" -or $Format -eq "both") {
    Write-Host "  For 7z package (NSIS installer):" -ForegroundColor Yellow
    Write-Host "    1. Run build_installer.ps1 to create Windows installer" -ForegroundColor Gray
    Write-Host "    2. The installer will use this 7z file internally" -ForegroundColor Gray
    Write-Host ""
}

Write-Host "Note: First-time startup will automatically import configuration and create default user (admin/admin123)" -ForegroundColor Yellow
Write-Host ""

