# TradingAgents-CN Pro - 一键部署脚本 (Windows PowerShell)
# 版本: v1.0.0
# 用途: 自动下载配置文件、创建目录、启动 Docker 服务

# 设置错误时停止
$ErrorActionPreference = "Stop"

# 配置
$NGINX_CONFIG_URL = "https://www.tradingagentscn.com/docker/nginx.conf"
$DOCKER_COMPOSE_URL = "https://www.tradingagentscn.com/docker/docker-compose.compiled.yml"
$ENV_DOCKER_URL = "https://www.tradingagentscn.com/docker/.env.docker"
$DOCKER_COMPOSE_FILE = "docker-compose.compiled.yml"

# 默认端口配置
$DEFAULT_NGINX_PORT = 8082
$DEFAULT_MONGODB_PORT = 27017
$DEFAULT_REDIS_PORT = 6379
$DEFAULT_BACKEND_PORT = 8000

# 端口变量（全局）
$script:NGINX_PORT = $DEFAULT_NGINX_PORT
$script:MONGODB_PORT = $DEFAULT_MONGODB_PORT
$script:REDIS_PORT = $DEFAULT_REDIS_PORT
$script:BACKEND_PORT = $DEFAULT_BACKEND_PORT

# 打印带颜色的消息
function Print-Info {
    param([string]$Message)
    Write-Host "ℹ️  $Message" -ForegroundColor Blue
}

function Print-Success {
    param([string]$Message)
    Write-Host "✅ $Message" -ForegroundColor Green
}

function Print-Warning {
    param([string]$Message)
    Write-Host "⚠️  $Message" -ForegroundColor Yellow
}

function Print-Error {
    param([string]$Message)
    Write-Host "❌ $Message" -ForegroundColor Red
}

# 打印标题
function Print-Header {
    Write-Host ""
    Write-Host "========================================" -ForegroundColor Blue
    Write-Host "  TradingAgents-CN Pro 一键部署脚本" -ForegroundColor Blue
    Write-Host "========================================" -ForegroundColor Blue
    Write-Host ""
}

# 检查命令是否存在
function Test-Command {
    param([string]$Command)
    
    $exists = $null -ne (Get-Command $Command -ErrorAction SilentlyContinue)
    return $exists
}

# 检查依赖
function Test-Dependencies {
    Print-Info "检查依赖..."
    
    if (-not (Test-Command "docker")) {
        Print-Error "Docker 未安装，请先安装 Docker Desktop"
        Print-Info "下载地址: https://www.docker.com/products/docker-desktop"
        exit 1
    }
    
    if (-not (Test-Command "docker-compose")) {
        Print-Error "docker-compose 未安装"
        Print-Info "Docker Desktop 应该已包含 docker-compose"
        exit 1
    }
    
    Print-Success "依赖检查通过"
}

# 询问端口配置
function Set-PortConfiguration {
    Print-Info "配置服务端口..."
    Write-Host ""

    # Nginx 端口
    Print-Info "Nginx 前端服务端口 (默认: $DEFAULT_NGINX_PORT)"
    $userInput = Read-Host "请输入端口 [直接回车使用默认]"
    if ([string]::IsNullOrWhiteSpace($userInput)) {
        $script:NGINX_PORT = $DEFAULT_NGINX_PORT
    } else {
        $script:NGINX_PORT = $userInput
    }
    Print-Success "Nginx 端口: $($script:NGINX_PORT)"

    # MongoDB 端口
    Print-Info "MongoDB 数据库端口 (默认: $DEFAULT_MONGODB_PORT)"
    $userInput = Read-Host "请输入端口 [直接回车使用默认]"
    if ([string]::IsNullOrWhiteSpace($userInput)) {
        $script:MONGODB_PORT = $DEFAULT_MONGODB_PORT
    } else {
        $script:MONGODB_PORT = $userInput
    }
    Print-Success "MongoDB 端口: $($script:MONGODB_PORT)"

    # Redis 端口
    Print-Info "Redis 缓存端口 (默认: $DEFAULT_REDIS_PORT)"
    $userInput = Read-Host "请输入端口 [直接回车使用默认]"
    if ([string]::IsNullOrWhiteSpace($userInput)) {
        $script:REDIS_PORT = $DEFAULT_REDIS_PORT
    } else {
        $script:REDIS_PORT = $userInput
    }
    Print-Success "Redis 端口: $($script:REDIS_PORT)"

    # Backend 端口
    Print-Info "Backend API 端口 (默认: $DEFAULT_BACKEND_PORT)"
    $userInput = Read-Host "请输入端口 [直接回车使用默认]"
    if ([string]::IsNullOrWhiteSpace($userInput)) {
        $script:BACKEND_PORT = $DEFAULT_BACKEND_PORT
    } else {
        $script:BACKEND_PORT = $userInput
    }
    Print-Success "Backend 端口: $($script:BACKEND_PORT)"

    Write-Host ""
    Print-Success "端口配置完成！"
    Write-Host ""
}

# 创建必需的目录
function New-RequiredDirectories {
    Print-Info "创建必需的目录..."

    New-Item -ItemType Directory -Force -Path "nginx" | Out-Null
    Print-Success "创建 nginx\ 目录"

    # logs、data、runtime 会由 Docker 自动创建，但我们也可以提前创建
    New-Item -ItemType Directory -Force -Path "logs" | Out-Null
    New-Item -ItemType Directory -Force -Path "data" | Out-Null
    New-Item -ItemType Directory -Force -Path "runtime" | Out-Null
    Print-Success "创建 logs\、data\、runtime\ 目录"
}

# 下载 docker-compose.compiled.yml 文件
function Get-DockerCompose {
    Print-Info "下载 Docker Compose 配置文件..."

    if (Test-Path $DOCKER_COMPOSE_FILE) {
        Print-Warning "$DOCKER_COMPOSE_FILE 已存在，是否覆盖？(Y/N)"
        $response = Read-Host
        if ($response -notmatch '^[Yy]$') {
            Print-Info "跳过下载 Docker Compose 配置"
            return
        }
    }

    try {
        Invoke-WebRequest -Uri $DOCKER_COMPOSE_URL -OutFile $DOCKER_COMPOSE_FILE
        Print-Success "Docker Compose 配置文件下载成功"
    }
    catch {
        Print-Error "Docker Compose 配置文件下载失败: $_"
        Print-Info "请手动下载: $DOCKER_COMPOSE_URL"
        exit 1
    }
}

# 下载 nginx 配置文件
function Get-NginxConfig {
    Print-Info "下载 Nginx 配置文件..."

    $nginxConfigPath = "nginx\nginx.conf"

    if (Test-Path $nginxConfigPath) {
        Print-Warning "nginx\nginx.conf 已存在，是否覆盖？(Y/N)"
        $response = Read-Host
        if ($response -notmatch '^[Yy]$') {
            Print-Info "跳过下载 Nginx 配置"
            return
        }
    }

    try {
        Invoke-WebRequest -Uri $NGINX_CONFIG_URL -OutFile $nginxConfigPath
        Print-Success "Nginx 配置文件下载成功"
    }
    catch {
        Print-Error "Nginx 配置文件下载失败: $_"
        Print-Info "请手动下载: $NGINX_CONFIG_URL"
        exit 1
    }
}

# 下载 .env 配置文件
function Get-EnvFile {
    Print-Info "下载 .env 配置文件..."

    if (Test-Path ".env") {
        Print-Warning ".env 文件已存在，是否覆盖？(Y/N)"
        $response = Read-Host
        if ($response -notmatch '^[Yy]$') {
            Print-Info "跳过下载 .env 配置"
            return
        }
    }

    try {
        Invoke-WebRequest -Uri $ENV_DOCKER_URL -OutFile ".env"
        Print-Success ".env 配置文件下载成功"
    }
    catch {
        Print-Error ".env 配置文件下载失败: $_"
        Print-Info "请手动下载: $ENV_DOCKER_URL"
        exit 1
    }
}

# 更新端口配置到 docker-compose.yml
function Update-DockerComposePorts {
    Print-Info "更新 Docker Compose 端口配置..."

    # 读取文件内容
    $content = Get-Content $DOCKER_COMPOSE_FILE -Raw

    # 替换端口配置
    $content = $content -replace '"27017:27017"', "`"$($script:MONGODB_PORT):27017`""
    $content = $content -replace '"6379:6379"', "`"$($script:REDIS_PORT):6379`""
    $content = $content -replace '"8082:8082"', "`"$($script:NGINX_PORT):8082`""

    # 写回文件
    $content | Set-Content $DOCKER_COMPOSE_FILE -NoNewline

    Print-Success "Docker Compose 端口配置已更新"
}

# 更新端口配置到 .env 文件
function Update-EnvPorts {
    Print-Info "更新 .env 端口配置..."

    # 读取文件内容
    $content = Get-Content ".env"

    # 替换端口配置
    $content = $content -replace '^MONGODB_PORT=.*', "MONGODB_PORT=$($script:MONGODB_PORT)"
    $content = $content -replace '^REDIS_PORT=.*', "REDIS_PORT=$($script:REDIS_PORT)"
    $content = $content -replace '^PORT=.*', "PORT=$($script:BACKEND_PORT)"
    $content = $content -replace '^NGINX_PORT=.*', "NGINX_PORT=$($script:NGINX_PORT)"

    # 写回文件
    $content | Set-Content ".env"

    Print-Success ".env 端口配置已更新"
}

# 检查 .env 文件是否存在
function Test-EnvFile {
    Print-Info "检查环境变量文件..."

    if (-not (Test-Path ".env")) {
        Print-Error ".env 文件不存在"
        Print-Info "请确保已下载 .env 配置文件"
        exit 1
    }
    else {
        Print-Success ".env 文件已存在"
    }
}

# 启动 Docker 服务
function Start-DockerServices {
    Print-Info "启动 Docker 服务..."
    
    if (-not (Test-Path $DOCKER_COMPOSE_FILE)) {
        Print-Error "$DOCKER_COMPOSE_FILE 文件不存在"
        exit 1
    }
    
    Print-Info "拉取最新镜像..."
    docker-compose -f $DOCKER_COMPOSE_FILE pull
    
    Print-Info "启动服务..."
    docker-compose -f $DOCKER_COMPOSE_FILE up -d
    
    Print-Success "Docker 服务启动成功"
}

# 显示服务状态
function Show-ServiceStatus {
    Print-Info "服务状态:"
    docker-compose -f $DOCKER_COMPOSE_FILE ps
}

# 显示访问信息
function Show-AccessInfo {
    Write-Host ""
    Print-Success "部署完成！"
    Write-Host ""
    Write-Host "========================================" -ForegroundColor Green
    Write-Host "  访问信息" -ForegroundColor Green
    Write-Host "========================================" -ForegroundColor Green
    Write-Host "前端地址: " -NoNewline -ForegroundColor Blue
    Write-Host "http://localhost:$($script:NGINX_PORT)"
    Write-Host "后端API: " -NoNewline -ForegroundColor Blue
    Write-Host "http://localhost:$($script:NGINX_PORT)/api"
    Write-Host "MongoDB: " -NoNewline -ForegroundColor Blue
    Write-Host "localhost:$($script:MONGODB_PORT)"
    Write-Host "Redis: " -NoNewline -ForegroundColor Blue
    Write-Host "localhost:$($script:REDIS_PORT)"
    Write-Host ""
    Write-Host "默认账号: " -NoNewline -ForegroundColor Blue
    Write-Host "admin"
    Write-Host "默认密码: " -NoNewline -ForegroundColor Blue
    Write-Host "admin123"
    Write-Host ""
    Write-Host "提示:" -ForegroundColor Yellow
    Write-Host "  - 查看日志: docker-compose -f $DOCKER_COMPOSE_FILE logs -f"
    Write-Host "  - 停止服务: docker-compose -f $DOCKER_COMPOSE_FILE down"
    Write-Host "  - 重启服务: docker-compose -f $DOCKER_COMPOSE_FILE restart"
    Write-Host ""
}

# 主函数
function Main {
    Print-Header

    # 检查依赖
    Test-Dependencies

    # 配置端口
    Set-PortConfiguration

    # 下载 Docker Compose 配置文件
    Get-DockerCompose

    # 更新 Docker Compose 端口配置
    Update-DockerComposePorts

    # 创建目录
    New-RequiredDirectories

    # 下载 Nginx 配置文件
    Get-NginxConfig

    # 下载 .env 配置文件
    Get-EnvFile

    # 检查 .env 文件是否存在
    Test-EnvFile

    # 更新 .env 端口配置
    Update-EnvPorts

    # 启动服务
    Start-DockerServices

    # 显示状态
    Show-ServiceStatus

    # 显示访问信息
    Show-AccessInfo
}

# 运行主函数
Main

