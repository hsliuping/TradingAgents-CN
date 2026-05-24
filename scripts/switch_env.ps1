# TradingAgents-CN 部署模式切换脚本
# 用法:
#   .\scripts\switch_env.ps1 hybrid   # 混合部署：Docker 只跑 DB，本地跑代码
#   .\scripts\switch_env.ps1 docker   # 全 Docker 部署
#   .\scripts\switch_env.ps1 status   # 查看当前模式

param(
    [Parameter(Position = 0)]
    [ValidateSet("hybrid", "docker", "status")]
    [string]$Mode = "status"
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$EnvFile = Join-Path $Root ".env"

if (-not (Test-Path $EnvFile)) {
    Write-Host "ERROR: .env not found. Copy .env.example to .env first." -ForegroundColor Red
    exit 1
}

function Get-EnvValue($key) {
    foreach ($line in Get-Content $EnvFile -Encoding UTF8) {
        if ($line -match "^\s*$key=(.*)$") { return $Matches[1].Trim() }
    }
    return $null
}

function Set-EnvValues([hashtable]$Updates) {
    $lines = Get-Content $EnvFile -Encoding UTF8
    $keys = @($Updates.Keys)
    $out = foreach ($line in $lines) {
        $matched = $false
        foreach ($key in $keys) {
            if ($line -match "^\s*$key=") {
                $matched = $true
                "$key=$($Updates[$key])"
                break
            }
        }
        if (-not $matched) { $line }
    }
    # append missing keys
    $existing = @{}
    foreach ($line in $out) {
        if ($line -match "^\s*([^#=][^=]*)=") { $existing[$Matches[1].Trim()] = $true }
    }
    foreach ($key in $keys) {
        if (-not $existing[$key]) { $out += "$key=$($Updates[$key])" }
    }
    Set-Content -Path $EnvFile -Value $out -Encoding UTF8
}

function Detect-Mode {
    $mongoHostVal = Get-EnvValue "MONGODB_HOST"
    if ($mongoHostVal -eq "mongodb") { return "docker" }
    if ($mongoHostVal -eq "localhost") { return "hybrid" }
    return "unknown ($mongoHostVal)"
}

if ($Mode -eq "status") {
    $current = Detect-Mode
    Write-Host "Current deployment mode: $current" -ForegroundColor Cyan
    Write-Host "  MONGODB_HOST = $(Get-EnvValue 'MONGODB_HOST')"
    Write-Host "  MONGODB_DATABASE_SCOPE = $(Get-EnvValue 'MONGODB_DATABASE_SCOPE')"
    Write-Host "  REDIS_HOST   = $(Get-EnvValue 'REDIS_HOST')"
    Write-Host "  DEBUG        = $(Get-EnvValue 'DEBUG')"
    Write-Host "  DOCKER_CONTAINER = $(Get-EnvValue 'DOCKER_CONTAINER')"
    exit 0
}

$backup = Join-Path $Root ".env.backup"
Copy-Item $EnvFile $backup -Force
Write-Host "Backed up .env -> .env.backup" -ForegroundColor DarkGray

$db = "tradingagentscn"
$auth = "authSource=admin"
$user = Get-EnvValue "MONGODB_USERNAME"
if (-not $user) { $user = "admin" }
$pass = Get-EnvValue "MONGODB_PASSWORD"
if (-not $pass) { $pass = "tradingagents123" }
$redisPass = Get-EnvValue "REDIS_PASSWORD"
if (-not $redisPass) { $redisPass = "tradingagents123" }

if ($Mode -eq "hybrid") {
    $mongoHost = "localhost"
    $redisHost = "localhost"
    $updates = @{
        DOCKER_CONTAINER = "false"
        MONGODB_HOST = $mongoHost
        MONGODB_URL = "mongodb://${user}:${pass}@${mongoHost}:27017/${db}?${auth}"
        MONGO_URI = "mongodb://${user}:${pass}@${mongoHost}:27017/${db}?${auth}"
        MONGODB_CONNECTION_STRING = "mongodb://${user}:${pass}@${mongoHost}:27017/${db}?${auth}"
        MONGODB_DATABASE = $db
        MONGODB_DATABASE_SCOPE = "explicit"
        REDIS_HOST = $redisHost
        REDIS_URL = "redis://:${redisPass}@${redisHost}:6379/0"
        DEBUG = "true"
        API_DEBUG = "true"
        ALLOWED_ORIGINS = '["http://localhost:3000", "http://localhost:80", "http://localhost:8000"]'
        TRADINGAGENTS_LOG_DIR = "logs"
        TRADINGAGENTS_LOG_FILE = "logs/tradingagents.log"
        TRADINGAGENTS_DATA_DIR = "data"
        TRADINGAGENTS_CACHE_DIR = "data/cache"
        TRADINGAGENTS_SESSIONS_DIR = "data/sessions"
        TRADINGAGENTS_LOGS_DIR = "data/logs"
        TRADINGAGENTS_CONFIG_DIR = "data/config"
        TRADINGAGENTS_TEMP_DIR = "data/temp"
        TRADINGAGENTS_RESULTS_DIR = "data/analysis_results"
        LOG_FILE = "logs/tradingagents.log"
    }
    Set-EnvValues $updates
    Write-Host "Switched to HYBRID mode" -ForegroundColor Green
    Write-Host ""
    Write-Host "Start:" -ForegroundColor Yellow
    Write-Host "  docker start tradingagents-mongodb tradingagents-redis"
    Write-Host "  .\venv\Scripts\Activate.ps1"
    Write-Host "  python -m app"
    Write-Host "  cd frontend && npm run dev"
    Write-Host ""
    Write-Host "Access: http://localhost:3000  (API docs: http://localhost:8000/docs)"
}
else {
    $mongoHost = "mongodb"
    $redisHost = "redis"
    $updates = @{
        DOCKER_CONTAINER = "true"
        MONGODB_HOST = $mongoHost
        MONGODB_URL = "mongodb://${user}:${pass}@${mongoHost}:27017/${db}?${auth}"
        MONGO_URI = "mongodb://${user}:${pass}@${mongoHost}:27017/${db}?${auth}"
        MONGODB_CONNECTION_STRING = "mongodb://${user}:${pass}@${mongoHost}:27017/${db}?${auth}"
        MONGODB_DATABASE = $db
        MONGODB_DATABASE_SCOPE = "explicit"
        REDIS_HOST = $redisHost
        REDIS_URL = "redis://:${redisPass}@${redisHost}:6379/0"
        DEBUG = "false"
        API_DEBUG = "false"
        ALLOWED_ORIGINS = '["http://localhost:80", "http://localhost:8000"]'
        CORS_ORIGINS = "*"
        TRADINGAGENTS_LOG_DIR = "/app/logs"
        TRADINGAGENTS_LOG_FILE = "/app/logs/tradingagents.log"
        TRADINGAGENTS_DATA_DIR = "/app/data"
        TRADINGAGENTS_CACHE_DIR = "/app/data/cache"
        TRADINGAGENTS_SESSIONS_DIR = "/app/data/sessions"
        TRADINGAGENTS_LOGS_DIR = "/app/data/logs"
        TRADINGAGENTS_CONFIG_DIR = "/app/data/config"
        TRADINGAGENTS_TEMP_DIR = "/app/data/temp"
        TRADINGAGENTS_RESULTS_DIR = "/app/data/analysis_results"
        LOG_FILE = "logs/tradingagents.log"
    }
    Set-EnvValues $updates
    Write-Host "Switched to DOCKER mode" -ForegroundColor Green
    Write-Host ""
    Write-Host "Start:" -ForegroundColor Yellow
    Write-Host "  docker compose -f docker-compose.hub.nginx.yml up -d"
    Write-Host ""
    Write-Host "Access: http://localhost  (Nginx 80)"
    Write-Host "Note: rebuild backend after code changes:"
    Write-Host "  docker compose -f docker-compose.hub.nginx.yml build backend"
    Write-Host "  docker compose -f docker-compose.hub.nginx.yml up -d backend"
}
