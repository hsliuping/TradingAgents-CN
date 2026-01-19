@echo off
REM TradingAgents-CN 开发环境启动脚本（Windows）
REM 同时启动后端和 Worker

echo 🚀 TradingAgents-CN 开发环境启动器
echo ============================================================
echo 将同时启动：
echo   1. FastAPI 后端服务
echo   2. Worker 队列消费者
echo ============================================================
echo.

REM 检查Python是否安装
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ Python is not installed or not in PATH
    pause
    exit /b 1
)

REM 启动后端和Worker（使用Python脚本）
python scripts\start_dev.py

if errorlevel 1 (
    echo ❌ 启动失败
    pause
    exit /b 1
)

pause
