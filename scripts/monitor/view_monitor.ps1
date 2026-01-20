# TradingAgents-CN 进程监控日志查看脚本

[CmdletBinding()]
param(
    [int]$Tail = 50,  # 显示最后N行
    [switch]$Follow,  # 实时跟踪（类似 tail -f）
    [switch]$Status   # 显示当前状态摘要
)

$ErrorActionPreference = "Continue"
$root = $PSScriptRoot
while (-not (Test-Path (Join-Path $root ".git")) -and $root.Length -gt 3) {
    $root = Split-Path $root
}
if (-not (Test-Path (Join-Path $root ".git"))) {
    $root = $PSScriptRoot
}

$logFile = Join-Path $root "logs\process_monitor.log"
$pidFile = Join-Path $root "logs\process_monitor.pid"
$historyFile = Join-Path $root "logs\process_monitor_history.json"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "TradingAgents-CN 进程监控查看器" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# 检查监控进程是否运行
$monitorRunning = $false
if (Test-Path $pidFile) {
    $processId = Get-Content $pidFile -ErrorAction SilentlyContinue
    if ($processId) {
        $process = Get-Process -Id $processId -ErrorAction SilentlyContinue
        if ($process) {
            $monitorRunning = $true
            Write-Host "✅ 监控守护进程正在运行 (PID: $processId)" -ForegroundColor Green
        } else {
            Write-Host "⚠️  PID文件存在但进程不存在，可能已退出" -ForegroundColor Yellow
        }
    }
}

if (-not $monitorRunning) {
    Write-Host "❌ 监控守护进程未运行" -ForegroundColor Red
    Write-Host "   启动监控: scripts\monitor\start_monitor.ps1" -ForegroundColor Gray
    Write-Host ""
}

# 显示状态摘要
if ($Status) {
    Write-Host "📊 当前监控状态:" -ForegroundColor Yellow
    Write-Host ""
    
    if (Test-Path $historyFile) {
        try {
            $history = Get-Content $historyFile -Raw | ConvertFrom-Json
            
            # 🔥 兼容两种格式：
            # 1. 新格式：{ "processes": { "Worker": {...}, ... } }
            # 2. 旧格式：{ "Worker": {...}, "Backend": {...}, ... }
            $processes = $null
            if ($history.PSObject.Properties.Name -contains "processes") {
                # 新格式：有 processes 键
                $processes = $history.processes
            } else {
                # 旧格式：直接是进程字典
                $processes = $history
            }
            
            if ($processes) {
                foreach ($procName in $processes.PSObject.Properties.Name) {
                    $proc = $processes.$procName
                    $status = $proc.status
                    $processId = $proc.pid
                    $exitCode = $proc.exit_code
                    $exitTime = $proc.exit_time
                    
                    if ($status -eq "running") {
                        Write-Host "  ✅ $procName" -ForegroundColor Green -NoNewline
                        Write-Host " (PID: $processId)" -ForegroundColor Gray
                    } elseif ($status -eq "stopped") {
                        Write-Host "  ❌ $procName" -ForegroundColor Red -NoNewline
                        if ($exitCode) {
                            Write-Host " (退出代码: $exitCode)" -ForegroundColor Yellow -NoNewline
                        }
                        if ($exitTime) {
                            Write-Host " (退出时间: $exitTime)" -ForegroundColor Gray
                        } else {
                            Write-Host ""
                        }
                    } else {
                        Write-Host "  ⚠️  $procName" -ForegroundColor Yellow -NoNewline
                        Write-Host " (状态: $status)" -ForegroundColor Gray
                    }
                }
            } else {
                Write-Host "  ℹ️  历史记录为空" -ForegroundColor Gray
            }
        } catch {
            Write-Host "  ⚠️  无法读取历史记录: $_" -ForegroundColor Yellow
        }
    } else {
        Write-Host "  ℹ️  暂无历史记录" -ForegroundColor Gray
    }
    Write-Host ""
}

# 显示日志
if (Test-Path $logFile) {
    if ($Follow) {
        Write-Host "📋 实时跟踪监控日志 (按 Ctrl+C 停止):" -ForegroundColor Yellow
        Write-Host "   日志文件: $logFile" -ForegroundColor Gray
        Write-Host ""
        
        # 使用 Get-Content -Wait 实时跟踪
        Get-Content $logFile -Tail $Tail -Wait -Encoding UTF8
    } else {
        Write-Host "📋 监控日志 (最后 $Tail 行):" -ForegroundColor Yellow
        Write-Host "   日志文件: $logFile" -ForegroundColor Gray
        Write-Host ""
        
        # 显示最后N行
        if ($Tail -gt 0) {
            Get-Content $logFile -Tail $Tail -Encoding UTF8
        } else {
            Get-Content $logFile -Encoding UTF8
        }
        
        Write-Host ""
        Write-Host "💡 提示:" -ForegroundColor Cyan
        Write-Host "   - 实时跟踪: .\view_monitor.ps1 -Follow" -ForegroundColor Gray
        Write-Host "   - 显示状态: .\view_monitor.ps1 -Status" -ForegroundColor Gray
        Write-Host "   - 更多行数: .\view_monitor.ps1 -Tail 100" -ForegroundColor Gray
    }
} else {
    Write-Host "⚠️  日志文件不存在: $logFile" -ForegroundColor Yellow
    Write-Host "   监控守护进程可能还未运行或未生成日志" -ForegroundColor Gray
}
