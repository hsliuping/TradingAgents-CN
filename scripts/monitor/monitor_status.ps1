# TradingAgents-CN 进程监控状态查看脚本（简洁版）

[CmdletBinding()]
param(
    [switch]$Json  # 以JSON格式输出
)

$ErrorActionPreference = "Continue"

# 🔥 智能检测项目根目录
# 1. 如果在开发环境（有 .git），使用开发目录
# 2. 如果在便携版/安装版（有 runtime/pids.json），使用当前目录
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
    # 尝试从脚本目录向上查找 runtime/pids.json
    $tempRoot = $root
    while ($tempRoot -and $tempRoot.Length -gt 3 -and -not (Test-Path (Join-Path $tempRoot "runtime\pids.json"))) {
        $tempRoot = Split-Path $tempRoot -Parent
    }

    if ($tempRoot -and (Test-Path (Join-Path $tempRoot "runtime\pids.json"))) {
        # 找到了 runtime/pids.json
        $root = $tempRoot
    } else {
        # 还是没找到，使用脚本所在目录的上两级（假设脚本在 scripts/monitor/ 下）
        $root = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
    }
}

$pidFile = Join-Path $root "logs\process_monitor.pid"
$historyFile = Join-Path $root "logs\process_monitor_history.json"
$runtimePidsFile = Join-Path $root "runtime\pids.json"

# 🔍 调试信息（临时）
# Write-Host "DEBUG: Root directory: $root" -ForegroundColor Magenta
# Write-Host "DEBUG: pids.json path: $runtimePidsFile" -ForegroundColor Magenta
# Write-Host "DEBUG: pids.json exists: $(Test-Path $runtimePidsFile)" -ForegroundColor Magenta

# 检查监控进程状态
$monitorStatus = @{
    running = $false
    pid = $null
}

if (Test-Path $pidFile) {
    $processId = Get-Content $pidFile -ErrorAction SilentlyContinue
    if ($processId) {
        $process = Get-Process -Id $processId -ErrorAction SilentlyContinue
        if ($process) {
            $monitorStatus.running = $true
            $monitorStatus.pid = $processId
        }
    }
}

# 读取进程状态
$processStatus = @{}
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
                $processStatus[$procName] = @{
                    status = $proc.status
                    pid = $proc.pid
                    exit_code = $proc.exit_code
                    exit_time = $proc.exit_time
                    error_message = $proc.error_message
                }
            }
        }
    } catch {
        Write-Host "⚠️  读取历史记录失败: $_" -ForegroundColor Yellow
        # 忽略错误，继续执行
    }
}

# 🔥 读取 runtime\pids.json（如果存在）
$runtimePids = $null
if (Test-Path $runtimePidsFile) {
    try {
        $runtimePids = Get-Content $runtimePidsFile -Raw | ConvertFrom-Json
    } catch {
        # 忽略错误
    }
}

if ($Json) {
    # JSON格式输出
    $output = @{
        monitor = $monitorStatus
        processes = $processStatus
        runtime_pids = $runtimePids
        timestamp = (Get-Date).ToString("yyyy-MM-dd HH:mm:ss")
    }
    $output | ConvertTo-Json -Depth 10
} else {
    # 人类可读格式
    Write-Host "进程监控状态" -ForegroundColor Cyan
    Write-Host "==============" -ForegroundColor Cyan
    Write-Host ""
    
    # 监控进程状态
    if ($monitorStatus.running) {
        Write-Host "监控守护进程: " -NoNewline
        Write-Host "✅ 运行中" -ForegroundColor Green -NoNewline
        Write-Host " (PID: $($monitorStatus.pid))" -ForegroundColor Gray
    } else {
        Write-Host "监控守护进程: " -NoNewline
        Write-Host "❌ 未运行" -ForegroundColor Red
    }
    Write-Host ""
    
    # 被监控的进程状态
    if ($processStatus.Count -gt 0) {
        Write-Host "被监控进程状态:" -ForegroundColor Yellow
        Write-Host ""
        
        foreach ($procName in $processStatus.Keys | Sort-Object) {
            $proc = $processStatus[$procName]
            $status = $proc.status
            $processId = $proc.pid
            $exitCode = $proc.exit_code
            $exitTime = $proc.exit_time
            $errorMsg = $proc.error_message
            
            Write-Host "  $procName" -NoNewline
            
            if ($status -eq "running") {
                Write-Host " ✅ 运行中" -ForegroundColor Green -NoNewline
                if ($processId) {
                    Write-Host " (PID: $processId)" -ForegroundColor Gray
                } else {
                    Write-Host ""
                }
            } elseif ($status -eq "stopped") {
                Write-Host " ❌ 已停止" -ForegroundColor Red -NoNewline
                if ($exitCode) {
                    Write-Host " (退出代码: $exitCode)" -ForegroundColor Yellow -NoNewline
                }
                if ($exitTime) {
                    Write-Host " (退出时间: $exitTime)" -ForegroundColor Gray
                } else {
                    Write-Host ""
                }
                if ($errorMsg) {
                    Write-Host "    错误: $errorMsg" -ForegroundColor Red
                }
            } else {
                Write-Host " ⚠️  $status" -ForegroundColor Yellow
            }
        }
    } elseif ($runtimePids) {
        # 🔥 使用 runtime\pids.json 显示进程状态
        Write-Host "被监控进程状态:" -ForegroundColor Yellow
        Write-Host ""
        
        $processMap = @{
            "mongodb" = @{ Name = "MongoDB"; Description = "数据库服务器" }
            "redis" = @{ Name = "Redis"; Description = "缓存服务器" }
            "backend" = @{ Name = "Backend API"; Description = "FastAPI 后端服务" }
            "nginx" = @{ Name = "Nginx"; Description = "Web 服务器" }
        }
        
        $foundCount = 0
        foreach ($key in $processMap.Keys | Sort-Object) {
            $procInfo = $processMap[$key]
            $procName = $procInfo.Name
            $procPid = $runtimePids.$key

            if ($procPid) {
                try {
                    $process = Get-Process -Id $procPid -ErrorAction SilentlyContinue
                    if ($process) {
                        Write-Host "  ✅ $procName" -ForegroundColor Green -NoNewline
                        Write-Host " (PID: $procPid)" -ForegroundColor Gray -NoNewline
                        Write-Host " - $($procInfo.Description)" -ForegroundColor DarkGray
                        $foundCount++
                    } else {
                        Write-Host "  ❌ $procName" -ForegroundColor Red -NoNewline
                        Write-Host " (PID: $procPid, 进程已退出)" -ForegroundColor Yellow -NoNewline
                        Write-Host " - $($procInfo.Description)" -ForegroundColor DarkGray
                    }
                } catch {
                    Write-Host "  ⚠️  $procName" -ForegroundColor Yellow -NoNewline
                    Write-Host " (PID: $procPid, 检查失败)" -ForegroundColor Gray
                }
            } else {
                Write-Host "  ⚠️  $procName" -ForegroundColor Yellow -NoNewline
                Write-Host " (未启动)" -ForegroundColor Gray -NoNewline
                Write-Host " - $($procInfo.Description)" -ForegroundColor DarkGray
            }
        }
        
        Write-Host ""
        if ($foundCount -eq $processMap.Count) {
            Write-Host "  ✅ 所有关键进程都在运行" -ForegroundColor Green
        } elseif ($foundCount -gt 0) {
            Write-Host "  ⚠️  部分进程未运行，请检查服务状态" -ForegroundColor Yellow
        } else {
            Write-Host "  ❌ 所有关键进程都未运行，请启动服务" -ForegroundColor Red
        }
        Write-Host ""
        Write-Host "  💡 提示:" -ForegroundColor Cyan
        Write-Host "     - 启动所有服务: scripts\installer\start_all.ps1" -ForegroundColor Gray
        Write-Host "     - 启动监控守护进程: scripts\monitor\start_monitor.ps1" -ForegroundColor Gray
        Write-Host "     - 监控守护进程会自动记录进程状态变化和退出信息" -ForegroundColor Gray
    } else {
        # 🔥 如果没有历史记录，尝试直接检查进程状态
        Write-Host "被监控进程状态:" -ForegroundColor Yellow
        Write-Host ""
        Write-Host "  ℹ️  暂无历史记录，尝试直接检查进程..." -ForegroundColor Gray
        Write-Host ""
        
        # 检查关键进程（改进的检测逻辑）
        $processesToCheck = @(
            @{ 
                Name = "Backend API"; 
                ProcessNames = @("python"); 
                Patterns = @("start_api.py", "uvicorn", "app.main", "app\\main");
                Description = "FastAPI 后端服务"
            }
            @{ 
                Name = "Nginx"; 
                ProcessNames = @("nginx"); 
                Patterns = @("nginx");
                Description = "Web 服务器"
            }
            @{ 
                Name = "Redis"; 
                ProcessNames = @("redis-server"); 
                Patterns = @("redis-server", "redis");
                Description = "缓存服务器"
            }
            @{ 
                Name = "MongoDB"; 
                ProcessNames = @("mongod"); 
                Patterns = @("mongod");
                Description = "数据库服务器"
            }
        )
        
        $foundCount = 0
        foreach ($procConfig in $processesToCheck) {
            $procName = $procConfig.Name
            $found = $false
            $foundPid = $null
            
            try {
                # 首先按进程名过滤（提高效率）
                $candidateProcesses = @()
                foreach ($procNamePattern in $procConfig.ProcessNames) {
                    $candidateProcesses += Get-Process -Name $procNamePattern -ErrorAction SilentlyContinue
                }
                
                # 如果没有找到同名进程，检查所有进程
                if ($candidateProcesses.Count -eq 0) {
                    $candidateProcesses = Get-Process -ErrorAction SilentlyContinue
                }
                
                foreach ($proc in $candidateProcesses) {
                    $cmdLine = ""
                    try {
                        $cmdLine = (Get-WmiObject Win32_Process -Filter "ProcessId = $($proc.Id)" -ErrorAction SilentlyContinue).CommandLine
                    } catch {
                        # 如果 WMI 失败，尝试使用其他方法
                        try {
                            $cmdLine = (Get-CimInstance Win32_Process -Filter "ProcessId = $($proc.Id)" -ErrorAction SilentlyContinue).CommandLine
                        } catch {
                            # 忽略错误
                        }
                    }
                    
                    $procInfo = "$($proc.ProcessName) $cmdLine".ToLower()
                    
                    foreach ($pattern in $procConfig.Patterns) {
                        if ($procInfo -like "*$($pattern.ToLower())*") {
                            $foundPid = $proc.Id
                            $found = $true
                            break
                        }
                    }
                    if ($found) { break }
                }
                
                if ($found) {
                    Write-Host "  ✅ $procName" -ForegroundColor Green -NoNewline
                    Write-Host " (PID: $foundPid)" -ForegroundColor Gray -NoNewline
                    Write-Host " - $($procConfig.Description)" -ForegroundColor DarkGray
                    $foundCount++
                } else {
                    Write-Host "  ❌ $procName" -ForegroundColor Red -NoNewline
                    Write-Host " (未运行)" -ForegroundColor Gray -NoNewline
                    Write-Host " - $($procConfig.Description)" -ForegroundColor DarkGray
                }
            } catch {
                Write-Host "  ⚠️  $procName" -ForegroundColor Yellow -NoNewline
                Write-Host " (检查失败: $_)" -ForegroundColor Gray
            }
        }
        
        Write-Host ""
        if ($foundCount -eq $processesToCheck.Count) {
            Write-Host "  ✅ 所有关键进程都在运行" -ForegroundColor Green
        } elseif ($foundCount -gt 0) {
            Write-Host "  ⚠️  部分进程未运行，请检查服务状态" -ForegroundColor Yellow
        } else {
            Write-Host "  ❌ 所有关键进程都未运行，请启动服务" -ForegroundColor Red
        }
        Write-Host ""
        Write-Host "  💡 提示:" -ForegroundColor Cyan
        Write-Host "     - 启动所有服务: scripts\installer\start_all.ps1" -ForegroundColor Gray
        Write-Host "     - 启动监控守护进程: scripts\monitor\start_monitor.ps1" -ForegroundColor Gray
        Write-Host "     - 监控守护进程会自动记录进程状态变化和退出信息" -ForegroundColor Gray
    }
    
    Write-Host ""
    Write-Host "💡 监控功能说明:" -ForegroundColor Cyan
    Write-Host "   📊 快速查看: 一键查看所有关键服务的运行状态" -ForegroundColor Gray
    Write-Host "   🔍 问题诊断: 发现服务异常退出时，记录退出代码和退出时间" -ForegroundColor Gray
    Write-Host "   📝 历史记录: 监控守护进程会记录进程状态变化历史" -ForegroundColor Gray
    Write-Host "   ⚠️  告警提示: 进程异常退出时自动告警，便于及时处理" -ForegroundColor Gray
    Write-Host ""
    Write-Host "💡 常用命令:" -ForegroundColor Cyan
    Write-Host "   - 查看详细日志: scripts\monitor\view_monitor.ps1" -ForegroundColor Gray
    Write-Host "   - 实时跟踪日志: scripts\monitor\view_monitor.ps1 -Follow" -ForegroundColor Gray
    Write-Host "   - 启动监控守护: scripts\monitor\start_monitor.ps1" -ForegroundColor Gray
    Write-Host "   - JSON格式输出: scripts\monitor\monitor_status.ps1 -Json" -ForegroundColor Gray
}
