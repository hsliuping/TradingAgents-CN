# 多市场数据架构 - 代码模板补充

> **配套文档**: [多市场数据架构开发指南](./2025-10-21-multi-market-data-architecture-guide.md)  
> **文档版本**: v1.0  
> **创建日期**: 2025-10-21

本文档提供多市场数据架构的详细代码模板，包括服务层、API层、测试等。

---

## 目录

- [1. 统一数据服务](#1-统一数据服务)
- [2. 港股数据服务](#2-港股数据服务)
- [3. 美股数据服务](#3-美股数据服务)
- [4. 统一API端点](#4-统一api端点)
- [5. 数据迁移脚本](#5-数据迁移脚本)
- [6. 测试代码](#6-测试代码)

---

## 1. 统一数据服务

文件：`app/services/unified_market_data_service.py`

```python
"""
统一市场数据服务 - 跨市场数据访问
"""
from typing import Dict, List, Optional, Tuple
import pandas as pd
from datetime import datetime
import logging

from app.services.stock_data_service import get_stock_data_service
from tradingagents.dataflows.normalization import parse_full_symbol, normalize_symbol

logger = logging.getLogger("webapi")


class UnifiedMarketDataService:
    """统一市场数据服务"""
    
    def __init__(self):
        # 延迟导入，避免循环依赖
        self._cn_service = None
        self._hk_service = None
        self._us_service = None
    
    @property
    def cn_service(self):
        """A股数据服务"""
        if self._cn_service is None:
            self._cn_service = get_stock_data_service()
        return self._cn_service
    
    @property
    def hk_service(self):
        """港股数据服务"""
        if self._hk_service is None:
            from app.services.hk_stock_data_service import get_hk_stock_data_service
            self._hk_service = get_hk_stock_data_service()
        return self._hk_service
    
    @property
    def us_service(self):
        """美股数据服务"""
        if self._us_service is None:
            from app.services.us_stock_data_service import get_us_stock_data_service
            self._us_service = get_us_stock_data_service()
        return self._us_service
    
    async def get_stock_info(self, full_symbol: str) -> Optional[Dict]:
        """
        统一获取股票信息
        
        Args:
            full_symbol: 完整标识符（如 "XSHE:000001", "XHKG:0700", "XNAS:AAPL"）
        
        Returns:
            标准化的股票信息
        """
        try:
            parsed = parse_full_symbol(full_symbol)
            market = parsed["market"]
            symbol = parsed["symbol"]
            
            logger.info(f"📊 获取股票信息: {full_symbol} (市场: {market}, 代码: {symbol})")
            
            if market == "CN":
                return await self.cn_service.get_stock_info(symbol)
            elif market == "HK":
                return await self.hk_service.get_stock_info(symbol)
            elif market == "US":
                return await self.us_service.get_stock_info(symbol)
            else:
                raise ValueError(f"不支持的市场: {market}")
        
        except Exception as e:
            logger.error(f"❌ 获取股票信息失败: {full_symbol}, 错误: {e}")
            raise
    
    async def get_historical_data(
        self,
        full_symbol: str,
        start_date: str,
        end_date: str,
        period: str = "daily"
    ) -> pd.DataFrame:
        """
        统一获取历史数据
        
        Args:
            full_symbol: 完整标识符
            start_date: 开始日期 (YYYY-MM-DD)
            end_date: 结束日期 (YYYY-MM-DD)
            period: 数据周期 (daily/weekly/monthly)
        
        Returns:
            标准化的历史数据DataFrame
        """
        try:
            parsed = parse_full_symbol(full_symbol)
            market = parsed["market"]
            symbol = parsed["symbol"]
            
            logger.info(f"📈 获取历史数据: {full_symbol} ({start_date} ~ {end_date})")
            
            if market == "CN":
                data = await self.cn_service.get_historical_data(symbol, start_date, end_date, period)
            elif market == "HK":
                data = await self.hk_service.get_historical_data(symbol, start_date, end_date, period)
            elif market == "US":
                data = await self.us_service.get_historical_data(symbol, start_date, end_date, period)
            else:
                raise ValueError(f"不支持的市场: {market}")
            
            # 标准化DataFrame字段
            return self._normalize_dataframe(data, market)
        
        except Exception as e:
            logger.error(f"❌ 获取历史数据失败: {full_symbol}, 错误: {e}")
            raise
    
    async def search_stocks(
        self,
        keyword: str,
        market: Optional[str] = None,
        limit: int = 20
    ) -> List[Dict]:
        """
        跨市场搜索股票
        
        Args:
            keyword: 搜索关键词（代码或名称）
            market: 市场筛选（CN/HK/US），None表示全市场
            limit: 返回数量限制
        
        Returns:
            股票列表
        """
        results = []
        
        try:
            if market is None or market == "CN":
                cn_results = await self.cn_service.search_stocks(keyword, limit)
                results.extend(cn_results)
            
            if market is None or market == "HK":
                hk_results = await self.hk_service.search_stocks(keyword, limit)
                results.extend(hk_results)
            
            if market is None or market == "US":
                us_results = await self.us_service.search_stocks(keyword, limit)
                results.extend(us_results)
            
            # 按相关度排序并限制数量
            return results[:limit]
        
        except Exception as e:
            logger.error(f"❌ 搜索股票失败: {keyword}, 错误: {e}")
            return []
    
    def _normalize_dataframe(self, df: pd.DataFrame, market: str) -> pd.DataFrame:
        """
        标准化DataFrame字段
        
        确保所有市场返回统一的字段名：
        - date: 交易日期
        - open, high, low, close: OHLC
        - volume: 成交量
        - amount: 成交额
        """
        if df is None or df.empty:
            return df
        
        # 字段映射（根据市场调整）
        column_mapping = {
            "trade_date": "date",
            "vol": "volume",
            "turnover": "amount"
        }
        
        df = df.rename(columns=column_mapping)
        
        # 确保必需字段存在
        required_columns = ["date", "open", "high", "low", "close", "volume"]
        for col in required_columns:
            if col not in df.columns:
                df[col] = None
        
        return df


# 全局服务实例
_unified_service = None

def get_unified_market_data_service() -> UnifiedMarketDataService:
    """获取统一市场数据服务实例"""
    global _unified_service
    if _unified_service is None:
        _unified_service = UnifiedMarketDataService()
    return _unified_service
```

---

## 2. 港股数据服务

文件：`app/services/hk_stock_data_service.py`

```python
"""
港股数据服务
"""
from typing import Dict, List, Optional
import pandas as pd
from datetime import datetime
import logging

from app.core.database import get_mongo_db
from tradingagents.dataflows.normalization import normalize_symbol

logger = logging.getLogger("webapi")


class HKStockDataService:
    """港股数据服务"""
    
    def __init__(self):
        self.db = None
        self.basic_info_collection = None
        self.daily_quotes_collection = None
        self.market_quotes_collection = None
    
    async def initialize(self):
        """初始化数据库连接"""
        if self.db is None:
            self.db = get_mongo_db()
            self.basic_info_collection = self.db.stock_basic_info_hk
            self.daily_quotes_collection = self.db.stock_daily_quotes_hk
            self.market_quotes_collection = self.db.market_quotes_hk
            logger.info("✅ 港股数据服务初始化完成")
    
    async def get_stock_info(self, symbol: str) -> Optional[Dict]:
        """
        获取港股基础信息
        
        Args:
            symbol: 港股代码（如 "0700"）
        
        Returns:
            股票基础信息
        """
        await self.initialize()
        
        # 标准化代码
        normalized = normalize_symbol("yfinance", symbol, "HK")
        symbol = normalized["symbol"]
        
        logger.info(f"📊 查询港股信息: {symbol}")
        
        # 查询数据库
        doc = await self.basic_info_collection.find_one({"symbol": symbol})
        
        if doc:
            doc["_id"] = str(doc["_id"])
            logger.info(f"✅ 找到港股信息: {symbol} - {doc.get('name', 'N/A')}")
            return doc
        
        logger.warning(f"⚠️ 未找到港股信息: {symbol}")
        return None
    
    async def get_historical_data(
        self,
        symbol: str,
        start_date: str,
        end_date: str,
        period: str = "daily"
    ) -> pd.DataFrame:
        """
        获取港股历史数据
        
        Args:
            symbol: 港股代码
            start_date: 开始日期 (YYYY-MM-DD)
            end_date: 结束日期 (YYYY-MM-DD)
            period: 数据周期
        
        Returns:
            历史数据DataFrame
        """
        await self.initialize()
        
        # 标准化代码
        normalized = normalize_symbol("yfinance", symbol, "HK")
        symbol = normalized["symbol"]
        
        logger.info(f"📈 查询港股历史数据: {symbol} ({start_date} ~ {end_date})")
        
        # 构建查询条件
        query = {
            "symbol": symbol,
            "period": period,
            "trade_date": {
                "$gte": start_date.replace("-", ""),
                "$lte": end_date.replace("-", "")
            }
        }
        
        # 查询数据
        cursor = self.daily_quotes_collection.find(query).sort("trade_date", 1)
        docs = await cursor.to_list(length=None)
        
        if not docs:
            logger.warning(f"⚠️ 港股历史数据为空: {symbol}")
            return pd.DataFrame()
        
        logger.info(f"✅ 获取港股历史数据: {symbol}, {len(docs)}条记录")
        
        # 转换为DataFrame
        df = pd.DataFrame(docs)
        df = df.drop(columns=["_id"], errors="ignore")
        
        return df
    
    async def search_stocks(self, keyword: str, limit: int = 20) -> List[Dict]:
        """
        搜索港股
        
        Args:
            keyword: 搜索关键词
            limit: 返回数量
        
        Returns:
            股票列表
        """
        await self.initialize()
        
        logger.info(f"🔍 搜索港股: {keyword}")
        
        # 构建查询条件（代码或名称）
        query = {
            "$or": [
                {"symbol": {"$regex": keyword, "$options": "i"}},
                {"name": {"$regex": keyword, "$options": "i"}},
                {"name_en": {"$regex": keyword, "$options": "i"}}
            ]
        }
        
        cursor = self.basic_info_collection.find(query).limit(limit)
        docs = await cursor.to_list(length=limit)
        
        # 转换_id
        for doc in docs:
            doc["_id"] = str(doc["_id"])
        
        logger.info(f"✅ 搜索港股结果: {len(docs)}条")
        return docs
    
    async def sync_basic_info(self):
        """同步港股基础信息"""
        logger.info("🔄 开始同步港股基础信息...")
        # TODO: 实现从Yahoo Finance同步
        pass
    
    async def sync_historical_data(self, symbol: str, start_date: str, end_date: str):
        """同步港股历史数据"""
        logger.info(f"🔄 开始同步港股历史数据: {symbol}")
        # TODO: 实现从Yahoo Finance同步
        pass


# 全局服务实例
_hk_service = None

def get_hk_stock_data_service() -> HKStockDataService:
    """获取港股数据服务实例"""
    global _hk_service
    if _hk_service is None:
        _hk_service = HKStockDataService()
    return _hk_service
```

---

## 3. 美股数据服务

文件：`app/services/us_stock_data_service.py`

```python
"""
美股数据服务
"""
from typing import Dict, List, Optional
import pandas as pd
from datetime import datetime
import logging

from app.core.database import get_mongo_db
from tradingagents.dataflows.normalization import normalize_symbol

logger = logging.getLogger("webapi")


class USStockDataService:
    """美股数据服务"""
    
    def __init__(self):
        self.db = None
        self.basic_info_collection = None
        self.daily_quotes_collection = None
        self.market_quotes_collection = None
    
    async def initialize(self):
        """初始化数据库连接"""
        if self.db is None:
            self.db = get_mongo_db()
            self.basic_info_collection = self.db.stock_basic_info_us
            self.daily_quotes_collection = self.db.stock_daily_quotes_us
            self.market_quotes_collection = self.db.market_quotes_us
            logger.info("✅ 美股数据服务初始化完成")
    
    async def get_stock_info(self, symbol: str) -> Optional[Dict]:
        """获取美股基础信息"""
        await self.initialize()
        
        normalized = normalize_symbol("yfinance", symbol, "US")
        symbol = normalized["symbol"]
        
        logger.info(f"📊 查询美股信息: {symbol}")
        
        doc = await self.basic_info_collection.find_one({"symbol": symbol})
        
        if doc:
            doc["_id"] = str(doc["_id"])
            logger.info(f"✅ 找到美股信息: {symbol} - {doc.get('name', 'N/A')}")
            return doc
        
        logger.warning(f"⚠️ 未找到美股信息: {symbol}")
        return None
    
    async def get_historical_data(
        self,
        symbol: str,
        start_date: str,
        end_date: str,
        period: str = "daily"
    ) -> pd.DataFrame:
        """获取美股历史数据"""
        await self.initialize()
        
        normalized = normalize_symbol("yfinance", symbol, "US")
        symbol = normalized["symbol"]
        
        logger.info(f"📈 查询美股历史数据: {symbol} ({start_date} ~ {end_date})")
        
        query = {
            "symbol": symbol,
            "period": period,
            "trade_date": {
                "$gte": start_date.replace("-", ""),
                "$lte": end_date.replace("-", "")
            }
        }
        
        cursor = self.daily_quotes_collection.find(query).sort("trade_date", 1)
        docs = await cursor.to_list(length=None)
        
        if not docs:
            logger.warning(f"⚠️ 美股历史数据为空: {symbol}")
            return pd.DataFrame()
        
        logger.info(f"✅ 获取美股历史数据: {symbol}, {len(docs)}条记录")
        
        df = pd.DataFrame(docs)
        df = df.drop(columns=["_id"], errors="ignore")
        
        return df
    
    async def search_stocks(self, keyword: str, limit: int = 20) -> List[Dict]:
        """搜索美股"""
        await self.initialize()
        
        logger.info(f"🔍 搜索美股: {keyword}")
        
        query = {
            "$or": [
                {"symbol": {"$regex": keyword, "$options": "i"}},
                {"name": {"$regex": keyword, "$options": "i"}}
            ]
        }
        
        cursor = self.basic_info_collection.find(query).limit(limit)
        docs = await cursor.to_list(length=limit)
        
        for doc in docs:
            doc["_id"] = str(doc["_id"])
        
        logger.info(f"✅ 搜索美股结果: {len(docs)}条")
        return docs


# 全局服务实例
_us_service = None

def get_us_stock_data_service() -> USStockDataService:
    """获取美股数据服务实例"""
    global _us_service
    if _us_service is None:
        _us_service = USStockDataService()
    return _us_service
```

---

## 4. 统一API端点

文件：`app/routers/unified_market.py`

请参考主文档中的完整代码模板。

---

## 5. 数据迁移脚本

文件：`scripts/setup/init_multi_market_collections.py`

请参考主文档中的完整代码模板。

---

## 6. 测试代码

### 6.1 单元测试 - 标准化函数

文件：`tests/test_normalization.py`

请参考主文档中的完整代码模板。

### 6.2 集成测试 - 统一市场服务

文件：`tests/test_unified_market_service.py`

```python
"""
测试统一市场数据服务
"""
import pytest
from app.services.unified_market_data_service import get_unified_market_data_service


@pytest.mark.asyncio
class TestUnifiedMarketService:
    """测试统一市场数据服务"""

    async def test_get_cn_stock_info(self):
        """测试获取A股信息"""
        service = get_unified_market_data_service()

        info = await service.get_stock_info("XSHE:000001")

        assert info is not None
        assert info["symbol"] == "000001"
        assert info["market"] == "CN"
        assert "name" in info

    async def test_get_hk_stock_info(self):
        """测试获取港股信息"""
        service = get_unified_market_data_service()

        info = await service.get_stock_info("XHKG:0700")

        assert info is not None
        assert info["symbol"] == "0700"
        assert info["market"] == "HK"

    async def test_get_us_stock_info(self):
        """测试获取美股信息"""
        service = get_unified_market_data_service()

        info = await service.get_stock_info("XNAS:AAPL")

        assert info is not None
        assert info["symbol"] == "AAPL"
        assert info["market"] == "US"

    async def test_get_historical_data_cn(self):
        """测试获取A股历史数据"""
        service = get_unified_market_data_service()

        df = await service.get_historical_data(
            "XSHE:000001",
            "2024-01-01",
            "2024-01-31"
        )

        assert not df.empty
        assert "date" in df.columns
        assert "open" in df.columns
        assert "close" in df.columns

    async def test_search_stocks_cn(self):
        """测试搜索A股"""
        service = get_unified_market_data_service()

        results = await service.search_stocks("平安", market="CN", limit=10)

        assert len(results) > 0
        assert all(r["market"] == "CN" for r in results)

    async def test_search_stocks_all_markets(self):
        """测试跨市场搜索"""
        service = get_unified_market_data_service()

        results = await service.search_stocks("银行", market=None, limit=20)

        assert len(results) > 0
        # 可能包含多个市场的结果
```

### 6.3 API端点测试

文件：`tests/test_unified_market_api.py`

```python
"""
测试统一市场API端点
"""
import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


class TestUnifiedMarketAPI:
    """测试统一市场API"""

    def test_get_stock_info_cn(self):
        """测试获取A股信息API"""
        response = client.get(
            "/api/markets/CN/stocks/000001",
            headers={"Authorization": "Bearer test_token"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["symbol"] == "000001"

    def test_get_historical_data_cn(self):
        """测试获取A股历史数据API"""
        response = client.get(
            "/api/markets/CN/stocks/000001/history",
            params={
                "start_date": "2024-01-01",
                "end_date": "2024-01-31",
                "period": "daily"
            },
            headers={"Authorization": "Bearer test_token"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert isinstance(data["data"], list)

    def test_search_stocks(self):
        """测试搜索股票API"""
        response = client.get(
            "/api/markets/search",
            params={"keyword": "平安", "market": "CN", "limit": 10},
            headers={"Authorization": "Bearer test_token"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert len(data["data"]) > 0

    def test_get_market_metadata(self):
        """测试获取市场元数据API"""
        response = client.get(
            "/api/markets/metadata",
            headers={"Authorization": "Bearer test_token"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "markets" in data["data"]
        assert "CN" in data["data"]["markets"]
        assert "HK" in data["data"]["markets"]
        assert "US" in data["data"]["markets"]
```

---

## 7. 前端工具函数

文件：`frontend/src/utils/multiMarket.ts`

```typescript
/**
 * 多市场工具函数
 */

export interface MarketInfo {
  market: 'CN' | 'HK' | 'US'
  exchangeMic: string
  exchange: string
  currency: string
  timezone: string
}

export interface NormalizedSymbol {
  symbol: string
  fullSymbol: string
  market: 'CN' | 'HK' | 'US'
  exchangeMic: string
  exchange: string
}

/**
 * 解析完整标识符
 * @param fullSymbol 完整标识符（如 "XSHE:000001"）
 * @returns 解析结果
 */
export function parseFullSymbol(fullSymbol: string): NormalizedSymbol | null {
  if (!fullSymbol) return null

  if (fullSymbol.includes(':')) {
    const [exchangeMic, symbol] = fullSymbol.split(':', 2)
    const market = exchangeMicToMarket(exchangeMic)
    const exchange = exchangeMicToCode(exchangeMic)

    return {
      symbol,
      fullSymbol,
      market,
      exchangeMic,
      exchange
    }
  }

  // 兼容旧格式：自动推断
  const market = inferMarket(fullSymbol)
  const exchangeMic = inferExchangeMic(fullSymbol, market)
  const exchange = exchangeMicToCode(exchangeMic)

  return {
    symbol: fullSymbol,
    fullSymbol: `${exchangeMic}:${fullSymbol}`,
    market,
    exchangeMic,
    exchange
  }
}

/**
 * 推断市场类型
 * @param code 股票代码
 * @returns 市场类型
 */
export function inferMarket(code: string): 'CN' | 'HK' | 'US' {
  // A股：6位数字
  if (/^\d{6}$/.test(code)) {
    return 'CN'
  }

  // 港股：4-5位数字
  if (/^\d{4,5}$/.test(code)) {
    return 'HK'
  }

  // 美股：字母代码
  if (/^[A-Z]{1,5}$/.test(code.toUpperCase())) {
    return 'US'
  }

  // 带后缀的格式
  if (code.includes('.')) {
    const suffix = code.split('.').pop()?.toUpperCase()
    if (['SH', 'SZ', 'BJ', 'SS'].includes(suffix || '')) {
      return 'CN'
    }
    if (suffix === 'HK') {
      return 'HK'
    }
    if (suffix === 'US') {
      return 'US'
    }
  }

  return 'CN' // 默认A股
}

/**
 * 推断交易所MIC代码
 * @param symbol 股票代码
 * @param market 市场类型
 * @returns 交易所MIC代码
 */
export function inferExchangeMic(symbol: string, market: 'CN' | 'HK' | 'US'): string {
  if (market === 'CN') {
    // A股：根据代码前缀判断
    if (symbol.startsWith('60') || symbol.startsWith('68') || symbol.startsWith('90')) {
      return 'XSHG' // 上海
    }
    if (symbol.startsWith('00') || symbol.startsWith('30') || symbol.startsWith('20')) {
      return 'XSHE' // 深圳
    }
    if (symbol.startsWith('8') || symbol.startsWith('4')) {
      return 'XBEJ' // 北京
    }
    return 'XSHG' // 默认上海
  }

  if (market === 'HK') {
    return 'XHKG'
  }

  if (market === 'US') {
    return 'XNAS' // 默认纳斯达克
  }

  return 'XSHG'
}

/**
 * MIC代码转市场类型
 * @param exchangeMic 交易所MIC代码
 * @returns 市场类型
 */
export function exchangeMicToMarket(exchangeMic: string): 'CN' | 'HK' | 'US' {
  const mapping: Record<string, 'CN' | 'HK' | 'US'> = {
    XSHG: 'CN',
    XSHE: 'CN',
    XBEJ: 'CN',
    XHKG: 'HK',
    XNAS: 'US',
    XNYS: 'US'
  }
  return mapping[exchangeMic] || 'CN'
}

/**
 * MIC代码转交易所简称
 * @param exchangeMic 交易所MIC代码
 * @returns 交易所简称
 */
export function exchangeMicToCode(exchangeMic: string): string {
  const mapping: Record<string, string> = {
    XSHG: 'SSE',
    XSHE: 'SZSE',
    XBEJ: 'BSE',
    XHKG: 'SEHK',
    XNAS: 'NASDAQ',
    XNYS: 'NYSE'
  }
  return mapping[exchangeMic] || 'SSE'
}

/**
 * 格式化股票代码显示
 * @param symbol 股票代码
 * @param market 市场类型
 * @returns 格式化后的代码
 */
export function formatSymbolDisplay(symbol: string, market: 'CN' | 'HK' | 'US'): string {
  if (market === 'CN') {
    return symbol // A股直接显示6位代码
  }

  if (market === 'HK') {
    return symbol.padStart(5, '0') // 港股补齐5位
  }

  if (market === 'US') {
    return symbol.toUpperCase() // 美股转大写
  }

  return symbol
}

/**
 * 获取市场显示名称
 * @param market 市场类型
 * @returns 显示名称
 */
export function getMarketDisplayName(market: 'CN' | 'HK' | 'US'): string {
  const names: Record<string, string> = {
    CN: 'A股',
    HK: '港股',
    US: '美股'
  }
  return names[market] || market
}
```

---

## 8. 总结

本文档提供了多市场数据架构的完整代码模板，包括：

1. **统一数据服务** - 跨市场数据访问的核心服务
2. **港股/美股数据服务** - 独立的市场数据服务
3. **统一API端点** - RESTful API接口
4. **数据迁移脚本** - 数据库初始化和迁移工具
5. **测试代码** - 单元测试、集成测试、API测试
6. **前端工具函数** - TypeScript工具函数

### 使用建议

1. **按阶段实施**：
   - Phase 0: 创建标准化工具函数
   - Phase 1: 实现港股/美股数据服务
   - Phase 2: 创建统一查询接口
   - Phase 3: 行业分类映射
   - Phase 4: 分析引擎适配

2. **测试驱动开发**：
   - 先写测试，再写实现
   - 确保每个功能都有测试覆盖
   - 运行测试确保通过

3. **渐进式迁移**：
   - 不破坏现有A股数据
   - 新字段设为可选
   - 保持向后兼容

4. **文档同步更新**：
   - 更新API文档
   - 更新用户手册
   - 记录变更日志

---

**文档结束**

