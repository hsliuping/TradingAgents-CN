# ============================================================================
# Create BAT files for installer
# ============================================================================
# 为安装程序创建.bat启动文件
# ============================================================================

# UTF-8编码设置
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
[Console]::InputEncoding = [System.Text.Encoding]::UTF8
$PSDefaultParameterValues['*:Encoding'] = 'utf8'
$OutputEncoding = [System.Text.Encoding]::UTF8

$root = Split-Path -Parent $PSScriptRoot
$portableDir = Join-Path $root "release\TradingAgentsCN-portable"

Write-Host "Creating BAT files for installer..." -ForegroundColor Cyan
Write-Host ""

# ============================================================================
# start_all.bat
# ============================================================================

$startBat = @'
@echo off
chcp 65001 >nul
title TradingAgents-CN - 启动中...

echo ============================================================================
echo   TradingAgents-CN Pro - 便携版启动器
echo ============================================================================
echo.

cd /d "%~dp0"

echo 正在启动所有服务...
echo.
echo 提示: 本脚本会调用 PowerShell 脚本来启动服务
echo.

REM 调用 PowerShell 启动脚本
powershell.exe -ExecutionPolicy Bypass -File "%~dp0start_all.ps1"

if errorlevel 1 (
    echo.
    echo ============================================================================
    echo   启动失败
    echo ============================================================================
    echo.
    echo 请检查错误信息，或尝试直接运行 start_all.ps1
    echo.
    pause
    exit /b 1
)

echo.
echo ============================================================================
echo   所有服务已启动！
echo ============================================================================
echo.
echo   访问地址: http://localhost
echo   默认账号: admin / admin123
echo.
pause

exit
'@

$startBatPath = Join-Path $portableDir "start_all.bat"
$startBat | Out-File -FilePath $startBatPath -Encoding ASCII
Write-Host "  ✅ Created: start_all.bat" -ForegroundColor Green

# ============================================================================
# stop_all.bat
# ============================================================================

$stopBat = @'
@echo off
chcp 65001 >nul
title TradingAgents-CN - 停止中...

echo ============================================================================
echo   TradingAgents-CN Pro - 停止所有服务
echo ============================================================================
echo.

cd /d "%~dp0"

echo [1/2] 停止应用服务...
taskkill /FI "WINDOWTITLE eq TradingAgents*" /F >nul 2>&1

echo.
echo [2/2] 停止数据库服务...
call scripts\stop_databases.bat

echo.
echo ============================================================================
echo   所有服务已停止！
echo ============================================================================
echo.
pause
'@

$stopBatPath = Join-Path $portableDir "stop_all.bat"
$stopBat | Out-File -FilePath $stopBatPath -Encoding ASCII
Write-Host "  ✅ Created: stop_all.bat" -ForegroundColor Green

Write-Host ""
Write-Host "BAT files created successfully!" -ForegroundColor Green

