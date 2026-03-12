<#
.SYNOPSIS
    TradingAgents-CN 自动更新器
.DESCRIPTION
    独立进程：等待后端退出 → 停止所有服务 → 备份 → 解压更新包 → 重启服务
    由后端 UpdateService.apply_update() 启动，必须独立于后端进程存活。
.PARAMETER UpdateFile
    更新包 zip 文件路径
.PARAMETER TargetVersion
    目标版本号
.PARAMETER CurrentVersion
    当前版本号
.PARAMETER ProjectRoot
    项目根目录
#>

param(
    [Parameter(Mandatory=$true)] [string]$UpdateFile,
    [Parameter(Mandatory=$true)] [string]$TargetVersion,
    [Parameter(Mandatory=$true)] [string]$CurrentVersion,
    [Parameter(Mandatory=$true)] [string]$ProjectRoot
)

$ErrorActionPreference = "Continue"

# ── 日志 ──────────────────────────────────────────────
$logsDir = Join-Path $ProjectRoot "logs"
if (-not (Test-Path $logsDir)) { New-Item -ItemType Directory -Path $logsDir -Force | Out-Null }
$logFile = Join-Path $logsDir "updater.log"

function Write-Log {
    param([string]$Message, [string]$Level = "INFO")
    $ts = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $line = "[$ts] [$Level] $Message"
    Add-Content -Path $logFile -Value $line -Encoding UTF8
    Write-Host $line
}

Write-Log "========== Update started: $CurrentVersion -> $TargetVersion =========="
Write-Log "UpdateFile : $UpdateFile"
Write-Log "ProjectRoot: $ProjectRoot"

# ── 1. 等待后端退出 ──────────────────────────────────
Write-Log "Step 1: Waiting for backend to exit..."
$pidFile = Join-Path $ProjectRoot "runtime\pids.json"
$backendPid = $null

if (Test-Path $pidFile) {
    try {
        $pids = Get-Content $pidFile -Raw | ConvertFrom-Json
        $backendPid = $pids.backend
    } catch {}
}

if ($backendPid) {
    $waited = 0
    while ($waited -lt 60) {
        $proc = Get-Process -Id $backendPid -ErrorAction SilentlyContinue
        if (-not $proc) { break }
        Start-Sleep -Seconds 2
        $waited += 2
    }
    if ($waited -ge 60) {
        Write-Log "Backend did not exit in 60s, force killing PID $backendPid" "WARN"
        Stop-Process -Id $backendPid -Force -ErrorAction SilentlyContinue
        Start-Sleep -Seconds 2
    }
}
Write-Log "Backend exited"

# ── 2. 停止所有服务 ──────────────────────────────────
Write-Log "Step 2: Stopping all services..."
$stopScript = Join-Path $ProjectRoot "scripts\installer\stop_all.ps1"
if (Test-Path $stopScript) {
    try {
        Push-Location $ProjectRoot
        & powershell -ExecutionPolicy Bypass -File $stopScript 2>&1 | ForEach-Object { Write-Log "  [stop] $_" }
        Pop-Location
    } catch {
        Write-Log "stop_all.ps1 error: $_" "WARN"
    }
} else {
    Write-Log "stop_all.ps1 not found, skipping" "WARN"
}
Start-Sleep -Seconds 3
Write-Log "All services stopped"

# ── 3. 备份当前版本 ──────────────────────────────────
Write-Log "Step 3: Backing up current version..."
$backupDir = Join-Path $ProjectRoot "backup"
$backupName = "v${CurrentVersion}_$(Get-Date -Format 'yyyyMMdd_HHmmss')"
$backupPath = Join-Path $backupDir $backupName

if (-not (Test-Path $backupDir)) { New-Item -ItemType Directory -Path $backupDir -Force | Out-Null }

try {
    New-Item -ItemType Directory -Path $backupPath -Force | Out-Null

    # 只备份代码目录（不备份 data/vendors/logs 等大目录）
    $backupItems = @(
        "app",
        "core",
        "frontend",
        "scripts",
        "tradingagents",
        "prompts",
        "migrations",
        "releases",
        "install",
        "config",
        "VERSION",
        "BUILD_INFO"
    )
    foreach ($item in $backupItems) {
        $src = Join-Path $ProjectRoot $item
        if (Test-Path $src) {
            $dst = Join-Path $backupPath $item
            if ((Get-Item $src).PSIsContainer) {
                Copy-Item -Path $src -Destination $dst -Recurse -Force
            } else {
                Copy-Item -Path $src -Destination $dst -Force
            }
        }
    }
    Write-Log "Backup created: $backupPath"
} catch {
    Write-Log "Backup failed: $_ (continuing anyway)" "WARN"
}

# ── 4. 解压更新包 ──────────────────────────────────
Write-Log "Step 4: Extracting update package..."
if (-not (Test-Path $UpdateFile)) {
    Write-Log "Update file not found: $UpdateFile" "ERROR"
    exit 1
}

$tempExtract = Join-Path $ProjectRoot "runtime\update_temp"
if (Test-Path $tempExtract) { Remove-Item -Path $tempExtract -Recurse -Force }

try {
    Expand-Archive -Path $UpdateFile -DestinationPath $tempExtract -Force
    Write-Log "Extracted to temp: $tempExtract"
} catch {
    Write-Log "Extract failed: $_" "ERROR"
    exit 1
}

# ── 5. 替换文件 ──────────────────────────────────────
Write-Log "Step 5: Replacing files..."
# 需要替换的目录/文件（不替换 vendors/data/.env/logs/runtime/backup）
$replaceItems = @(
    "app",
    "core",
    "frontend",
    "scripts",
    "tradingagents",
    "prompts",
    "migrations",
    "releases",
    "install",
    "config",
    "VERSION",
    "BUILD_INFO"
)
Write-Log ("  Replace items: " + ($replaceItems -join ", "))

# 检查解压目录中是否有子目录包装（有些 zip 会多一层目录）
$extractedContents = Get-ChildItem -Path $tempExtract
if ($extractedContents.Count -eq 1 -and $extractedContents[0].PSIsContainer) {
    $tempExtract = $extractedContents[0].FullName
    Write-Log "  Detected wrapper directory, using: $tempExtract"
}

$replacedCount = 0
foreach ($item in $replaceItems) {
    $src = Join-Path $tempExtract $item
    $dst = Join-Path $ProjectRoot $item
    if (Test-Path $src) {
        try {
            if ((Get-Item $src).PSIsContainer) {
                if (Test-Path $dst) { Remove-Item -Path $dst -Recurse -Force }
                Copy-Item -Path $src -Destination $dst -Recurse -Force
            } else {
                Copy-Item -Path $src -Destination $dst -Force
            }
            $replacedCount++
            Write-Log "  Replaced: $item"
        } catch {
            Write-Log "  Failed to replace $item : $_" "ERROR"
        }
    }
}
Write-Log "Replaced $replacedCount items"

# ── 6. 清理临时文件 ──────────────────────────────────
Write-Log "Step 6: Cleaning up..."
try {
    $tempDir = Join-Path $ProjectRoot "runtime\update_temp"
    if (Test-Path $tempDir) { Remove-Item -Path $tempDir -Recurse -Force }
    Write-Log "Temp directory cleaned"
} catch {
    Write-Log "Cleanup warning: $_" "WARN"
}

# ── 7. 重启所有服务 ──────────────────────────────────
Write-Log "Step 7: Restarting all services..."
$startScript = Join-Path $ProjectRoot "scripts\installer\start_all.ps1"
if (-not (Test-Path $startScript)) {
    $startScript = Join-Path $ProjectRoot "start_all.ps1"
}

if (Test-Path $startScript) {
    try {
        Push-Location $ProjectRoot
        Start-Process -FilePath "powershell.exe" `
            -ArgumentList "-ExecutionPolicy", "Bypass", "-File", $startScript `
            -WorkingDirectory $ProjectRoot `
            -WindowStyle Normal
        Pop-Location
        Write-Log "start_all.ps1 launched"
    } catch {
        Write-Log "Failed to launch start_all.ps1: $_" "ERROR"
    }
} else {
    Write-Log "start_all.ps1 not found at: $startScript" "ERROR"
    Write-Log "Please manually restart services" "ERROR"
}

# ── 8. 清理旧备份（保留最近 3 个）────────────────────
Write-Log "Step 8: Cleaning old backups..."
try {
    $backups = Get-ChildItem -Path $backupDir -Directory -ErrorAction SilentlyContinue |
        Sort-Object CreationTime -Descending |
        Select-Object -Skip 3
    foreach ($old in $backups) {
        Remove-Item -Path $old.FullName -Recurse -Force
        Write-Log "  Removed old backup: $($old.Name)"
    }
} catch {
    Write-Log "Backup cleanup warning: $_" "WARN"
}

Write-Log "========== Update completed: $CurrentVersion -> $TargetVersion =========="
Write-Log "Services are restarting. Please wait a moment and refresh the browser."
