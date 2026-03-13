# ============================================================================
# Complete Pro Version Compilation Strategy
# ============================================================================
# 完整的Pro版编译策略：
# 1. core/licensing/    → Cython编译（最关键）
# 2. core/其他目录      → 字节码编译
# 3. app/               → 字节码编译
# 4. tradingagents/     → 字节码编译
# 5. scripts/           → 字节码编译，仅保留运行入口 .py
# 6. migrations/        → 字节码编译，仅保留运行入口 .py
# 7. frontend/          → Vite构建（已编译）
# ============================================================================

param(
    [string]$PortableDir = ""
)

# UTF-8编码设置
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
[Console]::InputEncoding = [System.Text.Encoding]::UTF8
$PSDefaultParameterValues['*:Encoding'] = 'utf8'
$OutputEncoding = [System.Text.Encoding]::UTF8

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$pythonExe = ""

Write-Host "============================================================================" -ForegroundColor Cyan
Write-Host "  Complete Pro Version Compilation" -ForegroundColor Cyan
Write-Host "============================================================================" -ForegroundColor Cyan
Write-Host ""

# ============================================================================
# 设置路径
# ============================================================================

if (-not $PortableDir) {
    $PortableDir = Join-Path $root "release\TradingAgentsCN-portable"
}

if (-not (Test-Path $PortableDir)) {
    Write-Host "ERROR: Portable directory not found: $PortableDir" -ForegroundColor Red
    exit 1
}

Write-Host "Portable directory: $PortableDir" -ForegroundColor White
Write-Host ""

$portablePython = Join-Path $PortableDir "vendors\python\python.exe"
$pythonExe = if (Test-Path $portablePython) { $portablePython } else { "python" }

Write-Host "Python: $pythonExe" -ForegroundColor White
Write-Host ""

$preservedScriptSources = @(
    "scripts\apply_upgrade_config.py",
    "scripts\import_config_and_create_user.py",
    "scripts\import_mongodb_config.py",
    "scripts\init_mongodb_user.py",
    "scripts\installer\start_all.py",
    "scripts\monitor\process_monitor.py",
    "scripts\monitor\tray_monitor.py"
)

$preservedMigrationSources = @(
    "migrations\__main__.py",
    "migrations\cli.py"
)

function Invoke-CompileAndStrip {
    param(
        [string]$TargetDir,
        [string[]]$KeepRelativePaths = @(),
        [string[]]$KeepFileNames = @()
    )

    if (-not (Test-Path $TargetDir)) {
        Write-Host "  ⚠️  $TargetDir not found, skipping" -ForegroundColor Yellow
        return $false
    }

    Write-Host "  Cleaning old cache in $TargetDir ..." -ForegroundColor Gray
    $cacheDirs = Get-ChildItem -Path $TargetDir -Recurse -Directory -Filter "__pycache__" -ErrorAction SilentlyContinue
    if ($cacheDirs) {
        $cacheDirs | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
    }

    $oldPycFiles = Get-ChildItem -Path $TargetDir -Recurse -Filter "*.pyc" -ErrorAction SilentlyContinue
    if ($oldPycFiles) {
        $oldPycFiles | Remove-Item -Force -ErrorAction SilentlyContinue
    }

    Write-Host "  Compiling $TargetDir to bytecode..." -ForegroundColor Gray
    & $pythonExe -O -m compileall -b $TargetDir

    if ($LASTEXITCODE -ne 0) {
        Write-Host "  ⚠️  Compilation failed for $TargetDir, keeping source files" -ForegroundColor Yellow
        return $false
    }

    Write-Host "  Removing source files based on whitelist..." -ForegroundColor Gray
    $removedCount = 0
    $normalizedKeepRelativePaths = $KeepRelativePaths | ForEach-Object { $_ -replace '/', '\\' }

    Get-ChildItem -Path $TargetDir -Filter "*.py" -Recurse | ForEach-Object {
        $relativePath = $_.FullName.Substring($PortableDir.Length + 1)
        $relativePath = $relativePath -replace '/', '\\'
        $compiledPath = [System.IO.Path]::ChangeExtension($_.FullName, '.pyc')

        if ($normalizedKeepRelativePaths -contains $relativePath -or $KeepFileNames -contains $_.Name) {
            return
        }

        if (-not (Test-Path $compiledPath)) {
            Write-Host "  ⚠️  Keeping source without compiled bytecode: $relativePath" -ForegroundColor Yellow
            return
        }

        Remove-Item $_.FullName -Force
        $removedCount++
    }

    Write-Host "  ✅ Removed $removedCount source files, kept compiled bytecode" -ForegroundColor Green
    return $true
}

function Invoke-EnforceCompiledLayout {
    param(
        [string]$TargetDir,
        [string[]]$KeepRelativePaths = @(),
        [string[]]$KeepFileNames = @(),
        [switch]$RequireCompiledArtifacts = $true
    )

    if (-not (Test-Path $TargetDir)) {
        Write-Host "  ⚠️  $TargetDir not found, skipping enforcement" -ForegroundColor Yellow
        return $false
    }

    $normalizedKeepRelativePaths = $KeepRelativePaths | ForEach-Object { $_ -replace '/', '\\' }

    Write-Host "  Enforcing compiled-only layout in $TargetDir ..." -ForegroundColor Gray

    & $pythonExe -O -m compileall -b $TargetDir
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to compile bytecode in $TargetDir during final enforcement"
    }

    $removedCount = 0
    Get-ChildItem -Path $TargetDir -Filter "*.py" -Recurse -File | ForEach-Object {
        $relativePath = $_.FullName.Substring($PortableDir.Length + 1)
        $relativePath = $relativePath -replace '/', '\\'
        $compiledPath = [System.IO.Path]::ChangeExtension($_.FullName, '.pyc')
        $nativePath = [System.IO.Path]::ChangeExtension($_.FullName, '.pyd')

        if ($normalizedKeepRelativePaths -contains $relativePath -or $KeepFileNames -contains $_.Name) {
            return
        }

        if ((Test-Path $compiledPath) -or (Test-Path $nativePath)) {
            Remove-Item -Path $_.FullName -Force
            $removedCount++
            return
        }

        throw "Missing compiled artifact for source file: $relativePath"
    }

    $compiledCount = 0
    $compiledCount += (Get-ChildItem -Path $TargetDir -Recurse -Filter "*.pyc" -File -ErrorAction SilentlyContinue | Measure-Object).Count
    $compiledCount += (Get-ChildItem -Path $TargetDir -Recurse -Filter "*.pyd" -File -ErrorAction SilentlyContinue | Measure-Object).Count

    $remainingSourceCount = 0
    Get-ChildItem -Path $TargetDir -Filter "*.py" -Recurse -File | ForEach-Object {
        $relativePath = $_.FullName.Substring($PortableDir.Length + 1)
        $relativePath = $relativePath -replace '/', '\\'
        if ($normalizedKeepRelativePaths -contains $relativePath -or $KeepFileNames -contains $_.Name) {
            return
        }

        $remainingSourceCount++
    }

    if ($RequireCompiledArtifacts -and $compiledCount -le 0) {
        throw "No compiled artifacts found in $TargetDir after enforcement"
    }

    if ($remainingSourceCount -gt 0) {
        throw "Non-whitelisted source files still remain in $TargetDir after enforcement"
    }

    Write-Host "  ✅ Enforcement completed: removed $removedCount source files, compiled artifacts=$compiledCount" -ForegroundColor Green
    return $true
}

# ============================================================================
# Step 0: 清理所有旧的缓存和编译文件（编译前清理）
# ============================================================================

Write-Host "[0/4] Cleaning old cache and compiled files before compilation..." -ForegroundColor Yellow
Write-Host ""

$cleanedCacheDirs = 0
$cleanedPycFiles = 0
$cleanedPydFiles = 0
$cleanedPyoFiles = 0

# 清理所有 __pycache__ 目录
$cacheDirs = Get-ChildItem -Path $PortableDir -Recurse -Directory -Filter "__pycache__" -ErrorAction SilentlyContinue
if ($cacheDirs) {
    $cleanedCacheDirs = ($cacheDirs | Measure-Object).Count
    $cacheDirs | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
    Write-Host "  ✅ Cleaned $cleanedCacheDirs __pycache__ directories" -ForegroundColor Green
}

# 清理所有旧的 .pyc 文件（编译前，所有 .pyc 都是旧的缓存）
$pycFiles = Get-ChildItem -Path $PortableDir -Recurse -Filter "*.pyc" -ErrorAction SilentlyContinue
if ($pycFiles) {
    $cleanedPycFiles = ($pycFiles | Measure-Object).Count
    $pycFiles | Remove-Item -Force -ErrorAction SilentlyContinue
    Write-Host "  ✅ Cleaned $cleanedPycFiles old .pyc files" -ForegroundColor Green
}

# 清理 core/licensing 目录下的旧 .pyd 文件（Cython 编译生成的）
# 🔥 重要：只清理项目生成的 .pyd 文件，不清理外部依赖的 .pyd 文件
$coreLicensingDir = Join-Path $PortableDir "core\licensing"
if (Test-Path $coreLicensingDir) {
    $pydFiles = Get-ChildItem -Path $coreLicensingDir -Recurse -Filter "*.pyd" -ErrorAction SilentlyContinue
    if ($pydFiles) {
        $cleanedPydFiles = ($pydFiles | Measure-Object).Count
        $pydFiles | Remove-Item -Force -ErrorAction SilentlyContinue
        Write-Host "  ✅ Cleaned $cleanedPydFiles old .pyd files in core/licensing" -ForegroundColor Green
    }
}

# 清理所有 .pyo 文件
$pyoFiles = Get-ChildItem -Path $PortableDir -Recurse -Filter "*.pyo" -ErrorAction SilentlyContinue
if ($pyoFiles) {
    $cleanedPyoFiles = ($pyoFiles | Measure-Object).Count
    $pyoFiles | Remove-Item -Force -ErrorAction SilentlyContinue
    Write-Host "  ✅ Cleaned $cleanedPyoFiles .pyo files" -ForegroundColor Green
}

if ($cleanedCacheDirs -eq 0 -and $cleanedPycFiles -eq 0 -and $cleanedPydFiles -eq 0 -and $cleanedPyoFiles -eq 0) {
    Write-Host "  ✅ No old cache/compiled files found" -ForegroundColor Green
}

Write-Host ""

# ============================================================================
# Step 1: 编译 core/ 目录（混合编译）
# ============================================================================

Write-Host "[1/3] Compiling core/ directory..." -ForegroundColor Yellow
Write-Host ""

$coreDir = Join-Path $PortableDir "core"
$compileScript = Join-Path $PSScriptRoot "compile_core_hybrid.ps1"
& powershell -ExecutionPolicy Bypass -File $compileScript -OutputDir $coreDir

if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Core compilation failed" -ForegroundColor Red
    exit 1
}

Write-Host "  ✅ Core compilation completed" -ForegroundColor Green
Write-Host ""

# ============================================================================
# Step 2: 编译 app/ 目录（字节码）
# ============================================================================

Write-Host "[2/6] Compiling app/ directory..." -ForegroundColor Yellow
Write-Host ""

$appDir = Join-Path $PortableDir "app"
if (Test-Path $appDir) {
    $appCompiled = Invoke-CompileAndStrip -TargetDir $appDir -KeepFileNames @("__main__.py")
    if ($appCompiled) {
        Write-Host "  ✅ App compilation completed" -ForegroundColor Green
    }
} else {
    Write-Host "  ⚠️  app/ directory not found, skipping" -ForegroundColor Yellow
}

Write-Host ""

# ============================================================================
# Step 3: 编译 tradingagents/ 目录（字节码）
# ============================================================================

Write-Host "[3/6] Compiling tradingagents/ directory..." -ForegroundColor Yellow
Write-Host ""

$tradingagentsDir = Join-Path $PortableDir "tradingagents"
if (Test-Path $tradingagentsDir) {
    $tradingagentsCompiled = Invoke-CompileAndStrip -TargetDir $tradingagentsDir
    if ($tradingagentsCompiled) {
        Write-Host "  ✅ tradingagents/ compilation completed" -ForegroundColor Green
    }
} else {
    Write-Host "  ⚠️  tradingagents/ directory not found, skipping" -ForegroundColor Yellow
}

Write-Host ""

# ============================================================================
# Step 4: 编译 scripts/ 目录（字节码 + 入口白名单）
# ============================================================================

Write-Host "[4/6] Compiling scripts/ directory..." -ForegroundColor Yellow
Write-Host ""

$scriptsDir = Join-Path $PortableDir "scripts"
if (Test-Path $scriptsDir) {
    $scriptsCompiled = Invoke-CompileAndStrip -TargetDir $scriptsDir -KeepRelativePaths $preservedScriptSources
    if ($scriptsCompiled) {
        Write-Host "  ✅ scripts/ compilation completed" -ForegroundColor Green
    }
} else {
    Write-Host "  ⚠️  scripts/ directory not found, skipping" -ForegroundColor Yellow
}

Write-Host ""

# ============================================================================
# Step 5: 编译 migrations/ 目录（字节码 + 入口白名单）
# ============================================================================

Write-Host "[5/6] Compiling migrations/ directory..." -ForegroundColor Yellow
Write-Host ""

$migrationsDir = Join-Path $PortableDir "migrations"
if (Test-Path $migrationsDir) {
    $migrationsCompiled = Invoke-CompileAndStrip -TargetDir $migrationsDir -KeepRelativePaths $preservedMigrationSources -KeepFileNames @()
    if ($migrationsCompiled) {
        Write-Host "  ✅ migrations/ compilation completed" -ForegroundColor Green
    }
} else {
    Write-Host "  ⚠️  migrations/ directory not found, skipping" -ForegroundColor Yellow
}

Write-Host ""

# ============================================================================
# Step 6: 最终强制校验并递归剥离源码
# ============================================================================

Write-Host "[6/7] Enforcing compiled-only package layout..." -ForegroundColor Yellow
Write-Host ""

Invoke-EnforceCompiledLayout -TargetDir $coreDir | Out-Null
Invoke-EnforceCompiledLayout -TargetDir $appDir -KeepFileNames @("__main__.py") | Out-Null
Invoke-EnforceCompiledLayout -TargetDir $tradingagentsDir | Out-Null
Invoke-EnforceCompiledLayout -TargetDir $scriptsDir -KeepRelativePaths $preservedScriptSources | Out-Null
Invoke-EnforceCompiledLayout -TargetDir $migrationsDir -KeepRelativePaths $preservedMigrationSources | Out-Null

Write-Host ""

# ============================================================================
# Step 7: 验证编译结果
# ============================================================================

Write-Host "[7/7] Verifying compilation results..." -ForegroundColor Yellow
Write-Host ""

# 验证 core/other/ 中的编译文件
$coreOtherPyc = Get-ChildItem -Path (Join-Path $PortableDir "core\other") -Recurse -Filter "*.pyc" -ErrorAction SilentlyContinue
if ($coreOtherPyc) {
    Write-Host "  ✅ core/other/ bytecode: $($coreOtherPyc.Count) .pyc files" -ForegroundColor Green
}

# 验证 core/licensing/ 中的编译文件
$coreLicensingPyd = Get-ChildItem -Path (Join-Path $PortableDir "core\licensing") -Recurse -Filter "*.pyd" -ErrorAction SilentlyContinue
if ($coreLicensingPyd) {
    Write-Host "  ✅ core/licensing/ Cython: $($coreLicensingPyd.Count) .pyd files" -ForegroundColor Green
}

# 验证 app/ 中的编译文件
$appPyc = Get-ChildItem -Path (Join-Path $PortableDir "app") -Recurse -Filter "*.pyc" -ErrorAction SilentlyContinue
if ($appPyc) {
    Write-Host "  ✅ app/ bytecode: $($appPyc.Count) .pyc files" -ForegroundColor Green
}

$tradingagentsPyc = Get-ChildItem -Path (Join-Path $PortableDir "tradingagents") -Recurse -Filter "*.pyc" -ErrorAction SilentlyContinue
if ($tradingagentsPyc) {
    Write-Host "  ✅ tradingagents/ bytecode: $($tradingagentsPyc.Count) .pyc files" -ForegroundColor Green
}

$scriptsPyc = Get-ChildItem -Path (Join-Path $PortableDir "scripts") -Recurse -Filter "*.pyc" -ErrorAction SilentlyContinue
if ($scriptsPyc) {
    Write-Host "  ✅ scripts/ bytecode: $($scriptsPyc.Count) .pyc files" -ForegroundColor Green
}

$migrationsPyc = Get-ChildItem -Path (Join-Path $PortableDir "migrations") -Recurse -Filter "*.pyc" -ErrorAction SilentlyContinue
if ($migrationsPyc) {
    Write-Host "  ✅ migrations/ bytecode: $($migrationsPyc.Count) .pyc files" -ForegroundColor Green
}

Write-Host ""

# ============================================================================
# 完成总结
# ============================================================================

Write-Host "============================================================================" -ForegroundColor Green
Write-Host "  Pro Version Compilation Completed!" -ForegroundColor Green
Write-Host "============================================================================" -ForegroundColor Green
Write-Host ""

Write-Host "Compilation Summary:" -ForegroundColor White
Write-Host "  🔐 core/licensing/    → Cython compiled (.pyd)" -ForegroundColor Green
Write-Host "  📦 core/other/        → Bytecode compiled (.pyc)" -ForegroundColor Green
Write-Host "  📦 app/               → Bytecode compiled (.pyc)" -ForegroundColor Green
Write-Host "  📦 tradingagents/     → Bytecode compiled (.pyc)" -ForegroundColor Green
Write-Host "  📦 scripts/           → Bytecode compiled (.pyc), whitelist .py retained" -ForegroundColor Green
Write-Host "  📦 migrations/        → Bytecode compiled (.pyc), whitelist .py retained" -ForegroundColor Green
Write-Host "  ✨ frontend/dist/     → Vite built (production)" -ForegroundColor Green
Write-Host ""

