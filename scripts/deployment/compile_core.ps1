# ============================================================================
# Compile Core Module to Bytecode
# ============================================================================
# 将 core/ 目录编译为字节码，保护源代码
# 
# 功能：
# 1. 编译所有 .py 文件为 .pyc
# 2. 删除原始 .py 文件（保留 __init__.py）
# 3. 优化字节码（-OO 模式，移除文档字符串和断言）
# ============================================================================

param(
    [string]$SourceDir = "",
    [string]$OutputDir = "",
    [switch]$KeepSource = $false,
    [switch]$OptimizeLevel2 = $true
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)

Write-Host "============================================================================" -ForegroundColor Cyan
Write-Host "  Compile Core Module to Bytecode" -ForegroundColor Cyan
Write-Host "============================================================================" -ForegroundColor Cyan
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
# 步骤1：复制源码到输出目录
# ============================================================================

Write-Host "[1/4] Copying source files..." -ForegroundColor Yellow
Write-Host ""

if (Test-Path $OutputDir) {
    Remove-Item -Path $OutputDir -Recurse -Force
}

Copy-Item -Path $SourceDir -Destination $OutputDir -Recurse -Force
Write-Host "  ✅ Source files copied" -ForegroundColor Green
Write-Host ""

# ============================================================================
# 步骤2：编译为字节码
# ============================================================================

Write-Host "[2/4] Compiling to bytecode..." -ForegroundColor Yellow
Write-Host ""

$pythonExe = "python"

# 检查 Python 是否可用
try {
    $pythonVersion = & $pythonExe --version 2>&1
    Write-Host "  Using: $pythonVersion" -ForegroundColor Gray
} catch {
    Write-Host "ERROR: Python not found in PATH" -ForegroundColor Red
    exit 1
}

# 编译选项
$compileArgs = @(
    "-m", "compileall",
    "-b",  # 生成 .pyc 文件
    $OutputDir
)

if ($OptimizeLevel2) {
    # -OO: 移除文档字符串和断言，进一步保护代码
    $compileArgs = @("-OO") + $compileArgs
    Write-Host "  Optimization: Level 2 (-OO, remove docstrings)" -ForegroundColor Gray
} else {
    Write-Host "  Optimization: Level 0 (keep docstrings)" -ForegroundColor Gray
}

Write-Host "  Compiling..." -ForegroundColor Gray
$compileProcess = Start-Process -FilePath $pythonExe -ArgumentList $compileArgs -Wait -PassThru -NoNewWindow

if ($compileProcess.ExitCode -ne 0) {
    Write-Host "ERROR: Compilation failed" -ForegroundColor Red
    exit 1
}

Write-Host "  ✅ Compilation completed" -ForegroundColor Green
Write-Host ""

# ============================================================================
# 步骤3：移动 .pyc 文件到正确位置
# ============================================================================

Write-Host "[3/4] Organizing bytecode files..." -ForegroundColor Yellow
Write-Host ""

# Python 3.8+ 会将 .pyc 文件放在 __pycache__ 目录中
# 我们需要将它们移动到与 .py 文件相同的目录

Get-ChildItem -Path $OutputDir -Recurse -Directory -Filter "__pycache__" | ForEach-Object {
    $pycacheDir = $_.FullName
    $parentDir = Split-Path -Parent $pycacheDir

    Get-ChildItem -Path $pycacheDir -Filter "*.pyc" | ForEach-Object {
        $pycFile = $_.FullName
        $fileName = $_.Name

        # 提取原始文件名（去掉 .cpython-310.pyc 后缀）
        if ($fileName -match "^(.+)\.cpython-\d+\.pyc$") {
            $baseName = $matches[1]
            $newName = "$baseName.pyc"
            $destPath = Join-Path $parentDir $newName

            Move-Item -Path $pycFile -Destination $destPath -Force
            Write-Host "  Moved: $newName" -ForegroundColor Gray
        }
    }

    # 删除空的 __pycache__ 目录
    Remove-Item -Path $pycacheDir -Force -ErrorAction SilentlyContinue
}

Write-Host "  ✅ Bytecode files organized" -ForegroundColor Green
Write-Host ""

# ============================================================================
# 步骤4：删除源码文件（可选）
# ============================================================================

Write-Host "[4/4] Cleaning up source files..." -ForegroundColor Yellow
Write-Host ""

if ($KeepSource) {
    Write-Host "  ⚠️  Keeping source files (--KeepSource)" -ForegroundColor Yellow
} else {
    $deleteCount = 0

    Get-ChildItem -Path $OutputDir -Recurse -Filter "*.py" | ForEach-Object {
        $pyFile = $_.FullName
        $fileName = $_.Name

        # 保留 __init__.py（需要用于包导入）
        if ($fileName -eq "__init__.py") {
            # 但是清空内容，只保留基本导入
            $content = Get-Content $pyFile -Raw
            if ($content -match "^__all__\s*=") {
                # 保留 __all__ 定义
                $content -replace "(?s)^(.*?__all__\s*=\s*\[.*?\]).*", '$1' | Set-Content $pyFile
            } else {
                # 清空文件
                "" | Set-Content $pyFile
            }
            Write-Host "  Cleaned: $fileName" -ForegroundColor Gray
        } else {
            # 删除其他 .py 文件
            Remove-Item -Path $pyFile -Force
            $deleteCount++
        }
    }

    Write-Host "  ✅ Deleted $deleteCount source files" -ForegroundColor Green
}

Write-Host ""

# ============================================================================
# 总结
# ============================================================================

Write-Host "============================================================================" -ForegroundColor Green
Write-Host "  Compilation Completed!" -ForegroundColor Green
Write-Host "============================================================================" -ForegroundColor Green
Write-Host ""
Write-Host "Output directory: $OutputDir" -ForegroundColor Cyan
Write-Host ""
Write-Host "Next steps:" -ForegroundColor White
Write-Host "  1. Test the compiled module: python -c 'import core; print(core.__version__)'" -ForegroundColor Gray
Write-Host "  2. Package the release: .\scripts\deployment\build_pro_package.ps1" -ForegroundColor Gray
Write-Host ""

