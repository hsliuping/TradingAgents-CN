# 全新安装时更新所有端口配置
# 用法: powershell -File update_ports.ps1 -InstallDir "C:\TradingAgentsCN" -BackendPort 8000 -MongoPort 27017 -RedisPort 6379 -NginxPort 80
param(
    [Parameter(Mandatory=$true)]
    [string]$InstallDir,
    [Parameter(Mandatory=$true)]
    [int]$BackendPort,
    [Parameter(Mandatory=$true)]
    [int]$MongoPort,
    [Parameter(Mandatory=$true)]
    [int]$RedisPort,
    [Parameter(Mandatory=$true)]
    [int]$NginxPort
)

$ErrorActionPreference = "Continue"
$utf8NoBom = New-Object System.Text.UTF8Encoding $false

# ============================================================================
# 1. .env 文件：从 .env.example 创建（如果不存在），然后更新端口
# ============================================================================

$envFile = Join-Path $InstallDir ".env"
$envExample = Join-Path $InstallDir ".env.example"

if (-not (Test-Path $envFile) -and (Test-Path $envExample)) {
    Copy-Item -Path $envExample -Destination $envFile -Force
    Write-Host "  Created .env from .env.example"
}

if (Test-Path $envFile) {
    $content = Get-Content $envFile -Raw -Encoding UTF8
    $content = $content -replace "PORT=\d+", "PORT=$BackendPort"
    $content = $content -replace "API_PORT=\d+", "API_PORT=$BackendPort"
    $content = $content -replace "MONGODB_PORT=\d+", "MONGODB_PORT=$MongoPort"
    $content = $content -replace "REDIS_PORT=\d+", "REDIS_PORT=$RedisPort"
    $content = $content -replace "NGINX_PORT=\d+", "NGINX_PORT=$NginxPort"
    [System.IO.File]::WriteAllText($envFile, $content, $utf8NoBom)
    Write-Host "  Updated .env ports: Backend=$BackendPort, Mongo=$MongoPort, Redis=$RedisPort, Nginx=$NginxPort"
} else {
    Write-Host "  WARNING: .env not found at $envFile"
}

# ============================================================================
# 2. runtime/redis.conf：更新 Redis 端口
# ============================================================================

$redisConf = Join-Path $InstallDir "runtime\redis.conf"
if (Test-Path $redisConf) {
    $content = Get-Content $redisConf -Raw -Encoding UTF8
    $content = $content -replace "^port\s+\d+", "port $RedisPort"
    [System.IO.File]::WriteAllText($redisConf, $content, $utf8NoBom)
    Write-Host "  Updated redis.conf: port=$RedisPort"
} else {
    Write-Host "  WARNING: redis.conf not found at $redisConf"
}

# ============================================================================
# 3. runtime/mongodb.conf：更新 MongoDB 端口
# ============================================================================

$mongoConf = Join-Path $InstallDir "runtime\mongodb.conf"
if (Test-Path $mongoConf) {
    $content = Get-Content $mongoConf -Raw -Encoding UTF8
    $content = $content -replace "port:\s*\d+", "port: $MongoPort"
    [System.IO.File]::WriteAllText($mongoConf, $content, $utf8NoBom)
    Write-Host "  Updated mongodb.conf: port=$MongoPort"
} else {
    Write-Host "  WARNING: mongodb.conf not found at $mongoConf"
}

# ============================================================================
# 4. runtime/nginx.conf：更新 Nginx 监听端口和后端代理端口
# ============================================================================

$nginxConf = Join-Path $InstallDir "runtime\nginx.conf"
if (Test-Path $nginxConf) {
    $content = Get-Content $nginxConf -Raw -Encoding UTF8
    $content = $content -replace "listen\s+\d+;", "listen       $NginxPort;"
    $content = $content -replace "server\s+127\.0\.0\.1:\d+;", "server 127.0.0.1:$BackendPort;"
    [System.IO.File]::WriteAllText($nginxConf, $content, $utf8NoBom)
    Write-Host "  Updated nginx.conf: listen=$NginxPort, backend=127.0.0.1:$BackendPort"
} else {
    Write-Host "  WARNING: nginx.conf not found at $nginxConf"
}

Write-Host "Port configuration completed"
