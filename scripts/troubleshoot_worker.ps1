# ============================================================================
# Worker 故障排查脚本
# ============================================================================
# 用于诊断 Worker 进程退出的原因
# ============================================================================

param(
    [switch]$TestStart  # 测试启动 Worker
)

$root = $PSScriptRoot | Split-Path
$ErrorActionPreference = "Continue"

Write-Host "================================================================" -ForegroundColor Cyan
Write-Host "  Worker 故障排查" -ForegroundColor Cyan
Write-Host "================================================================" -ForegroundColor Cyan
Write-Host ""

# 1. 检查 Worker 模块是否存在
Write-Host "[1/6] 检查 Worker 模块..." -ForegroundColor Yellow
$workerModule = Join-Path $root "app\worker\__main__.py"
if (Test-Path $workerModule) {
    Write-Host "  [OK] Worker 模块存在: $workerModule" -ForegroundColor Green
} else {
    Write-Host "  [ERROR] Worker 模块不存在: $workerModule" -ForegroundColor Red
    Write-Host "  这是 Worker 无法启动的主要原因！" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "  解决方案:" -ForegroundColor Cyan
    Write-Host "    从源代码复制 app\worker 目录到安装目录" -ForegroundColor White
    exit 1
}

# 2. 检查日志文件
Write-Host ""
Write-Host "[2/6] 检查日志文件..." -ForegroundColor Yellow
$logFiles = @(
    "logs\worker.log",
    "logs\error.log",
    "logs\tradingagents.log"
)

foreach ($logFile in $logFiles) {
    $fullPath = Join-Path $root $logFile
    if (Test-Path $fullPath) {
        $size = (Get-Item $fullPath).Length
        $lastWrite = (Get-Item $fullPath).LastWriteTime
        Write-Host "  [OK] $logFile (大小: $size bytes, 修改: $lastWrite)" -ForegroundColor Green
        
        # 显示最后 20 行
        Write-Host "      最后 20 行:" -ForegroundColor Gray
        Get-Content $fullPath -Tail 20 | ForEach-Object {
            Write-Host "        $_" -ForegroundColor Gray
        }
        Write-Host ""
    } else {
        Write-Host "  [WARN] $logFile 不存在" -ForegroundColor Yellow
    }
}

# 3. 检查 Python 环境
Write-Host ""
Write-Host "[3/6] 检查 Python 环境..." -ForegroundColor Yellow
$pythonExe = Join-Path $root "vendors\python\python.exe"
if (-not (Test-Path $pythonExe)) {
    $pythonExe = Join-Path $root "venv\Scripts\python.exe"
}

if (Test-Path $pythonExe) {
    Write-Host "  [OK] Python: $pythonExe" -ForegroundColor Green
    $version = & $pythonExe --version 2>&1
    Write-Host "  版本: $version" -ForegroundColor Gray
} else {
    Write-Host "  [ERROR] Python 不存在" -ForegroundColor Red
    exit 1
}

# 4. 检查依赖包
Write-Host ""
Write-Host "[4/6] 检查关键依赖包..." -ForegroundColor Yellow
$packages = @("pymongo", "redis", "celery", "motor")
foreach ($pkg in $packages) {
    $result = & $pythonExe -c "import $pkg; print($pkg.__version__)" 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  [OK] $pkg : $result" -ForegroundColor Green
    } else {
        Write-Host "  [ERROR] $pkg : 未安装或导入失败" -ForegroundColor Red
    }
}

# 5. 检查数据库连接
Write-Host ""
Write-Host "[5/6] 检查数据库连接..." -ForegroundColor Yellow

# 检查 MongoDB
$mongoRunning = Get-Process -Name "mongod" -ErrorAction SilentlyContinue
if ($mongoRunning) {
    Write-Host "  [OK] MongoDB 进程运行中 (PID: $($mongoRunning.Id))" -ForegroundColor Green
} else {
    Write-Host "  [ERROR] MongoDB 进程未运行" -ForegroundColor Red
}

# 检查 Redis
$redisRunning = Get-Process -Name "redis-server" -ErrorAction SilentlyContinue
if ($redisRunning) {
    Write-Host "  [OK] Redis 进程运行中 (PID: $($redisRunning.Id))" -ForegroundColor Green
} else {
    Write-Host "  [ERROR] Redis 进程未运行" -ForegroundColor Red
}

# 6. 测试启动 Worker
if ($TestStart) {
    Write-Host ""
    Write-Host "[6/6] 测试启动 Worker (10 秒)..." -ForegroundColor Yellow
    Write-Host "  按 Ctrl+C 可以提前停止" -ForegroundColor Gray
    Write-Host ""
    
    try {
        & $pythonExe -m app.worker
    } catch {
        Write-Host "  [ERROR] Worker 启动失败: $_" -ForegroundColor Red
    }
} else {
    Write-Host ""
    Write-Host "[6/6] 跳过测试启动 (使用 -TestStart 参数启用)" -ForegroundColor Gray
}

Write-Host ""
Write-Host "================================================================" -ForegroundColor Cyan
Write-Host "  排查完成" -ForegroundColor Cyan
Write-Host "================================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "下一步:" -ForegroundColor Yellow
Write-Host "  1. 如果 Worker 模块不存在，需要复制 app\worker 目录" -ForegroundColor White
Write-Host "  2. 查看上面的日志文件，找到错误信息" -ForegroundColor White
Write-Host "  3. 使用 -TestStart 参数测试启动 Worker" -ForegroundColor White
Write-Host "  4. 检查 .env 文件中的数据库连接配置" -ForegroundColor White
Write-Host ""

