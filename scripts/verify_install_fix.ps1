# 验证安装目录中的脚本是否已修复

param(
    [string]$InstallDir = "C:\TradingAgentsCN111f"
)

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "验证安装目录脚本修复" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "安装目录: $InstallDir" -ForegroundColor Yellow
Write-Host ""

if (-not (Test-Path $InstallDir)) {
    Write-Host "❌ 安装目录不存在: $InstallDir" -ForegroundColor Red
    exit 1
}

$scriptsToCheck = @(
    "start_all.ps1",
    "start_services_clean.ps1"
)

$allPassed = $true

foreach ($script in $scriptsToCheck) {
    $scriptPath = Join-Path $InstallDir $script
    
    Write-Host "检查: $script" -ForegroundColor Yellow
    
    if (-not (Test-Path $scriptPath)) {
        Write-Host "  ❌ 文件不存在" -ForegroundColor Red
        $allPassed = $false
        continue
    }
    
    $content = Get-Content $scriptPath -Raw
    
    # 检查是否同时包含 -WindowStyle 和 -NoNewWindow
    $hasConflict = $false
    $lines = Get-Content $scriptPath
    
    for ($i = 0; $i -lt $lines.Count; $i++) {
        if ($lines[$i] -match 'Start-Process') {
            # 收集完整的命令块
            $commandBlock = $lines[$i]
            $j = $i + 1
            while ($j -lt $lines.Count -and $lines[$j - 1] -match '`\s*$') {
                $commandBlock += "`n" + $lines[$j]
                $j++
            }
            
            # 检查冲突
            if ($commandBlock -match '-WindowStyle' -and $commandBlock -match '-NoNewWindow') {
                Write-Host "  ❌ 第 $($i + 1) 行发现参数冲突" -ForegroundColor Red
                $hasConflict = $true
                $allPassed = $false
            }
        }
    }
    
    if (-not $hasConflict) {
        Write-Host "  ✅ 无参数冲突" -ForegroundColor Green
    }
    
    Write-Host ""
}

Write-Host "========================================" -ForegroundColor Cyan
if ($allPassed) {
    Write-Host "✅ 所有检查通过！可以尝试启动服务" -ForegroundColor Green
    Write-Host ""
    Write-Host "下一步:" -ForegroundColor Yellow
    Write-Host "  cd $InstallDir" -ForegroundColor Gray
    Write-Host "  .\start_all.ps1" -ForegroundColor Gray
} else {
    Write-Host "❌ 发现问题，请检查上述错误" -ForegroundColor Red
}
Write-Host "========================================" -ForegroundColor Cyan

