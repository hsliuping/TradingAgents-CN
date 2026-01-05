# ============================================================================
# Test UTF-8 Encoding
# ============================================================================
# 测试UTF-8编码设置是否正确
# ============================================================================

# 设置控制台和文件编码为UTF-8
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
[Console]::InputEncoding = [System.Text.Encoding]::UTF8
$PSDefaultParameterValues['*:Encoding'] = 'utf8'
$OutputEncoding = [System.Text.Encoding]::UTF8

$ErrorActionPreference = "Stop"

Write-Host "============================================================================" -ForegroundColor Cyan
Write-Host "  UTF-8 Encoding Test" -ForegroundColor Cyan
Write-Host "============================================================================" -ForegroundColor Cyan
Write-Host ""

# ============================================================================
# Test 1: Console Output
# ============================================================================

Write-Host "Test 1: Console Output" -ForegroundColor Yellow
Write-Host "----------------------------------------" -ForegroundColor Gray
Write-Host ""

$testStrings = @(
    "简体中文: 你好，世界！",
    "繁體中文: 你好，世界！",
    "日本語: こんにちは、世界！",
    "한국어: 안녕하세요, 세계!",
    "Emoji: 🎉 🚀 ✅ ❌ 💡",
    "Mixed: Hello 世界 🌍"
)

foreach ($str in $testStrings) {
    Write-Host "  $str" -ForegroundColor Green
}

Write-Host ""
Write-Host "✅ 如果上面的文字显示正常，控制台输出编码正确" -ForegroundColor Green
Write-Host ""

# ============================================================================
# Test 2: File Write/Read
# ============================================================================

Write-Host "Test 2: File Write/Read" -ForegroundColor Yellow
Write-Host "----------------------------------------" -ForegroundColor Gray
Write-Host ""

$tempFile = Join-Path $env:TEMP "utf8_test_$(Get-Date -Format 'yyyyMMddHHmmss').txt"

try {
    # Write test
    $testContent = @"
UTF-8 编码测试文件
==================

简体中文: 你好，世界！
繁體中文: 你好，世界！
日本語: こんにちは、世界！
한국어: 안녕하세요, 세계!
Emoji: 🎉 🚀 ✅ ❌ 💡

测试时间: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')
"@

    Write-Host "  Writing to: $tempFile" -ForegroundColor Cyan
    Set-Content -Path $tempFile -Value $testContent -Encoding UTF8
    Write-Host "  ✅ Write successful" -ForegroundColor Green
    Write-Host ""

    # Read test
    Write-Host "  Reading from: $tempFile" -ForegroundColor Cyan
    $readContent = Get-Content -Path $tempFile -Encoding UTF8 -Raw
    Write-Host "  ✅ Read successful" -ForegroundColor Green
    Write-Host ""

    # Verify
    Write-Host "  File content:" -ForegroundColor Cyan
    Write-Host "  ----------------------------------------" -ForegroundColor Gray
    $readContent -split "`n" | ForEach-Object {
        Write-Host "  $_" -ForegroundColor White
    }
    Write-Host "  ----------------------------------------" -ForegroundColor Gray
    Write-Host ""

    if ($testContent -eq $readContent) {
        Write-Host "✅ 文件读写编码正确（内容完全匹配）" -ForegroundColor Green
    } else {
        Write-Host "❌ 文件读写编码可能有问题（内容不匹配）" -ForegroundColor Red
    }

} catch {
    Write-Host "❌ 文件操作失败: $($_.Exception.Message)" -ForegroundColor Red
} finally {
    # Cleanup
    if (Test-Path $tempFile) {
        Remove-Item -Path $tempFile -Force
        Write-Host "  🗑️  Cleaned up temp file" -ForegroundColor Gray
    }
}

Write-Host ""

# ============================================================================
# Test 3: Encoding Settings
# ============================================================================

Write-Host "Test 3: Encoding Settings" -ForegroundColor Yellow
Write-Host "----------------------------------------" -ForegroundColor Gray
Write-Host ""

Write-Host "  Current Encoding Settings:" -ForegroundColor Cyan
Write-Host "  ----------------------------------------" -ForegroundColor Gray
Write-Host "  Console.OutputEncoding:  $([Console]::OutputEncoding.EncodingName)" -ForegroundColor White
Write-Host "  Console.InputEncoding:   $([Console]::InputEncoding.EncodingName)" -ForegroundColor White
Write-Host "  OutputEncoding:          $($OutputEncoding.EncodingName)" -ForegroundColor White
Write-Host "  Default File Encoding:   $($PSDefaultParameterValues['*:Encoding'])" -ForegroundColor White
Write-Host "  ----------------------------------------" -ForegroundColor Gray
Write-Host ""

$allUtf8 = $true

if ([Console]::OutputEncoding.CodePage -ne 65001) {
    Write-Host "  ❌ Console.OutputEncoding is not UTF-8" -ForegroundColor Red
    $allUtf8 = $false
}

if ([Console]::InputEncoding.CodePage -ne 65001) {
    Write-Host "  ❌ Console.InputEncoding is not UTF-8" -ForegroundColor Red
    $allUtf8 = $false
}

if ($OutputEncoding.CodePage -ne 65001) {
    Write-Host "  ❌ OutputEncoding is not UTF-8" -ForegroundColor Red
    $allUtf8 = $false
}

if ($PSDefaultParameterValues['*:Encoding'] -ne 'utf8') {
    Write-Host "  ❌ Default file encoding is not UTF-8" -ForegroundColor Red
    $allUtf8 = $false
}

if ($allUtf8) {
    Write-Host "✅ 所有编码设置都正确配置为UTF-8" -ForegroundColor Green
} else {
    Write-Host "❌ 部分编码设置不正确" -ForegroundColor Red
}

Write-Host ""

# ============================================================================
# Summary
# ============================================================================

Write-Host "============================================================================" -ForegroundColor Cyan
Write-Host "  Test Summary" -ForegroundColor Cyan
Write-Host "============================================================================" -ForegroundColor Cyan
Write-Host ""

Write-Host "✅ 测试完成！" -ForegroundColor Green
Write-Host ""
Write-Host "如果所有测试都通过，说明UTF-8编码设置正确。" -ForegroundColor White
Write-Host "如果有任何测试失败，请检查脚本开头的编码设置。" -ForegroundColor White
Write-Host ""

