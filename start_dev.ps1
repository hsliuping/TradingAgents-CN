# TradingAgents-CN Development Startup Script
# 支持按服务分别启动，方便调试
#
# 用法:
#   .\start_dev.ps1 docker 3.0          # 启动 v3.0 的 MongoDB+Redis
#   .\start_dev.ps1 backend 3.0         # 启动 v3.0 后端
#   .\start_dev.ps1 frontend 3.0        # 启动 v3.0 前端
#   .\start_dev.ps1 all 3.0             # 启动 v3.0 全部服务
#   .\start_dev.ps1 status              # 查看各版本端口配置

[CmdletBinding()]
param(
    [Parameter(Position=0)]
    [ValidateSet("docker", "backend", "frontend", "all", "status", $null)]
    [string]$Command,
    [Parameter(Position=1)]
    [ValidateSet("2.0", "2.1", "3.0", $null)]
    [string]$Version,
    [int]$BackendPort = 0,
    [switch]$Help
)

# 版本端口映射
$VersionConfig = @{
    "2.0" = @{ Project="ta-v201"; MongoDB=27017; Redis=6379; Backend=8000; Frontend=3000 }
    "2.1" = @{ Project="ta-v210"; MongoDB=27018; Redis=6380; Backend=8001; Frontend=3001 }
    "3.0" = @{ Project="ta-v3";   MongoDB=27019; Redis=6381; Backend=8002; Frontend=3002 }
}

if ($Help -or -not $Command) {
    Write-Host ""
    Write-Host "TradingAgents-CN Development Startup Script" -ForegroundColor Cyan
    Write-Host "============================================" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "Usage:" -ForegroundColor Yellow
    Write-Host "  .\start_dev.ps1 <command> [version]"
    Write-Host ""
    Write-Host "Commands:" -ForegroundColor Yellow
    Write-Host "  docker <version>     启动 MongoDB + Redis（Docker）"
    Write-Host "  backend <version>    启动后端（FastAPI + Uvicorn）"
    Write-Host "  frontend <version>   启动前端（Vite dev server）"
    Write-Host "  all <version>        启动全部服务"
    Write-Host "  status               查看各版本端口配置"
    Write-Host ""
    Write-Host "Examples:" -ForegroundColor Yellow
    Write-Host "  .\start_dev.ps1 docker 3.0       # 终端1: MongoDB+Redis"
    Write-Host "  .\start_dev.ps1 backend 3.0      # 终端2: 后端 http://localhost:8002"
    Write-Host "  .\start_dev.ps1 frontend 3.0     # 终端3: 前端 http://localhost:3002"
    Write-Host ""
    Write-Host "Version Ports:" -ForegroundColor Yellow
    Write-Host "  2.0: MongoDB=27017 Redis=6379 Backend=8000 Frontend=3000"
    Write-Host "  2.1: MongoDB=27018 Redis=6380 Backend=8001 Frontend=3001"
    Write-Host "  3.0: MongoDB=27019 Redis=6381 Backend=8002 Frontend=3002"
    Write-Host ""
    exit 0
}

$ErrorActionPreference = "Stop"
$root = $PSScriptRoot

# 解析版本配置
if ($Version) {
    $config = $VersionConfig[$Version]
    $MongoDBPort = $config.MongoDB
    $RedisPort = $config.Redis
    if ($BackendPort -eq 0) { $BackendPort = $config.Backend }
    $FrontendPort = $config.Frontend
    $DockerProject = $config.Project
} else {
    $MongoDBPort = 27017
    $RedisPort = 6379
    if ($BackendPort -eq 0) { $BackendPort = 8000 }
    $FrontendPort = 3000
    $DockerProject = "ta-debug"
}

# ==========================================
# status 子命令
# ==========================================
if ($Command -eq "status") {
    Write-Host ""
    Write-Host "=========================================" -ForegroundColor Cyan
    Write-Host "  开发环境端口配置" -ForegroundColor Cyan
    Write-Host "=========================================" -ForegroundColor Cyan
    Write-Host ""
    foreach ($v in @("2.0", "2.1", "3.0")) {
        $c = $VersionConfig[$v]
        Write-Host "  v$($v):" -ForegroundColor White
        Write-Host "    MongoDB:  $($c.MongoDB)" -ForegroundColor Gray
        Write-Host "    Redis:    $($c.Redis)" -ForegroundColor Gray
        Write-Host "    Backend:  $($c.Backend)  -> http://127.0.0.1:$($c.Backend)" -ForegroundColor Gray
        Write-Host "    Frontend: $($c.Frontend) -> http://localhost:$($c.Frontend)" -ForegroundColor Gray
        Write-Host ""
    }

    Write-Host "Docker 容器:" -ForegroundColor Yellow
    docker ps --filter "name=ta-v" --format "  {{.Names}}`t{{.Ports}}`t{{.Status}}" 2>$null
    if (-not $?) {
        Write-Host "  (Docker 未运行或无相关容器)" -ForegroundColor Gray
    }
    Write-Host ""
    exit 0
}

# ==========================================
# docker 子命令
# ==========================================
if ($Command -eq "docker" -or $Command -eq "all") {
    $composeFile = Join-Path $root "docker\docker-compose.dev.yml"
    if (-not (Test-Path $composeFile)) {
        Write-Host "[ERROR] docker-compose.dev.yml not found: $composeFile" -ForegroundColor Red
        exit 1
    }

    Write-Host ""
    Write-Host "[Docker] Starting MongoDB ($MongoDBPort) + Redis ($RedisPort)..." -ForegroundColor Yellow
    Write-Host "  Project: $DockerProject" -ForegroundColor Gray
    Write-Host ""

    $env:MONGODB_PORT = "$MongoDBPort"
    $env:REDIS_PORT = "$RedisPort"
    docker-compose -p $DockerProject -f $composeFile up -d 2>&1 | ForEach-Object { Write-Host "  $_" -ForegroundColor Gray }

    Start-Sleep -Seconds 3
    $running = docker-compose -p $DockerProject -f $composeFile ps -q 2>$null
    if ($running) {
        Write-Host ""
        Write-Host "[OK] Docker services started" -ForegroundColor Green
        Write-Host "  MongoDB: mongodb://admin:tradingagents123@localhost:$MongoDBPort/tradingagents?authSource=admin" -ForegroundColor Gray
        Write-Host "  Redis:   redis://:tradingagents123@localhost:$RedisPort/0" -ForegroundColor Gray
    } else {
        Write-Host "[WARN] Docker services may not have started correctly" -ForegroundColor Yellow
    }
    Write-Host ""

    if ($Command -eq "docker") { exit 0 }
}

# ==========================================
# backend 子命令
# ==========================================
if ($Command -eq "backend" -or $Command -eq "all") {
    # 设置环境变量（版本指定时覆盖 .env 默认值）
    if ($Version) {
        $env:PORT = "$BackendPort"
        $env:HOST = "127.0.0.1"
        $env:MONGODB_HOST = "localhost"
        $env:MONGODB_PORT = "$MongoDBPort"
        $env:REDIS_HOST = "localhost"
        $env:REDIS_PORT = "$RedisPort"
    }

    # 检测 Python
    $pythonExe = $null
    $pythonCandidates = @()

    if ($env:TRADINGAGENTS_PYTHON_EXE -and (Test-Path $env:TRADINGAGENTS_PYTHON_EXE)) {
        $pythonCandidates += $env:TRADINGAGENTS_PYTHON_EXE
    }
    $pythonCandidates += @(
        (Join-Path $root "env\Scripts\python.exe"),
        (Join-Path $root "venv\Scripts\python.exe"),
        (Join-Path $root "vendors\python\python.exe"),
        (Join-Path $root "release\TradingAgentsCN-portable\vendors\python\python.exe")
    )

    foreach ($path in $pythonCandidates) {
        if (Test-Path $path) {
            $pythonExe = $path
            break
        }
    }
    if (-not $pythonExe) { $pythonExe = "python" }

    $env:PYTHONIOENCODING = "utf-8"
    $env:PYTHONUTF8 = "1"
    $env:PYTHONUNBUFFERED = "1"

    # HuggingFace 模型缓存目录（项目内，便于统一管理）
    $env:HF_HOME = Join-Path $root "data\models\huggingface"
    $env:HF_HUB_OFFLINE = "1"  # 离线模式，不联网验证模型文件

    Write-Host ""
    Write-Host "[Backend] Starting FastAPI + Uvicorn..." -ForegroundColor Yellow
    Write-Host "  Python: $pythonExe ($(& $pythonExe --version 2>&1))" -ForegroundColor Gray
    Write-Host "  Port:   $BackendPort" -ForegroundColor Gray
    Write-Host "  URL:    http://127.0.0.1:$BackendPort" -ForegroundColor Gray
    Write-Host "  Docs:   http://127.0.0.1:$BackendPort/docs" -ForegroundColor Gray
    Write-Host ""

    if ($Command -eq "backend") {
        # 独立模式：前台运行，Ctrl+C 直接退出
        try {
            & $pythonExe -m uvicorn app.main:app --host 127.0.0.1 --port $BackendPort --log-level info
        } catch {
            Write-Host "[INFO] Backend stopped" -ForegroundColor Yellow
        }
        exit 0
    }

    # all 模式：后台 Job
    $backendJob = Start-Job -ScriptBlock {
        param($pythonExe, $backendPort, $root, $mongoDBPort, $redisPort)
        Set-Location $root
        $env:PYTHONIOENCODING = "utf-8"
        $env:PYTHONUTF8 = "1"
        $env:PYTHONUNBUFFERED = "1"
        $env:HF_HOME = Join-Path $root "data\models\huggingface"
        $env:HF_HUB_OFFLINE = "1"
        if ($mongoDBPort) { $env:MONGODB_PORT = $mongoDBPort }
        if ($redisPort) { $env:REDIS_PORT = $redisPort }
        & $pythonExe -m uvicorn app.main:app --host 127.0.0.1 --port $backendPort --log-level info
    } -ArgumentList $pythonExe, $BackendPort, $root, $(if ($Version) { "$MongoDBPort" } else { "" }), $(if ($Version) { "$RedisPort" } else { "" })

    $jobs = @($backendJob)
    Write-Host "[OK] Backend started (Job ID: $($backendJob.Id))" -ForegroundColor Green
    Write-Host ""
}

# ==========================================
# frontend 子命令
# ==========================================
if ($Command -eq "frontend" -or $Command -eq "all") {
    $frontendDir = Join-Path $root "frontend"
    if (-not (Test-Path $frontendDir)) {
        Write-Host "[ERROR] Frontend directory not found: $frontendDir" -ForegroundColor Red
        if ($Command -eq "frontend") { exit 1 }
    } else {
        Write-Host ""
        Write-Host "[Frontend] Starting Vite dev server..." -ForegroundColor Yellow
        Write-Host "  Port: $FrontendPort" -ForegroundColor Gray
        Write-Host "  URL:  http://localhost:$FrontendPort" -ForegroundColor Gray
        Write-Host "  API proxy -> http://localhost:$BackendPort" -ForegroundColor Gray
        Write-Host ""

        if ($Command -eq "frontend") {
            # 独立模式：前台运行
            $env:VITE_PORT = "$FrontendPort"
            $env:VITE_API_TARGET = "http://localhost:$BackendPort"
            Set-Location $frontendDir
            try {
                npm run dev
            } catch {
                Write-Host "[INFO] Frontend stopped" -ForegroundColor Yellow
            }
            exit 0
        }

        # all 模式：后台 Job
        $frontendJob = Start-Job -ScriptBlock {
            param($frontendDir, $frontendPort, $backendPort)
            $env:VITE_PORT = "$frontendPort"
            $env:VITE_API_TARGET = "http://localhost:$backendPort"
            Set-Location $frontendDir
            npm run dev
        } -ArgumentList $frontendDir, $FrontendPort, $BackendPort

        $jobs += $frontendJob
        Write-Host "[OK] Frontend started (Job ID: $($frontendJob.Id))" -ForegroundColor Green
        Write-Host ""
    }
}

# ==========================================
# all 模式：监控后台 Job
# ==========================================
if ($Command -eq "all") {
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host "All services running!" -ForegroundColor Green
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "  Backend:  http://127.0.0.1:$BackendPort" -ForegroundColor White
    Write-Host "  Frontend: http://localhost:$FrontendPort" -ForegroundColor White
    Write-Host "  MongoDB:  localhost:$MongoDBPort" -ForegroundColor White
    Write-Host "  Redis:    localhost:$RedisPort" -ForegroundColor White
    Write-Host ""
    Write-Host "Press Ctrl+C to stop all services" -ForegroundColor Yellow
    Write-Host ""

    try {
        while ($true) {
            foreach ($job in $jobs) {
                $output = Receive-Job -Job $job -ErrorAction SilentlyContinue
                if ($output) { Write-Host $output }
                if ($job.State -eq "Failed") {
                    Write-Host "[ERROR] Job $($job.Id) failed!" -ForegroundColor Red
                    $jobError = Receive-Job -Job $job -ErrorAction SilentlyContinue
                    Write-Host $jobError -ForegroundColor Red
                }
            }
            Start-Sleep -Milliseconds 100
        }
    } catch {
        Write-Host ""
        Write-Host "[INFO] Shutting down..." -ForegroundColor Yellow
    } finally {
        foreach ($job in $jobs) {
            if ($job.State -eq "Running") {
                Write-Host "Stopping Job $($job.Id)..." -ForegroundColor Gray
                Stop-Job -Job $job
                Remove-Job -Job $job -Force
            }
        }
        Write-Host "[OK] All processes stopped" -ForegroundColor Green
    }
}
