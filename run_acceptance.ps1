# TradingAgents-CN Acceptance Test Runner
# 按版本号运行验收测试，自动匹配 start_dev.ps1 中的端口配置。
#
# 用法:
#   .\run_acceptance.ps1 api 3.0        # 运行后端 API 验收测试
#   .\run_acceptance.ps1 e2e 3.0        # 运行前端 E2E 验收测试
#   .\run_acceptance.ps1 all 3.0        # 运行 API + E2E
#   .\run_acceptance.ps1 status         # 查看版本端口配置

[CmdletBinding()]
param(
    [Parameter(Position=0)]
    [ValidateSet("api", "e2e", "all", "status", $null)]
    [string]$Command,

    [Parameter(Position=1)]
    [ValidateSet("2.0", "2.1", "3.0", $null)]
    [string]$Version,

    [switch]$IncludeETF,
    [switch]$DryRun,
    [switch]$Help
)

$VersionConfig = @{
    "2.0" = @{ Backend=8000; Frontend=3000 }
    "2.1" = @{ Backend=8001; Frontend=3001 }
    "3.0" = @{ Backend=8002; Frontend=3002 }
}

function Show-Help {
    Write-Host ""
    Write-Host "TradingAgents-CN Acceptance Test Runner" -ForegroundColor Cyan
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "Usage:" -ForegroundColor Yellow
    Write-Host "  .\run_acceptance.ps1 <command> [version] [options]"
    Write-Host ""
    Write-Host "Commands:" -ForegroundColor Yellow
    Write-Host "  api <version>       运行后端 API 验收测试"
    Write-Host "  e2e <version>       运行前端 E2E 验收测试"
    Write-Host "  all <version>       运行 API + E2E 验收测试"
    Write-Host "  status              查看版本端口配置"
    Write-Host ""
    Write-Host "Options:" -ForegroundColor Yellow
    Write-Host "  -IncludeETF         包含 ETF GA 测试（可能访问外部数据源，耗时更长）"
    Write-Host "  -DryRun             只打印将要执行的命令，不实际运行"
    Write-Host "  -Help               显示帮助"
    Write-Host ""
    Write-Host "Examples:" -ForegroundColor Yellow
    Write-Host "  .\start_dev.ps1 all 3.0"
    Write-Host "  .\run_acceptance.ps1 all 3.0"
    Write-Host "  .\run_acceptance.ps1 api 3.0 -IncludeETF"
    Write-Host ""
}

if ($Help -or -not $Command) {
    Show-Help
    exit 0
}

if ($Command -eq "status") {
    Write-Host ""
    Write-Host "=========================================" -ForegroundColor Cyan
    Write-Host "  验收测试版本端口配置" -ForegroundColor Cyan
    Write-Host "=========================================" -ForegroundColor Cyan
    Write-Host ""
    foreach ($v in @("2.0", "2.1", "3.0")) {
        $c = $VersionConfig[$v]
        Write-Host "  v$($v):" -ForegroundColor White
        Write-Host "    Backend:  http://127.0.0.1:$($c.Backend)" -ForegroundColor Gray
        Write-Host "    Frontend: http://localhost:$($c.Frontend)" -ForegroundColor Gray
        Write-Host ""
    }
    exit 0
}

if (-not $Version) {
    Write-Host "[ERROR] 需要指定版本号，例如: .\run_acceptance.ps1 all 3.0" -ForegroundColor Red
    exit 1
}

$ErrorActionPreference = "Stop"
$root = $PSScriptRoot
$config = $VersionConfig[$Version]
$backendUrl = "http://127.0.0.1:$($config.Backend)"
$frontendUrl = "http://localhost:$($config.Frontend)"
$apiFilter = if ($IncludeETF) { "" } else { "-k `"not etf`"" }

$env:TEST_BACKEND_URL = $backendUrl
$env:E2E_BASE_URL = $frontendUrl

$pythonExe = $null
$pythonCandidates = @(
    (Join-Path $root "env\Scripts\python.exe"),
    (Join-Path $root "venv\Scripts\python.exe"),
    "python"
)
foreach ($path in $pythonCandidates) {
    if ($path -eq "python" -or (Test-Path $path)) {
        $pythonExe = $path
        break
    }
}

function Invoke-Step {
    param(
        [string]$Title,
        [string]$CommandLine,
        [scriptblock]$Block
    )

    Write-Host ""
    Write-Host "[$Title]" -ForegroundColor Yellow
    Write-Host "  $CommandLine" -ForegroundColor Gray

    if ($DryRun) { return }

    & $Block
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[FAILED] $Title" -ForegroundColor Red
        exit $LASTEXITCODE
    }
}

Write-Host ""
Write-Host "TradingAgents-CN Acceptance Test Runner" -ForegroundColor Cyan
Write-Host "Version: v$Version" -ForegroundColor Cyan
Write-Host "Backend: $backendUrl" -ForegroundColor Gray
Write-Host "Frontend: $frontendUrl" -ForegroundColor Gray
Write-Host "IncludeETF: $IncludeETF" -ForegroundColor Gray
Write-Host ""

if ($Command -eq "api" -or $Command -eq "all") {
    $cmdText = "$pythonExe -m pytest tests/acceptance/ -v --tb=short $apiFilter"
    Invoke-Step "API Acceptance Tests" $cmdText {
        if ($IncludeETF) {
            & $pythonExe -m pytest tests/acceptance/ -v --tb=short
        } else {
            & $pythonExe -m pytest tests/acceptance/ -v --tb=short -k "not etf"
        }
    }
}

if ($Command -eq "e2e" -or $Command -eq "all") {
    $cmdText = "npx playwright test --reporter=list"
    Invoke-Step "E2E Acceptance Tests" $cmdText {
        & npx playwright test --reporter=list
    }
}

Write-Host ""
Write-Host "[OK] 验收测试执行完成" -ForegroundColor Green
