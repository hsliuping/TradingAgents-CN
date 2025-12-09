# TradingAgents-CN Project Structure

## Root Layout
```
├── app/                    # FastAPI backend (proprietary)
├── frontend/               # Vue 3 frontend (proprietary)
├── tradingagents/          # Core multi-agent library (Apache 2.0)
├── config/                 # Configuration files (JSON/TOML)
├── docker/                 # Docker deployment files
├── data/                   # Data storage (analysis results, exports)
├── runtime/                # Runtime files (logs, cache)
└── tests/                  # Test files
```

## Backend (`app/`)
```
app/
├── main.py                 # FastAPI application entry point
├── worker.py               # Background worker process
├── core/                   # Core utilities (config, database, logging)
├── models/                 # Pydantic/MongoDB models
├── routers/                # API route handlers
├── services/               # Business logic services
├── middleware/             # Request middleware
├── utils/                  # Utility functions
└── worker/                 # Sync service workers (Tushare, AKShare, etc.)
```

## Frontend (`frontend/`)
```
frontend/
├── src/
│   ├── api/                # API client modules
│   ├── components/         # Reusable Vue components
│   ├── views/              # Page components
│   ├── stores/             # Pinia stores
│   ├── router/             # Vue Router config
│   ├── types/              # TypeScript type definitions
│   ├── utils/              # Utility functions
│   └── styles/             # SCSS styles
├── public/                 # Static assets
└── vite.config.ts          # Vite configuration
```

## Core Library (`tradingagents/`)
```
tradingagents/
├── agents/                 # Agent definitions
│   ├── analysts/           # Analyst agents (market, fundamentals, etc.)
│   ├── managers/           # Manager agents (research, risk)
│   ├── researchers/        # Bull/Bear researcher agents
│   ├── risk_mgmt/          # Risk debate agents
│   ├── trader/             # Trader agent
│   └── utils/              # Agent utilities and states
├── graph/                  # LangGraph workflow
│   ├── trading_graph.py    # Main graph orchestration
│   ├── setup.py            # Graph setup
│   ├── conditional_logic.py # Flow control
│   └── propagation.py      # State propagation
├── dataflows/              # Data retrieval and caching
│   ├── cache/              # Caching strategies
│   ├── providers/          # Data source providers
│   └── interface.py        # Unified data interface
├── llm_adapters/           # LLM provider adapters
├── config/                 # Configuration management
├── tools/                  # Agent tools (MCP, local)
└── utils/                  # Shared utilities
```

## Key Configuration Files
- `.env` - Environment variables (API keys, database config)
- `config/settings.json` - Application settings
- `config/models.json` - LLM model configurations
- `config/logging.toml` - Logging configuration
- `pyproject.toml` - Python dependencies
- `frontend/package.json` - Frontend dependencies
