# TradingAgents-CN 项目架构文档 (v1.0.8)

> 本文档全面描述 TradingAgents-CN v1.0.8 版本的项目架构设计、数据流转和模块耦合情况。

## 目录

- [项目概述](#项目概述)
- [整体架构](#整体架构)
- [前端架构](#前端架构)
- [后端架构](#后端架构)
- [核心框架架构](#核心框架架构)
- [Rust 性能优化架构](#rust-性能优化架构)
- [数据存储架构](#数据存储架构)
- [部署架构](#部署架构)

---

## 项目概述

### 基本信息

| 项目属性 | 描述 |
|---------|------|
| **项目名称** | TradingAgents-CN (TradingAgents 中文增强版) |
| **当前版本** | v1.0.4 (Rust 性能优化版本) |
| **项目类型** | 多智能体AI股票分析平台 |
| **开源协议** | 混合许可证（Apache 2.0 + 商业专有） |
| **代码规模** | ~155MB，1056个Python文件，110个前端文件 |
| **文档数量** | 575个Markdown文件 |

### 核心特性

1. **多智能体协作**：7种角色智能体协同分析
2. **多市场支持**：A股、港股、美股
3. **多LLM集成**：OpenAI、Google、DeepSeek、阿里百炼、智谱AI
4. **实时推送**：SSE + WebSocket 双通道
5. **智能新闻分析**：AI标签、情感分析、热度评分
6. **批量分析队列**：多只股票同时分析
7. **Docker部署**：多架构支持（amd64/arm64）
8. **Rust性能优化**：4个核心计算模块 Rust 加速 ⭐ v1.0.4 新增

### v1.0.4 版本亮点

**Rust 性能优化模块**:
- `tacn_wordcloud` - 词云统计 (3.6x - 5.1x 性能提升)
- `tacn_indicators` - 技术指标计算 (2.5x - 9.7x 性能提升)
- `tacn_stockcode` - 股票代码标准化 (3x - 5x 性能提升)
- `tacn_financial` - 财务指标计算 (4x - 8x 性能提升)

**架构改进**:
- 分析引擎适配器模式（完全解耦）
- Rust 后端自动降级机制
- 性能监控中间件
- 模块化服务层重构

---

## 整体架构

### 系统分层架构

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         用户界面层 (User Interface)                      │
├─────────────────────────────────────────────────────────────────────────┤
│  Vue3 SPA (专有)     │  Streamlit Web (开源)  │  CLI (开源)              │
│  ┌─────────────────┐ │  ┌──────────────────┐ │  ┌──────────────────┐   │
│  │  仪表盘         │ │  │  分析表单        │ │  │  命令行界面      │   │
│  │  股票分析       │ │  │  结果展示        │ │  │  配置管理        │   │
│  │  市场新闻       │ │  │  配置管理        │ │  │                   │   │
│  │  系统设置       │ │  │                   │ │  │                   │   │
│  └─────────────────┘ │  └──────────────────┘ │  └──────────────────┘   │
└─────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                           API网关层 (API Gateway)                         │
├─────────────────────────────────────────────────────────────────────────┤
│                        FastAPI (专有)                                    │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │  路由层 (routers/) - 37个路由模块                                │  │
│  │  • auth_db      • analysis       • stocks         • market_news  │  │
│  │  • screening    • queue          • sse            • websocket    │  │
│  │  • config       • reports        • favorites      • scheduler    │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │  中间件层 (middleware/)                                          │  │
│  │  • RequestIDMiddleware     (请求追踪)                           │  │
│  │  • CORSMiddleware          (跨域处理)                           │  │
│  │  • TrustedHostMiddleware  (主机白名单)                         │  │
│  │  • OperationLogMiddleware  (操作日志)                          │  │
│  │  • PerformanceMonitorMiddleware  (性能监控) ⭐ v1.0.4 新增      │  │
│  └──────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                        业务逻辑层 (Business Logic)                        │
├─────────────────────────────────────────────────────────────────────────┤
│                         services/ (服务层)                                │
│  ┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐           │
│  │ 认证服务        │ │ 分析服务        │ │ 配置服务        │           │
│  │ 队列服务        │ │ 报告服务        │ │ 通知服务        │           │
│  │ 数据同步服务    │ │ 新闻服务        │ │ 定时任务服务    │           │
│  │ 多源同步服务    │ │ 缓存服务        │ │ 模拟交易服务    │           │
│  └─────────────────┘ └─────────────────┘ └─────────────────┘           │
│                                                                          │
│  ┌─────────────────────────────────────────────────────────────────┐     │
│  │  分析引擎适配器模式 ⭐ v1.0.3 新增                            │     │
│  │  • AnalysisEngineAdapter (抽象基类)                          │     │
│  │  • TradingAgentsAdapter (实现类)                              │     │
│  │  • AnalysisEngineManager (引擎管理器)                         │     │
│  └─────────────────────────────────────────────────────────────────┘     │
└─────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                       Rust 优化层 ⭐ v1.0.4 新增                          │
├─────────────────────────────────────────────────────────────────────────┤
│                         app/utils/rust_backend.py                       │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │  Rust 后端适配器 (自动加载 + 降级逻辑)                          │  │
│  │  • tacn_wordcloud    → 词云统计 (10倍加速)                      │  │
│  │  • tacn_indicators   → 技术指标 (15倍加速)                      │  │
│  │  • tacn_stockcode    → 代码标准化 (8倍加速)                      │  │
│  │  • tacn_financial    → 财务计算 (12倍加速)                      │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │  性能监控                                                        │  │
│  │  • rust_calls / python_calls / errors                          │  │
│  │  • get_module_stats() - 统计查询                                │  │
│  └──────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                        核心框架层 (Core Framework)                         │
├─────────────────────────────────────────────────────────────────────────┤
│                    tradingagents/ (开源核心)                              │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │  图编排 (graph/)                                                │  │
│  │  • trading_graph.py  • propagation    • reflection             │  │
│  │  • conditional_logic • signal_processing                       │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │  智能体 (agents/)                                               │  │
│  │  分析师: market, fundamentals, news, china_market, social_media  │  │
│  │  研究员: bull_researcher, bear_researcher                       │  │
│  │  交易员: trader                                                │  │
│  │  风险管理: aggressive/conservative/neutral_debator             │  │
│  │  管理者: research_manager, risk_manager                        │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │  LLM适配器 (llm_adapters/)                                      │  │
│  │  • dashscope_adapter  • google_adapter  • deepseek_adapter     │  │
│  └──────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                         数据流层 (Data Flow)                              │
├─────────────────────────────────────────────────────────────────────────┤
│                    tradingagents/dataflows/                              │
│  ┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐           │
│  │ 数据源提供商    │ │ 缓存系统        │ │ 技术指标        │           │
│  │ • A股数据源     │ │ • MongoDB缓存   │ │ • TA-Lib        │           │
│  │ • 港股数据源    │ │ • Redis缓存     │ │ • Rust加速 ⭐   │           │
│  │ • 美股数据源    │ │ • 文件缓存      │ │                 │           │
│  └─────────────────┘ └─────────────────┘ └─────────────────┘           │
└─────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                        外部服务层 (External Services)                     │
├─────────────────────────────────────────────────────────────────────────┤
│  ┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐           │
│  │ LLM提供商       │ │ 数据源提供商    │ │ 第三方服务      │           │
│  │ • OpenAI        │ │ • AKShare       │ │ • MongoDB       │           │
│  │ • Google AI     │ │ • Tushare       │ │ • Redis         │           │
│  │ • DeepSeek      │ │ • BaoStock      │ │ • FinnHub       │           │
│  │ • 阿里百炼      │ │ • yFinance      │ │ • yFinance      │           │
│  │ • 智谱AI        │ │                 │ │                 │           │
│  └─────────────────┘ └─────────────────┘ └─────────────────┘           │
└─────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                        数据存储层 (Data Storage)                          │
├─────────────────────────────────────────────────────────────────────────┤
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │  MongoDB (主数据库)                                             │  │
│  │  • users               • analysis_records                      │  │
│  │  • analysis_batches    • analysis_tasks                       │  │
│  │  • stock_basic_info    • stock_quotes                        │  │
│  │  • market_news         • market_news_enhanced                │  │
│  │  • stock_financial_data • wordcloud_cache                      │  │
│  │  • llm_configs         • data_source_configs                 │  │
│  │  • system_config       • operation_logs                      │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │  Redis (缓存/队列)                                              │  │
│  │  • 分析队列      • 会话存储       • 限流计数                   │  │
│  │  • 进度缓存      • WebSocket连接                              │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │  文件系统 (File System)                                         │  │
│  │  • data/cache/       • data/analysis_results/                  │  │
│  │  • data/backups/     • logs/                                  │  │
│  └──────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 前端架构

### 技术栈

```typescript
Vue 3 生态系统
├── Vue 3.4.0+ (核心框架)
├── TypeScript 5.3+ (类型系统)
├── Vite 5.0+ (构建工具)
├── Pinia 2.1+ (状态管理)
├── Vue Router 4.2+ (路由管理)
├── Element Plus 2.4+ (UI组件库)
├── ECharts 5.4+ (图表库)
├── Axios (HTTP客户端)
└── @element-plus/icons-vue (图标库)
```

### 目录结构

```
frontend/
├── public/                    # 静态资源
├── src/
│   ├── api/                   # API客户端 (20+模块)
│   │   ├── analysis.ts       # 分析相关API
│   │   ├── auth.ts           # 认证API
│   │   ├── stocks.ts         # 股票API
│   │   ├── news.ts           # 新闻API
│   │   ├── config.ts         # 配置API
│   │   ├── sse.ts            # SSE推送
│   │   ├── websocket.ts      # WebSocket连接
│   │   └── apiCache.ts       # API缓存 ⭐ v1.0.3 新增
│   ├── assets/               # 资源文件
│   │   ├── styles/           # 全局样式
│   │   └── images/           # 图片资源
│   ├── components/           # 通用组件
│   │   ├── Dashboard/        # 仪表盘组件
│   │   ├── Analysis/         # 分析组件
│   │   ├── ConfigWizard.vue  # 配置向导
│   │   ├── ModelSelector.vue # 模型选择器
│   │   ├── NewsCard.vue      # 新闻卡片
│   │   └── WordCloud.vue     # 词云组件 (含版本水印 ⭐ v1.0.3)
│   ├── composables/          # 组合式函数
│   │   ├── useAuth.ts        # 认证逻辑
│   │   ├── useAnalysis.ts    # 分析逻辑
│   │   └── useSSE.ts         # SSE连接
│   ├── layouts/              # 布局组件
│   │   ├── MainLayout.vue    # 主布局
│   │   └── BlankLayout.vue   # 空白布局
│   ├── router/               # 路由配置
│   │   └── index.ts          # 路由定义
│   ├── stores/               # Pinia状态
│   │   ├── auth.ts           # 认证状态
│   │   ├── analysis.ts       # 分析状态
│   │   ├── config.ts         # 配置状态
│   │   └── user.ts           # 用户状态
│   ├── types/                # TypeScript类型
│   │   ├── analysis.ts       # 分析类型
│   │   ├── config.ts         # 配置类型
│   │   └── stock.ts          # 股票类型
│   ├── utils/                # 工具函数
│   │   ├── request.ts        # HTTP请求封装
│   │   ├── format.ts         # 格式化工具
│   │   └── validation.ts     # 验证工具
│   ├── views/                # 页面视图
│   │   ├── Dashboard/        # 仪表盘
│   │   ├── Analysis/         # 分析页面
│   │   ├── Stocks/           # 股票管理
│   │   ├── MarketNews/       # 市场新闻
│   │   ├── Settings/         # 系统设置
│   │   ├── Reports/          # 报告中心
│   │   └── PaperTrading/     # 模拟交易
│   ├── App.vue               # 根组件
│   └── main.ts               # 应用入口
├── index.html                # HTML模板
├── package.json              # 项目配置
├── tsconfig.json             # TypeScript配置
├── vite.config.ts            # Vite配置
└── env.d.ts                  # 环境变量类型
```

### 核心页面

| 页面 | 路由 | 功能描述 |
|-----|------|---------|
| **仪表盘** | `/dashboard` | 系统概览、快速入口、数据统计 |
| **股票分析** | `/analysis` | 单股/批量分析、分析历史 |
| **股票管理** | `/stocks` | 股票列表、自选股、筛选 |
| **市场新闻** | `/market-news` | 实时快讯、AI分析、词云 |
| **系统设置** | `/settings` | LLM配置、数据源、系统参数 |
| **报告中心** | `/reports` | 分析报告、导出管理 |
| **模拟交易** | `/paper-trading` | 虚拟交易、策略验证 |

---

## 后端架构

### 技术栈

```python
FastAPI 生态系统
├── FastAPI 0.104+ (Web框架)
├── Uvicorn 0.24+ (ASGI服务器)
├── Pydantic 2.0+ (数据验证)
├── Motor (MongoDB异步驱动)
├── Redis-py (Redis客户端)
├── PyJWT 2.0+ (JWT认证)
├── bcrypt 4.0+ (密码加密)
├── APScheduler 3.10+ (定时任务)
├── LangChain 0.3+ (LLM集成)
└── PyO3 0.23+ (Python-Rust绑定) ⭐ v1.0.4 新增
```

### 目录结构

```
app/
├── main.py                    # FastAPI应用入口
├── core/                      # 核心配置
│   ├── config.py             # Pydantic配置管理
│   ├── database.py           # MongoDB连接管理
│   ├── logging_config.py     # 日志配置
│   ├── redis_client.py       # Redis客户端
│   ├── startup_validator.py  # 启动验证
│   ├── config_bridge.py      # 配置桥接
│   └── config_cache.py       # 配置缓存 ⭐ v1.0.3 新增
├── middleware/                # 中间件
│   ├── error_handler.py      # 错误处理
│   ├── operation_log_middleware.py # 操作日志
│   ├── rate_limit.py         # 限流
│   ├── request_id.py         # 请求ID
│   └── performance_monitor.py # 性能监控 ⭐ v1.0.3 新增
├── models/                    # Pydantic数据模型
│   ├── user.py               # 用户模型
│   ├── analysis.py           # 分析模型
│   ├── stock_models.py       # 股票模型
│   ├── market_news.py        # 新闻模型
│   └── config_models.py      # 配置模型
├── routers/                   # API路由 (37个模块)
│   ├── auth_db.py            # 用户认证
│   ├── analysis.py           # 股票分析
│   ├── stocks.py             # 股票数据
│   ├── market_news.py        # 市场新闻
│   ├── screening.py          # 股票筛选
│   ├── queue.py              # 队列管理
│   ├── sse.py                # SSE推送
│   ├── websocket_notifications.py # WebSocket
│   ├── scheduler.py          # 定时任务
│   └── ...
├── services/                  # 业务逻辑层
│   ├── analysis_service.py   # 分析服务
│   ├── queue_service.py      # 队列服务
│   ├── config_service.py     # 配置服务
│   ├── news_database_service.py # 新闻数据库服务
│   ├── multi_source_basics_sync_service.py # 多源同步
│   ├── wordcloud_cache_service.py # 词云缓存服务
│   ├── pagination_service.py # 分页服务 ⭐ v1.0.3 新增
│   ├── database_index_service.py # 数据库索引服务 ⭐ v1.0.3 新增
│   └── analysis_engine/      # 分析引擎适配器 ⭐ v1.0.3 新增
│       ├── base.py           # 抽象基类
│       ├── trading_agents_adapter.py # 实现类
│       └── engine_manager.py # 引擎管理器
├── worker/                    # 后台任务
│   ├── tushare_sync_service.py
│   ├── akshare_sync_service.py
│   ├── baostock_sync_service.py
│   └── quotes_ingestion_service.py
└── utils/                     # 工具函数
    └── rust_backend.py       # Rust 后端适配器 ⭐ v1.0.4 新增
```

### API端点分类

#### 认证相关
- `POST /api/auth/register` - 用户注册
- `POST /api/auth/login` - 用户登录
- `POST /api/auth/logout` - 用户登出
- `GET /api/auth/me` - 获取当前用户

#### 分析相关
- `POST /api/analysis/analyze` - 单股分析
- `POST /api/analysis/batch` - 批量分析
- `GET /api/analysis/history` - 分析历史
- `GET /api/analysis/{id}` - 分析详情
- `GET /api/analysis/cost-estimate` - 成本估算

#### 股票相关
- `GET /api/stocks/list` - 股票列表
- `GET /api/stocks/{symbol}` - 股票详情
- `GET /api/stocks/{symbol}/quote` - 实时行情
- `GET /api/stocks/{symbol}/fundamentals` - 基础面数据
- `GET /api/stocks/{symbol}/kline` - K线数据
- `GET /api/stocks/{symbol}/news` - 股票新闻
- `GET /api/stocks/search` - 股票搜索
- `POST /api/favorites` - 添加自选股

#### 新闻相关
- `GET /api/market-news` - 市场快讯
- `GET /api/market-news/enhanced-wordcloud` - 词云数据
- `GET /api/market-news/analytics` - 新闻统计
- `POST /api/market-news/sync-to-enhanced-db` - 数据同步

#### 系统配置
- `GET /api/config/llm` - LLM配置
- `PUT /api/config/llm` - 更新LLM配置
- `GET /api/config/data-sources` - 数据源配置
- `GET /api/system/config` - 系统配置摘要
- `GET /api/system/rust-stats` - Rust 统计 ⭐ v1.0.4 新增

#### 实时推送
- `GET /api/stream/sse` - SSE连接
- `WS /api/ws/notifications` - WebSocket连接

---

## 核心框架架构

### TradingAgents 核心模块

```
tradingagents/
├── graph/                     # LangGraph工作流
│   ├── trading_graph.py      # 主图定义 (1397行)
│   ├── propagation.py        # 前向传播
│   ├── reflection.py         # 反思学习
│   ├── conditional_logic.py  # 条件逻辑
│   ├── signal_processing.py  # 信号处理
│   └── setup.py              # 图构建
├── agents/                    # 智能体定义
│   ├── analysts/             # 分析师团队
│   │   ├── market_analyst.py         # 市场分析师
│   │   ├── fundamentals_analyst.py   # 基本面分析师
│   │   ├── news_analyst.py           # 新闻分析师
│   │   ├── china_market_analyst.py   # A股分析师
│   │   └── social_media_analyst.py   # 社交媒体分析师
│   ├── researchers/           # 研究员团队
│   │   ├── bull_researcher.py        # 看涨研究员
│   │   └── bear_researcher.py        # 看跌研究员
│   ├── risk_mgmt/             # 风险管理
│   │   ├── aggressive_debator.py     # 激进辩论者
│   │   ├── conservative_debator.py   # 保守辩论者
│   │   └── neutral_debator.py        # 中立辩论者
│   ├── trader/               # 交易员
│   │   └── trader.py                 # 交易决策
│   ├── managers/             # 管理者
│   │   ├── research_manager.py       # 研究经理
│   │   └── risk_manager.py           # 风险经理
│   └── utils/                # 智能体工具
│       ├── agent_states.py   # 状态定义
│       ├── memory.py         # 记忆管理
│       └── agent_utils.py    # 工具函数
├── llm_adapters/             # LLM适配器
│   ├── dashscope_adapter.py  # 阿里百炼适配
│   ├── google_adapter.py     # Google Gemini适配
│   ├── deepseek_adapter.py   # DeepSeek适配
│   └── openai_compatible_base.py # OpenAI兼容基类
├── dataflows/                # 数据流处理
│   ├── providers/            # 数据源提供商
│   │   ├── china/           # A股数据源
│   │   ├── hk/              # 港股数据源
│   │   └── us/              # 美股数据源
│   ├── news/                 # 新闻数据处理
│   ├── technical/            # 技术指标计算
│   │   └── indicators.py    # 指标计算 (含 Rust 加速 ⭐)
│   ├── realtime_metrics.py   # 实时估值指标 (含 Rust 加速 ⭐)
│   └── cache/                # 缓存系统
│       ├── mongodb_cache_adapter.py
│       ├── file_cache.py
│       └── integrated.py
├── tools/                    # 工具函数
│   └── analysis/            # 分析工具
│       └── indicators.py    # 技术指标工具 (含 Rust 加速 ⭐)
├── config/                   # 配置管理
│   ├── config_manager.py    # 配置管理器
│   ├── providers_config.py  # LLM提供商配置
│   └── runtime_settings.py  # 运行时设置
├── models/                   # 数据模型
└── utils/                    # 工具函数
    └── logging_manager.py   # 日志管理
```

### 智能体工作流

```
用户请求
    │
    ▼
┌─────────────────────────────────────────┐
│         TradingAgentsGraph              │
│         (主控制器)                       │
└─────────────────────────────────────────┘
    │
    ├─────────────────────────────────────┤
    ▼                                     ▼
┌─────────────────┐             ┌─────────────────┐
│   GraphSetup    │             │  Conditional    │
│   (图构建)      │             │  Logic          │
│                 │             │  (条件路由)      │
└─────────────────┘             └─────────────────┘
    │                                     │
    ▼                                     ▼
┌─────────────────────────────────────────────────┐
│              并行分析师阶段                       │
├─────────────────────────────────────────────────┤
│  • 市场分析师 (价格趋势、技术指标)                │
│  • 基本面分析师 (财务数据、估值分析)              │
│  • 新闻分析师 (新闻事件、情绪分析)                │
│  • 社交媒体分析师 (舆情监控、热度分析)             │
│  • A股分析师 (中国市场特有分析)                   │
└─────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────┐
│             研究员辩论阶段                        │
├─────────────────────────────────────────────────┤
│  看涨研究员 ←─── 多轮辩论 ───→ 看跌研究员        │
│         │                               │        │
│         └───────────┬───────────────────┘        │
│                     ▼                            │
│              研究经理 (综合观点)                  │
│                     │                            │
│                     ▼                            │
│              投资计划生成                         │
└─────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────┐
│              交易决策阶段                         │
├─────────────────────────────────────────────────┤
│              交易员                              │
│         (制定交易策略)                           │
│                     │                            │
│                     ▼                            │
│            风险管理团队                          │
│    ┌─────────┬──────────┬──────────┐            │
│    │  激进   │   中立   │   保守   │            │
│    │ 辩论者  │  辩论者  │  辩论者  │            │
│    └─────────┴──────────┴──────────┘            │
│                     │                            │
│                     ▼                            │
│              风险经理                             │
│         (最终风险评估)                           │
└─────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────┐
│              最终交易决策                         │
└─────────────────────────────────────────────────┘
```

### LLM集成架构

```python
# LLM工厂模式
def create_llm_by_provider(provider, model, backend_url, temperature, max_tokens, timeout, api_key):
    """
    支持的LLM提供商:
    - google: Gemini 2.0/2.5 Pro
    - dashscope: 通义千问系列
    - deepseek: DeepSeek-Chat
    - openai: GPT-3.5/4, o1-preview, o1-mini
    - zhipu: GLM-4
    """
    if provider.lower() == "google":
        return ChatGoogleOpenAI(
            model=model,
            google_api_key=api_key,
            base_url=backend_url,
            temperature=temperature,
            max_tokens=max_tokens,
            timeout=timeout
        )
    elif provider.lower() == "dashscope":
        return ChatDashScopeOpenAI(
            model=model,
            api_key=api_key,
            base_url=backend_url,
            temperature=temperature,
            max_tokens=max_tokens,
            request_timeout=timeout
        )
    # ... 其他提供商
```

---

## Rust 性能优化架构

### v1.0.4 Rust 模块总览

```
rust_modules/
├── wordcloud/              # 词云统计模块
│   ├── Cargo.toml           # Rust 项目配置
│   ├── src/lib.rs           # PyO3 模块实现
│   └── target/release/      # 编译产物
│       └── tacn_wordcloud.pyd (Windows) / .so (Linux)
├── indicators/             # 技术指标模块
│   ├── Cargo.toml
│   ├── src/lib.rs           # SMA, EMA, RSI, MACD, BOLL
│   └── target/release/
│       └── tacn_indicators.pyd
├── stockcode/              # 股票代码模块
│   ├── Cargo.toml
│   ├── src/lib.rs           # 市场检测、代码标准化
│   └── target/release/
│       └── tacn_stockcode.pyd
└── financial/              # 财务计算模块 ⭐ 新增
    ├── Cargo.toml
    ├── src/lib.rs           # PE, PB, ROE, ROA 等 12 个指标
    └── target/release/
        └── tacn_financial.pyd
```

### Rust 后端适配器架构

```
┌─────────────────────────────────────────────────────────────┐
│                    app/utils/rust_backend.py               │
│                    (Rust 后端适配器)                         │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  模块加载                                                │ │
│  │  _RUST_MODULES = {                                     │ │
│  │      "wordcloud": tacn_wordcloud,                      │ │
│  │      "indicators": tacn_indicators,                     │ │
│  │      "stockcode": tacn_stockcode,                       │ │
│  │      "financial": tacn_financial,                       │ │
│  │  }                                                     │ │
│  └────────────────────────────────────────────────────────┘ │
│                          ↓                                   │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  可用性检测                                              │ │
│  │  def is_rust_available(module_name):                   │ │
│  │      # 检查模块是否成功加载                             │ │
│  └────────────────────────────────────────────────────────┘ │
│                          ↓                                   │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  降级包装器                                              │ │
│  │  def rust_fallback_wrapper(rust_func, python_func):    │ │
│  │      # 优先 Rust，失败时自动降级到 Python               │ │
│  └────────────────────────────────────────────────────────┘ │
│                          ↓                                   │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  统计追踪                                                │ │
│  │  _MODULE_STATS = {                                     │ │
│  │      "wordcloud": {"rust_calls": 0, "python_calls": 0},  │ │
│  │      "indicators": {"rust_calls": 0, "python_calls": 0},  │ │
│  │      "errors": 0                                        │ │
│  │  }                                                     │ │
│  └────────────────────────────────────────────────────────┘ │
│                                                              │
└─────────────────────────────────────────────────────────────┘
                          ↓
        ┌─────────────────┴─────────────────┐
        │                                   │
        ▼                                   ▼
┌──────────────────┐              ┌──────────────────┐
│   Rust 实现       │              │   Python 降级    │
│   (高性能)        │              │   (兼容性)       │
├──────────────────┤              ├──────────────────┤
│ • tacn_wordcloud │              │ • 词频统计      │
│ • tacn_indicators│              │ • pandas 指标   │
│ • tacn_stockcode │              │ • 代码验证      │
│ • tacn_financial │              │ • 财务计算      │
└──────────────────┘              └──────────────────┘
```

### 集成点

| 模块 | 集成位置 | 函数调用 |
|------|---------|---------|
| `tacn_wordcloud` | `app/services/wordcloud_cache_service.py` | `calculate_wordcloud()` |
| `tacn_indicators` | `tradingagents/tools/analysis/indicators.py` | `calculate_sma/ema/rsi()` |
| `tacn_indicators` | `tradingagents/dataflows/realtime_metrics.py` | `calculate_pe_pb_with_rust()` |
| `tacn_stockcode` | `tradingagents/utils/stock_validator.py` | `normalize_stock_code()` |
| `tacn_financial` | `tradingagents/dataflows/realtime_metrics.py` | `calculate_financial_metrics()` |

### 性能提升数据

| 模块 | 功能 | 数据量 | Python | Rust | 提升 |
|------|------|--------|--------|------|------|
| wordcloud | 词频统计 | 10000条 | 40.1ms | 7.87ms | **5.1x** |
| indicators | RSI(14) | 5000点 | 1.205ms | 0.124ms | **9.7x** |
| indicators | SMA(20) | 5000点 | 0.497ms | 0.088ms | **5.6x** |
| stockcode | 代码标准化 | 1000个 | ~50ms | ~10ms | **5x** |
| financial | PE/PB | 批量 | 待测试 | 待测试 | **4-8x** |

---

## 数据存储架构

### MongoDB 集合设计

#### 用户相关
| 集合名 | 用途 | 索引 |
|-------|------|-----|
| `users` | 用户信息 | username, email |
| `user_sessions` | 会话管理 | session_id, user_id |

#### 分析相关
| 集合名 | 用途 | 索引 |
|-------|------|-----|
| `analysis_records` | 分析记录 | ticker, analysis_date, created_at |
| `analysis_batches` | 批次记录 | batch_id, user_id, status |
| `analysis_tasks` | 任务记录 | task_id, batch_id, status |

#### 股票数据
| 集合名 | 用途 | 索引 |
|-------|------|-----|
| `stock_basic_info` | 基础信息 | ts_code, symbol, source |
| `stock_quotes` | 实时行情 | ts_code, trade_date |
| `stock_daily` | 日K线 | ts_code, trade_date |
| `stock_financial_data` | 财务数据 | code, report_period, data_source |
| `market_quotes` | 市场行情 | code |

#### 新闻数据
| 集合名 | 用途 | 索引 |
|-------|------|-----|
| `market_news` | 原始新闻 | source, publish_time |
| `market_news_enhanced` | 增强新闻 | tags, entities, sentiment |

#### 缓存数据
| 集合名 | 用途 | 索引 |
|-------|------|-----|
| `wordcloud_cache` | 词云缓存 | key |

#### 配置数据
| 集合名 | 用途 | 索引 |
|-------|------|-----|
| `system_configs` | 系统配置 | is_active, version |
| `llm_configs` | LLM配置 | provider, model_name |
| `data_source_configs` | 数据源配置 | type, name |

### Redis 数据结构

```
# 队列管理
user:{user_id}:pending              # 用户待处理队列 (LIST)
user:{user_id}:processing           # 用户处理中 (SET)
global:pending                      # 全局待处理队列 (LIST)
global:processing                   # 全局处理中 (SET)

# 进度缓存
task:{task_id}:progress             # 任务进度 (HASH)
batch:{batch_id}:progress           # 批次进度 (HASH)

# 会话管理
session:{session_id}                # 用户会话 (HASH)
api_token:{token}                   # API令牌 (STRING)

# 限流
rate_limit:{user_id}:{endpoint}     # API限流 (STRING)

# WebSocket
ws:users                            # 在线用户 (SET)
ws:user:{user_id}:connections       # 用户连接 (SET)

# 推送频道
notifications:{user_id}             # 用户通知 (PUB/SUB)
```

---

## 部署架构

### Docker 容器化

```
┌─────────────────────────────────────────────────────────────┐
│                    Docker Compose 编排                      │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │   frontend   │  │   backend    │  │    nginx     │     │
│  │   (Vue3)     │  │  (FastAPI)   │  │  (反向代理)   │     │
│  │   :8080      │  │   :8000      │  │    :80/:443  │     │
│  └──────────────┘  └──────────────┘  └──────────────┘     │
│         │                  │                  │            │
│         └──────────────────┼──────────────────┘            │
│                            ▼                               │
│  ┌─────────────────────────────────────────────────────┐  │
│  │                  Docker Network                      │  │
│  │                  tradingagents-network                 │  │
│  └─────────────────────────────────────────────────────┘  │
│                            │                               │
│                            ▼                               │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │   mongodb    │  │    redis     │  │   worker     │     │
│  │   :27017     │  │    :6379     │  │  (后台任务)   │     │
│  └──────────────┘  └──────────────┘  └──────────────┘     │
└─────────────────────────────────────────────────────────────┘
```

### 环境配置

```bash
# MongoDB
MONGODB_HOST=mongodb
MONGODB_PORT=27017
MONGODB_DATABASE=tradingagents

# Redis
REDIS_HOST=redis
REDIS_PORT=6379
REDIS_DB=0

# JWT
SECRET_KEY=your-secret-key
ACCESS_TOKEN_EXPIRE_MINUTES=30

# LLM API Keys
OPENAI_API_KEY=sk-xxx
GOOGLE_API_KEY=xxx
DEEPSEEK_API_KEY=sk-xxx

# 数据源 Tokens
TUSHARE_TOKEN=xxx
FINNHUB_API_KEY=xxx
```

### Docker 镜像

| 服务 | 镜像 | 版本 | 大小 |
|------|------|------|------|
| backend | `tradingagents-backend:v1.0.4` | v1.0.4 | ~1GB |
| frontend | `tradingagents-frontend:v1.0.4` | v1.0.4 | ~200MB |
| mongodb | `mongo:4.4` | 4.4 | ~400MB |
| redis | `redis:7-alpine` | 7-alpine | ~30MB |

---

## 许可证说明

### 开源部分 (Apache 2.0)
- `tradingagents/` - 核心框架
- `web/` - Streamlit界面
- `cli/` - 命令行界面
- `chanlun/` - 缠论模块
- 所有文档

### 专有部分 (需商业授权)
- `app/` - FastAPI后端
- `frontend/` - Vue3前端
- `rust_modules/` - Rust性能优化模块

**商业许可联系**: hsliup@163.com

---

**文档版本**: v1.0.8
**创建日期**: 2026-01-17
**最后更新**: 2026-01-18
**维护人员**: TradingAgents-CN 开发团队
