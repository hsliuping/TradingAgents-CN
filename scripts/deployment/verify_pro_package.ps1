# ============================================================================
# Verify Pro Package
# ============================================================================
# 验证Pro版打包是否正确排除了课程源码和敏感内容
# ============================================================================

param(
    [string]$PackagePath = "",
    [string]$ExtractPath = ""
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)

Write-Host "============================================================================" -ForegroundColor Cyan
Write-Host "  Verify Pro Package" -ForegroundColor Cyan
Write-Host "============================================================================" -ForegroundColor Cyan
Write-Host ""

# ============================================================================
# Find package file
# ============================================================================

if (-not $PackagePath) {
    $packagesDir = Join-Path $root "release\packages"
    if (Test-Path $packagesDir) {
        $latestPackage = Get-ChildItem -Path $packagesDir -Filter "TradingAgentsCN-Portable-*.zip" | 
                         Sort-Object LastWriteTime -Descending | 
                         Select-Object -First 1
        
        if ($latestPackage) {
            $PackagePath = $latestPackage.FullName
            Write-Host "Found latest package: $($latestPackage.Name)" -ForegroundColor Green
        } else {
            Write-Host "ERROR: No package found in $packagesDir" -ForegroundColor Red
            exit 1
        }
    } else {
        Write-Host "ERROR: Packages directory not found: $packagesDir" -ForegroundColor Red
        exit 1
    }
}

if (-not (Test-Path $PackagePath)) {
    Write-Host "ERROR: Package not found: $PackagePath" -ForegroundColor Red
    exit 1
}

Write-Host "Package: $PackagePath" -ForegroundColor Cyan
Write-Host ""

# ============================================================================
# Extract package
# ============================================================================

if (-not $ExtractPath) {
    $ExtractPath = Join-Path $env:TEMP "TradingAgentsCN-Verify-$(Get-Date -Format 'yyyyMMdd-HHmmss')"
}

Write-Host "Extracting to: $ExtractPath" -ForegroundColor Cyan
Write-Host ""

try {
    Expand-Archive -Path $PackagePath -DestinationPath $ExtractPath -Force
    Write-Host "✅ Package extracted" -ForegroundColor Green
} catch {
    Write-Host "ERROR: Failed to extract package: $_" -ForegroundColor Red
    exit 1
}

Write-Host ""

# ============================================================================
# Verification checks
# ============================================================================

$issues = @()
$warnings = @()
$passed = @()

Write-Host "Running verification checks..." -ForegroundColor Yellow
Write-Host ""

# Check 1: 课程扩写内容不应该存在
Write-Host "[1/6] Checking course expanded content..." -ForegroundColor Cyan
$expandedDir = Join-Path $ExtractPath "docs\courses\advanced\expanded"
if (Test-Path $expandedDir) {
    $issues += "❌ FAIL: Course expanded content found (should be excluded)"
    Write-Host "  ❌ FAIL: Found expanded/ directory" -ForegroundColor Red
} else {
    $passed += "✅ PASS: Course expanded content excluded"
    Write-Host "  ✅ PASS: No expanded/ directory" -ForegroundColor Green
}

# Check 2: PPT源文件不应该存在
Write-Host "[2/6] Checking PPT source files..." -ForegroundColor Cyan
$pptDir = Join-Path $ExtractPath "docs\courses\advanced\ppt"
if (Test-Path $pptDir) {
    $issues += "❌ FAIL: PPT source files found (should be excluded)"
    Write-Host "  ❌ FAIL: Found ppt/ directory" -ForegroundColor Red
} else {
    $passed += "✅ PASS: PPT source files excluded"
    Write-Host "  ✅ PASS: No ppt/ directory" -ForegroundColor Green
}

# Check 3: 设计文档不应该存在
Write-Host "[3/6] Checking design documents..." -ForegroundColor Cyan
$designDir = Join-Path $ExtractPath "docs\design"
if (Test-Path $designDir) {
    $issues += "❌ FAIL: Design documents found (should be excluded)"
    Write-Host "  ❌ FAIL: Found design/ directory" -ForegroundColor Red
} else {
    $passed += "✅ PASS: Design documents excluded"
    Write-Host "  ✅ PASS: No design/ directory" -ForegroundColor Green
}

# Check 4: 课程README应该存在
Write-Host "[4/6] Checking course README..." -ForegroundColor Cyan
$courseReadme = Join-Path $ExtractPath "docs\courses\advanced\README.md"
if (Test-Path $courseReadme) {
    $passed += "✅ PASS: Course README exists"
    Write-Host "  ✅ PASS: Course README found" -ForegroundColor Green
} else {
    $warnings += "⚠️  WARNING: Course README not found"
    Write-Host "  ⚠️  WARNING: Course README not found" -ForegroundColor Yellow
}

# Check 5: 核心代码应该存在
Write-Host "[5/6] Checking core code..." -ForegroundColor Cyan
$coreFiles = @(
    "app\main.py",
    "tradingagents\__init__.py",
    "requirements.txt"
)

$missingCore = @()
foreach ($file in $coreFiles) {
    $filePath = Join-Path $ExtractPath $file
    if (-not (Test-Path $filePath)) {
        $missingCore += $file
    }
}

if ($missingCore.Count -gt 0) {
    $issues += "❌ FAIL: Missing core files: $($missingCore -join ', ')"
    Write-Host "  ❌ FAIL: Missing core files" -ForegroundColor Red
} else {
    $passed += "✅ PASS: Core files present"
    Write-Host "  ✅ PASS: All core files present" -ForegroundColor Green
}

# Check 6: 前端dist应该存在
Write-Host "[6/6] Checking frontend dist..." -ForegroundColor Cyan
$frontendDist = Join-Path $ExtractPath "frontend\dist"
if (Test-Path $frontendDist) {
    $passed += "✅ PASS: Frontend dist exists"
    Write-Host "  ✅ PASS: Frontend dist found" -ForegroundColor Green
} else {
    $warnings += "⚠️  WARNING: Frontend dist not found"
    Write-Host "  ⚠️  WARNING: Frontend dist not found" -ForegroundColor Yellow
}

Write-Host ""

# ============================================================================
# Summary
# ============================================================================

Write-Host "============================================================================" -ForegroundColor Cyan
Write-Host "  Verification Summary" -ForegroundColor Cyan
Write-Host "============================================================================" -ForegroundColor Cyan
Write-Host ""

Write-Host "Passed: $($passed.Count)" -ForegroundColor Green
foreach ($item in $passed) {
    Write-Host "  $item" -ForegroundColor Green
}
Write-Host ""

if ($warnings.Count -gt 0) {
    Write-Host "Warnings: $($warnings.Count)" -ForegroundColor Yellow
    foreach ($item in $warnings) {
        Write-Host "  $item" -ForegroundColor Yellow
    }
    Write-Host ""
}

if ($issues.Count -gt 0) {
    Write-Host "Issues: $($issues.Count)" -ForegroundColor Red
    foreach ($item in $issues) {
        Write-Host "  $item" -ForegroundColor Red
    }
    Write-Host ""
    Write-Host "❌ VERIFICATION FAILED" -ForegroundColor Red
    Write-Host ""
    Write-Host "Please fix the issues and rebuild the package" -ForegroundColor Yellow
    exit 1
} else {
    Write-Host "✅ VERIFICATION PASSED" -ForegroundColor Green
    Write-Host ""
    Write-Host "Package is ready for distribution" -ForegroundColor Cyan
}

Write-Host ""
Write-Host "Extracted files location: $ExtractPath" -ForegroundColor Gray
Write-Host ""

