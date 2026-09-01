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

Write-Log "Copying application files..."
Copy-Item -Recurse -Force (Join-Path $root "app") (Join-Path $out "app")
Write-Log "app directory copied"

Copy-Item -Recurse -Force (Join-Path $root "scripts\installer") (Join-Path $out "scripts\installer")
Write-Log "scripts\installer directory copied"

# Keep the NSIS payload and the green package on the same tracked startup
# scripts. The NSIS launcher starts from the package root, while the documented
# portable layout also exposes scripts\installer.
$startupFiles = @(
  @{ Source = "scripts\installer\start_all.ps1"; Destination = "start_all.ps1" },
  @{ Source = "scripts\installer\start_services_clean.ps1"; Destination = "start_services_clean.ps1" },
  @{ Source = "scripts\installer\stop_all.ps1"; Destination = "stop_all.ps1" },
  @{ Source = "scripts\import_config_and_create_user.py"; Destination = "scripts\import_config_and_create_user.py" },
  @{ Source = "scripts\init_mongodb_user.py"; Destination = "scripts\init_mongodb_user.py" }
)
foreach ($file in $startupFiles) {
  $source = Join-Path $root $file.Source
  $destination = Join-Path $out $file.Destination
  if (-not (Test-Path -LiteralPath $source -PathType Leaf)) {
    Write-Log "Required startup file not found: $source" "ERROR"
    exit 1
  }
  $destinationDir = Split-Path -Parent $destination
  New-Item -ItemType Directory -Force -Path $destinationDir | Out-Null
  Copy-Item -LiteralPath $source -Destination $destination -Force
  Write-Log "$($file.Destination) copied"
}

$installSource = Join-Path $root "install"
if (Test-Path -LiteralPath $installSource) {
  $installDestination = Join-Path $out "install"
  New-Item -ItemType Directory -Force -Path $installDestination | Out-Null
  Get-ChildItem -LiteralPath $installSource -Filter "database_export_config*.json" -File | Copy-Item -Destination $installDestination -Force
  Write-Log "database configuration files copied"
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

Write-Log "Generating nginx configuration..."
$nginxConf = Join-Path $out "runtime\nginx.conf"
$nginxLines = @(
    "worker_processes auto;",
    "events { worker_connections 1024; }",
    "http {",
    "    upstream backend { server 127.0.0.1:8000; }",
    "    server {",
    "        listen 80;",
    "        server_name localhost;",
    "        client_max_body_size 100M;",
    "        location / { root /path/to/frontend; try_files `$uri `$uri/ /index.html; }",
    "        location /api { proxy_pass http://backend; proxy_set_header Host `$host; }",
    "    }",
    "}"
)
$nginxLines | Out-File -Encoding UTF8 $nginxConf
Write-Log "Nginx configuration generated"

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
