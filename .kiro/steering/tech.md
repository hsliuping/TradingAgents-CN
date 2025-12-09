# TradingAgents-CN Tech Stack

## Backend (FastAPI)
- **Framework**: FastAPI + Uvicorn
- **Language**: Python 3.10+
- **Package Manager**: pip/uv (pyproject.toml)
- **Database**: MongoDB (motor async driver) + Redis
- **Task Scheduling**: APScheduler
- **Authentication**: JWT + bcrypt

## Frontend (Vue 3)
- **Framework**: Vue 3 + Vite
- **UI Library**: Element Plus
- **State Management**: Pinia
- **Language**: TypeScript
- **Package Manager**: yarn/npm

## AI/LLM Stack
- **Orchestration**: LangChain + LangGraph
- **Vector Store**: ChromaDB
- **Supported Providers**: OpenAI, Anthropic, Google, DeepSeek, DashScope (Alibaba), SiliconFlow, OpenRouter, Zhipu, Qianfan

## Data Sources
- **China A-shares**: Tushare, AKShare, BaoStock
- **US Stocks**: FinnHub, yfinance
- **News**: Various adapters via AKShare

## Common Commands

### Backend Development
```bash
# Install dependencies
pip install -e .
# or with uv
uv pip install -e .

# Run FastAPI backend
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Run worker process
python -m app.worker
```

### Frontend Development
```bash
cd frontend

# Install dependencies
yarn install

# Development server
yarn dev

# Build for production
yarn build

# Type check
yarn type-check

# Lint
yarn lint
```

### Docker Deployment
```bash
cd docker

# Start all services
docker-compose up -d

# With management tools (Redis Commander, Mongo Express)
docker-compose --profile management up -d
```

## Environment Configuration
- Copy `.env.example` to `.env` and configure API keys
- Required: MongoDB, Redis, JWT_SECRET, at least one LLM API key
- See `.env.example` for detailed configuration options
