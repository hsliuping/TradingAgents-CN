param(
  [string]$OutputDir = "release\portable",
  [switch]$Verbose = $false
)

$ErrorActionPreference = "Stop"
$root = (Resolve-Path (Join-Path $PSScriptRoot "..\..\..")).Path
$out = Join-Path $root $OutputDir

function Write-Log {
    param([string]$Message, [string]$Level = "INFO")
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Write-Host "[$timestamp] [$Level] $Message"
}

Write-Log "Starting portable version build..."
Write-Log "Output directory: $out"

$frontendDir = Join-Path $root "frontend"
$frontendDist = Join-Path $frontendDir "dist"
$requirements = Join-Path $root "requirements.txt"

Write-Log "Creating directory structure..."
New-Item -ItemType Directory -Force -Path $out | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $out "runtime") | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $out "logs") | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $out "data\mongodb\db") | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $out "data\redis\data") | Out-Null
Write-Log "Directory structure created"

Write-Log "Copying configuration files..."
if (Test-Path (Join-Path $root ".env.example")) {
  Copy-Item -Force (Join-Path $root ".env.example") (Join-Path $out ".env.example")
  Write-Log ".env.example copied"
}

# 🔥 清理缓存：在复制前清理源目录的 Python 缓存（只清理源文件缓存）
Write-Log "Cleaning Python cache files (preserving compiled bytecode)..."
$cacheDirs = Get-ChildItem -Path $root -Recurse -Directory -Filter "__pycache__" -ErrorAction SilentlyContinue
$cacheCount = ($cacheDirs | Measure-Object).Count
if ($cacheCount -gt 0) {
    Write-Log "Found $cacheCount __pycache__ directories, removing..."
    $cacheDirs | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
    Write-Log "Python cache cleaned"
} else {
    Write-Log "No Python cache found"
}

Write-Log "Copying application files..."
# 🔥 只排除 __pycache__ 目录，保留编译后的 .pyc 和 .pyd 文件
$excludeItems = @("__pycache__")
Copy-Item -Recurse -Force -Exclude $excludeItems (Join-Path $root "app") (Join-Path $out "app")
Write-Log "app directory copied"

Copy-Item -Recurse -Force -Exclude $excludeItems (Join-Path $root "scripts\installer") (Join-Path $out "scripts\installer")
Write-Log "scripts\installer directory copied"

# Copy monitor scripts
Copy-Item -Recurse -Force -Exclude $excludeItems (Join-Path $root "scripts\monitor") (Join-Path $out "scripts\monitor")
Write-Log "scripts\monitor directory copied"

# 🔥 清理目标目录中可能存在的源文件缓存（双重保险，但保留编译后的字节码）
Write-Log "Cleaning source cache files in output directory (preserving compiled bytecode)..."
$outCacheDirs = Get-ChildItem -Path $out -Recurse -Directory -Filter "__pycache__" -ErrorAction SilentlyContinue
if ($outCacheDirs) {
    $outCacheDirs | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
    Write-Log "Output directory __pycache__ cleaned"
}
# 🔥 只清理不在编译目录中的 .pyc 文件（源文件的缓存）
$outPycFiles = Get-ChildItem -Path $out -Recurse -Filter "*.pyc" -ErrorAction SilentlyContinue | Where-Object {
    $fullPath = $_.FullName
    # 排除编译后的字节码目录
    $fullPath -notlike "*\core\other\*" -and
    $fullPath -notlike "*\app\*"
}
if ($outPycFiles) {
    $outPycFiles | Remove-Item -Force -ErrorAction SilentlyContinue
    Write-Log "Output directory source cache .pyc files cleaned (preserved compiled bytecode)"
}

if (Test-Path (Join-Path $root "vendors")) {
  Copy-Item -Recurse -Force (Join-Path $root "vendors") (Join-Path $out "vendors")
  Write-Log "vendors directory copied"
}

Write-Log "Checking frontend build..."
if (-not (Test-Path $frontendDist)) {
  Write-Log "Frontend dist not found, building frontend..."
  Push-Location $frontendDir
  try {
    npm install
    npm run build
    Write-Log "Frontend build completed"
  } catch {
    Write-Log "Frontend build failed: $_" "ERROR"
    exit 1
  } finally {
    Pop-Location
  }
}

Write-Log "Copying frontend files..."
Copy-Item -Recurse -Force $frontendDist (Join-Path $out "frontend")
Write-Log "Frontend files copied"

Write-Log "Creating Python virtual environment..."
$venvPath = Join-Path $out "venv"
python -m venv $venvPath
Write-Log "Virtual environment created"

Write-Log "Installing Python dependencies..."
$pipExe = Join-Path $venvPath "Scripts\pip.exe"
& $pipExe install -r $requirements
Write-Log "Dependencies installed"

Write-Log "Copying nginx configuration..."
$sourceNginxConf = Join-Path $PSScriptRoot "..\..\runtime\nginx.conf"
$destNginxConf = Join-Path $out "runtime\nginx.conf"
$destRuntimeDir = Join-Path $out "runtime"

# Ensure runtime directory exists
if (-not (Test-Path $destRuntimeDir)) {
    New-Item -ItemType Directory -Path $destRuntimeDir -Force | Out-Null
}

# Copy the complete nginx.conf from project root
if (Test-Path $sourceNginxConf) {
    Copy-Item -Path $sourceNginxConf -Destination $destNginxConf -Force
    Write-Log "nginx.conf copied from $sourceNginxConf"
} else {
    Write-Log "WARNING: nginx.conf not found at $sourceNginxConf, skipping..."
}

# Copy mime.types (required by nginx.conf)
$sourceMimeTypes = Join-Path $PSScriptRoot "..\..\runtime\mime.types"
$destMimeTypes = Join-Path $out "runtime\mime.types"
if (Test-Path $sourceMimeTypes) {
    Copy-Item -Path $sourceMimeTypes -Destination $destMimeTypes -Force
    Write-Log "mime.types copied from $sourceMimeTypes"
} else {
    Write-Log "WARNING: mime.types not found at $sourceMimeTypes, skipping..."
}

Write-Log "Nginx configuration generated"

# Copy startup scripts to root directory (for Windows installer)
Write-Log "Copying startup scripts to root directory..."
$startupScripts = @(
    "start_all.ps1",
    "start_services_clean.ps1",
    "stop_all.ps1"
)

foreach ($script in $startupScripts) {
    $sourceScript = Join-Path $root "scripts\installer\$script"
    $destScript = Join-Path $out $script

    if (Test-Path $sourceScript) {
        Copy-Item -Path $sourceScript -Destination $destScript -Force
        Write-Log "Copied $script to root directory"
    } else {
        Write-Log "WARNING: $script not found at $sourceScript" "WARNING"
    }
}

Write-Log ""
Write-Log "=========================================="
Write-Log "Portable version build completed!"
Write-Log "=========================================="
Write-Log "Location: $out"
Write-Log "Next steps:"
Write-Log "1. Review .env.example and create .env"
Write-Log "2. Start services: .\start_all.ps1"
Write-Log "3. Access Web UI at http://localhost"

return $out
