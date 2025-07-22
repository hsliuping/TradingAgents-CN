@echo off
echo 🚀 Starting TradingAgents-CN Web application...
echo.

REM Activate virtual environment
call env\Scripts\activate.bat

REM Check if the project is installed
python -c "import tradingagents" 2>nul
if errorlevel 1 (
    echo 📦 Installing project into virtual environment...
    pip install -e .
)

REM Start Streamlit application
python start_web.py

echo Press any key to exit...
pause
