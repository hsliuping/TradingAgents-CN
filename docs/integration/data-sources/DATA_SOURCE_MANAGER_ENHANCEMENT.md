# DataSourceManager 增强方案

## 📋 当前状态分析

### ✅ 已经通过 DataSourceManager 管理的数据

| 数据类型 | 方法 | MongoDB 支持 | 状态 |
|---------|------|-------------|------|
| **历史行情数据** | `get_stock_data()` | ✅ 是 | ✅ 完成 |
| **股票基本信息** | `get_stock_info()` | ⚠️ 部分 | ⚠️ 未统一 |

### ❌ 还没有通过 DataSourceManager 管理的数据

| 数据类型 | 当前实现 | MongoDB 支持 | 问题 |
|---------|---------|-------------|------|
| **基本面/财务数据** | 直接调用 Tushare | ❌ 否 | 没有统一管理 |
| **实时行情数据** | 各自独立实现 | ❌ 否 | 没有统一管理 |
| **新闻数据** | 独立的服务 | ✅ 是 | 没有统一管理 |
| **周线/月线数据** | 通过 period 参数 | ⚠️ 部分 | 需要明确支持 |

## 🎯 改进目标

将**所有数据获取**都纳入 `DataSourceManager` 统一管理，实现：

1. **统一的数据源优先级**：MongoDB → Tushare → AKShare → BaoStock → TDX
2. **统一的降级机制**：任何数据源失败都自动降级
3. **统一的日志标记**：所有数据都显示 `[数据来源: xxx]`
4. **统一的配置管理**：通过 `TA_USE_APP_CACHE` 控制所有数据

## 📝 详细改进方案

### 1. **基本面/财务数据**

#### 当前实现
```python
# interface.py
def get_china_stock_fundamentals_tushare(ticker: str) -> str:
    """直接调用 Tushare"""
    from .data_source_manager import get_data_source_manager
    manager = get_data_source_manager()
    return manager.get_china_stock_fundamentals_tushare(ticker)

# data_source_manager.py
def get_china_stock_fundamentals_tushare(self, symbol: str) -> str:
    """只支持 Tushare"""
    adapter = get_tushare_adapter()
    return adapter.get_fundamentals(symbol)
```

#### 改进后
```python
# data_source_manager.py
def get_fundamentals_data(self, symbol: str) -> str:
    """
    获取基本面数据，支持多数据源和降级
    优先级：MongoDB → Tushare → AKShare → 生成分析
    """
    logger.info(f"📊 [数据来源: {self.current_source.value}] 开始获取基本面数据: {symbol}")
    
    try:
        # 根据数据源调用相应的获取方法
        if self.current_source == ChinaDataSource.MONGODB:
            return self._get_mongodb_fundamentals(symbol)
        elif self.current_source == ChinaDataSource.TUSHARE:
            return self._get_tushare_fundamentals(symbol)
        elif self.current_source == ChinaDataSource.AKSHARE:
            return self._get_akshare_fundamentals(symbol)
        else:
            return self._generate_fundamentals_analysis(symbol)
    except Exception as e:
        logger.error(f"❌ [数据来源: {self.current_source.value}失败] {e}")
        return self._try_fallback_fundamentals(symbol)

def _get_mongodb_fundamentals(self, symbol: str) -> str:
    """从 MongoDB 获取财务数据"""
    from tradingagents.dataflows.enhanced_data_adapter import get_enhanced_data_adapter
    adapter = get_enhanced_data_adapter()
    
    # 从 MongoDB 获取财务数据
    financial_data = adapter.get_financial_data(symbol)
    
    if financial_data:
        logger.info(f"✅ [数据来源: MongoDB-财务数据] 成功获取: {symbol}")
        return self._format_financial_data(financial_data)
    else:
        logger.warning(f"⚠️ [数据来源: MongoDB] 未找到财务数据: {symbol}")
        return self._try_fallback_fundamentals(symbol)

def _get_tushare_fundamentals(self, symbol: str) -> str:
    """从 Tushare 获取基本面数据"""
    from .tushare_adapter import get_tushare_adapter
    adapter = get_tushare_adapter()
    fundamentals = adapter.get_fundamentals(symbol)
    
    if fundamentals:
        logger.info(f"✅ [数据来源: Tushare-基本面] 成功获取: {symbol}")
        return fundamentals
    else:
        logger.warning(f"⚠️ [数据来源: Tushare] 未找到基本面数据: {symbol}")
        return self._try_fallback_fundamentals(symbol)

def _try_fallback_fundamentals(self, symbol: str) -> str:
    """基本面数据降级处理"""
    fallback_order = [
        ChinaDataSource.TUSHARE,
        ChinaDataSource.AKSHARE,
    ]
    
    for source in fallback_order:
        if source != self.current_source and source in self.available_sources:
            try:
                logger.info(f"🔄 尝试备用数据源获取基本面: {source.value}")
                
                if source == ChinaDataSource.TUSHARE:
                    result = self._get_tushare_fundamentals(symbol)
                elif source == ChinaDataSource.AKSHARE:
                    result = self._get_akshare_fundamentals(symbol)
                
                if result and "❌" not in result:
                    logger.info(f"✅ [数据来源: 备用数据源] 降级成功: {source.value}")
                    return result
            except Exception as e:
                logger.error(f"❌ 备用数据源{source.value}失败: {e}")
                continue
    
    # 所有数据源都失败，生成基本分析
    logger.warning(f"⚠️ [数据来源: 生成分析] 所有数据源失败，生成基本分析: {symbol}")
    return self._generate_fundamentals_analysis(symbol)
```

### 2. **股票基本信息统一**

#### 当前问题
`get_stock_info()` 方法中有 MongoDB 缓存逻辑，但不是通过 `ChinaDataSource.MONGODB` 管理的。

#### 改进方案
```python
def get_stock_info(self, symbol: str) -> Dict:
    """获取股票基本信息，统一使用数据源管理"""
    logger.info(f"📊 [数据来源: {self.current_source.value}] 开始获取股票信息: {symbol}")
    
    try:
        # 根据数据源调用相应的获取方法
        if self.current_source == ChinaDataSource.MONGODB:
            return self._get_mongodb_stock_info(symbol)
        elif self.current_source == ChinaDataSource.TUSHARE:
            return self._get_tushare_stock_info(symbol)
        elif self.current_source == ChinaDataSource.AKSHARE:
            return self._get_akshare_stock_info(symbol)
        else:
            return self._try_fallback_stock_info(symbol)
    except Exception as e:
        logger.error(f"❌ [数据来源: {self.current_source.value}失败] {e}")
        return self._try_fallback_stock_info(symbol)

def _get_mongodb_stock_info(self, symbol: str) -> Dict:
    """从 MongoDB 获取股票基本信息"""
    from .app_cache_adapter import get_basics_from_cache
    doc = get_basics_from_cache(symbol)
    
    if doc:
        logger.info(f"✅ [数据来源: MongoDB-stock_basic_info] 缓存命中: {symbol}")
        return self._format_stock_info(doc)
    else:
        logger.warning(f"⚠️ [数据来源: MongoDB] 未找到股票信息: {symbol}")
        return self._try_fallback_stock_info(symbol)
```

### 3. **周线/月线数据明确支持**

#### 改进方案
```python
def get_stock_data(
    self, 
    symbol: str, 
    start_date: str, 
    end_date: str,
    period: str = "daily"  # 新增参数：daily/weekly/monthly
) -> str:
    """
    获取股票数据，支持多周期
    
    Args:
        symbol: 股票代码
        start_date: 开始日期
        end_date: 结束日期
        period: 数据周期（daily/weekly/monthly）
    """
    logger.info(f"📊 [数据来源: {self.current_source.value}] 开始获取{period}数据: {symbol}")
    
    try:
        if self.current_source == ChinaDataSource.MONGODB:
            return self._get_mongodb_data(symbol, start_date, end_date, period)
        elif self.current_source == ChinaDataSource.TUSHARE:
            return self._get_tushare_data(symbol, start_date, end_date, period)
        # ... 其他数据源
    except Exception as e:
        logger.error(f"❌ [数据来源: {self.current_source.value}失败] {e}")
        return self._try_fallback_sources(symbol, start_date, end_date, period)

def _get_mongodb_data(
    self, 
    symbol: str, 
    start_date: str, 
    end_date: str,
    period: str = "daily"
) -> str:
    """从 MongoDB 获取多周期数据"""
    from tradingagents.dataflows.enhanced_data_adapter import get_enhanced_data_adapter
    adapter = get_enhanced_data_adapter()
    
    # 从 MongoDB 获取指定周期的数据
    df = adapter.get_historical_data(symbol, start_date, end_date, period=period)
    
    if df is not None and not df.empty:
        logger.info(f"✅ [数据来源: MongoDB-{period}] 成功获取: {symbol} ({len(df)}条)")
        return df.to_string()
    else:
        logger.warning(f"⚠️ [数据来源: MongoDB] 未找到{period}数据: {symbol}")
        return self._try_fallback_sources(symbol, start_date, end_date, period)
```

### 4. **新闻数据统一管理**

#### 改进方案
```python
def get_news_data(
    self, 
    symbol: str, 
    hours_back: int = 24,
    limit: int = 20
) -> List[Dict]:
    """
    获取新闻数据，支持多数据源
    优先级：MongoDB → Tushare → AKShare → Finnhub
    """
    logger.info(f"📰 [数据来源: {self.current_source.value}] 开始获取新闻: {symbol}")
    
    try:
        if self.current_source == ChinaDataSource.MONGODB:
            return self._get_mongodb_news(symbol, hours_back, limit)
        elif self.current_source == ChinaDataSource.TUSHARE:
            return self._get_tushare_news(symbol, hours_back, limit)
        elif self.current_source == ChinaDataSource.AKSHARE:
            return self._get_akshare_news(symbol, hours_back, limit)
        else:
            return self._try_fallback_news(symbol, hours_back, limit)
    except Exception as e:
        logger.error(f"❌ [数据来源: {self.current_source.value}失败] {e}")
        return self._try_fallback_news(symbol, hours_back, limit)

def _get_mongodb_news(self, symbol: str, hours_back: int, limit: int) -> List[Dict]:
    """从 MongoDB 获取新闻数据"""
    from tradingagents.dataflows.enhanced_data_adapter import get_enhanced_data_adapter
    adapter = get_enhanced_data_adapter()
    
    news_data = adapter.get_news_data(symbol, hours_back=hours_back)
    
    if news_data:
        logger.info(f"✅ [数据来源: MongoDB-新闻] 成功获取: {symbol} ({len(news_data)}条)")
        return news_data[:limit]
    else:
        logger.warning(f"⚠️ [数据来源: MongoDB] 未找到新闻: {symbol}")
        return self._try_fallback_news(symbol, hours_back, limit)
```

## 🔄 实施步骤

### 阶段 1：基本面数据统一（优先级最高）
1. ✅ 在 `DataSourceManager` 中添加 `get_fundamentals_data()` 方法
2. ✅ 实现 `_get_mongodb_fundamentals()` 方法
3. ✅ 实现 `_get_tushare_fundamentals()` 方法
4. ✅ 实现 `_try_fallback_fundamentals()` 降级机制
5. ✅ 更新 `interface.py` 中的调用

### 阶段 2：股票信息统一
1. ⬜ 重构 `get_stock_info()` 方法
2. ⬜ 实现 `_get_mongodb_stock_info()` 方法
3. ⬜ 统一数据源管理逻辑

### 阶段 3：多周期数据支持
1. ⬜ 在 `get_stock_data()` 中添加 `period` 参数
2. ⬜ 更新所有数据源方法支持 `period`
3. ⬜ 更新 MongoDB 查询逻辑

### 阶段 4：新闻数据统一
1. ⬜ 添加 `get_news_data()` 方法
2. ⬜ 实现各数据源的新闻获取
3. ⬜ 实现降级机制

## 📊 预期效果

### 统一的数据获取流程

```
市场分析师
  ↓
统一接口（interface.py）
  ↓
DataSourceManager（统一管理）
  ↓
数据源选择（基于优先级）
  ├─ MongoDB（最高优先级）
  ├─ Tushare
  ├─ AKShare
  ├─ BaoStock
  └─ TDX
  ↓
自动降级（失败时）
  ↓
返回数据（带数据来源标记）
```

### 统一的日志输出

```log
📊 [数据来源: mongodb] 开始获取历史数据: 000001
✅ [数据来源: MongoDB] 成功获取数据: 000001 (42条记录)

📊 [数据来源: mongodb] 开始获取基本面数据: 000001
✅ [数据来源: MongoDB-财务数据] 成功获取: 000001

📊 [数据来源: mongodb] 开始获取股票信息: 000001
✅ [数据来源: MongoDB-stock_basic_info] 缓存命中: 000001

📰 [数据来源: mongodb] 开始获取新闻: 000001
✅ [数据来源: MongoDB-新闻] 成功获取: 000001 (15条)
```

## 🎯 优势总结

1. **统一管理**：所有数据获取都在一个地方管理
2. **优先级明确**：MongoDB 始终是最高优先级
3. **自动降级**：任何数据源失败都自动切换
4. **配置简单**：一个环境变量控制所有数据
5. **日志清晰**：所有数据都标注来源
6. **易于维护**：新增数据源只需修改一个地方
7. **性能优化**：充分利用 MongoDB 缓存

## 💡 建议

**建议优先实施阶段 1（基本面数据统一）**，因为：
1. 基本面数据是市场分析师最常用的数据
2. 当前完全没有 MongoDB 支持
3. 实施难度相对较低
4. 效果立竿见影

实施完成后，可以看到明显的性能提升和日志改善。

