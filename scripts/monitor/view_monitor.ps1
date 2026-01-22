# TradingAgents-CN 进程监控日志查看脚本

[CmdletBinding()]
param(
    [int]$Tail = 50,  # 显示最后N行
    [switch]$Follow,  # 实时跟踪（类似 tail -f）
    [switch]$Status   # 显示当前状态摘要
)

$ErrorActionPreference = "Continue"

# 🔥 智能检测项目根目录
# 1. 如果在开发环境（有 .git），使用开发目录
# 2. 如果在便携版/安装版（有 vendors 目录或 .env 文件），使用安装目录
$root = $PSScriptRoot

# 首先尝试查找 .git（开发环境）
$tempRoot = $root
while ($tempRoot -and $tempRoot.Length -gt 3 -and -not (Test-Path (Join-Path $tempRoot ".git"))) {
    $tempRoot = Split-Path $tempRoot -Parent
}

if ($tempRoot -and (Test-Path (Join-Path $tempRoot ".git"))) {
    # 找到了 .git，使用开发目录
    $root = $tempRoot
} else {
    # 没有找到 .git，可能是便携版/安装版
    # 尝试从脚本目录向上查找 vendors 目录或 .env 文件
    $tempRoot = $root
    while ($tempRoot -and $tempRoot.Length -gt 3) {
        if ((Test-Path (Join-Path $tempRoot "vendors")) -or (Test-Path (Join-Path $tempRoot ".env"))) {
            break
        }
        $tempRoot = Split-Path $tempRoot -Parent
    }

    if ($tempRoot -and ((Test-Path (Join-Path $tempRoot "vendors")) -or (Test-Path (Join-Path $tempRoot ".env")))) {
        # 找到了 vendors 或 .env
        $root = $tempRoot
    } else {
        # 还是没找到，使用脚本所在目录的上两级（假设脚本在 scripts/monitor/ 下）
        $root = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
    }
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
