# 定时任务说明文档

## 📋 概述

TradingAgents-CN 使用 **APScheduler** 来管理定时任务，主要有两个核心任务：

1. **BasicsSyncService.run_full_sync** - 股票基础信息同步
2. **QuotesIngestionService.run_once** - 实时行情入库

## 🔄 任务1: 股票基础信息同步 (BasicsSyncService)

### 📝 功能说明

**任务ID**: `basics_sync_service`

**功能**：
- 从数据源（Tushare/AKShare/BaoStock）获取股票基础信息
- 包括：股票代码、名称、行业、地区、上市日期等
- 同步到 MongoDB 的 `stock_basics` 集合

**数据内容**：
```json
{
  "code": "000001",
  "name": "平安银行",
  "industry": "银行",
  "area": "深圳",
  "market": "主板",
  "list_date": "19910403",
  "total_mv": 1234567.89,
  "circ_mv": 987654.32,
  "roe": 12.34,
  "updated_at": "2025-10-17T06:30:00"
}
```

### ⏰ 执行时间

**默认配置**：
- **每天早上 06:30** 执行一次
- **时区**：Asia/Shanghai（北京时间）

**配置方式**：

1. **简单时间配置**（默认）：
   ```env
   SYNC_STOCK_BASICS_ENABLED=true
   SYNC_STOCK_BASICS_TIME=06:30
   TIMEZONE=Asia/Shanghai
   ```

2. **CRON 表达式配置**（高级）：
   ```env
   SYNC_STOCK_BASICS_ENABLED=true
   SYNC_STOCK_BASICS_CRON=30 6 * * *
   TIMEZONE=Asia/Shanghai
   ```

### 🔁 执行频率

**不是一直执行**，而是：
- ✅ **每天执行一次**（默认 06:30）
- ✅ **启动时执行一次**（应用启动后立即执行）
- ❌ **不会持续运行**

### 📊 执行流程

```
06:30:00 ─→ 任务触发
06:30:01 ─→ 检查是否已在运行（防止重复）
06:30:02 ─→ 从数据源获取股票列表（5000+ 只）
06:30:15 ─→ 获取最新交易日期
06:30:20 ─→ 获取每日基础数据（市值、ROE等）
06:30:45 ─→ 批量更新 MongoDB
06:31:00 ─→ 任务完成，状态更新为 "success"
```

**耗时**：通常 30-60 秒

### 🎯 为什么选择 06:30

1. **避开交易时段**：不影响实时行情采集
2. **数据已更新**：数据源通常在凌晨更新前一交易日数据
3. **用户使用前**：在用户开始使用系统前完成同步

### 🛠️ 如何修改执行时间

**方法1：修改 `.env` 文件**
```env
# 改为每天凌晨 2:00 执行
SYNC_STOCK_BASICS_TIME=02:00
```

**方法2：使用 CRON 表达式**
```env
# 每周一凌晨 2:00 执行
SYNC_STOCK_BASICS_CRON=0 2 * * 1
```

**方法3：禁用定时任务**
```env
# 禁用自动同步，只能手动触发
SYNC_STOCK_BASICS_ENABLED=false
```

### 📡 手动触发

可以通过 API 手动触发同步：

```bash
# 使用默认数据源
POST /api/sync/multi-source/stock_basics/run

# 指定优先数据源
POST /api/sync/multi-source/stock_basics/run?preferred_sources=akshare,baostock

# 强制执行（即使正在运行）
POST /api/sync/multi-source/stock_basics/run?force=true
```

---

## 📈 任务2: 实时行情入库 (QuotesIngestionService)

### 📝 功能说明

**任务ID**: `quotes_ingestion_service`

**功能**：
- 从数据源获取全市场实时行情快照
- 包括：最新价、涨跌幅、成交额、开高低收等
- 更新到 MongoDB 的 `market_quotes` 集合

**数据内容**：
```json
{
  "code": "000001",
  "close": 10.50,
  "pct_chg": 2.34,
  "amount": 123456789.0,
  "open": 10.20,
  "high": 10.60,
  "low": 10.15,
  "pre_close": 10.26,
  "trade_date": "20251017",
  "updated_at": "2025-10-17T14:30:00"
}
```

### ⏰ 执行时间

**默认配置**：
- **每 30 秒执行一次**
- **只在交易时段执行**：
  - 周一至周五
  - 上午：09:30 - 11:30
  - 下午：13:00 - 15:00

**配置方式**：
```env
QUOTES_INGEST_ENABLED=true
QUOTES_INGEST_INTERVAL_SECONDS=30
QUOTES_BACKFILL_ON_STARTUP=true
QUOTES_BACKFILL_ON_OFFHOURS=true
```

### 🔁 执行频率

**是一直执行的**，但有智能判断：

| 时间段 | 行为 | 说明 |
|--------|------|------|
| **交易时段** | ✅ 每30秒采集一次 | 获取实时行情并入库 |
| **非交易时段** | ⏭️ 跳过采集 | 保持上次收盘数据 |
| **休市日** | ⏭️ 跳过采集 | 周末和节假日不执行 |
| **启动时** | 🔄 补数一次 | 如果数据库为空，补充上一交易日收盘数据 |

### 📊 执行流程

**交易时段**：
```
14:30:00 ─→ 任务触发
14:30:01 ─→ 检查是否交易时段（是）
14:30:02 ─→ 从数据源获取全市场行情（5000+ 只）
14:30:10 ─→ 批量更新 MongoDB
14:30:12 ─→ 任务完成
14:30:30 ─→ 下一次触发
```

**非交易时段**：
```
20:00:00 ─→ 任务触发
20:00:01 ─→ 检查是否交易时段（否）
20:00:02 ─→ 检查是否需要补数
20:00:03 ─→ 跳过采集，保持上次数据
20:00:30 ─→ 下一次触发
```

### 🎯 为什么每 30 秒

1. **平衡实时性和性能**：
   - 太频繁（如5秒）：对数据源和数据库压力大
   - 太慢（如5分钟）：数据不够实时
   - 30秒是一个较好的平衡点

2. **数据源限制**：
   - 免费数据源通常有频率限制
   - 30秒可以避免触发限流

3. **用户体验**：
   - 30秒的延迟对大多数用户可接受
   - 不是高频交易系统，不需要秒级更新

### 🛠️ 如何修改执行频率

**方法1：修改 `.env` 文件**
```env
# 改为每 60 秒执行一次
QUOTES_INGEST_INTERVAL_SECONDS=60
```

**方法2：禁用定时任务**
```env
# 禁用实时行情采集
QUOTES_INGEST_ENABLED=false
```

**方法3：禁用休市补数**
```env
# 禁用启动时补数
QUOTES_BACKFILL_ON_STARTUP=false

# 禁用休市期补数
QUOTES_BACKFILL_ON_OFFHOURS=false
```

---

## 🔍 如何查看任务状态

### 1. 通过前端界面

访问前端页面，可以看到：
- **运行中**：任务正在执行
- **下次执行时间**：例如 "2025/10/17 06:30:00"
- **倒计时**：例如 "11小时后"

### 2. 通过 API 接口

```bash
# 查看股票基础信息同步状态
GET /api/sync/status

# 查看调度器状态
GET /api/scheduler/status

# 查看所有任务
GET /api/scheduler/jobs
```

### 3. 通过日志

查看应用日志：
```bash
# 股票基础信息同步日志
[INFO] Stock basics sync scheduled daily at 06:30 (Asia/Shanghai)
[INFO] Stock basics sync started
[INFO] Successfully fetched 5438 stocks from tushare
[INFO] Stock basics sync completed: 5438 total, 0 inserted, 5438 updated

# 实时行情入库日志
[INFO] 实时行情入库任务已启动: 每 30s
[INFO] ✅ 行情入库成功: 5438 只股票 (来源: tushare)
[INFO] ⏭️ 非交易时段，跳过行情采集
```

---

## ⚙️ 配置参数完整列表

### 股票基础信息同步

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `SYNC_STOCK_BASICS_ENABLED` | bool | `true` | 是否启用定时同步 |
| `SYNC_STOCK_BASICS_TIME` | string | `"06:30"` | 执行时间（HH:MM格式） |
| `SYNC_STOCK_BASICS_CRON` | string | `""` | CRON表达式（优先级高于TIME） |
| `TIMEZONE` | string | `"Asia/Shanghai"` | 时区 |

### 实时行情入库

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `QUOTES_INGEST_ENABLED` | bool | `true` | 是否启用实时行情采集 |
| `QUOTES_INGEST_INTERVAL_SECONDS` | int | `30` | 采集间隔（秒） |
| `QUOTES_BACKFILL_ON_STARTUP` | bool | `true` | 启动时是否补数 |
| `QUOTES_BACKFILL_ON_OFFHOURS` | bool | `true` | 休市期是否补数 |

---

## 🚨 常见问题

### Q1: 为什么任务显示"运行中"很长时间？

**A**: 可能的原因：
1. **数据源响应慢**：网络问题或数据源服务器慢
2. **数据量大**：5000+ 只股票需要一定时间处理
3. **任务卡住**：极少数情况下任务可能卡住

**解决方法**：
- 查看日志确认任务是否真的在运行
- 如果卡住，可以重启应用
- 使用 `force=true` 参数强制重新执行

### Q2: 可以禁用定时任务吗？

**A**: 可以，修改 `.env` 文件：
```env
SYNC_STOCK_BASICS_ENABLED=false
QUOTES_INGEST_ENABLED=false
```

然后重启应用。

### Q3: 如何立即执行一次同步？

**A**: 通过 API 手动触发：
```bash
POST /api/sync/multi-source/stock_basics/run
```

### Q4: 实时行情任务会一直运行吗？

**A**: 是的，但有智能判断：
- **交易时段**：每30秒采集一次
- **非交易时段**：跳过采集，不消耗资源

### Q5: 如何修改执行时间？

**A**: 修改 `.env` 文件中的配置，然后重启应用：
```env
# 改为每天凌晨 2:00
SYNC_STOCK_BASICS_TIME=02:00

# 或使用 CRON 表达式
SYNC_STOCK_BASICS_CRON=0 2 * * *
```

---

## 📚 相关文档

- [多数据源同步指南](./MULTI_SOURCE_SYNC_GUIDE.md)
- [API架构升级文档](./API_ARCHITECTURE_UPGRADE.md)
- [配置文件说明](../README.md#配置)

---

## ✅ 总结

| 任务 | 执行频率 | 是否一直运行 | 主要用途 |
|------|----------|-------------|----------|
| **BasicsSyncService** | 每天 06:30 | ❌ 否 | 同步股票基础信息 |
| **QuotesIngestionService** | 每 30 秒 | ✅ 是（交易时段） | 采集实时行情 |

**关键点**：
- ✅ BasicsSyncService **不是一直执行**，每天只执行一次
- ✅ QuotesIngestionService **是一直执行**，但只在交易时段采集数据
- ✅ 两个任务都可以通过配置文件禁用或修改
- ✅ 两个任务都可以通过 API 手动触发

