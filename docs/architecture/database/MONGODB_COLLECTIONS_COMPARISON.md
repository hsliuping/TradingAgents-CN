# MongoDB 集合对比：market_quotes vs stock_daily_quotes

## 📊 概览对比

| 特性 | market_quotes | stock_daily_quotes |
|------|---------------|-------------------|
| **用途** | 实时/准实时行情快照 | 历史K线数据（日/周/月/分钟线） |
| **更新频率** | 每30秒（交易时段） | 每日一次（收盘后） |
| **数据来源** | 实时行情接口 | 历史数据接口 |
| **主键字段** | `code` (唯一) | `symbol` + `trade_date` + `data_source` + `period` (复合唯一) |
| **数据量** | ~5000条（全市场股票） | 数百万条（每只股票数百条历史记录） |
| **数据时效性** | 最新（延迟<1分钟） | 历史（T+1，收盘后更新） |
| **典型用例** | 股票列表、自选股、实时监控 | K线图、技术分析、回测 |

---

## 🗄️ market_quotes 集合

### 用途
存储**全市场股票的最新行情快照**，用于快速获取股票的当前价格、涨跌幅等实时信息。

### 数据结构

```json
{
  "code": "600036",              // 6位股票代码（主键，唯一）
  "close": 46.50,                // 最新价（当前价格）
  "open": 45.23,                 // 今日开盘价
  "high": 46.78,                 // 今日最高价
  "low": 45.01,                  // 今日最低价
  "pre_close": 45.42,            // 昨日收盘价
  "pct_chg": 2.38,               // 涨跌幅(%)
  "amount": 567890123.45,        // 成交额(元)
  "volume": 12345678,            // 成交量(股)
  "trade_date": "20251017",      // 交易日期
  "updated_at": ISODate("2025-10-17T02:31:26.000Z")  // 更新时间
}
```

### 索引

```javascript
// 唯一索引（主键）
db.market_quotes.createIndex({ "code": 1 }, { unique: true })

// 更新时间索引（用于查询最新数据）
db.market_quotes.createIndex({ "updated_at": 1 })
```

### 数据来源

**实时行情入库服务** (`QuotesIngestionService`)：
- 文件：`app/services/quotes_ingestion_service.py`
- 调度频率：每30秒（可配置 `QUOTES_INGEST_INTERVAL_SECONDS`）
- 数据源优先级：AKShare > BaoStock > Tushare
- 交易时段：09:30-15:00（自动判断）
- 非交易时段：保持上次收盘数据

**写入逻辑**：
```python
# 批量 upsert（更新或插入）
UpdateOne(
    {"code": "600036"},  # 查询条件
    {"$set": {
        "code": "600036",
        "close": 46.50,
        "pct_chg": 2.38,
        # ... 其他字段
        "updated_at": datetime.now()
    }},
    upsert=True  # 不存在则插入
)
```

### 使用场景

#### 1. 股票列表页面
```python
# 获取多只股票的最新行情
codes = ["600036", "000001", "000002"]
quotes = await db.market_quotes.find(
    {"code": {"$in": codes}},
    {"_id": 0}
).to_list(length=None)
```

#### 2. 自选股实时行情
```python
# app/services/favorites_service.py (第99-112行)
coll = db["market_quotes"]
cursor = coll.find(
    {"code": {"$in": codes}},
    {"code": 1, "close": 1, "pct_chg": 1, "amount": 1}
)
docs = await cursor.to_list(length=None)
```

#### 3. 股票详情页快照
```python
# app/routers/stocks.py (第27-46行)
# GET /api/stocks/{code}/quote
q = await db["market_quotes"].find_one({"code": code6}, {"_id": 0})
```

### 配置参数

```bash
# .env 文件
QUOTES_INGEST_ENABLED=true                    # 启用实时行情入库
QUOTES_INGEST_INTERVAL_SECONDS=30             # 采集间隔（秒）
QUOTES_BACKFILL_ON_OFFHOURS=true              # 非交易时段是否补数
```

---

## 📈 stock_daily_quotes 集合

### 用途
存储**股票的历史K线数据**，支持多周期（日线、周线、月线、分钟线），用于K线图展示和技术分析。

### 数据结构

```json
{
  "symbol": "600036",            // 6位股票代码（主键之一）
  "full_symbol": "600036.SH",    // 完整代码（带市场后缀）
  "market": "CN",                // 市场标识
  "trade_date": "20251016",      // 交易日期（主键之一）
  "period": "daily",             // 周期（主键之一）：daily/weekly/monthly/5min/15min/30min/60min
  "data_source": "akshare",      // 数据源（主键之一）：tushare/akshare/baostock
  
  // OHLCV 数据
  "open": 45.23,                 // 开盘价
  "high": 46.78,                 // 最高价
  "low": 45.01,                  // 最低价
  "close": 46.50,                // 收盘价
  "pre_close": 45.42,            // 前收盘价
  "volume": 12345678,            // 成交量(股)
  "amount": 567890123.45,        // 成交额(元)
  
  // 涨跌数据
  "change": 1.08,                // 涨跌额
  "pct_chg": 2.38,               // 涨跌幅(%)
  
  // 其他指标
  "turnover_rate": 1.23,         // 换手率(%)
  "volume_ratio": 1.05,          // 量比
  
  // 元数据
  "created_at": ISODate("2025-10-17T02:00:00.000Z"),
  "updated_at": ISODate("2025-10-17T02:00:00.000Z"),
  "version": 1
}
```

### 索引

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

### 数据来源

**历史数据同步服务** (`HistoricalDataService`)：
- 文件：`app/services/historical_data_service.py`
- 调度频率：每日一次（收盘后，如17:00）
- 数据源优先级：Tushare > AKShare > BaoStock
- 同步方式：增量同步（只同步缺失的日期）

**写入逻辑**：
```python
# app/services/historical_data_service.py (第113-143行)
doc = {
    "symbol": symbol,
    "full_symbol": self._get_full_symbol(symbol, market),
    "market": market,
    "trade_date": trade_date,
    "period": period,
    "data_source": data_source,
    "open": self._safe_float(row.get('open')),
    "high": self._safe_float(row.get('high')),
    "low": self._safe_float(row.get('low')),
    "close": self._safe_float(row.get('close')),
    # ... 其他字段
    "created_at": now,
    "updated_at": now,
    "version": 1
}

# 批量 upsert
await collection.update_one(
    {
        "symbol": doc["symbol"],
        "trade_date": doc["trade_date"],
        "data_source": doc["data_source"],
        "period": doc["period"]
    },
    {"$set": doc},
    upsert=True
)
```

### 使用场景

#### 1. K线图数据
```python
# app/routers/stocks.py (第180-240行)
# GET /api/stocks/{code}/kline?period=day&limit=200
from tradingagents.dataflows.cache.mongodb_cache_adapter import get_mongodb_cache_adapter

adapter = get_mongodb_cache_adapter()
df = adapter.get_historical_data(code, start_date, end_date, period="daily")
```

#### 2. 技术分析
```python
# 获取最近200个交易日的数据用于计算技术指标
df = await db.stock_daily_quotes.find({
    "symbol": "600036",
    "period": "daily"
}).sort("trade_date", -1).limit(200).to_list(length=None)
```

#### 3. 回测系统
```python
# 获取指定时间范围的历史数据
df = await db.stock_daily_quotes.find({
    "symbol": "600036",
    "period": "daily",
    "trade_date": {
        "$gte": "20240101",
        "$lte": "20241231"
    }
}).sort("trade_date", 1).to_list(length=None)
```

### 配置参数

```bash
# .env 文件
# AKShare 历史数据同步
SYNC_AKSHARE_HISTORICAL_ENABLED=true
SYNC_AKSHARE_HISTORICAL_CRON=0 18 * * 1-5    # 每个交易日17:00

# BaoStock 日K线同步
SYNC_BAOSTOCK_DAILY_QUOTES_ENABLED=true
SYNC_BAOSTOCK_DAILY_QUOTES_CRON=0 18 * * 1-5  # 每个交易日16:00

# Tushare 历史数据同步
SYNC_TUSHARE_HISTORICAL_ENABLED=false         # 需要Token
SYNC_TUSHARE_HISTORICAL_CRON=0 18 * * 1-5
```

---

## 🔄 数据流程对比

### market_quotes 数据流程

```
实时行情接口 (AKShare/BaoStock)
         ↓
QuotesIngestionService (每30秒)
         ↓
    批量 upsert
         ↓
market_quotes 集合 (5000条)
         ↓
前端/API 查询 (实时行情)
```

### stock_daily_quotes 数据流程

```
历史数据接口 (Tushare/AKShare/BaoStock)
         ↓
HistoricalDataService (每日17:00)
         ↓
    批量 upsert
         ↓
stock_daily_quotes 集合 (数百万条)
         ↓
前端/API 查询 (K线图)
```

---

## 🎯 使用建议

### 何时使用 market_quotes

✅ **适用场景**：
- 股票列表页面（显示最新价格）
- 自选股监控（实时涨跌）
- 股票详情页快照（当前价格）
- 实时排行榜（涨幅榜、跌幅榜）
- 交易决策（当前价格判断）

❌ **不适用场景**：
- K线图展示（需要历史数据）
- 技术分析（需要多日数据）
- 回测系统（需要历史数据）
- 趋势分析（需要时间序列）

### 何时使用 stock_daily_quotes

✅ **适用场景**：
- K线图展示（日线、周线、月线）
- 技术指标计算（MA、MACD、KDJ等）
- 回测系统（历史数据回测）
- 趋势分析（价格走势分析）
- 量价分析（成交量与价格关系）

❌ **不适用场景**：
- 实时价格监控（数据延迟T+1）
- 盘中交易决策（非实时数据）
- 快速行情查询（数据量大，查询慢）

---

## 🔧 常见问题

### Q1: 为什么 market_quotes 使用 `code` 字段，而 stock_daily_quotes 使用 `symbol` 字段？

**历史原因**：
- `market_quotes` 是早期设计，使用 `code` 作为主键
- `stock_daily_quotes` 是后期重构，统一使用 `symbol` 作为标准字段

**兼容性处理**：
- 查询时同时支持 `code` 和 `symbol`：`{"$or": [{"symbol": code}, {"code": code}]}`
- 新数据写入时同时写入两个字段（逐步迁移）

### Q2: 为什么 K线接口优先使用 stock_daily_quotes 而不是 market_quotes？

**原因**：
1. **数据完整性**：`stock_daily_quotes` 包含完整的历史数据，`market_quotes` 只有最新一条
2. **多周期支持**：`stock_daily_quotes` 支持日/周/月/分钟线，`market_quotes` 只有当日数据
3. **数据稳定性**：`stock_daily_quotes` 是收盘后的确定数据，`market_quotes` 是实时变化的

### Q3: 如果 stock_daily_quotes 为空怎么办？

**降级方案**：
```python
# app/routers/stocks.py (第242-259行)
if not items:  # MongoDB 无数据
    logger.info(f"📡 MongoDB 无数据，降级到外部 API")
    mgr = DataSourceManager()
    items, source = await asyncio.wait_for(
        asyncio.to_thread(mgr.get_kline_with_fallback, code, period, limit, adj),
        timeout=10.0
    )
```

**解决方案**：
1. 手动触发历史数据同步：`POST /api/multi-source-sync/historical`
2. 启用定时任务：`SYNC_AKSHARE_HISTORICAL_ENABLED=true`
3. 等待定时任务自动同步（每日17:00）

### Q4: 如何统一两个集合的字段名？

**迁移脚本**：
```bash
# 运行字段标准化脚本
python scripts/migration/standardize_stock_code_fields.py
```

**脚本功能**：
- 为 `market_quotes` 添加 `symbol` 字段（从 `code` 复制）
- 为 `stock_daily_quotes` 添加 `code` 字段（从 `symbol` 复制）
- 创建统一的索引
- 保持向后兼容

---

## 📚 相关文档

- [K线数据来源说明](KLINE_DATA_SOURCE.md)
- [定时任务配置指南](scheduled_tasks_configuration.md)
- [数据同步服务文档](../app/services/README.md)

---

## 🎉 总结

| 集合 | 核心特点 | 典型查询 |
|------|---------|---------|
| **market_quotes** | 实时快照，小数据量，高频更新 | `db.market_quotes.findOne({"code": "600036"})` |
| **stock_daily_quotes** | 历史数据，大数据量，低频更新 | `db.stock_daily_quotes.find({"symbol": "600036", "period": "daily"}).sort("trade_date", -1).limit(200)` |

**记忆口诀**：
- **market_quotes** = **Market** (市场) + **Quotes** (报价) = **实时行情**
- **stock_daily_quotes** = **Stock** (股票) + **Daily** (每日) + **Quotes** (报价) = **历史K线**

