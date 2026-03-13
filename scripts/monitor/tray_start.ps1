# TradingAgents-CN 托盘监控启动脚本
# 使用 pythonw 无控制台启动，随 start_all.ps1 一起运行

param()

$ErrorActionPreference = "Continue"

# 查找项目根目录
$root = $PSScriptRoot
$maxLevels = 3
$currentLevel = 0
while ($currentLevel -lt $maxLevels -and $root.Length -gt 3) {
    if ((Test-Path (Join-Path $root ".git")) -or
        (Test-Path (Join-Path $root "runtime\pids.json")) -or
        (Test-Path (Join-Path $root "vendors"))) {
        break
    }
    $root = Split-Path $root -Parent
    $currentLevel++
}

# 优先 pythonw（无控制台，GUI 应用推荐），其次 python.exe
$pythonExe = $null
foreach ($c in @(
    (Join-Path $root "vendors\python\pythonw.exe"),
    (Join-Path $root "vendors\python\python.exe"),
    (Join-Path $root "venv\Scripts\pythonw.exe"),
    (Join-Path $root "venv\Scripts\python.exe"),
    (Join-Path $root "env\Scripts\pythonw.exe"),
    (Join-Path $root "env\Scripts\python.exe")
)) {
    if (Test-Path $c) { $pythonExe = $c; break }
}
if (-not $pythonExe) { $pythonExe = "pythonw" }

$trayScript = Join-Path $root "scripts\monitor\tray_monitor.py"
if (-not (Test-Path $trayScript)) {
    Write-Host "托盘监控脚本未找到: $trayScript" -ForegroundColor Yellow
    exit 1
}

$logsDir = Join-Path $root "logs"
if (-not (Test-Path $logsDir)) { New-Item -ItemType Directory -Path $logsDir -Force | Out-Null }
$trayLog = Join-Path $logsDir "tray_monitor.log"

# 使用 UseShellExecute 启动，确保托盘进程在用户会话中运行
# 不使用 -WindowStyle Hidden，避免 GUI 托盘进程被创建到非交互桌面
try {
    Start-Process -FilePath $pythonExe -ArgumentList "`"$trayScript`"" -WorkingDirectory $root
} catch {
    "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] 托盘监控启动异常: $_" | Out-File -FilePath $trayLog -Encoding UTF8 -Append
    Write-Host "启动托盘监控失败: $_" -ForegroundColor Red
    exit 1
}
