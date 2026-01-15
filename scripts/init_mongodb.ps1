# MongoDB 初始化脚本
# 为绿色版创建管理员用户

param(
    [string]$MongoPath = "",
    [string]$DataPath = "",
    [int]$Port = 27017
)

$ErrorActionPreference = 'Continue'

Write-Host "🔧 MongoDB 初始化脚本" -ForegroundColor Cyan

if (-not $MongoPath) {
    $root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
    $mongoExe = Get-ChildItem -Path (Join-Path $root 'vendors\mongodb') -Recurse -Filter 'mongod.exe' -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($mongoExe) {
        $MongoPath = Split-Path $mongoExe.FullName
    } else {
        Write-Host "❌ 未找到 MongoDB 可执行文件" -ForegroundColor Red
        exit 1
    }
}

if (-not $DataPath) {
    $root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
    $DataPath = Join-Path $root 'data\mongodb\db'
}

$mongodExe = Join-Path $MongoPath 'mongod.exe'
$mongoExe = Join-Path $MongoPath 'mongo.exe'

if (-not (Test-Path $mongodExe)) {
    Write-Host "❌ 未找到 mongod.exe: $mongodExe" -ForegroundColor Red
    exit 1
}

Write-Host "📍 MongoDB 路径: $MongoPath" -ForegroundColor Green
Write-Host "📁 数据路径: $DataPath" -ForegroundColor Green

# 确保数据目录存在
if (-not (Test-Path $DataPath)) {
    New-Item -ItemType Directory -Path $DataPath -Force | Out-Null
    Write-Host "✅ 创建数据目录: $DataPath" -ForegroundColor Green
}

# 检查 MongoDB 是否已经在运行
try {
    $tcpClient = New-Object System.Net.Sockets.TcpClient
    $tcpClient.Connect('127.0.0.1', $Port)
    $tcpClient.Close()
    Write-Host "⚠️  MongoDB 已在端口 $Port 运行" -ForegroundColor Yellow
    
    # 尝试连接并创建用户
    if (Test-Path $mongoExe) {
        Write-Host "🔧 尝试创建管理员用户..." -ForegroundColor Cyan
        
        $createUserScript = @"
use admin
try {
    db.createUser({
        user: "admin",
        pwd: "tradingagents123",
        roles: [
            { role: "userAdminAnyDatabase", db: "admin" },
            { role: "readWriteAnyDatabase", db: "admin" },
            { role: "dbAdminAnyDatabase", db: "admin" }
        ]
    })
    print("✅ 管理员用户创建成功")
} catch (e) {
    if (e.code === 11000) {
        print("ℹ️  管理员用户已存在")
    } else {
        print("❌ 创建用户失败: " + e.message)
    }
}
"@
        
        $scriptFile = Join-Path $env:TEMP 'create_mongo_user.js'
        Set-Content -Path $scriptFile -Value $createUserScript -Encoding UTF8
        
        try {
            & $mongoExe --host "127.0.0.1:$Port" $scriptFile
        } catch {
            Write-Host "⚠️  无法连接到 MongoDB 或创建用户失败" -ForegroundColor Yellow
        } finally {
            Remove-Item $scriptFile -ErrorAction SilentlyContinue
        }
    }
    
    exit 0
} catch {
    Write-Host "✅ 端口 $Port 可用，准备启动 MongoDB" -ForegroundColor Green
}

# 启动 MongoDB（无认证模式，用于初始化）
Write-Host "🚀 启动 MongoDB（初始化模式）..." -ForegroundColor Cyan
$mongoArgs = "--dbpath `"$DataPath`" --bind_ip 127.0.0.1 --port $Port"

$psi = New-Object System.Diagnostics.ProcessStartInfo
$psi.FileName = $mongodExe
$psi.Arguments = $mongoArgs
$psi.UseShellExecute = $false
$psi.RedirectStandardOutput = $true
$psi.RedirectStandardError = $true
$mongoProcess = [System.Diagnostics.Process]::Start($psi)

Write-Host "⏳ 等待 MongoDB 启动..." -ForegroundColor Yellow
Start-Sleep -Seconds 5

# 检查 MongoDB 是否启动成功
$retries = 0
$maxRetries = 10
$connected = $false

while ($retries -lt $maxRetries -and -not $connected) {
    try {
        $tcpClient = New-Object System.Net.Sockets.TcpClient
        $tcpClient.Connect('127.0.0.1', $Port)
        $tcpClient.Close()
        $connected = $true
        Write-Host "✅ MongoDB 启动成功" -ForegroundColor Green
    } catch {
        $retries++
        Write-Host "⏳ 等待 MongoDB 启动... ($retries/$maxRetries)" -ForegroundColor Yellow
        Start-Sleep -Seconds 2
    }
}

if (-not $connected) {
    Write-Host "❌ MongoDB 启动失败" -ForegroundColor Red
    $mongoProcess.Kill()
    exit 1
}

# 创建管理员用户
if (Test-Path $mongoExe) {
    Write-Host "🔧 创建管理员用户..." -ForegroundColor Cyan
    
    $createUserScript = @"
use admin
db.createUser({
    user: "admin",
    pwd: "tradingagents123",
    roles: [
        { role: "userAdminAnyDatabase", db: "admin" },
        { role: "readWriteAnyDatabase", db: "admin" },
        { role: "dbAdminAnyDatabase", db: "admin" }
    ]
})
"@
    
    $scriptFile = Join-Path $env:TEMP 'create_mongo_user.js'
    Set-Content -Path $scriptFile -Value $createUserScript -Encoding UTF8
    
    try {
        & $mongoExe --host "127.0.0.1:$Port" $scriptFile
        Write-Host "✅ 管理员用户创建成功" -ForegroundColor Green
    } catch {
        Write-Host "⚠️  管理员用户可能已存在或创建失败" -ForegroundColor Yellow
    } finally {
        Remove-Item $scriptFile -ErrorAction SilentlyContinue
    }
} else {
    Write-Host "⚠️  未找到 mongo.exe，跳过用户创建" -ForegroundColor Yellow
}

# 停止 MongoDB
Write-Host "🛑 停止 MongoDB..." -ForegroundColor Yellow
$mongoProcess.Kill()
$mongoProcess.WaitForExit(5000)

Write-Host "✅ MongoDB 初始化完成" -ForegroundColor Green
Write-Host "💡 现在可以使用认证模式启动 MongoDB" -ForegroundColor Cyan
