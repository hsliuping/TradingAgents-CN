# TradingAgents-CN Portable - Start All Services
# This script starts MongoDB, Redis, Backend, and Nginx

[CmdletBinding()]
param(
    [switch]$ForceImport  # Force import configuration even if already imported
)

$ErrorActionPreference = "Stop"

# Support both the package-root copies and the canonical source-tree layout.
$root = $PSScriptRoot
$parent = Split-Path -Parent $PSScriptRoot
if ((Split-Path -Leaf $PSScriptRoot) -eq 'installer' -and
    (Split-Path -Leaf $parent) -eq 'scripts') {
    $root = Split-Path -Parent $parent
}

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

function Sync-MongoUriEndpoints {
    param(
        [string]$File,
        [string]$HostName,
        [int]$PortNumber
    )

    if (-not (Test-Path -LiteralPath $File -PathType Leaf)) { return }

    $content = Get-Content -LiteralPath $File -Raw -Encoding UTF8
    $formattedHost = $HostName
    if ($formattedHost -match ':' -and -not ($formattedHost.StartsWith('['))) {
        $formattedHost = "[$formattedHost]"
    }

    # Replace only the local MongoDB endpoint. Credentials, database names,
    # and query parameters in every supported URI alias remain unchanged.
    $uriPattern = '(?m)^((?:MONGODB_CONNECTION_STRING|MONGODB_URL|MONGO_URI|MONGODB_URI)=mongodb://)([^@\r\n/?]+@)?(\[[^\]]+\]|[^:/\r\n/?]+)(?::\d+)?'
    $replacement = '$1$2' + $formattedHost + ':' + $PortNumber
    $updated = [regex]::Replace($content, $uriPattern, $replacement)
    if ($updated -ne $content) {
        $utf8NoBom = New-Object System.Text.UTF8Encoding $false
        [System.IO.File]::WriteAllText($File, $updated, $utf8NoBom)
    }
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

$envMap = Load-Env (Join-Path $root '.env')
$backendPort = if ($envMap.ContainsKey('PORT')) { [int]$envMap['PORT'] } else { 8000 }
$nginxPort = if ($envMap.ContainsKey('NGINX_PORT')) { [int]$envMap['NGINX_PORT'] } else { 80 }
$mongoPort = if ($envMap.ContainsKey('MONGODB_PORT')) { [int]$envMap['MONGODB_PORT'] } else { 27017 }
$mongoHost = if ($envMap.ContainsKey('MONGODB_HOST') -and -not [string]::IsNullOrWhiteSpace($envMap['MONGODB_HOST'])) { [string]$envMap['MONGODB_HOST'] } else { 'localhost' }
$redisPort = if ($envMap.ContainsKey('REDIS_PORT')) { [int]$envMap['REDIS_PORT'] } else { 6379 }
$mongoProbeHost = $mongoHost
if ([string]::IsNullOrWhiteSpace($mongoProbeHost) -or
    $mongoProbeHost -eq '0.0.0.0' -or $mongoProbeHost -eq '::' -or $mongoProbeHost -eq '*') {
    $mongoProbeHost = '127.0.0.1'
}

Sync-MongoUriEndpoints -File (Join-Path $root '.env') -HostName $mongoHost -PortNumber $mongoPort

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "TradingAgents-CN Portable - Start All" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# ============================================================================
# Step 0: Update pyvenv.cfg with correct absolute path
# ============================================================================

$pyvenvCfg = Join-Path $root "venv\pyvenv.cfg"
if (Test-Path $pyvenvCfg) {
    # Always update to use absolute path to vendors\python
    $vendorsPythonPath = Join-Path $root "vendors\python"
    $content = Get-Content $pyvenvCfg -Raw
    $newContent = $content -replace 'home\s*=\s*.*', "home = $vendorsPythonPath"
    Set-Content -Path $pyvenvCfg -Value $newContent -Encoding UTF8 -NoNewline
}

# Step 1: Start MongoDB and Redis
Write-Host "[1/4] Starting MongoDB and Redis..." -ForegroundColor Yellow
$servicesScript = Join-Path $PSScriptRoot "start_services_clean.ps1"
if (-not (Test-Path -LiteralPath $servicesScript)) {
    $servicesScript = Join-Path $root "start_services_clean.ps1"
}
if (Test-Path $servicesScript) {
    & powershell -ExecutionPolicy Bypass -File $servicesScript
    $servicesExitCode = $LASTEXITCODE
    if ($servicesExitCode -ne 0) {
        Write-Host "ERROR: Failed to start services" -ForegroundColor Red
        exit $servicesExitCode
    }
} else {
    Write-Host "ERROR: Services script not found: $servicesScript" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "[2/4] Waiting for services to be ready..." -ForegroundColor Yellow
if (-not (Wait-ForTcpPort -HostName $mongoProbeHost -Port $mongoPort -TimeoutSeconds 60)) {
    Write-Host "ERROR: MongoDB is not reachable at ${mongoProbeHost}:$mongoPort" -ForegroundColor Red
    Write-Host "Check the MongoDB startup logs before retrying." -ForegroundColor Yellow
    exit 1
}
Write-Host "  MongoDB is reachable at ${mongoProbeHost}:$mongoPort" -ForegroundColor Green

# Step 2: Import configuration and create user (first time only)
$importMarkerFile = Join-Path $root 'runtime\.config_imported'
$needsImport = (-not (Test-Path $importMarkerFile)) -or $ForceImport

if ($needsImport) {
    Write-Host ""
    if ($ForceImport) {
        Write-Host "[2.5/4] Force importing configuration and creating default user..." -ForegroundColor Yellow
    } else {
        Write-Host "[2.5/4] First time setup: Importing configuration and creating default user..." -ForegroundColor Yellow
    }

    $pythonExe = Join-Path $root 'venv\Scripts\python.exe'
    if (-not (Test-Path -LiteralPath $pythonExe)) {
        $pythonExe = Join-Path $root 'vendors\python\python.exe'
    }
    if (-not (Test-Path $pythonExe)) {
        Write-Host "  ERROR: Python not found at: $pythonExe" -ForegroundColor Red
        Write-Host "  Configuration import cannot continue." -ForegroundColor Red
        exit 1
    } else {
        # Test Python first
        Write-Host "  Testing Python: $pythonExe" -ForegroundColor Gray
        try {
            $pythonTest = & $pythonExe --version 2>&1
            $pythonTestExitCode = $LASTEXITCODE
            if ($pythonTestExitCode -ne 0) {
                throw "Python exited with code $pythonTestExitCode"
            }
            Write-Host "  Python version: $pythonTest" -ForegroundColor Gray
        } catch {
            Write-Host "  ERROR: Python failed to run: $_" -ForegroundColor Red
            Write-Host "  Exception details: $($_.Exception.Message)" -ForegroundColor Red
            exit 1
        }

        $importScript = Join-Path $root 'scripts\import_config_and_create_user.py'
        $installDir = Join-Path $root 'install'
        $configCandidates = @()
        if (Test-Path -LiteralPath $installDir) {
            $configCandidates = @(Get-ChildItem -LiteralPath $installDir -Filter 'database_export_config_*.json' -File | Sort-Object Name -Descending)
            if ($configCandidates.Count -eq 0) {
                $configCandidates = @(Get-ChildItem -LiteralPath $installDir -Filter 'database_export_config.json' -File)
            }
        }
        $configFile = if ($configCandidates.Count -gt 0) { $configCandidates[0].FullName } else { $null }

        if ((Test-Path -LiteralPath $importScript) -and $configFile -and (Test-Path -LiteralPath $configFile)) {
            try {
                Write-Host "  Running import script..." -ForegroundColor Gray
                Write-Host "  Command: $pythonExe $importScript $configFile --host --mongodb-host $mongoHost --mongodb-port $mongoPort" -ForegroundColor Gray

                # Set console output encoding to UTF-8 to handle Chinese characters
                $originalOutputEncoding = [Console]::OutputEncoding
                [Console]::OutputEncoding = [System.Text.Encoding]::UTF8

                # Set environment variable for Python to use UTF-8
                $env:PYTHONIOENCODING = "utf-8"

                # Capture output for debugging
                try {
                    $importOutput = & $pythonExe $importScript $configFile --host --mongodb-host $mongoHost --mongodb-port $mongoPort 2>&1
                    $importExitCode = $LASTEXITCODE
                } finally {
                    [Console]::OutputEncoding = $originalOutputEncoding
                }

                # Print all output
                if ($importOutput) {
                    Write-Host "  Output:" -ForegroundColor Gray
                    $importOutput | ForEach-Object { Write-Host "    $_" -ForegroundColor Gray }
                }

                # Check if import was successful
                if ($importExitCode -eq 0) {
                    Write-Host "  Configuration imported successfully" -ForegroundColor Green

                    # Create marker file to indicate import is done
                    $runtimeDir = Join-Path $root 'runtime'
                    if (-not (Test-Path $runtimeDir)) {
                        New-Item -ItemType Directory -Path $runtimeDir -Force | Out-Null
                    }
                    Set-Content -LiteralPath $importMarkerFile -Value (Get-Date).ToString('o') -Encoding ASCII -ErrorAction Stop
                    Write-Host "  Import marker created: $importMarkerFile" -ForegroundColor Gray
                } else {
                    Write-Host "  ERROR: Import script failed with exit code $importExitCode" -ForegroundColor Red
                    exit 1
                }
            } catch {
                Write-Host "  ERROR: Failed to import configuration: $_" -ForegroundColor Red
                Write-Host "  Exception details: $($_.Exception.Message)" -ForegroundColor Red
                Write-Host "  Import marker was not created." -ForegroundColor Yellow
                exit 1
            }
        } else {
            if (-not (Test-Path $importScript)) {
                Write-Host "  WARNING: Import script not found: $importScript" -ForegroundColor Yellow
            }
            if (-not $configFile -or -not (Test-Path -LiteralPath $configFile)) {
                Write-Host "  WARNING: Config file not found under: $installDir" -ForegroundColor Yellow
            }
            Write-Host "  Configuration import cannot continue." -ForegroundColor Red
            exit 1
        }
    }
} else {
    Write-Host ""
    Write-Host "[2.5/4] Configuration already imported, skipping..." -ForegroundColor Gray
    Write-Host "  (Use -ForceImport parameter to force re-import)" -ForegroundColor Gray
}

# Step 3: Start Backend
Write-Host "" 
Write-Host "[3/4] Starting Backend..." -ForegroundColor Yellow

Write-Host "  Checking port $backendPort..." -ForegroundColor Gray
$portInUse = Get-NetTCPConnection -LocalPort $backendPort -State Listen -ErrorAction SilentlyContinue
if ($portInUse) {
    Write-Host "  WARNING: Port $backendPort is already in use!" -ForegroundColor Yellow
    foreach ($conn in $portInUse) {
        $process = Get-Process -Id $conn.OwningProcess -ErrorAction SilentlyContinue
        if ($process) {
            Write-Host "    Process: $($process.ProcessName) (PID: $($process.Id))" -ForegroundColor Gray
            Write-Host "    Path: $($process.Path)" -ForegroundColor Gray

            # Check if it's a Python process (likely our backend)
            if ($process.ProcessName -eq "python" -or $process.ProcessName -eq "pythonw") {
                Write-Host "  Stopping existing backend process (PID: $($process.Id))..." -ForegroundColor Yellow
                try {
                    Stop-Process -Id $process.Id -Force -ErrorAction Stop
                    Start-Sleep -Seconds 2
                    Write-Host "  Existing backend process stopped" -ForegroundColor Green
                } catch {
                    Write-Host "  ERROR: Failed to stop process: $_" -ForegroundColor Red
                    Write-Host "  Please manually stop the process and try again" -ForegroundColor Yellow
                    exit 1
                }
            } else {
                Write-Host "  ERROR: Port $backendPort is occupied by another application" -ForegroundColor Red
                Write-Host "  Please stop the process manually and try again" -ForegroundColor Yellow
                exit 1
            }
        }
    }
}

$pythonExe = Join-Path $root 'venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $pythonExe)) {
    $pythonExe = Join-Path $root 'vendors\python\python.exe'
}
if (-not (Test-Path -LiteralPath $pythonExe)) {
    Write-Host "  ERROR: Python not found at: $pythonExe" -ForegroundColor Red
    exit 1
}

# Test Python first
Write-Host "  Testing Python..." -ForegroundColor Gray
try {
    $pythonTest = & $pythonExe --version 2>&1
    $pythonTestExitCode = $LASTEXITCODE
    if ($pythonTestExitCode -ne 0) {
        throw "Python exited with code $pythonTestExitCode"
    }
    Write-Host "  Python version: $pythonTest" -ForegroundColor Gray
} catch {
    Write-Host "  ERROR: Python failed to run: $_" -ForegroundColor Red
    exit 1
}

# Create logs directory if it doesn't exist
$logsDir = Join-Path $root 'logs'
if (-not (Test-Path $logsDir)) {
    New-Item -ItemType Directory -Path $logsDir -Force | Out-Null
}

# Start backend with output redirection to log files
$backendLog = Join-Path $logsDir 'backend_startup.log'
$backendErrorLog = Join-Path $logsDir 'backend_error.log'
Write-Host "  Starting backend (logs: backend_startup.log, backend_error.log)..." -ForegroundColor Gray

# Try to start backend and capture any immediate errors
try {
    # Set UTF-8 encoding environment variables for Python
    $env:PYTHONIOENCODING = "utf-8"
    $env:PYTHONUTF8 = "1"

    # Use app\__main__.py directly instead of -m app to avoid module path issues
    $appMain = Join-Path $root 'app\__main__.py'

    # Create a process start info with UTF-8 environment
    $psi = New-Object System.Diagnostics.ProcessStartInfo
    $psi.FileName = $pythonExe
    $psi.Arguments = "`"$appMain`""
    $psi.WorkingDirectory = $root
    $psi.WindowStyle = [System.Diagnostics.ProcessWindowStyle]::Hidden
    $psi.UseShellExecute = $false
    $psi.RedirectStandardOutput = $true
    $psi.RedirectStandardError = $true
    $psi.StandardOutputEncoding = [System.Text.Encoding]::UTF8
    $psi.StandardErrorEncoding = [System.Text.Encoding]::UTF8

    # Set environment variables for the process
    $psi.EnvironmentVariables["PYTHONIOENCODING"] = "utf-8"
    $psi.EnvironmentVariables["PYTHONUTF8"] = "1"

    # Start the process
    $backendProcess = [System.Diagnostics.Process]::Start($psi)

    # Create log file streams with UTF-8 encoding
    $outStream = [System.IO.StreamWriter]::new($backendLog, $false, [System.Text.Encoding]::UTF8)
    $errStream = [System.IO.StreamWriter]::new($backendErrorLog, $false, [System.Text.Encoding]::UTF8)

    # Start async reading
    $backendProcess.OutputDataReceived.Add({
        param($sender, $e)
        if ($null -ne $e.Data) {
            $outStream.WriteLine($e.Data)
            $outStream.Flush()
        }
    })
    $backendProcess.ErrorDataReceived.Add({
        param($sender, $e)
        if ($null -ne $e.Data) {
            $errStream.WriteLine($e.Data)
            $errStream.Flush()
        }
    })

    $backendProcess.BeginOutputReadLine()
    $backendProcess.BeginErrorReadLine()

    if ($backendProcess) {
        Write-Host "  Backend started with PID: $($backendProcess.Id)" -ForegroundColor Green

        # Wait a moment to see if it crashes immediately
        Start-Sleep -Seconds 2

        # Check if process is still running
        $stillRunning = Get-Process -Id $backendProcess.Id -ErrorAction SilentlyContinue
        if (-not $stillRunning) {
            Write-Host "  ERROR: Backend process crashed immediately!" -ForegroundColor Red
            Write-Host "  Standard output:" -ForegroundColor Yellow
            if (Test-Path $backendLog) {
                Get-Content $backendLog | ForEach-Object { Write-Host "    $_" -ForegroundColor Gray }
            }
            Write-Host "  Error output:" -ForegroundColor Yellow
            if (Test-Path $backendErrorLog) {
                Get-Content $backendErrorLog | ForEach-Object { Write-Host "    $_" -ForegroundColor Red }
            }
            exit 1
        }
    } else {
        Write-Host "  ERROR: Failed to start backend" -ForegroundColor Red
        exit 1
    }
} catch {
    Write-Host "  ERROR: Failed to start backend: $_" -ForegroundColor Red
    Write-Host "  Exception details: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}

# Wait for backend to be ready
Write-Host "  Waiting for backend to be ready..."
$maxRetries = 30
$retryCount = 0
$backendReady = $false

while ($retryCount -lt $maxRetries) {
    # Check if process is still running
    $stillRunning = Get-Process -Id $backendProcess.Id -ErrorAction SilentlyContinue
    if (-not $stillRunning) {
        Write-Host ""
        Write-Host "  ERROR: Backend process crashed!" -ForegroundColor Red
        Write-Host "  Standard output:" -ForegroundColor Yellow
        if (Test-Path $backendLog) {
            Get-Content $backendLog | ForEach-Object { Write-Host "    $_" -ForegroundColor Gray }
        }
        Write-Host "  Error output:" -ForegroundColor Yellow
        if (Test-Path $backendErrorLog) {
            Get-Content $backendErrorLog | ForEach-Object { Write-Host "    $_" -ForegroundColor Red }
        }
        exit 1
    }

    try {
        $response = Invoke-WebRequest -Uri "http://127.0.0.1:$backendPort/api/health" -TimeoutSec 2 -UseBasicParsing -ErrorAction SilentlyContinue
        if ($response.StatusCode -eq 200) {
            $backendReady = $true
            break
        }
    } catch {
        # Backend not ready yet
    }
    Start-Sleep -Seconds 1
    $retryCount++
    Write-Host "." -NoNewline
}

Write-Host ""
if ($backendReady) {
    Write-Host "  Backend is ready!" -ForegroundColor Green
} else {
    Write-Host "  WARNING: Backend may not be fully ready yet" -ForegroundColor Yellow
    Write-Host "  Check log files for details" -ForegroundColor Gray

    # Show last 20 lines of standard output
    if (Test-Path $backendLog) {
        Write-Host "  Last 20 lines of standard output:" -ForegroundColor Yellow
        Get-Content $backendLog -Tail 20 | ForEach-Object { Write-Host "    $_" -ForegroundColor Gray }
    }

    # Show last 20 lines of error output
    if (Test-Path $backendErrorLog) {
        Write-Host "  Last 20 lines of error output:" -ForegroundColor Yellow
        Get-Content $backendErrorLog -Tail 20 | ForEach-Object { Write-Host "    $_" -ForegroundColor Red }
    }
}

# Step 3: Start Nginx
Write-Host ""
Write-Host "[4/4] Starting Nginx..." -ForegroundColor Yellow

$nginxExe = Join-Path $root 'vendors\nginx\nginx-1.29.3\nginx.exe'
$nginxConf = Join-Path $root 'runtime\nginx.conf'
$nginxWorkDir = Join-Path $root 'vendors\nginx\nginx-1.29.3'
$nginxErrorLog = Join-Path $root 'logs\nginx_error.log'

if (-not (Test-Path $nginxExe)) {
    Write-Host "ERROR: Nginx executable not found: $nginxExe" -ForegroundColor Red
    exit 1
}

if (-not (Test-Path $nginxConf)) {
    Write-Host "ERROR: Nginx config not found: $nginxConf" -ForegroundColor Red
    exit 1
}

# Check if nginx port is already in use
$port80InUse = Get-NetTCPConnection -LocalPort $nginxPort -ErrorAction SilentlyContinue
if ($port80InUse) {
    Write-Host "  WARNING: Port $nginxPort is already in use!" -ForegroundColor Yellow
    foreach ($conn in $port80InUse) {
        $process = Get-Process -Id $conn.OwningProcess -ErrorAction SilentlyContinue
        if ($process) {
            Write-Host "    Process: $($process.ProcessName) (PID: $($process.Id))" -ForegroundColor Gray
        }
    }
    Write-Host "  Attempting to stop conflicting processes..." -ForegroundColor Yellow
}

# Check if Nginx is already running
$existingNginx = Get-Process -Name "nginx" -ErrorAction SilentlyContinue
if ($existingNginx) {
    Write-Host "  Stopping existing Nginx processes..." -ForegroundColor Yellow
    Stop-Process -Name "nginx" -Force -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 2
}

# Clean up old PID file if exists
$nginxPidFile = Join-Path $root 'logs\nginx.pid'
if (Test-Path $nginxPidFile) {
    Remove-Item $nginxPidFile -Force -ErrorAction SilentlyContinue
}

# Create temp directories for Nginx
$tempDirs = @("temp\client_body_temp", "temp\proxy_temp", "temp\fastcgi_temp", "temp\uwsgi_temp", "temp\scgi_temp")
foreach ($dir in $tempDirs) {
    $fullPath = Join-Path $root $dir
    if (-not (Test-Path $fullPath)) {
        New-Item -ItemType Directory -Path $fullPath -Force | Out-Null
    }
}

# Create logs directory if not exists
$logsDir = Join-Path $root 'logs'
if (-not (Test-Path $logsDir)) {
    New-Item -ItemType Directory -Path $logsDir -Force | Out-Null
}

try {
    Write-Host "  Updating Nginx configuration..." -ForegroundColor Gray
    Write-Host "    Backend port: $backendPort, Nginx port: $nginxPort" -ForegroundColor Gray

    $confText = Get-Content -LiteralPath $nginxConf -Raw -ErrorAction Stop
    $newText = $confText

    # Update listen port
    $listenBefore = if ($confText -match 'listen\s+(\d+);') { $matches[1] } else { "not found" }
    $newText = [regex]::Replace($newText, 'listen\s+\d+;', "listen $nginxPort;")

    # Update upstream backend server port
    $upstreamBefore = if ($confText -match 'upstream\s+backend\s*\{[^}]*server\s+127\.0\.0\.1:(\d+)') { $matches[1] } else { "not found" }
    $newText = [regex]::Replace($newText, '(upstream\s+backend\s*\{[^}]*server\s+127\.0\.0\.1:)\d+', "`${1}$backendPort")

    # Update proxy_pass port (if any direct proxy_pass with port)
    $newText = [regex]::Replace($newText, 'proxy_pass\s+http://127\.0\.0\.1:\d+', "proxy_pass http://127.0.0.1:$backendPort")

    if ($newText -ne $confText) {
        Write-Host "    Updating: listen $listenBefore -> $nginxPort, upstream $upstreamBefore -> $backendPort" -ForegroundColor Gray
        # Write without BOM to avoid Nginx parsing errors
        $utf8NoBom = New-Object System.Text.UTF8Encoding $false
        [System.IO.File]::WriteAllText($nginxConf, $newText, $utf8NoBom)
        Write-Host "    Nginx configuration updated successfully" -ForegroundColor Green
    } else {
        Write-Host "    Nginx configuration already up to date" -ForegroundColor Gray
    }
} catch {
    Write-Host "    WARNING: Failed to update Nginx configuration: $_" -ForegroundColor Yellow
}

# Start Nginx with absolute paths
try {
    $nginxConfAbs = (Resolve-Path $nginxConf).Path
    $rootAbs = (Resolve-Path $root).Path

    $nginxArgs = @("-c", "`"$nginxConfAbs`"", "-p", "`"$rootAbs`"")
    $nginxProcess = Start-Process -FilePath $nginxExe -ArgumentList $nginxArgs -WorkingDirectory $root -WindowStyle Hidden -PassThru

    Start-Sleep -Seconds 3

    # Check if Nginx is running
    $nginxRunning = Get-Process -Name "nginx" -ErrorAction SilentlyContinue
    if ($nginxRunning) {
        Write-Host "  Nginx started successfully" -ForegroundColor Green
    } else {
        Write-Host "WARNING: Nginx process may have exited" -ForegroundColor Yellow

        # Try to read error log
        if (Test-Path $nginxErrorLog) {
            Write-Host "  Last error from nginx_error.log:" -ForegroundColor Yellow
            $lastErrors = Get-Content $nginxErrorLog -Tail 5 -ErrorAction SilentlyContinue
            if ($lastErrors) {
                foreach ($line in $lastErrors) {
                    Write-Host "    $line" -ForegroundColor Gray
                }
            }
        }

        Write-Host "  💡 Tip: Run 'powershell -ExecutionPolicy Bypass -File scripts\diagnose_nginx.ps1' for detailed diagnosis" -ForegroundColor Cyan
    }
} catch {
    Write-Host "ERROR: Failed to start Nginx: $_" -ForegroundColor Red
    Write-Host "Check logs/nginx_error.log for details" -ForegroundColor Yellow
    exit 1
}

# Summary
Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "All Services Started Successfully!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Service Status:" -ForegroundColor White
Write-Host "  MongoDB:  ${mongoProbeHost}:$mongoPort" -ForegroundColor Green
Write-Host "  Redis:    127.0.0.1:$redisPort" -ForegroundColor Green
Write-Host "  Backend:  http://127.0.0.1:$backendPort" -ForegroundColor Green
Write-Host "  Frontend: http://127.0.0.1:$nginxPort" -ForegroundColor Green
Write-Host ""
Write-Host "Access the application:" -ForegroundColor White
$webUrl = if ($nginxPort -eq 80) { "http://localhost" } else { "http://localhost:$nginxPort" }
Write-Host "  Web UI:   $webUrl" -ForegroundColor Cyan
$apiDocsUrl = if ($nginxPort -eq 80) { "http://localhost/docs" } else { "http://localhost:$nginxPort/docs" }
Write-Host "  API Docs: $apiDocsUrl" -ForegroundColor Cyan
Write-Host ""
Write-Host "Default Login:" -ForegroundColor White
Write-Host "  Username: admin" -ForegroundColor Cyan
Write-Host "  Password: admin123" -ForegroundColor Cyan
Write-Host ""
Write-Host "Press Ctrl+C to stop all services" -ForegroundColor Yellow
Write-Host ""

# Keep script running
try {
    while ($true) {
        Start-Sleep -Seconds 10
        
        # Check if processes are still running
        $mongoRunning = Get-Process -Name "mongod" -ErrorAction SilentlyContinue
        $redisRunning = Get-Process -Name "redis-server" -ErrorAction SilentlyContinue
        $backendRunning = Get-Process -Id $backendProcess.Id -ErrorAction SilentlyContinue
        $nginxRunning = Get-Process -Name "nginx" -ErrorAction SilentlyContinue
        
        if (-not $mongoRunning) {
            Write-Host "WARNING: MongoDB process stopped" -ForegroundColor Red
        }
        if (-not $redisRunning) {
            Write-Host "WARNING: Redis process stopped" -ForegroundColor Red
        }
        if (-not $backendRunning) {
            Write-Host "WARNING: Backend process stopped" -ForegroundColor Red
        }
        if (-not $nginxRunning) {
            Write-Host "WARNING: Nginx process stopped" -ForegroundColor Red
        }
    }
} finally {
    Write-Host ""
    Write-Host "Stopping all services..." -ForegroundColor Yellow
    
    # Stop Nginx
    Stop-Process -Name "nginx" -Force -ErrorAction SilentlyContinue
    
    # Stop Backend
    if ($backendProcess) {
        Stop-Process -Id $backendProcess.Id -Force -ErrorAction SilentlyContinue
    }
    
    # Stop MongoDB and Redis
    Stop-Process -Name "mongod" -Force -ErrorAction SilentlyContinue
    Stop-Process -Name "redis-server" -Force -ErrorAction SilentlyContinue
    
    Write-Host "All services stopped" -ForegroundColor Green
}

