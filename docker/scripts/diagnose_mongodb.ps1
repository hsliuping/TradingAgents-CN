# MongoDB 诊断脚本 (PowerShell)

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "MongoDB 诊断工具" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

# 1. 检查 MongoDB 容器状态
Write-Host "[1/5] 检查 MongoDB 容器状态..." -ForegroundColor Yellow
$mongodbContainers = docker ps -a --filter "name=mongodb" --format "{{.Names}}"

if ([string]::IsNullOrWhiteSpace($mongodbContainers)) {
    Write-Host "❌ 未找到 MongoDB 容器" -ForegroundColor Red
    Write-Host "   请检查 docker-compose.yml 中的服务配置" -ForegroundColor Yellow
} else {
    $containerNames = $mongodbContainers -split "`n" | Where-Object { $_ -ne "" }
    foreach ($container in $containerNames) {
        Write-Host "✅ 找到容器: $container" -ForegroundColor Green
        
        # 检查容器状态
        $status = docker inspect --format='{{.State.Status}}' $container 2>$null
        Write-Host "   状态: $status" -ForegroundColor Gray
        
        if ($status -ne "running") {
            Write-Host "⚠️  容器未运行，尝试启动..." -ForegroundColor Yellow
            docker start $container
            Start-Sleep -Seconds 5
        }
    }
}

Write-Host ""

# 2. 检查网络连接
Write-Host "[2/5] 检查网络连接..." -ForegroundColor Yellow
$networkCheck = docker network inspect tradingagents-network 2>$null
if ($LASTEXITCODE -eq 0) {
    Write-Host "✅ 网络 tradingagents-network 存在" -ForegroundColor Green
    
    # 检查 MongoDB 是否在网络上
    $networkInfo = docker network inspect tradingagents-network --format='{{range .Containers}}{{.Name}} {{end}}' 2>$null
    if ($networkInfo -match "mongodb") {
        Write-Host "✅ MongoDB 容器在网络中" -ForegroundColor Green
    } else {
        Write-Host "⚠️  MongoDB 容器不在网络中，尝试连接..." -ForegroundColor Yellow
        if ($containerNames) {
            docker network connect tradingagents-network $containerNames[0] 2>$null
        }
    }
} else {
    Write-Host "❌ 网络 tradingagents-network 不存在" -ForegroundColor Red
    Write-Host "   请运行: docker network create tradingagents-network" -ForegroundColor Yellow
}

Write-Host ""

# 3. 测试 MongoDB 连接
Write-Host "[3/5] 测试 MongoDB 连接..." -ForegroundColor Yellow
if ($containerNames) {
    $testResult = docker exec $containerNames[0] mongosh --eval "db.runCommand('ping')" 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Host "✅ MongoDB 内部连接正常" -ForegroundColor Green
    } else {
        Write-Host "❌ MongoDB 内部连接失败" -ForegroundColor Red
        Write-Host "   查看容器日志: docker logs $($containerNames[0])" -ForegroundColor Yellow
    }
} else {
    Write-Host "⚠️  无法测试，未找到 MongoDB 容器" -ForegroundColor Yellow
}

Write-Host ""

# 4. 从后端容器测试连接
Write-Host "[4/5] 从后端容器测试 MongoDB 连接..." -ForegroundColor Yellow
$backendContainer = docker ps --filter "name=backend" --format "{{.Names}}" | Select-Object -First 1

if ($backendContainer) {
    Write-Host "   使用后端容器: $backendContainer" -ForegroundColor Gray
    $testScript = @"
from pymongo import MongoClient
try:
    client = MongoClient('mongodb://admin:tradingagents123@mongodb:27017/tradingagents?authSource=admin', serverSelectionTimeoutMS=5000)
    client.server_info()
    print('✅ 连接成功')
except Exception as e:
    print(f'❌ 连接失败: {e}')
"@
    
    $testResult = docker exec $backendContainer python -c $testScript 2>&1
    Write-Host $testResult
} else {
    Write-Host "⚠️  后端容器未运行" -ForegroundColor Yellow
}

Write-Host ""

# 5. 检查数据卷
Write-Host "[5/5] 检查 MongoDB 数据卷..." -ForegroundColor Yellow
$volumes = docker volume ls --filter "name=mongodb" --format "{{.Name}}"
if ($volumes) {
    Write-Host "✅ 找到数据卷:" -ForegroundColor Green
    $volumeList = $volumes -split "`n" | Where-Object { $_ -ne "" }
    foreach ($vol in $volumeList) {
        Write-Host "   - $vol" -ForegroundColor Gray
    }
} else {
    Write-Host "⚠️  未找到 MongoDB 数据卷" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "诊断完成" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "如果 MongoDB 连接失败，可以尝试：" -ForegroundColor White
if ($containerNames) {
    Write-Host "1. 重启 MongoDB 容器: docker restart $($containerNames[0])" -ForegroundColor Gray
}
Write-Host "2. 删除并重建数据卷（会丢失数据）:" -ForegroundColor Gray
Write-Host "   docker-compose down -v" -ForegroundColor DarkGray
Write-Host "   docker volume rm tradingagents_mongodb_data" -ForegroundColor DarkGray
Write-Host "   docker-compose up -d mongodb" -ForegroundColor DarkGray
if ($containerNames) {
    Write-Host "3. 查看 MongoDB 日志: docker logs $($containerNames[0])" -ForegroundColor Gray
}
