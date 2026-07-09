# 对话驱动回测系统设计文档

## 📋 项目概述

**项目名称**: 对话驱动回测系统 (Conversational Backtesting System)  
**版本**: v2.3  
**设计日期**: 2026-02-14  
**设计目标**: 实现类似 OpenClaw/NexusTrade 的对话式策略回测功能

### 核心理念

用户通过自然语言描述投资策略想法 → AI 分析可行性 → 用户确认参数 → 生成结构化策略 → 执行回测 → 展示结果

**完整工作流**:
```
用户描述想法 → AI分析可行性 → 用户确认 → 生成策略 → 执行回测 → 展示结果
```

---

## 🏗️ 系统架构

### 架构原则

1. **GPL 许可证隔离**: Backtrader (GPLv3) 运行在独立容器中，通过 HTTP 通信避免许可证传染
2. **策略 DSL 化**: 不生成任意 Python 代码，使用 JSON 结构化策略定义，安全可控
3. **LLM 驱动**: 利用 LLM 理解用户意图，生成标准化策略参数
4. **数据复用**: 基于现有 MongoDB 数据基础设施 (10年+ 历史数据)

### 系统组件

```
┌─────────────────────────────────────────────────────────────┐
│                    前端 (Vue 3)                              │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────────────────┐ │
│  │ 策略对话界面 │ │ 参数确认 UI │ │ 回测结果可视化           │ │
│  └─────────────┘ └─────────────┘ └─────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
                              │ HTTP API
┌─────────────────────────────────────────────────────────────┐
│                 主平台 (专有许可证)                          │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │              后端 API (FastAPI)                         │ │
│  │  app/routers/backtest.py + app/services/backtest_service.py │
│  └─────────────────────────────────────────────────────────┘ │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │            回测核心 (core/backtest/)                    │ │
│  │  • strategy_analyzer.py   (LLM 策略分析)               │ │
│  │  • strategy_generator.py  (LLM DSL 生成)               │ │
│  │  • engine_client.py       (HTTP 客户端)                │ │
│  │  • schemas.py             (数据模型)                   │ │
│  └─────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
                              │ HTTP
┌─────────────────────────────────────────────────────────────┐
│            Backtrader 服务容器 (GPLv3)                      │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │              FastAPI 包装器                             │ │
│  │  POST /run  GET /health                                 │ │
│  └─────────────────────────────────────────────────────────┘ │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │                回测引擎                                 │ │
│  │  • translator.py    (DSL → Backtrader Strategy)        │ │
│  │  • data_feed.py     (MongoDB → DataFeed)               │ │
│  │  • cn_broker.py     (A股市场规则)                       │ │
│  │  • analyzers.py     (绩效指标计算)                      │ │
│  └─────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────┐
│                    MongoDB 数据层                           │
│  • stock_daily_quotes     (10年+ OHLCV 数据)               │
│  • dividend 数据          (Tushare API)                    │
│  • backtest_sessions      (回测会话)                       │
│  • backtest_results       (回测结果)                       │
│  • paper_market_rules     (市场规则配置)                   │
└─────────────────────────────────────────────────────────────┘
```

---

## 📊 策略 DSL Schema

### 设计原则

- **结构化**: JSON 格式，LLM 生成稳定
- **安全性**: 不执行任意代码，预定义条件类型
- **可扩展**: 支持新增条件类型和市场规则
- **可审核**: 用户可直观理解和修改参数

### 核心 Schema

```json
{
  "name": "策略名称",
  "description": "策略描述",
  "universe": {
    "type": "股票池类型",
    "params": { /* 股票池参数 */ }
  },
  "entry_rules": [
    { /* 买入条件列表 */ }
  ],
  "exit_rules": [
    { /* 卖出条件列表 */ }
  ],
  "config": {
    "start_year": 2016,
    "end_year": 2025,
    "initial_capital": 1000000,
    "position_size": "equal_weight",
    "max_positions": 10,
    "benchmark": "000300",
    "market": "CN"
  }
}
```

### 示例 1: 高分红股票进场时机验证

```json
{
  "name": "高分红股票进场时机验证",
  "description": "验证连续高分红股票在不同月份买入的胜率和收益表现",
  "universe": {
    "type": "dividend_screen",
    "params": {
      "min_cash_div": 0.3,
      "min_consecutive_years": 3,
      "top_n": 30
    }
  },
  "entry_rules": [
    {"type": "calendar_month", "months": [1,2,3,4,5,6,7,8,9,10,11,12]}
  ],
  "exit_rules": [
    {"type": "holding_days", "days": 90}
  ],
  "config": {
    "start_year": 2016,
    "end_year": 2025,
    "initial_capital": 1000000,
    "position_size": "equal_weight",
    "max_positions": 10,
    "benchmark": "000300",
    "market": "CN"
  }
}
```

### 示例 2: 低估值高股息策略

```json
{
  "name": "低估值高股息策略",
  "description": "PE < 15 且股息率 > 3% 时买入，涨 20% 止盈或跌 10% 止损",
  "universe": {
    "type": "static",
    "symbols": ["601318", "600036", "000651"]
  },
  "entry_rules": [
    {"type": "indicator", "field": "pe", "op": "<", "value": 15},
    {"type": "indicator", "field": "dividend_yield", "op": ">", "value": 3.0}
  ],
  "exit_rules": [
    {"type": "profit_target", "pct": 20},
    {"type": "stop_loss", "pct": -10},
    {"type": "holding_days", "days": 180}
  ],
  "config": {
    "start_year": 2018,
    "end_year": 2025,
    "initial_capital": 1000000,
    "position_size": "equal_weight",
    "max_positions": 5,
    "market": "CN"
  }
}
```

---

## 🔧 技术选型

### 回测引擎: Backtrader (容器化隔离)

**选择理由**:
- ✅ 成熟稳定，社区验证多年
- ✅ 内置撮合引擎、持仓管理、费用计算
- ✅ 支持复杂策略和自定义 Analyzer
- ✅ 容器化部署避免 GPL 许可证传染

**GPL 合规策略**:
- Backtrader 服务独立部署，附 GPLv3 LICENSE
- 主平台通过 HTTP 调用，无代码链接
- 源码开放，满足 GPL 分发要求

### 数据基础: MongoDB + Tushare

**现有优势**:
- `stock_daily_quotes`: 10年+ OHLCV 数据，支持日/周/月线
- `dividend` 数据: 新增的 Tushare API 支持
- `paper_market_rules`: 完整的 CN/HK/US 市场规则
- 三源冗余: Tushare + AKShare + BaoStock

### LLM 集成: 复用现有架构

- 统一 LLM 客户端 (`core/llm/`)
- 投资教练系统提示词
- RAG 知识库支持

---

## 📡 API 设计

### REST 端点

```
POST /api/backtest/analyze      # 第1步：AI 分析策略可行性
POST /api/backtest/generate     # 第2步：生成策略 DSL
POST /api/backtest/run          # 第3步：执行回测
GET  /api/backtest/results/{id} # 获取回测结果
GET  /api/backtest/sessions     # 列出用户的回测历史
DELETE /api/backtest/sessions/{id} # 删除回测记录
```

### Backtrader 服务端点

```
POST /run          # 接收策略 DSL，返回回测结果
GET  /health       # 健康检查
```

---

## 📈 回测结果数据结构

### 汇总指标

```json
{
  "session_id": "uuid",
  "strategy": { /* 策略 DSL */ },
  "summary": {
    "total_return": 0.156,
    "annual_return": 0.082,
    "max_drawdown": -0.123,
    "sharpe_ratio": 1.25,
    "win_rate": 0.68,
    "profit_loss_ratio": 2.1,
    "total_trades": 45,
    "avg_holding_days": 72
  },
  "monthly_breakdown": [
    {"month": 1, "win_rate": 0.72, "avg_return": 0.083, "trades": 8},
    {"month": 2, "win_rate": 0.65, "avg_return": 0.052, "trades": 7}
  ],
  "equity_curve": [ /* 每日净值数组 */ ],
  "trade_list": [ /* 每笔交易明细 */ ],
  "benchmark_comparison": { /* vs 沪深300 */ }
}
```

### 交易明细

```json
{
  "trade_id": "uuid",
  "symbol": "000001",
  "entry_date": "2023-01-15",
  "exit_date": "2023-04-15",
  "entry_price": 12.50,
  "exit_price": 13.80,
  "quantity": 800,
  "return_pct": 0.104,
  "holding_days": 90,
  "entry_reason": "calendar_month",
  "exit_reason": "holding_days"
}
```

---

## 🚀 实施计划

### Phase 1: Backtrader 容器化服务 (2-3 天)

**目标**: 搭建独立的回测服务，支持基本策略类型

**任务清单**:
1. ✅ 创建 `backtest-service/` 项目结构
2. ✅ 实现策略 DSL 翻译器 (JSON → Backtrader Strategy)
3. ✅ 实现 MongoDB DataFeed (stock_daily_quotes → Backtrader)
4. ✅ 实现 CN Broker (T+1、涨跌停、手续费)
5. ✅ 实现绩效分析器 (胜率、收益、回撤、Sharpe)
6. ✅ 构建 Docker 镜像和健康检查

**验收标准**:
- 服务可独立启动，响应 `/health` 端点
- 支持分红时机验证和简单买卖策略
- 返回完整的回测结果 JSON

### Phase 2: 主平台集成 (1-2 天)

**目标**: 实现 LLM 驱动的策略分析和生成，集成回测服务

**任务清单**:
1. ✅ HTTP 客户端 (`core/backtest/engine_client.py`)
2. ✅ LLM 策略分析器 (`core/backtest/strategy_analyzer.py`)
3. ✅ LLM 策略生成器 (`core/backtest/strategy_generator.py`)
4. ✅ 后端 API 端点 (`app/routers/backtest.py`)
5. ✅ 业务服务层 (`app/services/backtest_service.py`)
6. ✅ MongoDB 存储 (sessions + results)

**验收标准**:
- 用户可通过 API 描述策略，获得可行性分析
- 确认后生成 DSL，执行回测，存储结果
- 支持历史会话查询和结果检索

### Phase 3: 前端 UI 开发 (2-3 天)

**目标**: 完整的用户交互界面，可视化回测结果

**任务清单**:
1. ✅ 策略对话界面 (聊天式交互)
2. ✅ 参数确认 UI (DSL 参数展示和编辑)
3. ✅ 结果可视化 (收益曲线、交易明细、月度统计)
4. ✅ 历史会话管理

**验收标准**:
- 完整的用户体验流程
- 直观的结果展示和数据导出
- 响应式设计，支持移动端

---

## 🔒 安全和合规

### GPL 许可证合规

1. **源码开放**: `backtest-service/` 独立开源，附 GPLv3 LICENSE
2. **隔离部署**: 独立容器，HTTP 通信，无代码链接
3. **分发合规**: Docker 镜像附带源码获取链接
4. **主平台保护**: 专有许可证不受影响

### 数据安全

1. **用户隔离**: 回测会话按用户 ID 隔离
2. **参数验证**: 严格的 DSL Schema 验证
3. **资源限制**: 回测时间和内存限制
4. **审计日志**: 完整的操作记录

### 投资合规

1. **教育定位**: 明确标注"仅供学习研究，不构成投资建议"
2. **风险提示**: 历史回测不代表未来表现
3. **免责声明**: 用户自行承担投资风险

---

**文档版本**: v1.0  
**最后更新**: 2026-02-14  
**维护者**: TradingAgents-CN Pro Team
