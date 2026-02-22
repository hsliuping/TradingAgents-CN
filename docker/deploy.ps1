# TradingAgents-CN Pro - One-Click Deploy Script (Windows PowerShell)
# Version: v1.0.1
# Usage: Auto-download configs, create dirs, start Docker services
# Note: Uses ASCII-only output for compatibility across different system encodings

$ErrorActionPreference = "Stop"

# Config
$NGINX_CONFIG_URL = "https://www.tradingagentscn.com/docker/nginx-proxy.conf"
$DOCKER_COMPOSE_URL = "https://www.tradingagentscn.com/docker/docker-compose.compiled.yml"
$ENV_DOCKER_URL = "https://www.tradingagentscn.com/docker/.env.docker"
$DOCKER_COMPOSE_FILE = "docker-compose.compiled.yml"

# Default ports
$DEFAULT_NGINX_PORT = 8082
$DEFAULT_MONGODB_PORT = 27017
$DEFAULT_REDIS_PORT = 6379
$DEFAULT_BACKEND_PORT = 8000

$script:NGINX_PORT = $DEFAULT_NGINX_PORT
$script:MONGODB_PORT = $DEFAULT_MONGODB_PORT
$script:REDIS_PORT = $DEFAULT_REDIS_PORT
$script:BACKEND_PORT = $DEFAULT_BACKEND_PORT

function Print-Info {
    param([string]$Message)
    Write-Host "[INFO] $Message" -ForegroundColor Blue
}

function Print-Success {
    param([string]$Message)
    Write-Host "[OK] $Message" -ForegroundColor Green
}

function Print-Warning {
    param([string]$Message)
    Write-Host "[WARN] $Message" -ForegroundColor Yellow
}

function Print-Error {
    param([string]$Message)
    Write-Host "[ERR] $Message" -ForegroundColor Red
}

function Print-Header {
    Write-Host ""
    Write-Host "========================================" -ForegroundColor Blue
    Write-Host "  TradingAgents-CN Pro Deploy Script" -ForegroundColor Blue
    Write-Host "========================================" -ForegroundColor Blue
    Write-Host ""
}

function Test-Command {
    param([string]$Command)
    $exists = $null -ne (Get-Command $Command -ErrorAction SilentlyContinue)
    return $exists
}

function Test-Dependencies {
    Print-Info "Checking dependencies..."

    if (-not (Test-Command "docker")) {
        Print-Error "Docker not installed. Please install Docker Desktop first."
        Print-Info "Download: https://www.docker.com/products/docker-desktop"
        exit 1
    }

    if (-not (Test-Command "docker-compose")) {
        Print-Error "docker-compose not installed."
        Print-Info "Docker Desktop should include docker-compose."
        exit 1
    }

    Print-Success "Dependencies OK"
}

function Set-PortConfiguration {
    Print-Info "Configuring ports..."
    Write-Host ""

    Print-Info "Nginx port (default: $DEFAULT_NGINX_PORT)"
    $userInput = Read-Host "Enter port [Enter for default]"
    if ([string]::IsNullOrWhiteSpace($userInput)) {
        $script:NGINX_PORT = $DEFAULT_NGINX_PORT
    } else {
        $script:NGINX_PORT = $userInput
    }
    Print-Success "Nginx port: $($script:NGINX_PORT)"

    Print-Info "MongoDB port (default: $DEFAULT_MONGODB_PORT)"
    $userInput = Read-Host "Enter port [Enter for default]"
    if ([string]::IsNullOrWhiteSpace($userInput)) {
        $script:MONGODB_PORT = $DEFAULT_MONGODB_PORT
    } else {
        $script:MONGODB_PORT = $userInput
    }
    Print-Success "MongoDB port: $($script:MONGODB_PORT)"

    Print-Info "Redis port (default: $DEFAULT_REDIS_PORT)"
    $userInput = Read-Host "Enter port [Enter for default]"
    if ([string]::IsNullOrWhiteSpace($userInput)) {
        $script:REDIS_PORT = $DEFAULT_REDIS_PORT
    } else {
        $script:REDIS_PORT = $userInput
    }
    Print-Success "Redis port: $($script:REDIS_PORT)"

    Print-Info "Backend API port (default: $DEFAULT_BACKEND_PORT)"
    $userInput = Read-Host "Enter port [Enter for default]"
    if ([string]::IsNullOrWhiteSpace($userInput)) {
        $script:BACKEND_PORT = $DEFAULT_BACKEND_PORT
    } else {
        $script:BACKEND_PORT = $userInput
    }
    Print-Success "Backend port: $($script:BACKEND_PORT)"

    Write-Host ""
    Print-Success "Port configuration done."
    Write-Host ""
}

function New-RequiredDirectories {
    Print-Info "Creating directories..."

    New-Item -ItemType Directory -Force -Path "nginx" | Out-Null
    Print-Success "Created nginx\"

    New-Item -ItemType Directory -Force -Path "logs" | Out-Null
    New-Item -ItemType Directory -Force -Path "data" | Out-Null
    New-Item -ItemType Directory -Force -Path "runtime" | Out-Null
    Print-Success "Created logs\, data\, runtime\"
}

function Get-DockerCompose {
    Print-Info "Downloading Docker Compose config..."

    if (Test-Path $DOCKER_COMPOSE_FILE) {
        Print-Warning "$DOCKER_COMPOSE_FILE exists. Overwrite? (Y/N)"
        $response = Read-Host
        if ($response -notmatch '^[Yy]$') {
            Print-Info "Skipping Docker Compose download"
            return
        }
    }

    try {
        Invoke-WebRequest -Uri $DOCKER_COMPOSE_URL -OutFile $DOCKER_COMPOSE_FILE -UseBasicParsing
        Print-Success "Docker Compose config downloaded"
    }
    catch {
        Print-Error "Failed to download Docker Compose: $_"
        Print-Info "Manual download: $DOCKER_COMPOSE_URL"
        exit 1
    }
}

function Get-NginxConfig {
    Print-Info "Downloading Nginx config..."

    $nginxConfigPath = "nginx\nginx-proxy.conf"

    if (Test-Path $nginxConfigPath) {
        Print-Warning "nginx\nginx-proxy.conf exists. Overwrite? (Y/N)"
        $response = Read-Host
        if ($response -notmatch '^[Yy]$') {
            Print-Info "Skipping Nginx config download"
            return
        }
    }

    try {
        Invoke-WebRequest -Uri $NGINX_CONFIG_URL -OutFile $nginxConfigPath -UseBasicParsing
        Print-Success "Nginx config downloaded"
    }
    catch {
        Print-Error "Failed to download Nginx config: $_"
        Print-Info "Manual download: $NGINX_CONFIG_URL"
        exit 1
    }
}

function Get-EnvFile {
    Print-Info "Downloading .env config..."

    if (Test-Path ".env") {
        Print-Warning ".env exists. Overwrite? (Y/N)"
        $response = Read-Host
        if ($response -notmatch '^[Yy]$') {
            Print-Info "Skipping .env download"
            return
        }
    }

    try {
        Invoke-WebRequest -Uri $ENV_DOCKER_URL -OutFile ".env" -UseBasicParsing
        Print-Success ".env config downloaded"
    }
    catch {
        Print-Error "Failed to download .env: $_"
        Print-Info "Manual download: $ENV_DOCKER_URL"
        exit 1
    }
}

function Update-DockerComposePorts {
    Print-Info "Updating Docker Compose ports..."

    $content = Get-Content $DOCKER_COMPOSE_FILE -Raw -Encoding UTF8

    $content = $content -replace '"27017:27017"', "`"$($script:MONGODB_PORT):27017`""
    $content = $content -replace '"6379:6379"', "`"$($script:REDIS_PORT):6379`""
    $content = $content -replace '"8082:8082"', "`"$($script:NGINX_PORT):8082`""

    $utf8NoBom = New-Object System.Text.UTF8Encoding $false
    [System.IO.File]::WriteAllText((Join-Path $PWD $DOCKER_COMPOSE_FILE), $content, $utf8NoBom)

    Print-Success "Docker Compose ports updated"
}

function Update-EnvPorts {
    Print-Info "Updating .env ports..."

    $content = Get-Content ".env" -Encoding UTF8

    $content = $content -replace '^MONGODB_PORT=.*', "MONGODB_PORT=$($script:MONGODB_PORT)"
    $content = $content -replace '^REDIS_PORT=.*', "REDIS_PORT=$($script:REDIS_PORT)"
    $content = $content -replace '^PORT=.*', "PORT=$($script:BACKEND_PORT)"
    $content = $content -replace '^NGINX_PORT=.*', "NGINX_PORT=$($script:NGINX_PORT)"

    $content | Set-Content ".env" -Encoding UTF8

    Print-Success ".env ports updated"
}

function Test-EnvFile {
    Print-Info "Checking .env file..."

    if (-not (Test-Path ".env")) {
        Print-Error ".env file not found"
        Print-Info "Please ensure .env has been downloaded"
        exit 1
    }
    else {
        Print-Success ".env file OK"
    }
}

function Start-DockerServices {
    Print-Info "Starting Docker services..."

    if (-not (Test-Path $DOCKER_COMPOSE_FILE)) {
        Print-Error "$DOCKER_COMPOSE_FILE not found"
        exit 1
    }

    Print-Info "Pulling images..."
    docker-compose -f $DOCKER_COMPOSE_FILE pull

    Print-Info "Starting services..."
    docker-compose -f $DOCKER_COMPOSE_FILE up -d

    Print-Success "Docker services started"
}

function Show-ServiceStatus {
    Print-Info "Service status:"
    docker-compose -f $DOCKER_COMPOSE_FILE ps
}

function Show-AccessInfo {
    Write-Host ""
    Print-Success "Deploy complete!"
    Write-Host ""
    Write-Host "========================================" -ForegroundColor Green
    Write-Host "  Access Info" -ForegroundColor Green
    Write-Host "========================================" -ForegroundColor Green
    Write-Host "Frontend: " -NoNewline -ForegroundColor Blue
    Write-Host "http://localhost:$($script:NGINX_PORT)"
    Write-Host "Backend API: " -NoNewline -ForegroundColor Blue
    Write-Host "http://localhost:$($script:NGINX_PORT)/api"
    Write-Host "MongoDB: " -NoNewline -ForegroundColor Blue
    Write-Host "localhost:$($script:MONGODB_PORT)"
    Write-Host "Redis: " -NoNewline -ForegroundColor Blue
    Write-Host "localhost:$($script:REDIS_PORT)"
    Write-Host ""
    Write-Host "Default login: " -NoNewline -ForegroundColor Blue
    Write-Host "admin / admin123"
    Write-Host ""
    Write-Host "Tips:" -ForegroundColor Yellow
    Write-Host "  - Logs: docker-compose -f $DOCKER_COMPOSE_FILE logs -f"
    Write-Host "  - Stop: docker-compose -f $DOCKER_COMPOSE_FILE down"
    Write-Host "  - Restart: docker-compose -f $DOCKER_COMPOSE_FILE restart"
    Write-Host ""
}

function Main {
    Print-Header

    Test-Dependencies
    Set-PortConfiguration
    Get-DockerCompose
    Update-DockerComposePorts
    New-RequiredDirectories
    Get-NginxConfig
    Get-EnvFile
    Test-EnvFile
    Update-EnvPorts
    Start-DockerServices
    Show-ServiceStatus
    Show-AccessInfo
}

Main
