# TradingAgents-CN Pro - 数据库设计文档

**版本**: v2.0  
**最后更新**: 2026-01-25  
**数据库**: MongoDB 4.4+

---

## 📋 目录

- [概览](#概览)
- [核心集合分类](#核心集合分类)
- [集合详细说明](#集合详细说明)
- [常见问题](#常见问题)

---

## 概览

TradingAgents-CN Pro 使用 MongoDB 作为主数据库，共有 **70+ 个集合**，分为以下几大类：

| 分类 | 集合数量 | 用途 |
|------|---------|------|
| **v2.0 核心** | 10 | 工作流、Agent、工具配置 |
| **系统配置** | 8 | 系统配置、LLM、数据源 |
| **用户相关** | 5 | 用户、会话、收藏、标签 |
| **股票数据** | 15 | 基础信息、行情、财务、新闻 |
| **分析任务** | 5 | 分析任务、报告、历史 |
| **交易系统** | 12 | 模拟/实盘账户、订单、持仓 |
| **调度任务** | 4 | 定时任务、执行历史 |
| **其他** | 11 | 日志、通知、邮件等 |

---

## 核心集合分类

### 1. v2.0 核心集合（工作流引擎）

| 集合名 | 用途 | 关键字段 |
|--------|------|---------|
| `workflow_definitions` | 工作流定义 | `workflow_id`, `name`, `nodes`, `edges` |
| `workflows` | 工作流实例 | `workflow_id`, `status`, `created_at` |
| `agent_configs` | Agent 配置 | `agent_id`, `name`, `type`, `llm_config` |
| `tool_configs` | 工具配置 | `tool_id`, `name`, `type`, `parameters` |
| `tool_agent_bindings` | 工具-Agent 绑定 | `tool_id`, `agent_id`, `priority` |
| `agent_workflow_bindings` | Agent-工作流 绑定 | `agent_id`, `workflow_id`, `node_id` |
| `agent_io_definitions` | Agent IO 定义 | `agent_id`, `input_schema`, `output_schema` |
| `prompt_templates` | 提示词模板 | `template_id`, `name`, `content`, `variables` |
| `user_template_configs` | 用户模板配置 | `user_id`, `template_id`, `custom_content` |
| `template_history` | 模板历史 | `template_id`, `version`, `changes` |

### 2. 系统配置集合

| 集合名 | 用途 | 关键字段 |
|--------|------|---------|
| `system_configs` | 系统配置 | `config_key`, `config_value`, `category` |
| `llm_providers` | LLM 提供商 | `provider_id`, `name`, `api_base`, `api_key` |
| `model_catalog` | 模型目录 | `provider`, `models[]`, `capabilities` |
| `platform_configs` | 平台配置 | `platform`, `config`, `enabled` |
| `datasource_groupings` | 数据源分组 | `group_id`, `name`, `data_sources[]` |
| `market_categories` | 市场分类 | `category`, `name`, `markets[]` |
| `smtp_config` | SMTP 配置 | `host`, `port`, `username`, `password` |
| `sync_status` | 同步状态 | `job`, `status`, `last_sync`, `next_sync` |

### 3. 用户相关集合

| 集合名 | 用途 | 关键字段 |
|--------|------|---------|
| `users` | 用户数据 | `username`, `email`, `hashed_password`, `plan` |
| `user_sessions` | 用户会话 | `session_id`, `user_id`, `expires_at` |
| `user_favorites` | 用户收藏 | `user_id`, `symbol`, `created_at` |
| `user_tags` | 用户标签 | `user_id`, `tag_name`, `symbols[]` |
| `watchlist_groups` | 自选股分组 | `user_id`, `group_name`, `symbols[]` |

### 4. 股票数据集合

#### 4.1 A股数据

| 集合名 | 用途 | 数据量 | 更新频率 |
|--------|------|--------|---------|
| `stock_basic_info` | 股票基础信息 | ~5000 | 每日 |
| `market_quotes` | 实时行情快照 | ~5000 | 每30秒 |
| `stock_daily_quotes` | 历史K线数据 | 数百万 | 每日 |
| `stock_financial_data` | 财务数据 | 数万 | 每季度 |
| `stock_news` | 股票新闻 | 数千 | 实时 |

#### 4.2 港股数据

| 集合名 | 用途 |
|--------|------|
| `stock_basic_info_hk` | 港股基础信息 |
| `market_quotes_hk` | 港股实时行情 |
| `stock_daily_quotes_hk` | 港股历史K线 |
| `stock_financial_data_hk` | 港股财务数据 |
| `stock_news_hk` | 港股新闻 |

#### 4.3 美股数据

| 集合名 | 用途 |
|--------|------|
| `stock_basic_info_us` | 美股基础信息 |
| `market_quotes_us` | 美股实时行情 |
| `stock_daily_quotes_us` | 美股历史K线 |
| `stock_financial_data_us` | 美股财务数据 |
| `stock_news_us` | 美股新闻 |

### 5. 分析任务集合

| 集合名 | 用途 | 关键字段 |
|--------|------|---------|
| `unified_analysis_tasks` | 统一分析任务（v2.0） | `task_id`, `workflow_id`, `status` |
| `analysis_tasks` | 分析任务（v1.x） | `task_id`, `symbol`, `status` |
| `analysis_reports` | 分析报告 | `task_id`, `symbol`, `report_content` |
| `position_analysis_reports` | 持仓分析报告 | `account_id`, `positions[]`, `analysis` |
| `portfolio_analysis_reports` | 组合分析报告 | `portfolio_id`, `holdings[]`, `analysis` |

### 6. 交易系统集合

#### 6.1 模拟交易

| 集合名 | 用途 | 关键字段 |
|--------|------|---------|
| `paper_accounts` | 模拟账户 | `account_id`, `user_id`, `balance`, `total_assets` |
| `paper_market_rules` | 模拟市场规则 | `market`, `trading_hours`, `commission_rate` |
| `paper_positions` | 模拟持仓 | `account_id`, `symbol`, `quantity`, `cost` |
| `paper_orders` | 模拟订单 | `order_id`, `account_id`, `symbol`, `status` |
| `paper_trades` | 模拟交易 | `trade_id`, `order_id`, `price`, `quantity` |

#### 6.2 实盘交易

| 集合名 | 用途 | 关键字段 |
|--------|------|---------|
| `real_accounts` | 实盘账户 | `account_id`, `user_id`, `broker`, `api_key` |
| `real_positions` | 实盘持仓 | `account_id`, `symbol`, `quantity`, `cost` |
| `capital_transactions` | 资金交易 | `account_id`, `type`, `amount`, `balance` |
| `position_changes` | 持仓变化 | `account_id`, `symbol`, `change_type`, `quantity` |

#### 6.3 交易计划

| 集合名 | 用途 | 关键字段 |
|--------|------|---------|
| `trading_systems` | 个人交易计划 | `system_id`, `user_id`, `name`, `rules` |
| `trade_reviews` | 交易复盘 | `trade_id`, `review_content`, `lessons` |
| `trading_system_evaluations` | 交易系统评估 | `system_id`, `performance`, `metrics` |

### 7. 调度任务集合

| 集合名 | 用途 | 关键字段 |
|--------|------|---------|
| `scheduled_analysis_configs` | 定时分析配置 | `config_id`, `cron`, `workflow_id` |
| `scheduled_analysis_history` | 定时分析历史 | `config_id`, `execution_time`, `status` |
| `scheduler_metadata` | 调度器元数据 | `scheduler_id`, `status`, `last_heartbeat` |
| `scheduler_executions` | 调度执行记录 | `execution_id`, `task_id`, `result` |

### 8. 其他集合

| 集合名 | 用途 | 关键字段 |
|--------|------|---------|
| `operation_logs` | 操作日志 | `user_id`, `action`, `timestamp`, `details` |
| `notifications` | 通知 | `user_id`, `type`, `content`, `read` |
| `email_records` | 邮件记录 | `to`, `subject`, `status`, `sent_at` |
| `token_usage` | Token 使用统计 | `user_id`, `model`, `tokens`, `cost` |
| `license_cache` | 许可证缓存 | `email`, `plan`, `expires_at` |
| `quotes_ingestion_status` | 行情采集状态 | `market`, `last_update`, `status` |
| `financial_data_cache` | 财务数据缓存 | `symbol`, `data`, `cached_at` |
| `imported_data` | 导入数据记录 | `user_id`, `data_type`, `count`, `imported_at` |
| `social_media_messages` | 社交媒体消息 | `platform`, `content`, `created_at` |
| `stock_screening_view` | 股票筛选视图 | 聚合视图，不存储数据 |
| `workflow_history` | 工作流历史 | `workflow_id`, `execution_id`, `logs` |

---

## 集合详细说明

### 🔥 重点：`market_quotes` vs `stock_daily_quotes`

这是两个最容易混淆的集合，理解它们的区别非常重要！

#### `market_quotes` - 实时行情快照

**用途**: 存储全市场股票的**最新行情快照**，用于快速获取股票的当前价格、涨跌幅等实时信息。

**数据结构**:
```javascript
{
  "code": "600036",              // 股票代码（主键）
  "name": "招商银行",
  "close": 46.50,                // 最新价
  "pct_chg": 2.38,               // 涨跌幅(%)
  "change": 1.08,                // 涨跌额
  "volume": 12345678,            // 成交量(股)
  "amount": 567890123.45,        // 成交额(元)
  "high": 46.78,                 // 最高价
  "low": 45.01,                  // 最低价
  "open": 45.23,                 // 开盘价
  "pre_close": 45.42,            // 前收盘价
  "turnover_rate": 1.23,         // 换手率(%)
  "volume_ratio": 1.05,          // 量比
  "updated_at": ISODate("2026-01-25T06:30:00Z")
}
```

**特点**:
- ✅ **小数据量**: ~5000条（全市场股票）
- ✅ **高频更新**: 每30秒更新一次（交易时段）
- ✅ **快速查询**: 单键查询，毫秒级响应
- ✅ **实时性强**: 延迟 <1分钟

**索引**:
```javascript
db.market_quotes.createIndex({ "code": 1 }, { unique: true })
db.market_quotes.createIndex({ "updated_at": -1 })
```

**使用场景**:
- ✅ 股票列表页面（显示最新价格）
- ✅ 自选股监控（实时涨跌）
- ✅ 股票详情页快照（当前价格）
- ✅ 实时排行榜（涨幅榜、跌幅榜）
- ✅ 交易决策（当前价格判断）

**不适用场景**:
- ❌ K线图展示（需要历史数据）
- ❌ 技术分析（需要多日数据）
- ❌ 回测系统（需要历史数据）

---

#### `stock_daily_quotes` - 历史K线数据

**用途**: 存储股票的**历史K线数据**，支持多数据源、多周期，用于K线图、技术分析、回测等。

**数据结构**:
```javascript
{
  "symbol": "600036",            // 股票代码
  "trade_date": "20260125",      // 交易日期（YYYYMMDD）
  "data_source": "local",        // 数据源（local/tushare/akshare/baostock）
  "period": "daily",             // 周期（daily/weekly/monthly/5min/15min/30min/60min）
  "open": 45.23,                 // 开盘价
  "high": 46.78,                 // 最高价
  "low": 45.01,                  // 最低价
  "close": 46.50,                // 收盘价
  "volume": 12345678,            // 成交量(股)
  "amount": 567890123.45,        // 成交额(元)
  "pre_close": 45.42,            // 前收盘价
  "change": 1.08,                // 涨跌额
  "pct_chg": 2.38,               // 涨跌幅(%)
  "turnover_rate": 1.23,         // 换手率(%)
  "volume_ratio": 1.05,          // 量比
  "created_at": ISODate("2026-01-25T09:00:00Z"),
  "updated_at": ISODate("2026-01-25T09:00:00Z")
}
```

**特点**:
- ✅ **大数据量**: 数百万条（每只股票数百条历史记录）
- ✅ **低频更新**: 每日一次（收盘后）
- ✅ **多数据源**: 支持 local、tushare、akshare、baostock
- ✅ **多周期**: 支持日线、周线、月线、分钟线
- ✅ **历史数据**: T+1，收盘后更新

**索引**:
```javascript
// 复合唯一索引（主键）
db.stock_daily_quotes.createIndex({
  "symbol": 1,
  "trade_date": 1,
  "data_source": 1,
  "period": 1
}, { unique: true })

// 查询优化索引
db.stock_daily_quotes.createIndex({ "symbol": 1, "period": 1, "trade_date": 1 })
db.stock_daily_quotes.createIndex({ "symbol": 1 })
db.stock_daily_quotes.createIndex({ "trade_date": -1 })
```

**使用场景**:
- ✅ K线图展示（日线、周线、月线）
- ✅ 技术指标计算（MA、MACD、KDJ等）
- ✅ 回测系统（历史数据回测）
- ✅ 趋势分析（价格走势分析）
- ✅ 量价分析（成交量与价格关系）

**不适用场景**:
- ❌ 实时价格监控（数据延迟T+1）
- ❌ 盘中交易决策（非实时数据）
- ❌ 快速行情查询（数据量大，查询慢）

---

#### 对比总结

| 特性 | market_quotes | stock_daily_quotes |
|------|---------------|-------------------|
| **用途** | 实时/准实时行情快照 | 历史K线数据 |
| **更新频率** | 每30秒（交易时段） | 每日一次（收盘后） |
| **数据来源** | 实时行情接口 | 历史数据接口 |
| **主键字段** | `code` (唯一) | `symbol` + `trade_date` + `data_source` + `period` |
| **数据量** | ~5000条 | 数百万条 |
| **数据时效性** | 最新（延迟<1分钟） | 历史（T+1） |
| **典型用例** | 股票列表、自选股、实时监控 | K线图、技术分析、回测 |

**记忆口诀**:
- **market_quotes** = **Market** (市场) + **Quotes** (报价) = **实时行情**
- **stock_daily_quotes** = **Stock** (股票) + **Daily** (每日) + **Quotes** (报价) = **历史K线**

---

### 数据源优先级系统

TradingAgents-CN Pro 支持多数据源，并通过数据库配置管理优先级。

#### 数据源类型

| 数据源 | 类型 | 默认优先级 | 说明 |
|--------|------|-----------|------|
| `local` | 本地导入 | 10 | 用户通过API导入的数据 |
| `tushare` | Tushare | 3 | 需要Token，数据质量高 |
| `akshare` | AKShare | 2 | 免费，数据全面 |
| `baostock` | BaoStock | 1 | 免费，历史数据 |

#### 优先级配置

优先级存储在 `system_configs` 集合中：

```javascript
{
  "config_key": "data_source_configs",
  "config_value": [
    {
      "type": "local",
      "name": "本地数据",
      "priority": 10,
      "enabled": true,
      "market_category": "a_shares"
    },
    {
      "type": "tushare",
      "name": "Tushare",
      "priority": 3,
      "enabled": true,
      "market_category": "a_shares"
    }
  ]
}
```

#### 数据查询流程

1. **获取优先级配置**: 从 `system_configs` 读取数据源优先级
2. **按优先级排序**: 数字越大，优先级越高
3. **依次尝试**: 从优先级最高的数据源开始查询
4. **降级机制**: 如果高优先级数据源无数据，自动降级到下一个

**示例代码**:
```python
from app.core.data_source_priority import get_preferred_data_source_async

# 获取优先级最高的数据源
preferred_source = await get_preferred_data_source_async(market_category="a_shares")
# 返回: "local" (如果 local 优先级最高)
```

---

### 本地数据导入流程

用户可以通过批量导入API将数据导入到系统中，数据源标记为 `local`。

#### 支持的数据类型

1. **股票基础信息** → `stock_basic_info` (source='local')
2. **实时行情** → `market_quotes` (code=xxx)
3. **财务数据** → `stock_financial_data` (data_source='local')
4. **股票新闻** → `stock_news` (source='local')
5. **历史K线** → `stock_daily_quotes` (data_source='local')

#### 导入API

| API | 集合 | 数据源标记 |
|-----|------|-----------|
| `POST /api/stock-data/batch-save` | `stock_basic_info` | `source='local'` |
| `POST /api/quotes-data/batch-save` | `market_quotes` | 无标记 |
| `POST /api/financial-data/batch-save` | `stock_financial_data` | `data_source='local'` |
| `POST /api/news-data/save` | `stock_news` | `source='local'` |
| `POST /api/historical-data/batch-import` | `stock_daily_quotes` | `data_source='local'` |

#### 数据查询优先级

当 `local` 数据源优先级最高时：

1. **股票筛选**: 优先显示 `source='local'` 的股票
2. **K线数据**: 优先查询 `data_source='local'` 的历史数据
3. **财务数据**: 优先使用 `data_source='local'` 的财务数据

---

## 常见问题

### Q1: 为什么 `market_quotes` 使用 `code` 字段，而 `stock_daily_quotes` 使用 `symbol` 字段？

**历史原因**:
- `market_quotes` 是早期设计，使用 `code` 作为主键
- `stock_daily_quotes` 是后期重构，统一使用 `symbol` 作为标准字段

**兼容性处理**:
- 查询时同时支持 `code` 和 `symbol`
- 新数据写入时同时写入两个字段（逐步迁移）

### Q2: 为什么 K线接口优先使用 `stock_daily_quotes` 而不是 `market_quotes`？

**原因**:
- `market_quotes` 只有最新一条数据（实时快照）
- `stock_daily_quotes` 有完整的历史数据（数百条）
- K线图需要历史数据，所以必须使用 `stock_daily_quotes`

### Q3: 本地导入的数据存储在哪里？

**存储位置**:
- 股票基础信息: `stock_basic_info` (source='local')
- 实时行情: `market_quotes` (无特殊标记)
- 财务数据: `stock_financial_data` (data_source='local')
- 历史K线: `stock_daily_quotes` (data_source='local', period='daily')

### Q4: 如何确保本地数据优先被使用？

**配置方法**:
1. 在系统管理 → 数据源配置中，将 `local` 的优先级设为最高（如 10）
2. 系统会自动按优先级查询数据
3. 如果本地数据不存在，会自动降级到其他数据源

### Q5: `stock_daily_quotes` 支持哪些周期？

**支持的周期**:
- `daily` - 日线
- `weekly` - 周线
- `monthly` - 月线
- `5min` - 5分钟线
- `15min` - 15分钟线
- `30min` - 30分钟线
- `60min` - 60分钟线

---

## 相关文档

- [MongoDB 集合对比](../../architecture/database/MONGODB_COLLECTIONS_COMPARISON.md)
- [数据库初始化方案](../../../DATABASE_INIT_SOLUTION.md)
- [股票数据导入API](../../api/STOCK_DATA_IMPORT_API.md)
- [数据源优先级管理](../../../app/core/data_source_priority.py)

---

**最后更新**: 2026-01-25
**维护者**: TradingAgents-CN Pro Team


