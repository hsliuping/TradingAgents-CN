#!/bin/bash
# TradingAgents-CN Web application startup script

echo "🚀 Starting TradingAgents-CN Web application..."
echo

# Activate virtual environment
source env/bin/activate

# Check if the project is installed
if ! python -c "import tradingagents" 2>/dev/null; then
    echo "📦 Installing project into virtual environment..."
    pip install -e .
fi

# Start Streamlit application
python start_web.py

echo "Press any key to exit..."
read -n 1
