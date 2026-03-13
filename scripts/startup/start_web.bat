@echo off
chcp 65001 >nul
echo 启动 TradingAgents-CN Web 应用...
echo.

REM 激活虚拟环境
call env\Scripts\activate.bat

REM 检查项目是否已安装
python -c "import tradingagents" 2>nul
if errorlevel 1 (
    echo 📦 安装项目到虚拟环境...
    pip install -e .
)

REM 启动Streamlit应用
python start_web.py

pause
