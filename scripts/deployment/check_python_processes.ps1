# ============================================================================
# Check Python Processes
# ============================================================================
# 检查是否有正在运行的 Python 进程，避免文件锁定问题
# ============================================================================

param(
    [switch]$Force = $false,
    [switch]$KillAll = $false
)

$ErrorActionPreference = "Stop"

Write-Host "============================================================================" -ForegroundColor Cyan
Write-Host "  Check Python Processes" -ForegroundColor Cyan
Write-Host "============================================================================" -ForegroundColor Cyan
Write-Host ""

# 查找所有 Python 进程
$pythonProcesses = Get-Process -Name "python*" -ErrorAction SilentlyContinue

if (-not $pythonProcesses) {
    Write-Host "✅ No Python processes found" -ForegroundColor Green
    Write-Host ""
    Write-Host "Safe to proceed with build" -ForegroundColor White
    exit 0
}

# 显示进程信息
Write-Host "⚠️  Found $($pythonProcesses.Count) running Python process(es):" -ForegroundColor Yellow
Write-Host ""

$pythonProcesses | Format-Table @(
    @{Label="PID"; Expression={$_.Id}; Width=8},
    @{Label="Name"; Expression={$_.ProcessName}; Width=20},
    @{Label="Start Time"; Expression={$_.StartTime.ToString("yyyy-MM-dd HH:mm:ss")}; Width=20},
    @{Label="CPU (s)"; Expression={[Math]::Round($_.CPU, 2)}; Width=10},
    @{Label="Memory (MB)"; Expression={[Math]::Round($_.WorkingSet64 / 1MB, 2)}; Width=12}
) -AutoSize

Write-Host ""
Write-Host "These processes may lock .pyd files and cause build to hang!" -ForegroundColor Red
Write-Host ""

# 如果指定了 -KillAll，直接终止所有进程
if ($KillAll) {
    Write-Host "Killing all Python processes..." -ForegroundColor Yellow
    Write-Host ""
    
    foreach ($process in $pythonProcesses) {
        try {
            Stop-Process -Id $process.Id -Force
            Write-Host "  ✅ Killed: $($process.ProcessName) (PID: $($process.Id))" -ForegroundColor Green
        } catch {
            Write-Host "  ❌ Failed to kill: $($process.ProcessName) (PID: $($process.Id))" -ForegroundColor Red
        }
    }
    
    Write-Host ""
    Write-Host "✅ All Python processes terminated" -ForegroundColor Green
    exit 0
}

# 提供操作建议
Write-Host "Recommended actions:" -ForegroundColor White
Write-Host ""
Write-Host "  1. Stop FastAPI server:" -ForegroundColor Yellow
Write-Host "     - Press Ctrl+C in the terminal running the server" -ForegroundColor Gray
Write-Host ""
Write-Host "  2. Close Jupyter notebooks:" -ForegroundColor Yellow
Write-Host "     - Save and close all notebooks" -ForegroundColor Gray
Write-Host "     - Shutdown Jupyter server" -ForegroundColor Gray
Write-Host ""
Write-Host "  3. Exit Python interactive shells:" -ForegroundColor Yellow
Write-Host "     - Type exit() or press Ctrl+Z" -ForegroundColor Gray
Write-Host ""
Write-Host "  4. Kill all Python processes (use with caution):" -ForegroundColor Yellow
Write-Host "     .\scripts\deployment\check_python_processes.ps1 -KillAll" -ForegroundColor Gray
Write-Host ""

# 如果指定了 -Force，继续执行
if ($Force) {
    Write-Host "⚠️  Continuing anyway (--Force specified)..." -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Build may hang if files are locked!" -ForegroundColor Red
    exit 0
}

# 询问用户是否继续
Write-Host "============================================================================" -ForegroundColor Cyan
Write-Host ""
$response = Read-Host "Do you want to continue anyway? (y/N)"

if ($response -eq "y" -or $response -eq "Y") {
    Write-Host ""
    Write-Host "⚠️  Continuing with build..." -ForegroundColor Yellow
    Write-Host "If build hangs, press Ctrl+C and kill Python processes" -ForegroundColor Yellow
    exit 0
} else {
    Write-Host ""
    Write-Host "Build cancelled" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Please close Python processes and try again" -ForegroundColor White
    exit 1
}

