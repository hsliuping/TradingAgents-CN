"""
Local data source adapter for user-imported data
"""
from typing import Optional, Dict
import logging
import pandas as pd

from .base import DataSourceAdapter

logger = logging.getLogger(__name__)


class LocalAdapter(DataSourceAdapter):
    """本地数据源适配器（用户通过API导入的数据）"""

    def __init__(self):
        super().__init__()  # 调用父类初始化

    @property
    def name(self) -> str:
        return "local"

    def _get_default_priority(self) -> int:
        return 10  # 默认最高优先级（数字越大优先级越高）

    def is_available(self) -> bool:
        """检查本地数据源是否可用（检查MongoDB中是否有本地数据）"""
        try:
            from app.core.database import get_mongo_db_sync
            db = get_mongo_db_sync()
            collection = db.stock_basic_info
            
            # 检查是否有 source='local' 的数据
            count = collection.count_documents({"source": "local"}, limit=1)
            return count > 0
        except Exception as e:
            logger.warning(f"Local: Failed to check availability: {e}")
            return False

    def get_stock_list(self) -> Optional[pd.DataFrame]:
        """获取本地股票列表"""
        try:
            from app.core.database import get_mongo_db_sync
            db = get_mongo_db_sync()
            collection = db.stock_basic_info
            
            # 查询 source='local' 的股票
            cursor = collection.find({"source": "local"})
            stocks = list(cursor)
            
            if not stocks:
                logger.info("Local: No local stocks found")
                return None
            
            # 转换为 DataFrame
            df = pd.DataFrame(stocks)
            
            # 标准化字段名（确保有必需的字段）
            if 'symbol' in df.columns and 'name' in df.columns:
                logger.info(f"Local: Successfully fetched {len(df)} local stocks")
                return df
            else:
                logger.warning("Local: Missing required fields (symbol, name)")
                return None
                
        except Exception as e:
            logger.error(f"Local: Failed to fetch stock list: {e}")
            return None

    def get_daily_basic(self, trade_date: str) -> Optional[pd.DataFrame]:
        """获取每日基础财务数据（本地数据源暂不支持）"""
        logger.warning("Local: get_daily_basic not supported")
        return None

    def find_latest_trade_date(self) -> Optional[str]:
        """查找最新交易日期（本地数据源暂不支持）"""
        logger.warning("Local: find_latest_trade_date not supported")
        return None

    def get_realtime_quotes(self) -> Optional[Dict[str, Dict[str, Optional[float]]]]:
        """获取实时行情（从本地数据库读取）"""
        try:
            from app.core.database import get_mongo_db_sync
            db = get_mongo_db_sync()
            collection = db.market_quotes
            
            # 查询所有行情数据
            cursor = collection.find({})
            quotes = list(cursor)
            
            if not quotes:
                logger.info("Local: No local quotes found")
                return None
            
            # 转换为字典格式
            result = {}
            for quote in quotes:
                symbol = quote.get('symbol')
                if symbol:
                    result[symbol] = {
                        'close': quote.get('close'),
                        'pct_chg': quote.get('pct_chg'),
                        'amount': quote.get('amount')
                    }
            
            logger.info(f"Local: Successfully fetched {len(result)} quotes")
            return result
            
        except Exception as e:
            logger.error(f"Local: Failed to fetch realtime quotes: {e}")
            return None

    def get_kline(self, code: str, period: str = "day", limit: int = 120, adj: Optional[str] = None):
        """获取K线数据（从本地数据库读取）"""
        try:
            from app.core.database import get_mongo_db_sync
            db = get_mongo_db_sync()
            collection = db.stock_historical_data
            
            # 查询K线数据
            cursor = collection.find(
                {"symbol": code, "data_source": "local", "period": period}
            ).sort("trade_date", 1).limit(limit)
            
            klines = list(cursor)
            
            if not klines:
                logger.info(f"Local: No kline data found for {code}")
                return []
            
            # 转换为标准格式
            result = []
            for kline in klines:
                result.append({
                    'time': kline.get('trade_date'),
                    'open': kline.get('open'),
                    'high': kline.get('high'),
                    'low': kline.get('low'),
                    'close': kline.get('close'),
                    'volume': kline.get('volume'),
                    'amount': kline.get('amount')
                })
            
            logger.info(f"Local: Successfully fetched {len(result)} klines for {code}")
            return result
            
        except Exception as e:
            logger.error(f"Local: Failed to fetch kline for {code}: {e}")
            return []

    def get_news(self, code: str, days: int = 2, limit: int = 50, include_announcements: bool = True):
        """获取新闻/公告（本地数据源暂不支持）"""
        logger.warning("Local: get_news not supported")
        return []

