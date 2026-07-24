# Prototype v2 本地预览
$port = 8766
$dir = $PSScriptRoot
Set-Location $dir
Write-Host "TradingAgents v4.0 Prototype v2 -> http://127.0.0.1:$port/" -ForegroundColor Cyan
Write-Host "目录: $dir" -ForegroundColor DarkGray
python -m http.server $port
