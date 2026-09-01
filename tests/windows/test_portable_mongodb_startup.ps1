[CmdletBinding()]
param(
    [int]$MongoPort = 27017
)

$ErrorActionPreference = 'Stop'

if ($MongoPort -lt 1024 -or $MongoPort -gt 65535) {
    throw "MongoPort must be between 1024 and 65535: $MongoPort"
}

$root = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$setupPath = Join-Path $root 'scripts\installer\setup.ps1'
$servicesPath = Join-Path $root 'scripts\installer\start_services_clean.ps1'
$startAllPath = Join-Path $root 'scripts\installer\start_all.ps1'
$helperPath = Join-Path $root 'scripts\init_mongodb_user.py'
$syncPath = Join-Path $root 'scripts\deployment\sync_to_portable.ps1'
$packagePath = Join-Path $root 'scripts\deployment\build_portable_package.ps1'
$preparePath = Join-Path $root 'scripts\windows-installer\prepare\build_portable.ps1'
$nsisPath = Join-Path $root 'scripts\windows-installer\nsis\installer.nsi'

function Assert-Contains {
    param([string]$Text, [string]$Pattern, [string]$Description)
    if ($Text -notmatch $Pattern) {
        throw "Missing expected $Description"
    }
}

foreach ($path in @($setupPath, $servicesPath, $startAllPath, $helperPath, $syncPath, $packagePath, $preparePath, $nsisPath)) {
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
        throw "Required startup file not found: $path"
    }
}

$setup = Get-Content -LiteralPath $setupPath -Raw
$services = Get-Content -LiteralPath $servicesPath -Raw
$startAll = Get-Content -LiteralPath $startAllPath -Raw
$sync = Get-Content -LiteralPath $syncPath -Raw
$package = Get-Content -LiteralPath $packagePath -Raw
$prepare = Get-Content -LiteralPath $preparePath -Raw
$nsis = Get-Content -LiteralPath $nsisPath -Raw

Assert-Contains $services '\$mongoPort\s*=.*27017' 'default MongoDB port'
Assert-Contains $services '--port \$mongoPort' 'configured MongoDB port argument'
Assert-Contains $services '--auth-source' 'MongoDB auth-source propagation'
Assert-Contains $services '--create-only' 'no-auth MongoDB user creation'
Assert-Contains $services 'Wait-ForTcpPort' 'bounded MongoDB readiness check'
Assert-Contains $services '--verify-only' 'authenticated MongoDB verification'
Assert-Contains $services 'No initialization marker was created' 'failed-initialization marker guard'

if ($services -match '(?m)initScript.*27017') {
    throw 'MongoDB initialization helper must not receive a hard-coded 27017 port'
}

Assert-Contains $startAll 'Wait-ForTcpPort\s+-HostName \$mongoProbeHost\s+-Port \$mongoPort' 'import readiness gate'
Assert-Contains $startAll '--mongodb-host \$mongoHost --mongodb-port \$mongoPort' 'explicit import endpoint arguments'
Assert-Contains $startAll 'importExitCode\s+-eq 0' 'successful import check'
Assert-Contains $startAll 'Import marker was not created' 'failed-import marker guard'
Assert-Contains $setup 'Sync-MongoUriEndpoints' 'portable setup URI synchronization'
Assert-Contains $setup 'MONGODB_CONNECTION_STRING\|MONGODB_URL\|MONGO_URI\|MONGODB_URI' 'portable setup URI aliases'
Assert-Contains $setup '-PortNumber \$MongoPort' 'portable setup selected MongoDB port'
Assert-Contains $startAll 'Sync-MongoUriEndpoints' 'portable startup URI synchronization'
Assert-Contains $startAll 'MONGODB_CONNECTION_STRING\|MONGODB_URL\|MONGO_URI\|MONGODB_URI' 'portable startup URI aliases'

foreach ($assemblyScript in @($sync, $package, $prepare)) {
    Assert-Contains $assemblyScript 'scripts\\init_mongodb_user\.py' 'staged MongoDB initialization helper'
    Assert-Contains $assemblyScript 'scripts\\import_config_and_create_user\.py' 'staged configuration importer'
    Assert-Contains $assemblyScript 'start_services_clean\.ps1' 'staged service starter'
}

Assert-Contains $nsis 'MONGODB_CONNECTION_STRING\|MONGODB_URL\|MONGO_URI\|MONGODB_URI' 'derived MongoDB URI rewrite'
Assert-Contains $nsis 'MONGODB_PORT=\$MongoPort' 'selected MongoDB port rewrite'
Assert-Contains $nsis '`\$\$1`\$\$2`\$\$3:\$MongoPort' 'URI endpoint replacement preserving URI suffix'

Write-Host "Portable MongoDB startup smoke checks passed for port $MongoPort" -ForegroundColor Green
