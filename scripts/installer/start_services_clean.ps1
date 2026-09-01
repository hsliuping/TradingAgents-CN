# TradingAgents-CN Services Starter (Clean English Version)
# Start MongoDB and Redis services without Chinese characters.

param(
    [switch]$SkipMongoDB,
    [switch]$SkipRedis
)

$ErrorActionPreference = 'Stop'

# The distributable package contains copies at its root, while the source tree
# keeps the canonical scripts under scripts\installer. Support both layouts.
$root = $PSScriptRoot
$parent = Split-Path -Parent $PSScriptRoot
if ((Split-Path -Leaf $PSScriptRoot) -eq 'installer' -and
    (Split-Path -Leaf $parent) -eq 'scripts') {
    $root = Split-Path -Parent $parent
}

$envPath = Join-Path $root '.env'

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
                if ($val.Length -ge 2 -and
                    (($val.StartsWith('"') -and $val.EndsWith('"')) -or
                     ($val.StartsWith("'") -and $val.EndsWith("'")))) {
                    $val = $val.Substring(1, $val.Length - 2)
                }
                $map[$key] = $val
            }
        }
    }
    return $map
}

function Get-ConfiguredInt($map, $key, $default) {
    if (-not $map.ContainsKey($key) -or [string]::IsNullOrWhiteSpace($map[$key])) {
        return [int]$default
    }
    try {
        return [int]$map[$key]
    } catch {
        throw "Invalid integer value for ${key}: $($map[$key])"
    }
}

function Get-ConfiguredValue($map, $key, $default) {
    if ($map.ContainsKey($key) -and -not [string]::IsNullOrWhiteSpace($map[$key])) {
        return [string]$map[$key]
    }
    return [string]$default
}

$envMap = Load-Env $envPath
$mongoHost = Get-ConfiguredValue $envMap 'MONGODB_HOST' 'localhost'
$mongoPort = Get-ConfiguredInt $envMap 'MONGODB_PORT' 27017
$mongoUsername = Get-ConfiguredValue $envMap 'MONGODB_USERNAME' 'admin'
$mongoPassword = Get-ConfiguredValue $envMap 'MONGODB_PASSWORD' 'tradingagents123'
$mongoAuthSource = Get-ConfiguredValue $envMap 'MONGODB_AUTH_SOURCE' 'admin'
$redisPort = Get-ConfiguredInt $envMap 'REDIS_PORT' 6379

$mongoExe = Join-Path $root 'vendors\mongodb\mongodb-win32-x86_64-windows-8.0.13\bin\mongod.exe'
$redisExe = Join-Path $root 'vendors\redis\Redis-8.2.2-Windows-x64-msys2\redis-server.exe'
$mongoData = Join-Path $root 'data\mongodb\db'
$redisData = Join-Path $root 'data\redis\data'
$logsDir = Join-Path $root 'logs'
$mongoProbeHost = $mongoHost
if ([string]::IsNullOrWhiteSpace($mongoProbeHost) -or
    $mongoProbeHost -eq '0.0.0.0' -or $mongoProbeHost -eq '::' -or $mongoProbeHost -eq '*') {
    $mongoProbeHost = '127.0.0.1'
}

function Ensure-Dir($path) {
    if (-not (Test-Path -LiteralPath $path)) {
        New-Item -ItemType Directory -Path $path -Force | Out-Null
    }
}

function Check-Port($Port, $ServiceName) {
    Write-Host "  Checking port $Port..." -ForegroundColor Gray
    $portInUse = @(Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue)
    if ($portInUse.Count -gt 0) {
        Write-Host "  WARNING: Port $Port is already in use!" -ForegroundColor Yellow
        foreach ($conn in $portInUse) {
            $process = Get-Process -Id $conn.OwningProcess -ErrorAction SilentlyContinue
            if (-not $process) { continue }

            Write-Host "    Process: $($process.ProcessName) (PID: $($process.Id))" -ForegroundColor Gray
            $shouldStop = (($ServiceName -eq 'MongoDB' -and $process.ProcessName -eq 'mongod') -or
                ($ServiceName -eq 'Redis' -and $process.ProcessName -eq 'redis-server'))

            if ($shouldStop) {
                Write-Host "  Stopping existing $ServiceName process (PID: $($process.Id))..." -ForegroundColor Yellow
                try {
                    Stop-Process -Id $process.Id -Force -ErrorAction Stop
                    Start-Sleep -Seconds 2
                    Write-Host "  Existing $ServiceName process stopped" -ForegroundColor Green
                } catch {
                    Write-Host "  ERROR: Failed to stop process: $_" -ForegroundColor Red
                    return $false
                }
            } else {
                Write-Host "  ERROR: Port $Port is occupied by another application" -ForegroundColor Red
                return $false
            }
        }
    }
    return $true
}

function Test-TcpPort {
    param(
        [string]$HostName,
        [int]$Port,
        [int]$TimeoutMilliseconds = 1000
    )

    $client = New-Object System.Net.Sockets.TcpClient
    try {
        $connectTask = $client.ConnectAsync($HostName, $Port)
        return ($connectTask.Wait($TimeoutMilliseconds) -and $client.Connected)
    } catch {
        return $false
    } finally {
        $client.Dispose()
    }
}

function Wait-ForTcpPort {
    param(
        [string]$HostName,
        [int]$Port,
        [int]$TimeoutSeconds = 60
    )

    for ($attempt = 0; $attempt -lt $TimeoutSeconds; $attempt++) {
        if (Test-TcpPort -HostName $HostName -Port $Port) {
            return $true
        }
        Start-Sleep -Seconds 1
    }
    return (Test-TcpPort -HostName $HostName -Port $Port)
}

function Resolve-PythonExecutable {
    $candidates = @(
        (Join-Path $root 'venv\Scripts\python.exe'),
        (Join-Path $root 'vendors\python\python.exe')
    )
    foreach ($candidate in $candidates) {
        if (Test-Path -LiteralPath $candidate) {
            return $candidate
        }
    }

    $pythonCommand = Get-Command python.exe -ErrorAction SilentlyContinue
    if ($pythonCommand) { return $pythonCommand.Source }
    $pythonCommand = Get-Command python -ErrorAction SilentlyContinue
    if ($pythonCommand) { return $pythonCommand.Source }
    return $null
}

function Start-MongoProcess {
    param(
        [switch]$WithAuth,
        [string]$LogPrefix = 'mongodb'
    )

    $stdoutPath = Join-Path $logsDir "$LogPrefix`_stdout.log"
    $stderrPath = Join-Path $logsDir "$LogPrefix`_stderr.log"
    $arguments = "--dbpath `"$mongoData`" --bind_ip 127.0.0.1 --port $mongoPort"
    if ($WithAuth) { $arguments = "$arguments --auth" }

    Write-Host "  MongoDB command: $mongoExe $arguments" -ForegroundColor Gray
    $process = Start-Process -FilePath $mongoExe -ArgumentList $arguments `
        -WorkingDirectory $root -WindowStyle Hidden -PassThru `
        -RedirectStandardOutput $stdoutPath -RedirectStandardError $stderrPath
    if (-not $process) {
        throw 'MongoDB process could not be started'
    }
    return [pscustomobject]@{
        Process = $process
        StdOut = $stdoutPath
        StdErr = $stderrPath
    }
}

function Stop-MongoProcess($processInfo) {
    if (-not $processInfo -or -not $processInfo.Process) { return }
    try {
        if (-not $processInfo.Process.HasExited) {
            $processInfo.Process.Kill()
            if (-not $processInfo.Process.WaitForExit(5000)) {
                Stop-Process -Id $processInfo.Process.Id -Force -ErrorAction SilentlyContinue
            }
        }
    } catch {
        Write-Host "  WARNING: Failed to stop MongoDB process: $_" -ForegroundColor Yellow
    }
}

function Show-MongoDiagnostics($processInfo) {
    if (-not $processInfo) { return }
    foreach ($entry in @(
        @{ Label = 'STDOUT'; Path = $processInfo.StdOut },
        @{ Label = 'STDERR'; Path = $processInfo.StdErr }
    )) {
        if (Test-Path -LiteralPath $entry.Path) {
            $content = Get-Content -LiteralPath $entry.Path -ErrorAction SilentlyContinue
            if ($content) {
                Write-Host "  MongoDB $($entry.Label):" -ForegroundColor Gray
                $content | ForEach-Object { Write-Host "    $_" -ForegroundColor Gray }
            }
        }
    }
}

function Invoke-MongoUserScript {
    param([switch]$VerifyOnly)

    $scriptArguments = @(
        $initScript,
        $mongoProbeHost,
        ([string]$mongoPort),
        $mongoUsername,
        $mongoPassword,
        '--auth-source',
        $mongoAuthSource
    )
    if ($VerifyOnly) {
        $scriptArguments += '--verify-only'
    } else {
        $scriptArguments += '--create-only'
    }

    $mode = if ($VerifyOnly) { 'verification' } else { 'initialization' }
    Write-Host "  Running MongoDB user $mode on ${mongoProbeHost}:$mongoPort..." -ForegroundColor Gray
    $output = & $pythonExe @scriptArguments 2>&1
    $exitCode = $LASTEXITCODE
    if ($output) {
        $output | ForEach-Object { Write-Host "    $_" -ForegroundColor Gray }
    }
    return [int]$exitCode
}

function Start-Proc($FilePath, $Arguments, $Name, $WaitSeconds = 3, $WorkingDirectory = $null) {
    Write-Host "Starting $Name..."
    Write-Host "  Command: $FilePath $Arguments"
    try {
        $psi = New-Object System.Diagnostics.ProcessStartInfo
        $psi.FileName = $FilePath
        $psi.Arguments = $Arguments
        $psi.UseShellExecute = $false
        $psi.CreateNoWindow = $true
        if ($WorkingDirectory) {
            $psi.WorkingDirectory = $WorkingDirectory
            Write-Host "  Working Directory: $WorkingDirectory"
        }

        $process = [System.Diagnostics.Process]::Start($psi)
        Write-Host "  Process started, waiting $WaitSeconds seconds..."
        Start-Sleep -Seconds $WaitSeconds

        if ($process.HasExited) {
            Write-Host "Failed to start $Name (process exited)" -ForegroundColor Red
            return $null
        }
        Write-Host "$Name started with PID: $($process.Id)" -ForegroundColor Green
        return $process
    } catch {
        Write-Host "Error starting $Name`: $_" -ForegroundColor Red
        return $null
    }
}

Ensure-Dir $logsDir

# Start MongoDB
if (-not $SkipMongoDB) {
    if (-not (Test-Path -LiteralPath $mongoExe)) {
        Write-Host "ERROR: MongoDB executable not found: $mongoExe" -ForegroundColor Red
        exit 1
    }
    if (-not (Check-Port -Port $mongoPort -ServiceName 'MongoDB')) {
        Write-Host "ERROR: Cannot start MongoDB - port $mongoPort is not available" -ForegroundColor Red
        exit 1
    }

    Ensure-Dir $mongoData
    $initMarker = Join-Path $mongoData '.mongo_initialized'
    $pythonExe = Resolve-PythonExecutable
    $initScript = Join-Path $root 'scripts\init_mongodb_user.py'

    if (-not $pythonExe) {
        Write-Host 'ERROR: Python executable not found; MongoDB initialization cannot continue' -ForegroundColor Red
        exit 1
    }
    if (-not (Test-Path -LiteralPath $initScript)) {
        Write-Host "ERROR: MongoDB initialization helper not found: $initScript" -ForegroundColor Red
        exit 1
    }

    if (-not (Test-Path -LiteralPath $initMarker)) {
        Write-Host 'Initializing MongoDB for first time...' -ForegroundColor Yellow
        $initializationSucceeded = $false
        $initProcessInfo = $null
        $verifyProcessInfo = $null

        try {
            $initProcessInfo = Start-MongoProcess -LogPrefix 'mongodb_init'
            Write-Host "  Waiting for MongoDB on ${mongoProbeHost}:$mongoPort..." -ForegroundColor Gray
            if (-not (Wait-ForTcpPort -HostName $mongoProbeHost -Port $mongoPort -TimeoutSeconds 60)) {
                throw "MongoDB did not become reachable on ${mongoProbeHost}:$mongoPort"
            }

            $exitCode = Invoke-MongoUserScript
            if ($exitCode -ne 0) {
                throw "MongoDB user initialization returned exit code $exitCode"
            }

            Stop-MongoProcess $initProcessInfo
            $verifyProcessInfo = Start-MongoProcess -WithAuth -LogPrefix 'mongodb_init_auth'
            if (-not (Wait-ForTcpPort -HostName $mongoProbeHost -Port $mongoPort -TimeoutSeconds 60)) {
                throw "MongoDB with authentication did not become reachable on ${mongoProbeHost}:$mongoPort"
            }

            $exitCode = Invoke-MongoUserScript -VerifyOnly
            if ($exitCode -ne 0) {
                throw "MongoDB authentication verification returned exit code $exitCode"
            }
            $initializationSucceeded = $true
        } catch {
            Write-Host "ERROR: MongoDB initialization failed: $_" -ForegroundColor Red
        } finally {
            Stop-MongoProcess $verifyProcessInfo
            Stop-MongoProcess $initProcessInfo
        }

        if (-not $initializationSucceeded) {
            Show-MongoDiagnostics $initProcessInfo
            Show-MongoDiagnostics $verifyProcessInfo
            Write-Host '  No initialization marker was created. Existing database data was not removed.' -ForegroundColor Yellow
            exit 1
        }

        try {
            Set-Content -LiteralPath $initMarker -Value (Get-Date).ToString('o') -Encoding UTF8 -ErrorAction Stop
        } catch {
            Write-Host "ERROR: MongoDB was initialized, but the marker could not be written: $_" -ForegroundColor Red
            exit 1
        }
        Write-Host 'MongoDB initialization completed' -ForegroundColor Green
    } else {
        Write-Host 'MongoDB initialization marker found; validating authentication' -ForegroundColor Gray
    }

    # Start MongoDB with authentication and verify the final process. This
    # also detects stale markers from older failed startup attempts.
    $mongoProcessInfo = $null
    try {
        $mongoProcessInfo = Start-MongoProcess -WithAuth -LogPrefix 'mongodb'
        if (-not (Wait-ForTcpPort -HostName $mongoProbeHost -Port $mongoPort -TimeoutSeconds 60)) {
            throw "MongoDB did not become reachable on ${mongoProbeHost}:$mongoPort"
        }
        $exitCode = Invoke-MongoUserScript -VerifyOnly
        if ($exitCode -ne 0) {
            throw "MongoDB authentication verification returned exit code $exitCode"
        }
        Write-Host "MongoDB is ready on ${mongoProbeHost}:$mongoPort" -ForegroundColor Green
    } catch {
        Write-Host "ERROR: MongoDB failed to start or authenticate: $_" -ForegroundColor Red
        Stop-MongoProcess $mongoProcessInfo
        Show-MongoDiagnostics $mongoProcessInfo
        Write-Host '  The initialization marker may be stale. Review the MongoDB logs/credentials and retry; database data was not removed.' -ForegroundColor Yellow
        exit 1
    }
} else {
    Write-Host 'MongoDB skipped' -ForegroundColor Yellow
}

# Start Redis
if (-not $SkipRedis -and (Test-Path -LiteralPath $redisExe)) {
    if (-not (Check-Port -Port $redisPort -ServiceName 'Redis')) {
        Write-Host "ERROR: Cannot start Redis - port $redisPort is not available" -ForegroundColor Red
        exit 1
    }

    Ensure-Dir $redisData
    Ensure-Dir (Join-Path $root 'runtime')
    $redisConf = Join-Path $root 'runtime\redis.conf'
    $redisDataUnix = $redisData -replace '\\', '/'
    $conf = @(
        'bind 127.0.0.1',
        "port $redisPort",
        "dir $redisDataUnix",
        'requirepass tradingagents123',
        'appendonly yes',
        'save 900 1',
        'save 300 10',
        'save 60 10000'
    )
    $utf8NoBom = New-Object System.Text.UTF8Encoding $false
    [System.IO.File]::WriteAllText($redisConf, ($conf -join "`n"), $utf8NoBom)

    $redisConfRelative = 'runtime\redis.conf'
    $redisProc = Start-Proc -FilePath $redisExe -Arguments "`"$redisConfRelative`"" `
        -Name 'Redis' -WaitSeconds 5 -WorkingDirectory $root
    if (-not $redisProc) {
        Write-Host 'ERROR: Redis failed to start' -ForegroundColor Red
        exit 1
    }
} else {
    Write-Host 'Redis skipped or binary not found' -ForegroundColor Yellow
}

Write-Host 'Services startup completed.' -ForegroundColor Green
if (-not $SkipMongoDB) {
    Write-Host "MongoDB is available at: ${mongoProbeHost}:$mongoPort"
}
if (-not $SkipRedis -and (Test-Path -LiteralPath $redisExe)) {
    Write-Host "Redis should be available at: 127.0.0.1:$redisPort"
}
