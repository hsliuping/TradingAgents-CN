# ============================================================================
# Windows 10 兼容性修复脚本
# ============================================================================
# 解决 Win10 上安装后无法使用的问题：
# 1. PowerShell 执行策略（默认 Restricted 会阻止脚本运行）
# 2. 控制台字符集（GBK 导致中文乱码、脚本解析错误）
# 3. 验证环境
#
# 使用方法（以管理员身份运行）：
#   powershell -ExecutionPolicy Bypass -File scripts\setup\fix_win10_compatibility.ps1
# ============================================================================

$ErrorActionPreference = "Stop"

[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
[Console]::InputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8

Write-Host "============================================================================" -ForegroundColor Cyan
Write-Host "  TradingAgents-CN - Windows 10 兼容性修复" -ForegroundColor Cyan
Write-Host "============================================================================" -ForegroundColor Cyan
Write-Host ""

$fixed = $false

# 1. 检查并设置 PowerShell 执行策略
Write-Host "[1/3] 检查 PowerShell 执行策略..." -ForegroundColor Yellow
$policy = Get-ExecutionPolicy -Scope CurrentUser -ErrorAction SilentlyContinue
if ($policy -eq "Restricted" -or $policy -eq "AllSigned") {
    Write-Host "  当前策略: $policy (会阻止脚本运行)" -ForegroundColor Red
    try {
        Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser -Force
        Write-Host "  已设置为 RemoteSigned (当前用户)" -ForegroundColor Green
        $fixed = $true
    } catch {
        Write-Host "  设置失败: $_" -ForegroundColor Red
        Write-Host "  请以管理员身份运行此脚本" -ForegroundColor Yellow
    }
} else {
    Write-Host "  当前策略: $policy (OK)" -ForegroundColor Green
}
Write-Host ""

# 2. 检查控制台编码
Write-Host "[2/3] 检查控制台编码..." -ForegroundColor Yellow
$codePage = [Console]::OutputEncoding.CodePage
if ($codePage -eq 65001) {
    Write-Host "  编码: UTF-8 (65001) (OK)" -ForegroundColor Green
} else {
    Write-Host "  当前编码: $codePage (非 UTF-8，可能导致乱码)" -ForegroundColor Yellow
    Write-Host "  建议: 在运行 .bat 前会自动执行 chcp 65001" -ForegroundColor Gray
    Write-Host "  或手动执行: chcp 65001" -ForegroundColor Gray
}
Write-Host ""

# 3. 系统区域 UTF-8 选项（可选）
Write-Host "[3/3] 系统 UTF-8 支持..." -ForegroundColor Yellow
$buildNumber = (Get-ItemProperty "HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion" -ErrorAction SilentlyContinue).CurrentBuildNumber
if ($buildNumber -ge 18362) {
    Write-Host "  Windows 版本: Build $buildNumber (支持 UTF-8 区域)" -ForegroundColor Green
    Write-Host "  如需启用系统级 UTF-8，可运行: .\scripts\setup\enable_utf8_gui.ps1" -ForegroundColor Gray
} else {
    Write-Host "  Windows 版本: Build $buildNumber" -ForegroundColor Gray
    Write-Host "  建议升级到 Win10 1903+ 以获得更好的 UTF-8 支持" -ForegroundColor Yellow
}
Write-Host ""

Write-Host "============================================================================" -ForegroundColor Cyan
Write-Host "  修复完成" -ForegroundColor Cyan
Write-Host "============================================================================" -ForegroundColor Cyan
Write-Host ""
if ($fixed) {
    Write-Host "已修复执行策略。请重新运行启动脚本。" -ForegroundColor Green
} else {
    Write-Host "如仍有问题，请尝试：" -ForegroundColor Yellow
    Write-Host "  1. 以管理员身份运行启动脚本" -ForegroundColor White
    Write-Host "  2. 右键启动脚本 -> 使用 PowerShell 运行" -ForegroundColor White
    Write-Host "  3. 在 CMD 中先执行 chcp 65001，再运行 .bat" -ForegroundColor White
}
Write-Host ""
Write-Host "按任意键退出..." -ForegroundColor Gray
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
