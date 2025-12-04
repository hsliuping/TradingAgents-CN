# 多市场支持实施方案（多数据源架构）

**版本**: v1.1
**创建日期**: 2025-11-08
**更新日期**: 2025-11-08
**作者**: AI Assistant
**状态**: 待确认

## 🎯 核心设计

**分市场存储 + 多数据源支持**：
- ✅ 三个市场数据分开存储（A股/港股/美股独立集合）
- ✅ 参考A股设计，同一股票可有多个数据源记录
- ✅ 通过 `(code, source)` 联合唯一索引区分数据源
- ✅ 数据源优先级在数据库中配置（`datasource_groupings` 集合）
- ✅ 查询时按优先级自动选择最优数据源

---

## 📋 目录

1. [现状分析](#现状分析)
2. [目标与范围](#目标与范围)
3. [技术方案](#技术方案)
4. [实施计划](#实施计划)
5. [风险评估](#风险评估)
6. [资源需求](#资源需求)

---

## 🔍 现状分析

### 1. 现有架构概览

```
TradingAgentsCN/
├── app/                          # FastAPI后端
│   ├── models/stock_models.py    # 数据模型（已支持MarketType: CN/HK/US）
│   ├── services/
│   │   ├── data_sources/         # 数据源适配器（CN: tushare/akshare/baostock）
│   │   └── stock_data_service.py # 统一数据访问层
│   ├── routers/stocks.py         # 股票API路由
│   └── worker/                   # 数据同步服务
│       ├── tushare_sync_service.py
│       ├── akshare_sync_service.py
│       └── baostock_sync_service.py
│
├── tradingagents/                # 核心分析引擎
│   ├── dataflows/
│   │   ├── providers/
│   │   │   ├── china/            # A股数据提供器（已完善）
│   │   │   ├── hk/               # 港股数据提供器（已有基础实现）
│   │   │   └── us/               # 美股数据提供器（已有基础实现）
│   │   ├── interface.py          # 统一数据接口
│   │   └── data_source_manager.py # 数据源管理器
│   └── agents/                   # 智能体（目前主要针对A股）
│
└── frontend/                     # Vue 3前端
    ├── src/api/stocks.ts         # 股票API客户端
    └── src/views/Stocks/         # 股票详情页面
```

### 2. 已有基础

#### ✅ **数据模型层**
- `app/models/stock_models.py` 已定义 `MarketType = Literal["CN", "HK", "US"]`
- `MarketInfo` 结构已支持多市场元数据
- `StockBasicInfoExtended` 和 `MarketQuotesExtended` 已预留扩展字段

#### ✅ **数据提供器层**
- **港股**: `tradingagents/dataflows/providers/hk/`
  - `hk_stock.py`: 基于yfinance的港股数据获取
  - `improved_hk.py`: 改进版港股提供器（支持AKShare + yfinance）
- **美股**: `tradingagents/dataflows/providers/us/`
  - `yfinance.py`: 基于yfinance的美股数据获取
  - `finnhub.py`: Finnhub新闻和情绪数据

#### ✅ **数据库设计**
- MongoDB集合：`stock_basic_info`, `market_quotes`
- 索引：`(code, source)` 联合唯一索引，支持多数据源
- 字段：已预留 `market_info`, `status`, `currency` 等扩展字段

#### ⚠️ **待完善部分**
1. **后端API层**：`app/routers/stocks.py` 目前只支持A股（6位数字代码）
2. **数据同步服务**：`app/worker/` 下没有港股/美股的同步服务
3. **前端界面**：股票搜索、详情页面只支持A股代码格式
4. **智能体分析**：`tradingagents/agents/` 主要针对A股市场

---

## 🎯 目标与范围

### 核心目标

**在v1.0.0架构基础上，实现港股和美股的完整支持，包括：**
1. 数据获取、存储、查询
2. 实时行情和历史数据
3. 基本面信息和新闻数据
4. 前端界面适配
5. 智能体分析支持（简化版）

### 范围界定

#### ✅ **本期实施**
- 港股和美股的基础数据服务（行情、基本面、新闻）
- 统一的数据标准和符号规范
- 后端API扩展（支持多市场查询）
- 前端界面适配（市场选择、代码格式）
- 简化版行业分类映射（GICS）

#### ❌ **本期不做**
- 回测/模拟交易系统（延后到Phase 5+）
- 完整的GICS行业分类映射（只做简化版）
- 港股/美股的深度智能体分析（先支持基础分析）
- 跨市场对比分析（延后）

---

## 🛠 技术方案

### 方案1: 数据标准化层

#### 1.1 统一符号规范

**Full Symbol格式**: `{exchange_mic}:{symbol}`

| 市场 | 示例 | Full Symbol | Exchange MIC |
|------|------|-------------|--------------|
| A股 | 000001 | XSHE:000001 | XSHG/XSHE/XBEJ |
| 港股 | 0700 | XHKG:0700 | XHKG |
| 美股 | AAPL | XNAS:AAPL | XNAS/XNYS |

**实现**:
- 配置文件: `docs/config/data_standards.yaml` ✅ 已创建
- 工具函数: `tradingagents/dataflows/normalization.py` ✅ 已创建
  - `normalize_symbol()`: 标准化代码
  - `parse_full_symbol()`: 解析完整标识符
  - `get_exchange_info()`: 获取交易所信息

#### 1.2 数据模型扩展

**新模型**: `tradingagents/models/multi_market_models.py` ✅ 已创建
- `MultiMarketStockBasicInfo`: 多市场基础信息
- `MultiMarketStockDailyQuote`: 多市场日线行情
- `MultiMarketRealTimeQuote`: 多市场实时行情
- `SymbolRegistry`: 符号注册表（统一查询）

**现有模型兼容**:
- `app/models/stock_models.py` 保持不变
- 通过适配器层转换新旧模型

---

### 方案2: 后端服务层

#### 2.1 数据提供器增强

**港股提供器** (`app/services/data_sources/hk_adapter.py` - 新建)
```python
class HKStockAdapter(DataSourceAdapter):
    """港股数据适配器（基于yfinance + AKShare）"""
    
    def get_stock_list(self) -> List[Dict]:
        """获取港股列表（从AKShare）"""
    
    def get_realtime_quotes(self, symbols: List[str]) -> Dict:
        """获取实时行情（从yfinance）"""
    
    def get_stock_info(self, symbol: str) -> Dict:
        """获取基本信息（从yfinance.info）"""
```

**美股提供器** (`app/services/data_sources/us_adapter.py` - 新建)
```python
class USStockAdapter(DataSourceAdapter):
    """美股数据适配器（基于yfinance）"""
    
    def get_stock_list(self) -> List[Dict]:
        """获取美股列表（从预定义列表或API）"""
    
    def get_realtime_quotes(self, symbols: List[str]) -> Dict:
        """获取实时行情"""
    
    def get_stock_info(self, symbol: str) -> Dict:
        """获取基本信息"""
```

#### 2.2 数据同步服务

**港股同步服务** (`app/worker/hk_sync_service.py` - 新建)
- 基础信息同步（每日一次）
- 实时行情同步（交易时间每30秒）
- 历史数据同步（增量）

**美股同步服务** (`app/worker/us_sync_service.py` - 新建)
- 基础信息同步（每日一次）
- 实时行情同步（交易时间每30秒）
- 历史数据同步（增量）

#### 2.3 API路由扩展

**修改**: `app/routers/stocks.py`
```python
@router.get("/{market}/{code}/quote")
async def get_quote(market: str, code: str):
    """
    获取股票行情（支持多市场）
    
    Args:
        market: 市场类型 (cn/hk/us)
        code: 股票代码
    """
    # 标准化代码
    normalized = normalize_symbol(source="api", code=code, market=market.upper())
    
    # 查询数据库
    quote = await db.market_quotes.find_one({
        "full_symbol": normalized["full_symbol"]
    })
    
    return ok(data=quote)
```

**新增路由**:
- `GET /api/stocks/search?q={query}&market={market}` - 股票搜索
- `GET /api/stocks/{market}/list` - 市场股票列表
- `GET /api/markets` - 支持的市场列表

---

### 方案3: 前端界面层

#### 3.1 API客户端扩展

**修改**: `frontend/src/api/stocks.ts`
```typescript
export interface StockSearchParams {
  query: string
  market?: 'CN' | 'HK' | 'US'  // 市场筛选
  limit?: number
}

export interface StockInfo {
  symbol: string
  full_symbol: string
  market: 'CN' | 'HK' | 'US'
  name: string
  name_en?: string
  exchange: string
  currency: string
}

export const stocksApi = {
  // 股票搜索（支持多市场）
  async searchStocks(params: StockSearchParams) {
    return ApiClient.get<StockInfo[]>('/api/stocks/search', { params })
  },
  
  // 获取行情（支持多市场）
  async getQuote(market: string, symbol: string) {
    return ApiClient.get(`/api/stocks/${market}/${symbol}/quote`)
  }
}
```

#### 3.2 界面组件适配

**股票搜索组件** (`frontend/src/components/StockSearch.vue` - 新建)
- 市场选择下拉框（A股/港股/美股）
- 智能代码格式识别
- 搜索结果显示市场标识

**股票详情页** (`frontend/src/views/Stocks/Detail.vue` - 修改)
- 根据市场类型显示不同货币单位
- 港股显示每手股数
- 美股显示盘前盘后行情

---

### 方案4: MongoDB数据库设计（分市场存储 + 多数据源支持）

#### 4.1 设计原则

**核心思想**:
1. 三个市场的数据**分开存储**，字段结构**保持一致**
2. **参考A股多数据源设计**：同一股票可有多个数据源记录
3. 通过 `(code, source)` 联合唯一索引区分不同数据源

**优点**:
- ✅ 数据隔离，查询性能好
- ✅ 数据库压力分散
- ✅ 不影响现有A股数据和代码
- ✅ 扩展简单，风险低
- ✅ 便于独立维护和备份
- ✅ 支持多数据源冗余，提高可靠性
- ✅ 可按优先级选择最优数据源

#### 4.2 集合命名规范

**基础信息集合**:
- `stock_basic_info` → 保持不变（A股）
- `stock_basic_info_hk` → 新建（港股）
- `stock_basic_info_us` → 新建（美股）

**实时行情集合**:
- `market_quotes` → 保持不变（A股）
- `market_quotes_hk` → 新建（港股）
- `market_quotes_us` → 新建（美股）

**历史K线集合**:
- `stock_daily_quotes` → 保持不变（A股）
- `stock_daily_quotes_hk` → 新建（港股）
- `stock_daily_quotes_us` → 新建（美股）

**财务数据集合**:
- `stock_financial_data` → 保持不变（A股）
- `stock_financial_data_hk` → 新建（港股）
- `stock_financial_data_us` → 新建（美股）

**新闻数据集合**:
- `stock_news` → 保持不变（A股）
- `stock_news_hk` → 新建（港股）
- `stock_news_us` → 新建（美股）

#### 4.3 统一字段结构

**stock_basic_info / stock_basic_info_hk / stock_basic_info_us**

**A股字段**（现有，保持不变）:
```javascript
// stock_basic_info (A股)
{
  "code": "000001",           // 6位代码
  "name": "平安银行",
  "source": "tushare",        // 数据源
  "area": "深圳",
  "industry": "银行",
  "market": "深圳证券交易所",
  "list_date": "1991-04-03",
  "total_mv": 2500.0,         // 总市值（亿元）
  "circ_mv": 1800.0,          // 流通市值（亿元）
  "pe": 5.2,
  "pb": 0.8,
  "turnover_rate": 1.5,
  "updated_at": ISODate("2024-01-01T00:00:00Z")
}
```

**港股字段**（新建集合，字段对齐，支持多数据源）:
```javascript
// stock_basic_info_hk (港股) - 同一股票可有多个数据源记录
// 示例1: 腾讯控股 - yfinance数据源
{
  "code": "00700",            // 5位代码（补齐前导0）
  "name": "腾讯控股",
  "name_en": "Tencent Holdings",  // 英文名称
  "source": "yfinance",       // 数据源: yfinance
  "area": "香港",             // 地区
  "industry": "互联网",       // 行业（中文）
  "sector": "Communication Services",  // GICS行业（英文）
  "industry_code": "5010",    // GICS行业代码
  "market": "香港交易所",
  "list_date": "2004-06-16",
  "total_mv": 32000.0,        // 总市值（港币亿元）
  "circ_mv": 32000.0,         // 流通市值（港币亿元）
  "pe": 25.5,
  "pb": 4.2,
  "turnover_rate": 0.8,
  "lot_size": 100,            // 每手股数（港股特有）
  "currency": "HKD",          // 货币
  "updated_at": ISODate("2024-01-01T00:00:00Z")
}

// 示例2: 腾讯控股 - akshare数据源（同一股票，不同数据源）
{
  "code": "00700",
  "name": "腾讯控股",
  "source": "akshare",        // 数据源: akshare
  "area": "香港",
  "industry": "互联网",
  "market": "香港交易所",
  "list_date": "2004-06-16",
  "total_mv": 31800.0,        // 可能与yfinance略有差异
  "circ_mv": 31800.0,
  "pe": 25.3,
  "pb": 4.1,
  "turnover_rate": 0.9,
  "lot_size": 100,
  "currency": "HKD",
  "updated_at": ISODate("2024-01-01T00:00:00Z")
}
```

**美股字段**（新建集合，字段对齐，支持多数据源）:
```javascript
// stock_basic_info_us (美股) - 同一股票可有多个数据源记录
// 示例1: 苹果 - yfinance数据源
{
  "code": "AAPL",             // ticker代码
  "name": "苹果公司",         // 中文名称
  "name_en": "Apple Inc.",    // 英文名称
  "source": "yfinance",       // 数据源: yfinance
  "area": "美国",             // 地区
  "industry": "科技",         // 行业（中文）
  "sector": "Information Technology",  // GICS行业（英文）
  "industry_code": "4520",    // GICS行业代码
  "market": "纳斯达克",
  "list_date": "1980-12-12",
  "total_mv": 28000.0,        // 总市值（美元亿元）
  "circ_mv": 28000.0,         // 流通市值（美元亿元）
  "pe": 28.5,
  "pb": 45.2,
  "turnover_rate": 1.2,
  "currency": "USD",          // 货币
  "updated_at": ISODate("2024-01-01T00:00:00Z")
}

// 示例2: 苹果 - alphavantage数据源（可选，默认不启用）
{
  "code": "AAPL",
  "name": "苹果公司",
  "name_en": "Apple Inc.",
  "source": "alphavantage",   // 数据源: alphavantage
  "area": "美国",
  "industry": "科技",
  "sector": "Information Technology",
  "industry_code": "4520",
  "market": "纳斯达克",
  "list_date": "1980-12-12",
  "total_mv": 27950.0,        // 可能与yfinance略有差异
  "circ_mv": 27950.0,
  "pe": 28.3,
  "pb": 45.0,
  "turnover_rate": 1.3,
  "currency": "USD",
  "updated_at": ISODate("2024-01-01T00:00:00Z")
}
```

#### 4.4 索引设计（保持一致，支持多数据源）

**A股索引**（现有，保持不变）:
```javascript
// stock_basic_info
// 🔥 联合唯一索引：(code, source) - 允许同一股票有多个数据源
db.stock_basic_info.createIndex({ "code": 1, "source": 1 }, { unique: true })
db.stock_basic_info.createIndex({ "code": 1 })  // 非唯一索引，用于查询所有数据源
db.stock_basic_info.createIndex({ "source": 1 })  // 数据源索引
db.stock_basic_info.createIndex({ "market": 1 })
db.stock_basic_info.createIndex({ "industry": 1 })
db.stock_basic_info.createIndex({ "updated_at": 1 })
```

**港股索引**（新建，结构一致，支持多数据源）:
```javascript
// stock_basic_info_hk
// 🔥 联合唯一索引：(code, source) - 允许同一股票有多个数据源
db.stock_basic_info_hk.createIndex({ "code": 1, "source": 1 }, { unique: true })
db.stock_basic_info_hk.createIndex({ "code": 1 })  // 非唯一索引，用于查询所有数据源
db.stock_basic_info_hk.createIndex({ "source": 1 })  // 数据源索引
db.stock_basic_info_hk.createIndex({ "market": 1 })
db.stock_basic_info_hk.createIndex({ "industry": 1 })
db.stock_basic_info_hk.createIndex({ "sector": 1 })  // GICS行业
db.stock_basic_info_hk.createIndex({ "updated_at": 1 })
```

**美股索引**（新建，结构一致，支持多数据源）:
```javascript
// stock_basic_info_us
// 🔥 联合唯一索引：(code, source) - 允许同一股票有多个数据源
db.stock_basic_info_us.createIndex({ "code": 1, "source": 1 }, { unique: true })
db.stock_basic_info_us.createIndex({ "code": 1 })  // 非唯一索引，用于查询所有数据源
db.stock_basic_info_us.createIndex({ "source": 1 })  // 数据源索引
db.stock_basic_info_us.createIndex({ "market": 1 })
db.stock_basic_info_us.createIndex({ "industry": 1 })
db.stock_basic_info_us.createIndex({ "sector": 1 })  // GICS行业
db.stock_basic_info_us.createIndex({ "updated_at": 1 })
```

#### 4.5 实时行情集合（结构一致）

**A股行情**（现有）:
```javascript
// market_quotes
{
  "code": "000001",
  "close": 12.65,
  "pct_chg": 1.61,
  "amount": 1580000000,
  "open": 12.50,
  "high": 12.80,
  "low": 12.30,
  "volume": 125000000,
  "trade_date": "2024-01-15",
  "updated_at": ISODate("2024-01-15T15:00:00Z")
}
```

**港股行情**（新建）:
```javascript
// market_quotes_hk
{
  "code": "0700",
  "close": 320.50,
  "pct_chg": 2.15,
  "amount": 15800000000,      // 港币
  "open": 315.00,
  "high": 325.00,
  "low": 312.00,
  "volume": 48500000,
  "trade_date": "2024-01-15",
  "currency": "HKD",
  "updated_at": ISODate("2024-01-15T16:00:00Z")
}
```

**美股行情**（新建）:
```javascript
// market_quotes_us
{
  "code": "AAPL",
  "close": 185.50,
  "pct_chg": 1.25,
  "amount": 5800000000,       // 美元
  "open": 183.00,
  "high": 186.50,
  "low": 182.50,
  "volume": 52000000,
  "trade_date": "2024-01-15",
  "currency": "USD",
  "pre_market_price": 183.50,  // 盘前价格（美股特有）
  "after_market_price": 186.00, // 盘后价格（美股特有）
  "updated_at": ISODate("2024-01-15T21:00:00Z")
}
```

#### 4.6 数据访问层设计（支持多数据源）

**统一查询接口** (`app/services/unified_stock_service.py`):
```python
class UnifiedStockService:
    """统一股票数据服务（跨市场，支持多数据源）"""

    def __init__(self, db):
        self.db = db
        # 集合映射
        self.collection_map = {
            "CN": {
                "basic_info": "stock_basic_info",
                "quotes": "market_quotes",
                "daily": "stock_daily_quotes",
                "financial": "stock_financial_data",
                "news": "stock_news"
            },
            "HK": {
                "basic_info": "stock_basic_info_hk",
                "quotes": "market_quotes_hk",
                "daily": "stock_daily_quotes_hk",
                "financial": "stock_financial_data_hk",
                "news": "stock_news_hk"
            },
            "US": {
                "basic_info": "stock_basic_info_us",
                "quotes": "market_quotes_us",
                "daily": "stock_daily_quotes_us",
                "financial": "stock_financial_data_us",
                "news": "stock_news_us"
            }
        }

    async def get_stock_info(
        self,
        market: str,
        code: str,
        source: Optional[str] = None
    ) -> Optional[Dict]:
        """
        获取股票基础信息（支持多数据源）

        Args:
            market: 市场类型 (CN/HK/US)
            code: 股票代码
            source: 指定数据源（可选）

        Returns:
            股票基础信息字典
        """
        collection_name = self.collection_map[market]["basic_info"]
        collection = self.db[collection_name]

        if source:
            # 指定数据源
            query = {"code": code, "source": source}
            doc = await collection.find_one(query, {"_id": 0})
        else:
            # 🔥 按优先级查询（参考A股设计）
            source_priority = await self._get_source_priority(market)
            doc = None

            for src in source_priority:
                query = {"code": code, "source": src}
                doc = await collection.find_one(query, {"_id": 0})
                if doc:
                    logger.debug(f"✅ 使用数据源: {src}")
                    break

        return doc

    async def _get_source_priority(self, market: str) -> List[str]:
        """
        从数据库获取数据源优先级

        Args:
            market: 市场类型 (CN/HK/US)

        Returns:
            数据源优先级列表
        """
        market_category_map = {
            "CN": "a_shares",
            "HK": "hk_stocks",
            "US": "us_stocks"
        }

        market_category_id = market_category_map.get(market)

        # 从 datasource_groupings 集合查询
        groupings = await self.db.datasource_groupings.find({
            "market_category_id": market_category_id,
            "enabled": True
        }).sort("priority", -1).to_list(length=None)

        if groupings:
            return [g["data_source_name"] for g in groupings]

        # 默认优先级
        default_priority = {
            "CN": ["tushare", "akshare", "baostock"],
            "HK": ["yfinance_hk", "akshare_hk"],
            "US": ["yfinance_us"]
        }
        return default_priority.get(market, [])

    async def get_stock_quote(self, market: str, code: str):
        """获取实时行情"""
        collection_name = self.collection_map[market]["quotes"]
        collection = self.db[collection_name]
        return await collection.find_one({"code": code})

    async def search_stocks(self, market: str, query: str, limit: int = 20):
        """搜索股票（去重，只返回每个股票的最优数据源）"""
        collection_name = self.collection_map[market]["basic_info"]
        collection = self.db[collection_name]

        # 支持代码和名称搜索
        filter_query = {
            "$or": [
                {"code": {"$regex": query, "$options": "i"}},
                {"name": {"$regex": query, "$options": "i"}},
                {"name_en": {"$regex": query, "$options": "i"}}
            ]
        }

        # 查询所有匹配的记录
        cursor = collection.find(filter_query)
        all_results = await cursor.to_list(length=None)

        # 按 code 分组，每个 code 只保留优先级最高的数据源
        source_priority = await self._get_source_priority(market)
        unique_results = {}

        for doc in all_results:
            code = doc.get("code")
            source = doc.get("source")

            if code not in unique_results:
                unique_results[code] = doc
            else:
                # 比较优先级
                current_source = unique_results[code].get("source")
                if source_priority.index(source) < source_priority.index(current_source):
                    unique_results[code] = doc

        # 返回前 limit 条
        return list(unique_results.values())[:limit]
```

---

### 方案5: 多数据源配置与管理

#### 5.1 数据源配置（存储在数据库）

**数据源定义** (`datasources` 集合):
```javascript
// 港股数据源 - yfinance
{
  "name": "yfinance_hk",
  "type": "yfinance",
  "description": "Yahoo Finance港股数据",
  "enabled": true,
  "config": {
    "rate_limit": 2000,  // 每小时请求限制
    "timeout": 30
  },
  "created_at": ISODate("2024-01-01T00:00:00Z"),
  "updated_at": ISODate("2024-01-01T00:00:00Z")
}

// 港股数据源 - akshare
{
  "name": "akshare_hk",
  "type": "akshare",
  "description": "AKShare港股数据",
  "enabled": true,
  "config": {
    "rate_limit": 1000
  },
  "created_at": ISODate("2024-01-01T00:00:00Z"),
  "updated_at": ISODate("2024-01-01T00:00:00Z")
}

// 美股数据源 - yfinance
{
  "name": "yfinance_us",
  "type": "yfinance",
  "description": "Yahoo Finance美股数据",
  "enabled": true,
  "config": {
    "rate_limit": 2000,
    "timeout": 30
  },
  "created_at": ISODate("2024-01-01T00:00:00Z"),
  "updated_at": ISODate("2024-01-01T00:00:00Z")
}
```

**数据源优先级配置** (`datasource_groupings` 集合):
```javascript
// 港股市场数据源优先级
{
  "data_source_name": "yfinance_hk",
  "market_category_id": "hk_stocks",
  "priority": 100,  // 最高优先级
  "enabled": true,
  "created_at": ISODate("2024-01-01T00:00:00Z"),
  "updated_at": ISODate("2024-01-01T00:00:00Z")
}
{
  "data_source_name": "akshare_hk",
  "market_category_id": "hk_stocks",
  "priority": 80,   // 备用数据源
  "enabled": true,
  "created_at": ISODate("2024-01-01T00:00:00Z"),
  "updated_at": ISODate("2024-01-01T00:00:00Z")
}

// 美股市场数据源优先级
{
  "data_source_name": "yfinance_us",
  "market_category_id": "us_stocks",
  "priority": 100,
  "enabled": true,
  "created_at": ISODate("2024-01-01T00:00:00Z"),
  "updated_at": ISODate("2024-01-01T00:00:00Z")
}
```

#### 5.2 数据同步服务设计

**港股同步服务** (`app/worker/hk_sync_service.py`):
```python
from tradingagents.dataflows.providers.hk.improved_hk import ImprovedHKStockProvider
from tradingagents.dataflows.providers.hk.hk_stock import HKStockProvider

class HKSyncService:
    """港股数据同步服务（支持多数据源）"""

    def __init__(self, db):
        self.db = db
        self.providers = {
            "yfinance": HKStockProvider(),
            "akshare": ImprovedHKStockProvider(),
        }

    async def sync_basic_info_from_source(self, source: str):
        """从指定数据源同步港股基础信息"""
        provider = self.providers.get(source)
        if not provider:
            logger.error(f"❌ 不支持的数据源: {source}")
            return

        # 获取港股列表
        hk_stocks = await self._get_hk_stock_list()

        # 批量同步
        operations = []
        for stock_code in hk_stocks:
            try:
                # 从数据源获取数据
                stock_info = provider.get_stock_info(stock_code)

                # 添加 source 字段
                stock_info["source"] = source
                stock_info["updated_at"] = datetime.now()

                # 批量更新操作
                operations.append(
                    UpdateOne(
                        {"code": stock_code, "source": source},  # 🔥 联合查询条件
                        {"$set": stock_info},
                        upsert=True
                    )
                )
            except Exception as e:
                logger.error(f"❌ 同步失败: {stock_code} from {source}: {e}")

        # 执行批量操作
        if operations:
            result = await self.db.stock_basic_info_hk.bulk_write(operations)
            logger.info(f"✅ {source}: 更新 {result.modified_count} 条，插入 {result.upserted_count} 条")

# 同步任务函数
async def run_hk_yfinance_basic_info_sync():
    """港股基础信息同步（yfinance）"""
    db = get_mongo_db()
    service = HKSyncService(db)
    await service.sync_basic_info_from_source("yfinance")

async def run_hk_akshare_basic_info_sync():
    """港股基础信息同步（AKShare）"""
    db = get_mongo_db()
    service = HKSyncService(db)
    await service.sync_basic_info_from_source("akshare")
```

**美股同步服务** (`app/worker/us_sync_service.py`):
```python
from tradingagents.dataflows.providers.us.yfinance import YFinanceUtils

class USSyncService:
    """美股数据同步服务（支持多数据源）"""

    def __init__(self, db):
        self.db = db
        self.providers = {
            "yfinance": YFinanceUtils(),
            # "alphavantage": AlphaVantageProvider(),  # 可选
        }

    async def sync_basic_info_from_source(self, source: str):
        """从指定数据源同步美股基础信息"""
        # 类似港股的实现
        pass

# 同步任务函数
async def run_us_yfinance_basic_info_sync():
    """美股基础信息同步（yfinance）"""
    db = get_mongo_db()
    service = USSyncService(db)
    await service.sync_basic_info_from_source("yfinance")
```

#### 5.3 定时任务配置

**环境变量** (`.env`):
```bash
# 港股同步配置
HK_SYNC_ENABLED=true
HK_YFINANCE_SYNC_ENABLED=true
HK_AKSHARE_SYNC_ENABLED=true
HK_BASIC_INFO_SYNC_CRON="0 3 * * *"  # 每日凌晨3点
HK_QUOTES_SYNC_CRON="*/30 9-16 * * 1-5"  # 港股交易时间 09:30-16:00

# 美股同步配置
US_SYNC_ENABLED=true
US_YFINANCE_SYNC_ENABLED=true
US_BASIC_INFO_SYNC_CRON="0 4 * * *"  # 每日凌晨4点
US_QUOTES_SYNC_CRON="*/30 21-4 * * 1-5"  # 美股交易时间 21:30-04:00 (北京时间)
```

**调度器配置** (`app/main.py`):
```python
# 港股同步任务 - yfinance
scheduler.add_job(
    run_hk_yfinance_basic_info_sync,
    CronTrigger.from_crontab(settings.HK_BASIC_INFO_SYNC_CRON),
    id="hk_yfinance_basic_info_sync",
    name="港股基础信息同步（yfinance）",
    kwargs={"force_update": False}
)
if not (settings.HK_SYNC_ENABLED and settings.HK_YFINANCE_SYNC_ENABLED):
    scheduler.pause_job("hk_yfinance_basic_info_sync")

# 港股同步任务 - akshare
scheduler.add_job(
    run_hk_akshare_basic_info_sync,
    CronTrigger.from_crontab(settings.HK_BASIC_INFO_SYNC_CRON),
    id="hk_akshare_basic_info_sync",
    name="港股基础信息同步（AKShare）",
    kwargs={"force_update": False}
)
if not (settings.HK_SYNC_ENABLED and settings.HK_AKSHARE_SYNC_ENABLED):
    scheduler.pause_job("hk_akshare_basic_info_sync")

# 美股同步任务 - yfinance
scheduler.add_job(
    run_us_yfinance_basic_info_sync,
    CronTrigger.from_crontab(settings.US_BASIC_INFO_SYNC_CRON),
    id="us_yfinance_basic_info_sync",
    name="美股基础信息同步（yfinance）",
    kwargs={"force_update": False}
)
if not (settings.US_SYNC_ENABLED and settings.US_YFINANCE_SYNC_ENABLED):
    scheduler.pause_job("us_yfinance_basic_info_sync")
```

---

## 📅 实施计划

### Phase 0: 准备阶段 (2-3天)

**时间**: 2025-11-08 ~ 2025-11-10
**状态**: 进行中

#### 已完成 ✅
- [x] 分析现有MongoDB数据库结构
- [x] 确定分市场存储方案（三个市场独立集合）
- [x] 确定多数据源支持方案（参考A股设计）
- [x] 设计统一字段结构
- [x] 清理不需要的文件（基于混合存储方案的文件）
- [x] 创建MongoDB初始化脚本 (`scripts/setup/init_multi_market_collections.py`)

#### 待完成 ⏳
- [ ] 更新MongoDB初始化脚本（支持 `(code, source)` 联合唯一索引）
- [ ] 创建统一数据访问服务 (`app/services/unified_stock_service.py`)
  - 实现多数据源查询逻辑
  - 实现数据源优先级管理
- [ ] 扩展数据模型 (`app/models/stock_models.py`)
  - 添加港股/美股特有字段（`lot_size`, `name_en`, `sector` 等）
- [ ] 在数据库中配置港股/美股数据源
  - 添加 `datasources` 集合记录（yfinance_hk, akshare_hk, yfinance_us）
  - 添加 `datasource_groupings` 集合记录（优先级配置）
- [ ] 添加环境变量配置 (`app/core/config.py`)
  - 港股同步配置（HK_SYNC_ENABLED, HK_YFINANCE_SYNC_ENABLED 等）
  - 美股同步配置（US_SYNC_ENABLED, US_YFINANCE_SYNC_ENABLED 等）
- [ ] 备份现有数据库（可选）

**说明**:
- 由于采用分市场存储，**不需要迁移现有A股数据**，只需创建新集合即可
- 数据源供应商配置在数据库中管理，不需要额外配置文件
- **多数据源设计**：同一股票可有多个数据源记录，通过 `(code, source)` 联合唯一索引区分

---

### Phase 1: 港股数据服务（多数据源支持）(2周)

**目标**: 实现港股数据的完整获取、存储和查询（支持多数据源）

#### Week 1: 后端服务（多数据源）
- [ ] 创建港股同步服务 (`app/worker/hk_sync_service.py`)
  - 支持 yfinance 数据源
  - 支持 akshare 数据源
  - 实现批量同步逻辑（使用 `(code, source)` 联合查询）
- [ ] 在 `app/main.py` 中注册港股同步任务
  - `hk_yfinance_basic_info_sync`: 港股基础信息同步（yfinance）
  - `hk_akshare_basic_info_sync`: 港股基础信息同步（AKShare）
  - `hk_yfinance_quotes_sync`: 港股实时行情同步（yfinance）
- [ ] 扩展API路由支持港股 (`app/routers/stocks.py`)
  - `GET /api/stocks/hk/{code}/info?source={source}`: 获取港股信息（支持指定数据源）
  - `GET /api/stocks/hk/{code}/quote`: 获取港股行情
  - `GET /api/stocks/hk/search?q={query}`: 搜索港股（去重，返回最优数据源）
- [ ] 单元测试

#### Week 2: 前端适配
- [ ] 扩展API客户端 (`frontend/src/api/stocks.ts`)
  - 添加港股查询接口
  - 支持市场参数（CN/HK/US）
- [ ] 创建股票搜索组件（支持港股）
  - 市场选择下拉框
  - 港股代码格式识别（4-5位数字）
- [ ] 修改股票详情页（支持港股）
  - 显示港股特有字段（每手股数、GICS行业）
  - 货币单位显示（HKD）
- [ ] 集成测试

**交付物**:
- ✅ 港股基础信息同步（每日，支持 yfinance + akshare）
- ✅ 港股实时行情同步（交易时间，yfinance）
- ✅ 港股查询API（支持多数据源，按优先级返回）
- ✅ 前端港股搜索和详情展示

---

### Phase 2: 美股数据服务（多数据源支持）(2周)

**目标**: 实现美股数据的完整获取、存储和查询（支持多数据源）

#### Week 1: 后端服务（多数据源）
- [ ] 创建美股同步服务 (`app/worker/us_sync_service.py`)
  - 支持 yfinance 数据源
  - 预留 alphavantage 数据源接口（可选，默认不启用）
  - 实现批量同步逻辑（使用 `(code, source)` 联合查询）
- [ ] 在 `app/main.py` 中注册美股同步任务
  - `us_yfinance_basic_info_sync`: 美股基础信息同步（yfinance）
  - `us_yfinance_quotes_sync`: 美股实时行情同步（yfinance）
- [ ] 扩展API路由支持美股
  - `GET /api/stocks/us/{code}/info?source={source}`: 获取美股信息（支持指定数据源）
  - `GET /api/stocks/us/{code}/quote`: 获取美股行情
  - `GET /api/stocks/us/search?q={query}`: 搜索美股（去重，返回最优数据源）
- [ ] 单元测试

#### Week 2: 统一查询接口
- [ ] 完善统一股票查询服务 (`app/services/unified_stock_service.py`)
  - 支持三个市场（CN/HK/US）
  - 实现多数据源优先级查询
  - 实现跨市场搜索（去重）
- [ ] 实现跨市场搜索API
  - `GET /api/stocks/search?q={query}&market={market}`: 跨市场搜索
  - `GET /api/markets`: 获取支持的市场列表
- [ ] 前端市场切换功能
  - 市场选择组件（A股/港股/美股）
  - 智能代码格式识别
- [ ] 集成测试

**交付物**:
- 美股基础信息同步（每日）
- 美股实时行情同步（交易时间）
- 美股查询API
- 统一的多市场查询接口

---

### Phase 3: 行业分类映射 (1周)

**目标**: 实现简化版GICS行业分类映射

- [ ] 创建行业映射配置 (`docs/config/industry_mapping.yaml`)
- [ ] 实现行业映射工具 (`tradingagents/dataflows/industry_mapper.py`)
- [ ] 批量更新现有数据的行业分类
- [ ] API支持按行业筛选（跨市场）

**交付物**:
- CN/HK/US行业分类统一到GICS
- 行业筛选API
- 前端行业筛选功能

---

### Phase 4: 智能体分析适配 (1周)

**目标**: 适配现有智能体以支持多市场

- [ ] 修改数据获取工具 (`tradingagents/tools/`)
- [ ] 适配技术分析工具（支持多市场）
- [ ] 适配基本面分析工具（支持多市场）
- [ ] 简化版港股/美股分析流程

**交付物**:
- 智能体可分析港股/美股（基础功能）
- 多市场技术指标计算
- 多市场基本面数据获取

---

## ⚠️ 风险评估

### 高风险

1. **数据源稳定性**
   - **风险**: yfinance API不稳定，可能被限流
   - **缓解**: 实现多数据源备份（yfinance + AKShare + Futu）

2. **数据一致性**
   - **风险**: 不同市场的数据格式差异大
   - **缓解**: 严格的数据标准化和验证

### 中风险

3. **性能问题**
   - **风险**: 港股/美股数据量大，同步慢
   - **缓解**: 增量同步 + 缓存优化

4. **时区处理**
   - **风险**: 多市场时区不同，容易出错
   - **缓解**: 统一使用UTC存储，显示时转换

### 低风险

5. **前端兼容性**
   - **风险**: 现有前端代码假设A股格式
   - **缓解**: 渐进式改造，保持向后兼容

---

## 📊 资源需求

### 开发资源
- **后端开发**: 3周（Phase 1-2）
- **前端开发**: 1周（Phase 1-2）
- **测试**: 1周（贯穿各Phase）

### 基础设施
- **数据库**: MongoDB存储空间增加（预计+50GB）
- **Redis**: 缓存空间增加（预计+2GB）
- **API配额**: yfinance免费版（需监控使用量）

### 第三方服务
- **yfinance**: 免费（有限流）
- **AKShare**: 免费
- **Futu OpenAPI**: 可选（需申请）

---

## ✅ 验收标准

### Phase 1 (港股)
- [ ] 可同步至少100只港股的基础信息
- [ ] 实时行情延迟<5秒
- [ ] 前端可搜索和查看港股详情
- [ ] API响应时间<500ms

### Phase 2 (美股)
- [ ] 可同步至少500只美股的基础信息
- [ ] 实时行情延迟<5秒
- [ ] 前端可搜索和查看美股详情
- [ ] 统一查询接口支持跨市场搜索

### Phase 3 (行业分类)
- [ ] 至少80%的股票有GICS分类
- [ ] 行业筛选API可用
- [ ] 前端支持按行业筛选

### Phase 4 (智能体)
- [ ] 智能体可分析港股/美股（基础功能）
- [ ] 技术指标计算正确
- [ ] 分析报告包含市场标识

---

## 📝 后续优化方向

1. **数据源扩展**
   - 接入Futu OpenAPI（港股深度数据）
   - 接入Alpha Vantage（美股基本面）

2. **功能增强**
   - 跨市场对比分析
   - 港股通/沪深港通标识
   - ADR/H股关联

3. **性能优化**
   - 实时行情WebSocket推送
   - 数据预加载和智能缓存

---

## 🤝 需要确认的问题

### 1. **MongoDB数据库设计确认** ✅ 已确认

**已采用方案**: 分市场存储（方案B）

**集合命名**:
- A股：`stock_basic_info`, `market_quotes`, `stock_daily_quotes` 等（保持不变）
- 港股：`stock_basic_info_hk`, `market_quotes_hk`, `stock_daily_quotes_hk` 等（新建）
- 美股：`stock_basic_info_us`, `market_quotes_us`, `stock_daily_quotes_us` 等（新建）

**优点**:
- ✅ 数据隔离，查询性能好
- ✅ 数据库压力分散
- ✅ 不影响现有A股数据和代码
- ✅ 不需要数据迁移
- ✅ 字段结构保持一致，便于维护

---

### 2. **数据源选择**

**港股数据源**:
- 基础方案：yfinance（免费，但有限流风险）
- 增强方案：yfinance + AKShare（国内数据源，更稳定）
- 专业方案：Futu OpenAPI（需要申请，数据质量最好）

**美股数据源**:
- 基础方案：yfinance（免费，覆盖主流股票）
- 增强方案：yfinance + Alpha Vantage（需要API Key）

**您的选择？** 建议先用基础方案（yfinance），后续根据需要升级。

---

### 3. **实施优先级**

**建议顺序**:
1. Phase 0: 数据库迁移（2-3天）
2. Phase 1: 港股支持（2周）
3. Phase 2: 美股支持（2周）
4. Phase 3: 行业分类映射（1周，可选）
5. Phase 4: 智能体适配（1周）

**问题**:
- 是否同意先港股后美股？
- 行业分类映射是否必须？（可以简化或延后）
- 智能体分析是否只做基础功能？（深度分析延后）

---

### 4. **功能范围**

**本期不做**（建议延后）:
- ❌ 港股期权、美股期权
- ❌ 港股窝轮、牛熊证
- ❌ 美股ETF、基金
- ❌ 跨市场对比分析
- ❌ 回测/模拟交易系统

**您是否同意？** 如有特殊需求请说明。

---

### 5. **性能要求**

**实时行情**:
- 建议延迟：<5秒（交易时间）
- 同步频率：30秒（可配置）
- 非交易时间：保持上次收盘数据

**数据同步**:
- 基础信息：每日一次（凌晨）
- 历史数据：增量同步（每日收盘后）

**您的要求？**

---

### 6. **关键技术决策**

**符号标准化**:
- 使用 `full_symbol` 格式：`XSHE:000001`, `XHKG:0700`, `XNAS:AAPL`
- 保留 `code` 字段向后兼容
- 新增 `symbol` 字段作为标准化代码

**您是否同意这个设计？**

---

---

## 📊 方案总结

### 核心优势

1. **完全兼容A股多数据源设计**
   - 同一股票可有多个数据源记录
   - `(code, source)` 联合唯一索引
   - 数据源优先级在数据库中配置
   - 查询时自动选择最优数据源

2. **零风险实施**
   - A股数据和代码完全不受影响
   - 只需创建新集合，无需数据迁移
   - 渐进式实施，可随时回滚

3. **高可靠性**
   - 港股支持 yfinance + akshare 双数据源
   - 美股支持 yfinance（可扩展 alphavantage）
   - 数据源故障自动降级

4. **易于维护**
   - 统一的数据访问层 (`UnifiedStockService`)
   - 统一的同步服务架构
   - 统一的索引设计

### 数据源配置

| 市场 | 主数据源 | 备用数据源 | 可选数据源 |
|------|---------|-----------|-----------|
| A股 | Tushare | AKShare | BaoStock |
| 港股 | yfinance | AKShare | Futu OpenAPI（可选） |
| 美股 | yfinance | - | Alpha Vantage（可选） |

### 实施时间线

- **Phase 0**: 2-3天（基础架构）
- **Phase 1**: 2周（港股多数据源支持）
- **Phase 2**: 2周（美股多数据源支持）
- **Phase 3**: 1周（行业分类映射，可选）
- **Phase 4**: 1周（智能体适配）

**总计**: 约 5-6 周

---

## ✅ 下一步行动

**请您确认以上方案后，我将立即开始实施 Phase 0：**

1. ✅ 更新MongoDB初始化脚本（支持 `(code, source)` 联合唯一索引）
2. ✅ 创建统一数据访问服务 (`app/services/unified_stock_service.py`)
3. ✅ 创建港股同步服务 (`app/worker/hk_sync_service.py`)
4. ✅ 创建美股同步服务 (`app/worker/us_sync_service.py`)
5. ✅ 在数据库中配置港股/美股数据源和优先级
6. ✅ 添加环境变量配置 (`app/core/config.py`)
7. ✅ 在 `app/main.py` 中注册港股/美股同步任务
8. ✅ 运行初始化脚本创建新集合

**预计完成时间**: 5-6周（约1.5个月）

---

**方案已完整更新，包含完整的多数据源支持设计。请确认后开始实施！** 🚀
