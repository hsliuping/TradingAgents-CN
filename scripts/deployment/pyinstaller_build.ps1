# ============================================================================
# PyInstaller Build Script
# ============================================================================
# 使用 PyInstaller 将整个应用打包为可执行文件
# 
# 优点：
# - 最简单的保护方案
# - 用户无需安装 Python
# - 所有代码都被打包（包括 core/）
# 
# 缺点：
# - 打包文件较大
# - 启动速度稍慢
# - 需要为每个平台单独打包
# ============================================================================

param(
    [string]$OutputDir = "",
    [switch]$OneFile = $false,
    [switch]$Console = $true
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)

Write-Host "============================================================================" -ForegroundColor Cyan
Write-Host "  PyInstaller Build" -ForegroundColor Cyan
Write-Host "============================================================================" -ForegroundColor Cyan
Write-Host ""

# ============================================================================
# 检查依赖
# ============================================================================

Write-Host "Checking dependencies..." -ForegroundColor Yellow
Write-Host ""

try {
    $pyinstallerVersion = & python -c "import PyInstaller; print(PyInstaller.__version__)" 2>&1
    Write-Host "  ✅ PyInstaller: $pyinstallerVersion" -ForegroundColor Green
} catch {
    Write-Host "  ❌ PyInstaller not installed" -ForegroundColor Red
    Write-Host ""
    Write-Host "Install PyInstaller:" -ForegroundColor Yellow
    Write-Host "  pip install pyinstaller" -ForegroundColor Gray
    exit 1
}

Write-Host ""

# ============================================================================
# 设置路径
# ============================================================================

if (-not $OutputDir) {
    $OutputDir = Join-Path $root "release\pyinstaller-build"
}

$specFile = Join-Path $root "tradingagents.spec"

Write-Host "Output: $OutputDir" -ForegroundColor Green
Write-Host ""

# ============================================================================
# 创建 .spec 文件
# ============================================================================

Write-Host "Creating .spec file..." -ForegroundColor Yellow
Write-Host ""

$specContent = @"
# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['start_api.py'],
    pathex=['$($root -replace '\\', '/')'],
    binaries=[],
    datas=[
        ('config', 'config'),
        ('prompts', 'prompts'),
        ('web/templates', 'web/templates'),
        ('web/static', 'web/static'),
        ('frontend/dist', 'frontend/dist'),
    ],
    hiddenimports=[
        'core',
        'core.agents',
        'core.workflow',
        'core.llm',
        'core.licensing',
        'tradingagents',
        'app',
        'uvicorn',
        'fastapi',
        'pydantic',
        'sqlalchemy',
        'motor',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    $(if ($OneFile) { "a.binaries," } else { "" })
    $(if ($OneFile) { "a.zipfiles," } else { "" })
    $(if ($OneFile) { "a.datas," } else { "" })
    [],
    name='TradingAgentsCN',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=$($Console.ToString().ToLower()),
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

$(if (-not $OneFile) {
@"
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='TradingAgentsCN',
)
"@
})
"@

$specContent | Set-Content $specFile -Encoding UTF8

Write-Host "  ✅ .spec file created" -ForegroundColor Green
Write-Host ""

# ============================================================================
# 构建
# ============================================================================

Write-Host "Building with PyInstaller..." -ForegroundColor Yellow
Write-Host ""
Write-Host "  ⚠️  This may take several minutes..." -ForegroundColor Yellow
Write-Host ""

$buildArgs = @(
    "-m", "PyInstaller",
    "--clean",
    "--distpath", $OutputDir,
    $specFile
)

$buildProcess = Start-Process -FilePath "python" -ArgumentList $buildArgs -Wait -PassThru -NoNewWindow

if ($buildProcess.ExitCode -ne 0) {
    Write-Host "ERROR: PyInstaller build failed" -ForegroundColor Red
    exit 1
}

Write-Host "  ✅ Build completed" -ForegroundColor Green
Write-Host ""

# ============================================================================
# 总结
# ============================================================================

Write-Host "============================================================================" -ForegroundColor Green
Write-Host "  Build Completed!" -ForegroundColor Green
Write-Host "============================================================================" -ForegroundColor Green
Write-Host ""
Write-Host "Output directory: $OutputDir" -ForegroundColor Cyan
Write-Host ""

if ($OneFile) {
    Write-Host "Executable: $OutputDir\TradingAgentsCN.exe" -ForegroundColor Cyan
} else {
    Write-Host "Application folder: $OutputDir\TradingAgentsCN\" -ForegroundColor Cyan
}

Write-Host ""
Write-Host "Next steps:" -ForegroundColor White
Write-Host "  1. Test the executable" -ForegroundColor Gray
Write-Host "  2. Package for distribution" -ForegroundColor Gray
Write-Host ""

