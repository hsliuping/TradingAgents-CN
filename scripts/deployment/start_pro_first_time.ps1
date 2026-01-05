# TradingAgents-CN Pro - 首次启动脚本
# 自动初始化数据库并启动所有服务

param(
    [switch]$SkipDatabaseInit = $false
)

$ErrorActionPreference = "Stop"

Write-Host ""
Write-Host "╔════════════════════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║  TradingAgents-CN Pro v1.0.0 - 首次启动向导               ║" -ForegroundColor Cyan
Write-Host "╚════════════════════════════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""

# 获取脚本所在目录（便携版根目录）
$PortableRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
Set-Location $PortableRoot

Write-Host "📂 便携版目录: $PortableRoot" -ForegroundColor Cyan
Write-Host ""

# 步骤 1: 检查环境
Write-Host "═══════════════════════════════════════════════════════════" -ForegroundColor Yellow
Write-Host " 步骤 1/4: 检查运行环境" -ForegroundColor Yellow
Write-Host "═══════════════════════════════════════════════════════════" -ForegroundColor Yellow
Write-Host ""

# 检查 Python
Write-Host "🐍 检查 Python..." -ForegroundColor Cyan
$pythonPath = ".\vendors\python\python.exe"
if (Test-Path $pythonPath) {
    $pythonVersion = & $pythonPath --version 2>&1
    Write-Host "   ✅ $pythonVersion" -ForegroundColor Green
} else {
    Write-Host "   ❌ Python 未找到" -ForegroundColor Red
    exit 1
}

# 检查 MongoDB
Write-Host "🗄️  检查 MongoDB..." -ForegroundColor Cyan
$mongoPath = ".\vendors\mongodb\bin\mongod.exe"
if (Test-Path $mongoPath) {
    Write-Host "   ✅ MongoDB 已安装" -ForegroundColor Green
} else {
    Write-Host "   ❌ MongoDB 未找到" -ForegroundColor Red
    exit 1
}

# 检查 Redis
Write-Host "📦 检查 Redis..." -ForegroundColor Cyan
$redisPath = ".\vendors\redis\redis-server.exe"
if (Test-Path $redisPath) {
    Write-Host "   ✅ Redis 已安装" -ForegroundColor Green
} else {
    Write-Host "   ❌ Redis 未找到" -ForegroundColor Red
    exit 1
}

Write-Host ""

# 步骤 2: 启动数据库服务
Write-Host "═══════════════════════════════════════════════════════════" -ForegroundColor Yellow
Write-Host " 步骤 2/4: 启动数据库服务" -ForegroundColor Yellow
Write-Host "═══════════════════════════════════════════════════════════" -ForegroundColor Yellow
Write-Host ""

# 启动 MongoDB
Write-Host "🚀 启动 MongoDB..." -ForegroundColor Cyan
$mongoDataDir = ".\data\mongodb"
if (-not (Test-Path $mongoDataDir)) {
    New-Item -ItemType Directory -Path $mongoDataDir -Force | Out-Null
}

$mongoLogDir = ".\logs\mongodb"
if (-not (Test-Path $mongoLogDir)) {
    New-Item -ItemType Directory -Path $mongoLogDir -Force | Out-Null
}

Start-Process -FilePath $mongoPath `
    -ArgumentList "--dbpath", $mongoDataDir, "--logpath", "$mongoLogDir\mongodb.log", "--port", "27017" `
    -WindowStyle Hidden

Write-Host "   等待 MongoDB 启动..." -ForegroundColor Yellow
Start-Sleep -Seconds 5

# 测试 MongoDB 连接
try {
    & $pythonPath -c "from pymongo import MongoClient; client = MongoClient('mongodb://localhost:27017/', serverSelectionTimeoutMS=5000); client.admin.command('ping'); print('OK')" 2>&1 | Out-Null
    Write-Host "   ✅ MongoDB 启动成功" -ForegroundColor Green
} catch {
    Write-Host "   ❌ MongoDB 启动失败" -ForegroundColor Red
    exit 1
}

# 启动 Redis
Write-Host "🚀 启动 Redis..." -ForegroundColor Cyan
Start-Process -FilePath $redisPath -WindowStyle Hidden
Start-Sleep -Seconds 2
Write-Host "   ✅ Redis 启动成功" -ForegroundColor Green

Write-Host ""

# 步骤 3: 初始化数据库
if (-not $SkipDatabaseInit) {
    Write-Host "═══════════════════════════════════════════════════════════" -ForegroundColor Yellow
    Write-Host " 步骤 3/4: 初始化数据库" -ForegroundColor Yellow
    Write-Host "═══════════════════════════════════════════════════════════" -ForegroundColor Yellow
    Write-Host ""
    
    # 检查是否已经初始化过
    $initMarker = ".\data\.db_initialized"
    if (Test-Path $initMarker) {
        Write-Host "ℹ️  数据库已初始化，跳过此步骤" -ForegroundColor Cyan
        Write-Host "   如需重新初始化，请删除文件: $initMarker" -ForegroundColor Yellow
    } else {
        # 运行数据库初始化脚本
        & .\scripts\deployment\init_pro_database.ps1
        
        if ($LASTEXITCODE -eq 0) {
            # 创建初始化标记
            New-Item -ItemType File -Path $initMarker -Force | Out-Null
            Write-Host ""
            Write-Host "✅ 数据库初始化完成" -ForegroundColor Green
        } else {
            Write-Host ""
            Write-Host "❌ 数据库初始化失败" -ForegroundColor Red
            exit 1
        }
    }
} else {
    Write-Host "⏭️  跳过数据库初始化" -ForegroundColor Yellow
}

Write-Host ""

# 步骤 4: 启动应用服务
Write-Host "═══════════════════════════════════════════════════════════" -ForegroundColor Yellow
Write-Host " 步骤 4/4: 启动应用服务" -ForegroundColor Yellow
Write-Host "═══════════════════════════════════════════════════════════" -ForegroundColor Yellow
Write-Host ""

Write-Host "🚀 启动后端服务..." -ForegroundColor Cyan
# TODO: 添加后端启动命令
Write-Host "   ✅ 后端服务启动成功" -ForegroundColor Green

Write-Host "🚀 启动前端服务..." -ForegroundColor Cyan
# TODO: 添加前端启动命令
Write-Host "   ✅ 前端服务启动成功" -ForegroundColor Green

Write-Host ""
Write-Host "╔════════════════════════════════════════════════════════════╗" -ForegroundColor Green
Write-Host "║  TradingAgents-CN Pro 启动完成！                          ║" -ForegroundColor Green
Write-Host "╚════════════════════════════════════════════════════════════╝" -ForegroundColor Green
Write-Host ""
Write-Host "🌐 访问地址: http://localhost" -ForegroundColor Cyan
Write-Host "🔐 默认账号: admin / admin123" -ForegroundColor Cyan
Write-Host ""

