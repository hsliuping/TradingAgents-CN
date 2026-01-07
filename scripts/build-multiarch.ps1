# TradingAgents-CN 多架构 Docker 镜像构建脚本 (PowerShell)
# 支持 amd64 (x86_64) 和 arm64 (ARM) 架构
# 使用编译后的 .pyc 和 .pyd 文件（代码保护）

param(
    [string]$Version = "v1.0.0-preview",
    [string]$Registry = "",  # 留空表示本地构建，设置为 Docker Hub 用户名可推送到远程
    [string]$Platforms = "linux/amd64,linux/arm64",
    [switch]$SkipCompile  # 跳过编译步骤（使用现有编译产物）
)

$ErrorActionPreference = "Stop"

# 镜像名称
$BackendImage = "tradingagents-backend"
$FrontendImage = "tradingagents-frontend"

Write-Host "========================================" -ForegroundColor Blue
Write-Host "TradingAgents-CN 多架构镜像构建（编译版）" -ForegroundColor Blue
Write-Host "========================================" -ForegroundColor Blue
Write-Host ""
Write-Host "版本: $Version" -ForegroundColor Green
Write-Host "架构: $Platforms" -ForegroundColor Green
Write-Host "代码保护: 使用 .pyc 和 .pyd 文件" -ForegroundColor Green
if ($Registry) {
    Write-Host "仓库: $Registry" -ForegroundColor Green
} else {
    Write-Host "仓库: 本地构建（不推送）" -ForegroundColor Yellow
}
Write-Host ""

# 步骤 0: 编译代码（生成 .pyc 和 .pyd 文件）
if (-not $SkipCompile) {
    Write-Host "========================================" -ForegroundColor Blue
    Write-Host "步骤 0: 编译代码" -ForegroundColor Blue
    Write-Host "========================================" -ForegroundColor Blue
    Write-Host ""
    Write-Host "正在运行便携版构建脚本（生成编译后的代码）..." -ForegroundColor Yellow

    $CompileScript = ".\scripts\deployment\build_portable_package.ps1"
    if (-not (Test-Path $CompileScript)) {
        Write-Host "❌ 编译脚本不存在: $CompileScript" -ForegroundColor Red
        exit 1
    }

    # 运行编译脚本（跳过打包步骤，只编译代码）
    & $CompileScript -SkipPackage

    if ($LASTEXITCODE -ne 0) {
        Write-Host "❌ 代码编译失败" -ForegroundColor Red
        exit 1
    }

    # 检查编译产物是否存在
    $CompiledPath = "release\TradingAgentsCN-portable"
    if (-not (Test-Path $CompiledPath)) {
        Write-Host "❌ 编译产物不存在: $CompiledPath" -ForegroundColor Red
        exit 1
    }

    Write-Host "✅ 代码编译成功" -ForegroundColor Green
    Write-Host ""
} else {
    Write-Host "⚠️  跳过编译步骤（使用现有编译产物）" -ForegroundColor Yellow
    Write-Host ""

    # 检查编译产物是否存在
    $CompiledPath = "release\TradingAgentsCN-portable"
    if (-not (Test-Path $CompiledPath)) {
        Write-Host "❌ 编译产物不存在: $CompiledPath" -ForegroundColor Red
        Write-Host "请先运行: .\scripts\deployment\build_portable_package.ps1" -ForegroundColor Yellow
        exit 1
    }
}

# 检查 Docker 是否安装
try {
    $null = docker --version
    Write-Host "✅ Docker 已安装" -ForegroundColor Green
} catch {
    Write-Host "❌ Docker 未安装" -ForegroundColor Red
    exit 1
}

# 检查 Docker Buildx 是否可用
try {
    $null = docker buildx version
    Write-Host "✅ Docker Buildx 可用" -ForegroundColor Green
} catch {
    Write-Host "❌ Docker Buildx 未安装或不可用" -ForegroundColor Red
    Write-Host "请升级到 Docker 19.03+ 或安装 Buildx 插件" -ForegroundColor Yellow
    exit 1
}

# 创建或使用 buildx builder
Write-Host ""
Write-Host "配置 Docker Buildx..." -ForegroundColor Blue
$BuilderName = "tradingagents-builder"

$builderExists = docker buildx inspect $BuilderName 2>$null
if ($LASTEXITCODE -eq 0) {
    Write-Host "✅ Builder '$BuilderName' 已存在" -ForegroundColor Green
} else {
    Write-Host "创建新的 Builder '$BuilderName'..." -ForegroundColor Yellow
    docker buildx create --name $BuilderName --use --platform $Platforms
    if ($LASTEXITCODE -ne 0) {
        Write-Host "❌ Builder 创建失败" -ForegroundColor Red
        exit 1
    }
    Write-Host "✅ Builder 创建成功" -ForegroundColor Green
}

# 使用指定的 builder
docker buildx use $BuilderName

# 启动 builder（如果未运行）
docker buildx inspect --bootstrap

Write-Host ""
Write-Host "========================================" -ForegroundColor Blue
Write-Host "开始构建镜像" -ForegroundColor Blue
Write-Host "========================================" -ForegroundColor Blue

# 构建后端镜像
Write-Host ""
Write-Host "📦 构建后端镜像..." -ForegroundColor Yellow
$BackendTag = "${BackendImage}:${Version}"
$BackendLatestTag = "${BackendImage}:latest"
if ($Registry) {
    $BackendTag = "${Registry}/${BackendTag}"
    $BackendLatestTag = "${Registry}/${BackendLatestTag}"
}

$BuildArgs = @(
    "buildx", "build"
)

if ($Registry) {
    # 推送到远程仓库
    $BuildArgs += "--platform", $Platforms
    $BuildArgs += "--push"
    Write-Host "将推送到:" -ForegroundColor Yellow
    Write-Host "  - $BackendTag" -ForegroundColor Yellow
    Write-Host "  - $BackendLatestTag" -ForegroundColor Yellow
} else {
    # 本地构建并加载
    Write-Host "本地构建: $BackendTag" -ForegroundColor Yellow
    Write-Host "⚠️  注意: --load 只支持单一架构，将只构建当前平台" -ForegroundColor Yellow
    # 获取当前平台
    $CurrentPlatform = "linux/amd64"  # Windows 上通常构建 amd64
    $BuildArgs += "--platform", $CurrentPlatform
    $BuildArgs += "--load"
}

$BuildArgs += "-f", "Dockerfile.backend.compiled"
$BuildArgs += "-t", $BackendTag
if ($Registry) {
    $BuildArgs += "-t", $BackendLatestTag
}
$BuildArgs += "."

Write-Host "构建命令: docker $($BuildArgs -join ' ')" -ForegroundColor Blue
& docker $BuildArgs

if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ 后端镜像构建失败" -ForegroundColor Red
    exit 1
}
Write-Host "✅ 后端镜像构建成功" -ForegroundColor Green

# 构建前端镜像
Write-Host ""
Write-Host "📦 构建前端镜像..." -ForegroundColor Yellow
$FrontendTag = "${FrontendImage}:${Version}"
$FrontendLatestTag = "${FrontendImage}:latest"
if ($Registry) {
    $FrontendTag = "${Registry}/${FrontendTag}"
    $FrontendLatestTag = "${Registry}/${FrontendLatestTag}"
}

$BuildArgs = @(
    "buildx", "build"
)

if ($Registry) {
    # 推送到远程仓库
    $BuildArgs += "--platform", $Platforms
    $BuildArgs += "--push"
    Write-Host "将推送到:" -ForegroundColor Yellow
    Write-Host "  - $FrontendTag" -ForegroundColor Yellow
    Write-Host "  - $FrontendLatestTag" -ForegroundColor Yellow
} else {
    # 本地构建并加载
    Write-Host "本地构建: $FrontendTag" -ForegroundColor Yellow
    Write-Host "⚠️  注意: --load 只支持单一架构，将只构建当前平台" -ForegroundColor Yellow
    # 获取当前平台
    $CurrentPlatform = "linux/amd64"  # Windows 上通常构建 amd64
    $BuildArgs += "--platform", $CurrentPlatform
    $BuildArgs += "--load"
}

$BuildArgs += "-f", "Dockerfile.frontend"
$BuildArgs += "-t", $FrontendTag
if ($Registry) {
    $BuildArgs += "-t", $FrontendLatestTag
}
$BuildArgs += "."

Write-Host "构建命令: docker $($BuildArgs -join ' ')" -ForegroundColor Blue
& docker $BuildArgs

if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ 前端镜像构建失败" -ForegroundColor Red
    exit 1
}
Write-Host "✅ 前端镜像构建成功" -ForegroundColor Green

# 构建完成
Write-Host ""
Write-Host "========================================" -ForegroundColor Blue
Write-Host "✅ 所有镜像构建完成！" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Blue
Write-Host ""

if ($Registry) {
    Write-Host "镜像已推送到远程仓库:" -ForegroundColor Green
    Write-Host "  后端镜像:"
    Write-Host "    - $BackendTag"
    Write-Host "    - $BackendLatestTag"
    Write-Host "  前端镜像:"
    Write-Host "    - $FrontendTag"
    Write-Host "    - $FrontendLatestTag"
    Write-Host ""
    Write-Host "使用方法:" -ForegroundColor Yellow
    Write-Host "  # 拉取指定版本"
    Write-Host "  docker pull $BackendTag"
    Write-Host "  docker pull $FrontendTag"
    Write-Host ""
    Write-Host "  # 拉取最新版本"
    Write-Host "  docker pull $BackendLatestTag"
    Write-Host "  docker pull $FrontendLatestTag"
} else {
    Write-Host "镜像已构建到本地:" -ForegroundColor Green
    Write-Host "  - $BackendTag"
    Write-Host "  - $FrontendTag"
    Write-Host ""
    Write-Host "使用方法:" -ForegroundColor Yellow
    Write-Host "  docker-compose -f docker-compose.v1.0.0.yml up -d"
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Blue
Write-Host "💡 提示" -ForegroundColor Yellow
Write-Host "========================================" -ForegroundColor Blue
Write-Host ""
Write-Host "1. 推送到 Docker Hub:" -ForegroundColor Yellow
Write-Host "   .\scripts\build-multiarch.ps1 -Registry your-dockerhub-username -Version v1.0.0"
Write-Host ""
Write-Host "2. 本地构建（当前架构）:" -ForegroundColor Yellow
Write-Host "   .\scripts\build-multiarch.ps1"
Write-Host ""
Write-Host "3. 构建特定架构:" -ForegroundColor Yellow
Write-Host "   docker buildx build --platform linux/arm64 -f Dockerfile.backend -t tradingagents-backend:arm64 ."
Write-Host ""
Write-Host "4. 查看镜像信息:" -ForegroundColor Yellow
Write-Host "   docker buildx imagetools inspect $BackendTag"
Write-Host ""

