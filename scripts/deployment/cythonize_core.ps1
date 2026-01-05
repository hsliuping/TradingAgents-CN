# ============================================================================
# Cythonize Core Module
# ============================================================================
# 使用 Cython 将 core/ 目录编译为 C 扩展（.pyd/.so）
# 
# 优点：
# - 更难反编译（编译为机器码）
# - 性能提升
# - 更好的保护
# 
# 缺点：
# - 需要为每个平台单独编译
# - 编译时间较长
# - 需要安装 Cython 和 C 编译器
# ============================================================================

param(
    [string]$SourceDir = "",
    [string]$OutputDir = "",
    [switch]$SkipCleanup = $false
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)

Write-Host "============================================================================" -ForegroundColor Cyan
Write-Host "  Cythonize Core Module" -ForegroundColor Cyan
Write-Host "============================================================================" -ForegroundColor Cyan
Write-Host ""

# ============================================================================
# 检查依赖
# ============================================================================

Write-Host "Checking dependencies..." -ForegroundColor Yellow
Write-Host ""

# 检查 Python
try {
    $pythonVersion = & python --version 2>&1
    Write-Host "  ✅ Python: $pythonVersion" -ForegroundColor Green
} catch {
    Write-Host "  ❌ Python not found" -ForegroundColor Red
    exit 1
}

# 检查 Cython
try {
    $cythonVersion = & python -c "import Cython; print(Cython.__version__)" 2>&1
    Write-Host "  ✅ Cython: $cythonVersion" -ForegroundColor Green
} catch {
    Write-Host "  ❌ Cython not installed" -ForegroundColor Red
    Write-Host ""
    Write-Host "Install Cython:" -ForegroundColor Yellow
    Write-Host "  pip install Cython" -ForegroundColor Gray
    exit 1
}

# 检查 C 编译器（Windows 上需要 Visual Studio Build Tools）
try {
    $clVersion = & cl 2>&1 | Select-String "Microsoft"
    Write-Host "  ✅ C Compiler: $clVersion" -ForegroundColor Green
} catch {
    Write-Host "  ⚠️  C Compiler not found (may need Visual Studio Build Tools)" -ForegroundColor Yellow
}

Write-Host ""

# ============================================================================
# 设置路径
# ============================================================================

if (-not $SourceDir) {
    $SourceDir = Join-Path $root "core"
}

if (-not $OutputDir) {
    $OutputDir = Join-Path $root "release\TradingAgentsCN-portable\core"
}

if (-not (Test-Path $SourceDir)) {
    Write-Host "ERROR: Source directory not found: $SourceDir" -ForegroundColor Red
    exit 1
}

Write-Host "Source: $SourceDir" -ForegroundColor Green
Write-Host "Output: $OutputDir" -ForegroundColor Green
Write-Host ""

# ============================================================================
# 创建 setup.py
# ============================================================================

Write-Host "Creating setup.py..." -ForegroundColor Yellow
Write-Host ""

$setupPy = @"
from setuptools import setup, Extension
from Cython.Build import cythonize
import os
import glob

# 查找所有 .py 文件（排除 __init__.py）
py_files = []
for root, dirs, files in os.walk("$($SourceDir -replace '\\', '/')"):
    for file in files:
        if file.endswith('.py') and file != '__init__.py':
            py_files.append(os.path.join(root, file))

# 创建扩展模块
extensions = []
for py_file in py_files:
    # 计算模块名
    rel_path = os.path.relpath(py_file, "$($SourceDir -replace '\\', '/')")
    module_name = rel_path.replace(os.sep, '.').replace('.py', '')
    module_name = 'core.' + module_name
    
    extensions.append(Extension(
        module_name,
        [py_file],
        extra_compile_args=['/O2'] if os.name == 'nt' else ['-O3'],
    ))

setup(
    name='tradingagents-core',
    ext_modules=cythonize(
        extensions,
        compiler_directives={
            'language_level': '3',
            'embedsignature': False,  # 不嵌入签名（减小体积）
            'boundscheck': False,     # 禁用边界检查（提升性能）
            'wraparound': False,      # 禁用负索引（提升性能）
        },
        build_dir='build',
    ),
)
"@

$setupPath = Join-Path $root "setup_cython.py"
$setupPy | Set-Content $setupPath -Encoding UTF8

Write-Host "  ✅ setup.py created" -ForegroundColor Green
Write-Host ""

# ============================================================================
# 编译
# ============================================================================

Write-Host "Compiling with Cython..." -ForegroundColor Yellow
Write-Host ""
Write-Host "  ⚠️  This may take several minutes..." -ForegroundColor Yellow
Write-Host ""

$buildProcess = Start-Process -FilePath "python" -ArgumentList @(
    $setupPath,
    "build_ext",
    "--inplace"
) -Wait -PassThru -NoNewWindow

if ($buildProcess.ExitCode -ne 0) {
    Write-Host "ERROR: Cython compilation failed" -ForegroundColor Red
    exit 1
}

Write-Host "  ✅ Compilation completed" -ForegroundColor Green
Write-Host ""

# ============================================================================
# 复制编译后的文件
# ============================================================================

Write-Host "Copying compiled files..." -ForegroundColor Yellow
Write-Host ""

if (Test-Path $OutputDir) {
    Remove-Item -Path $OutputDir -Recurse -Force
}

New-Item -ItemType Directory -Path $OutputDir -Force | Out-Null

# 复制 .pyd/.so 文件
Get-ChildItem -Path $SourceDir -Recurse -Include "*.pyd", "*.so" | ForEach-Object {
    $relativePath = $_.FullName.Substring($SourceDir.Length + 1)
    $destPath = Join-Path $OutputDir $relativePath
    $destDir = Split-Path -Parent $destPath

    if (-not (Test-Path $destDir)) {
        New-Item -ItemType Directory -Path $destDir -Force | Out-Null
    }

    Copy-Item -Path $_.FullName -Destination $destPath -Force
    Write-Host "  Copied: $relativePath" -ForegroundColor Gray
}

# 复制 __init__.py 文件（必需）
Get-ChildItem -Path $SourceDir -Recurse -Filter "__init__.py" | ForEach-Object {
    $relativePath = $_.FullName.Substring($SourceDir.Length + 1)
    $destPath = Join-Path $OutputDir $relativePath
    $destDir = Split-Path -Parent $destPath

    if (-not (Test-Path $destDir)) {
        New-Item -ItemType Directory -Path $destDir -Force | Out-Null
    }

    Copy-Item -Path $_.FullName -Destination $destPath -Force
}

Write-Host "  ✅ Files copied" -ForegroundColor Green
Write-Host ""

# ============================================================================
# 清理
# ============================================================================

if (-not $SkipCleanup) {
    Write-Host "Cleaning up..." -ForegroundColor Yellow
    Write-Host ""

    Remove-Item -Path $setupPath -Force -ErrorAction SilentlyContinue
    Remove-Item -Path (Join-Path $root "build") -Recurse -Force -ErrorAction SilentlyContinue

    # 删除源码目录中的编译产物
    Get-ChildItem -Path $SourceDir -Recurse -Include "*.pyd", "*.so", "*.c" | Remove-Item -Force

    Write-Host "  ✅ Cleanup completed" -ForegroundColor Green
}

Write-Host ""

# ============================================================================
# 总结
# ============================================================================

Write-Host "============================================================================" -ForegroundColor Green
Write-Host "  Cythonization Completed!" -ForegroundColor Green
Write-Host "============================================================================" -ForegroundColor Green
Write-Host ""
Write-Host "Output directory: $OutputDir" -ForegroundColor Cyan
Write-Host ""
Write-Host "⚠️  Important:" -ForegroundColor Yellow
Write-Host "  - Compiled extensions are platform-specific" -ForegroundColor Gray
Write-Host "  - You need to compile separately for Windows/Linux/macOS" -ForegroundColor Gray
Write-Host ""

