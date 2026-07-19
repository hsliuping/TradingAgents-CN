# TradingAgents-CN Pro — 数据架构总体规划

**版本**: v3.0
**日期**: 2026-02-26
**状态**: 规划中

---

## 📋 目录

1. [现状盘点](#1-现状盘点)
2. [数据分类体系](#2-数据分类体系)
3. [存储架构](#3-存储架构)
4. [数据获取管线](#4-数据获取管线)
5. [Agent 数据消费](#5-agent-数据消费)
6. [人工查询与审计](#6-人工查询与审计)
7. [MCP 接入规划](#7-mcp-接入规划)
8. [未来扩展](#8-未来扩展)

---

## 1. 现状盘点

### 1.1 数据存储组件

| 组件 | 角色 | 当前用途 |
|------|------|---------|
| **MongoDB** | 主数据库 | 70+ 集合，存储所有业务数据和配置 |
| **Redis** | 缓存 + 队列 | 任务队列、进度跟踪、会话、限流、分布式锁、数据缓存 |
| **文件系统** | 降级缓存 | dataflows 文件缓存（Redis/MongoDB 不可用时自动降级） |

### 1.2 现有 MongoDB 集合完整清单（~70+ 个）

#### A. 配置类集合（~25 个）

| 分类 | 集合 | 文档量级 | 说明 |
|------|------|---------|------|
| **v2.0 核心** | `workflow_definitions` | ~10 | 工作流定义（节点+边） |
| | `workflows` | ~10 | 工作流实例 |
| | `agent_configs` | ~30 | Agent 配置（类型、LLM、提示词） |
| | `tool_configs` | ~50 | 工具配置（参数、描述） |
| | `tool_agent_bindings` | ~100 | 工具↔Agent 绑定关系 |
| | `agent_workflow_bindings` | ~50 | Agent↔工作流 绑定关系 |
| | `agent_io_definitions` | ~30 | Agent 输入输出定义 |
| **系统配置** | `system_configs` | ~20 | 系统级键值配置（含数据源优先级） |
| | `llm_providers` | ~10 | LLM 提供商（API 地址、密钥） |
| | `model_catalog` | ~10 | 模型目录（能力标签） |
| | `platform_configs` | ~5 | 平台配置 |
| | `datasource_groupings` | ~10 | 数据源分组 |
| | `market_categories` | ~5 | 市场分类（A股/港股/美股） |
| | `smtp_config` | 1 | SMTP 邮件配置 |
| | `sync_status` | ~10 | 数据同步状态 |
| **提示词** | `prompt_templates` | ~30 | 提示词模板 |
| | `user_template_configs` | ~30 | 用户个性化模板 |
| | `template_history` | ~100 | 模板变更历史 |
| **用户** | `users` | ~10 | 用户账户 |
| | `user_favorites` | ~50 | 用户收藏 |
| | `user_tags` | ~20 | 用户标签 |
| | `watchlist_groups` | ~10 | 股票关注列表分组 |
| **调度** | `scheduled_analysis_configs` | ~10 | 定时分析配置 |
| | `scheduler_metadata` | ~5 | 调度器元数据 |

#### B. 业务数据集合（~45+ 个）

**股票数据（A股 5 + 港股 5 + 美股 5 = 15）**

| 集合（A股） | 文档量级 | 更新频率 | 说明 |
|------------|---------|---------|------|
| `stock_basic_info` | ~5,000 | 每日 | 股票代码、名称、行业、上市日期 |
| `market_quotes` | ~5,000 | 30秒 | 实时行情快照（每只股票一条，覆盖写入） |
| `stock_daily_quotes` | 数百万 | 每日 | 历史K线（多数据源、多周期） |
| `stock_financial_data` | 数万 | 每季度 | 财务报表（利润表、资产负债表、现金流） |
| `stock_news` | 数千 | 实时 | 新闻（含情绪分析标签） |

> 港股后缀 `_hk`，美股后缀 `_us`，字段结构相同。

**交易系统（~12 个）**

| 集合 | 文档量级 | 说明 |
|------|---------|------|
| `trading_systems` | ~10 | 个人交易计划 |
| `trading_system_versions` | ~50 | 交易计划版本历史 |
| `paper_accounts` | ~10 | 模拟账户 |
| `paper_market_rules` | ~5 | 模拟市场规则 |
| `paper_positions` | ~100 | 模拟持仓 |
| `paper_orders` | ~500 | 模拟订单 |
| `paper_trades` | ~500 | 模拟成交 |
| `real_accounts` | ~5 | 实盘账户 |
| `real_positions` | ~50 | 实盘持仓 |
| `capital_transactions` | ~100 | 资金变动 |
| `position_changes` | ~200 | 持仓变化记录 |
| `trade_reviews` | ~50 | 交易复盘 |
| `trading_system_evaluations` | ~20 | 交易系统评估 |

**分析任务（~5 个）**

| 集合 | 文档量级 | 说明 |
|------|---------|------|
| `unified_analysis_tasks` | 数千 | v2.0 统一分析任务 |
| `analysis_tasks` | 数百 | v1.x 分析任务（兼容） |
| `analysis_reports` | 数百 | 分析报告 |
| `position_analysis_reports` | ~50 | 持仓分析报告 |
| `portfolio_analysis_reports` | ~20 | 组合分析报告 |

**历史与通知（~5 个）**

| 集合 | 文档量级 | 说明 |
|------|---------|------|
| `workflow_history` | 数百 | 工作流执行历史 |
| `scheduled_analysis_history` | 数百 | 定时分析执行历史 |
| `notifications` | 数千 | 站内通知 |
| `email_records` | ~100 | 邮件发送记录 |
| `user_channel_configs` | ~20 | 渠道推送配置（飞书/钉钉/企微） |

**其他（~5 个）**

| 集合 | 文档量级 | 说明 |
|------|---------|------|
| `operation_logs` | 数千 | 操作审计日志 |
| `sessions` | ~50 | 用户登录会话 |
| `mcp_servers` | ~10 | MCP Server 配置 |
| `generated_skills` | ~20 | AI 生成的 Skill |
| `skill_gap_reports` | ~50 | 技能缺口报告 |

### 1.3 Redis 键空间

| 键模式 | 数据结构 | TTL | 用途 |
|--------|---------|-----|------|
| `qa:ready` | LIST | 无 | 分析任务就绪队列 |
| `qa:task:{id}` | HASH | 无 | 任务详情 |
| `qa:batch:{id}` | HASH | 无 | 批次详情 |
| `qa:processing` / `qa:completed` / `qa:failed` | SET | 无 | 任务状态集合 |
| `qa:user_processing:{uid}` | STRING | 无 | 用户并发计数 |
| `task:{id}:progress` | HASH | 无 | 任务进度 |
| `batch:{id}:progress` | HASH | 无 | 批次进度 |
| `session:{sid}` | HASH | 1h | 用户会话 |
| `rate_limit:{uid}:{ep}` | STRING | 1h | API 限流计数 |
| `quota:{uid}:{date}` | STRING | 24h | 每日配额 |
| `screening:{key}` | HASH | 2h | 选股结果缓存 |
| `analysis:{key}` | HASH | 2h | 分析结果缓存 |
| `scheduler:job:{id}:*` | HASH | 无 | 定时任务进度/状态 |
| `trade_date:latest:*` | STRING | 动态 | 最新交易日缓存 |
| `worker:{id}:heartbeat` | STRING | 30s | Worker 心跳 |

### 1.4 数据源提供商

| 市场 | 数据源 | 类型 | 特点 | 限制 |
|------|--------|------|------|------|
| **A股** | MongoDB(local) | 本地 | 最高优先级，零延迟 | 需预先同步 |
| | Tushare | 远程API | 数据质量高 | 积分制，有限额 |
| | AKShare | 远程API | 免费，覆盖广 | 反爬不稳定 |
| | BaoStock | 远程API | 免费，历史数据丰富 | 实时性差 |
| **美股** | yfinance | 远程API | 免费 | 不稳定 |
| | Alpha Vantage | 远程API | 免费tier | 限流严格 |
| | Finnhub | 远程API | 实时数据 | 限流 |
| **港股** | AKShare | 远程API | 免费 | 同A股 |

**降级链机制**：`datasource_groupings` 集合配置每个市场的数据源优先级（priority 字段降序），`DataSourceManager._try_fallback_sources()` 按优先级逐个尝试，失败后自动切换下一个。

### 1.5 dataflows 缓存层

```
三级缓存降级:
  Redis（TTL: A股1h/美股2h/新闻4-6h/基本面12-24h）
    ↓ miss
  MongoDB（持久化）
    ↓ miss
  文件系统（最终降级，JSON 文件）
```

由 `tradingagents/dataflows/cache/adaptive.py` 统一管理，自动探测可用后端。



---

## 2. 数据分类体系

将系统中所有数据按**结构化程度**和**业务用途**两个维度分类：

### 2.1 按结构化程度

| 类别 | 特征 | 当前数据 | 未来可能新增 |
|------|------|---------|------------|
| **结构化** | 固定字段、可直接聚合计算 | 行情(market_quotes)、K线(stock_daily_quotes)、财务(stock_financial_data)、基础信息(stock_basic_info) | 筹码分布、龙虎榜、融资融券、ETF 持仓、期权数据 |
| **半结构化** | 有固定元数据 + 可变内容 | 新闻(stock_news — 标题/日期/来源 + 正文)、分析报告(analysis_reports — 元数据 + JSON 结论) | 研报摘要、公告解读、社交媒体帖子 |
| **非结构化** | 纯文本或二进制 | 暂无 | 研报全文(PDF/HTML)、公告原文、音频转录、图片（K线截图） |

### 2.2 按业务用途

```
数据用途分层:

├── 🔧 配置数据（读多写少，系统运行基础）
│     workflow_definitions, agent_configs, tool_configs,
│     system_configs, llm_providers, model_catalog, ...
│     → 特点：文档量小，变更低频，需完整导出/导入
│
├── 📊 市场数据（读多写多，分析核心输入）
│     market_quotes, stock_daily_quotes, stock_financial_data,
│     stock_basic_info, stock_news
│     → 特点：数据量大，需定时同步，多数据源降级
│
├── 📝 分析产出（写一次读多次，业务核心输出）
│     unified_analysis_tasks, analysis_reports,
│     position_analysis_reports, portfolio_analysis_reports
│     → 特点：需长期保留，支持审计回溯
│
├── 💼 交易数据（事务性强，资金相关）
│     paper_accounts, paper_orders, paper_trades,
│     paper_positions, real_accounts, real_positions, ...
│     → 特点：一致性要求高，需审计追踪
│
├── 📜 历史记录（只追加，用于审计/回溯）
│     workflow_history, operation_logs, email_records,
│     notifications, scheduled_analysis_history
│     → 特点：只增不改，可设 TTL 自动清理
│
└── 🔄 运行态数据（临时性，用完即弃）
      Redis 队列、进度、会话、缓存
      → 特点：TTL 自动过期，丢失可恢复
```

---

## 3. 存储架构

### 3.1 存储选型原则

| 数据特征 | 存储位置 | 原因 |
|---------|---------|------|
| 需持久化 + 查询 | MongoDB | 主数据库，支持灵活 schema |
| 高频读 + 可丢失 | Redis | 亚毫秒响应，TTL 自动清理 |
| 大文件/二进制 | 文件系统 / GridFS | MongoDB 文档限制 16MB |
| 临时缓存 + 服务不可用时降级 | 文件系统 JSON | dataflows 已有实现 |

### 3.2 MongoDB 集合设计规范

**命名规范**：
- 业务数据：`{domain}_{entity}`，如 `stock_daily_quotes`、`paper_orders`
- 多市场数据：A股无后缀、港股 `_hk`、美股 `_us`
- 配置数据：`{entity}_configs` 或 `{entity}_definitions`
- 历史记录：`{entity}_history`

**通用字段**：
```python
{
    "created_at": datetime,    # 创建时间
    "updated_at": datetime,    # 更新时间（可选）
    "data_source": str,        # 数据来源（如 tushare/akshare/mcp:tdx）
    "user_id": str,            # 所属用户（用户隔离的数据）
}
```

**索引策略**：
- 市场数据：`(stock_code, trade_date, data_source)` 复合索引
- 用户数据：`(user_id, created_at)` 复合索引
- 配置数据：唯一键索引

### 3.3 Redis 使用规范

| 场景 | TTL | 键前缀 |
|------|-----|--------|
| 股票行情缓存 | 1h（A股）/ 2h（美股） | `cache:stock:` |
| 新闻缓存 | 4-6h | `cache:news:` |
| 基本面缓存 | 12-24h | `cache:fundamentals:` |
| 任务队列 | 无（永久） | `qa:` |
| 会话 | 1h | `session:` |
| 限流计数 | 1h | `rate_limit:` |
| 定时任务进度 | 无 | `scheduler:` |

---

## 4. 数据获取管线

### 4.1 当前数据流向全景

```
                        ┌─────────────────────────────────┐
                        │     外部数据源 (远程 API)         │
                        │  Tushare | AKShare | BaoStock    │
                        │  yfinance | Alpha Vantage        │
                        └────────────┬────────────────────┘
                                     │
                          ┌──────────▼──────────┐
                          │  dataflows 适配层    │
                          │  providers/china/    │
                          │  providers/us/       │
                          │  标准化 + 格式统一   │
                          └──────────┬──────────┘
                                     │
              ┌──────────────────────┼──────────────────────┐
              ▼                      ▼                      ▼
     ┌────────────────┐   ┌──────────────────┐   ┌──────────────────┐
     │   Redis 缓存    │   │   MongoDB 持久化  │   │  文件系统降级缓存  │
     │  (TTL 自动过期)  │   │  (主数据存储)     │   │  (最终降级)       │
     └───────┬────────┘   └────────┬─────────┘   └──────────────────┘
             │                     │
             └──────────┬──────────┘
                        ▼
              ┌──────────────────┐        ┌──────────────────┐
              │ Backend API 层   │        │ Agent 工具层      │
              │ app/routers/     │        │ core/tools/       │
              │ (人工查询)       │        │ implementations/  │
              └──────────────────┘        └──────────────────┘
                        │                          │
                        ▼                          ▼
              ┌──────────────────┐        ┌──────────────────┐
              │  前端 Vue 3      │        │  LLM 分析        │
              │  图表/列表/搜索  │        │  生成报告         │
              └──────────────────┘        └──────────────────┘
```

### 4.2 数据同步机制

| 数据类型 | 同步方式 | 触发条件 | 写入集合 |
|---------|---------|---------|---------|
| 股票列表 | 批量同步 | 手动/每日定时 | `stock_basic_info` |
| 实时行情 | 覆盖写入 | 30秒轮询 | `market_quotes` |
| 历史K线 | 增量追加 | 手动/每日定时 | `stock_daily_quotes` |
| 财务数据 | 增量追加 | 手动/每季度 | `stock_financial_data` |
| 新闻数据 | 增量追加 | 实时/按需 | `stock_news` |

### 4.3 降级链流程（以行情数据为例）

```
请求行情数据(600519)
  │
  ├─① Redis 缓存命中？ → 返回
  │
  ├─② MongoDB(local) 有数据？ → 返回 + 写入 Redis 缓存
  │
  ├─③ Tushare API 成功？ → 返回 + 写入 MongoDB + Redis
  │
  ├─④ AKShare API 成功？ → 返回 + 写入 MongoDB + Redis
  │
  ├─⑤ BaoStock API 成功？ → 返回 + 写入 MongoDB + Redis
  │
  └─⑥ 全部失败 → 返回错误/空数据
```

优先级由 `datasource_groupings` 集合配置，用户可在管理界面调整。

### 4.4 界面导入

用户通过前端页面上传文件或填写表单，将数据写入系统。

| 导入功能 | 前端入口 | 后端端点 | 目标集合 | 支持格式 |
|---------|---------|---------|---------|---------|
| **数据库配置导入** | 系统管理 → 数据库管理 | `POST /api/system/database/import` | 自动检测（单/多集合模式） | JSON / ZIP（内含 JSON） |
| **持仓批量导入** | 持仓管理 → 导入 | `POST /api/paper/positions/import` | `real_positions` | JSON（PositionCreate 数组） |
| **Skill 文件导入** | Skill 管理 → 导入 | `POST /api/skills/import-file` | `external_skills` | SKILL.md（Markdown 格式） |
| **Skill 内容导入** | Skill 管理 → 粘贴导入 | `POST /api/skills/import` | `external_skills` | SKILL.md 文本内容 |

**数据库配置导入**是最通用的入口，支持：
- **单集合模式**：JSON 数组 → 指定集合
- **多集合模式**：`{集合名: [文档数组]}` 的 JSON → 自动分发到各集合
- **覆盖/增量**：可选覆盖已有数据或仅追加
- **ZIP 支持**：自动解压，提取内部 JSON 文件
- **日期字段自动转换**：字符串日期自动转为 `datetime` 对象
- **`_id` 字段处理**：字符串 `_id` 自动转为 `ObjectId`

### 4.5 接口导入（API / 脚本）

通过 REST API 或命令行脚本将数据写入系统，用于自动化场景。

| 导入方式 | 端点 / 脚本 | 目标集合 | 用途 |
|---------|-----------|---------|------|
| **单股同步** | `POST /api/stock-sync/single` | `market_quotes` / `stock_daily_quotes` / `stock_financial_data` | 前端触发单只股票全量同步（行情+K线+财务+基础） |
| **批量同步** | `POST /api/stock-sync/batch` | 同上 | 前端触发多只股票批量同步 |
| **定时同步** | APScheduler → `tushare_sync_service` / `akshare_sync_service` | 同上 | 系统定时任务自动同步 |
| **财务数据批量写入** | `POST /api/financial-data/batch` | `stock_financial_data` | 程序化写入财务数据 |
| **Skill URL 导入** | `POST /api/skills/import-url` | `external_skills` | 从远程 URL 获取 SKILL.md |
| **配置初始化脚本** | `scripts/import_config_and_create_user.py` | 多集合（配置类） | 新系统首次初始化，导入预置配置 + 创建默认用户 |
| **数据库导出 API** | `POST /api/system/database/export` | — | 导出配置/数据用于迁移或备份 |

**数据同步接口**的关键特性：
- 支持数据源选择：`tushare` / `akshare` / `qmt`
- 支持增量/全量模式
- 后台异步执行（`BackgroundTasks`），前端可查询进度
- 自动去重（`upsert` 模式写入 MongoDB）
- 与降级链复用同一套 provider 适配层

```
数据导入的三条路径:

  ┌─────────────────┐   ┌─────────────────┐   ┌─────────────────┐
  │  界面导入         │   │  API 接口导入     │   │  脚本导入         │
  │  (用户上传文件)    │   │  (程序化调用)     │   │  (命令行)         │
  │  JSON/ZIP/SKILL  │   │  stock-sync/     │   │  import_config   │
  │                  │   │  financial-data/ │   │  _and_create_    │
  │                  │   │  skills/         │   │  user.py         │
  └───────┬─────────┘   └───────┬─────────┘   └───────┬─────────┘
          │                     │                     │
          └──────────┬──────────┴──────────┬──────────┘
                     ▼                     ▼
            ┌────────────────┐    ┌────────────────┐
            │ MongoDB 持久化  │    │ Redis 缓存刷新  │
            │ (主数据存储)     │    │ (TTL 自动更新)  │
            └────────────────┘    └────────────────┘
```

---

## 5. Agent 数据消费

### 5.1 v2.0 Agent 工具体系

Agent 通过 `tool_agent_bindings` 绑定工具，工具实现位于 `core/tools/implementations/`：

| 工具分类 | 目录 | 数据来源 | 读取方式 |
|---------|------|---------|---------|
| **行情数据** | `market/stock_market_data.py` | `market_quotes` / `stock_daily_quotes` | MongoDB 查询 + 数据源优先级 |
| **筹码分布** | `market/chip_distribution_tools.py` | 实时计算（基于K线数据） | 读 `stock_daily_quotes` 后计算 |
| **技术指标** | `market/technical_indicators.py` | 基于K线计算 | 读 `stock_daily_quotes` 后计算 |
| **基本面** | `fundamentals/financial_tools.py` | `stock_financial_data` | MongoDB 查询 + 数据源优先级 |
| **新闻** | `news/stock_news.py` | `stock_news` | MongoDB 查询 + 数据源优先级 |
| **社交情绪** | `social/stock_sentiment.py` | 新闻数据 + LLM 分析 | 读新闻 → LLM 判断情绪 |
| **交易复盘** | `trade_review/*.py` | `paper_*` / `real_*` 集合 | MongoDB 查询 |

**关键特征**：所有工具统一通过 `data_source_priority` 模块决定优先读取哪个数据源的数据。

### 5.2 Skill（AI 生成工具）数据访问

`core/tools/external/local_data.py` 提供给 AI 生成的 Skill 使用：

```python
# Skill 可用的数据访问函数
get_stock_basic_info(symbol)       # → stock_basic_info
get_stock_daily_quotes(symbol, ...) # → stock_daily_quotes
get_stock_news(symbol, ...)        # → stock_news
get_market_quotes(symbol)          # → market_quotes
get_stock_financial_data(symbol)   # → stock_financial_data
```

所有函数内部都遵循 `data_source_priority` 优先级，确保一致性。

### 5.3 MCP 工具数据访问

当前 MCP 工具（`core/tools/mcp/client_manager.py`）通过 MCP 协议实时调用外部 Server，数据**不经过 MongoDB**，直接返回给 Agent 的 LLM context。

→ 这是本文档要解决的核心问题之一（见第 7 节）。

---

## 6. 人工查询与审计

### 6.1 前端数据查询接口

| 前端 API | 后端路由 | 数据来源 | 功能 |
|---------|---------|---------|------|
| `stocks.ts` | `/api/stocks/{code}/quote` | `market_quotes` + 实时fallback | 股票行情查询 |
| `stocks.ts` | `/api/stocks/{code}/kline` | `stock_daily_quotes` + fallback | K线数据 |
| `stocks.ts` | `/api/stocks/{code}/fundamentals` | `stock_financial_data` | 基本面数据 |
| `news.ts` | `/api/news-data/query/{symbol}` | `stock_news` + 实时fallback | 新闻查询（DB优先，无数据时实时获取） |
| `multiMarket.ts` | `/api/markets/{market}/stocks/...` | 多市场集合 | 跨市场数据 |
| `stockSync.ts` | `/api/stock-sync/single\|batch` | 触发同步 | 手动数据同步 |
| `analysis.ts` | `/api/analysis/...` | `unified_analysis_tasks` | 分析任务管理 |
| `paper.ts` | `/api/paper/...` | `paper_*` 集合 | 模拟交易 |

### 6.2 审计能力

| 审计维度 | 当前状态 | 数据来源 |
|---------|---------|---------|
| **操作审计** | ✅ 已实现 | `operation_logs`（OperationLogMiddleware 自动记录） |
| **数据来源追踪** | ✅ 已实现 | 每条数据记录 `data_source` 字段 |
| **分析过程回溯** | ✅ 已实现 | `unified_analysis_tasks` 记录完整分析过程 |
| **MCP 数据审计** | ❌ 未实现 | MCP 调用数据不落地，无法回溯 |
| **数据变更追踪** | ⚠️ 部分 | 配置有 `template_history`，数据无变更日志 |

---

## 7. MCP 接入规划

### 7.1 两大类 MCP 分类

```
MCP 接入
  │
  ├── 📊 数据源类 MCP
  │     定义：返回的数据可映射到已有/可扩展的 MongoDB 集合
  │     示例：TDX 行情、其他行情源、境外财务数据
  │     处理：适配器 → 标准化 → MongoDB → 参与降级链
  │
  └── 🔧 功能类 MCP
        定义：提供计算/查询/生成等功能，输出不适合持久化
        示例：网页搜索、代码执行、知识库检索、情感分析
        处理：Agent 运行时直接调用，LLM 消费返回结果
```

**分类时机**：在 MCP Server 配置时（`mcp_servers` 集合）通过 `category` 字段标记。

### 7.2 数据源类 MCP — 三层数据处理

```
数据源类 MCP 返回的数据
  │
  ├── 结构化 + 现有集合可容纳
  │     行情价格、财务指标等
  │     → 适配器字段映射 → 写入现有集合（market_quotes 等）
  │     → data_source 标记为 "mcp:{server_name}"
  │
  ├── 结构化 + 现有集合无法容纳
  │     筹码分布、龙虎榜、融资融券等全新数据类型
  │     → 适配器映射 → 创建新专用集合
  │     → 同步注册到 Agent 工具系统
  │
  └── 非结构化
        研报全文、公告原文、社交媒体内容
        → 提取结构化元数据（stock_code、date、tags）
        → 内容原样存入 mcp_documents 集合
        → Agent 通过元数据检索，LLM 消费原文
```

### 7.3 MCP Server 配置 Schema 扩展

```python
# mcp_servers 集合增加字段
{
    "server_name": "a-share-tdx",
    "category": "datasource",           # datasource | function
    "data_mappings": [                   # 仅 datasource 类需要
        {
            "tool_name": "get_stock_quotes",
            "target_collection": "market_quotes",
            "adapter": "tdx_quotes",     # 适配器名称
            "field_mapping": {           # 字段映射
                "code": "stock_code",
                "o": "open", "c": "close",
                "h": "high", "l": "low",
                "vol": "volume"
            },
            "unit_conversion": {         # 单位转换
                "vol": {"from": "手", "to": "股", "factor": 100}
            }
        }
    ]
}
```

### 7.4 降级链扩展

```python
# datasource_groupings 集合支持 MCP 数据源
{
    "data_source_name": "mcp:a-share-tdx",
    "market_category_id": "a_shares",
    "priority": 5,              # 优先级低于内置源
    "enabled": true,
    "source_type": "mcp"        # 标记为 MCP 类型
}
```

降级链变为：`local → Tushare → AKShare → BaoStock → MCP:TDX → ...`

### 7.5 MCP 审计方案

所有 MCP 工具调用（无论数据源类还是功能类）均记录审计日志：

```python
# mcp_audit_logs 集合
{
    "task_id": "关联分析任务ID",
    "user_id": "触发用户",
    "server_name": "a-share-tdx",
    "tool_name": "get_stock_quotes",
    "category": "datasource",
    "request_params": {...},
    "response_summary": "200 OK, 10 records",
    "persisted_to": "market_quotes",   # 数据源类：写入了哪个集合
    "created_at": "2026-02-26T10:30:00"
}
```

---

## 8. 未来扩展

### 8.1 新数据类型规划

| 数据类型 | 来源 | 存储方案 | 优先级 |
|---------|------|---------|--------|
| 筹码分布数据 | TDX MCP / 计算生成 | 新建 `stock_chip_distribution` | 高 |
| 龙虎榜数据 | AKShare / MCP | 新建 `stock_top_list` | 中 |
| 融资融券数据 | AKShare / MCP | 新建 `stock_margin_trading` | 中 |
| ETF 持仓明细 | MCP | 新建 `etf_holdings` | 低 |
| 期权数据 | MCP | 新建 `stock_options` | 低 |
| 研报全文 | MCP | `mcp_documents` (doc_type=research_report) | 中 |
| 公告原文 | MCP | `mcp_documents` (doc_type=announcement) | 中 |
| 社交媒体 | MCP | `mcp_documents` (doc_type=social_media) | 低 |

### 8.2 非结构化数据存储集合

```python
# mcp_documents 集合 — 统一存储非结构化 MCP 数据
{
    "doc_id": "uuid",
    "source": "mcp:{server_name}",
    "tool_name": "get_research_report",
    "doc_type": "research_report",    # 文档类型标签

    # 可检索的结构化元数据
    "stock_code": "600519",
    "date": "2026-02-26",
    "author": "某券商",
    "tags": ["白酒", "消费"],

    # 非结构化内容
    "content": "正文纯文本...",
    "raw_content": "原始 HTML/Markdown",
    "content_type": "text/html",

    # 审计信息
    "task_id": "关联分析任务",
    "user_id": "触发用户",
    "created_at": "2026-02-26T10:30:00",
    "ttl_expire_at": "2026-05-26T10:30:00"  # 可选：90天自动过期
}
```

### 8.3 新市场扩展

当前支持 A股/港股/美股，扩展新市场时：
1. 创建 `stock_basic_info_{market}` 等 5 个基础集合
2. 在 `market_categories` 注册新市场
3. 在 `datasource_groupings` 配置该市场的数据源优先级
4. 在 `providers/` 下添加对应数据源适配器

### 8.4 架构演进路线

```
当前 (v1.x~v3.0):
  内置数据源 → dataflows 适配 → MongoDB → Agent/前端

近期 (v3.1):
  + MCP 数据源类接入降级链
  + MCP 审计日志
  + mcp_documents 非结构化存储

中期 (v3.x):
  + 新结构化数据集合（筹码/龙虎榜/融资融券）
  + 数据质量监控（完整性/时效性/一致性）
  + 更多市场支持

远期:
  + 向量数据库（嵌入式检索研报/新闻）
  + 实时流数据（WebSocket 行情）
  + 数据血缘追踪
```

---

**最后更新**: 2026-02-26
**维护者**: TradingAgents-CN Pro Team
