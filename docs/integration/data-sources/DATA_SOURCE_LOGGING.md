# 数据来源日志功能说明

## 📋 概述

为了方便调试和追踪数据获取过程，系统在所有数据获取操作中添加了 **数据来源标记**，可以清楚地看到每次数据是从哪里获取的。

## 🎯 功能特性

### 1. **数据来源标记格式**

所有数据获取日志都使用统一格式：
```
[数据来源: xxx] 操作描述
```

### 2. **支持的数据来源类型**

#### MongoDB 数据库
- `[数据来源: MongoDB]` - 从 MongoDB 数据库获取
- `[数据来源: MongoDB-历史数据]` - MongoDB 历史行情数据
- `[数据来源: MongoDB-财务数据]` - MongoDB 财务数据
- `[数据来源: MongoDB-新闻数据]` - MongoDB 新闻数据
- `[数据来源: MongoDB-stock_basic_info]` - MongoDB 股票基本信息

#### 文件缓存
- `[数据来源: 文件缓存]` - 从本地文件缓存获取
- `[数据来源: 文件缓存-FINNHUB]` - FINNHUB 数据缓存
- `[数据来源: 文件缓存-Yahoo Finance]` - Yahoo Finance 数据缓存

#### API 调用
- `[数据来源: tushare]` - Tushare API
- `[数据来源: akshare]` - AKShare API
- `[数据来源: baostock]` - BaoStock API
- `[数据来源: API调用-FINNHUB]` - FINNHUB API
- `[数据来源: API调用-Yahoo Finance]` - Yahoo Finance API
- `[数据来源: API调用-AKShare]` - AKShare API（港股）
- `[数据来源: API调用成功-XXX]` - API 调用成功

#### 备用数据
- `[数据来源: 过期缓存]` - 使用过期的缓存数据
- `[数据来源: 备用数据]` - 生成的备用数据
- `[数据来源: 备用数据源]` - 降级到备用数据源
- `[数据来源: API失败]` - API 调用失败

#### 生成分析
- `[数据来源: 生成分析]` - 生成基本面分析
- `[数据来源: 生成分析成功]` - 分析生成成功

## 📊 数据获取流程

### A股数据获取流程

```
市场分析师
  ↓
get_stock_market_data_unified (agent_utils.py)
  ↓
get_china_stock_data_unified (interface.py)
  ↓
DataSourceManager.get_stock_data (data_source_manager.py)
  ↓
Provider (AKShare/Tushare/BaoStock)
  ↓
日志: [数据来源: akshare] 开始获取股票数据: 000001
日志: ✅ [数据来源: akshare] 成功获取股票数据: 000001 (455字符, 耗时0.19秒)
```

### 美股数据获取流程

```
市场分析师
  ↓
get_us_stock_data_cached (optimized_us_data.py)
  ↓
缓存检查
  ↓ (缓存命中)
日志: ⚡ [数据来源: 文件缓存-FINNHUB] 从缓存加载美股数据: AAPL
  ↓ (缓存未命中)
FINNHUB API / Yahoo Finance API
  ↓
日志: 🌐 [数据来源: API调用-FINNHUB] 从FINNHUB API获取数据: AAPL
日志: ✅ [数据来源: API调用成功-FINNHUB] FINNHUB数据获取成功: AAPL
```

## 🔍 日志示例

### 示例 1: A股数据从 AKShare 获取

```log
2025-09-30 17:30:12,310 | dataflows | INFO | 📊 [数据来源: akshare] 开始获取股票数据: 002475
2025-09-30 17:30:12,524 | dataflows | INFO | ✅ [数据来源: akshare] 成功获取股票数据: 002475 (455字符, 耗时0.19秒)
```

### 示例 2: 股票信息从 MongoDB 缓存获取

```log
2025-09-30 17:30:11,250 | dataflows | INFO | ✅ [数据来源: MongoDB-stock_basic_info] 缓存命中 | cache_hit=true code=002475
```

### 示例 3: 美股数据从 FINNHUB API 获取

```log
2025-09-30 17:17:20,655 | agents | INFO | 🌐 [数据来源: API调用-FINNHUB] 从FINNHUB API获取数据: AAPL
2025-09-30 17:17:21,807 | agents | INFO | ✅ [数据来源: API调用成功-FINNHUB] FINNHUB数据获取成功: AAPL
2025-09-30 17:17:21,809 | agents | INFO | 💾 [数据来源: finnhub] 数据已缓存: AAPL
```

### 示例 4: 港股数据降级处理

```log
2025-09-30 17:17:21,820 | agents | INFO | 🌐 [数据来源: API调用-FINNHUB] 从FINNHUB API获取数据: 0700.HK
2025-09-30 17:17:22,648 | agents | ERROR | ⚠️ [数据来源: API失败-FINNHUB] FINNHUB数据获取失败，尝试备用方案
2025-09-30 17:17:22,666 | agents | INFO | 🇭🇰 [数据来源: API调用-AKShare] 尝试使用AKShare获取港股数据: 0700.HK
2025-09-30 17:17:52,604 | agents | INFO | ✅ [数据来源: API调用成功-AKShare] AKShare港股数据获取成功: 0700.HK
```

### 示例 5: MongoDB 历史数据获取

```log
2025-09-30 17:17:20,177 | agents | INFO | 📊 [数据来源: MongoDB] 使用MongoDB历史数据: 000001 (42条记录)
```

### 示例 6: 财务数据从数据库缓存获取

```log
2025-09-30 17:30:27,316 | agents | INFO | 🔍 优先从数据库缓存获取002475财务数据
2025-09-30 17:30:27,410 | agents | INFO | ✅ [财务缓存] 从数据库缓存获取002475原始财务数据
```

## 🛠️ 实现细节

### 修改的文件

1. **`tradingagents/dataflows/data_source_manager.py`**
   - 在 `get_stock_data()` 方法中添加数据来源标记
   - 在 `get_stock_info()` 方法中添加数据来源标记
   - 在降级处理中添加数据来源标记

2. **`tradingagents/dataflows/optimized_china_data.py`**
   - 在 `get_stock_data()` 方法中添加数据来源标记
   - 在 `get_fundamentals_data()` 方法中添加数据来源标记
   - 在缓存、API、备用数据等各个环节添加标记

3. **`tradingagents/dataflows/optimized_us_data.py`**
   - 在 `get_stock_data()` 方法中添加数据来源标记
   - 区分 FINNHUB、Yahoo Finance、AKShare 等不同来源
   - 在缓存和 API 调用中添加标记

4. **`tradingagents/dataflows/enhanced_data_adapter.py`**
   - 在 `get_historical_data()` 方法中添加数据来源标记
   - 在 `get_financial_data()` 方法中添加数据来源标记
   - 在 `get_news_data()` 方法中添加数据来源标记

## 📈 使用场景

### 1. **调试数据获取问题**

当数据获取失败时，可以通过日志快速定位问题：
- 是缓存问题？
- 是 API 调用失败？
- 是数据源不可用？

### 2. **性能优化**

通过日志可以看到：
- 哪些数据从缓存获取（快速）
- 哪些数据需要 API 调用（慢速）
- 是否需要优化缓存策略

### 3. **数据源监控**

可以统计：
- 各个数据源的使用频率
- 各个数据源的成功率
- 降级处理的触发频率

### 4. **问题排查**

当用户报告数据问题时，可以通过日志：
- 确认数据来源
- 检查数据获取时间
- 验证数据完整性

## 🎯 最佳实践

### 1. **查看实时日志**

```bash
# 查看所有数据来源日志
tail -f logs/tradingagents.log | grep "数据来源"

# 查看特定股票的数据来源
tail -f logs/tradingagents.log | grep "数据来源" | grep "000001"

# 查看 API 调用日志
tail -f logs/tradingagents.log | grep "数据来源.*API"

# 查看缓存命中日志
tail -f logs/tradingagents.log | grep "数据来源.*缓存"
```

### 2. **分析数据来源分布**

```bash
# 统计各数据来源的使用次数
grep "数据来源" logs/tradingagents.log | grep -oP '\[数据来源: \K[^\]]+' | sort | uniq -c | sort -rn
```

### 3. **监控 API 失败率**

```bash
# 查看 API 失败日志
grep "数据来源.*失败" logs/tradingagents.log

# 统计失败次数
grep "数据来源.*失败" logs/tradingagents.log | wc -l
```

## 🔧 配置说明

### 启用 MongoDB 优先模式

```bash
# 设置环境变量
export TA_USE_APP_CACHE=true

# 或在 .env 文件中
TA_USE_APP_CACHE=true
```

启用后，日志会显示：
```
📊 [数据来源: MongoDB] 使用MongoDB历史数据: 000001 (42条记录)
```

### 禁用 MongoDB 模式

```bash
export TA_USE_APP_CACHE=false
```

禁用后，日志会显示：
```
🌐 [数据来源: akshare] 开始获取股票数据: 000001
```

## 📚 相关文档

- [新闻数据同步功能](NEWS_SYNC_FEATURE.md)
- [新闻情绪分析功能](NEWS_SENTIMENT_ANALYSIS.md)
- [增强数据集成](integration/enhanced_data_integration.md)
- [多周期数据同步](MULTI_PERIOD_DATA_SYNC_UPDATE.md)

## 🎉 总结

数据来源日志功能为系统提供了完整的数据获取追踪能力，使得：
- ✅ 调试更容易
- ✅ 性能优化有依据
- ✅ 问题排查更快速
- ✅ 数据来源清晰可见

所有数据获取操作都会在日志中明确标注数据来源，方便开发和运维人员快速定位问题！

