# TradingAgents-CN 进程监控守护进程启动脚本

[CmdletBinding()]
param(
    [int]$Interval = 30,
    [string]$LogFile = "logs\process_monitor.log",
    [switch]$Background
)

$ErrorActionPreference = "Continue"
$root = $PSScriptRoot
while (-not (Test-Path (Join-Path $root ".git")) -and $root.Length -gt 3) {
    $root = Split-Path $root
}
if (-not (Test-Path (Join-Path $root ".git"))) {
    $root = $PSScriptRoot
}

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "TradingAgents-CN 进程监控守护进程" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# 检查 Python
$pythonExe = Join-Path $root 'vendors\python\python.exe'
if (-not (Test-Path $pythonExe)) {
    $pythonExe = Join-Path $root 'venv\Scripts\python.exe'
}

if (-not (Test-Path $pythonExe)) {
    Write-Host "ERROR: Python not found" -ForegroundColor Red
    exit 1
}

# 检查监控脚本
$monitorScript = Join-Path $root 'scripts\monitor\process_monitor.py'
if (-not (Test-Path $monitorScript)) {
    Write-Host "ERROR: 监控脚本未找到: $monitorScript" -ForegroundColor Red
    exit 1
}

# 检查是否已经运行
$pidFile = Join-Path $root 'logs\process_monitor.pid'
if (Test-Path $pidFile) {
    $existingPid = Get-Content $pidFile -ErrorAction SilentlyContinue
    if ($existingPid) {
        $existingProcess = Get-Process -Id $existingPid -ErrorAction SilentlyContinue
        if ($existingProcess) {
            Write-Host "⚠️  监控守护进程已在运行 (PID: $existingPid)" -ForegroundColor Yellow
            Write-Host "   如需重启，请先停止现有进程: Stop-Process -Id $existingPid" -ForegroundColor Gray
            exit 0
        } else {
            # PID 文件存在但进程不存在，删除旧文件
            Remove-Item $pidFile -Force -ErrorAction SilentlyContinue
        }
    }
}

# 确保日志目录存在
$logDir = Split-Path $LogFile -Parent
if ($logDir) {
    New-Item -ItemType Directory -Path $logDir -Force | Out-Null
}

Write-Host "🚀 启动进程监控守护进程..." -ForegroundColor Yellow
Write-Host "   监控间隔: $Interval 秒" -ForegroundColor Gray
Write-Host "   日志文件: $LogFile" -ForegroundColor Gray
Write-Host ""

# 设置 UTF-8 编码
$env:PYTHONIOENCODING = "utf-8"
$env:PYTHONUTF8 = "1"

# 构建参数
$monitorArgs = @(
    "`"$monitorScript`"",
    "--interval", $Interval,
    "--log-file", "`"$LogFile`""
)

if ($Background) {
    # 后台运行
    Write-Host "   模式: 后台运行" -ForegroundColor Gray
    $process = Start-Process -FilePath $pythonExe -ArgumentList $monitorArgs -WorkingDirectory $root -WindowStyle Hidden -PassThru
    
    if ($process) {
        Write-Host "✅ 监控守护进程已启动 (PID: $($process.Id))" -ForegroundColor Green
        Write-Host "   查看日志: Get-Content $LogFile -Tail 50 -Wait" -ForegroundColor Cyan
    } else {
        Write-Host "❌ 启动失败" -ForegroundColor Red
        exit 1
    }
} else {
    # 前台运行
    Write-Host "   模式: 前台运行 (按 Ctrl+C 停止)" -ForegroundColor Gray
    Write-Host ""
    & $pythonExe $monitorArgs
}
