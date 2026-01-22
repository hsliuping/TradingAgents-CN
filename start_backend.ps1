# 启动 Backend 服务（开发环境）
# 用法: .\start_backend.ps1 [-Port 8000]

param(
    [int]$Port = 8000
)

$ErrorActionPreference = "Stop"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  TradingAgents-CN Pro - Backend 启动" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# 检测 Python 环境
$root = $PSScriptRoot
$pythonExe = $null
$venvPaths = @(
    (Join-Path $root "env\Scripts\python.exe"),      # 优先使用 env
    (Join-Path $root "venv\Scripts\python.exe"),
    (Join-Path $root "vendors\python\python.exe")
)

foreach ($path in $venvPaths) {
    if (Test-Path $path) {
        $pythonExe = $path
        Write-Host "✅ 找到 Python: $path" -ForegroundColor Green
        break
    }
}

if (-not $pythonExe) {
    Write-Host "❌ 未找到 Python 环境" -ForegroundColor Red
    exit 1
}

# 设置环境变量
$env:PYTHONIOENCODING = "utf-8"
$env:PYTHONUTF8 = "1"
$env:PYTHONUNBUFFERED = "1"

Write-Host ""
Write-Host "🚀 启动 Backend 服务..." -ForegroundColor Cyan
Write-Host "   端口: $Port" -ForegroundColor Gray
Write-Host "   日志: logs/backend.log" -ForegroundColor Gray
Write-Host ""

# 启动 Backend
& $pythonExe -m uvicorn app.main:app --host 127.0.0.1 --port $Port --log-level info

