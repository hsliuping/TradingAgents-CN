# ============================================================================
# Verify Python DLLs
# ============================================================================
# 快速验证 Python DLLs 是否完整
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
$dllsDir = Join-Path $pythonDir "DLLs"

Write-Host "============================================================================" -ForegroundColor Cyan
Write-Host "  Verify Python DLLs" -ForegroundColor Cyan
Write-Host "============================================================================" -ForegroundColor Cyan
Write-Host ""

# Check Python executable
if (-not (Test-Path $pythonExe)) {
    Write-Host "❌ Python executable not found: $pythonExe" -ForegroundColor Red
    exit 1
}
Write-Host "✅ Python executable: $pythonExe" -ForegroundColor Green

# Check DLLs directory
if (-not (Test-Path $dllsDir)) {
    Write-Host "❌ DLLs directory not found: $dllsDir" -ForegroundColor Red
    exit 1
}
Write-Host "✅ DLLs directory: $dllsDir" -ForegroundColor Green

# Check _socket.pyd
$socketPyd = Join-Path $dllsDir "_socket.pyd"
if (-not (Test-Path $socketPyd)) {
    Write-Host "❌ _socket.pyd NOT found!" -ForegroundColor Red
    exit 1
}
Write-Host "✅ _socket.pyd found" -ForegroundColor Green

# Count .pyd files
$pydFiles = Get-ChildItem -Path $dllsDir -Filter "*.pyd" -ErrorAction SilentlyContinue
$pydCount = $pydFiles.Count
Write-Host "✅ Found $pydCount .pyd files" -ForegroundColor Green

# Test critical imports
Write-Host ""
Write-Host "Testing critical imports..." -ForegroundColor Yellow

$testImports = @(
    @{Name="_socket"; Critical=$true},
    @{Name="socket"; Critical=$true},
    @{Name="pip"; Critical=$true}
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

if ($allPassed) {
    Write-Host "============================================================================" -ForegroundColor Cyan
    Write-Host "✅ All checks passed! Python DLLs are OK." -ForegroundColor Green
    Write-Host "============================================================================" -ForegroundColor Cyan
    exit 0
} else {
    Write-Host "============================================================================" -ForegroundColor Cyan
    Write-Host "❌ Some checks failed!" -ForegroundColor Red
    Write-Host "============================================================================" -ForegroundColor Cyan
    exit 1
}
