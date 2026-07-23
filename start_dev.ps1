# TradingAgents-CN Development Startup Script
# 支持按服务分别启动，方便调试
#
# 用法:
#   .\start_dev.ps1 docker 3.0          # 启动 v3.0 的 MongoDB+Redis
#   .\start_dev.ps1 backend 3.0         # 启动 v3.0 后端
#   .\start_dev.ps1 frontend 3.0        # 启动 v3.0 前端
#   .\start_dev.ps1 all 3.0             # 启动 v3.0 全部服务
#   .\start_dev.ps1 status              # 查看各版本端口配置
#
# 京东云合作版（独立容器、独立端口、独立数据卷，与 v3.0 完全隔离）:
#   .\start_dev.ps1 docker jdyun        # 启动 jdyun 的 MongoDB(27022)+Redis(6383)
#   .\start_dev.ps1 backend jdyun       # 以京东云模式启动后端（自动设置 JDYUN_MODE=true）
#   .\start_dev.ps1 frontend jdyun      # 以京东云模式启动前端（自动 --mode jdyun）
#   .\start_dev.ps1 all jdyun           # 以京东云模式启动全部服务
#
# 京东云模式说明:
#   - 后端: 设置 JDYUN_MODE=true，启用京东云短路逻辑和API端点保护
#   - 前端: 使用 --mode jdyun 启动 Vite，加载 frontend/.env.jdyun
#   - 配置: 京东云相关参数(OPENAI_API_BASE/KEY/MODEL、TUSHARE_TOKEN等)从 .env 读取
#   - 用户无需在界面配置大模型和数据源，全部通过环境变量注入
#   - 独立 Docker 项目名 ta-jdyun，数据卷与 v3.0(ta-v3) 完全隔离

[CmdletBinding()]
param(
    [Parameter(Position=0)]
    [ValidateSet("docker", "backend", "frontend", "all", "status", $null)]
    [string]$Command,
    [Parameter(Position=1)]
    [ValidateSet("2.0", "2.1", "3.0", "jdyun", $null)]
    [string]$Version,
    [int]$BackendPort = 0,
    [switch]$Jdyun,
    [switch]$Help
)

# 版本端口映射（jdyun 使用独立端口和数据卷，与 v3.0 完全隔离）
$VersionConfig = @{
    "2.0" = @{ Project="ta-v201"; MongoDB=27017; Redis=6379; Backend=8000; Frontend=3000 }
    "2.1" = @{ Project="ta-v210"; MongoDB=27018; Redis=6380; Backend=8001; Frontend=3001 }
    "3.0" = @{ Project="ta-v3";   MongoDB=27019; Redis=6381; Backend=8002; Frontend=3002 }
    "jdyun" = @{ Project="ta-jdyun"; MongoDB=27022; Redis=6383; Backend=8003; Frontend=3003 }
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
    Write-Host "Versions:" -ForegroundColor Yellow
    Write-Host "  2.0    v2.0.1 开发环境"
    Write-Host "  2.1    v2.1.0 开发环境"
    Write-Host "  3.0    v3.0 开发环境（主线）"
    Write-Host "  jdyun  京东云合作版（独立容器/端口/数据卷，自动启用 JDYUN_MODE）"
    Write-Host ""
    Write-Host "Examples:" -ForegroundColor Yellow
    Write-Host "  .\start_dev.ps1 docker 3.0            # 终端1: MongoDB+Redis"
    Write-Host "  .\start_dev.ps1 backend 3.0           # 终端2: 后端 http://localhost:8002"
    Write-Host "  .\start_dev.ps1 frontend 3.0          # 终端3: 前端 http://localhost:3002"
    Write-Host "  .\start_dev.ps1 docker jdyun          # 京东云: MongoDB(27022)+Redis(6383)"
    Write-Host "  .\start_dev.ps1 backend jdyun         # 京东云后端 http://localhost:8003"
    Write-Host "  .\start_dev.ps1 frontend jdyun        # 京东云前端 http://localhost:3003"
    Write-Host ""
    Write-Host "Version Ports:" -ForegroundColor Yellow
    Write-Host "  2.0:   MongoDB=27017 Redis=6379 Backend=8000 Frontend=3000"
    Write-Host "  2.1:   MongoDB=27018 Redis=6380 Backend=8001 Frontend=3001"
    Write-Host "  3.0:   MongoDB=27019 Redis=6381 Backend=8002 Frontend=3002"
    Write-Host "  jdyun: MongoDB=27022 Redis=6383 Backend=8003 Frontend=3003"
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

# 版本 jdyun 自动启用京东云模式（无需额外传 --jdyun 开关）
# --jdyun 开关仍保留向后兼容（如 start_dev.ps1 backend 3.0 --jdyun）
if ($Version -eq "jdyun") {
    $Jdyun = $true
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
    foreach ($v in @("2.0", "2.1", "3.0", "jdyun")) {
        $c = $VersionConfig[$v]
        $label = if ($v -eq "jdyun") { "jdyun (京东云)" } else { "v$($v)" }
        Write-Host "  ${label}:" -ForegroundColor White
        Write-Host "    MongoDB:  $($c.MongoDB)" -ForegroundColor Gray
        Write-Host "    Redis:    $($c.Redis)" -ForegroundColor Gray
        Write-Host "    Backend:  $($c.Backend)  -> http://127.0.0.1:$($c.Backend)" -ForegroundColor Gray
        Write-Host "    Frontend: $($c.Frontend) -> http://localhost:$($c.Frontend)" -ForegroundColor Gray
        Write-Host ""
    }

    Write-Host "Docker 容器:" -ForegroundColor Yellow
    docker ps --filter "name=ta-" --format "  {{.Names}}`t{{.Ports}}`t{{.Status}}" 2>$null
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
    $prevEAP = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    docker-compose -p $DockerProject -f $composeFile up -d 2>&1 | ForEach-Object { Write-Host "  $_" -ForegroundColor Gray }
    $ErrorActionPreference = $prevEAP

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

    # 京东云模式：设置 JDYUN_MODE=true 开关和 DOTENV_FILE=.env.jdyun
    # 京东云参数(OPENAI_API_BASE/KEY/MODEL、EMBEDDING_MODEL、TUSHARE_TOKEN)由 .env.jdyun 提供
    if ($Jdyun) {
        $env:JDYUN_MODE = "true"
        $env:DOTENV_FILE = ".env.jdyun"
        Write-Host "[Jdyun] 京东云合作版模式已启用" -ForegroundColor Magenta
        Write-Host "  - 配置管理界面已隐藏，配置通过环境变量注入" -ForegroundColor Gray
        Write-Host "  - 大模型/数据源 API 端点已设为只读" -ForegroundColor Gray
        Write-Host "  - 环境文件: .env.jdyun（后端自动加载）" -ForegroundColor Gray
        Write-Host "  - 请确保 .env.jdyun 中已配置 OPENAI_API_BASE / OPENAI_API_KEY / OPENAI_MODEL / TUSHARE_TOKEN" -ForegroundColor Gray
        Write-Host "  - MongoDB: localhost:$MongoDBPort  Redis: localhost:$RedisPort" -ForegroundColor Gray
        Write-Host ""
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
        param($pythonExe, $backendPort, $root, $mongoDBPort, $redisPort, $jdyunMode)
        Set-Location $root
        $env:PYTHONIOENCODING = "utf-8"
        $env:PYTHONUTF8 = "1"
        $env:PYTHONUNBUFFERED = "1"
        if ($mongoDBPort) { $env:MONGODB_PORT = $mongoDBPort }
        if ($redisPort) { $env:REDIS_PORT = $redisPort }
        if ($jdyunMode) {
            $env:JDYUN_MODE = "true"
            $env:DOTENV_FILE = ".env.jdyun"
        }
        & $pythonExe -m uvicorn app.main:app --host 127.0.0.1 --port $backendPort --log-level info
    } -ArgumentList $pythonExe, $BackendPort, $root, $(if ($Version) { "$MongoDBPort" } else { "" }), $(if ($Version) { "$RedisPort" } else { "" }), $([bool]$Jdyun)

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
        # 京东云模式：检查 .env.jdyun 是否存在
        $jdyunEnvFile = Join-Path $frontendDir ".env.jdyun"
        if ($Jdyun -and -not (Test-Path $jdyunEnvFile)) {
            Write-Host "[WARN] frontend\.env.jdyun not found, VITE_JDYUN_MODE will not be set" -ForegroundColor Yellow
            Write-Host "  Please create it with: VITE_JDYUN_MODE=true" -ForegroundColor Gray
        }

        Write-Host ""
        Write-Host "[Frontend] Starting Vite dev server..." -ForegroundColor Yellow
        Write-Host "  Port: $FrontendPort" -ForegroundColor Gray
        Write-Host "  URL:  http://localhost:$FrontendPort" -ForegroundColor Gray
        Write-Host "  API proxy -> http://localhost:$BackendPort" -ForegroundColor Gray
        if ($Jdyun) {
            Write-Host "  Mode: jdyun (loading .env.jdyun)" -ForegroundColor Magenta
        }
        Write-Host ""

        if ($Command -eq "frontend") {
            # 独立模式：前台运行
            $env:VITE_PORT = "$FrontendPort"
            $env:VITE_API_TARGET = "http://localhost:$BackendPort"
            Set-Location $frontendDir
            try {
                if ($Jdyun) {
                    npm run dev -- --mode jdyun
                } else {
                    npm run dev
                }
            } catch {
                Write-Host "[INFO] Frontend stopped" -ForegroundColor Yellow
            }
            exit 0
        }

        # all 模式：后台 Job
        $frontendJob = Start-Job -ScriptBlock {
            param($frontendDir, $frontendPort, $backendPort, $jdyunMode)
            $env:VITE_PORT = "$frontendPort"
            $env:VITE_API_TARGET = "http://localhost:$backendPort"
            Set-Location $frontendDir
            if ($jdyunMode) {
                npm run dev -- --mode jdyun
            } else {
                npm run dev
            }
        } -ArgumentList $frontendDir, $FrontendPort, $BackendPort, $([bool]$Jdyun)

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
    if ($Jdyun) {
        Write-Host "All services running (JDYUN MODE)" -ForegroundColor Magenta
    } else {
        Write-Host "All services running!" -ForegroundColor Green
    }
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "  Backend:  http://127.0.0.1:$BackendPort" -ForegroundColor White
    Write-Host "  Frontend: http://localhost:$FrontendPort" -ForegroundColor White
    Write-Host "  MongoDB:  localhost:$MongoDBPort" -ForegroundColor White
    Write-Host "  Redis:    localhost:$RedisPort" -ForegroundColor White
    if ($Jdyun) {
        Write-Host "  Mode:     京东云合作版" -ForegroundColor Magenta
    }
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
