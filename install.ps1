<#
.SYNOPSIS
    TradingAgents-CN 社区版一键安装脚本（Windows）

.DESCRIPTION
    自动完成：Python 环境准备 → 获取代码 → 下载 MongoDB/Redis 运行时 →
    构建/下载前端 → 创建虚拟环境并安装依赖 → 生成 .env → 启动服务。

.PARAMETER InstallDir
    安装目录（默认 $HOME\TradingAgentsCN）

.PARAMETER SourcePath
    本地源码模式：直接使用指定目录作为项目根（跳过代码下载），CI 验证用

.PARAMETER Port
    Web 服务端口（默认 8000）

.PARAMETER MongoPort
    MongoDB 端口（默认 27017）

.PARAMETER RedisPort
    Redis 端口（默认 6379）

.PARAMETER AdminPassword
    管理员初始密码（默认随机生成并打印）

.PARAMETER SkipFrontendBuild
    跳过前端构建（要求 frontend\dist 已存在）

.PARAMETER NoStart
    只安装不启动

.PARAMETER Mirror
    下载镜像前缀（可选），用于 MongoDB/Redis 下载加速

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File .\install.ps1
    powershell -ExecutionPolicy Bypass -File .\install.ps1 -Port 8080 -AdminPassword "MyPass123!"
    powershell -ExecutionPolicy Bypass -File .\install.ps1 -SourcePath .
#>

[CmdletBinding()]
param(
    [string]$InstallDir = (Join-Path $HOME "TradingAgentsCN"),
    [string]$SourcePath = "",
    [int]$Port = 8000,
    [int]$MongoPort = 27017,
    [int]$RedisPort = 6379,
    [string]$AdminPassword = "",
    [switch]$SkipFrontendBuild,
    [switch]$NoStart,
    [string]$Mirror = "",
    [string]$MongoVersion = "7.0.14",
    [string]$RedisVersion = "5.0.14.1",
    [string]$RepoUrl = "https://github.com/hsliuping/TradingAgents-CN",
    [string]$Ref = "community"
)

$ErrorActionPreference = "Stop"
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

function Write-Step($msg) { Write-Host "`n==> $msg" -ForegroundColor Cyan }
function Write-Ok($msg)   { Write-Host "  [OK] $msg" -ForegroundColor Green }
function Write-Warn2($msg){ Write-Host "  [警告] $msg" -ForegroundColor Yellow }
function Fail($msg)       { Write-Host "  [失败] $msg" -ForegroundColor Red; exit 1 }

function Resolve-Url($url) {
    if ($Mirror) { return ($Mirror.TrimEnd('/') + '/' + ($url -split '/')[-1]) }
    return $url
}

function Download-File($url, $dest) {
    $url = Resolve-Url $url
    Write-Host "  下载: $url"
    $dir = Split-Path $dest -Parent
    if ($dir -and -not (Test-Path $dir)) { New-Item -ItemType Directory -Path $dir -Force | Out-Null }
    try {
        Invoke-WebRequest -Uri $url -OutFile $dest -UseBasicParsing
    } catch {
        Write-Warn2 "Invoke-WebRequest 失败，尝试 curl.exe"
        & curl.exe -L --fail -o $dest $url
        if ($LASTEXITCODE -ne 0 -or -not (Test-Path $dest)) { Fail "下载失败: $url" }
    }
    Write-Ok "已下载: $(Split-Path $dest -Leaf)"
}

function Test-PortOpen([int]$p) {
    $client = New-Object Net.Sockets.TcpClient
    try {
        $iar = $client.BeginConnect("127.0.0.1", $p, $null, $null)
        if ($iar.AsyncWaitHandle.WaitOne(1000)) { $client.EndConnect($iar); return $true }
        return $false
    } catch { return $false } finally { $client.Close() }
}

function Get-PythonInfo {
    $candidates = @(
        @{ Cmd = "py";     Pre = @("-3.11") },
        @{ Cmd = "py";     Pre = @("-3.12") },
        @{ Cmd = "python"; Pre = @() },
        @{ Cmd = "python3";Pre = @() }
    )
    foreach ($c in $candidates) {
        if (-not (Get-Command $c.Cmd -ErrorAction SilentlyContinue)) { continue }
        $a = $c.Pre + @("-c", "import sys;print('%d.%d' % sys.version_info[:2])")
        try {
            $out = (& $c.Cmd @a 2>$null | Out-String).Trim()
            if ($out -match '^3\.(\d+)$' -and [int]$Matches[1] -ge 11) { return $c }
        } catch { }
    }
    return $null
}

function Ensure-Python {
    $info = Get-PythonInfo
    if ($info) { Write-Ok "Python 已就绪: $($info.Cmd) $($info.Pre -join ' ')"; return $info }

    Write-Warn2 "未检测到 Python 3.11+，尝试用 winget 自动安装"
    if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
        Fail "未找到 winget。请手动安装 Python 3.11+：https://www.python.org/downloads/"
    }
    & winget install --id Python.Python.3.11 -e --silent --accept-package-agreements --accept-source-agreements | Out-Host
    $info = Get-PythonInfo
    if (-not $info) {
        Fail "Python 自动安装后仍未检测到 3.11+。请重新打开终端后重试，或手动安装：https://www.python.org/downloads/"
    }
    Write-Ok "Python 自动安装完成"
    return $info
}

function Start-Bg($exe, [string[]]$argList, $workDir, $outLog, $errLog) {
    $p = Start-Process -FilePath $exe -ArgumentList $argList -WorkingDirectory $workDir `
        -RedirectStandardOutput $outLog -RedirectStandardError $errLog `
        -WindowStyle Hidden -PassThru
    return $p
}

function Wait-Port([int]$p, [int]$timeoutSec, $name) {
    $deadline = (Get-Date).AddSeconds($timeoutSec)
    while ((Get-Date) -lt $deadline) {
        if (Test-PortOpen $p) { Write-Ok "$name 已就绪（端口 $p）"; return $true }
        Start-Sleep -Seconds 2
    }
    return $false
}

function Wait-Health([int]$p, [int]$timeoutSec) {
    $deadline = (Get-Date).AddSeconds($timeoutSec)
    $url = "http://127.0.0.1:$p/api/health"
    while ((Get-Date) -lt $deadline) {
        try {
            $resp = Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 5
            if ($resp.StatusCode -eq 200) {
                $json = $resp.Content | ConvertFrom-Json
                if ($json.success -eq $true -and $json.data.status -eq "ok") { return $true }
            }
        } catch { }
        Start-Sleep -Seconds 3
    }
    return $false
}

function New-RandomHex([int]$bytes) {
    $buf = New-Object byte[] $bytes
    $rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    $rng.GetBytes($buf)
    $rng.Dispose()
    return (($buf | ForEach-Object { $_.ToString("x2") }) -join "")
}

function Set-EnvFile($envPath, $examplePath, [hashtable]$overrides) {
    if (-not (Test-Path $examplePath)) { Fail "未找到 .env.example：$examplePath" }
    $lines = Get-Content $examplePath -Encoding UTF8
    $seen = @{}
    $out = New-Object System.Collections.Generic.List[string]
    foreach ($line in $lines) {
        if ($line -match '^([A-Za-z_][A-Za-z0-9_]*)=') {
            $key = $Matches[1]
            if ($overrides.ContainsKey($key)) {
                $out.Add("$key=$($overrides[$key])")
                $seen[$key] = $true
                continue
            }
        }
        $out.Add($line)
    }
    foreach ($k in $overrides.Keys) {
        if (-not $seen.ContainsKey($k)) { $out.Add("$k=$($overrides[$k])") }
    }
    # 写 UTF-8 无 BOM（PS 5.1 的 Set-Content -Encoding UTF8 会带 BOM，可能导致 .env 首行键名解析异常）
    [System.IO.File]::WriteAllLines($envPath, $out, (New-Object System.Text.UTF8Encoding($false)))
}

# ============================== 主流程 ==============================

$localMode = [bool]$SourcePath
if ($localMode) {
    $root = (Resolve-Path $SourcePath).Path
    Write-Step "本地源码模式：$root"
} else {
    $root = $InstallDir
    Write-Step "安装目录：$root"
}

$runtimeDir = Join-Path $root "runtime"
$dataDir    = Join-Path $root "data"
$logsDir    = Join-Path $root "logs"
foreach ($d in @($runtimeDir, $dataDir, $logsDir, (Join-Path $dataDir "mongodb"), (Join-Path $dataDir "redis"))) {
    if (-not (Test-Path $d)) { New-Item -ItemType Directory -Path $d -Force | Out-Null }
}

# ---- 1. Python ----
Write-Step "[1/8] 检查 Python 环境"
$py = Ensure-Python

# ---- 2. 获取代码 ----
Write-Step "[2/8] 获取代码"
if (-not $localMode) {
    $zip = Join-Path $env:TEMP "tradingagents-community-$Ref.zip"
    $srcUrl = "$RepoUrl/archive/refs/heads/$Ref.zip"
    Download-File $srcUrl $zip
    if (Test-Path $root) { Get-ChildItem $root -Force | Where-Object { $_.Name -ne 'runtime' -and $_.Name -ne 'data' -and $_.Name -ne 'logs' } | Remove-Item -Recurse -Force }
    $tmpExtract = Join-Path $env:TEMP "tradingagents-extract"
    if (Test-Path $tmpExtract) { Remove-Item $tmpExtract -Recurse -Force }
    Expand-Archive -Path $zip -DestinationPath $tmpExtract -Force
    $inner = Get-ChildItem $tmpExtract -Directory | Select-Object -First 1
    New-Item -ItemType Directory -Path $root -Force | Out-Null
    Get-ChildItem $inner.FullName -Force | Copy-Item -Destination $root -Recurse -Force
    Remove-Item $tmpExtract -Recurse -Force
    Remove-Item $zip -Force
    Write-Ok "代码已就绪"
} else {
    Write-Ok "使用本地源码：$root"
}
if (-not (Test-Path (Join-Path $root "app\main.py"))) { Fail "代码不完整（缺少 app\main.py）：$root" }

# ---- 3. MongoDB ----
Write-Step "[3/8] 准备 MongoDB $MongoVersion"
$mongodExe = Join-Path $runtimeDir "mongodb\bin\mongod.exe"
if (-not (Test-Path $mongodExe)) {
    $zip = Join-Path $env:TEMP "mongodb-win64-$MongoVersion.zip"
    Download-File "https://fastdl.mongodb.org/windows/mongodb-windows-x86_64-$MongoVersion.zip" $zip
    Expand-Archive -Path $zip -DestinationPath (Join-Path $runtimeDir "mongodb-tmp") -Force
    $inner = Get-ChildItem (Join-Path $runtimeDir "mongodb-tmp") -Directory | Select-Object -First 1
    Move-Item $inner.FullName (Join-Path $runtimeDir "mongodb")
    Remove-Item (Join-Path $runtimeDir "mongodb-tmp") -Recurse -Force
    Remove-Item $zip -Force
}
Write-Ok "mongod: $mongodExe"

# ---- 4. Redis ----
Write-Step "[4/8] 准备 Redis $RedisVersion（tporadowski Windows 构建）"
$redisExe = Join-Path $runtimeDir "redis\redis-server.exe"
if (-not (Test-Path $redisExe)) {
    $zip = Join-Path $env:TEMP "redis-win64-$RedisVersion.zip"
    Download-File "https://github.com/tporadowski/redis/releases/download/v$RedisVersion/Redis-x64-$RedisVersion.zip" $zip
    Expand-Archive -Path $zip -DestinationPath (Join-Path $runtimeDir "redis") -Force
    Remove-Item $zip -Force
}
Write-Ok "redis-server: $redisExe"

if (-not $NoStart) {
    # ---- 启动数据库 ----
    Write-Step "[5/8] 启动 MongoDB / Redis"
    if (Test-PortOpen $MongoPort) {
        Write-Ok "MongoDB 端口 $MongoPort 已在监听，跳过启动"
    } else {
        $mongoArgs = @("--dbpath", "`"$(Join-Path $dataDir 'mongodb')`"", "--port", "$MongoPort", "--bind_ip", "127.0.0.1")
        Start-Bg $mongodExe $mongoArgs $root (Join-Path $logsDir "mongod.out.log") (Join-Path $logsDir "mongod.err.log") | Out-Null
        if (-not (Wait-Port $MongoPort 90 "MongoDB")) {
            Write-Warn2 "MongoDB 启动失败，请查看 $logsDir\mongod.err.log（若提示缺少 DLL，请安装 VC++ 运行库）"
            Fail "MongoDB 未能在 90 秒内就绪"
        }
    }
    if (Test-PortOpen $RedisPort) {
        Write-Ok "Redis 端口 $RedisPort 已在监听，跳过启动"
    } else {
        # 注意：不能传空字符串参数（""），Start-Process -ArgumentList 的 ValidateNotNullOrEmpty 会拒绝
        $redisArgs = @("--port", "$RedisPort", "--bind", "127.0.0.1", "--save", "900", "1", "--appendonly", "no")
        Start-Bg $redisExe $redisArgs (Join-Path $dataDir "redis") (Join-Path $logsDir "redis.out.log") (Join-Path $logsDir "redis.err.log") | Out-Null
        if (-not (Wait-Port $RedisPort 60 "Redis")) {
            Write-Warn2 "Redis 启动失败，请查看 $logsDir\redis.err.log"
            Fail "Redis 未能在 60 秒内就绪"
        }
    }
} else {
    Write-Step "[5/8] 跳过数据库启动（-NoStart）"
}

# ---- 5. 前端 ----
Write-Step "[6/8] 准备前端"
$distIndex = Join-Path $root "frontend\dist\index.html"
if (Test-Path $distIndex) {
    Write-Ok "前端构建产物已存在，跳过"
} elseif ($SkipFrontendBuild) {
    Fail "指定了 -SkipFrontendBuild 但 frontend\dist 不存在"
} else {
    if (Get-Command npm -ErrorAction SilentlyContinue) {
        Write-Host "  使用 npm 构建前端（首次较慢）"
        Push-Location (Join-Path $root "frontend")
        try {
            $env:NODE_OPTIONS = "--max-old-space-size=4096"
            & npm ci --no-audit --no-fund
            if ($LASTEXITCODE -ne 0) { Fail "npm ci 失败" }
            & npm run build
            if ($LASTEXITCODE -ne 0) { Fail "npm run build 失败" }
        } finally { Pop-Location }
        Write-Ok "前端构建完成"
    } else {
        Write-Warn2 "未检测到 Node.js，尝试下载预构建前端"
        $zip = Join-Path $env:TEMP "frontend-dist.zip"
        Download-File "$RepoUrl/releases/latest/download/frontend-dist.zip" $zip
        Expand-Archive -Path $zip -DestinationPath (Join-Path $root "frontend\dist") -Force
        Remove-Item $zip -Force
        Write-Ok "预构建前端已就绪"
    }
}

# ---- 6. 虚拟环境与依赖 ----
Write-Step "[7/8] 安装 Python 依赖"
$venvDir = Join-Path $root ".venv"
$venvPy  = Join-Path $venvDir "Scripts\python.exe"
if (-not (Test-Path $venvPy)) {
    $a = $py.Pre + @("-m", "venv", $venvDir)
    & $py.Cmd @a
    if ($LASTEXITCODE -ne 0) { Fail "创建虚拟环境失败" }
}
& $venvPy -m pip install --upgrade pip --quiet
$pipArgs = @("-m", "pip", "install", "-e", ".", "--quiet")
if ($Mirror) { $pipArgs += @("-i", "$($Mirror.TrimEnd('/'))/pypi/simple") }
Push-Location $root
try {
    & $venvPy @pipArgs
    if ($LASTEXITCODE -ne 0) { Fail "依赖安装失败（可尝试 -Mirror 换源后重试）" }
} finally { Pop-Location }
Write-Ok "依赖安装完成"

# ---- 7. 生成 .env ----
Write-Step "生成 .env 配置"
if (-not $AdminPassword) { $AdminPassword = "admin" + (New-RandomHex 4) }
$envPath = Join-Path $root ".env"
$overrides = @{
    "MONGODB_HOST"           = "127.0.0.1"
    "MONGODB_PORT"           = "$MongoPort"
    "MONGODB_USERNAME"       = ""
    "MONGODB_PASSWORD"       = ""
    # 本地 mongod 未启用认证，必须清掉 .env.example 里的占位凭据连接串（否则认证失败）
    "MONGODB_CONNECTION_STRING" = "mongodb://127.0.0.1:$MongoPort/tradingagents"
    "REDIS_HOST"             = "127.0.0.1"
    "REDIS_PORT"             = "$RedisPort"
    "REDIS_PASSWORD"         = ""
    "REDIS_DB"               = "0"
    "JWT_SECRET"             = (New-RandomHex 32)
    "CSRF_SECRET"            = (New-RandomHex 32)
    "ADMIN_DEFAULT_PASSWORD" = $AdminPassword
    "HOST"                   = "127.0.0.1"
    "PORT"                   = "$Port"
    "DEBUG"                  = "false"
}
Set-EnvFile $envPath (Join-Path $root ".env.example") $overrides
Write-Ok ".env 已生成（JWT/CSRF 密钥随机，管理员密码见下方输出）"

if ($NoStart) {
    Write-Step "安装完成（-NoStart，未启动服务）"
    Write-Host "  启动命令: $venvPy installer\run_server.py"
    exit 0
}

# ---- 8. 启动服务 ----
Write-Step "[8/8] 启动服务"
$serverOut = Join-Path $logsDir "server.out.log"
$serverErr = Join-Path $logsDir "server.err.log"
Start-Bg $venvPy @("installer\run_server.py") $root $serverOut $serverErr | Out-Null
if (-not (Wait-Health $Port 300)) {
    Write-Warn2 "服务未在 5 分钟内就绪，请查看 $serverErr"
    if (Test-Path $serverErr) { Get-Content $serverErr -Tail 20 | ForEach-Object { Write-Host "    $_" } }
    Fail "启动失败"
}
Write-Ok "服务已就绪"

# ---- 生成启动/停止脚本（非本地源码模式）----
if (-not $localMode) {
    $startPs1 = @"
Set-Location '$root'
`$py = Join-Path '$root' '.venv\Scripts\python.exe'
Start-Process -FilePath `$py -ArgumentList 'installer\run_server.py' -WorkingDirectory '$root' -WindowStyle Hidden
Write-Host 'TradingAgents-CN 已启动: http://127.0.0.1:$Port'
"@
    Set-Content -Path (Join-Path $root "start.ps1") -Value $startPs1 -Encoding UTF8
    $stopPs1 = @"
Get-CimInstance Win32_Process | Where-Object { `$_.CommandLine -match 'run_server\.py|mongod.*--port $MongoPort|redis-server.*--port $RedisPort' } | ForEach-Object { Stop-Process -Id `$_.ProcessId -Force -ErrorAction SilentlyContinue }
Write-Host 'TradingAgents-CN 已停止'
"@
    Set-Content -Path (Join-Path $root "stop.ps1") -Value $stopPs1 -Encoding UTF8
}

Write-Host ""
Write-Host "==================================================" -ForegroundColor Green
Write-Host " TradingAgents-CN 安装完成" -ForegroundColor Green
Write-Host "==================================================" -ForegroundColor Green
Write-Host "  访问地址   : http://127.0.0.1:$Port"
Write-Host "  管理员账号 : admin"
Write-Host "  管理员密码 : $AdminPassword"
Write-Host "  项目目录   : $root"
Write-Host "  日志目录   : $logsDir"
if (-not $localMode) {
    Write-Host "  启动/停止  : .\start.ps1 / .\stop.ps1"
}
Write-Host "==================================================" -ForegroundColor Green
