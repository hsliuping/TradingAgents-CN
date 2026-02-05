# TradingAgents-CN Services Diagnostic Script
# 诊断MongoDB和Redis服务的启动状态和错误信息

[CmdletBinding()]
param(
    [Parameter(Mandatory=$false)]
    [ValidateSet("mongodb", "redis", "all")]
    [string]$Service = "all",
    
    [Parameter(Mandatory=$false)]
    [switch]$Start,
    
    [Parameter(Mandatory=$false)]
    [switch]$ShowLogs,
    
    [Parameter(Mandatory=$false)]
    [switch]$TestConnection
)

$ErrorActionPreference = "Continue"
# Script is at project root directory
# Project root is the same as script directory
$root = $PSScriptRoot
$envPath = Join-Path $root '.env'

# ============================================================================
# Helper Functions
# ============================================================================

function Load-Env($path) {
    $map = @{}
    if (Test-Path -LiteralPath $path) {
        foreach ($line in Get-Content -LiteralPath $path) {
            if ($line -match '^\s*#') { continue }
            if ($line -match '^\s*$') { continue }
            $idx = $line.IndexOf('=')
            if ($idx -gt 0) {
                $key = $line.Substring(0, $idx).Trim()
                $val = $line.Substring($idx + 1).Trim()
                $map[$key] = $val
            }
        }
    }
    return $map
}

function Ensure-Dir($path) {
    if (-not (Test-Path -LiteralPath $path)) {
        New-Item -ItemType Directory -Path $path -Force | Out-Null
    }
}

function Test-TcpConnection($hostname, $port, $timeoutSeconds = 3) {
    try {
        $tcpClient = New-Object System.Net.Sockets.TcpClient
        $connect = $tcpClient.BeginConnect($hostname, $port, $null, $null)
        $wait = $connect.AsyncWaitHandle.WaitOne([TimeSpan]::FromSeconds($timeoutSeconds), $false)
        if ($wait) {
            $tcpClient.EndConnect($connect)
            $tcpClient.Close()
            return $true
        } else {
            $tcpClient.Close()
            return $false
        }
    } catch {
        return $false
    }
}

function Get-ProcessInfo($processName) {
    $processes = Get-Process -Name $processName -ErrorAction SilentlyContinue
    if ($processes) {
        return $processes | Select-Object -First 1 | ForEach-Object {
            @{
                Exists = $true
                PID = $_.Id
                Name = $_.ProcessName
                Path = $_.Path
                StartTime = $_.StartTime
            }
        }
    }
    return @{ Exists = $false }
}

function Get-PortInfo($port) {
    $connections = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
    if ($connections) {
        $conn = $connections | Select-Object -First 1
        $process = Get-Process -Id $conn.OwningProcess -ErrorAction SilentlyContinue
        return @{
            InUse = $true
            PID = $conn.OwningProcess
            ProcessName = if ($process) { $process.ProcessName } else { "Unknown" }
            State = $conn.State
        }
    }
    return @{ InUse = $false }
}

# ============================================================================
# MongoDB Diagnostic Functions
# ============================================================================

function Test-MongoDBConnection($hostname, $port, $username, $password) {
    Write-Host "  📡 测试MongoDB连接..." -ForegroundColor Gray
    
    # First test TCP connection
    if (-not (Test-TcpConnection -hostname $hostname -port $port -timeoutSeconds 5)) {
        Write-Host "    ❌ TCP连接失败: 无法连接到 $hostname`:$port" -ForegroundColor Red
        return $false
    }
    Write-Host "    ✅ TCP连接成功" -ForegroundColor Green
    
    # Try Python connection test if available
    $pythonExe = Join-Path $root 'vendors\python\python.exe'
    if (-not (Test-Path $pythonExe)) {
        $pythonExe = Join-Path $root 'venv\Scripts\python.exe'
    }
    
    if (Test-Path $pythonExe) {
        try {
            $testScript = @"
import sys
import json
try:
    from pymongo import MongoClient
    from pymongo.errors import ConnectionFailure, OperationFailure
    
    client = MongoClient(
        host='$hostname',
        port=$port,
        username='$username',
        password='$password',
        authSource='admin',
        serverSelectionTimeoutMS=10000
    )
    
    # Test connection with ping
    result = client.admin.command('ping')
    print('PING_SUCCESS')
    
    # Get server info
    server_info = client.server_info()
    print(f'SERVER_VERSION: {server_info.get("version", "unknown")}')
    
    # List databases
    db_list = client.list_database_names()
    print(f'DATABASES: {", ".join(db_list) if db_list else "(empty)"}')
    
    # Try to get database stats
    try:
        admin_db = client.admin
        db_stats = admin_db.command('dbStats')
        data_size = db_stats.get("dataSize", 0)
        print(f'ADMIN_DB_SIZE: {data_size}')
    except Exception as e:
        print(f'ADMIN_DB_SIZE: 0')
    
    # Test write/read if possible
    try:
        from datetime import datetime
        test_db = client.get_database('test')
        test_collection = test_db.get_collection('connection_test')
        test_collection.insert_one({'test': 'connection', 'timestamp': datetime.now().isoformat()})
        count = test_collection.count_documents({})
        test_collection.delete_one({'test': 'connection'})
        print(f'WRITE_READ_TEST: SUCCESS (count={count})')
    except Exception as e:
        print(f'WRITE_READ_TEST: SKIPPED ({str(e)[:50]})')
    
    print('ALL_TESTS_PASSED')
    sys.exit(0)
except ConnectionFailure as e:
    print(f'CONNECTION_ERROR: {e}')
    sys.exit(1)
except OperationFailure as e:
    print(f'AUTH_ERROR: {e}')
    sys.exit(2)
except Exception as e:
    print(f'ERROR: {e}')
    import traceback
    traceback.print_exc()
    sys.exit(3)
"@
            $scriptFile = Join-Path $env:TEMP "test_mongo_$(Get-Random).py"
            Set-Content -Path $scriptFile -Value $testScript -Encoding UTF8
            
            $output = & $pythonExe $scriptFile 2>&1 | Out-String
            Remove-Item $scriptFile -ErrorAction SilentlyContinue
            
            if ($LASTEXITCODE -eq 0) {
                Write-Host "    ✅ MongoDB认证连接成功" -ForegroundColor Green
                
                # Parse and display test results
                try {
                    $outputLines = $output -split "`n" | Where-Object { $_.Trim() }
                    foreach ($line in $outputLines) {
                        $line = $line.Trim()
                        if ([string]::IsNullOrWhiteSpace($line)) { continue }
                        
                        try {
                            if ($line -match '^SERVER_VERSION:') {
                                $version = $line -replace '^SERVER_VERSION:\s*', ''
                                Write-Host "      📌 MongoDB版本: $version" -ForegroundColor Gray
                            } elseif ($line -match '^DATABASES:') {
                                $dbs = $line -replace '^DATABASES:\s*', ''
                                Write-Host "      📌 数据库列表: $dbs" -ForegroundColor Gray
                            } elseif ($line -match '^ADMIN_DB_SIZE:') {
                                $sizeStr = $line -replace '^ADMIN_DB_SIZE:\s*', ''
                                # Try to extract numeric value (handle formats like "0", "0.0", "1234", etc.)
                                if ($sizeStr -match '^(\d+(?:\.\d+)?)$') {
                                    try {
                                        $sizeBytes = [double]$matches[1]
                                        $sizeMB = [math]::Round($sizeBytes / 1MB, 2)
                                        Write-Host "      📌 Admin数据库大小: $sizeMB MB" -ForegroundColor Gray
                                    } catch {
                                        Write-Host "      📌 Admin数据库大小: $sizeStr" -ForegroundColor Gray
                                    }
                                } else {
                                    Write-Host "      📌 Admin数据库大小: $sizeStr" -ForegroundColor Gray
                                }
                            } elseif ($line -match '^WRITE_READ_TEST:') {
                                $testResult = $line -replace '^WRITE_READ_TEST:\s*', ''
                                if ($testResult -match 'SUCCESS') {
                                    Write-Host "      ✅ 读写测试成功: $testResult" -ForegroundColor Green
                                } else {
                                    Write-Host "      ⚠️ 读写测试跳过: $testResult" -ForegroundColor Yellow
                                }
                            }
                        } catch {
                            # Ignore parsing errors for individual lines
                            # Don't display error to avoid cluttering output
                        }
                    }
                } catch {
                    # If parsing fails completely, still consider connection successful
                    Write-Host "      ⚠️ 解析测试结果时遇到问题，但连接测试成功" -ForegroundColor Yellow
                }
                
                return $true
            } else {
                Write-Host "    ❌ MongoDB连接测试失败" -ForegroundColor Red
                $outputLines = $output -split "`n" | Where-Object { $_.Trim() } | Select-Object -First 3
                foreach ($line in $outputLines) {
                    Write-Host "      $($line.Trim())" -ForegroundColor Red
                }
                return $false
            }
        } catch {
            # Check if Python script actually ran successfully
            # If it did, connection test passed even if parsing failed
            if ($LASTEXITCODE -eq 0) {
                Write-Host "    ⚠️ 解析测试结果时遇到问题: $_" -ForegroundColor Yellow
                Write-Host "    ✅ 但MongoDB连接测试本身成功" -ForegroundColor Green
                return $true
            } else {
                Write-Host "    ⚠️ Python连接测试失败: $_" -ForegroundColor Yellow
                return $false
            }
        }
    } else {
        Write-Host "    ⚠️ 未找到Python可执行文件，跳过详细连接测试" -ForegroundColor Yellow
        Write-Host "    💡 提示: TCP连接成功，但无法验证认证和数据库访问" -ForegroundColor Gray
    }
    
    return $true  # TCP connection succeeded
}

function Start-MongoDBWithLogs($mongoExe, $mongoData, $mongoPort, $showLogs) {
    Write-Host "  🚀 启动MongoDB..." -ForegroundColor Cyan
    
    Ensure-Dir $mongoData
    
    # Check if initialized
    $initMarker = Join-Path $mongoData '.mongo_initialized'
    $needsAuth = Test-Path $initMarker
    
    $mongoArgs = "--dbpath `"$mongoData`" --bind_ip 127.0.0.1 --port $mongoPort"
    if ($needsAuth) {
        $mongoArgs += " --auth"
    }
    
    try {
        # Start process without redirecting streams to avoid blocking
        # Use ProcessStartInfo to have better control
        $psi = New-Object System.Diagnostics.ProcessStartInfo
        $psi.FileName = $mongoExe
        $psi.Arguments = $mongoArgs
        $psi.UseShellExecute = $false
        $psi.CreateNoWindow = $true
        # Don't redirect output to avoid blocking on ReadLine()
        $psi.RedirectStandardOutput = $false
        $psi.RedirectStandardError = $false
        
        $process = New-Object System.Diagnostics.Process
        $process.StartInfo = $psi
        $process.Start() | Out-Null
        
        Write-Host "    MongoDB进程已启动 (PID: $($process.Id))" -ForegroundColor Gray
        
        if ($showLogs) {
            Write-Host "    📋 MongoDB启动信息:" -ForegroundColor Cyan
            Write-Host "      ⚠️ 注意: 为避免阻塞，日志输出已禁用" -ForegroundColor Yellow
            Write-Host "      💡 提示: 如需查看详细日志，请检查MongoDB数据目录下的日志文件" -ForegroundColor Gray
            Write-Host "      💡 提示: 或手动运行查看输出: $mongoExe $mongoArgs" -ForegroundColor Gray
        }
        
        # Give MongoDB a moment to start
        Start-Sleep -Seconds 2
        
        if ($process.HasExited) {
            Write-Host "    ❌ MongoDB进程已退出 (退出代码: $($process.ExitCode))" -ForegroundColor Red
            Write-Host "    💡 提示: 请检查MongoDB数据目录权限和日志文件" -ForegroundColor Yellow
            Write-Host "    💡 提示: 或手动运行查看错误: $mongoExe $mongoArgs" -ForegroundColor Gray
            return $null
        } else {
            Write-Host "    ✅ MongoDB进程运行中" -ForegroundColor Green
            Write-Host "    ⏳ 等待MongoDB完全启动（检查端口监听）..." -ForegroundColor Gray
            
            # Wait for port to be listening (max 30 seconds)
            $portReady = $false
            $waitStartTime = Get-Date
            $maxWaitSeconds = 30
            
            while (-not $portReady -and (Get-Date).Subtract($waitStartTime).TotalSeconds -lt $maxWaitSeconds) {
                if ($process.HasExited) {
                    Write-Host "    ❌ MongoDB进程意外退出" -ForegroundColor Red
                    return $null
                }
                
                $portInfo = Get-PortInfo -port $mongoPort
                if ($portInfo.InUse -and $portInfo.ProcessName -eq "mongod") {
                    $portReady = $true
                    break
                }
                Start-Sleep -Seconds 1
            }
            
            if ($portReady) {
                Write-Host "    ✅ MongoDB端口 $mongoPort 已开始监听" -ForegroundColor Green
            } else {
                Write-Host "    ⚠️ MongoDB进程运行中，但端口 $mongoPort 尚未监听（可能仍在启动中）" -ForegroundColor Yellow
            }
            
            return $process
        }
    } catch {
        Write-Host "    ❌ 启动MongoDB失败: $_" -ForegroundColor Red
        return $null
    }
}

function Diagnose-MongoDB($envMap, $root, $start, $showLogs, $testConnection) {
    Write-Host ""
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host "MongoDB 诊断" -ForegroundColor Cyan
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host ""
    
    $mongoPort = if ($envMap.ContainsKey('MONGODB_PORT')) { [int]$envMap['MONGODB_PORT'] } else { 27017 }
    $mongoHost = if ($envMap.ContainsKey('MONGODB_HOST')) { $envMap['MONGODB_HOST'] } else { "localhost" }
    $mongoUsername = if ($envMap.ContainsKey('MONGODB_USERNAME')) { $envMap['MONGODB_USERNAME'] } else { "admin" }
    $mongoPassword = if ($envMap.ContainsKey('MONGODB_PASSWORD')) { $envMap['MONGODB_PASSWORD'] } else { "tradingagents123" }
    
    Write-Host "📋 配置信息:" -ForegroundColor Cyan
    Write-Host "  主机: $mongoHost" -ForegroundColor Gray
    Write-Host "  端口: $mongoPort" -ForegroundColor Gray
    Write-Host "  用户名: $mongoUsername" -ForegroundColor Gray
    Write-Host ""
    
    # Check executable
    $mongoExe = Join-Path $root 'vendors\mongodb\mongodb-win32-x86_64-windows-8.0.13\bin\mongod.exe'
    Write-Host "🔍 检查MongoDB可执行文件..." -ForegroundColor Cyan
    if (-not (Test-Path -LiteralPath $mongoExe)) {
        Write-Host "  ❌ MongoDB可执行文件不存在: $mongoExe" -ForegroundColor Red
        Write-Host "  💡 建议: 检查安装目录是否正确" -ForegroundColor Yellow
        return
    }
    Write-Host "  ✅ MongoDB可执行文件存在" -ForegroundColor Green
    Write-Host ""
    
    # Check data directory
    $mongoData = Join-Path $root 'data\mongodb\db'
    Write-Host "🔍 检查数据目录..." -ForegroundColor Cyan
    if (-not (Test-Path -LiteralPath $mongoData)) {
        Write-Host "  ⚠️ 数据目录不存在，将自动创建: $mongoData" -ForegroundColor Yellow
        Ensure-Dir $mongoData
    } else {
        Write-Host "  ✅ 数据目录存在: $mongoData" -ForegroundColor Green
    }
    Write-Host ""
    
    # Check process
    Write-Host "🔍 检查MongoDB进程..." -ForegroundColor Cyan
    $procInfo = Get-ProcessInfo -processName "mongod"
    if ($procInfo.Exists) {
        Write-Host "  ✅ MongoDB进程正在运行" -ForegroundColor Green
        Write-Host "    PID: $($procInfo.PID)" -ForegroundColor Gray
        Write-Host "    路径: $($procInfo.Path)" -ForegroundColor Gray
        Write-Host "    启动时间: $($procInfo.StartTime)" -ForegroundColor Gray
    } else {
        Write-Host "  ❌ MongoDB进程未运行" -ForegroundColor Red
    }
    Write-Host ""
    
    # Check port
    Write-Host "🔍 检查端口 $mongoPort..." -ForegroundColor Cyan
    $portInfo = Get-PortInfo -port $mongoPort
    if ($portInfo.InUse) {
        Write-Host "  ✅ 端口 $mongoPort 正在监听" -ForegroundColor Green
        Write-Host "    进程: $($portInfo.ProcessName) (PID: $($portInfo.PID))" -ForegroundColor Gray
        if ($portInfo.ProcessName -ne "mongod") {
            Write-Host "    ⚠️ 警告: 端口被其他进程占用!" -ForegroundColor Yellow
        }
    } else {
        Write-Host "  ❌ 端口 $mongoPort 未监听" -ForegroundColor Red
    }
    Write-Host ""
    
    # Test connection
    if ($testConnection) {
        Test-MongoDBConnection -hostname $mongoHost -port $mongoPort -username $mongoUsername -password $mongoPassword | Out-Null
        Write-Host ""
    }
    
    # Start if requested and not running
    if ($start -and -not $procInfo.Exists) {
        Write-Host "🔧 尝试启动MongoDB..." -ForegroundColor Cyan
        $process = Start-MongoDBWithLogs -mongoExe $mongoExe -mongoData $mongoData -mongoPort $mongoPort -showLogs $showLogs
        
        if ($process) {
            Write-Host ""
            Write-Host "  ⏳ 等待MongoDB完全启动..." -ForegroundColor Yellow
            # Wait a bit more for MongoDB to be fully ready
            Start-Sleep -Seconds 3
            
            # Re-check process and port
            $procInfo = Get-ProcessInfo -processName "mongod"
            $portInfo = Get-PortInfo -port $mongoPort
            
            if ($procInfo.Exists -and $portInfo.InUse -and $portInfo.ProcessName -eq "mongod") {
                Write-Host "  ✅ MongoDB启动成功!" -ForegroundColor Green
                Write-Host ""
                
                # Automatically test connection after startup
                Write-Host "🔍 自动测试MongoDB连接..." -ForegroundColor Cyan
                $connectionOk = Test-MongoDBConnection -hostname $mongoHost -port $mongoPort -username $mongoUsername -password $mongoPassword
                Write-Host ""
                
                if ($connectionOk) {
                    Write-Host "  ✅ MongoDB连接测试成功，服务已就绪" -ForegroundColor Green
                } else {
                    Write-Host "  ⚠️ MongoDB进程运行中，但连接测试失败" -ForegroundColor Yellow
                    Write-Host "  💡 提示: MongoDB可能仍在初始化中，请稍后重试" -ForegroundColor Gray
                }
            } else {
                Write-Host "  ❌ MongoDB启动失败，进程已退出或端口未监听" -ForegroundColor Red
            }
        } else {
            Write-Host "  ❌ MongoDB启动失败" -ForegroundColor Red
        }
        Write-Host ""
    } elseif ($start -and $procInfo.Exists) {
        Write-Host "  ℹ️ MongoDB已在运行，无需启动" -ForegroundColor Cyan
        Write-Host ""
        
        # Test connection if already running
        if ($testConnection) {
            Write-Host "🔍 测试MongoDB连接..." -ForegroundColor Cyan
            $connectionOk = Test-MongoDBConnection -hostname $mongoHost -port $mongoPort -username $mongoUsername -password $mongoPassword
            Write-Host ""
        }
    }
    
    # Summary and Error Diagnostics
    Write-Host "📊 诊断摘要:" -ForegroundColor Cyan
    $procInfo = Get-ProcessInfo -processName "mongod"
    $portInfo = Get-PortInfo -port $mongoPort
    
    if ($procInfo.Exists -and $portInfo.InUse -and $portInfo.ProcessName -eq "mongod") {
        Write-Host "  ✅ MongoDB运行正常" -ForegroundColor Green
    } else {
        Write-Host "  ❌ MongoDB存在问题" -ForegroundColor Red
        Write-Host ""
        Write-Host "🔧 错误诊断和修复建议:" -ForegroundColor Yellow
        
        if (-not $procInfo.Exists) {
            Write-Host "  ❌ 问题: MongoDB进程未运行" -ForegroundColor Red
            Write-Host "    可能原因:" -ForegroundColor Gray
            Write-Host "      1. MongoDB未启动" -ForegroundColor Gray
            Write-Host "      2. MongoDB启动后立即崩溃" -ForegroundColor Gray
            Write-Host "      3. 数据目录权限问题" -ForegroundColor Gray
            Write-Host "      4. 数据文件损坏" -ForegroundColor Gray
            Write-Host "    修复建议:" -ForegroundColor Cyan
            Write-Host "      - 使用 -Start 参数尝试启动: .\debug_services.ps1 -Service mongodb -Start -ShowLogs" -ForegroundColor Gray
            Write-Host "      - 检查数据目录权限: $mongoData" -ForegroundColor Gray
            Write-Host "      - 查看MongoDB日志文件（如果存在）" -ForegroundColor Gray
            Write-Host ""
        }
        
        if (-not $portInfo.InUse) {
            Write-Host "  ❌ 问题: 端口 $mongoPort 未监听" -ForegroundColor Red
            Write-Host "    可能原因:" -ForegroundColor Gray
            Write-Host "      1. MongoDB进程未启动" -ForegroundColor Gray
            Write-Host "      2. MongoDB启动失败" -ForegroundColor Gray
            Write-Host "      3. 端口配置错误" -ForegroundColor Gray
            Write-Host "    修复建议:" -ForegroundColor Cyan
            Write-Host "      - 检查 .env 文件中的 MONGODB_PORT 配置" -ForegroundColor Gray
            Write-Host "      - 使用 -Start 参数启动MongoDB: .\debug_services.ps1 -Service mongodb -Start" -ForegroundColor Gray
            Write-Host "      - 检查防火墙是否阻止了端口" -ForegroundColor Gray
            Write-Host ""
        }
        
        if ($portInfo.InUse -and $portInfo.ProcessName -ne "mongod") {
            Write-Host "  ⚠️ 问题: 端口 $mongoPort 被其他进程占用" -ForegroundColor Yellow
            Write-Host "    占用进程: $($portInfo.ProcessName) (PID: $($portInfo.PID))" -ForegroundColor Gray
            Write-Host "    修复建议:" -ForegroundColor Cyan
            Write-Host "      - 停止占用端口的进程: Stop-Process -Id $($portInfo.PID) -Force" -ForegroundColor Gray
            Write-Host "      - 或修改 .env 文件中的 MONGODB_PORT 使用其他端口" -ForegroundColor Gray
            Write-Host ""
        }
        
        # Check data directory permissions
        if (Test-Path -LiteralPath $mongoData) {
            try {
                $testFile = Join-Path $mongoData "test_write_$(Get-Random).tmp"
                [System.IO.File]::WriteAllText($testFile, "test")
                Remove-Item $testFile -ErrorAction SilentlyContinue
            } catch {
                Write-Host "  ⚠️ 问题: 数据目录权限不足" -ForegroundColor Yellow
                Write-Host "    目录: $mongoData" -ForegroundColor Gray
                Write-Host "    修复建议:" -ForegroundColor Cyan
                Write-Host "      - 以管理员身份运行PowerShell" -ForegroundColor Gray
                Write-Host "      - 检查目录权限: icacls `"$mongoData`"" -ForegroundColor Gray
                Write-Host "      - 授予当前用户完全控制权限" -ForegroundColor Gray
                Write-Host ""
            }
        }
    }
    Write-Host ""
}

# ============================================================================
# Redis Diagnostic Functions
# ============================================================================

function Test-RedisConnection($hostname, $port, $password) {
    Write-Host "  📡 测试Redis连接..." -ForegroundColor Gray
    
    # First test TCP connection
    if (-not (Test-TcpConnection -hostname $hostname -port $port -timeoutSeconds 5)) {
        Write-Host "    ❌ TCP连接失败: 无法连接到 $hostname`:$port" -ForegroundColor Red
        return $false
    }
    Write-Host "    ✅ TCP连接成功" -ForegroundColor Green
    
    # Try Python connection test if available
    $pythonExe = Join-Path $root 'vendors\python\python.exe'
    if (-not (Test-Path $pythonExe)) {
        $pythonExe = Join-Path $root 'venv\Scripts\python.exe'
    }
    
    if (Test-Path $pythonExe) {
        try {
            $testScript = @"
import sys
try:
    import redis
    
    r = redis.Redis(
        host='$hostname',
        port=$port,
        password='$password',
        socket_connect_timeout=5,
        decode_responses=True
    )
    
    # Test connection
    r.ping()
    print('SUCCESS')
    sys.exit(0)
except redis.ConnectionError as e:
    print(f'CONNECTION_ERROR: {e}')
    sys.exit(1)
except redis.AuthenticationError as e:
    print(f'AUTH_ERROR: {e}')
    sys.exit(2)
except Exception as e:
    print(f'ERROR: {e}')
    sys.exit(3)
"@
            $scriptFile = Join-Path $env:TEMP "test_redis_$(Get-Random).py"
            Set-Content -Path $scriptFile -Value $testScript -Encoding UTF8
            
            $output = & $pythonExe $scriptFile 2>&1
            Remove-Item $scriptFile -ErrorAction SilentlyContinue
            
            if ($LASTEXITCODE -eq 0) {
                Write-Host "    ✅ Redis认证连接成功" -ForegroundColor Green
                return $true
            } else {
                Write-Host "    ⚠️ Redis连接测试: $output" -ForegroundColor Yellow
                return $false
            }
        } catch {
            Write-Host "    ⚠️ Python连接测试失败: $_" -ForegroundColor Yellow
        }
    }
    
    return $true  # TCP connection succeeded
}

function Start-RedisWithLogs($redisExe, $root, $redisPort, $showLogs) {
    Write-Host "  🚀 启动Redis..." -ForegroundColor Cyan
    
    # Ensure directories
    $redisData = Join-Path $root 'data\redis\data'
    Ensure-Dir $redisData
    Ensure-Dir (Join-Path $root 'runtime')
    
    # Create Redis config
    $redisConf = Join-Path $root 'runtime\redis.conf'
    $redisDataUnix = $redisData -replace '\\', '/'
    $conf = @(
        "bind 127.0.0.1",
        "port $redisPort",
        "dir $redisDataUnix",
        "requirepass tradingagents123",
        "appendonly yes",
        "save 900 1",
        "save 300 10",
        "save 60 10000"
    )
    $utf8NoBom = New-Object System.Text.UTF8Encoding $false
    [System.IO.File]::WriteAllText($redisConf, ($conf -join "`n"), $utf8NoBom)
    
    $redisConfRelative = "runtime\redis.conf"
    
    try {
        $psi = New-Object System.Diagnostics.ProcessStartInfo
        $psi.FileName = $redisExe
        $psi.Arguments = "`"$redisConfRelative`""
        $psi.UseShellExecute = $false
        $psi.CreateNoWindow = $true
        $psi.RedirectStandardOutput = $true
        $psi.RedirectStandardError = $true
        $psi.WorkingDirectory = $root
        
        $process = [System.Diagnostics.Process]::Start($psi)
        Write-Host "    Redis进程已启动 (PID: $($process.Id))" -ForegroundColor Gray
        
        # Wait and capture output
        Start-Sleep -Seconds 5
        
        if ($showLogs) {
            Write-Host "    📋 Redis启动日志:" -ForegroundColor Cyan
            try {
                $stdout = ""
                $stderr = ""
                while ($process.StandardOutput.Peek() -gt -1) {
                    $line = $process.StandardOutput.ReadLine()
                    $stdout += $line + "`n"
                    Write-Host "      $line" -ForegroundColor Gray
                }
                while ($process.StandardError.Peek() -gt -1) {
                    $line = $process.StandardError.ReadLine()
                    $stderr += $line + "`n"
                    Write-Host "      $line" -ForegroundColor Yellow
                }
            } catch {
                # Ignore read errors
            }
        }
        
        if ($process.HasExited) {
            Write-Host "    ❌ Redis进程已退出 (退出代码: $($process.ExitCode))" -ForegroundColor Red
            
            # Try to read error output for diagnostics
            try {
                $errorOutput = ""
                while ($process.StandardError.Peek() -gt -1) {
                    $errorOutput += $process.StandardError.ReadLine() + "`n"
                }
                if ($errorOutput) {
                    Write-Host "    📋 错误输出:" -ForegroundColor Yellow
                    $errorOutput -split "`n" | ForEach-Object {
                        if ($_.Trim()) {
                            Write-Host "      $_" -ForegroundColor Yellow
                        }
                    }
                    
                    # Common error patterns
                    if ($errorOutput -match "Address already in use|bind.*failed") {
                        Write-Host "    💡 诊断: 端口可能已被占用" -ForegroundColor Cyan
                    }
                    if ($errorOutput -match "Permission denied|access denied") {
                        Write-Host "    💡 诊断: 权限不足，请以管理员身份运行" -ForegroundColor Cyan
                    }
                    if ($errorOutput -match "config.*error|parse.*error") {
                        Write-Host "    💡 诊断: 配置文件可能有错误，检查 runtime\redis.conf" -ForegroundColor Cyan
                    }
                }
            } catch {
                # Ignore read errors
            }
            
            return $null
        } else {
            Write-Host "    ✅ Redis进程运行中" -ForegroundColor Green
            return $process
        }
    } catch {
        Write-Host "    ❌ 启动Redis失败: $_" -ForegroundColor Red
        return $null
    }
}

function Diagnose-Redis($envMap, $root, $start, $showLogs, $testConnection) {
    Write-Host ""
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host "Redis 诊断" -ForegroundColor Cyan
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host ""
    
    $redisPort = if ($envMap.ContainsKey('REDIS_PORT')) { [int]$envMap['REDIS_PORT'] } else { 6379 }
    $redisHost = if ($envMap.ContainsKey('REDIS_HOST')) { $envMap['REDIS_HOST'] } else { "localhost" }
    $redisPassword = if ($envMap.ContainsKey('REDIS_PASSWORD')) { $envMap['REDIS_PASSWORD'] } else { "tradingagents123" }
    
    Write-Host "📋 配置信息:" -ForegroundColor Cyan
    Write-Host "  主机: $redisHost" -ForegroundColor Gray
    Write-Host "  端口: $redisPort" -ForegroundColor Gray
    Write-Host ""
    
    # Check executable
    $redisExe = Join-Path $root 'vendors\redis\Redis-8.2.2-Windows-x64-msys2\redis-server.exe'
    Write-Host "🔍 检查Redis可执行文件..." -ForegroundColor Cyan
    if (-not (Test-Path -LiteralPath $redisExe)) {
        Write-Host "  ❌ Redis可执行文件不存在: $redisExe" -ForegroundColor Red
        Write-Host "  💡 建议: 检查安装目录是否正确" -ForegroundColor Yellow
        return
    }
    Write-Host "  ✅ Redis可执行文件存在" -ForegroundColor Green
    Write-Host ""
    
    # Check data directory
    $redisData = Join-Path $root 'data\redis\data'
    Write-Host "🔍 检查数据目录..." -ForegroundColor Cyan
    if (-not (Test-Path -LiteralPath $redisData)) {
        Write-Host "  ⚠️ 数据目录不存在，将自动创建: $redisData" -ForegroundColor Yellow
        Ensure-Dir $redisData
    } else {
        Write-Host "  ✅ 数据目录存在: $redisData" -ForegroundColor Green
    }
    Write-Host ""
    
    # Check process
    Write-Host "🔍 检查Redis进程..." -ForegroundColor Cyan
    $procInfo = Get-ProcessInfo -processName "redis-server"
    if ($procInfo.Exists) {
        Write-Host "  ✅ Redis进程正在运行" -ForegroundColor Green
        Write-Host "    PID: $($procInfo.PID)" -ForegroundColor Gray
        Write-Host "    路径: $($procInfo.Path)" -ForegroundColor Gray
        Write-Host "    启动时间: $($procInfo.StartTime)" -ForegroundColor Gray
    } else {
        Write-Host "  ❌ Redis进程未运行" -ForegroundColor Red
    }
    Write-Host ""
    
    # Check port
    Write-Host "🔍 检查端口 $redisPort..." -ForegroundColor Cyan
    $portInfo = Get-PortInfo -port $redisPort
    if ($portInfo.InUse) {
        Write-Host "  ✅ 端口 $redisPort 正在监听" -ForegroundColor Green
        Write-Host "    进程: $($portInfo.ProcessName) (PID: $($portInfo.PID))" -ForegroundColor Gray
        if ($portInfo.ProcessName -ne "redis-server") {
            Write-Host "    ⚠️ 警告: 端口被其他进程占用!" -ForegroundColor Yellow
        }
    } else {
        Write-Host "  ❌ 端口 $redisPort 未监听" -ForegroundColor Red
    }
    Write-Host ""
    
    # Test connection
    if ($testConnection) {
        Test-RedisConnection -hostname $redisHost -port $redisPort -password $redisPassword | Out-Null
        Write-Host ""
    }
    
    # Start if requested and not running
    if ($start -and -not $procInfo.Exists) {
        Write-Host "🔧 尝试启动Redis..." -ForegroundColor Cyan
        $process = Start-RedisWithLogs -redisExe $redisExe -root $root -redisPort $redisPort -showLogs $showLogs
        
        if ($process) {
            Write-Host ""
            Write-Host "  ⏳ 等待Redis启动完成..." -ForegroundColor Yellow
            Start-Sleep -Seconds 3
            
            # Re-check
            $procInfo = Get-ProcessInfo -processName "redis-server"
            if ($procInfo.Exists) {
                Write-Host "  ✅ Redis启动成功!" -ForegroundColor Green
            } else {
                Write-Host "  ❌ Redis启动失败，进程已退出" -ForegroundColor Red
            }
        } else {
            Write-Host "  ❌ Redis启动失败" -ForegroundColor Red
        }
        Write-Host ""
    } elseif ($start -and $procInfo.Exists) {
        Write-Host "  ℹ️ Redis已在运行，无需启动" -ForegroundColor Cyan
        Write-Host ""
    }
    
    # Summary and Error Diagnostics
    Write-Host "📊 诊断摘要:" -ForegroundColor Cyan
    $procInfo = Get-ProcessInfo -processName "redis-server"
    $portInfo = Get-PortInfo -port $redisPort
    
    if ($procInfo.Exists -and $portInfo.InUse -and $portInfo.ProcessName -eq "redis-server") {
        Write-Host "  ✅ Redis运行正常" -ForegroundColor Green
    } else {
        Write-Host "  ❌ Redis存在问题" -ForegroundColor Red
        Write-Host ""
        Write-Host "🔧 错误诊断和修复建议:" -ForegroundColor Yellow
        
        if (-not $procInfo.Exists) {
            Write-Host "  ❌ 问题: Redis进程未运行" -ForegroundColor Red
            Write-Host "    可能原因:" -ForegroundColor Gray
            Write-Host "      1. Redis未启动" -ForegroundColor Gray
            Write-Host "      2. Redis启动后立即崩溃" -ForegroundColor Gray
            Write-Host "      3. 配置文件错误" -ForegroundColor Gray
            Write-Host "      4. 数据目录权限问题" -ForegroundColor Gray
            Write-Host "    修复建议:" -ForegroundColor Cyan
            Write-Host "      - 使用 -Start 参数尝试启动: .\debug_services.ps1 -Service redis -Start -ShowLogs" -ForegroundColor Gray
            Write-Host "      - 检查配置文件: $root\runtime\redis.conf" -ForegroundColor Gray
            Write-Host "      - 检查数据目录权限: $redisData" -ForegroundColor Gray
            Write-Host ""
        }
        
        if (-not $portInfo.InUse) {
            Write-Host "  ❌ 问题: 端口 $redisPort 未监听" -ForegroundColor Red
            Write-Host "    可能原因:" -ForegroundColor Gray
            Write-Host "      1. Redis进程未启动" -ForegroundColor Gray
            Write-Host "      2. Redis启动失败" -ForegroundColor Gray
            Write-Host "      3. 端口配置错误" -ForegroundColor Gray
            Write-Host "    修复建议:" -ForegroundColor Cyan
            Write-Host "      - 检查 .env 文件中的 REDIS_PORT 配置" -ForegroundColor Gray
            Write-Host "      - 使用 -Start 参数启动Redis: .\debug_services.ps1 -Service redis -Start" -ForegroundColor Gray
            Write-Host "      - 检查防火墙是否阻止了端口" -ForegroundColor Gray
            Write-Host ""
        }
        
        if ($portInfo.InUse -and $portInfo.ProcessName -ne "redis-server") {
            Write-Host "  ⚠️ 问题: 端口 $redisPort 被其他进程占用" -ForegroundColor Yellow
            Write-Host "    占用进程: $($portInfo.ProcessName) (PID: $($portInfo.PID))" -ForegroundColor Gray
            Write-Host "    修复建议:" -ForegroundColor Cyan
            Write-Host "      - 停止占用端口的进程: Stop-Process -Id $($portInfo.PID) -Force" -ForegroundColor Gray
            Write-Host "      - 或修改 .env 文件中的 REDIS_PORT 使用其他端口" -ForegroundColor Gray
            Write-Host ""
        }
        
        # Check Redis config file
        $redisConf = Join-Path $root 'runtime\redis.conf'
        if (-not (Test-Path -LiteralPath $redisConf)) {
            Write-Host "  ⚠️ 问题: Redis配置文件不存在" -ForegroundColor Yellow
            Write-Host "    文件: $redisConf" -ForegroundColor Gray
            Write-Host "    修复建议:" -ForegroundColor Cyan
            Write-Host "      - 配置文件会在启动时自动创建" -ForegroundColor Gray
            Write-Host "      - 使用 -Start 参数启动Redis: .\debug_services.ps1 -Service redis -Start" -ForegroundColor Gray
            Write-Host ""
        }
        
        # Check data directory permissions
        if (Test-Path -LiteralPath $redisData) {
            try {
                $testFile = Join-Path $redisData "test_write_$(Get-Random).tmp"
                [System.IO.File]::WriteAllText($testFile, "test")
                Remove-Item $testFile -ErrorAction SilentlyContinue
            } catch {
                Write-Host "  ⚠️ 问题: 数据目录权限不足" -ForegroundColor Yellow
                Write-Host "    目录: $redisData" -ForegroundColor Gray
                Write-Host "    修复建议:" -ForegroundColor Cyan
                Write-Host "      - 以管理员身份运行PowerShell" -ForegroundColor Gray
                Write-Host "      - 检查目录权限: icacls `"$redisData`"" -ForegroundColor Gray
                Write-Host "      - 授予当前用户完全控制权限" -ForegroundColor Gray
                Write-Host ""
            }
        }
    }
    Write-Host ""
}

# ============================================================================
# Main Script
# ============================================================================

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "TradingAgents-CN 服务诊断工具" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Load environment variables
Write-Host "📋 加载配置文件..." -ForegroundColor Cyan
Write-Host "  项目根目录: $root" -ForegroundColor Gray
if (Test-Path $envPath) {
    Write-Host "  ✅ 找到 .env 文件: $envPath" -ForegroundColor Green
} else {
    Write-Host "  ⚠️ 未找到 .env 文件: $envPath" -ForegroundColor Yellow
    Write-Host "  将使用默认配置" -ForegroundColor Gray
}
Write-Host ""

$envMap = Load-Env $envPath

# Run diagnostics
if ($Service -eq "mongodb" -or $Service -eq "all") {
    Diagnose-MongoDB -envMap $envMap -root $root -start $Start -showLogs $ShowLogs -testConnection $TestConnection
}

if ($Service -eq "redis" -or $Service -eq "all") {
    Diagnose-Redis -envMap $envMap -root $root -start $Start -showLogs $ShowLogs -testConnection $TestConnection
}

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "诊断完成" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
