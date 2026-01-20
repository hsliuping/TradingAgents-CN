# ============================================================================
# Copy Python DLLs from System Installation
# ============================================================================
# 从系统 Python 安装复制 DLLs 目录到嵌入式 Python
# ============================================================================

param(
    [string]$PortableDir = "",
    [string]$SourcePythonDir = ""
)

$ErrorActionPreference = "Stop"

# Determine portable directory
if (-not $PortableDir) {
    $root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
    $PortableDir = Join-Path $root "release\TradingAgentsCN-portable"
}

if (-not (Test-Path $PortableDir)) {
    Write-Host "❌ Portable directory not found: $PortableDir" -ForegroundColor Red
    exit 1
}

$pythonDir = Join-Path $PortableDir "vendors\python"
$targetDllsDir = Join-Path $pythonDir "DLLs"

if (-not (Test-Path $pythonDir)) {
    Write-Host "❌ Python directory not found: $pythonDir" -ForegroundColor Red
    exit 1
}

Write-Host "============================================================================" -ForegroundColor Cyan
Write-Host "  Copy Python DLLs" -ForegroundColor Cyan
Write-Host "============================================================================" -ForegroundColor Cyan
Write-Host ""

# Step 1: Find source Python installation
Write-Host "[1/3] Finding source Python installation..." -ForegroundColor Yellow
Write-Host ""

$sourceDllsDir = $null

# Option 1: User specified source
if ($SourcePythonDir -and (Test-Path $SourcePythonDir)) {
    $testDlls = Join-Path $SourcePythonDir "DLLs"
    if (Test-Path $testDlls) {
        $sourceDllsDir = $testDlls
        Write-Host "  ✅ Using user-specified source: $SourcePythonDir" -ForegroundColor Green
    }
}

# Option 2: Try to find system Python
if (-not $sourceDllsDir) {
    Write-Host "  Searching for system Python installations..." -ForegroundColor Gray
    
    $possiblePaths = @(
        "$env:LOCALAPPDATA\Programs\Python\Python310\DLLs",
        "$env:LOCALAPPDATA\Programs\Python\Python311\DLLs",
        "$env:LOCALAPPDATA\Programs\Python\Python312\DLLs",
        "C:\Python310\DLLs",
        "C:\Python311\DLLs",
        "C:\Python312\DLLs",
        "C:\Program Files\Python310\DLLs",
        "C:\Program Files\Python311\DLLs",
        "C:\Program Files\Python312\DLLs"
    )
    
    foreach ($path in $possiblePaths) {
        if (Test-Path $path) {
            $pydCount = (Get-ChildItem -Path $path -Filter "*.pyd" -ErrorAction SilentlyContinue).Count
            if ($pydCount -gt 0) {
                $socketPyd = Join-Path $path "_socket.pyd"
                if (Test-Path $socketPyd) {
                    $sourceDllsDir = $path
                    Write-Host "  ✅ Found: $path ($pydCount .pyd files)" -ForegroundColor Green
                    break
                }
            }
        }
    }
}

# Option 3: Try to get from python command
if (-not $sourceDllsDir) {
    Write-Host "  Trying to get Python path from 'python' command..." -ForegroundColor Gray
    try {
        $pythonPath = & python -c "import sys; print(sys.executable)" 2>&1
        if ($LASTEXITCODE -eq 0 -and $pythonPath) {
            $pythonExeDir = Split-Path -Parent $pythonPath
            $testDlls = Join-Path $pythonExeDir "DLLs"
            if (Test-Path $testDlls) {
                $socketPyd = Join-Path $testDlls "_socket.pyd"
                if (Test-Path $socketPyd) {
                    $sourceDllsDir = $testDlls
                    Write-Host "  ✅ Found from python command: $testDlls" -ForegroundColor Green
                }
            }
        }
    } catch {
        Write-Host "  ⚠️  Could not get Python path from command" -ForegroundColor Yellow
    }
}

if (-not $sourceDllsDir) {
    Write-Host ""
    Write-Host "❌ Could not find source DLLs directory!" -ForegroundColor Red
    Write-Host ""
    Write-Host "💡 Please specify the source Python directory:" -ForegroundColor Yellow
    Write-Host "  .\scripts\deployment\copy_python_dlls.ps1 -SourcePythonDir 'C:\Python310'" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "Or manually copy DLLs directory:" -ForegroundColor Yellow
    Write-Host "  1. Find your Python installation (e.g., C:\Python310\DLLs)" -ForegroundColor Cyan
    Write-Host "  2. Copy all files from DLLs to: $targetDllsDir" -ForegroundColor Cyan
    exit 1
}

Write-Host ""

# Step 2: Verify source DLLs
Write-Host "[2/3] Verifying source DLLs..." -ForegroundColor Yellow
Write-Host ""

$socketPyd = Join-Path $sourceDllsDir "_socket.pyd"
if (-not (Test-Path $socketPyd)) {
    Write-Host "  ❌ _socket.pyd not found in source: $sourceDllsDir" -ForegroundColor Red
    exit 1
}

$pydFiles = Get-ChildItem -Path $sourceDllsDir -Filter "*.pyd" -ErrorAction SilentlyContinue
$pydCount = $pydFiles.Count

Write-Host "  ✅ Source DLLs directory: $sourceDllsDir" -ForegroundColor Green
Write-Host "  Found $pydCount .pyd files" -ForegroundColor Gray
Write-Host "  ✅ _socket.pyd found" -ForegroundColor Green

Write-Host ""

# Step 3: Copy DLLs
Write-Host "[3/3] Copying DLLs..." -ForegroundColor Yellow
Write-Host ""

# Create target directory if needed
if (-not (Test-Path $targetDllsDir)) {
    Write-Host "  Creating target directory: $targetDllsDir" -ForegroundColor Gray
    New-Item -ItemType Directory -Path $targetDllsDir -Force | Out-Null
}

# Backup existing files if any
$existingFiles = Get-ChildItem -Path $targetDllsDir -ErrorAction SilentlyContinue
if ($existingFiles.Count -gt 0) {
    Write-Host "  ⚠️  Target directory already contains $($existingFiles.Count) files" -ForegroundColor Yellow
    $backupDir = "$targetDllsDir.backup.$(Get-Date -Format 'yyyyMMdd_HHmmss')"
    Write-Host "  Creating backup: $backupDir" -ForegroundColor Gray
    Copy-Item -Path $targetDllsDir -Destination $backupDir -Recurse -Force
}

# Copy all .pyd files
Write-Host "  Copying .pyd files..." -ForegroundColor Gray
$copiedCount = 0
foreach ($pydFile in $pydFiles) {
    $destPath = Join-Path $targetDllsDir $pydFile.Name
    Copy-Item -Path $pydFile.FullName -Destination $destPath -Force
    $copiedCount++
}

Write-Host "  ✅ Copied $copiedCount .pyd files" -ForegroundColor Green

# Also copy any .dll files in DLLs directory
$dllFiles = Get-ChildItem -Path $sourceDllsDir -Filter "*.dll" -ErrorAction SilentlyContinue
if ($dllFiles.Count -gt 0) {
    Write-Host "  Copying .dll files..." -ForegroundColor Gray
    $dllCopiedCount = 0
    foreach ($dllFile in $dllFiles) {
        $destPath = Join-Path $targetDllsDir $dllFile.Name
        Copy-Item -Path $dllFile.FullName -Destination $destPath -Force
        $dllCopiedCount++
    }
    Write-Host "  ✅ Copied $dllCopiedCount .dll files" -ForegroundColor Green
}

Write-Host ""

# Verify copy
Write-Host "  Verifying copy..." -ForegroundColor Gray
$targetSocketPyd = Join-Path $targetDllsDir "_socket.pyd"
if (Test-Path $targetSocketPyd) {
    Write-Host "  ✅ _socket.pyd copied successfully" -ForegroundColor Green
} else {
    Write-Host "  ❌ _socket.pyd copy failed!" -ForegroundColor Red
    exit 1
}

$targetPydCount = (Get-ChildItem -Path $targetDllsDir -Filter "*.pyd" -ErrorAction SilentlyContinue).Count
Write-Host "  ✅ Target directory now contains $targetPydCount .pyd files" -ForegroundColor Green

Write-Host ""
Write-Host "============================================================================" -ForegroundColor Cyan
Write-Host "✅ DLLs copy completed!" -ForegroundColor Green
Write-Host "============================================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "💡 Now run fix_embedded_python.ps1 again to verify:" -ForegroundColor Yellow
Write-Host "  .\scripts\deployment\fix_embedded_python.ps1" -ForegroundColor Cyan
Write-Host ""

exit 0
