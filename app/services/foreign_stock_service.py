"""
港股和美股数据服务
🔥 复用统一数据源管理器（UnifiedStockService）
🔥 按照数据库配置的数据源优先级调用API
🔥 请求去重机制：防止并发请求重复调用API
"""
from typing import Optional, Dict, List, Tuple
from datetime import datetime, timedelta
import logging
import json
import re
import asyncio
from collections import defaultdict

# 复用现有缓存系统
from tradingagents.dataflows.cache import get_cache

# 复用现有数据源提供者
from tradingagents.dataflows.providers.hk.hk_stock import HKStockProvider

logger = logging.getLogger(__name__)


class ForeignStockService:
    """港股和美股数据服务（复用统一数据源管理器，按数据库优先级调用）"""

    # 缓存时间配置（秒）
    CACHE_TTL = {
        "HK": {
            "quote": 600,        # 10分钟（实时行情）
            "info": 86400,       # 1天（基础信息）
            "kline": 7200,       # 2小时（K线数据）
        },
        "US": {
            "quote": 600,        # 10分钟
            "info": 86400,       # 1天
            "kline": 7200,       # 2小时
        }
    }

    def __init__(self, db=None):
        # 使用统一缓存系统（自动选择 MongoDB/Redis/File）
        self.cache = get_cache()

        # 初始化港股数据源提供者
        self.hk_provider = HKStockProvider()

        # 保存数据库连接（用于查询数据源优先级）
        self.db = db

        # 🔥 请求去重：为每个 (market, code, data_type) 创建独立的锁
        self._request_locks = defaultdict(asyncio.Lock)

        # 🔥 正在进行的请求缓存（用于共享结果）
        self._pending_requests = {}

        logger.info("✅ ForeignStockService 初始化完成（已启用请求去重）")
    
    async def get_quote(self, market: str, code: str, force_refresh: bool = False) -> Dict:
        """
        获取实时行情
        
        Args:
            market: 市场类型 (HK/US)
            code: 股票代码
            force_refresh: 是否强制刷新（跳过缓存）
        
        Returns:
            实时行情数据
        
        流程：
        1. 检查是否强制刷新
        2. 从缓存获取（Redis → MongoDB → File）
        3. 缓存未命中 → 调用数据源API（按优先级）
        4. 保存到缓存
        """
        if market == 'HK':
            return await self._get_hk_quote(code, force_refresh)
        elif market == 'US':
            return await self._get_us_quote(code, force_refresh)
        else:
            raise ValueError(f"不支持的市场类型: {market}")
    
    async def get_basic_info(self, market: str, code: str, force_refresh: bool = False) -> Dict:
        """
        获取基础信息
        
        Args:
            market: 市场类型 (HK/US)
            code: 股票代码
            force_refresh: 是否强制刷新
        
        Returns:
            基础信息数据
        """
        if market == 'HK':
            return await self._get_hk_info(code, force_refresh)
        elif market == 'US':
            return await self._get_us_info(code, force_refresh)
        else:
            raise ValueError(f"不支持的市场类型: {market}")
    
    async def get_kline(self, market: str, code: str, period: str = 'day', 
                       limit: int = 120, force_refresh: bool = False) -> List[Dict]:
        """
        获取K线数据
        
        Args:
            market: 市场类型 (HK/US)
            code: 股票代码
            period: 周期 (day/week/month)
            limit: 数据条数
            force_refresh: 是否强制刷新
        
        Returns:
            K线数据列表
        """
        if market == 'HK':
            return await self._get_hk_kline(code, period, limit, force_refresh)
        elif market == 'US':
            return await self._get_us_kline(code, period, limit, force_refresh)
        else:
            raise ValueError(f"不支持的市场类型: {market}")
    
    async def _get_hk_quote(self, code: str, force_refresh: bool = False) -> Dict:
        """
        获取港股实时行情（带请求去重）
        🔥 按照数据库配置的数据源优先级调用API
        🔥 防止并发请求重复调用API
        """
        # 1. 检查缓存（除非强制刷新）
        if not force_refresh:
            cache_key = self.cache.find_cached_stock_data(
                symbol=code,
                data_source="hk_realtime_quote"
            )

            if cache_key:
                cached_data = self.cache.load_stock_data(cache_key)
                if cached_data:
                    logger.info(f"⚡ 从缓存获取港股行情: {code}")
                    return self._parse_cached_data(cached_data, 'HK', code)

        # 2. 🔥 请求去重：使用锁确保同一股票同时只有一个API调用
        request_key = f"HK_quote_{code}_{force_refresh}"
        lock = self._request_locks[request_key]

        async with lock:
            # 🔥 再次检查缓存（可能在等待锁的过程中，其他请求已经完成并缓存了数据）
            # 即使 force_refresh=True，也要检查是否有其他并发请求刚刚完成
            cache_key = self.cache.find_cached_stock_data(
                symbol=code,
                data_source="hk_realtime_quote"
            )
            if cache_key:
                cached_data = self.cache.load_stock_data(cache_key)
                if cached_data:
                    # 检查缓存时间，如果是最近1秒内的，说明是并发请求刚刚缓存的
                    try:
                        data_dict = json.loads(cached_data) if isinstance(cached_data, str) else cached_data
                        updated_at = data_dict.get('updated_at', '')
                        if updated_at:
                            cache_time = datetime.fromisoformat(updated_at)
                            time_diff = (datetime.now() - cache_time).total_seconds()
                            if time_diff < 1:  # 1秒内的缓存，说明是并发请求刚刚完成的
                                logger.info(f"⚡ [去重] 使用并发请求的结果: {code} (缓存时间: {time_diff:.2f}秒前)")
                                return self._parse_cached_data(cached_data, 'HK', code)
                    except Exception as e:
                        logger.debug(f"检查缓存时间失败: {e}")

                    # 如果不是强制刷新，使用缓存
                    if not force_refresh:
                        logger.info(f"⚡ [去重后] 从缓存获取港股行情: {code}")
                        return self._parse_cached_data(cached_data, 'HK', code)

            logger.info(f"🔄 开始获取港股行情: {code} (force_refresh={force_refresh})")

            # 3. 从数据库获取数据源优先级（使用统一方法）
            source_priority = await self._get_source_priority('HK')

            # 4. 按优先级尝试各个数据源
            quote_data = None
            data_source = None

            # 数据源名称映射（数据库名称 → 处理函数）
            # 🔥 只有这些是有效的数据源名称
            source_handlers = {
                'yahoo_finance': ('yfinance', self._get_hk_quote_from_yfinance),
                'akshare': ('akshare', self._get_hk_quote_from_akshare),
            }

            # 过滤有效数据源并去重
            valid_priority = []
            seen = set()
            for source_name in source_priority:
                source_key = source_name.lower()
                # 只保留有效的数据源
                if source_key in source_handlers and source_key not in seen:
                    seen.add(source_key)
                    valid_priority.append(source_name)

            if not valid_priority:
                logger.warning(f"⚠️ 数据库中没有配置有效的港股数据源，使用默认顺序")
                valid_priority = ['yahoo_finance', 'akshare']

            logger.info(f"📊 [HK有效数据源] {valid_priority} (股票: {code})")

            for source_name in valid_priority:
                source_key = source_name.lower()
                handler_name, handler_func = source_handlers[source_key]
                try:
                    # 🔥 使用 asyncio.to_thread 避免阻塞事件循环
                    quote_data = await asyncio.to_thread(handler_func, code)
                    data_source = handler_name

                    if quote_data:
                        logger.info(f"✅ {data_source}获取港股行情成功: {code}")
                        break
                except Exception as e:
                    logger.warning(f"⚠️ {source_name}获取失败 ({code}): {e}")
                    continue

            if not quote_data:
                raise Exception(f"无法获取港股{code}的行情数据：所有数据源均失败")

            # 5. 格式化数据
            formatted_data = self._format_hk_quote(quote_data, code, data_source)

            # 6. 保存到缓存
            self.cache.save_stock_data(
                symbol=code,
                data=json.dumps(formatted_data, ensure_ascii=False),
                data_source="hk_realtime_quote"
            )
            logger.info(f"💾 港股行情已缓存: {code}")

            return formatted_data

    async def _get_source_priority(self, market: str) -> List[str]:
        """
        从数据库获取数据源优先级（统一方法）
        🔥 复用 UnifiedStockService 的实现
        """
        market_category_map = {
            "CN": "a_shares",
            "HK": "hk_stocks",
            "US": "us_stocks"
        }

        market_category_id = market_category_map.get(market)

        try:
            # 从 datasource_groupings 集合查询
            groupings = await self.db.datasource_groupings.find({
                "market_category_id": market_category_id,
                "enabled": True
            }).sort("priority", -1).to_list(length=None)

            if groupings:
                priority_list = [g["data_source_name"] for g in groupings]
                logger.info(f"📊 [{market}数据源优先级] 从数据库读取: {priority_list}")
                return priority_list
        except Exception as e:
            logger.warning(f"⚠️ [{market}数据源优先级] 从数据库读取失败: {e}，使用默认顺序")

        # 默认优先级
        default_priority = {
            "CN": ["tushare", "akshare", "baostock"],
            "HK": ["yfinance", "akshare"],
            "US": ["yfinance", "alpha_vantage", "finnhub"]
        }
        priority_list = default_priority.get(market, [])
        logger.info(f"📊 [{market}数据源优先级] 使用默认: {priority_list}")
        return priority_list

    def _get_hk_quote_from_yfinance(self, code: str) -> Dict:
        """从yfinance获取港股行情"""
        quote_data = self.hk_provider.get_real_time_price(code)
        if not quote_data:
            raise Exception("无数据")
        return quote_data

    def _get_hk_quote_from_akshare(self, code: str) -> Dict:
        """从AKShare获取港股行情"""
        from tradingagents.dataflows.providers.hk.improved_hk import get_hk_stock_info_akshare
        info = get_hk_stock_info_akshare(code)
        if not info or 'error' in info:
            raise Exception("无数据")

        # 检查是否有价格数据
        if not info.get('price'):
            raise Exception("无价格数据")

        return info
    
    async def _get_us_quote(self, code: str, force_refresh: bool = False) -> Dict:
        """
        获取美股实时行情（带请求去重）
        🔥 按照数据库配置的数据源优先级调用API
        🔥 防止并发请求重复调用API
        """
        # 1. 检查缓存（除非强制刷新）
        if not force_refresh:
            cache_key = self.cache.find_cached_stock_data(
                symbol=code,
                data_source="us_realtime_quote"
            )

            if cache_key:
                cached_data = self.cache.load_stock_data(cache_key)
                if cached_data:
                    logger.info(f"⚡ 从缓存获取美股行情: {code}")
                    return self._parse_cached_data(cached_data, 'US', code)

        # 2. 🔥 请求去重：使用锁确保同一股票同时只有一个API调用
        request_key = f"US_quote_{code}_{force_refresh}"
        lock = self._request_locks[request_key]

        async with lock:
            # 🔥 再次检查缓存（可能在等待锁的过程中，其他请求已经完成并缓存了数据）
            cache_key = self.cache.find_cached_stock_data(
                symbol=code,
                data_source="us_realtime_quote"
            )
            if cache_key:
                cached_data = self.cache.load_stock_data(cache_key)
                if cached_data:
                    # 检查缓存时间，如果是最近1秒内的，说明是并发请求刚刚缓存的
                    try:
                        data_dict = json.loads(cached_data) if isinstance(cached_data, str) else cached_data
                        updated_at = data_dict.get('updated_at', '')
                        if updated_at:
                            cache_time = datetime.fromisoformat(updated_at)
                            time_diff = (datetime.now() - cache_time).total_seconds()
                            if time_diff < 1:  # 1秒内的缓存，说明是并发请求刚刚完成的
                                logger.info(f"⚡ [去重] 使用并发请求的结果: {code} (缓存时间: {time_diff:.2f}秒前)")
                                return self._parse_cached_data(cached_data, 'US', code)
                    except Exception as e:
                        logger.debug(f"检查缓存时间失败: {e}")

                    # 如果不是强制刷新，使用缓存
                    if not force_refresh:
                        logger.info(f"⚡ [去重后] 从缓存获取美股行情: {code}")
                        return self._parse_cached_data(cached_data, 'US', code)

            logger.info(f"🔄 开始获取美股行情: {code} (force_refresh={force_refresh})")

            # 3. 从数据库获取数据源优先级（使用统一方法）
            source_priority = await self._get_source_priority('US')

            # 4. 按优先级尝试各个数据源
            quote_data = None
            data_source = None

            # 数据源名称映射（数据库名称 → 处理函数）
            # 🔥 只有这些是有效的数据源名称：alpha_vantage, yahoo_finance, finnhub
            source_handlers = {
                'alpha_vantage': ('alpha_vantage', self._get_us_quote_from_alpha_vantage),
                'yahoo_finance': ('yfinance', self._get_us_quote_from_yfinance),
                'finnhub': ('finnhub', self._get_us_quote_from_finnhub),
            }

            # 过滤有效数据源并去重
            valid_priority = []
            seen = set()
            for source_name in source_priority:
                source_key = source_name.lower()
                # 只保留有效的数据源
                if source_key in source_handlers and source_key not in seen:
                    seen.add(source_key)
                    valid_priority.append(source_name)

            if not valid_priority:
                logger.warning("⚠️ 数据库中没有配置有效的美股数据源，使用默认顺序")
                valid_priority = ['yahoo_finance', 'alpha_vantage', 'finnhub']

            logger.info(f"📊 [US有效数据源] {valid_priority} (股票: {code})")

            for source_name in valid_priority:
                source_key = source_name.lower()
                handler_name, handler_func = source_handlers[source_key]
                try:
                    # 🔥 使用 asyncio.to_thread 避免阻塞事件循环
                    quote_data = await asyncio.to_thread(handler_func, code)
                    data_source = handler_name

                    if quote_data:
                        logger.info(f"✅ {data_source}获取美股行情成功: {code}")
                        break
                except Exception as e:
                    logger.warning(f"⚠️ {source_name}获取失败 ({code}): {e}")
                    continue

            if not quote_data:
                raise Exception(f"无法获取美股{code}的行情数据：所有数据源均失败")

            # 5. 格式化数据
            formatted_data = {
                'code': code,
                'name': quote_data.get('name', f'美股{code}'),
                'market': 'US',
                'price': quote_data.get('price'),
                'open': quote_data.get('open'),
                'high': quote_data.get('high'),
                'low': quote_data.get('low'),
                'volume': quote_data.get('volume'),
                'change_percent': quote_data.get('change_percent'),
                'trade_date': quote_data.get('trade_date'),
                'currency': quote_data.get('currency', 'USD'),
                'source': data_source,
                'updated_at': datetime.now().isoformat()
            }

            # 6. 保存到缓存
            self.cache.save_stock_data(
                symbol=code,
                data=json.dumps(formatted_data, ensure_ascii=False),
                data_source="us_realtime_quote"
            )
            logger.info(f"💾 美股行情已缓存: {code}")

            return formatted_data

    def _get_us_quote_from_yfinance(self, code: str) -> Dict:
        """从yfinance获取美股行情"""
        import yfinance as yf

        ticker = yf.Ticker(code)
        hist = ticker.history(period='1d')

        if hist.empty:
            raise Exception("无数据")

        latest = hist.iloc[-1]
        info = ticker.info

        return {
            'name': info.get('longName') or info.get('shortName'),
            'price': float(latest['Close']),
            'open': float(latest['Open']),
            'high': float(latest['High']),
            'low': float(latest['Low']),
            'volume': int(latest['Volume']),
            'change_percent': round(((latest['Close'] - latest['Open']) / latest['Open'] * 100), 2),
            'trade_date': hist.index[-1].strftime('%Y-%m-%d'),
            'currency': info.get('currency', 'USD')
        }

    def _get_us_quote_from_alpha_vantage(self, code: str) -> Dict:
        """从Alpha Vantage获取美股行情"""
        try:
            from tradingagents.dataflows.providers.us.alpha_vantage_common import get_api_key, _make_api_request

            # 获取 API Key
            api_key = get_api_key()
            if not api_key:
                raise Exception("Alpha Vantage API Key 未配置")

            # 调用 GLOBAL_QUOTE API
            params = {
                "symbol": code.upper(),
            }

            data = _make_api_request("GLOBAL_QUOTE", params)

            if not data or "Global Quote" not in data:
                raise Exception("Alpha Vantage 返回数据为空")

            quote = data["Global Quote"]

            if not quote:
                raise Exception("无数据")

            # 解析数据
            return {
                'symbol': quote.get('01. symbol', code),
                'price': float(quote.get('05. price', 0)),
                'open': float(quote.get('02. open', 0)),
                'high': float(quote.get('03. high', 0)),
                'low': float(quote.get('04. low', 0)),
                'volume': int(quote.get('06. volume', 0)),
                'latest_trading_day': quote.get('07. latest trading day', ''),
                'previous_close': float(quote.get('08. previous close', 0)),
                'change': float(quote.get('09. change', 0)),
                'change_percent': quote.get('10. change percent', '0%').rstrip('%'),
            }

        except Exception as e:
            logger.error(f"❌ Alpha Vantage获取美股行情失败: {e}")
            raise

    def _get_us_quote_from_finnhub(self, code: str) -> Dict:
        """从Finnhub获取美股行情"""
        try:
            import finnhub
            import os

            # 获取 API Key
            api_key = os.getenv('FINNHUB_API_KEY')
            if not api_key:
                raise Exception("Finnhub API Key 未配置")

            # 创建客户端
            client = finnhub.Client(api_key=api_key)

            # 获取实时报价
            quote = client.quote(code.upper())

            if not quote or 'c' not in quote:
                raise Exception("无数据")

            # 解析数据
            return {
                'symbol': code.upper(),
                'price': quote.get('c', 0),  # current price
                'open': quote.get('o', 0),   # open price
                'high': quote.get('h', 0),   # high price
                'low': quote.get('l', 0),    # low price
                'previous_close': quote.get('pc', 0),  # previous close
                'change': quote.get('d', 0),  # change
                'change_percent': quote.get('dp', 0),  # change percent
                'timestamp': quote.get('t', 0),  # timestamp
            }

        except Exception as e:
            logger.error(f"❌ Finnhub获取美股行情失败: {e}")
            raise
    
    async def _get_hk_info(self, code: str, force_refresh: bool = False) -> Dict:
        """
        获取港股基础信息
        🔥 按照数据库配置的数据源优先级调用API
        """
        # 1. 检查缓存（除非强制刷新）
        if not force_refresh:
            cache_key = self.cache.find_cached_stock_data(
                symbol=code,
                data_source="hk_basic_info"
            )

            if cache_key:
                cached_data = self.cache.load_stock_data(cache_key)
                if cached_data:
                    logger.info(f"⚡ 从缓存获取港股基础信息: {code}")
                    return self._parse_cached_data(cached_data, 'HK', code)

        # 2. 从数据库获取数据源优先级
        source_priority = await self._get_source_priority('HK')

        # 3. 按优先级尝试各个数据源
        info_data = None
        data_source = None

        # 数据源名称映射
        source_handlers = {
            'akshare': ('akshare', self._get_hk_info_from_akshare),
            'yahoo_finance': ('yfinance', self._get_hk_info_from_yfinance),
            'finnhub': ('finnhub', self._get_hk_info_from_finnhub),
        }

        # 过滤有效数据源并去重
        valid_priority = []
        seen = set()
        for source_name in source_priority:
            source_key = source_name.lower()
            if source_key in source_handlers and source_key not in seen:
                seen.add(source_key)
                valid_priority.append(source_name)

        if not valid_priority:
            logger.warning("⚠️ 数据库中没有配置有效的港股基础信息数据源，使用默认顺序")
            valid_priority = ['akshare', 'yahoo_finance', 'finnhub']

        logger.info(f"📊 [HK基础信息有效数据源] {valid_priority}")

        for source_name in valid_priority:
            source_key = source_name.lower()
            handler_name, handler_func = source_handlers[source_key]
            try:
                # 🔥 使用 asyncio.to_thread 避免阻塞事件循环
                import asyncio
                info_data = await asyncio.to_thread(handler_func, code)
                data_source = handler_name

                if info_data:
                    logger.info(f"✅ {data_source}获取港股基础信息成功: {code}")
                    break
            except Exception as e:
                logger.warning(f"⚠️ {source_name}获取基础信息失败: {e}")
                continue

        if not info_data:
            raise Exception(f"无法获取港股{code}的基础信息：所有数据源均失败")

        # 4. 格式化数据
        formatted_data = self._format_hk_info(info_data, code, data_source)

        # 5. 保存到缓存
        self.cache.save_stock_data(
            symbol=code,
            data=json.dumps(formatted_data, ensure_ascii=False),
            data_source="hk_basic_info"
        )
        logger.info(f"💾 港股基础信息已缓存: {code}")

        return formatted_data

    async def _get_us_info(self, code: str, force_refresh: bool = False) -> Dict:
        """
        获取美股基础信息
        🔥 按照数据库配置的数据源优先级调用API
        """
        # 1. 检查缓存（除非强制刷新）
        if not force_refresh:
            cache_key = self.cache.find_cached_stock_data(
                symbol=code,
                data_source="us_basic_info"
            )

            if cache_key:
                cached_data = self.cache.load_stock_data(cache_key)
                if cached_data:
                    logger.info(f"⚡ 从缓存获取美股基础信息: {code}")
                    return self._parse_cached_data(cached_data, 'US', code)

        # 2. 从数据库获取数据源优先级
        source_priority = await self._get_source_priority('US')

        # 3. 按优先级尝试各个数据源
        info_data = None
        data_source = None

        # 数据源名称映射
        source_handlers = {
            'alpha_vantage': ('alpha_vantage', self._get_us_info_from_alpha_vantage),
            'yahoo_finance': ('yfinance', self._get_us_info_from_yfinance),
            'finnhub': ('finnhub', self._get_us_info_from_finnhub),
        }

        # 过滤有效数据源并去重
        valid_priority = []
        seen = set()
        for source_name in source_priority:
            source_key = source_name.lower()
            if source_key in source_handlers and source_key not in seen:
                seen.add(source_key)
                valid_priority.append(source_name)

        if not valid_priority:
            logger.warning("⚠️ 数据库中没有配置有效的美股数据源，使用默认顺序")
            valid_priority = ['yahoo_finance', 'alpha_vantage', 'finnhub']

        logger.info(f"📊 [US基础信息有效数据源] {valid_priority}")

        for source_name in valid_priority:
            source_key = source_name.lower()
            handler_name, handler_func = source_handlers[source_key]
            try:
                # 🔥 使用 asyncio.to_thread 避免阻塞事件循环
                import asyncio
                info_data = await asyncio.to_thread(handler_func, code)
                data_source = handler_name

                if info_data:
                    logger.info(f"✅ {data_source}获取美股基础信息成功: {code}")
                    break
            except Exception as e:
                logger.warning(f"⚠️ {source_name}获取基础信息失败: {e}")
                continue

        if not info_data:
            raise Exception(f"无法获取美股{code}的基础信息：所有数据源均失败")

        # 4. 格式化数据（匹配前端期望的字段名）
        market_cap = info_data.get('market_cap')
        formatted_data = {
            'code': code,
            'name': info_data.get('name') or f'美股{code}',
            'market': 'US',
            'industry': info_data.get('industry'),
            'sector': info_data.get('sector'),
            # 前端期望 total_mv（单位：亿元）
            'total_mv': market_cap / 1e8 if market_cap else None,
            # 前端期望 pe_ttm 或 pe
            'pe_ttm': info_data.get('pe_ratio'),
            'pe': info_data.get('pe_ratio'),
            # 前端期望 pb
            'pb': info_data.get('pb_ratio'),
            # 前端期望 ps（暂无数据）
            'ps': None,
            'ps_ttm': None,
            # 前端期望 roe 和 debt_ratio（暂无数据）
            'roe': None,
            'debt_ratio': None,
            'dividend_yield': info_data.get('dividend_yield'),
            'currency': info_data.get('currency', 'USD'),
            'source': data_source,
            'updated_at': datetime.now().isoformat()
        }

        # 5. 保存到缓存
        self.cache.save_stock_data(
            symbol=code,
            data=json.dumps(formatted_data, ensure_ascii=False),
            data_source="us_basic_info"
        )
        logger.info(f"💾 美股基础信息已缓存: {code}")

        return formatted_data

    async def _get_hk_kline(self, code: str, period: str, limit: int, force_refresh: bool = False) -> List[Dict]:
        """
        获取港股K线数据
        🔥 按照数据库配置的数据源优先级调用API
        """
        # 1. 检查缓存（除非强制刷新）
        cache_key_str = f"hk_kline_{period}_{limit}"
        if not force_refresh:
            cache_key = self.cache.find_cached_stock_data(
                symbol=code,
                data_source=cache_key_str
            )

            if cache_key:
                cached_data = self.cache.load_stock_data(cache_key)
                if cached_data:
                    logger.info(f"⚡ 从缓存获取港股K线: {code}")
                    return self._parse_cached_kline(cached_data)

        # 2. 从数据库获取数据源优先级
        source_priority = await self._get_source_priority('HK')

        # 3. 按优先级尝试各个数据源
        kline_data = None
        data_source = None

        # 数据源名称映射
        source_handlers = {
            'akshare': ('akshare', self._get_hk_kline_from_akshare),
            'yahoo_finance': ('yfinance', self._get_hk_kline_from_yfinance),
            'finnhub': ('finnhub', self._get_hk_kline_from_finnhub),
        }

        # 过滤有效数据源并去重
        valid_priority = []
        seen = set()
        for source_name in source_priority:
            source_key = source_name.lower()
            if source_key in source_handlers and source_key not in seen:
                seen.add(source_key)
                valid_priority.append(source_name)

        if not valid_priority:
            logger.warning("⚠️ 数据库中没有配置有效的港股K线数据源，使用默认顺序")
            valid_priority = ['akshare', 'yahoo_finance', 'finnhub']

        logger.info(f"📊 [HK K线有效数据源] {valid_priority}")

        for source_name in valid_priority:
            source_key = source_name.lower()
            handler_name, handler_func = source_handlers[source_key]
            try:
                # 🔥 使用 asyncio.to_thread 避免阻塞事件循环
                import asyncio
                kline_data = await asyncio.to_thread(handler_func, code, period, limit)
                data_source = handler_name

                if kline_data:
                    logger.info(f"✅ {data_source}获取港股K线成功: {code}")
                    break
            except Exception as e:
                logger.warning(f"⚠️ {source_name}获取K线失败: {e}")
                continue

        if not kline_data:
            raise Exception(f"无法获取港股{code}的K线数据：所有数据源均失败")

        # 4. 保存到缓存
        self.cache.save_stock_data(
            symbol=code,
            data=json.dumps(kline_data, ensure_ascii=False),
            data_source=cache_key_str
        )
        logger.info(f"💾 港股K线已缓存: {code}")

        return kline_data

    async def _get_us_kline(self, code: str, period: str, limit: int, force_refresh: bool = False) -> List[Dict]:
        """
        获取美股K线数据
        🔥 按照数据库配置的数据源优先级调用API
        """
        # 1. 检查缓存（除非强制刷新）
        cache_key_str = f"us_kline_{period}_{limit}"
        if not force_refresh:
            cache_key = self.cache.find_cached_stock_data(
                symbol=code,
                data_source=cache_key_str
            )

            if cache_key:
                cached_data = self.cache.load_stock_data(cache_key)
                if cached_data:
                    logger.info(f"⚡ 从缓存获取美股K线: {code}")
                    return self._parse_cached_kline(cached_data)

        # 2. 从数据库获取数据源优先级
        source_priority = await self._get_source_priority('US')

        # 3. 按优先级尝试各个数据源
        kline_data = None
        data_source = None

        # 数据源名称映射
        source_handlers = {
            'alpha_vantage': ('alpha_vantage', self._get_us_kline_from_alpha_vantage),
            'yahoo_finance': ('yfinance', self._get_us_kline_from_yfinance),
            'finnhub': ('finnhub', self._get_us_kline_from_finnhub),
        }

        # 过滤有效数据源并去重
        valid_priority = []
        seen = set()
        for source_name in source_priority:
            source_key = source_name.lower()
            if source_key in source_handlers and source_key not in seen:
                seen.add(source_key)
                valid_priority.append(source_name)

        if not valid_priority:
            logger.warning("⚠️ 数据库中没有配置有效的美股数据源，使用默认顺序")
            valid_priority = ['yahoo_finance', 'alpha_vantage', 'finnhub']

        logger.info(f"📊 [US K线有效数据源] {valid_priority}")

        for source_name in valid_priority:
            source_key = source_name.lower()
            handler_name, handler_func = source_handlers[source_key]
            try:
                # 🔥 使用 asyncio.to_thread 避免阻塞事件循环
                import asyncio
                kline_data = await asyncio.to_thread(handler_func, code, period, limit)
                data_source = handler_name

                if kline_data:
                    logger.info(f"✅ {data_source}获取美股K线成功: {code}")
                    break
            except Exception as e:
                logger.warning(f"⚠️ {source_name}获取K线失败: {e}")
                continue

        if not kline_data:
            raise Exception(f"无法获取美股{code}的K线数据：所有数据源均失败")

        # 4. 保存到缓存
        self.cache.save_stock_data(
            symbol=code,
            data=json.dumps(kline_data, ensure_ascii=False),
            data_source=cache_key_str
        )
        logger.info(f"💾 美股K线已缓存: {code}")

        return kline_data
    
    def _format_hk_quote(self, data: Dict, code: str, source: str) -> Dict:
        """格式化港股行情数据"""
        return {
            'code': code,
            'name': data.get('name', f'港股{code}'),
            'market': 'HK',
            'price': data.get('price') or data.get('close'),
            'open': data.get('open'),
            'high': data.get('high'),
            'low': data.get('low'),
            'volume': data.get('volume'),
            'currency': data.get('currency', 'HKD'),
            'source': source,
            'trade_date': data.get('timestamp', datetime.now().strftime('%Y-%m-%d')),
            'updated_at': datetime.now().isoformat()
        }

    def _format_hk_info(self, data: Dict, code: str, source: str) -> Dict:
        """格式化港股基础信息"""
        market_cap = data.get('market_cap')
        return {
            'code': code,
            'name': data.get('name', f'港股{code}'),
            'market': 'HK',
            'industry': data.get('industry'),
            'sector': data.get('sector'),
            # 前端期望 total_mv（单位：亿元）
            'total_mv': market_cap / 1e8 if market_cap else None,
            # 前端期望 pe_ttm 或 pe
            'pe_ttm': data.get('pe_ratio'),
            'pe': data.get('pe_ratio'),
            # 前端期望 pb
            'pb': data.get('pb_ratio'),
            # 前端期望 ps
            'ps': data.get('ps_ratio'),
            'ps_ttm': data.get('ps_ratio'),
            # 🔥 从财务指标中获取 roe 和 debt_ratio
            'roe': data.get('roe'),
            'debt_ratio': data.get('debt_ratio'),
            'dividend_yield': data.get('dividend_yield'),
            'currency': data.get('currency', 'HKD'),
            'source': source,
            'updated_at': datetime.now().isoformat()
        }

    def _parse_cached_data(self, cached_data: str, market: str, code: str) -> Dict:
        """解析缓存的数据"""
        try:
            # 尝试解析JSON
            if isinstance(cached_data, str):
                data = json.loads(cached_data)
            else:
                data = cached_data

            # 确保包含必要字段
            if isinstance(data, dict):
                data['market'] = market
                data['code'] = code
                return data
            else:
                raise ValueError("缓存数据格式错误")
        except Exception as e:
            logger.warning(f"⚠️ 解析缓存数据失败: {e}")
            # 返回空数据，触发重新获取
            return None

    def _parse_cached_kline(self, cached_data: str) -> List[Dict]:
        """解析缓存的K线数据"""
        try:
            # 尝试解析JSON
            if isinstance(cached_data, str):
                data = json.loads(cached_data)
            else:
                data = cached_data

            # 确保是列表
            if isinstance(data, list):
                return data
            else:
                raise ValueError("缓存K线数据格式错误")
        except Exception as e:
            logger.warning(f"⚠️ 解析缓存K线数据失败: {e}")
            # 返回空列表，触发重新获取
            return []

    def _get_us_info_from_yfinance(self, code: str) -> Dict:
        """从yfinance获取美股基础信息"""
        import yfinance as yf

        ticker = yf.Ticker(code)
        info = ticker.info

        if not info:
            raise Exception("无数据")

        return {
            'name': info.get('longName') or info.get('shortName'),
            'industry': info.get('industry'),
            'sector': info.get('sector'),
            'market_cap': info.get('marketCap'),
            'pe_ratio': info.get('trailingPE'),
            'pb_ratio': info.get('priceToBook'),
            'dividend_yield': info.get('dividendYield'),
            'currency': info.get('currency', 'USD'),
        }

    def _safe_float(self, value, default=None):
        """安全地转换为浮点数，处理 'None' 字符串和空值"""
        if value is None or value == '' or value == 'None' or value == 'N/A':
            return default
        try:
            return float(value)
        except (ValueError, TypeError):
            return default

    def _get_us_info_from_alpha_vantage(self, code: str) -> Dict:
        """从Alpha Vantage获取美股基础信息"""
        from tradingagents.dataflows.providers.us.alpha_vantage_common import get_api_key, _make_api_request

        # 获取 API Key
        api_key = get_api_key()
        if not api_key:
            raise Exception("Alpha Vantage API Key 未配置")

        # 调用 OVERVIEW API
        params = {"symbol": code.upper()}
        data = _make_api_request("OVERVIEW", params)

        if not data or not data.get('Symbol'):
            raise Exception("无数据")

        return {
            'name': data.get('Name'),
            'industry': data.get('Industry'),
            'sector': data.get('Sector'),
            'market_cap': self._safe_float(data.get('MarketCapitalization')),
            'pe_ratio': self._safe_float(data.get('TrailingPE')),
            'pb_ratio': self._safe_float(data.get('PriceToBookRatio')),
            'dividend_yield': self._safe_float(data.get('DividendYield')),
            'currency': 'USD',
        }

    def _get_us_info_from_finnhub(self, code: str) -> Dict:
        """从Finnhub获取美股基础信息"""
        import finnhub
        import os

        # 获取 API Key
        api_key = os.getenv('FINNHUB_API_KEY')
        if not api_key:
            raise Exception("Finnhub API Key 未配置")

        # 创建客户端
        client = finnhub.Client(api_key=api_key)

        # 获取公司信息
        profile = client.company_profile2(symbol=code.upper())

        if not profile:
            raise Exception("无数据")

        return {
            'name': profile.get('name'),
            'industry': profile.get('finnhubIndustry'),
            'sector': None,  # Finnhub 不提供 sector
            'market_cap': profile.get('marketCapitalization') * 1000000 if profile.get('marketCapitalization') else None,  # 转换为美元
            'pe_ratio': None,  # Finnhub profile 不直接提供 PE
            'pb_ratio': None,  # Finnhub profile 不直接提供 PB
            'dividend_yield': None,  # Finnhub profile 不直接提供股息率
            'currency': profile.get('currency', 'USD'),
        }

    def _get_us_kline_from_yfinance(self, code: str, period: str, limit: int) -> List[Dict]:
        """从yfinance获取美股K线数据"""
        import yfinance as yf

        ticker = yf.Ticker(code)

        # 周期映射
        period_map = {
            'day': '1d',
            'week': '1wk',
            'month': '1mo',
            '5m': '5m',
            '15m': '15m',
            '30m': '30m',
            '60m': '60m'
        }

        interval = period_map.get(period, '1d')
        hist = ticker.history(period=f'{limit}d', interval=interval)

        if hist.empty:
            raise Exception("无数据")

        # 格式化数据
        kline_data = []
        for date, row in hist.iterrows():
            date_str = date.strftime('%Y-%m-%d')
            kline_data.append({
                'date': date_str,
                'trade_date': date_str,  # 前端需要这个字段
                'open': float(row['Open']),
                'high': float(row['High']),
                'low': float(row['Low']),
                'close': float(row['Close']),
                'volume': int(row['Volume'])
            })

        return kline_data

    def _get_us_kline_from_alpha_vantage(self, code: str, period: str, limit: int) -> List[Dict]:
        """从Alpha Vantage获取美股K线数据"""
        from tradingagents.dataflows.providers.us.alpha_vantage_common import get_api_key, _make_api_request
        import pandas as pd

        # 获取 API Key
        api_key = get_api_key()
        if not api_key:
            raise Exception("Alpha Vantage API Key 未配置")

        # 根据周期选择API函数
        if period in ['5m', '15m', '30m', '60m']:
            function = "TIME_SERIES_INTRADAY"
            params = {
                "symbol": code.upper(),
                "interval": period,
                "outputsize": "full"
            }
            time_series_key = f"Time Series ({period})"
        else:
            function = "TIME_SERIES_DAILY"
            params = {
                "symbol": code.upper(),
                "outputsize": "full"
            }
            time_series_key = "Time Series (Daily)"

        data = _make_api_request(function, params)

        if not data or time_series_key not in data:
            raise Exception("无数据")

        time_series = data[time_series_key]

        # 转换为 DataFrame
        df = pd.DataFrame.from_dict(time_series, orient='index')
        df.index = pd.to_datetime(df.index)
        df = df.sort_index(ascending=False)  # 最新的在前

        # 限制数量
        df = df.head(limit)

        # 格式化数据
        kline_data = []
        for date, row in df.iterrows():
            date_str = date.strftime('%Y-%m-%d')
            kline_data.append({
                'date': date_str,
                'trade_date': date_str,  # 前端需要这个字段
                'open': float(row['1. open']),
                'high': float(row['2. high']),
                'low': float(row['3. low']),
                'close': float(row['4. close']),
                'volume': int(row['5. volume'])
            })

        return kline_data

    def _get_us_kline_from_finnhub(self, code: str, period: str, limit: int) -> List[Dict]:
        """从Finnhub获取美股K线数据"""
        import finnhub
        import os
        from datetime import datetime, timedelta

        # 获取 API Key
        api_key = os.getenv('FINNHUB_API_KEY')
        if not api_key:
            raise Exception("Finnhub API Key 未配置")

        # 创建客户端
        client = finnhub.Client(api_key=api_key)

        # 计算日期范围
        end_date = datetime.now()

        # 根据周期计算开始日期
        if period == 'day':
            start_date = end_date - timedelta(days=limit)
            resolution = 'D'
        elif period == 'week':
            start_date = end_date - timedelta(weeks=limit)
            resolution = 'W'
        elif period == 'month':
            start_date = end_date - timedelta(days=limit * 30)
            resolution = 'M'
        elif period == '5m':
            start_date = end_date - timedelta(days=limit)
            resolution = '5'
        elif period == '15m':
            start_date = end_date - timedelta(days=limit)
            resolution = '15'
        elif period == '30m':
            start_date = end_date - timedelta(days=limit)
            resolution = '30'
        elif period == '60m':
            start_date = end_date - timedelta(days=limit)
            resolution = '60'
        else:
            start_date = end_date - timedelta(days=limit)
            resolution = 'D'

        # 获取K线数据
        candles = client.stock_candles(
            code.upper(),
            resolution,
            int(start_date.timestamp()),
            int(end_date.timestamp())
        )

        if not candles or candles.get('s') != 'ok':
            raise Exception("无数据")

        # 格式化数据
        kline_data = []
        for i in range(len(candles['t'])):
            date_str = datetime.fromtimestamp(candles['t'][i]).strftime('%Y-%m-%d')
            kline_data.append({
                'date': date_str,
                'trade_date': date_str,  # 前端需要这个字段
                'open': float(candles['o'][i]),
                'high': float(candles['h'][i]),
                'low': float(candles['l'][i]),
                'close': float(candles['c'][i]),
                'volume': int(candles['v'][i])
            })

        return kline_data

    async def get_hk_news(self, code: str, days: int = 2, limit: int = 50) -> Dict:
        """
        获取港股新闻

        Args:
            code: 股票代码
            days: 回溯天数
            limit: 返回数量限制

        Returns:
            包含新闻列表和数据源的字典
        """
        from datetime import datetime, timedelta

        logger.info(f"📰 开始获取港股新闻: {code}, days={days}, limit={limit}")

        # 1. 尝试从缓存获取
        cache_key_str = f"hk_news_{days}_{limit}"
        cache_key = self.cache.find_cached_stock_data(
            symbol=code,
            data_source=cache_key_str
        )

        if cache_key:
            cached_data = self.cache.load_stock_data(cache_key)
            if cached_data:
                logger.info(f"⚡ 从缓存获取港股新闻: {code}")
                return json.loads(cached_data)

        # 2. 从数据库获取数据源优先级
        source_priority = await self._get_source_priority('HK')

        # 3. 按优先级尝试各个数据源
        news_data = None
        data_source = None

        # 数据源名称映射
        source_handlers = {
            'akshare': ('akshare', self._get_hk_news_from_akshare),
            'finnhub': ('finnhub', self._get_hk_news_from_finnhub),
        }

        # 过滤有效数据源并去重
        valid_priority = []
        seen = set()
        for source_name in source_priority:
            source_key = source_name.lower()
            if source_key in source_handlers and source_key not in seen:
                seen.add(source_key)
                valid_priority.append(source_name)

        if not valid_priority:
            logger.warning("⚠️ 数据库中没有配置有效的港股新闻数据源，使用默认顺序")
            valid_priority = ['akshare', 'finnhub']

        logger.info(f"📊 [HK新闻有效数据源] {valid_priority}")

        for source_name in valid_priority:
            source_key = source_name.lower()
            handler_name, handler_func = source_handlers[source_key]
            try:
                # 🔥 使用 asyncio.to_thread 避免阻塞事件循环
                import asyncio
                news_data = await asyncio.to_thread(handler_func, code, days, limit)
                data_source = handler_name

                if news_data:
                    logger.info(f"✅ {data_source}获取港股新闻成功: {code}, 返回 {len(news_data)} 条")
                    break
            except Exception as e:
                logger.warning(f"⚠️ {source_name}获取新闻失败: {e}")
                continue

        if not news_data:
            logger.warning(f"⚠️ 无法获取港股{code}的新闻数据：所有数据源均失败")
            news_data = []
            data_source = 'none'

        # 4. 构建返回数据
        result = {
            'code': code,
            'days': days,
            'limit': limit,
            'source': data_source,
            'items': news_data
        }

        # 5. 缓存数据
        self.cache.save_stock_data(
            symbol=code,
            data=json.dumps(result, ensure_ascii=False),
            data_source=cache_key_str
        )

        return result

    async def get_us_news(self, code: str, days: int = 2, limit: int = 50) -> Dict:
        """
        获取美股新闻

        Args:
            code: 股票代码
            days: 回溯天数
            limit: 返回数量限制

        Returns:
            包含新闻列表和数据源的字典
        """
        from datetime import datetime, timedelta

        logger.info(f"📰 开始获取美股新闻: {code}, days={days}, limit={limit}")

        # 1. 尝试从缓存获取
        cache_key_str = f"us_news_{days}_{limit}"
        cache_key = self.cache.find_cached_stock_data(
            symbol=code,
            data_source=cache_key_str
        )

        if cache_key:
            cached_data = self.cache.load_stock_data(cache_key)
            if cached_data:
                logger.info(f"⚡ 从缓存获取美股新闻: {code}")
                return json.loads(cached_data)

        # 2. 从数据库获取数据源优先级
        source_priority = await self._get_source_priority('US')

        # 3. 按优先级尝试各个数据源
        news_data = None
        data_source = None

        # 数据源名称映射
        source_handlers = {
            'alpha_vantage': ('alpha_vantage', self._get_us_news_from_alpha_vantage),
            'finnhub': ('finnhub', self._get_us_news_from_finnhub),
        }

        # 过滤有效数据源并去重
        valid_priority = []
        seen = set()
        for source_name in source_priority:
            source_key = source_name.lower()
            if source_key in source_handlers and source_key not in seen:
                seen.add(source_key)
                valid_priority.append(source_name)

        if not valid_priority:
            logger.warning("⚠️ 数据库中没有配置有效的美股新闻数据源，使用默认顺序")
            valid_priority = ['alpha_vantage', 'finnhub']

        logger.info(f"📊 [US新闻有效数据源] {valid_priority}")

        for source_name in valid_priority:
            source_key = source_name.lower()
            handler_name, handler_func = source_handlers[source_key]
            try:
                # 🔥 使用 asyncio.to_thread 避免阻塞事件循环
                import asyncio
                news_data = await asyncio.to_thread(handler_func, code, days, limit)
                data_source = handler_name

                if news_data:
                    logger.info(f"✅ {data_source}获取美股新闻成功: {code}, 返回 {len(news_data)} 条")
                    break
            except Exception as e:
                logger.warning(f"⚠️ {source_name}获取新闻失败: {e}")
                continue

        if not news_data:
            logger.warning(f"⚠️ 无法获取美股{code}的新闻数据：所有数据源均失败")
            news_data = []
            data_source = 'none'

        # 4. 构建返回数据
        result = {
            'code': code,
            'days': days,
            'limit': limit,
            'source': data_source,
            'items': news_data
        }

        # 5. 缓存数据
        self.cache.save_stock_data(
            symbol=code,
            data=json.dumps(result, ensure_ascii=False),
            data_source=cache_key_str
        )

        return result

    def _get_us_news_from_alpha_vantage(self, code: str, days: int, limit: int) -> List[Dict]:
        """从Alpha Vantage获取美股新闻"""
        from tradingagents.dataflows.providers.us.alpha_vantage_common import get_api_key, _make_api_request
        from datetime import datetime, timedelta

        # 获取 API Key
        api_key = get_api_key()
        if not api_key:
            raise Exception("Alpha Vantage API Key 未配置")

        # 计算时间范围
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)

        # 调用 NEWS_SENTIMENT API
        params = {
            "tickers": code.upper(),
            "time_from": start_date.strftime('%Y%m%dT%H%M'),
            "time_to": end_date.strftime('%Y%m%dT%H%M'),
            "sort": "LATEST",
            "limit": str(limit),
        }

        data = _make_api_request("NEWS_SENTIMENT", params)

        if not data or 'feed' not in data:
            raise Exception("无数据")

        # 格式化新闻数据
        news_list = []
        for article in data.get('feed', [])[:limit]:
            # 解析时间
            time_published = article.get('time_published', '')
            try:
                # Alpha Vantage 时间格式: 20240101T120000
                pub_time = datetime.strptime(time_published, '%Y%m%dT%H%M%S')
                pub_time_str = pub_time.strftime('%Y-%m-%d %H:%M:%S')
            except:
                pub_time_str = time_published

            # 提取相关股票的情感分数
            sentiment_score = None
            sentiment_label = article.get('overall_sentiment_label', 'Neutral')

            ticker_sentiment = article.get('ticker_sentiment', [])
            for ts in ticker_sentiment:
                if ts.get('ticker', '').upper() == code.upper():
                    sentiment_score = ts.get('ticker_sentiment_score')
                    sentiment_label = ts.get('ticker_sentiment_label', sentiment_label)
                    break

            news_list.append({
                'title': article.get('title', ''),
                'summary': article.get('summary', ''),
                'url': article.get('url', ''),
                'source': article.get('source', ''),
                'publish_time': pub_time_str,
                'sentiment': sentiment_label,
                'sentiment_score': sentiment_score,
            })

        return news_list

    def _get_us_news_from_finnhub(self, code: str, days: int, limit: int) -> List[Dict]:
        """从Finnhub获取美股新闻"""
        import finnhub
        import os
        from datetime import datetime, timedelta

        # 获取 API Key
        api_key = os.getenv('FINNHUB_API_KEY')
        if not api_key:
            raise Exception("Finnhub API Key 未配置")

        # 创建客户端
        client = finnhub.Client(api_key=api_key)

        # 计算时间范围
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)

        # 获取公司新闻
        news = client.company_news(
            code.upper(),
            _from=start_date.strftime('%Y-%m-%d'),
            to=end_date.strftime('%Y-%m-%d')
        )

        if not news:
            raise Exception("无数据")

        # 格式化新闻数据
        news_list = []
        for article in news[:limit]:
            # 解析时间戳
            timestamp = article.get('datetime', 0)
            pub_time = datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')

            news_list.append({
                'title': article.get('headline', ''),
                'summary': article.get('summary', ''),
                'url': article.get('url', ''),
                'source': article.get('source', ''),
                'publish_time': pub_time,
                'sentiment': None,  # Finnhub 不提供情感分析
                'sentiment_score': None,
            })

        return news_list

    def _get_hk_news_from_finnhub(self, code: str, days: int, limit: int) -> List[Dict]:
        """从Finnhub获取港股新闻"""
        import finnhub
        import os
        from datetime import datetime, timedelta

        # 获取 API Key
        api_key = os.getenv('FINNHUB_API_KEY')
        if not api_key:
            raise Exception("Finnhub API Key 未配置")

        # 创建客户端
        client = finnhub.Client(api_key=api_key)

        # 计算时间范围
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)

        # 港股代码需要添加 .HK 后缀
        hk_symbol = f"{code}.HK" if not code.endswith('.HK') else code

        # 获取公司新闻
        news = client.company_news(
            hk_symbol,
            _from=start_date.strftime('%Y-%m-%d'),
            to=end_date.strftime('%Y-%m-%d')
        )

        if not news:
            raise Exception("无数据")

        # 格式化新闻数据
        news_list = []
        for article in news[:limit]:
            # 解析时间戳
            timestamp = article.get('datetime', 0)
            pub_time = datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')

            news_list.append({
                'title': article.get('headline', ''),
                'summary': article.get('summary', ''),
                'url': article.get('url', ''),
                'source': article.get('source', ''),
                'publish_time': pub_time,
                'sentiment': None,  # Finnhub 不提供情感分析
                'sentiment_score': None,
            })

        return news_list

    def _get_hk_info_from_akshare(self, code: str) -> Dict:
        """从AKShare获取港股基础信息和财务指标"""
        from tradingagents.dataflows.providers.hk.improved_hk import (
            get_hk_stock_info_akshare,
            get_hk_financial_indicators
        )

        # 1. 获取基础信息（包含当前价格）
        info = get_hk_stock_info_akshare(code)
        if not info or 'error' in info:
            raise Exception("无数据")

        # 2. 获取财务指标（EPS、BPS、ROE、负债率等）
        financial_indicators = {}
        try:
            financial_indicators = get_hk_financial_indicators(code)
            logger.info(f"✅ 获取港股{code}财务指标成功: {list(financial_indicators.keys())}")
        except Exception as e:
            logger.warning(f"⚠️ 获取港股{code}财务指标失败: {e}")

        # 3. 计算 PE、PB、PS（参考分析模块的计算方式）
        current_price = info.get('price')  # 当前价格
        pe_ratio = None
        pb_ratio = None
        ps_ratio = None

        if current_price and financial_indicators:
            # 计算 PE = 当前价 / EPS_TTM
            eps_ttm = financial_indicators.get('eps_ttm')
            if eps_ttm and eps_ttm > 0:
                pe_ratio = current_price / eps_ttm
                logger.info(f"📊 计算 PE: {current_price} / {eps_ttm} = {pe_ratio:.2f}")

            # 计算 PB = 当前价 / BPS
            bps = financial_indicators.get('bps')
            if bps and bps > 0:
                pb_ratio = current_price / bps
                logger.info(f"📊 计算 PB: {current_price} / {bps} = {pb_ratio:.2f}")

            # 计算 PS = 市值 / 营业收入（需要市值数据，暂时无法计算）
            # ps_ratio 暂时为 None

        # 4. 合并数据
        return {
            'name': info.get('name', f'港股{code}'),
            'market_cap': None,  # AKShare 基础信息不包含市值
            'industry': None,
            'sector': None,
            # 🔥 计算得到的估值指标
            'pe_ratio': pe_ratio,
            'pb_ratio': pb_ratio,
            'ps_ratio': ps_ratio,
            'dividend_yield': None,
            'currency': 'HKD',
            # 🔥 从财务指标中获取
            'roe': financial_indicators.get('roe_avg'),  # 平均净资产收益率
            'debt_ratio': financial_indicators.get('debt_asset_ratio'),  # 资产负债率
        }

    def _get_hk_info_from_yfinance(self, code: str) -> Dict:
        """从Yahoo Finance获取港股基础信息"""
        import yfinance as yf

        ticker = yf.Ticker(f"{code}.HK")
        info = ticker.info

        return {
            'name': info.get('longName') or info.get('shortName') or f'港股{code}',
            'market_cap': info.get('marketCap'),
            'industry': info.get('industry'),
            'sector': info.get('sector'),
            'pe_ratio': info.get('trailingPE'),
            'pb_ratio': info.get('priceToBook'),
            'dividend_yield': info.get('dividendYield'),
            'currency': info.get('currency', 'HKD'),
        }

    def _get_hk_info_from_finnhub(self, code: str) -> Dict:
        """从Finnhub获取港股基础信息"""
        import finnhub
        import os

        # 获取 API Key
        api_key = os.getenv('FINNHUB_API_KEY')
        if not api_key:
            raise Exception("Finnhub API Key 未配置")

        # 创建客户端
        client = finnhub.Client(api_key=api_key)

        # 港股代码需要添加 .HK 后缀
        hk_symbol = f"{code}.HK" if not code.endswith('.HK') else code

        # 获取公司基本信息
        profile = client.company_profile2(symbol=hk_symbol)

        if not profile:
            raise Exception("无数据")

        return {
            'name': profile.get('name', f'港股{code}'),
            'market_cap': profile.get('marketCapitalization') * 1e6 if profile.get('marketCapitalization') else None,  # Finnhub返回的是百万单位
            'industry': profile.get('finnhubIndustry'),
            'sector': None,
            'pe_ratio': None,
            'pb_ratio': None,
            'dividend_yield': None,
            'currency': profile.get('currency', 'HKD'),
        }

    def _get_hk_kline_from_akshare(self, code: str, period: str, limit: int) -> List[Dict]:
        """从AKShare获取港股K线数据"""
        import akshare as ak
        import pandas as pd
        from datetime import datetime, timedelta
        from tradingagents.dataflows.providers.hk.improved_hk import get_improved_hk_provider

        # 标准化代码
        provider = get_improved_hk_provider()
        normalized_code = provider._normalize_hk_symbol(code)

        # 直接使用 AKShare API
        df = ak.stock_hk_daily(symbol=normalized_code, adjust="qfq")

        if df is None or df.empty:
            raise Exception("无数据")

        # 过滤最近的数据
        df = df.tail(limit)

        # 格式化数据
        kline_data = []
        for _, row in df.iterrows():
            # AKShare 返回的列名：date, open, close, high, low, volume
            date_str = row['date'].strftime('%Y-%m-%d') if hasattr(row['date'], 'strftime') else str(row['date'])
            kline_data.append({
                'date': date_str,
                'trade_date': date_str,
                'open': float(row['open']),
                'high': float(row['high']),
                'low': float(row['low']),
                'close': float(row['close']),
                'volume': int(row['volume']) if 'volume' in row else 0
            })

        return kline_data

    def _get_hk_kline_from_yfinance(self, code: str, period: str, limit: int) -> List[Dict]:
        """从Yahoo Finance获取港股K线数据"""
        import yfinance as yf
        import pandas as pd

        ticker = yf.Ticker(f"{code}.HK")

        # 周期映射
        period_map = {
            'day': '1d',
            'week': '1wk',
            'month': '1mo',
            '5m': '5m',
            '15m': '15m',
            '30m': '30m',
            '60m': '60m'
        }

        interval = period_map.get(period, '1d')
        hist = ticker.history(period=f'{limit}d', interval=interval)

        if hist.empty:
            raise Exception("无数据")

        # 格式化数据
        kline_data = []
        for date, row in hist.iterrows():
            date_str = date.strftime('%Y-%m-%d')
            kline_data.append({
                'date': date_str,
                'trade_date': date_str,
                'open': float(row['Open']),
                'high': float(row['High']),
                'low': float(row['Low']),
                'close': float(row['Close']),
                'volume': int(row['Volume'])
            })

        return kline_data[-limit:]  # 返回最后limit条

    def _get_hk_kline_from_finnhub(self, code: str, period: str, limit: int) -> List[Dict]:
        """从Finnhub获取港股K线数据"""
        import finnhub
        import os
        from datetime import datetime, timedelta

        # 获取 API Key
        api_key = os.getenv('FINNHUB_API_KEY')
        if not api_key:
            raise Exception("Finnhub API Key 未配置")

        # 创建客户端
        client = finnhub.Client(api_key=api_key)

        # 港股代码需要添加 .HK 后缀
        hk_symbol = f"{code}.HK" if not code.endswith('.HK') else code

        # 周期映射
        resolution_map = {
            'day': 'D',
            'week': 'W',
            'month': 'M',
            '5m': '5',
            '15m': '15',
            '30m': '30',
            '60m': '60'
        }

        resolution = resolution_map.get(period, 'D')

        # 计算时间范围
        end_time = int(datetime.now().timestamp())
        start_time = int((datetime.now() - timedelta(days=limit * 2)).timestamp())

        # 获取K线数据
        candles = client.stock_candles(hk_symbol, resolution, start_time, end_time)

        if not candles or candles.get('s') != 'ok':
            raise Exception("无数据")

        # 格式化数据
        kline_data = []
        for i in range(len(candles['t'])):
            date_str = datetime.fromtimestamp(candles['t'][i]).strftime('%Y-%m-%d')
            kline_data.append({
                'date': date_str,
                'trade_date': date_str,
                'open': float(candles['o'][i]),
                'high': float(candles['h'][i]),
                'low': float(candles['l'][i]),
                'close': float(candles['c'][i]),
                'volume': int(candles['v'][i])
            })

        return kline_data[-limit:]  # 返回最后limit条

    def _get_hk_news_from_akshare(self, code: str, days: int, limit: int) -> List[Dict]:
        """从AKShare获取港股新闻"""
        try:
            import akshare as ak
            from datetime import datetime, timedelta

            # AKShare 的港股新闻接口
            # 注意：AKShare 可能没有专门的港股新闻接口，这里使用通用新闻接口
            # 如果没有合适的接口，抛出异常让系统尝试下一个数据源

            # 尝试获取港股新闻（使用东方财富港股新闻）
            try:
                df = ak.stock_news_em(symbol=code)
                if df is None or df.empty:
                    raise Exception("无数据")

                # 格式化新闻数据
                news_list = []
                for _, row in df.head(limit).iterrows():
                    pub_time = row['发布时间'] if '发布时间' in row else datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    news_list.append({
                        'title': row['新闻标题'] if '新闻标题' in row else '',
                        'summary': row['新闻内容'] if '新闻内容' in row else '',
                        'url': row['新闻链接'] if '新闻链接' in row else '',
                        'source': 'AKShare-东方财富',
                        'publish_time': pub_time,
                        'sentiment': None,
                        'sentiment_score': None,
                    })

                return news_list
            except Exception as e:
                logger.debug(f"AKShare 东方财富接口失败: {e}")
                raise Exception("AKShare 暂不支持港股新闻")

        except Exception as e:
            logger.warning(f"⚠️ AKShare获取港股新闻失败: {e}")
            raise

