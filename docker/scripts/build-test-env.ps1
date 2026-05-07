# TradingAgents-CN Pro - 测试环境镜像打包脚本
#
# 一键完成: 前端构建 → 镜像打包 → docker-compose 启动
#
# 使用方法:
#   .\docker\scripts\build-test-env.ps1              # 全部步骤
#   .\docker\scripts\build-test-env.ps1 -SkipFrontendBuild   # 跳过前端构建(已有dist)
#   .\docker\scripts\build-test-env.ps1 -SkipComposeUp       # 只打包不启动
#   .\docker\scripts\build-test-env.ps1 -Version 3.0         # 指定版本(默认读VERSION文件)
#   .\docker\scripts\build-test-env.ps1 -Step frontend       # 只执行某一步(base/backend/frontend/compose)
#
# 步骤说明:
#   1. 基础镜像(base)    - 系统依赖 + Python包, 变化少, 通常只需构建一次
#   2. 后端镜像(backend)  - 编译Python代码, 每次代码变更需重新构建
#   3. 前端镜像(frontend) - 宿主机 npm build → Nginx, 前端代码变更需重新构建
#   4. 启动服务(compose)  - docker-compose 启动 MongoDB + Redis + Backend + Frontend + Nginx

param(
    [string]$Version = "",
    [string]$Registry = "hsliup",
    [string]$Step = "",
  [int]$MongoPort = 0,
  [int]$RedisPort = 0,
  [int]$NginxPort = 0,
    [switch]$SkipFrontendBuild,
    [switch]$SkipComposeUp,
    [switch]$SkipBase,
    [switch]$SkipBackend,
    [switch]$SkipFrontend,
    [switch]$ForceRebuild
)

$ErrorActionPreference = "Stop"

# ── 颜色函数 ──────────────────────────────────────────────────────────────
function Write-Color($Text, $Color = "White") { Write-Host $Text -ForegroundColor $Color }
function Write-Step($Text) { Write-Color "`n========================================" "Cyan"; Write-Color $Text "Cyan"; Write-Color "========================================" "Cyan"; Write-Host "" }
function Write-Info($Text) { Write-Color "  $Text" "Green" }
function Write-Warn($Text) { Write-Color "  $Text" "Yellow" }
function Write-Err($Text)  { Write-Color "  $Text" "Red" }
function Write-Detail($Text) { Write-Color "    $Text" "DarkGray" }

# ── 读取版本号 ────────────────────────────────────────────────────────────
if (-not $Version) {
    $versionFile = Join-Path $PSScriptRoot "..\..\VERSION"
    if (Test-Path $versionFile) {
        $Version = (Get-Content $versionFile -Raw).Trim()
    } else {
        Write-Err "VERSION 文件不存在, 请用 -Version 指定版本号"
        exit 1
    }
}

# ── 版本 → 端口映射 ──────────────────────────────────────────────────────
$VersionPorts = @{
    "2.0" = @{ Mongo = 27017; Redis = 6379; Nginx = 8080; Project = "ta-v201" }
    "2.1" = @{ Mongo = 27018; Redis = 6380; Nginx = 8081; Project = "ta-v210" }
    "3.0" = @{ Mongo = 27019; Redis = 6381; Nginx = 8082; Project = "ta-v3"   }
}

# 从完整版本号提取主版本 (2.1.0 → 2.1, 3.0.1 → 3.0)
# 同时保留完整版本号用于 Docker 镜像标签
$FullVersion = $Version
$MajorMinor = if ($Version -match '^(\d+\.\d+)') { $Matches[1] } else { $Version }

if (-not $VersionPorts.ContainsKey($MajorMinor)) {
    Write-Err "不支持版本 $Version, 可选: $($VersionPorts.Keys -join ', ')"
    exit 1
}

$ports = $VersionPorts[$MajorMinor]
$ports = @{
  Mongo = $ports.Mongo
  Redis = $ports.Redis
  Nginx = $ports.Nginx
  Project = $ports.Project
}

if ($MongoPort -gt 0) { $ports.Mongo = $MongoPort }
if ($RedisPort -gt 0) { $ports.Redis = $RedisPort }
if ($NginxPort -gt 0) { $ports.Nginx = $NginxPort }

$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$baseTag = "python3.10-bookworm"

$baseImage    = "$Registry/tradingagents-pro-backend-base:$baseTag"
$backendImage = "$Registry/tradingagents-pro-backend:$FullVersion"
$frontendImage = "$Registry/tradingagents-pro-frontend:$FullVersion"

# ── 打印构建配置 ──────────────────────────────────────────────────────────
Write-Color "`n========================================" "Cyan"
Write-Color " TradingAgents-CN Pro - 测试环境构建" "Cyan"
Write-Color "========================================" "Cyan"
Write-Host ""
Write-Info "版本: $Version"
Write-Info "Docker 项目名: $($ports.Project)"
Write-Info "MongoDB 端口: $($ports.Mongo)"
Write-Info "Redis 端口: $($ports.Redis)"
Write-Info "Nginx 端口: $($ports.Nginx)"
Write-Host ""
Write-Info "基础镜像: $baseImage"
Write-Info "后端镜像: $backendImage"
Write-Info "前端镜像: $frontendImage"
Write-Host ""

# ── 辅助: 判断是否应执行某步骤 ───────────────────────────────────────────
function Test-ShouldRun($StepName) {
    if ($Step -and $Step -ne $StepName) { return $false }
    switch ($StepName) {
        "base"     { return -not $SkipBase }
        "backend"  { return -not $SkipBackend }
        "frontend" { return -not $SkipFrontend }
        "compose"  { return -not $SkipComposeUp }
        default    { return $true }
    }
}

function Get-DockerPortOccupants([int]$Port) {
  $dockerLines = docker ps --format "{{.Names}}|{{.Ports}}" 2>$null
  if ($LASTEXITCODE -ne 0 -or -not $dockerLines) {
    return @()
  }

  return @(
    $dockerLines |
      Where-Object { $_ -match ":$Port->" } |
      ForEach-Object {
        $parts = $_ -split "\|", 2
        [PSCustomObject]@{
          Name  = $parts[0]
          Ports = if ($parts.Count -gt 1) { $parts[1] } else { "" }
        }
      }
  )
}

function Test-PortAvailable([int]$Port) {
  $listeners = @(Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue)
  return $listeners.Count -eq 0
}

function Get-PortSuggestion([int]$PreferredPort) {
  $basePort = [int]$PreferredPort
  $primaryCandidate = $basePort + 100
  if ($primaryCandidate -gt 0 -and (Test-PortAvailable -Port $primaryCandidate)) {
    return $primaryCandidate
  }

  $secondaryCandidate = $basePort + 1000
  if ($secondaryCandidate -gt 0 -and (Test-PortAvailable -Port $secondaryCandidate)) {
    return $secondaryCandidate
  }

  for ($offset = 1; $offset -le 50; $offset++) {
    $candidate = $basePort + 100 + $offset
    if (Test-PortAvailable -Port $candidate) {
      return $candidate
    }
  }

  return $null
}

function Assert-PortsAvailable($RequiredPorts, [string]$ProjectName, [string]$Version) {
  $conflicts = @()
  $projectContainerPrefix = "$ProjectName-"

  foreach ($entry in $RequiredPorts.GetEnumerator()) {
    $port = [int]$entry.Value
    $service = [string]$entry.Key

    $listeners = @(Get-NetTCPConnection -State Listen -LocalPort $port -ErrorAction SilentlyContinue)
    if (-not $listeners) {
      continue
    }

    $dockerOccupants = @(Get-DockerPortOccupants -Port $port)
    $foreignDockerOccupants = @($dockerOccupants | Where-Object { $_.Name -notlike "$projectContainerPrefix*" })

    if ($dockerOccupants.Count -gt 0 -and $foreignDockerOccupants.Count -eq 0) {
      continue
    }

    $processIds = @($listeners | Select-Object -ExpandProperty OwningProcess -Unique | Where-Object { $_ -and $_ -ne 0 })
    $processNames = @(
      foreach ($processId in $processIds) {
        $process = Get-Process -Id $processId -ErrorAction SilentlyContinue
        if ($process) {
          "PID ${processId} ($($process.ProcessName))"
        } else {
          "PID ${processId}"
        }
      }
    )

    $conflicts += [PSCustomObject]@{
      Service = $service
      Port = $port
      DockerOccupants = $foreignDockerOccupants
      Processes = $processNames
    }
  }

  if (-not $conflicts) {
    return
  }

  Write-Err "启动前检测到端口冲突，已停止执行 docker-compose。"
  Write-Host ""

  foreach ($conflict in $conflicts) {
    Write-Err "$($conflict.Service) 需要宿主机端口 $($conflict.Port)，但该端口已被占用"

    foreach ($occupant in $conflict.DockerOccupants) {
      Write-Detail "Docker 容器: $($occupant.Name) [$($occupant.Ports)]"
    }

    foreach ($processName in $conflict.Processes) {
      Write-Detail "监听进程: $processName"
    }

    Write-Host ""
  }

  $dockerContainerNames = @(
    $conflicts |
      ForEach-Object { $_.DockerOccupants } |
      Where-Object { $_ } |
      Select-Object -ExpandProperty Name -Unique
  )
  $devContainers = @($dockerContainerNames | Where-Object { $_ -like "tradingagents-dev-*" })
  $otherContainers = @($dockerContainerNames | Where-Object { $_ -notlike "tradingagents-dev-*" })
  $mongoSuggestion = Get-PortSuggestion -PreferredPort ([int]$RequiredPorts.mongodb)
  $redisSuggestion = Get-PortSuggestion -PreferredPort ([int]$RequiredPorts.redis)
  $nginxSuggestion = Get-PortSuggestion -PreferredPort ([int]$RequiredPorts.nginx)

  Write-Warn "当前测试环境项目名: $ProjectName"
  if ($devContainers.Count -gt 0) {
    Write-Warn "检测到同版本开发环境容器占用了测试环境端口，可先整体停止开发环境。"
    Write-Detail "示例: docker compose -f docker/docker-compose.dev-compiled.yml down"
  }
  if ($otherContainers.Count -gt 0) {
    Write-Warn "以下其他容器也占用了目标端口，请先停止或调整它们的端口映射。"
    Write-Detail ("冲突容器: " + ($otherContainers -join ", "))
    Write-Detail ("示例: docker stop " + ($otherContainers -join " "))
  }
  if ($mongoSuggestion -and $redisSuggestion -and $nginxSuggestion) {
    Write-Warn "如需直接换端口启动，可改用以下示例命令。"
    Write-Detail ".\docker\scripts\build-test-env.ps1 -Version $Version -Step compose -MongoPort $mongoSuggestion -RedisPort $redisSuggestion -NginxPort $nginxSuggestion"
  }
  Write-Detail '查看端口占用: docker ps --format "table {{.Names}}\t{{.Ports}}"'
  throw "端口冲突导致 docker-compose 无法启动"
}

# ── 步骤 1: 基础镜像 ─────────────────────────────────────────────────────
  if (Test-ShouldRun "base") {
    Write-Step "步骤 1/4: 构建基础镜像 ($baseImage)"
    Write-Info "包含系统依赖 + Python 包, 通常只需构建一次"
    Write-Host ""

    # 检查是否已存在
    $existingBase = docker images --format "{{.Repository}}:{{.Tag}}" | Where-Object { $_ -eq $baseImage }
    if ($existingBase -and -not $ForceRebuild) {
        Write-Warn "基础镜像已存在: $baseImage"
        Write-Warn "如需重新构建, 请使用 -ForceRebuild 参数"
    } else {
        Write-Info "构建命令:"
        Write-Detail "docker build -f docker/Dockerfile.backend.base.ubuntu -t $baseImage ."
        Write-Host ""

        Push-Location $projectRoot
        try {
            docker build `
                -f "docker/Dockerfile.backend.base.ubuntu" `
                -t $baseImage `
                . 2>&1 | ForEach-Object { Write-Host $_ }
            if ($LASTEXITCODE -ne 0) { throw "基础镜像构建失败" }
            Write-Info "基础镜像构建完成"
        } finally {
            Pop-Location
        }
    }
}

# ── 步骤 2: 后端镜像 ─────────────────────────────────────────────────────
if (Test-ShouldRun "backend") {
    Write-Step "步骤 2/4: 构建后端镜像 ($backendImage)"
    Write-Info "容器内编译 Python 代码 → .pyc + .so"
  Write-Info "直接使用项目根目录作为构建上下文，与 Dockerfile 的 COPY 清单保持一致"
    Write-Host ""

  Write-Info "构建命令:"
  Write-Detail "docker build -f docker/Dockerfile.backend.compiled.ubuntu -t $backendImage --build-arg BASE_IMAGE=$baseImage ."
  Write-Host ""

  Push-Location $projectRoot
  try {
    docker build `
      -f "docker/Dockerfile.backend.compiled.ubuntu" `
      -t $backendImage `
      --build-arg "BASE_IMAGE=$baseImage" `
      . 2>&1 | ForEach-Object { Write-Host $_ }
    if ($LASTEXITCODE -ne 0) { throw "后端镜像构建失败" }
    Write-Info "后端镜像构建完成"
  } finally {
    Pop-Location
  }
}

# ── 步骤 3: 前端镜像 ─────────────────────────────────────────────────────
if (Test-ShouldRun "frontend") {
    Write-Step "步骤 3/4: 构建前端镜像 ($frontendImage)"

    $frontendDir = Join-Path $projectRoot "frontend"
    $distDir = Join-Path $frontendDir "dist"

    # 3a. 宿主机 npm build
    if (-not $SkipFrontendBuild) {
        Write-Info "在宿主机构建前端产物 (npx vite build)..."
        Write-Host ""

        Push-Location $frontendDir
        try {
            # 先尝试标准构建 (vue-tsc + vite build)
            Write-Info "尝试 npm run build (含类型检查)..."
            npm run build 2>&1 | ForEach-Object { Write-Detail $_ }
            if ($LASTEXITCODE -ne 0) {
                Write-Warn "npm run build 失败(类型错误), 改用 npx vite build 跳过类型检查..."
                npx vite build 2>&1 | ForEach-Object { Write-Detail $_ }
                if ($LASTEXITCODE -ne 0) { throw "前端构建失败" }
            }
            Write-Info "前端产物构建完成"
        } finally {
            Pop-Location
        }
    } else {
        if (Test-Path $distDir) {
            Write-Info "跳过前端构建, 使用已有 dist 目录"
        } else {
            Write-Err "dist 目录不存在, 请去掉 -SkipFrontendBuild 或先手动构建"
            exit 1
        }
    }

    # 验证 dist 目录
    if (-not (Test-Path $distDir)) {
        Write-Err "dist 目录不存在: $distDir"
        exit 1
    }
    $distFiles = (Get-ChildItem $distDir -Recurse -File).Count
    Write-Info "dist 目录包含 $distFiles 个文件"

    # 3b. 构建前端 Docker 镜像
    Write-Host ""
    Write-Info "构建前端 Docker 镜像..."

    Push-Location $projectRoot
    try {
        docker build `
            -f "docker/Dockerfile.frontend" `
            -t $frontendImage `
            . 2>&1 | ForEach-Object { Write-Host $_ }
        if ($LASTEXITCODE -ne 0) { throw "前端镜像构建失败" }
        Write-Info "前端镜像构建完成"
    } finally {
        Pop-Location
    }
}

# ── 步骤 4: docker-compose 启动 ──────────────────────────────────────────
if (Test-ShouldRun "compose") {
    Write-Step "步骤 4/4: 启动测试环境 (docker-compose)"

    # 动态生成版本感知的 compose 文件
    $composeOverride = Join-Path $projectRoot "docker\docker-compose.dev-test.yml"

    $mongoPort = $ports.Mongo
    $redisPort = $ports.Redis
    $nginxPort = $ports.Nginx
    $projectName = $ports.Project
    $hostLogsDir = "./logs/$projectName"
    $hostDataDir = "./data/$projectName"
    $hostRuntimeDir = "./runtime/$projectName"

    @(
      (Join-Path $projectRoot "docker\logs\$projectName"),
      (Join-Path $projectRoot "docker\data\$projectName"),
      (Join-Path $projectRoot "docker\runtime\$projectName")
    ) | ForEach-Object {
      if (-not (Test-Path $_)) {
        New-Item -Path $_ -ItemType Directory -Force | Out-Null
      }
    }

    # 生成测试环境 compose 文件 (基于 dev-compiled, 替换端口和镜像标签)
    $composeContent = @"
# TradingAgents-CN Pro 测试环境 - 版本 $Version
# 自动生成, 请勿手动修改
# 启动: docker-compose -p $projectName -f docker/docker-compose.dev-test.yml up -d

services:
  mongodb:
    image: mongo:4.4
    container_name: ${projectName}-mongodb
    restart: unless-stopped
    ports:
      - "${mongoPort}:27017"
    volumes:
      - ${projectName}_mongodb_data:/data/db
    environment:
      MONGO_INITDB_ROOT_USERNAME: admin
      MONGO_INITDB_ROOT_PASSWORD: tradingagents123
      MONGO_INITDB_DATABASE: tradingagents
      TZ: "Asia/Shanghai"
    networks:
      - ${projectName}-network
    healthcheck:
      test: echo 'db.runCommand("ping").ok' | mongo localhost:27017/test --quiet
      interval: 10s
      timeout: 5s
      retries: 5
      start_period: 10s

  redis:
    image: redis:7-alpine
    container_name: ${projectName}-redis
    restart: unless-stopped
    ports:
      - "${redisPort}:6379"
    volumes:
      - ${projectName}_redis_data:/data
    environment:
      TZ: "Asia/Shanghai"
    command: redis-server --appendonly yes --requirepass tradingagents123
    networks:
      - ${projectName}-network
    healthcheck:
      test: ["CMD", "redis-cli", "-a", "tradingagents123", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5
      start_period: 5s

  backend:
    image: ${backendImage}
    container_name: ${projectName}-backend
    restart: unless-stopped
    expose:
      - "8000"
    volumes:
      - ${hostLogsDir}:/app/logs
      - ${hostDataDir}:/app/data
      - ${hostRuntimeDir}:/app/runtime
    env_file:
      - .env
    environment:
      TZ: "Asia/Shanghai"
      TRADINGAGENTS_LOG_LEVEL: "INFO"
      MONGODB_HOST: "mongodb"
      MONGODB_PORT: "27017"
      MONGODB_USERNAME: "admin"
      MONGODB_PASSWORD: "tradingagents123"
      MONGODB_DATABASE: "tradingagents"
      MONGODB_AUTH_SOURCE: "admin"
      MONGODB_URL: "mongodb://admin:tradingagents123@mongodb:27017/tradingagents?authSource=admin"
      MONGODB_CONNECTION_STRING: "mongodb://admin:tradingagents123@mongodb:27017/tradingagents?authSource=admin"
      REDIS_HOST: "redis"
      REDIS_PORT: "6379"
      REDIS_PASSWORD: "tradingagents123"
      REDIS_URL: "redis://:tradingagents123@redis:6379/0"
      DOCKER_CONTAINER: "true"
      CORS_ORIGINS: "*"
    depends_on:
      mongodb:
        condition: service_healthy
      redis:
        condition: service_healthy
    networks:
      - ${projectName}-network
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/api/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s

  frontend:
    image: ${frontendImage}
    container_name: ${projectName}-frontend
    restart: unless-stopped
    expose:
      - "80"
    environment:
      TZ: "Asia/Shanghai"
    depends_on:
      - backend
    networks:
      - ${projectName}-network
    healthcheck:
      test: ["CMD", "wget", "--quiet", "--tries=1", "--spider", "http://127.0.0.1:80"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 10s

  nginx:
    image: nginx:alpine
    container_name: ${projectName}-nginx
    restart: unless-stopped
    ports:
      - "${nginxPort}:80"
    volumes:
      - ./nginx/nginx-proxy.conf:/etc/nginx/nginx.conf:ro
    depends_on:
      - frontend
      - backend
    networks:
      - ${projectName}-network
    healthcheck:
      test: ["CMD", "wget", "--quiet", "--tries=1", "--spider", "http://127.0.0.1:80/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 10s

volumes:
  ${projectName}_mongodb_data:
    driver: local
  ${projectName}_redis_data:
    driver: local

networks:
  ${projectName}-network:
    driver: bridge
"@

    Set-Content -Path $composeOverride -Value $composeContent -Encoding UTF8
    Write-Info "已生成 docker-compose 文件: docker/docker-compose.dev-test.yml"
    Write-Host ""

    Assert-PortsAvailable -RequiredPorts @{
      mongodb = $mongoPort
      redis = $redisPort
      nginx = $nginxPort
    } -ProjectName $projectName -Version $Version

    # 启动
    $dockerDir = Join-Path $projectRoot "docker"
    Push-Location $dockerDir
    try {
        Write-Info "启动服务 (项目: $projectName)..."
        Write-Host ""

        docker-compose -p $projectName -f docker-compose.dev-test.yml up -d 2>&1 | ForEach-Object { Write-Host $_ }
        if ($LASTEXITCODE -ne 0) { throw "docker-compose 启动失败" }

        Write-Host ""
        Write-Info "等待服务就绪..."
        Start-Sleep -Seconds 5

        # 显示容器状态
        Write-Host ""
        docker-compose -p $projectName -f docker-compose.dev-test.yml ps 2>&1 | ForEach-Object { Write-Host $_ }
    } finally {
        Pop-Location
    }
}

# ── 完成 ──────────────────────────────────────────────────────────────────
Write-Host ""
Write-Color "========================================" "Cyan"
Write-Color " 构建完成!" "Green"
Write-Color "========================================" "Cyan"
Write-Host ""

if (Test-ShouldRun "compose") {
    $url = "http://localhost:$($ports.Nginx)"
    Write-Info "访问地址: $url"
    Write-Info "API 文档: ${url}/api/docs"
    Write-Host ""
    Write-Info "管理命令:"
    Write-Detail "查看日志: docker-compose -p $($ports.Project) -f docker/docker-compose.dev-test.yml logs -f"
    Write-Detail "停止服务: docker-compose -p $($ports.Project) -f docker/docker-compose.dev-test.yml down"
    Write-Detail "重启后端: docker-compose -p $($ports.Project) -f docker/docker-compose.dev-test.yml restart backend"
} else {
    Write-Info "镜像已构建:"
    if (Test-ShouldRun "backend")  { Write-Detail $backendImage }
    if (Test-ShouldRun "frontend") { Write-Detail $frontendImage }
    Write-Host ""
    Write-Info "启动服务:"
    Write-Detail ".\docker\scripts\build-test-env.ps1 -Version $Version -Step compose"
    Write-Detail "或: docker-compose -p $($ports.Project) -f docker/docker-compose.dev-test.yml up -d"
}
