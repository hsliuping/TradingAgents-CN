# TradingAgents 股票数据获取方法整理

## 📋 概述

本文档整理了 `D:\code\TradingAgents-CN\tradingagents` 目录下所有股票数据获取相关的函数和方法，按照架构层次和数据类型进行分类。

## 🏗️ 架构层次

### 1. 🎯 用户接口层

#### API接口 (`app/`)
- **后端API路由**: 提供RESTful接口
- **Web界面**: 前端交互界面
- **CLI工具**: 命令行工具

#### 统一API (`tradingagents/api/stock_api.py`)
```python
def get_stock_info(stock_code: str) -> Optional[Dict[str, Any]]
def get_stock_data(stock_code: str, start_date: str = None, end_date: str = None) -> str
```

### 2. 🔄 统一接口层

#### 股票API (`tradingagents/dataflows/stock_api.py`)
```python
def get_stock_info(stock_code: str) -> Optional[Dict[str, Any]]
def get_stock_data(stock_code: str, start_date: str, end_date: str) -> str
```

#### 接口层 (`tradingagents/dataflows/interface.py`)
```python
# 中国股票数据
def get_china_stock_data_unified(symbol: str, start_date: str, end_date: str) -> str
def get_china_stock_info_unified(symbol: str) -> Dict
def get_china_stock_fundamentals_tushare(symbol: str) -> str

# 港股数据
def get_hk_stock_data_unified(symbol: str, start_date: str, end_date: str) -> str

# 美股数据
def get_YFin_data(symbol: str, start_date: str, end_date: str) -> str
def get_YFin_data_window(symbol: str, start_date: str, end_date: str) -> str

# 市场自动识别
def get_stock_data_by_market(symbol: str, start_date: str = None, end_date: str = None) -> str

# 财务报表
def get_simfin_balance_sheet(symbol: str) -> str
def get_simfin_cashflow(symbol: str) -> str
def get_simfin_income_statements(symbol: str) -> str

# 新闻和情绪
def get_finnhub_news(symbol: str) -> str
def get_finnhub_company_insider_sentiment(symbol: str) -> str
def get_google_news(query: str) -> str
def get_reddit_global_news() -> str
def get_reddit_company_news(symbol: str) -> str

# 技术分析
def get_stock_stats_indicators_window(symbol: str, start_date: str, end_date: str) -> str
def get_stockstats_indicator(symbol: str, indicator: str) -> str
```

#### 数据源管理器 (`tradingagents/dataflows/data_source_manager.py`)
```python
class DataSourceManager:
    def get_stock_data(self, symbol: str, start_date: str, end_date: str) -> str
    def get_stock_info(self, symbol: str) -> Dict
    def switch_data_source(self, source: ChinaDataSource)
    def get_available_sources(self) -> List[ChinaDataSource]
```

### 3. ⚡ 优化数据提供器层

#### 中国股票数据提供器 (`tradingagents/dataflows/optimized_china_data.py`)
```python
class OptimizedChinaDataProvider:
    # 历史数据
    def get_stock_data(self, symbol: str, start_date: str, end_date: str, force_refresh: bool = False) -> str
    
    # 基本面数据
    def get_fundamentals_data(self, symbol: str, force_refresh: bool = False) -> str
    
    # 内部方法
    def _get_stock_basic_info_only(self, symbol: str) -> Dict
    def _get_real_financial_metrics(self, symbol: str, price_value: float) -> dict
    def _parse_akshare_financial_data(self, financial_data: dict, stock_info: dict, price_value: float) -> dict
    def _parse_financial_data(self, financial_data: dict, stock_info: dict, price_value: float) -> dict
    
    # 缓存方法
    def _get_cached_raw_financial_data(self, symbol: str) -> dict
    def _get_cached_stock_info(self, symbol: str) -> dict
    def _cache_raw_financial_data(self, symbol: str, financial_data: dict, stock_info: dict)
    def _restore_financial_data_format(self, cached_data: dict) -> dict

# 便捷函数
def get_china_stock_data_cached(symbol: str, start_date: str, end_date: str, force_refresh: bool = False) -> str
def get_china_fundamentals_cached(symbol: str, force_refresh: bool = False) -> str
```

#### 美股数据提供器 (`tradingagents/dataflows/optimized_us_data.py`)
```python
class OptimizedUSDataProvider:
    def get_stock_data(self, symbol: str, start_date: str, end_date: str, force_refresh: bool = False) -> str
    def _format_stock_data(self, symbol: str, data: pd.DataFrame, start_date: str, end_date: str) -> str
    def _wait_for_rate_limit(self)

# 便捷函数
def get_us_stock_data_cached(symbol: str, start_date: str, end_date: str, force_refresh: bool = False) -> str
```

#### 港股数据工具 (`tradingagents/dataflows/hk_stock_utils.py`)
```python
class HKStockDataProvider:
    def get_stock_data(self, symbol: str, start_date: str, end_date: str) -> Optional[pd.DataFrame]
    def get_stock_info(self, symbol: str) -> Dict[str, Any]

# 便捷函数
def get_hk_stock_data(symbol: str, start_date: str = None, end_date: str = None) -> str
def get_hk_stock_info(symbol: str) -> Dict[str, Any]
```

### 4. 🔌 数据源适配器层

#### Tushare适配器 (`tradingagents/dataflows/tushare_utils.py`)
```python
class TushareProvider:
    # 基础数据
    def get_stock_list(self) -> pd.DataFrame
    def get_stock_info(self, symbol: str) -> Dict
    def get_stock_daily(self, symbol: str, start_date: str = None, end_date: str = None) -> pd.DataFrame
    
    # 财务数据
    def get_financial_data(self, symbol: str, period: str = "20231231") -> Dict
    def get_balance_sheet(self, symbol: str, period: str = "20231231") -> pd.DataFrame
    def get_income_statement(self, symbol: str, period: str = "20231231") -> pd.DataFrame
    def get_cashflow_statement(self, symbol: str, period: str = "20231231") -> pd.DataFrame
    
    # 实用方法
    def _normalize_symbol(self, symbol: str) -> str
    def _format_stock_data(self, data: pd.DataFrame, symbol: str) -> str

# 便捷函数
def get_china_stock_data_tushare(symbol: str, start_date: str = None, end_date: str = None) -> pd.DataFrame
def get_china_stock_info_tushare(symbol: str) -> Dict
def search_china_stocks_tushare(keyword: str) -> List[Dict]
def get_china_stock_fundamentals_tushare(symbol: str) -> str
```

#### AKShare适配器 (`tradingagents/dataflows/akshare_utils.py`)
```python
class AKShareProvider:
    # 基础数据
    def get_stock_data(self, symbol: str, start_date: str = None, end_date: str = None) -> Optional[pd.DataFrame]
    def get_stock_info(self, symbol: str) -> Dict[str, Any]
    def get_stock_list(self) -> Optional[pd.DataFrame]
    
    # 港股数据
    def get_hk_stock_data(self, symbol: str, start_date: str = None, end_date: str = None) -> Optional[pd.DataFrame]
    def get_hk_stock_info(self, symbol: str) -> Dict[str, Any]
    
    # 财务数据
    def get_financial_data(self, symbol: str) -> Dict[str, Any]
    
    # 实时数据
    def get_realtime_data(self, symbol: str) -> Dict[str, Any]

# 便捷函数
def get_hk_stock_data_akshare(symbol: str, start_date: str = None, end_date: str = None) -> str
```

#### Yahoo Finance适配器 (`tradingagents/dataflows/yfin_utils.py`)
```python
class YFinanceUtils:
    def get_stock_data(symbol: str, start_date: str, end_date: str, save_path: SavePathType = None) -> DataFrame
```

#### BaoStock适配器 (`tradingagents/dataflows/baostock_utils.py`)
```python
class BaoStockProvider:
    def get_stock_data(self, symbol: str, start_date: str, end_date: str) -> Optional[pd.DataFrame]
    def get_stock_info(self, symbol: str) -> Dict[str, Any]
```

#### TDX适配器 (`tradingagents/dataflows/tdx_utils.py`)
```python
class TongDaXinDataProvider:
    def get_stock_data(self, symbol: str, start_date: str, end_date: str) -> str
    def get_stock_info(self, symbol: str) -> Dict[str, Any]
```

### 5. 🎯 专业服务层

#### 股票数据服务 (`tradingagents/dataflows/stock_data_service.py`)
```python
class StockDataService:
    def get_stock_basic_info(self, stock_code: str = None) -> Optional[Dict[str, Any]]
    def get_stock_data_with_fallback(self, stock_code: str, start_date: str, end_date: str) -> str
    def get_stock_list_with_fallback(self) -> List[Dict[str, Any]]
```

#### 实时新闻工具 (`tradingagents/dataflows/realtime_news_utils.py`)
```python
class RealtimeNewsAggregator:
    def get_realtime_stock_news(self, ticker: str, hours_back: int = 6, max_news: int = 10) -> List[NewsItem]
    def get_realtime_market_news(self, hours_back: int = 6, max_news: int = 20) -> List[NewsItem]
```

## 📊 数据类型分类

### 1. 基础股票信息
- **股票列表**: `get_stock_list()` 系列方法
- **股票基本信息**: `get_stock_info()` 系列方法
- **股票搜索**: `search_china_stocks_tushare()`

### 2. 历史价格数据
- **日线数据**: `get_stock_data()` 系列方法
- **K线数据**: `get_kline()` 方法
- **技术指标**: `get_stock_stats_indicators_window()`, `get_stockstats_indicator()`

### 3. 财务数据
- **基本面分析**: `get_fundamentals_data()`, `get_china_stock_fundamentals_tushare()`
- **财务报表**: `get_balance_sheet()`, `get_income_statement()`, `get_cashflow_statement()`
- **财务指标**: `get_financial_data()` 系列方法

### 4. 实时数据
- **实时行情**: `get_realtime_data()`, `get_realtime_quotes()`
- **实时新闻**: `get_realtime_stock_news()`, `get_realtime_market_news()`

### 5. 新闻和情绪数据
- **公司新闻**: `get_finnhub_news()`, `get_google_news()`
- **社交媒体**: `get_reddit_company_news()`, `get_reddit_global_news()`
- **内部交易**: `get_finnhub_company_insider_sentiment()`, `get_finnhub_company_insider_transactions()`

## 🔄 数据流向

### 缓存优先级 (当 `TA_USE_APP_CACHE=true` 时)
1. **MongoDB数据库缓存** (stock_basic_info, market_quotes, financial_data_cache)
2. **Redis缓存** (实时数据)
3. **文件缓存** (历史数据)
4. **API调用** (外部数据源)

### 数据源优先级
1. **中国A股**: Tushare → AKShare → BaoStock → TDX
2. **港股**: AKShare → Yahoo Finance → Finnhub
3. **美股**: Yahoo Finance → Finnhub

## 🎯 使用建议

### 推荐使用的统一接口
```python
# 中国A股 - 推荐
from tradingagents.dataflows import get_china_stock_data_unified, get_china_stock_info_unified

# 美股 - 推荐  
from tradingagents.dataflows.optimized_us_data import get_us_stock_data_cached

# 港股 - 推荐
from tradingagents.dataflows.interface import get_hk_stock_data_unified

# 自动识别市场 - 最推荐
from tradingagents.dataflows.interface import get_stock_data_by_market
```

### 基本面分析专用
```python
# 中国A股基本面 - 优化版本
from tradingagents.dataflows.optimized_china_data import get_china_fundamentals_cached
```

## 📝 注意事项

1. **缓存配置**: 通过 `TA_USE_APP_CACHE` 环境变量控制是否优先使用数据库缓存
2. **API限制**: 各数据源都有API调用频率限制，系统内置了限流机制
3. **数据质量**: Tushare > AKShare > BaoStock > TDX，按质量递减
4. **错误处理**: 所有方法都包含完整的错误处理和降级机制
5. **日志记录**: 详细的日志记录便于调试和监控

## 📋 详细方法参数说明

### 核心数据获取方法

#### 1. 历史价格数据获取

**`get_stock_data(symbol, start_date, end_date, force_refresh=False)`**
- **参数**:
  - `symbol`: 股票代码 (str) - 支持6位A股代码、港股代码、美股代码
  - `start_date`: 开始日期 (str) - 格式 'YYYY-MM-DD'
  - `end_date`: 结束日期 (str) - 格式 'YYYY-MM-DD'
  - `force_refresh`: 强制刷新缓存 (bool) - 默认False
- **返回**: 格式化的股票数据字符串 (str)
- **数据内容**: 开盘价、收盘价、最高价、最低价、成交量、成交额、涨跌幅等

#### 2. 股票基本信息获取

**`get_stock_info(symbol)`**
- **参数**:
  - `symbol`: 股票代码 (str)
- **返回**: 股票信息字典 (Dict)
- **数据内容**:
  ```python
  {
      'symbol': '000001',
      'name': '平安银行',
      'industry': '银行',
      'market': '主板',
      'list_date': '1991-04-03',
      'area': '深圳',
      'source': 'tushare'
  }
  ```

#### 3. 基本面数据获取

**`get_fundamentals_data(symbol, force_refresh=False)`**
- **参数**:
  - `symbol`: 股票代码 (str)
  - `force_refresh`: 强制刷新缓存 (bool)
- **返回**: 基本面分析报告 (str)
- **数据内容**: PE比率、PB比率、ROE、ROA、财务指标、行业对比等

#### 4. 财务数据获取

**`get_financial_data(symbol, period="20231231")`**
- **参数**:
  - `symbol`: 股票代码 (str)
  - `period`: 报告期 (str) - 格式 'YYYYMMDD'
- **返回**: 财务数据字典 (Dict)
- **数据内容**: 资产负债表、利润表、现金流量表数据

### 缓存相关方法

#### 数据库缓存方法
- **`_get_cached_raw_financial_data(symbol)`**: 从数据库获取原始财务数据
- **`_cache_raw_financial_data(symbol, financial_data, stock_info)`**: 缓存原始财务数据到数据库
- **`_get_cached_stock_info(symbol)`**: 从数据库获取股票基本信息
- **`_restore_financial_data_format(cached_data)`**: 恢复财务数据格式

### 数据源切换方法

**`switch_china_data_source(source)`**
- **参数**:
  - `source`: 数据源类型 (ChinaDataSource枚举)
    - `ChinaDataSource.TUSHARE`: Tushare数据源
    - `ChinaDataSource.AKSHARE`: AKShare数据源
    - `ChinaDataSource.BAOSTOCK`: BaoStock数据源
    - `ChinaDataSource.TDX`: 通达信数据源

## 🔍 数据获取策略详解

### 1. 缓存策略 (TA_USE_APP_CACHE=true)

```
数据获取流程:
1. 检查MongoDB数据库缓存
   ├── 命中且未过期 → 返回缓存数据
   └── 未命中或过期 → 继续下一步
2. 调用外部API获取数据
   ├── 成功 → 缓存到数据库 → 返回数据
   └── 失败 → 继续下一步
3. 检查Redis缓存
   ├── 命中 → 返回缓存数据
   └── 未命中 → 继续下一步
4. 检查文件缓存
   ├── 命中 → 返回缓存数据
   └── 未命中 → 返回错误信息
```

### 2. 数据源降级策略

**中国A股数据源优先级:**
1. **Tushare** (最高质量) - 专业金融数据API
2. **AKShare** (高质量) - 开源金融数据库
3. **BaoStock** (中等质量) - 免费股票数据API
4. **TDX** (低质量) - 通达信接口 (将被淘汰)

**港股数据源优先级:**
1. **AKShare** - 港股数据支持
2. **Yahoo Finance** - 国际股票数据
3. **Finnhub** - 专业金融API (付费)

**美股数据源优先级:**
1. **Yahoo Finance** - 免费美股数据
2. **Finnhub** - 专业金融API (付费)

### 3. 错误处理机制

```python
try:
    # 1. 尝试主要数据源
    data = primary_data_source.get_data(symbol)
    if data and is_valid(data):
        return data
except Exception as e:
    logger.warning(f"主要数据源失败: {e}")

try:
    # 2. 尝试备用数据源
    data = fallback_data_source.get_data(symbol)
    if data and is_valid(data):
        return data
except Exception as e:
    logger.warning(f"备用数据源失败: {e}")

# 3. 尝试缓存数据
cached_data = get_cached_data(symbol)
if cached_data:
    logger.info("使用缓存数据")
    return cached_data

# 4. 返回错误信息
return generate_error_response(symbol, "所有数据源均不可用")
```

## 🚀 性能优化建议

### 1. 批量数据获取
```python
# 推荐：批量获取多只股票数据
symbols = ['000001', '000002', '000858']
for symbol in symbols:
    data = get_china_stock_data_cached(symbol, start_date, end_date)
    # 处理数据...
```

### 2. 缓存配置优化
```bash
# 环境变量配置
export TA_USE_APP_CACHE=true  # 启用数据库缓存
export TA_CHINA_MIN_API_INTERVAL_SECONDS=0.5  # API调用间隔
export TA_US_MIN_API_INTERVAL_SECONDS=1.0     # 美股API调用间隔
```

### 3. 数据源选择建议
- **生产环境**: 使用Tushare (需要token)
- **开发测试**: 使用AKShare (免费)
- **历史数据**: 优先使用缓存
- **实时数据**: 直接调用API

---

*最后更新: 2025-09-28*
