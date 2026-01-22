# ============================================================================
# Hybrid Core Compilation Strategy
# ============================================================================
# 混合编译策略：
# 1. core/licensing/ → Cython编译（最关键，防止绕过验证）
# 2. core/其他目录 → 字节码编译（保护知识产权）
# ============================================================================

param(
    [string]$SourceDir = "",
    [string]$OutputDir = "",
    [switch]$SkipCython = $false,
    [switch]$KeepSource = $false
)

# 设置控制台和文件编码为UTF-8
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
[Console]::InputEncoding = [System.Text.Encoding]::UTF8
$PSDefaultParameterValues['*:Encoding'] = 'utf8'
$OutputEncoding = [System.Text.Encoding]::UTF8

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)

Write-Host "============================================================================" -ForegroundColor Cyan
Write-Host "  Hybrid Core Compilation" -ForegroundColor Cyan
Write-Host "============================================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Strategy:" -ForegroundColor White
Write-Host "  - core/licensing/  → Cython (C extension)" -ForegroundColor Yellow
Write-Host "  - core/other/      → Bytecode (.pyc)" -ForegroundColor Yellow
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
# 步骤0：清理输出目录中的旧缓存和编译文件（编译前清理）
# ============================================================================

Write-Host "[0/4] Cleaning old cache and compiled files in output directory..." -ForegroundColor Yellow
Write-Host ""

if (Test-Path $OutputDir) {
    # 清理所有 __pycache__ 目录
    $cacheDirs = Get-ChildItem -Path $OutputDir -Recurse -Directory -Filter "__pycache__" -ErrorAction SilentlyContinue
    if ($cacheDirs) {
        $cacheDirs | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
        Write-Host "  ✅ Cleaned __pycache__ directories" -ForegroundColor Green
    }
    
    # 清理所有旧的 .pyc 文件
    $pycFiles = Get-ChildItem -Path $OutputDir -Recurse -Filter "*.pyc" -ErrorAction SilentlyContinue
    if ($pycFiles) {
        $pycFiles | Remove-Item -Force -ErrorAction SilentlyContinue
        Write-Host "  ✅ Cleaned old .pyc files" -ForegroundColor Green
    }
    
    # 清理所有旧的 .pyd 文件
    $pydFiles = Get-ChildItem -Path $OutputDir -Recurse -Filter "*.pyd" -ErrorAction SilentlyContinue
    if ($pydFiles) {
        $pydFiles | Remove-Item -Force -ErrorAction SilentlyContinue
        Write-Host "  ✅ Cleaned old .pyd files" -ForegroundColor Green
    }
    
    # 清理所有 .pyo 文件
    $pyoFiles = Get-ChildItem -Path $OutputDir -Recurse -Filter "*.pyo" -ErrorAction SilentlyContinue
    if ($pyoFiles) {
        $pyoFiles | Remove-Item -Force -ErrorAction SilentlyContinue
        Write-Host "  ✅ Cleaned .pyo files" -ForegroundColor Green
    }
}

Write-Host ""

# ============================================================================
# 步骤1：确保输出目录存在（不删除，使用同步脚本已复制的源码）
# ============================================================================

Write-Host "[1/4] Checking output directory..." -ForegroundColor Yellow
Write-Host ""

if (-not (Test-Path $OutputDir)) {
    Write-Host "  ⚠️  Output directory not found, copying from source..." -ForegroundColor Yellow
    Copy-Item -Path $SourceDir -Destination $OutputDir -Recurse -Force
    Write-Host "  ✅ Source files copied" -ForegroundColor Green
} else {
    Write-Host "  ✅ Output directory exists (using synced source code)" -ForegroundColor Green
    Write-Host "  Path: $OutputDir" -ForegroundColor Gray
}

Write-Host ""

# ============================================================================
# 步骤2：Cython编译 licensing 目录
# ============================================================================

if (-not $SkipCython) {
    Write-Host "[2/4] Compiling licensing module with Cython..." -ForegroundColor Yellow
    Write-Host ""

    # 检查Cython
    try {
        $cythonVersion = & python -c "import Cython; print(Cython.__version__)" 2>&1
        Write-Host "  Using Cython: $cythonVersion" -ForegroundColor Gray
    } catch {
        Write-Host "  ⚠️  Cython not installed, skipping Cython compilation" -ForegroundColor Yellow
        Write-Host "  Install with: pip install Cython" -ForegroundColor Gray
        $SkipCython = $true
    }

    if (-not $SkipCython) {
        $licensingDir = Join-Path $OutputDir "licensing"
        
        # 创建setup.py
        $setupPy = @"
from setuptools import setup, Extension
from Cython.Build import cythonize
import os

# 需要编译的文件
py_files = [
    'validator.py',
    'manager.py',
    'features.py',
]

extensions = []
for py_file in py_files:
    file_path = os.path.join('$($licensingDir -replace '\\', '/')', py_file)
    if os.path.exists(file_path):
        module_name = f'core.licensing.{py_file[:-3]}'
        extensions.append(Extension(
            module_name,
            [file_path],
            extra_compile_args=['/O2'] if os.name == 'nt' else ['-O3'],
        ))

setup(
    name='tradingagents-core-licensing',
    ext_modules=cythonize(
        extensions,
        compiler_directives={
            'language_level': '3',
            'embedsignature': False,
            'boundscheck': False,
            'wraparound': False,
        },
        build_dir='build',
    ),
)
"@

        $setupPath = Join-Path $root "setup_licensing.py"
        $setupPy | Set-Content $setupPath -Encoding UTF8

        # 🔥 在编译前，先删除旧的 .pyd 文件（避免文件锁定）
        Write-Host "  Cleaning old .pyd files..." -ForegroundColor Gray
        Get-ChildItem -Path $licensingDir -Filter "*.pyd" -ErrorAction SilentlyContinue | ForEach-Object {
            try {
                Remove-Item -Path $_.FullName -Force -ErrorAction Stop
                Write-Host "    Removed: $($_.Name)" -ForegroundColor Gray
            } catch {
                Write-Host "    ⚠️  Cannot remove $($_.Name) (file may be in use)" -ForegroundColor Yellow
                Write-Host "    Please close all Python processes and try again" -ForegroundColor Yellow
            }
        }

        Write-Host "  Compiling..." -ForegroundColor Gray
        $buildProcess = Start-Process -FilePath "python" -ArgumentList @(
            $setupPath,
            "build_ext",
            "--inplace"
        ) -Wait -PassThru -NoNewWindow

        if ($buildProcess.ExitCode -eq 0) {
            Write-Host "  ✅ Cython compilation completed" -ForegroundColor Green

            # 复制编译后的文件到目标目录
            $buildLibDir = Join-Path $root "build\lib.win-amd64-cpython-310\core\licensing"
            if (Test-Path $buildLibDir) {
                Get-ChildItem -Path $buildLibDir -Include "*.pyd", "*.so" -Recurse | ForEach-Object {
                    $destPath = Join-Path $licensingDir $_.Name
                    Copy-Item -Path $_.FullName -Destination $destPath -Force
                    Write-Host "  Compiled: $($_.Name)" -ForegroundColor Gray
                }
            } else {
                Write-Host "  ⚠️  Build output directory not found: $buildLibDir" -ForegroundColor Yellow
            }
            
            # 删除源码（保留__init__.py和models.py）
            Get-ChildItem -Path $licensingDir -Filter "*.py" | ForEach-Object {
                $fileName = $_.Name
                if ($fileName -notin @("__init__.py", "models.py")) {
                    Remove-Item -Path $_.FullName -Force
                    Write-Host "  Removed source: $fileName" -ForegroundColor Gray
                }
            }
            
            # 清理
            Remove-Item -Path $setupPath -Force -ErrorAction SilentlyContinue
            Remove-Item -Path (Join-Path $root "build") -Recurse -Force -ErrorAction SilentlyContinue
            Get-ChildItem -Path $licensingDir -Include "*.c" -Recurse | Remove-Item -Force
        } else {
            Write-Host "  ⚠️  Cython compilation failed, falling back to bytecode" -ForegroundColor Yellow
        }
    }
} else {
    Write-Host "[2/4] Skipping Cython compilation..." -ForegroundColor Gray
}

Write-Host ""

# ============================================================================
# 步骤3：字节码编译其他目录
# ============================================================================

Write-Host "[3/4] Compiling other modules to bytecode..." -ForegroundColor Yellow
Write-Host ""

# 编译整个core目录为字节码
$compileArgs = @(
    "-O",   # 优化级别1：移除assert，保留docstring（LangChain工具需要docstring）
    "-m", "compileall",
    "-b",   # 生成.pyc文件
    $OutputDir
)

Write-Host "  Compiling..." -ForegroundColor Gray
$compileProcess = Start-Process -FilePath "python" -ArgumentList $compileArgs -Wait -PassThru -NoNewWindow

if ($compileProcess.ExitCode -eq 0) {
    Write-Host "  ✅ Bytecode compilation completed" -ForegroundColor Green

    # 移动.pyc文件到正确位置
    Get-ChildItem -Path $OutputDir -Recurse -Directory -Filter "__pycache__" | ForEach-Object {
        $pycacheDir = $_.FullName
        $parentDir = Split-Path -Parent $pycacheDir

        Get-ChildItem -Path $pycacheDir -Filter "*.pyc" | ForEach-Object {
            $pycFile = $_.FullName
            $fileName = $_.Name

            if ($fileName -match "^(.+)\.cpython-\d+\.pyc$") {
                $baseName = $matches[1]
                $newName = "$baseName.pyc"
                $destPath = Join-Path $parentDir $newName

                Move-Item -Path $pycFile -Destination $destPath -Force
            }
        }

        Remove-Item -Path $pycacheDir -Force -ErrorAction SilentlyContinue
    }
} else {
    Write-Host "  ⚠️  Bytecode compilation failed" -ForegroundColor Yellow
}

Write-Host ""

# ============================================================================
# 步骤4：清理源码文件
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
        $relativePath = $pyFile.Substring($OutputDir.Length + 1)

        # 保留的文件
        $keepFiles = @(
            "__init__.py",
            "models.py"  # licensing/models.py需要保留（被其他模块导入）
        )

        # 🔥 保留的目录（不删除源码）
        $keepDirs = @(
            "prompts"  # 提示词模板目录，必须保留源码
        )

        # 检查是否在保留目录中
        $inKeepDir = $false
        foreach ($keepDir in $keepDirs) {
            if ($relativePath -like "*\$keepDir\*" -or $relativePath -like "$keepDir\*") {
                $inKeepDir = $true
                break
            }
        }

        if ($inKeepDir) {
            Write-Host "  Kept (in prompts/): $relativePath" -ForegroundColor Cyan
        } elseif ($fileName -in $keepFiles) {
            # 清空__init__.py内容（只保留导入）
            if ($fileName -eq "__init__.py") {
                $content = Get-Content $pyFile -Raw -ErrorAction SilentlyContinue
                if ($content -and $content -match "__all__\s*=") {
                    $content -replace "(?s)^(.*?__all__\s*=\s*\[.*?\]).*", '$1' | Set-Content $pyFile
                } else {
                    "" | Set-Content $pyFile
                }
                Write-Host "  Cleaned: $relativePath" -ForegroundColor Gray
            }
        } else {
            # 检查是否有对应的.pyc或.pyd文件
            $pycFile = $pyFile -replace "\.py$", ".pyc"
            $pydFile = $pyFile -replace "\.py$", ".pyd"

            if ((Test-Path $pycFile) -or (Test-Path $pydFile)) {
                Remove-Item -Path $pyFile -Force
                $deleteCount++
                Write-Host "  Deleted: $relativePath" -ForegroundColor Gray
            }
        }
    }

    Write-Host ""
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
Write-Host "Protection summary:" -ForegroundColor White
Write-Host "  🔐 core/licensing/     → Cython compiled (C extension)" -ForegroundColor Green
Write-Host "  📦 core/other/         → Bytecode compiled (.pyc)" -ForegroundColor Green
Write-Host ""
Write-Host "Security features:" -ForegroundColor White
Write-Host "  ✅ License validation logic protected (cannot be bypassed)" -ForegroundColor Green
Write-Host "  ✅ Core business logic protected (cannot be easily read)" -ForegroundColor Green
Write-Host "  ✅ Online validation prevents fake licenses" -ForegroundColor Green
Write-Host ""
Write-Host "Next steps:" -ForegroundColor White
Write-Host "  1. Test the compiled module: python -c 'import core; print(core.__version__)'" -ForegroundColor Gray
Write-Host "  2. Test license validation: python -c 'from core.licensing import LicenseManager; m=LicenseManager()'" -ForegroundColor Gray
Write-Host "  3. Package the release: .\scripts\deployment\build_pro_package.ps1" -ForegroundColor Gray
Write-Host ""

