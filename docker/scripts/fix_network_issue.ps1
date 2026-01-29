# 修复 Docker 网络问题的 PowerShell 脚本
# 用于解决容器不在同一网络导致的连接问题

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "修复 Docker 网络配置" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

# 获取当前目录
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$DockerDir = Split-Path -Parent $ScriptDir

Set-Location $DockerDir

Write-Host "1. 停止并删除所有相关容器..." -ForegroundColor Yellow
docker-compose -f docker-compose.compiled.yml down

Write-Host ""
Write-Host "2. 检查并清理孤立的网络..." -ForegroundColor Yellow
# 查找所有 tradingagents 相关的网络
$Networks = docker network ls --filter "name=tradingagents" --format "{{.Name}}"
if ($Networks) {
    Write-Host "找到以下网络:" -ForegroundColor Yellow
    $Networks | ForEach-Object { Write-Host "  - $_" }
    Write-Host ""
    $Response = Read-Host "是否删除这些网络? (y/N)"
    if ($Response -eq "y" -or $Response -eq "Y") {
        $Networks | ForEach-Object {
            Write-Host "删除网络: $_" -ForegroundColor Yellow
            docker network rm $_ 2>$null
            if ($LASTEXITCODE -ne 0) {
                Write-Host "  网络 $_ 可能正在使用中，跳过" -ForegroundColor Gray
            }
        }
    }
}

Write-Host ""
Write-Host "3. 重新创建并启动所有服务..." -ForegroundColor Yellow
docker-compose -f docker-compose.compiled.yml up -d

Write-Host ""
Write-Host "4. 等待服务启动..." -ForegroundColor Yellow
Start-Sleep -Seconds 5

Write-Host ""
Write-Host "5. 检查容器状态..." -ForegroundColor Yellow
docker-compose -f docker-compose.compiled.yml ps

Write-Host ""
Write-Host "6. 检查网络配置..." -ForegroundColor Yellow
$NetworkInfo = docker network inspect tradingagents-network 2>$null
if ($NetworkInfo) {
    Write-Host "网络信息:" -ForegroundColor Green
    $NetworkInfo | ConvertFrom-Json | Select-Object -ExpandProperty Containers | Format-Table
} else {
    Write-Host "网络检查失败，请手动检查" -ForegroundColor Red
}

Write-Host ""
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "完成！" -ForegroundColor Green
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "如果仍有问题，请检查：" -ForegroundColor Yellow
Write-Host "1. docker logs tradingagents-mongodb-propro"
Write-Host "2. docker logs tradingagents-backend-pro"
Write-Host "3. docker network inspect tradingagents-network"
