# Test Port Configuration Script
# Verify that all scripts use dynamic ports correctly

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Port Configuration Test" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

$root = Split-Path -Parent $PSScriptRoot

# Test 1: Check start_all.ps1 for hardcoded ports
Write-Host "[1/3] Checking start_all.ps1..." -ForegroundColor Yellow
$startAllPath = Join-Path $root "scripts\installer\start_all.ps1"
$startAllContent = Get-Content $startAllPath -Raw

$hardcodedPorts = @()
if ($startAllContent -match 'mongodb.*27017' -and $startAllContent -notmatch '\$mongoPort') {
    $hardcodedPorts += "MongoDB port 27017 hardcoded in start_all.ps1"
}
if ($startAllContent -match 'redis.*6379' -and $startAllContent -notmatch '\$redisPort') {
    $hardcodedPorts += "Redis port 6379 hardcoded in start_all.ps1"
}
if ($startAllContent -match 'backend.*8000' -and $startAllContent -notmatch '\$backendPort') {
    $hardcodedPorts += "Backend port 8000 hardcoded in start_all.ps1"
}

if ($hardcodedPorts.Count -eq 0) {
    Write-Host "  ✅ No hardcoded ports found" -ForegroundColor Green
} else {
    Write-Host "  ❌ Found hardcoded ports:" -ForegroundColor Red
    $hardcodedPorts | ForEach-Object { Write-Host "    - $_" -ForegroundColor Red }
}

# Test 2: Check start_services_clean.ps1 for hardcoded ports
Write-Host ""
Write-Host "[2/3] Checking start_services_clean.ps1..." -ForegroundColor Yellow
$startServicesPath = Join-Path $root "scripts\installer\start_services_clean.ps1"
$startServicesContent = Get-Content $startServicesPath -Raw

$hardcodedPorts = @()
if ($startServicesContent -match '127\.0\.0\.1\s+27017' -and $startServicesContent -notmatch '\$mongoPort') {
    $hardcodedPorts += "MongoDB port 27017 hardcoded in start_services_clean.ps1"
}
if ($startServicesContent -match 'port\s+27017' -and $startServicesContent -notmatch '\$mongoPort') {
    $hardcodedPorts += "MongoDB port 27017 in error message"
}
if ($startServicesContent -match 'port\s+6379' -and $startServicesContent -notmatch '\$redisPort') {
    $hardcodedPorts += "Redis port 6379 in error message"
}
if ($startServicesContent -match '127\.0\.0\.1:27017' -and $startServicesContent -notmatch '\$mongoPort') {
    $hardcodedPorts += "MongoDB connection string hardcoded"
}

if ($hardcodedPorts.Count -eq 0) {
    Write-Host "  ✅ No hardcoded ports found" -ForegroundColor Green
} else {
    Write-Host "  ❌ Found hardcoded ports:" -ForegroundColor Red
    $hardcodedPorts | ForEach-Object { Write-Host "    - $_" -ForegroundColor Red }
}

# Test 3: Check for database_export_config_*.json pattern
Write-Host ""
Write-Host "[3/3] Checking config file pattern..." -ForegroundColor Yellow
if ($startAllContent -match 'database_export_config_\*\.json') {
    Write-Host "  ✅ Using wildcard pattern for config file" -ForegroundColor Green
} elseif ($startAllContent -match 'database_export_config_\d{4}-\d{2}-\d{2}\.json') {
    Write-Host "  ❌ Hardcoded config file date" -ForegroundColor Red
} else {
    Write-Host "  ⚠️  Config file pattern not found" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Test completed" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

