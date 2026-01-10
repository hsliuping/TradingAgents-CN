# ============================================================================
# Clean and Compile - 清理旧文件并重新编译
# ============================================================================
# 解决 "拒绝访问" 问题的脚本
# ============================================================================

param(
    [string]$PortableDir = ""
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)

if (-not $PortableDir) {
    $PortableDir = Join-Path $root "release\TradingAgentsCN-portable"
}

Write-Host "============================================================================" -ForegroundColor Cyan
Write-Host "  Clean and Compile" -ForegroundColor Cyan
Write-Host "============================================================================" -ForegroundColor Cyan
Write-Host ""

# ============================================================================
# Step 1: 停止所有可能占用文件的进程
# ============================================================================

Write-Host "[1/4] Stopping Python processes..." -ForegroundColor Yellow
Write-Host ""

$pythonProcesses = Get-Process | Where-Object {$_.ProcessName -eq "python"}
if ($pythonProcesses) {
    Write-Host "  Found $($pythonProcesses.Count) Python process(es)" -ForegroundColor Gray
    foreach ($proc in $pythonProcesses) {
        try {
            Write-Host "  Stopping PID $($proc.Id)..." -ForegroundColor Gray
            Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
            Start-Sleep -Milliseconds 500
        } catch {
            Write-Host "  Warning: Could not stop PID $($proc.Id)" -ForegroundColor Yellow
        }
    }
    Write-Host "  Waiting for processes to exit..." -ForegroundColor Gray
    Start-Sleep -Seconds 2
} else {
    Write-Host "  No Python processes found" -ForegroundColor Green
}

Write-Host ""

# ============================================================================
# Step 2: 清理旧的编译文件
# ============================================================================

Write-Host "[2/4] Cleaning old compiled files..." -ForegroundColor Yellow
Write-Host ""

$coreLicensingDir = Join-Path $PortableDir "core\licensing"

if (Test-Path $coreLicensingDir) {
    Write-Host "  Cleaning core/licensing directory..." -ForegroundColor Gray
    
    # 删除所有 .pyd 文件
    Get-ChildItem -Path $coreLicensingDir -Filter "*.pyd" -ErrorAction SilentlyContinue | ForEach-Object {
        try {
            Remove-Item -Path $_.FullName -Force -ErrorAction Stop
            Write-Host "    Removed: $($_.Name)" -ForegroundColor DarkGray
        } catch {
            Write-Host "    Warning: Could not remove $($_.Name): $_" -ForegroundColor Yellow
        }
    }
    
    # 删除所有 .c 文件
    Get-ChildItem -Path $coreLicensingDir -Filter "*.c" -ErrorAction SilentlyContinue | ForEach-Object {
        try {
            Remove-Item -Path $_.FullName -Force -ErrorAction Stop
            Write-Host "    Removed: $($_.Name)" -ForegroundColor DarkGray
        } catch {
            Write-Host "    Warning: Could not remove $($_.Name): $_" -ForegroundColor Yellow
        }
    }
    
    Write-Host "  ✅ Cleanup completed" -ForegroundColor Green
} else {
    Write-Host "  Warning: core/licensing directory not found" -ForegroundColor Yellow
}

Write-Host ""

# ============================================================================
# Step 3: 清理构建目录
# ============================================================================

Write-Host "[3/4] Cleaning build directories..." -ForegroundColor Yellow
Write-Host ""

$buildDir = Join-Path $root "build"
if (Test-Path $buildDir) {
    try {
        Remove-Item -Path $buildDir -Recurse -Force -ErrorAction Stop
        Write-Host "  Removed: build/" -ForegroundColor DarkGray
    } catch {
        Write-Host "  Warning: Could not remove build/: $_" -ForegroundColor Yellow
    }
}

Write-Host ""

# ============================================================================
# Step 4: 重新编译
# ============================================================================

Write-Host "[4/4] Recompiling..." -ForegroundColor Yellow
Write-Host ""

$compileScript = Join-Path $root "scripts\deployment\compile_pro_complete.ps1"

if (Test-Path $compileScript) {
    & powershell -ExecutionPolicy Bypass -File $compileScript -PortableDir $PortableDir
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host ""
        Write-Host "============================================================================" -ForegroundColor Green
        Write-Host "  Compilation Completed Successfully!" -ForegroundColor Green
        Write-Host "============================================================================" -ForegroundColor Green
    } else {
        Write-Host ""
        Write-Host "ERROR: Compilation failed" -ForegroundColor Red
        exit 1
    }
} else {
    Write-Host "ERROR: Compile script not found: $compileScript" -ForegroundColor Red
    exit 1
}

