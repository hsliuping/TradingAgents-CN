# ============================================================================
# Test Compilation Results
# ============================================================================
# 测试编译结果脚本
#
# 功能：
# 1. 测试core模块导入
# 2. 测试许可证管理器
# 3. 测试验证器
# 4. 检查编译产物
# ============================================================================

param(
    [string]$PortableDir = ""
)

# 设置控制台和文件编码为UTF-8
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
[Console]::InputEncoding = [System.Text.Encoding]::UTF8
$PSDefaultParameterValues['*:Encoding'] = 'utf8'
$OutputEncoding = [System.Text.Encoding]::UTF8

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)

if (-not $PortableDir) {
    $PortableDir = Join-Path $root "release\TradingAgentsCN-portable"
}

Write-Host "============================================================================" -ForegroundColor Cyan
Write-Host "  Testing Compilation Results" -ForegroundColor Cyan
Write-Host "============================================================================" -ForegroundColor Cyan
Write-Host ""

# ============================================================================
# 检查编译产物
# ============================================================================

Write-Host "[1/4] Checking compiled files..." -ForegroundColor Yellow
Write-Host ""

$licensingDir = Join-Path $PortableDir "core\licensing"

if (-not (Test-Path $licensingDir)) {
    Write-Host "ERROR: Licensing directory not found: $licensingDir" -ForegroundColor Red
    exit 1
}

Write-Host "Licensing directory contents:" -ForegroundColor Gray
Get-ChildItem -Path $licensingDir -Recurse | ForEach-Object {
    $relativePath = $_.FullName.Substring($licensingDir.Length + 1)
    $type = if ($_.PSIsContainer) { "[DIR]" } else { "[FILE]" }
    $size = if (-not $_.PSIsContainer) { " ($([math]::Round($_.Length / 1KB, 2)) KB)" } else { "" }
    
    if ($_.Extension -in @(".pyd", ".so")) {
        Write-Host "  ✅ $type $relativePath$size" -ForegroundColor Green
    } elseif ($_.Extension -eq ".pyc") {
        Write-Host "  📦 $type $relativePath$size" -ForegroundColor Cyan
    } elseif ($_.Extension -eq ".py") {
        Write-Host "  📄 $type $relativePath$size" -ForegroundColor Gray
    } else {
        Write-Host "  $type $relativePath$size" -ForegroundColor Gray
    }
}

Write-Host ""

# 检查是否有Cython编译产物
$pydFiles = Get-ChildItem -Path $licensingDir -Filter "*.pyd" -Recurse
$soFiles = Get-ChildItem -Path $licensingDir -Filter "*.so" -Recurse

if ($pydFiles.Count -gt 0 -or $soFiles.Count -gt 0) {
    Write-Host "✅ Found Cython compiled files:" -ForegroundColor Green
    $pydFiles | ForEach-Object { Write-Host "  - $($_.Name)" -ForegroundColor Green }
    $soFiles | ForEach-Object { Write-Host "  - $($_.Name)" -ForegroundColor Green }
} else {
    Write-Host "⚠️  No Cython compiled files found (.pyd/.so)" -ForegroundColor Yellow
    Write-Host "Checking for bytecode files..." -ForegroundColor Gray
    
    $pycFiles = Get-ChildItem -Path $licensingDir -Filter "*.pyc" -Recurse
    if ($pycFiles.Count -gt 0) {
        Write-Host "📦 Found bytecode files:" -ForegroundColor Cyan
        $pycFiles | ForEach-Object { Write-Host "  - $($_.Name)" -ForegroundColor Cyan }
    } else {
        Write-Host "❌ No compiled files found!" -ForegroundColor Red
    }
}

Write-Host ""

# ============================================================================
# 测试Python导入
# ============================================================================

Write-Host "[2/4] Testing Python imports..." -ForegroundColor Yellow
Write-Host ""

# 切换到portable目录
Push-Location $PortableDir

try {
    # 测试1: 导入core模块
    Write-Host "Test 1: Import core module..." -ForegroundColor Gray
    $result = & python -c "import sys; sys.path.insert(0, '.'); import core; print(f'✅ core version: {core.__version__}')" 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  $result" -ForegroundColor Green
    } else {
        Write-Host "  ❌ Failed: $result" -ForegroundColor Red
    }
    Write-Host ""

    # 测试2: 导入许可证管理器
    Write-Host "Test 2: Import LicenseManager..." -ForegroundColor Gray
    $result = & python -c "import sys; sys.path.insert(0, '.'); from core.licensing import LicenseManager; m = LicenseManager(); print(f'✅ LicenseManager tier: {m.tier}')" 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  $result" -ForegroundColor Green
    } else {
        Write-Host "  ❌ Failed: $result" -ForegroundColor Red
    }
    Write-Host ""

    # 测试3: 导入验证器
    Write-Host "Test 3: Import LicenseValidator..." -ForegroundColor Gray
    $result = & python -c "import sys; sys.path.insert(0, '.'); from core.licensing.validator import LicenseValidator; v = LicenseValidator(offline_mode=True); print('✅ LicenseValidator created')" 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  $result" -ForegroundColor Green
    } else {
        Write-Host "  ❌ Failed: $result" -ForegroundColor Red
    }
    Write-Host ""

    # 测试4: 测试功能门控
    Write-Host "Test 4: Import require_feature..." -ForegroundColor Gray
    $result = & python -c "import sys; sys.path.insert(0, '.'); from core.licensing import require_feature; print('✅ require_feature imported')" 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  $result" -ForegroundColor Green
    } else {
        Write-Host "  ❌ Failed: $result" -ForegroundColor Red
    }
    Write-Host ""

} finally {
    Pop-Location
}

# ============================================================================
# 测试许可证验证
# ============================================================================

Write-Host "[3/4] Testing license validation..." -ForegroundColor Yellow
Write-Host ""

Push-Location $PortableDir

try {
    # 创建测试脚本
    $testScript = @"
import sys
sys.path.insert(0, '.')

from core.licensing.validator import LicenseValidator

# 测试离线验证
validator = LicenseValidator(offline_mode=True)

# 测试无效许可证
is_valid, license_obj, error = validator.validate_offline("invalid-key")
print(f"Invalid key test: valid={is_valid}, error={error}")

# 测试格式错误
is_valid, license_obj, error = validator.validate_offline("pro")
print(f"Format error test: valid={is_valid}, error={error}")

print("✅ License validation tests completed")
"@

    $testScript | Set-Content "test_license.py" -Encoding UTF8
    
    $result = & python test_license.py 2>&1
    Write-Host $result -ForegroundColor Gray
    
    Remove-Item "test_license.py" -Force -ErrorAction SilentlyContinue
    
} finally {
    Pop-Location
}

Write-Host ""

# ============================================================================
# 总结
# ============================================================================

Write-Host "[4/4] Summary" -ForegroundColor Yellow
Write-Host ""

Write-Host "============================================================================" -ForegroundColor Green
Write-Host "  Test Completed!" -ForegroundColor Green
Write-Host "============================================================================" -ForegroundColor Green
Write-Host ""
Write-Host "Next steps:" -ForegroundColor White
Write-Host "  1. If all tests passed, the compilation is successful" -ForegroundColor Gray
Write-Host "  2. Run the full package build: .\scripts\deployment\build_pro_package.ps1" -ForegroundColor Gray
Write-Host "  3. Test the packaged application" -ForegroundColor Gray
Write-Host ""

