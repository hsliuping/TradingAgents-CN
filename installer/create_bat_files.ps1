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
echo   TradingAgents-CN Pro - 启动所有服务
echo ============================================================================
echo.

cd /d "%~dp0"

echo [1/3] 启动数据库服务...
call scripts\start_databases.bat
if errorlevel 1 (
    echo ERROR: 数据库启动失败
    pause
    exit /b 1
)

echo.
echo [2/3] 启动后端服务...
start "TradingAgents Backend" cmd /k "call scripts\start_backend.bat"

echo.
echo [3/3] 启动前端服务...
timeout /t 3 /nobreak >nul
start "TradingAgents Frontend" cmd /k "call scripts\start_frontend.bat"

echo.
echo ============================================================================
echo   所有服务已启动！
echo ============================================================================
echo.
echo   访问地址: http://localhost
echo   默认账号: admin / admin123
echo.
echo   按任意键打开浏览器...
pause >nul

start http://localhost

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

