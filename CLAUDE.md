# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Quick Commands

### Setup & Installation
```bash
# Install dependencies
pip install -r requirements.txt

# Setup databases (MongoDB + Redis)
docker-compose up -d
python scripts/setup_databases.py

# Configure API keys
cp .env.example .env
# Edit .env with your actual API keys
```

### Running the System
```bash
# Web interface (recommended)
python -m streamlit run web/app.py

# CLI interface
python -m cli.main

# Programmatic usage
python main.py

# Examples
python examples/dashscope/demo_dashscope_chinese.py
```

### Testing
```bash
# Run all tests
python -m pytest tests/

# Run specific tests
python tests/test_all_apis.py
python tests/integration/test_dashscope_integration.py
python tests/fast_tdx_test.py

# Debug/diagnostic tools
python tests/debug_imports.py
python tests/diagnose_gemini_25.py
```

## Architecture Overview

### Core Components
- **TradingAgentsGraph**: Main orchestrator class in `tradingagents/graph/trading_graph.py`
- **Multi-Agent System**: 4 analyst types + 2 researchers + trader + risk management + managers
- **Data Layer**: FinnHub, Yahoo Finance, Reddit, Google News with Redis/MongoDB caching
- **LLM Support**: OpenAI, Anthropic, Google AI, DashScope (阿里百炼)

### Key Directories
- `tradingagents/agents/`: All agent implementations (analysts, researchers, trader, risk)
- `tradingagents/graph/`: Core workflow logic (propagation, reflection, signal processing)
- `tradingagents/dataflows/`: Data sources, caching, and database management
- `web/`: Streamlit web interface
- `tests/`: Comprehensive test suite
- `examples/`: Usage examples and demos

### Agent Structure
- **Analysts**: fundamentals, market, news, social_media
- **Researchers**: bull_researcher, bear_researcher (structured debates)
- **Trader**: Makes final trading decisions
- **Risk Management**: aggressive, conservative, neutral debators
- **Managers**: research_manager, risk_manager (coordinate workflows)

## Configuration

### Essential API Keys (.env)
```bash
# Required
DASHSCOPE_API_KEY=your_dashscope_key  # 阿里百炼 (recommended for Chinese users)
FINNHUB_API_KEY=your_finnhub_key

# Optional but recommended
GOOGLE_API_KEY=your_google_key
OPENAI_API_KEY=your_openai_key
NEWSAPI_KEY=your_newsapi_key

# Database (if using Docker)
MONGODB_USERNAME=admin
MONGODB_PASSWORD=tradingagents123
REDIS_PASSWORD=tradingagents123
```

### Configuration Files
- `tradingagents/default_config.py`: Default settings
- `web/config/`: Web interface configurations
- `.env`: Environment variables and API keys

## Development Workflow

### 1. Basic Analysis
```python
from tradingagents.graph.trading_graph import TradingAgentsGraph
from tradingagents.default_config import DEFAULT_CONFIG

config = DEFAULT_CONFIG.copy()
config["llm_provider"] = "dashscope"
config["deep_think_llm"] = "qwen-plus"

ta = TradingAgentsGraph(debug=True, config=config)
state, decision = ta.propagate("AAPL", "2024-01-15")
print(f"Action: {decision['action']}, Confidence: {decision['confidence']}")
```

### 2. Custom Configuration
```python
config = {
    "llm_provider": "dashscope",
    "deep_think_llm": "qwen-plus",
    "quick_think_llm": "qwen-turbo",
    "max_debate_rounds": 2,
    "online_tools": True,
    "selected_analysts": ["market", "fundamentals", "news"]
}
```

### 3. Web Interface Features
- **Research Depth**: 5 levels (1-5, from 2-4min to 15-25min)
- **Stock Support**: AAPL, TSLA, NVDA (US); 000001, 600519 (A-share)
- **Real-time Data**: TDX integration for A-shares
- **Chinese Interface**: Full Chinese localization

## Testing Strategy

### Test Categories
- **API Tests**: `test_all_apis.py`, `test_correct_apis.py`
- **Integration Tests**: `test_dashscope_integration.py`, `test_tdx_integration.py`
- **Performance Tests**: `test_redis_performance.py`
- **Chinese Output**: `test_chinese_output.py`
- **Web Interface**: `test_web_interface.py`

### Diagnostic Tools
- `debug_imports.py`: Import issues
- `diagnose_gemini_25.py`: Gemini model issues
- `check_gemini_models.py`: Available models

## Data Sources

### US Markets
- FinnHub API: Real-time stock data
- Yahoo Finance: Historical data
- Google News: News sentiment
- Reddit API: Social sentiment

### China Markets
- TDX (通达信): Real-time A-share data
- Tushare: Chinese financial data
- AkShare: Alternative Chinese data

### Caching Strategy
- **Redis**: In-memory caching (1-24h TTL based on data type)
- **MongoDB**: Persistent storage for analysis results
- **File Cache**: Local JSON files as fallback

## Common Issues & Solutions

### API Key Issues
- Check `.env` file format and key validity
- Verify network connectivity to API endpoints
- Use diagnostic tools to test individual APIs

### Database Connection
- Ensure Docker services are running: `docker-compose ps`
- Check MongoDB/Redis connection strings in config
- Verify firewall settings for ports 27018, 6380

### Memory/Performance
- Reduce `max_debate_rounds` for faster execution
- Use `gpt-4o-mini` instead of `gpt-4o` for cost optimization
- Enable caching to reduce API calls

## Cost Optimization
- **Economic Mode**: gpt-4o-mini (~$0.01-0.05/analysis)
- **Standard Mode**: gpt-4o (~$0.05-0.15/analysis)
- **Premium Mode**: gpt-4o + multiple rounds (~$0.10-0.30/analysis)

## Security Notes
- Never commit `.env` files with real API keys
- Use `.env.example` as template
- Rotate API keys regularly
- Monitor usage and costs via provider dashboards