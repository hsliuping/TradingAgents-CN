# TradingAgents-CN Web application startup script

Write-Host "🚀 Starting TradingAgents-CN Web application..." -ForegroundColor Green
Write-Host ""

# Activate virtual environment
& ".\env\Scripts\Activate.ps1"

# Check if the project is installed
try {
    python -c "import tradingagents" 2>$null
    if ($LASTEXITCODE -ne 0) {
        Write-Host "📦 Installing project into virtual environment..." -ForegroundColor Yellow
        pip install -e .
    }
} catch {
    Write-Host "📦 Installing project into virtual environment..." -ForegroundColor Yellow
    pip install -e .
}

# Start Streamlit application
python start_web.py

Write-Host "Press any key to exit..." -ForegroundColor Yellow
Read-Host
