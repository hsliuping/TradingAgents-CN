# TradingAgents-CN 进程监控守护进程停止脚本

$ErrorActionPreference = "Continue"
$root = $PSScriptRoot
while (-not (Test-Path (Join-Path $root ".git")) -and $root.Length -gt 3) {
    $root = Split-Path $root
}
if (-not (Test-Path (Join-Path $root ".git"))) {
    $root = $PSScriptRoot
}

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "停止进程监控守护进程" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

$pidFile = Join-Path $root 'logs\process_monitor.pid'
if (Test-Path $pidFile) {
    $pid = Get-Content $pidFile -ErrorAction SilentlyContinue
    if ($pid) {
        $process = Get-Process -Id $pid -ErrorAction SilentlyContinue
        if ($process) {
            Write-Host "🛑 正在停止监控守护进程 (PID: $pid)..." -ForegroundColor Yellow
            Stop-Process -Id $pid -Force -ErrorAction SilentlyContinue
            Start-Sleep -Seconds 1
            
            # 验证是否已停止
            $stillRunning = Get-Process -Id $pid -ErrorAction SilentlyContinue
            if (-not $stillRunning) {
                Write-Host "✅ 监控守护进程已停止" -ForegroundColor Green
                Remove-Item $pidFile -Force -ErrorAction SilentlyContinue
            } else {
                Write-Host "⚠️  进程仍在运行，可能需要手动停止" -ForegroundColor Yellow
            }
        } else {
            Write-Host "⚠️  PID 文件存在但进程不存在，清理 PID 文件" -ForegroundColor Yellow
            Remove-Item $pidFile -Force -ErrorAction SilentlyContinue
        }
    }
} else {
    Write-Host "ℹ️  监控守护进程未运行（PID 文件不存在）" -ForegroundColor Gray
}
