# TradingAgents-CN Pro - 一键部署脚本 (Windows PowerShell)
# 版本: v1.0.0
# 用途: 自动下载配置文件、创建目录、启动 Docker 服务

# 设置错误时停止
$ErrorActionPreference = "Stop"

# 配置
$NGINX_CONFIG_URL = "https://www.tradingagentscn.com/docker/nginx-proxy.conf"
$DOCKER_COMPOSE_URL = "https://www.tradingagentscn.com/docker/docker-compose.compiled.yml"
$DOCKER_COMPOSE_FILE = "docker-compose.compiled.yml"

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

    $nginxConfigPath = "nginx\nginx-proxy.conf"

    if (Test-Path $nginxConfigPath) {
        Print-Warning "nginx\nginx-proxy.conf 已存在，是否覆盖？(Y/N)"
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

# 检查并创建 .env 文件
function Initialize-EnvFile {
    Print-Info "配置环境变量文件..."
    
    if (-not (Test-Path ".env")) {
        if (Test-Path ".env.example") {
            Copy-Item ".env.example" ".env"
            Print-Success "已从 .env.example 创建 .env 文件"
            Print-Warning "请编辑 .env 文件，配置必要的环境变量"
            Print-Info "按回车键继续编辑 .env 文件，或输入 'skip' 跳过"
            $response = Read-Host
            if ($response -ne "skip") {
                notepad .env
            }
        }
        else {
            Print-Error ".env.example 文件不存在"
            exit 1
        }
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
    Write-Host "http://localhost:8082"
    Write-Host "后端API: " -NoNewline -ForegroundColor Blue
    Write-Host "http://localhost:8082/api"
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

    # 下载 Docker Compose 配置文件
    Get-DockerCompose

    # 创建目录
    New-RequiredDirectories

    # 下载 Nginx 配置文件
    Get-NginxConfig

    # 配置环境变量
    Initialize-EnvFile

    # 启动服务
    Start-DockerServices

    # 显示状态
    Show-ServiceStatus

    # 显示访问信息
    Show-AccessInfo
}

# 运行主函数
Main

