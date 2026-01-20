# ============================================================================
# Fix Embedded Python Configuration
# ============================================================================
# 修复嵌入式 Python 的配置，确保 _socket 等内置模块可用
# ============================================================================

param(
    [string]$PortableDir = ""
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
$pythonExe = Join-Path $pythonDir "python.exe"

if (-not (Test-Path $pythonExe)) {
    Write-Host "❌ Python executable not found: $pythonExe" -ForegroundColor Red
    exit 1
}

Write-Host "============================================================================" -ForegroundColor Cyan
Write-Host "  Fix Embedded Python Configuration" -ForegroundColor Cyan
Write-Host "============================================================================" -ForegroundColor Cyan
Write-Host ""

# Step 1: Check and fix _pth file
Write-Host "[1/3] Checking and fixing python*._pth file..." -ForegroundColor Yellow
Write-Host ""

$pthFile = Get-ChildItem -Path $pythonDir -Filter "python*._pth" | Select-Object -First 1

if (-not $pthFile) {
    Write-Host "  ❌ Python ._pth file not found" -ForegroundColor Red
    Write-Host "  💡 Please run setup_embedded_python.ps1 first" -ForegroundColor Yellow
    exit 1
}

Write-Host "  Found: $($pthFile.Name)" -ForegroundColor Gray

# Read current content
$content = Get-Content $pthFile.FullName -Raw
$originalContent = $content

# Ensure DLLs directory is included
# Check if DLLs is mentioned (with or without backslash)
$hasDLLs = $content -match "\.\\DLLs" -or $content -match "DLLs" -or $content -match "\./DLLs"

if (-not $hasDLLs) {
    Write-Host "  ⚠️  DLLs directory not found in _pth file" -ForegroundColor Yellow
    Write-Host "  Adding .\DLLs to _pth file..." -ForegroundColor Gray
    
    # Split into lines
    $lines = $content -split "`r?`n"
    $newLines = @()
    $dllsAdded = $false
    
    foreach ($line in $lines) {
        $trimmedLine = $line.Trim()
        
        # Skip empty lines and comments for now
        if ($trimmedLine -eq "" -or $trimmedLine.StartsWith("#")) {
            $newLines += $line
            continue
        }
        
        $newLines += $line
        
        # Add DLLs right after python310.zip line (before any other paths)
        if ($trimmedLine -match "python\d+\.zip" -and -not $dllsAdded) {
            $newLines += ".\DLLs"
            $dllsAdded = $true
        }
    }
    
    # If still not added, add it at the beginning (after python310.zip)
    if (-not $dllsAdded) {
        $newLines = @()
        foreach ($line in $lines) {
            $trimmedLine = $line.Trim()
            $newLines += $line
            
            if ($trimmedLine -match "python\d+\.zip" -and -not $dllsAdded) {
                $newLines += ".\DLLs"
                $dllsAdded = $true
            }
        }
    }
    
    $content = $newLines -join "`r`n"
} else {
    Write-Host "  ✅ DLLs directory already in _pth file" -ForegroundColor Green
}

# Ensure import site is uncommented
if ($content -match "#import site") {
    Write-Host "  Uncommenting 'import site'..." -ForegroundColor Gray
    $content = $content -replace "#import site", "import site"
}

# Ensure Lib\site-packages is included
if ($content -notmatch "\.\\Lib\\site-packages") {
    Write-Host "  Adding .\Lib\site-packages..." -ForegroundColor Gray
    $content += "`r`n.\Lib\site-packages"
}

# Write back
if ($content -ne $originalContent) {
    Set-Content -Path $pthFile.FullName -Value $content -Encoding ASCII -NoNewline
    Write-Host "  ✅ _pth file updated" -ForegroundColor Green
    Write-Host ""
    Write-Host "  Updated content:" -ForegroundColor Gray
    Get-Content $pthFile.FullName | ForEach-Object { Write-Host "    $_" -ForegroundColor DarkGray }
} else {
    Write-Host "  ✅ _pth file is already correctly configured" -ForegroundColor Green
}

Write-Host ""

# Step 2: Check DLLs directory
Write-Host "[2/3] Checking DLLs directory..." -ForegroundColor Yellow
Write-Host ""

$dllsDir = Join-Path $pythonDir "DLLs"

if (-not (Test-Path $dllsDir)) {
    Write-Host "  ⚠️  DLLs directory not found: $dllsDir" -ForegroundColor Yellow
    Write-Host "  Creating DLLs directory..." -ForegroundColor Gray
    New-Item -ItemType Directory -Path $dllsDir -Force | Out-Null
    Write-Host "  ✅ DLLs directory created" -ForegroundColor Green
    Write-Host "  ⚠️  WARNING: DLLs directory is empty! _socket.pyd and other modules are missing!" -ForegroundColor Red
    Write-Host "  💡 You need to copy DLLs directory from a complete Python installation" -ForegroundColor Yellow
} else {
    Write-Host "  ✅ DLLs directory exists" -ForegroundColor Green
    $dllCount = (Get-ChildItem -Path $dllsDir -Filter "*.pyd" -ErrorAction SilentlyContinue).Count
    Write-Host "  Found $dllCount .pyd files" -ForegroundColor Gray
    
    # Check specifically for _socket.pyd
    $socketPyd = Join-Path $dllsDir "_socket.pyd"
    if (Test-Path $socketPyd) {
        Write-Host "  ✅ _socket.pyd found" -ForegroundColor Green
    } else {
        Write-Host "  ❌ _socket.pyd NOT found!" -ForegroundColor Red
        Write-Host "  💡 This is required for pip to work. Please copy it from a complete Python installation." -ForegroundColor Yellow
    }
}

Write-Host ""

# Step 3: Test Python import
Write-Host "[3/3] Testing Python imports..." -ForegroundColor Yellow
Write-Host ""

$testImports = @(
    @{Name="_socket"; Critical=$true},
    @{Name="socket"; Critical=$true},
    @{Name="sys"; Critical=$true},
    @{Name="os"; Critical=$true}
)

$allPassed = $true
foreach ($test in $testImports) {
    Write-Host "  Testing: import $($test.Name)..." -NoNewline
    try {
        $output = & $pythonExe -c "import $($test.Name)" 2>&1
        if ($LASTEXITCODE -eq 0) {
            Write-Host " ✅" -ForegroundColor Green
        } else {
            Write-Host " ❌" -ForegroundColor Red
            if ($test.Critical) {
                $allPassed = $false
            }
            if ($output) {
                Write-Host "    Error: $output" -ForegroundColor DarkGray
            }
        }
    } catch {
        Write-Host " ❌" -ForegroundColor Red
        if ($test.Critical) {
            $allPassed = $false
        }
        Write-Host "    Exception: $_" -ForegroundColor DarkGray
    }
}

Write-Host ""

if (-not $allPassed) {
    Write-Host "❌ Critical imports failed!" -ForegroundColor Red
    Write-Host ""
    Write-Host "💡 Possible solutions:" -ForegroundColor Yellow
    Write-Host "  1. Re-run setup_embedded_python.ps1 to reinstall Python" -ForegroundColor Cyan
    Write-Host "  2. Check if DLLs directory contains _socket.pyd" -ForegroundColor Cyan
    Write-Host "  3. Verify Python version compatibility" -ForegroundColor Cyan
    exit 1
}

Write-Host "✅ All critical imports passed!" -ForegroundColor Green
Write-Host ""
Write-Host "============================================================================" -ForegroundColor Cyan
Write-Host "✅ Configuration fix completed!" -ForegroundColor Green
Write-Host "============================================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "💡 Now you can try installing dependencies again:" -ForegroundColor Yellow
Write-Host "  .\vendors\python\python.exe -m pip install -r requirements.txt -i https://mirrors.aliyun.com/pypi/simple/ --trusted-host mirrors.aliyun.com" -ForegroundColor Cyan
Write-Host ""

exit 0
