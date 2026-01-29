@echo off
chcp 65001 >nul
title MongoDB Database Tools 安装程序

echo ============================================================================
echo   MongoDB Database Tools 安装程序
echo ============================================================================
echo.

cd /d "%~dp0"

echo 正在启动 PowerShell 安装脚本...
echo.

powershell.exe -ExecutionPolicy Bypass -File "%~dp0install_mongodb_tools.ps1"

if errorlevel 1 (
    echo.
    echo ============================================================================
    echo   安装失败
    echo ============================================================================
    echo.
    pause
    exit /b 1
)

echo.
echo ============================================================================
echo   安装完成
echo ============================================================================
echo.
pause
