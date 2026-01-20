# 测试 Start-Process 参数修复
# 验证 -WindowStyle 和 -NoNewWindow 不会同时使用

$ErrorActionPreference = "Stop"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "测试 Start-Process 参数修复" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

$root = Split-Path -Parent $PSScriptRoot

# 测试文件列表
$testFiles = @(
    "scripts\installer\start_all.ps1",
    "scripts\installer\start_services_clean.ps1"
)

$totalTests = 0
$passedTests = 0
$failedTests = 0

foreach ($file in $testFiles) {
    $filePath = Join-Path $root $file
    
    Write-Host "检查文件: $file" -ForegroundColor Yellow
    
    if (-not (Test-Path $filePath)) {
        Write-Host "  ❌ 文件不存在" -ForegroundColor Red
        $failedTests++
        $totalTests++
        continue
    }
    
    $content = Get-Content $filePath -Raw
    
    # 检查是否同时使用了 -WindowStyle 和 -NoNewWindow
    $lines = Get-Content $filePath
    $lineNumber = 0
    $hasIssue = $false
    
    for ($i = 0; $i -lt $lines.Count; $i++) {
        $line = $lines[$i]
        
        # 检查是否是 Start-Process 命令的开始
        if ($line -match 'Start-Process') {
            $lineNumber = $i + 1
            $commandBlock = $line
            
            # 收集多行命令（使用反引号续行）
            $j = $i + 1
            while ($j -lt $lines.Count -and $lines[$j - 1] -match '`\s*$') {
                $commandBlock += "`n" + $lines[$j]
                $j++
            }
            
            # 检查是否同时包含 -WindowStyle 和 -NoNewWindow
            $hasWindowStyle = $commandBlock -match '-WindowStyle'
            $hasNoNewWindow = $commandBlock -match '-NoNewWindow'
            
            if ($hasWindowStyle -and $hasNoNewWindow) {
                Write-Host "  ❌ 第 $lineNumber 行: 同时使用了 -WindowStyle 和 -NoNewWindow" -ForegroundColor Red
                Write-Host "     命令块:" -ForegroundColor Gray
                $commandBlock -split "`n" | ForEach-Object {
                    Write-Host "     $_" -ForegroundColor Gray
                }
                $hasIssue = $true
                $failedTests++
            }
            
            $totalTests++
        }
    }
    
    if (-not $hasIssue) {
        Write-Host "  ✅ 通过检查" -ForegroundColor Green
        $passedTests++
    }
    
    Write-Host ""
}

# 汇总结果
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "测试结果汇总" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "总测试数: $totalTests" -ForegroundColor White
Write-Host "通过: $passedTests" -ForegroundColor Green
Write-Host "失败: $failedTests" -ForegroundColor $(if ($failedTests -eq 0) { "Green" } else { "Red" })
Write-Host ""

if ($failedTests -eq 0) {
    Write-Host "🎉 所有测试通过！" -ForegroundColor Green
    exit 0
} else {
    Write-Host "⚠️ 有 $failedTests 个测试失败" -ForegroundColor Red
    exit 1
}

