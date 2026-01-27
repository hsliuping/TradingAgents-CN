# 激活虚拟环境并运行脚本

param(
    [Parameter(Mandatory=$true)]
    [string]$ScriptPath
)

$venvPath = ".\venv\Scripts\Activate.ps1"
if (-not (Test-Path $venvPath)) {
    $venvPath = ".\env\Scripts\Activate.ps1"
}

if (Test-Path $venvPath) {
    Write-Host "激活虚拟环境: $venvPath"
    & $venvPath
    
    Write-Host "运行脚本: $ScriptPath"
    python $ScriptPath
} else {
    Write-Host "错误: 找不到虚拟环境" -ForegroundColor Red
    exit 1
}

