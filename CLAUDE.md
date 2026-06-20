# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**TradingAgents-CN** is a multi-agent, LLM-powered stock analysis system for Chinese markets (A-shares, HK, US stocks). It is a Chinese-localized fork of TauricResearch/TradingAgents, extended with a FastAPI backend, Vue 3 frontend, and comprehensive data source integrations.

**Version**: v1.0.1 (stable). License: Apache 2.0 for `tradingagents/` and most code; `app/` and `frontend/` are proprietary and require separate commercial authorization.

## Architecture

The codebase has three major components:

### 1. Core Analysis Engine (`tradingagents/`)

The multi-agent analysis engine built on **LangGraph**:

- **`tradingagents/agents/`** — Agent definitions using lazy-loading `__getattr__` pattern in `__init__.py`. Key agents:
  - Analysts: `market_analyst`, `fundamentals_analyst`, `news_analyst`, `social_media_analyst`, `china_market`
  - Researchers: `bull_researcher`, `bear_researcher` + `research_manager`
  - Risk management: `risky_debator`, `safe_debator`, `neutral_debator` + `risk_manager`
  - Trader: execution agent
- **`tradingagents/graph/`** — LangGraph workflow orchestration:
  - `trading_graph.py` — Main orchestrator (~55KB), creates the state graph, wires agents/nodes/edges
  - `conditional_logic.py` — Controls graph flow (debate continuation, tool-call loop protection)
  - `setup.py`, `propagation.py`, `reflection.py`, `signal_processing.py` — Graph building blocks
- **`tradingagents/dataflows/`** — Unified data source abstraction (~112KB `data_source_manager.py`):
  - `providers/china/` — AKShare, Tushare, BaoStock implementations
  - `providers/hk/`, `providers/us/` — HK and US stock data
  - `technical/`, `news/`, `cache/` — Supporting modules
- **`tradingagents/llm_clients/`** & **`tradingagents/llm_adapters/`** — Multi-provider LLM abstraction (OpenAI, Google, Anthropic, DashScope/Qwen, DeepSeek, SiliconFlow, etc.)
- **`tradingagents/tools/`** — Analysis tools and news tools
- **`tradingagents/utils/`** — Logging, utilities, shared helpers

### 2. FastAPI Backend (`app/`)

RESTful API server with 37+ routers and 40+ services:

- **`app/main.py`** — Entry point, lifespan management, scheduler setup
- **`app/core/`** — Config (`settings.py`), database connections, logging
- **`app/routers/`** — API endpoints: auth, analysis, screening, queue, SSE, favorites, config, reports, paper trading, scheduler, stock data, notifications, WebSocket, logs, cache
- **`app/services/`** — Business logic: analysis, screening, data sync (Tushare/AKShare/BaoStock), quotes ingestion, progress tracking, WebSocket management, favorites, notifications
- **`app/worker/`** — Background data sync workers for each data source
- **`app/middleware/`** — CORS, operation logging, request ID, trusted host
- **`app/models/`**, **`app/schemas/`** — MongoDB models and Pydantic schemas

### 3. Vue 3 Frontend (`frontend/`)

Vue 3 + TypeScript + Vite + Element Plus SPA:

- **`frontend/src/views/`** — Page components
- **`frontend/src/components/`** — Reusable components
- **`frontend/src/api/`** — Axios API client modules
- **`frontend/src/stores/`** — Pinia state management
- **`frontend/src/router/`** — Vue Router configuration

### Other directories

- **`web/`** — Legacy Streamlit interface (still functional)
- **`cli/`** — CLI for interactive analysis and data initialization
- **`config/`** — `settings.json`, `models.json`, `pricing.json`, `logging.toml`
- **`scripts/`** — 200+ ops/debug/test/migration scripts
- **`tests/`** — Test suite (unit, integration, system tests)
- **`docker/`**, **`nginx/`** — Deployment configs

## Development Commands

### Backend

```bash
# Install dependencies
pip install -e .
# Or faster with uv:
uv pip install -e .

# Start backend server
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# Or use the app module directly
python -m app

# Run CLI interactive analysis
python -m cli.main

# Initialize stock data
python -m cli.main init

# Test configuration
python -m cli.main test

# Quick analysis (direct graph execution)
python main.py

# Run legacy Streamlit interface
python -m streamlit run web/app.py
```

### Frontend

```bash
cd frontend

# Install dependencies
npm install

# Dev server with hot reload
npm run dev

# Build for production
npm run build

# Type check
npm run type-check

# Lint
npm run lint

# Format
npm run format
```

### Docker

```bash
# Start full stack (backend + frontend + MongoDB + Redis)
docker-compose up -d

# Services: Backend :8000, Frontend :3000, MongoDB :27017, Redis :6379
```

### Tests

```bash
# Run tests with pytest (tests/ directory contains conftest.py for path setup)
python -m pytest tests/ -v

# Run a single test file
python -m pytest tests/dataflows/test_realtime_metrics.py -v

# Run tests with output
python -m pytest tests/ -v -s
```

## Key Configuration

- **`.env`** — Runtime environment variables: MongoDB/Redis connection, JWT/CSRF secrets, API keys (DeepSeek, DashScope, Tushare, etc.), `DEFAULT_CHINA_DATA_SOURCE`, debug mode
- **`config/settings.json`** — Active system settings: LLM provider, models, debate rounds, cache settings
- **`config/models.json`** — Model catalog
- **`config/pricing.json`** — LLM pricing data
- **`pyproject.toml`** — Python package definition and dependencies

## Git 提交和 PR 创建

**永远不要手动执行 git commit/push 命令**，使用以下脚本：

```bash
# 提交所有变更并创建 PR
./scripts/commit_and_push.sh "fix: 简要描述修改内容"

# 或指定不同的 PR 标题
./scripts/commit_and_push.sh "fix: commit message" "feat: 不同的 PR title"
```

脚本自动处理：
- 自动配置 git 身份（xiaodutou / xiaodutou@users.noreply.github.com）
- 使用 `gh auth git-credential` 进行 GitHub 认证推送
- 自动 `git pull --rebase` 同步远程变更
- 推送到 fork 仓库（xiaodutou/TradingAgents-CN-xdt）
- 自动向上游仓库（hsliuping/TradingAgents-CN）创建 PR

### 手动 Git 配置（仅首次需要）

如果脚本报错 "Please tell me who you are"，运行：
```bash
git config user.name "xiaodutou"
git config user.email "xiaodutou@users.noreply.github.com"
```

## Important Patterns

- **Lazy agent loading**: `tradingagents/agents/__init__.py` uses `__getattr__` to lazily import agents, avoiding circular imports
- **Tool-call loop protection**: `conditional_logic.py` enforces `max_tool_calls=3` per agent to prevent infinite loops
- **Multi-source data**: AKShare (free/default), Tushare (professional, supports custom API), BaoStock for A-shares
- **On-demand + cache**: HK and US stocks use on-demand fetching with caching, not scheduled sync
- **MongoDB + Redis**: Dual storage — MongoDB for persistent data, Redis for caching and queue
