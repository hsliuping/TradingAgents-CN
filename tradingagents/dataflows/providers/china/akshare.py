"""
AKShare统一数据提供器
基于AKShare SDK的统一数据同步方案，提供标准化的数据接口
"""
import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, List, Optional, Union
import pandas as pd

from ..base_provider import BaseStockDataProvider

logger = logging.getLogger(__name__)


class AKShareProvider(BaseStockDataProvider):
    """
    AKShare统一数据提供器
    
    提供标准化的股票数据接口，支持：
    - 股票基础信息获取
    - 历史行情数据
    - 实时行情数据
    - 财务数据
    - 港股数据支持
    """
    
    def __init__(self):
        super().__init__("AKShare")
        self.ak = None
        self.connected = False
        self._stock_list_cache = None  # 缓存股票列表，避免重复获取
        self._cache_time = None  # 缓存时间
        self._initialize_akshare()
    
    def _initialize_akshare(self):
        """初始化AKShare连接"""
        try:
            import akshare as ak
            import requests
            import time

            # 尝试导入 curl_cffi，如果可用则使用它来绕过反爬虫
            try:
                from curl_cffi import requests as curl_requests
                use_curl_cffi = True
                logger.info("🔧 检测到 curl_cffi，将使用它来模拟真实浏览器 TLS 指纹")
            except ImportError:
                use_curl_cffi = False
                logger.warning("⚠️ curl_cffi 未安装，将使用标准 requests（可能被反爬虫拦截）")
                logger.warning("   建议安装: pip install curl-cffi")

            # 修复AKShare的bug：设置requests的默认headers，并添加请求延迟
            # AKShare的stock_news_em()函数没有设置必要的headers，导致API返回空响应
            if not hasattr(requests, '_akshare_headers_patched'):
                original_get = requests.get
                last_request_time = {'time': 0}  # 使用字典以便在闭包中修改

                def patched_get(url, **kwargs):
                    """
                    包装requests.get方法，自动添加必要的headers和请求延迟
                    修复AKShare stock_news_em()函数缺少headers的问题
                    如果可用，使用 curl_cffi 模拟真实浏览器 TLS 指纹
                    """
                    # 添加请求延迟，避免被反爬虫封禁
                    # 只对东方财富网的请求添加延迟
                    if 'eastmoney.com' in url:
                        current_time = time.time()
                        time_since_last_request = current_time - last_request_time['time']
                        if time_since_last_request < 0.5:  # 至少间隔0.5秒
                            time.sleep(0.5 - time_since_last_request)
                        last_request_time['time'] = time.time()

                    # 如果是东方财富网的请求，且 curl_cffi 可用，使用它来绕过反爬虫
                    if use_curl_cffi and 'eastmoney.com' in url:
                        try:
                            # 使用 curl_cffi 模拟 Chrome 120 的 TLS 指纹
                            # 注意：使用 impersonate 时，不要传递自定义 headers，让 curl_cffi 自动设置
                            curl_kwargs = {
                                'timeout': kwargs.get('timeout', 10),
                                'impersonate': "chrome120"  # 模拟 Chrome 120
                            }

                            # 只传递非 headers 的参数
                            if 'params' in kwargs:
                                curl_kwargs['params'] = kwargs['params']
                            # 不传递 headers，让 impersonate 自动设置
                            if 'data' in kwargs:
                                curl_kwargs['data'] = kwargs['data']
                            if 'json' in kwargs:
                                curl_kwargs['json'] = kwargs['json']

                            response = curl_requests.get(url, **curl_kwargs)
                            # curl_cffi 的响应对象已经兼容 requests.Response
                            return response
                        except Exception as e:
                            # curl_cffi 失败，回退到标准 requests
                            error_msg = str(e)
                            # 忽略 TLS 库错误和 400 错误的详细日志（这是 Docker 环境的已知问题）
                            if 'invalid library' not in error_msg and '400' not in error_msg:
                                logger.warning(f"⚠️ curl_cffi 请求失败，回退到标准 requests: {e}")

                    # 标准 requests 请求（非东方财富网，或 curl_cffi 不可用/失败）
                    # 设置浏览器请求头
                    if 'headers' not in kwargs or kwargs['headers'] is None:
                        kwargs['headers'] = {
                            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
                            'Accept-Encoding': 'gzip, deflate, br',
                            'Referer': 'https://www.eastmoney.com/',
                            'Connection': 'keep-alive',
                        }
                    elif isinstance(kwargs['headers'], dict):
                        # 如果已有headers，确保包含必要的字段
                        if 'User-Agent' not in kwargs['headers']:
                            kwargs['headers']['User-Agent'] = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
                        if 'Referer' not in kwargs['headers']:
                            kwargs['headers']['Referer'] = 'https://www.eastmoney.com/'
                        if 'Accept' not in kwargs['headers']:
                            kwargs['headers']['Accept'] = 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8'
                        if 'Accept-Language' not in kwargs['headers']:
                            kwargs['headers']['Accept-Language'] = 'zh-CN,zh;q=0.9,en;q=0.8'

                    # 添加重试机制（最多3次）
                    max_retries = 3
                    for attempt in range(max_retries):
                        try:
                            return original_get(url, **kwargs)
                        except Exception as e:
                            # 检查是否是SSL错误
                            error_str = str(e)
                            is_ssl_error = ('SSL' in error_str or 'ssl' in error_str or
                                          'UNEXPECTED_EOF_WHILE_READING' in error_str)

                            if is_ssl_error and attempt < max_retries - 1:
                                # SSL错误，等待后重试
                                wait_time = 0.5 * (attempt + 1)  # 递增等待时间
                                time.sleep(wait_time)
                                continue
                            else:
                                # 非SSL错误或已达到最大重试次数，直接抛出
                                raise

                # 应用patch
                requests.get = patched_get
                requests._akshare_headers_patched = True

                if use_curl_cffi:
                    logger.info("🔧 已修复AKShare的headers问题，使用 curl_cffi 模拟真实浏览器（Chrome 120）")
                else:
                    logger.info("🔧 已修复AKShare的headers问题，并添加请求延迟（0.5秒）")

            self.ak = ak
            self.connected = True

            # 配置超时和重试
            self._configure_timeout()

            logger.info("✅ AKShare连接成功")
        except ImportError as e:
            logger.error(f"❌ AKShare未安装: {e}")
            self.connected = False
        except Exception as e:
            logger.error(f"❌ AKShare初始化失败: {e}")
            self.connected = False

    def _get_stock_news_direct(self, symbol: str, limit: int = 10) -> Optional[pd.DataFrame]:
        """
        直接调用东方财富网新闻 API（绕过 AKShare）
        使用 curl_cffi 模拟真实浏览器，适用于 Docker 环境

        Args:
            symbol: 股票代码
            limit: 返回数量限制

        Returns:
            新闻 DataFrame 或 None
        """
        try:
            from curl_cffi import requests as curl_requests
            import json
            import time
            import os

            # 标准化股票代码
            symbol_6 = symbol.zfill(6)

            # 构建请求参数
            url = "https://search-api-web.eastmoney.com/search/jsonp"
            param = {
                "uid": "",
                "keyword": symbol_6,
                "type": ["cmsArticleWebOld"],
                "client": "web",
                "clientType": "web",
                "clientVersion": "curr",
                "param": {
                    "cmsArticleWebOld": {
                        "searchScope": "default",
                        "sort": "default",
                        "pageIndex": 1,
                        "pageSize": limit,
                        "preTag": "<em>",
                        "postTag": "</em>"
                    }
                }
            }

            params = {
                "cb": f"jQuery{int(time.time() * 1000)}",
                "param": json.dumps(param),
                "_": str(int(time.time() * 1000))
            }

            # 使用 curl_cffi 发送请求
            response = curl_requests.get(
                url,
                params=params,
                timeout=10,
                impersonate="chrome120"
            )

            if response.status_code != 200:
                self.logger.error(f"❌ {symbol} 东方财富网 API 返回错误: {response.status_code}")
                return None

            # 解析 JSONP 响应
            text = response.text
            if text.startswith("jQuery"):
                text = text[text.find("(")+1:text.rfind(")")]

            data = json.loads(text)

            # 检查返回数据
            if "result" not in data or "cmsArticleWebOld" not in data["result"]:
                self.logger.error(f"❌ {symbol} 东方财富网 API 返回数据结构异常")
                return None

            articles = data["result"]["cmsArticleWebOld"]

            if not articles:
                self.logger.warning(f"⚠️ {symbol} 未获取到新闻")
                return None

            # 转换为 DataFrame（与 AKShare 格式兼容）
            news_data = []
            for article in articles:
                news_data.append({
                    "新闻标题": article.get("title", ""),
                    "新闻内容": article.get("content", ""),
                    "发布时间": article.get("date", ""),
                    "新闻链接": article.get("url", ""),
                    "关键词": article.get("keywords", ""),
                    "新闻来源": article.get("source", "东方财富网"),
                    "新闻类型": article.get("type", "")
                })

            df = pd.DataFrame(news_data)
            self.logger.info(f"✅ {symbol} 直接调用 API 获取新闻成功: {len(df)} 条")
            return df

        except Exception as e:
            self.logger.error(f"❌ {symbol} 直接调用 API 失败: {e}")
            return None

    def _configure_timeout(self):
        """配置AKShare的超时设置"""
        try:
            import socket
            socket.setdefaulttimeout(60)  # 60秒超时
            logger.info("🔧 AKShare超时配置完成: 60秒")
        except Exception as e:
            logger.warning(f"⚠️ AKShare超时配置失败: {e}")
    
    async def connect(self) -> bool:
        """连接到AKShare数据源"""
        return await self.test_connection()

    async def test_connection(self) -> bool:
        """测试AKShare连接"""
        if not self.connected:
            return False

        # AKShare 是基于网络爬虫的库，不需要传统的"连接"测试
        # 只要库已经导入成功，就认为可用
        # 实际的网络请求会在具体调用时进行，并有各自的错误处理
        logger.info("✅ AKShare连接测试成功（库已加载）")
        return True
    
    def get_stock_list_sync(self) -> Optional[pd.DataFrame]:
        """获取股票列表（同步版本）"""
        if not self.connected:
            return None

        try:
            logger.info("📋 获取AKShare股票列表（同步）...")
            stock_df = self.ak.stock_info_a_code_name()

            if stock_df is None or stock_df.empty:
                logger.warning("⚠️ AKShare股票列表为空")
                return None

            logger.info(f"✅ AKShare股票列表获取成功: {len(stock_df)}只股票")
            return stock_df

        except Exception as e:
            logger.error(f"❌ AKShare获取股票列表失败: {e}")
            return None

    async def get_stock_list(self) -> List[Dict[str, Any]]:
        """
        获取股票列表

        Returns:
            股票列表，包含代码和名称
        """
        if not self.connected:
            return []

        try:
            logger.info("📋 获取AKShare股票列表...")

            # 使用线程池异步获取股票列表，添加超时保护
            def fetch_stock_list():
                return self.ak.stock_info_a_code_name()

            stock_df = await asyncio.to_thread(fetch_stock_list)

            if stock_df is None or stock_df.empty:
                logger.warning("⚠️ AKShare股票列表为空")
                return []

            # 转换为标准格式
            stock_list = []
            for _, row in stock_df.iterrows():
                stock_list.append({
                    "code": str(row.get("code", "")),
                    "name": str(row.get("name", "")),
                    "source": "akshare"
                })

            logger.info(f"✅ AKShare股票列表获取成功: {len(stock_list)}只股票")
            return stock_list

        except Exception as e:
            logger.error(f"❌ AKShare获取股票列表失败: {e}")
            return []
    
    async def get_stock_basic_info(self, code: str) -> Optional[Dict[str, Any]]:
        """
        获取股票基础信息
        
        Args:
            code: 股票代码
            
        Returns:
            标准化的股票基础信息
        """
        if not self.connected:
            return None
        
        try:
            logger.debug(f"📊 获取{code}基础信息...")
            
            # 获取股票基本信息
            stock_info = await self._get_stock_info_detail(code)
            
            if not stock_info:
                logger.warning(f"⚠️ 未找到{code}的基础信息")
                return None
            
            # 转换为标准化字典
            basic_info = {
                "code": code,
                "name": stock_info.get("name", f"股票{code}"),
                "area": stock_info.get("area", "未知"),
                "industry": stock_info.get("industry", "未知"),
                "market": self._determine_market(code),
                "list_date": stock_info.get("list_date", ""),
                # 扩展字段
                "full_symbol": self._get_full_symbol(code),
                "market_info": self._get_market_info(code),
                "data_source": "akshare",
                "last_sync": datetime.now(timezone.utc),
                "sync_status": "success"
            }
            
            logger.debug(f"✅ {code}基础信息获取成功")
            return basic_info
            
        except Exception as e:
            logger.error(f"❌ 获取{code}基础信息失败: {e}")
            return None
    
    async def _get_stock_list_cached(self):
        """获取缓存的股票列表（避免重复获取）"""
        from datetime import datetime, timedelta

        # 如果缓存存在且未过期（1小时），直接返回
        if self._stock_list_cache is not None and self._cache_time is not None:
            if datetime.now() - self._cache_time < timedelta(hours=1):
                return self._stock_list_cache

        # 否则重新获取
        def fetch_stock_list():
            return self.ak.stock_info_a_code_name()

        try:
            stock_list = await asyncio.to_thread(fetch_stock_list)
            if stock_list is not None and not stock_list.empty:
                self._stock_list_cache = stock_list
                self._cache_time = datetime.now()
                logger.info(f"✅ 股票列表缓存更新: {len(stock_list)} 只股票")
                return stock_list
        except Exception as e:
            logger.error(f"❌ 获取股票列表失败: {e}")

        return None

    async def _get_stock_info_detail(self, code: str) -> Dict[str, Any]:
        """获取股票详细信息"""
        try:
            # 方法1: 尝试获取个股详细信息（包含行业、地区等详细信息）
            def fetch_individual_info():
                return self.ak.stock_individual_info_em(symbol=code)

            try:
                stock_info = await asyncio.to_thread(fetch_individual_info)

                if stock_info is not None and not stock_info.empty:
                    # 解析信息
                    info = {"code": code}

                    # 提取股票名称
                    name_row = stock_info[stock_info['item'] == '股票简称']
                    if not name_row.empty:
                        info['name'] = str(name_row['value'].iloc[0])

                    # 提取行业信息
                    industry_row = stock_info[stock_info['item'] == '所属行业']
                    if not industry_row.empty:
                        info['industry'] = str(industry_row['value'].iloc[0])

                    # 提取地区信息
                    area_row = stock_info[stock_info['item'] == '所属地区']
                    if not area_row.empty:
                        info['area'] = str(area_row['value'].iloc[0])

                    # 提取上市日期
                    list_date_row = stock_info[stock_info['item'] == '上市时间']
                    if not list_date_row.empty:
                        info['list_date'] = str(list_date_row['value'].iloc[0])

                    return info
            except Exception as e:
                logger.debug(f"获取{code}个股详细信息失败: {e}")

            # 方法2: 从缓存的股票列表中获取基本信息（只有代码和名称）
            try:
                stock_list = await self._get_stock_list_cached()
                if stock_list is not None and not stock_list.empty:
                    stock_row = stock_list[stock_list['code'] == code]
                    if not stock_row.empty:
                        return {
                            "code": code,
                            "name": str(stock_row['name'].iloc[0]),
                            "industry": "未知",
                            "area": "未知"
                        }
            except Exception as e:
                logger.debug(f"从股票列表获取{code}信息失败: {e}")

            # 如果都失败，返回基本信息
            return {"code": code, "name": f"股票{code}", "industry": "未知", "area": "未知"}

        except Exception as e:
            logger.debug(f"获取{code}详细信息失败: {e}")
            return {"code": code, "name": f"股票{code}", "industry": "未知", "area": "未知"}
    
    def _determine_market(self, code: str) -> str:
        """根据股票代码判断市场"""
        if code.startswith(('60', '68')):
            return "上海证券交易所"
        elif code.startswith(('00', '30')):
            return "深圳证券交易所"
        elif code.startswith('8'):
            return "北京证券交易所"
        else:
            return "未知市场"
    
    def _get_full_symbol(self, code: str) -> str:
        """
        获取完整股票代码

        Args:
            code: 6位股票代码

        Returns:
            完整标准化代码，如果无法识别则返回原始代码（确保不为空）
        """
        # 确保 code 不为空
        if not code:
            return ""

        # 标准化为字符串
        code = str(code).strip()

        # 根据代码前缀判断交易所
        if code.startswith(('60', '68', '90')):  # 上海证券交易所（增加90开头的B股）
            return f"{code}.SS"
        elif code.startswith(('00', '30', '20')):  # 深圳证券交易所（增加20开头的B股）
            return f"{code}.SZ"
        elif code.startswith(('8', '4')):  # 北京证券交易所（增加4开头的新三板）
            return f"{code}.BJ"
        else:
            # 无法识别的代码，返回原始代码（确保不为空）
            return code if code else ""
    
    def _get_market_info(self, code: str) -> Dict[str, Any]:
        """获取市场信息"""
        if code.startswith(('60', '68')):
            return {
                "market_type": "CN",
                "exchange": "SSE",
                "exchange_name": "上海证券交易所",
                "currency": "CNY",
                "timezone": "Asia/Shanghai"
            }
        elif code.startswith(('00', '30')):
            return {
                "market_type": "CN",
                "exchange": "SZSE", 
                "exchange_name": "深圳证券交易所",
                "currency": "CNY",
                "timezone": "Asia/Shanghai"
            }
        elif code.startswith('8'):
            return {
                "market_type": "CN",
                "exchange": "BSE",
                "exchange_name": "北京证券交易所", 
                "currency": "CNY",
                "timezone": "Asia/Shanghai"
            }
        else:
            return {
                "market_type": "CN",
                "exchange": "UNKNOWN",
                "exchange_name": "未知交易所",
                "currency": "CNY",
                "timezone": "Asia/Shanghai"
            }
    
    async def get_batch_stock_quotes(self, codes: List[str]) -> Dict[str, Dict[str, Any]]:
        """
        批量获取股票实时行情（优化版：一次获取全市场快照）

        优先使用新浪财经接口（更稳定），失败时回退到东方财富接口

        Args:
            codes: 股票代码列表

        Returns:
            股票代码到行情数据的映射字典
        """
        if not self.connected:
            return {}

        # 重试逻辑
        max_retries = 2
        retry_delay = 1  # 秒

        for attempt in range(max_retries):
            try:
                logger.debug(f"📊 批量获取 {len(codes)} 只股票的实时行情... (尝试 {attempt + 1}/{max_retries})")

                # 优先使用新浪财经接口（更稳定，不容易被封）
                def fetch_spot_data_sina():
                    import time
                    time.sleep(0.3)  # 添加延迟避免频率限制
                    return self.ak.stock_zh_a_spot()

                try:
                    spot_df = await asyncio.to_thread(fetch_spot_data_sina)
                    data_source = "sina"
                    logger.debug("✅ 使用新浪财经接口获取数据")
                except Exception as e:
                    logger.warning(f"⚠️ 新浪财经接口失败: {e}，尝试东方财富接口...")
                    # 回退到东方财富接口
                    def fetch_spot_data_em():
                        import time
                        time.sleep(0.5)
                        return self.ak.stock_zh_a_spot_em()
                    spot_df = await asyncio.to_thread(fetch_spot_data_em)
                    data_source = "eastmoney"
                    logger.debug("✅ 使用东方财富接口获取数据")

                if spot_df is None or spot_df.empty:
                    logger.warning("⚠️ 全市场快照为空")
                    if attempt < max_retries - 1:
                        await asyncio.sleep(retry_delay)
                        continue
                    return {}

                # 构建代码到行情的映射
                quotes_map = {}
                codes_set = set(codes)

                # 构建代码映射表（支持带前缀的代码匹配）
                # 例如：sh600000 -> 600000, sz000001 -> 000001
                code_mapping = {}
                for code in codes:
                    code_mapping[code] = code  # 原始代码
                    # 添加可能的前缀变体
                    for prefix in ['sh', 'sz', 'bj']:
                        code_mapping[f"{prefix}{code}"] = code

                for _, row in spot_df.iterrows():
                    raw_code = str(row.get("代码", ""))

                    # 尝试匹配代码（支持带前缀和不带前缀）
                    matched_code = None
                    if raw_code in code_mapping:
                        matched_code = code_mapping[raw_code]
                    elif raw_code in codes_set:
                        matched_code = raw_code

                    if matched_code:
                        quotes_data = {
                            "name": str(row.get("名称", f"股票{matched_code}")),
                            "price": self._safe_float(row.get("最新价", 0)),
                            "change": self._safe_float(row.get("涨跌额", 0)),
                            "change_percent": self._safe_float(row.get("涨跌幅", 0)),
                            "volume": self._safe_int(row.get("成交量", 0)),
                            "amount": self._safe_float(row.get("成交额", 0)),
                            "open": self._safe_float(row.get("今开", 0)),
                            "high": self._safe_float(row.get("最高", 0)),
                            "low": self._safe_float(row.get("最低", 0)),
                            "pre_close": self._safe_float(row.get("昨收", 0)),
                            # 🔥 新增：财务指标字段
                            "turnover_rate": self._safe_float(row.get("换手率", None)),  # 换手率（%）
                            "volume_ratio": self._safe_float(row.get("量比", None)),  # 量比
                            "pe": self._safe_float(row.get("市盈率-动态", None)),  # 动态市盈率
                            "pb": self._safe_float(row.get("市净率", None)),  # 市净率
                            "total_mv": self._safe_float(row.get("总市值", None)),  # 总市值（元）
                            "circ_mv": self._safe_float(row.get("流通市值", None)),  # 流通市值（元）
                        }

                        # 转换为标准化字典（使用匹配后的代码）
                        quotes_map[matched_code] = {
                            "code": matched_code,
                            "symbol": matched_code,
                            "name": quotes_data.get("name", f"股票{matched_code}"),
                            "price": float(quotes_data.get("price", 0)),
                            "change": float(quotes_data.get("change", 0)),
                            "change_percent": float(quotes_data.get("change_percent", 0)),
                            "volume": int(quotes_data.get("volume", 0)),
                            "amount": float(quotes_data.get("amount", 0)),
                            "open_price": float(quotes_data.get("open", 0)),
                            "high_price": float(quotes_data.get("high", 0)),
                            "low_price": float(quotes_data.get("low", 0)),
                            "pre_close": float(quotes_data.get("pre_close", 0)),
                            # 🔥 新增：财务指标字段
                            "turnover_rate": quotes_data.get("turnover_rate"),  # 换手率（%）
                            "volume_ratio": quotes_data.get("volume_ratio"),  # 量比
                            "pe": quotes_data.get("pe"),  # 动态市盈率
                            "pe_ttm": quotes_data.get("pe"),  # TTM市盈率（与动态市盈率相同）
                            "pb": quotes_data.get("pb"),  # 市净率
                            "total_mv": quotes_data.get("total_mv") / 1e8 if quotes_data.get("total_mv") else None,  # 总市值（转换为亿元）
                            "circ_mv": quotes_data.get("circ_mv") / 1e8 if quotes_data.get("circ_mv") else None,  # 流通市值（转换为亿元）
                            # 扩展字段
                            "full_symbol": self._get_full_symbol(matched_code),
                            "market_info": self._get_market_info(matched_code),
                            "data_source": "akshare",
                            "last_sync": datetime.now(timezone.utc),
                            "sync_status": "success"
                        }

                found_count = len(quotes_map)
                missing_count = len(codes) - found_count
                logger.debug(f"✅ 批量获取完成: 找到 {found_count} 只, 未找到 {missing_count} 只")

                # 记录未找到的股票
                if missing_count > 0:
                    missing_codes = codes_set - set(quotes_map.keys())
                    if missing_count <= 10:
                        logger.debug(f"⚠️ 未找到行情的股票: {list(missing_codes)}")
                    else:
                        logger.debug(f"⚠️ 未找到行情的股票: {list(missing_codes)[:10]}... (共{missing_count}只)")

                return quotes_map

            except Exception as e:
                logger.warning(f"⚠️ 批量获取实时行情失败 (尝试 {attempt + 1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(retry_delay)
                else:
                    logger.error(f"❌ 批量获取实时行情失败，已达最大重试次数: {e}")
                    return {}

    async def get_stock_quotes(self, code: str) -> Optional[Dict[str, Any]]:
        """
        获取单个股票实时行情

        🔥 策略：使用 stock_bid_ask_em 接口获取单个股票的实时行情报价
        - 优点：只获取单个股票数据，速度快，不浪费资源
        - 适用场景：手动同步单个股票

        Args:
            code: 股票代码

        Returns:
            标准化的行情数据
        """
        if not self.connected:
            return None

        try:
            logger.info(f"📈 使用 stock_bid_ask_em 接口获取 {code} 实时行情...")

            # 🔥 使用 stock_bid_ask_em 接口获取单个股票实时行情
            def fetch_bid_ask():
                return self.ak.stock_bid_ask_em(symbol=code)

            bid_ask_df = await asyncio.to_thread(fetch_bid_ask)

            # 🔥 打印原始返回数据
            logger.info(f"📊 stock_bid_ask_em 返回数据类型: {type(bid_ask_df)}")
            if bid_ask_df is not None:
                logger.info(f"📊 DataFrame shape: {bid_ask_df.shape}")
                logger.info(f"📊 DataFrame columns: {list(bid_ask_df.columns)}")
                logger.info(f"📊 DataFrame 完整数据:\n{bid_ask_df.to_string()}")

            if bid_ask_df is None or bid_ask_df.empty:
                logger.warning(f"⚠️ 未找到{code}的行情数据")
                return None

            # 将 DataFrame 转换为字典
            data_dict = dict(zip(bid_ask_df['item'], bid_ask_df['value']))
            logger.info(f"📊 转换后的字典: {data_dict}")

            # 转换为标准化字典
            # 🔥 注意：字段名必须与 app/routers/stocks.py 中的查询字段一致
            # 前端查询使用的是 high/low/open，不是 high_price/low_price/open_price

            # 🔥 获取当前日期（UTC+8）
            from datetime import datetime, timezone, timedelta
            cn_tz = timezone(timedelta(hours=8))
            now_cn = datetime.now(cn_tz)
            trade_date = now_cn.strftime("%Y-%m-%d")  # 格式：2025-11-05

            # 🔥 成交量单位转换：手 → 股（1手 = 100股）
            volume_in_lots = int(data_dict.get("总手", 0))  # 单位：手
            volume_in_shares = volume_in_lots * 100  # 单位：股

            quotes = {
                "code": code,
                "symbol": code,
                "name": f"股票{code}",  # stock_bid_ask_em 不返回股票名称
                "price": float(data_dict.get("最新", 0)),
                "close": float(data_dict.get("最新", 0)),  # 🔥 close 字段（与 price 相同）
                "current_price": float(data_dict.get("最新", 0)),  # 🔥 current_price 字段（兼容旧数据）
                "change": float(data_dict.get("涨跌", 0)),
                "change_percent": float(data_dict.get("涨幅", 0)),
                "pct_chg": float(data_dict.get("涨幅", 0)),  # 🔥 pct_chg 字段（兼容旧数据）
                "volume": volume_in_shares,  # 🔥 单位：股（已转换）
                "amount": float(data_dict.get("金额", 0)),  # 单位：元
                "open": float(data_dict.get("今开", 0)),  # 🔥 使用 open 而不是 open_price
                "high": float(data_dict.get("最高", 0)),  # 🔥 使用 high 而不是 high_price
                "low": float(data_dict.get("最低", 0)),  # 🔥 使用 low 而不是 low_price
                "pre_close": float(data_dict.get("昨收", 0)),
                # 🔥 新增：财务指标字段
                "turnover_rate": float(data_dict.get("换手", 0)),  # 换手率（%）
                "volume_ratio": float(data_dict.get("量比", 0)),  # 量比
                "pe": None,  # stock_bid_ask_em 不返回市盈率
                "pe_ttm": None,
                "pb": None,  # stock_bid_ask_em 不返回市净率
                "total_mv": None,  # stock_bid_ask_em 不返回总市值
                "circ_mv": None,  # stock_bid_ask_em 不返回流通市值
                # 🔥 新增：交易日期和更新时间
                "trade_date": trade_date,  # 交易日期（格式：2025-11-05）
                "updated_at": now_cn.isoformat(),  # 更新时间（ISO格式，带时区）
                # 扩展字段
                "full_symbol": self._get_full_symbol(code),
                "market_info": self._get_market_info(code),
                "data_source": "akshare",
                "last_sync": datetime.now(timezone.utc),
                "sync_status": "success"
            }

            logger.info(f"✅ {code} 实时行情获取成功: 最新价={quotes['price']}, 涨跌幅={quotes['change_percent']}%, 成交量={quotes['volume']}, 成交额={quotes['amount']}")
            return quotes

        except Exception as e:
            logger.error(f"❌ 获取{code}实时行情失败: {e}", exc_info=True)
            return None
    
    async def _get_realtime_quotes_data(self, code: str) -> Dict[str, Any]:
        """获取实时行情数据"""
        try:
            # 方法1: 获取A股实时行情
            def fetch_spot_data():
                return self.ak.stock_zh_a_spot_em()

            try:
                spot_df = await asyncio.to_thread(fetch_spot_data)

                if spot_df is not None and not spot_df.empty:
                    # 查找对应股票
                    stock_data = spot_df[spot_df['代码'] == code]

                    if not stock_data.empty:
                        row = stock_data.iloc[0]

                        # 解析行情数据
                        return {
                            "name": str(row.get("名称", f"股票{code}")),
                            "price": self._safe_float(row.get("最新价", 0)),
                            "change": self._safe_float(row.get("涨跌额", 0)),
                            "change_percent": self._safe_float(row.get("涨跌幅", 0)),
                            "volume": self._safe_int(row.get("成交量", 0)),
                            "amount": self._safe_float(row.get("成交额", 0)),
                            "open": self._safe_float(row.get("今开", 0)),
                            "high": self._safe_float(row.get("最高", 0)),
                            "low": self._safe_float(row.get("最低", 0)),
                            "pre_close": self._safe_float(row.get("昨收", 0)),
                            # 🔥 新增：财务指标字段
                            "turnover_rate": self._safe_float(row.get("换手率", None)),  # 换手率（%）
                            "volume_ratio": self._safe_float(row.get("量比", None)),  # 量比
                            "pe": self._safe_float(row.get("市盈率-动态", None)),  # 动态市盈率
                            "pb": self._safe_float(row.get("市净率", None)),  # 市净率
                            "total_mv": self._safe_float(row.get("总市值", None)),  # 总市值（元）
                            "circ_mv": self._safe_float(row.get("流通市值", None)),  # 流通市值（元）
                        }
            except Exception as e:
                logger.debug(f"获取{code}A股实时行情失败: {e}")

            # 方法2: 尝试获取单只股票实时数据
            def fetch_individual_spot():
                return self.ak.stock_zh_a_hist(symbol=code, period="daily", adjust="")

            try:
                hist_df = await asyncio.to_thread(fetch_individual_spot)
                if hist_df is not None and not hist_df.empty:
                    # 取最新一天的数据作为当前行情
                    latest_row = hist_df.iloc[-1]
                    return {
                        "name": f"股票{code}",
                        "price": self._safe_float(latest_row.get("收盘", 0)),
                        "change": 0,  # 历史数据无法计算涨跌额
                        "change_percent": self._safe_float(latest_row.get("涨跌幅", 0)),
                        "volume": self._safe_int(latest_row.get("成交量", 0)),
                        "amount": self._safe_float(latest_row.get("成交额", 0)),
                        "open": self._safe_float(latest_row.get("开盘", 0)),
                        "high": self._safe_float(latest_row.get("最高", 0)),
                        "low": self._safe_float(latest_row.get("最低", 0)),
                        "pre_close": self._safe_float(latest_row.get("收盘", 0))
                    }
            except Exception as e:
                logger.debug(f"获取{code}历史数据作为行情失败: {e}")

            return {}

        except Exception as e:
            logger.debug(f"获取{code}实时行情数据失败: {e}")
            return {}
    
    def _safe_float(self, value: Any) -> float:
        """安全转换为浮点数"""
        try:
            if pd.isna(value) or value is None:
                return 0.0
            return float(value)
        except (ValueError, TypeError):
            return 0.0
    
    def _safe_int(self, value: Any) -> int:
        """安全转换为整数"""
        try:
            if pd.isna(value) or value is None:
                return 0
            return int(float(value))
        except (ValueError, TypeError):
            return 0
    
    def _safe_str(self, value: Any) -> str:
        """安全转换为字符串"""
        try:
            if pd.isna(value) or value is None:
                return ""
            return str(value)
        except:
            return ""

    async def get_historical_data(
        self,
        code: str,
        start_date: str,
        end_date: str,
        period: str = "daily"
    ) -> Optional[pd.DataFrame]:
        """
        获取历史行情数据

        Args:
            code: 股票代码
            start_date: 开始日期 (YYYY-MM-DD)
            end_date: 结束日期 (YYYY-MM-DD)
            period: 周期 (daily, weekly, monthly)

        Returns:
            历史行情数据DataFrame
        """
        if not self.connected:
            return None

        try:
            logger.debug(f"📊 获取{code}历史数据: {start_date} 到 {end_date}")

            # 转换周期格式
            period_map = {
                "daily": "daily",
                "weekly": "weekly",
                "monthly": "monthly"
            }
            ak_period = period_map.get(period, "daily")

            # 格式化日期
            start_date_formatted = start_date.replace('-', '')
            end_date_formatted = end_date.replace('-', '')

            # 获取历史数据
            def fetch_historical_data():
                return self.ak.stock_zh_a_hist(
                    symbol=code,
                    period=ak_period,
                    start_date=start_date_formatted,
                    end_date=end_date_formatted,
                    adjust="qfq"  # 前复权
                )

            hist_df = await asyncio.to_thread(fetch_historical_data)

            if hist_df is None or hist_df.empty:
                logger.warning(f"⚠️ {code}历史数据为空")
                return None

            # 标准化列名
            hist_df = self._standardize_historical_columns(hist_df, code)

            logger.debug(f"✅ {code}历史数据获取成功: {len(hist_df)}条记录")
            return hist_df

        except Exception as e:
            logger.error(f"❌ 获取{code}历史数据失败: {e}")
            return None

    def _standardize_historical_columns(self, df: pd.DataFrame, code: str) -> pd.DataFrame:
        """标准化历史数据列名"""
        try:
            # 标准化列名映射
            column_mapping = {
                '日期': 'date',
                '开盘': 'open',
                '收盘': 'close',
                '最高': 'high',
                '最低': 'low',
                '成交量': 'volume',
                '成交额': 'amount',
                '振幅': 'amplitude',
                '涨跌幅': 'change_percent',
                '涨跌额': 'change',
                '换手率': 'turnover'
            }

            # 重命名列
            df = df.rename(columns=column_mapping)

            # 添加标准字段
            df['code'] = code
            df['full_symbol'] = self._get_full_symbol(code)

            # 确保日期格式
            if 'date' in df.columns:
                df['date'] = pd.to_datetime(df['date'])

            # 数据类型转换
            numeric_columns = ['open', 'close', 'high', 'low', 'volume', 'amount']
            for col in numeric_columns:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

            return df

        except Exception as e:
            logger.error(f"标准化{code}历史数据列名失败: {e}")
            return df

    async def get_financial_data(self, code: str) -> Dict[str, Any]:
        """
        获取财务数据

        Args:
            code: 股票代码

        Returns:
            财务数据字典
        """
        if not self.connected:
            return {}

        try:
            logger.debug(f"💰 获取{code}财务数据...")

            financial_data = {}

            # 1. 获取主要财务指标
            try:
                def fetch_financial_abstract():
                    return self.ak.stock_financial_abstract(symbol=code)

                main_indicators = await asyncio.to_thread(fetch_financial_abstract)
                if main_indicators is not None and not main_indicators.empty:
                    financial_data['main_indicators'] = main_indicators.to_dict('records')
                    logger.debug(f"✅ {code}主要财务指标获取成功")
            except Exception as e:
                logger.debug(f"获取{code}主要财务指标失败: {e}")

            # 2. 获取资产负债表
            try:
                def fetch_balance_sheet():
                    return self.ak.stock_balance_sheet_by_report_em(symbol=code)

                balance_sheet = await asyncio.to_thread(fetch_balance_sheet)
                if balance_sheet is not None and not balance_sheet.empty:
                    financial_data['balance_sheet'] = balance_sheet.to_dict('records')
                    logger.debug(f"✅ {code}资产负债表获取成功")
            except Exception as e:
                logger.debug(f"获取{code}资产负债表失败: {e}")

            # 3. 获取利润表
            try:
                def fetch_income_statement():
                    return self.ak.stock_profit_sheet_by_report_em(symbol=code)

                income_statement = await asyncio.to_thread(fetch_income_statement)
                if income_statement is not None and not income_statement.empty:
                    financial_data['income_statement'] = income_statement.to_dict('records')
                    logger.debug(f"✅ {code}利润表获取成功")
            except Exception as e:
                logger.debug(f"获取{code}利润表失败: {e}")

            # 4. 获取现金流量表
            try:
                def fetch_cash_flow():
                    return self.ak.stock_cash_flow_sheet_by_report_em(symbol=code)

                cash_flow = await asyncio.to_thread(fetch_cash_flow)
                if cash_flow is not None and not cash_flow.empty:
                    financial_data['cash_flow'] = cash_flow.to_dict('records')
                    logger.debug(f"✅ {code}现金流量表获取成功")
            except Exception as e:
                logger.debug(f"获取{code}现金流量表失败: {e}")

            if financial_data:
                logger.debug(f"✅ {code}财务数据获取完成: {len(financial_data)}个数据集")
            else:
                logger.warning(f"⚠️ {code}未获取到任何财务数据")

            return financial_data

        except Exception as e:
            logger.error(f"❌ 获取{code}财务数据失败: {e}")
            return {}

    async def get_market_status(self) -> Dict[str, Any]:
        """
        获取市场状态信息

        Returns:
            市场状态信息
        """
        try:
            # AKShare没有直接的市场状态API，返回基本信息
            now = datetime.now()

            # 简单的交易时间判断
            is_trading_time = (
                now.weekday() < 5 and  # 工作日
                ((9 <= now.hour < 12) or (13 <= now.hour < 15))  # 交易时间
            )

            return {
                "market_status": "open" if is_trading_time else "closed",
                "current_time": now.isoformat(),
                "data_source": "akshare",
                "trading_day": now.weekday() < 5
            }

        except Exception as e:
            logger.error(f"❌ 获取市场状态失败: {e}")
            return {
                "market_status": "unknown",
                "current_time": datetime.now().isoformat(),
                "data_source": "akshare",
                "error": str(e)
            }

    def get_stock_news_sync(self, symbol: str = None, limit: int = 10) -> Optional[pd.DataFrame]:
        """
        获取股票新闻（同步版本，返回原始 DataFrame）

        Args:
            symbol: 股票代码，为None时获取市场新闻
            limit: 返回数量限制

        Returns:
            新闻 DataFrame 或 None
        """
        if not self.is_available():
            return None

        try:
            import akshare as ak
            import json
            import time

            if symbol:
                # 获取个股新闻
                self.logger.debug(f"📰 获取AKShare个股新闻: {symbol}")

                # 标准化股票代码
                symbol_6 = symbol.zfill(6)

                # 获取东方财富个股新闻，添加重试机制
                max_retries = 3
                retry_delay = 1  # 秒
                news_df = None

                for attempt in range(max_retries):
                    try:
                        news_df = ak.stock_news_em(symbol=symbol_6)
                        break  # 成功则跳出重试循环
                    except json.JSONDecodeError as e:
                        if attempt < max_retries - 1:
                            self.logger.warning(f"⚠️ {symbol} 第{attempt+1}次获取新闻失败(JSON解析错误)，{retry_delay}秒后重试...")
                            time.sleep(retry_delay)
                            retry_delay *= 2  # 指数退避
                        else:
                            self.logger.error(f"❌ {symbol} 获取新闻失败(JSON解析错误): {e}")
                            return None
                    except Exception as e:
                        if attempt < max_retries - 1:
                            self.logger.warning(f"⚠️ {symbol} 第{attempt+1}次获取新闻失败: {e}，{retry_delay}秒后重试...")
                            time.sleep(retry_delay)
                            retry_delay *= 2
                        else:
                            raise

                if news_df is not None and not news_df.empty:
                    self.logger.info(f"✅ {symbol} AKShare新闻获取成功: {len(news_df)} 条")
                    return news_df.head(limit) if limit else news_df
                else:
                    self.logger.warning(f"⚠️ {symbol} 未获取到AKShare新闻数据")
                    return None
            else:
                # 获取市场新闻
                self.logger.debug("📰 获取AKShare市场新闻")
                news_df = ak.news_cctv()

                if news_df is not None and not news_df.empty:
                    self.logger.info(f"✅ AKShare市场新闻获取成功: {len(news_df)} 条")
                    return news_df.head(limit) if limit else news_df
                else:
                    self.logger.warning("⚠️ 未获取到AKShare市场新闻数据")
                    return None

        except Exception as e:
            self.logger.error(f"❌ AKShare新闻获取失败: {e}")
            return None

    async def get_stock_news(self, symbol: str = None, limit: int = 10) -> Optional[List[Dict[str, Any]]]:
        """
        获取股票新闻（异步版本，返回结构化列表）

        Args:
            symbol: 股票代码，为None时获取市场新闻
            limit: 返回数量限制

        Returns:
            新闻列表
        """
        if not self.is_available():
            return None

        try:
            import akshare as ak
            import json
            import os

            if symbol:
                # 获取个股新闻
                self.logger.debug(f"📰 获取AKShare个股新闻: {symbol}")

                # 标准化股票代码
                symbol_6 = symbol.zfill(6)

                # 检测是否在 Docker 环境中
                is_docker = os.path.exists('/.dockerenv') or os.environ.get('DOCKER_CONTAINER') == 'true'

                # 获取东方财富个股新闻，添加重试机制
                max_retries = 3
                retry_delay = 1  # 秒
                news_df = None

                # 如果在 Docker 环境中，尝试使用 curl_cffi 直接调用 API
                if is_docker:
                    try:
                        from curl_cffi import requests as curl_requests
                        self.logger.debug(f"🐳 检测到 Docker 环境，使用 curl_cffi 直接调用 API")
                        news_df = await asyncio.to_thread(
                            self._get_stock_news_direct,
                            symbol=symbol_6,
                            limit=limit
                        )
                        if news_df is not None and not news_df.empty:
                            self.logger.info(f"✅ {symbol} Docker 环境直接调用 API 成功")
                        else:
                            self.logger.warning(f"⚠️ {symbol} Docker 环境直接调用 API 失败，回退到 AKShare")
                            news_df = None  # 回退到 AKShare
                    except ImportError:
                        self.logger.warning(f"⚠️ curl_cffi 未安装，回退到 AKShare")
                        news_df = None
                    except Exception as e:
                        self.logger.warning(f"⚠️ {symbol} Docker 环境直接调用 API 异常: {e}，回退到 AKShare")
                        news_df = None

                # 如果直接调用失败或不在 Docker 环境，使用 AKShare
                if news_df is None:
                    for attempt in range(max_retries):
                        try:
                            news_df = await asyncio.to_thread(
                                ak.stock_news_em,
                                symbol=symbol_6
                            )
                            break  # 成功则跳出重试循环
                        except json.JSONDecodeError as e:
                            if attempt < max_retries - 1:
                                self.logger.warning(f"⚠️ {symbol} 第{attempt+1}次获取新闻失败(JSON解析错误)，{retry_delay}秒后重试...")
                                await asyncio.sleep(retry_delay)
                                retry_delay *= 2  # 指数退避
                            else:
                                self.logger.error(f"❌ {symbol} 获取新闻失败(JSON解析错误): {e}")
                                return []
                        except KeyError as e:
                            # 东方财富网接口变更或反爬虫拦截，返回的字段结构改变
                            if str(e) == "'cmsArticleWebOld'":
                                self.logger.error(f"❌ {symbol} AKShare新闻接口返回数据结构异常: 缺少 'cmsArticleWebOld' 字段")
                                self.logger.error(f"   这通常是因为：1) 反爬虫拦截 2) 接口变更 3) 网络问题")
                                self.logger.error(f"   建议：检查 AKShare 版本是否为最新 (当前要求 >=1.17.86)")
                                # 返回空列表，避免程序崩溃
                                return []
                            else:
                                if attempt < max_retries - 1:
                                    self.logger.warning(f"⚠️ {symbol} 第{attempt+1}次获取新闻失败(字段错误): {e}，{retry_delay}秒后重试...")
                                    await asyncio.sleep(retry_delay)
                                    retry_delay *= 2
                                else:
                                    self.logger.error(f"❌ {symbol} 获取新闻失败(字段错误): {e}")
                                    return []
                        except Exception as e:
                            if attempt < max_retries - 1:
                                self.logger.warning(f"⚠️ {symbol} 第{attempt+1}次获取新闻失败: {e}，{retry_delay}秒后重试...")
                                await asyncio.sleep(retry_delay)
                                retry_delay *= 2
                            else:
                                raise

                if news_df is not None and not news_df.empty:
                    news_list = []

                    for _, row in news_df.head(limit).iterrows():
                        title = str(row.get('新闻标题', '') or row.get('标题', ''))
                        content = str(row.get('新闻内容', '') or row.get('内容', ''))
                        summary = str(row.get('新闻摘要', '') or row.get('摘要', ''))

                        news_item = {
                            "symbol": symbol,
                            "title": title,
                            "content": content,
                            "summary": summary,
                            "url": str(row.get('新闻链接', '') or row.get('链接', '')),
                            "source": str(row.get('文章来源', '') or row.get('来源', '') or '东方财富'),
                            "author": str(row.get('作者', '') or ''),
                            "publish_time": self._parse_news_time(row.get('发布时间', '') or row.get('时间', '')),
                            "category": self._classify_news(content, title),
                            "sentiment": self._analyze_news_sentiment(content, title),
                            "sentiment_score": self._calculate_sentiment_score(content, title),
                            "keywords": self._extract_keywords(content, title),
                            "importance": self._assess_news_importance(content, title),
                            "data_source": "akshare"
                        }

                        # 过滤空标题的新闻
                        if news_item["title"]:
                            news_list.append(news_item)

                    self.logger.info(f"✅ {symbol} AKShare新闻获取成功: {len(news_list)} 条")
                    return news_list
                else:
                    self.logger.warning(f"⚠️ {symbol} 未获取到AKShare新闻数据")
                    return []
            else:
                # 获取市场新闻
                self.logger.debug("📰 获取AKShare市场新闻")

                try:
                    # 获取财经新闻
                    news_df = await asyncio.to_thread(
                        ak.news_cctv,
                        limit=limit
                    )

                    if news_df is not None and not news_df.empty:
                        news_list = []

                        for _, row in news_df.iterrows():
                            title = str(row.get('title', '') or row.get('标题', ''))
                            content = str(row.get('content', '') or row.get('内容', ''))
                            summary = str(row.get('brief', '') or row.get('摘要', ''))

                            news_item = {
                                "title": title,
                                "content": content,
                                "summary": summary,
                                "url": str(row.get('url', '') or row.get('链接', '')),
                                "source": str(row.get('source', '') or row.get('来源', '') or 'CCTV财经'),
                                "author": str(row.get('author', '') or ''),
                                "publish_time": self._parse_news_time(row.get('time', '') or row.get('时间', '')),
                                "category": self._classify_news(content, title),
                                "sentiment": self._analyze_news_sentiment(content, title),
                                "sentiment_score": self._calculate_sentiment_score(content, title),
                                "keywords": self._extract_keywords(content, title),
                                "importance": self._assess_news_importance(content, title),
                                "data_source": "akshare"
                            }

                            if news_item["title"]:
                                news_list.append(news_item)

                        self.logger.info(f"✅ AKShare市场新闻获取成功: {len(news_list)} 条")
                        return news_list

                except Exception as e:
                    self.logger.debug(f"CCTV新闻获取失败: {e}")

                return []

        except Exception as e:
            self.logger.error(f"❌ 获取AKShare新闻失败 symbol={symbol}: {e}")
            return None

    def _parse_news_time(self, time_str: str) -> Optional[datetime]:
        """解析新闻时间"""
        if not time_str:
            return datetime.utcnow()

        try:
            # 尝试多种时间格式
            formats = [
                "%Y-%m-%d %H:%M:%S",
                "%Y-%m-%d %H:%M",
                "%Y-%m-%d",
                "%Y/%m/%d %H:%M:%S",
                "%Y/%m/%d %H:%M",
                "%Y/%m/%d",
                "%m-%d %H:%M",
                "%m/%d %H:%M"
            ]

            for fmt in formats:
                try:
                    parsed_time = datetime.strptime(str(time_str), fmt)

                    # 如果只有月日，补充年份
                    if fmt in ["%m-%d %H:%M", "%m/%d %H:%M"]:
                        current_year = datetime.now().year
                        parsed_time = parsed_time.replace(year=current_year)

                    return parsed_time
                except ValueError:
                    continue

            # 如果都失败了，返回当前时间
            self.logger.debug(f"⚠️ 无法解析新闻时间: {time_str}")
            return datetime.utcnow()

        except Exception as e:
            self.logger.debug(f"解析新闻时间异常: {e}")
            return datetime.utcnow()

    def _analyze_news_sentiment(self, content: str, title: str) -> str:
        """
        分析新闻情绪

        Args:
            content: 新闻内容
            title: 新闻标题

        Returns:
            情绪类型: positive/negative/neutral
        """
        text = f"{title} {content}".lower()

        # 积极关键词
        positive_keywords = [
            '利好', '上涨', '增长', '盈利', '突破', '创新高', '买入', '推荐',
            '看好', '乐观', '强势', '大涨', '飙升', '暴涨', '涨停', '涨幅',
            '业绩增长', '营收增长', '净利润增长', '扭亏为盈', '超预期',
            '获批', '中标', '签约', '合作', '并购', '重组', '分红', '回购'
        ]

        # 消极关键词
        negative_keywords = [
            '利空', '下跌', '亏损', '风险', '暴跌', '卖出', '警告', '下调',
            '看空', '悲观', '弱势', '大跌', '跳水', '暴跌', '跌停', '跌幅',
            '业绩下滑', '营收下降', '净利润下降', '亏损', '低于预期',
            '被查', '违规', '处罚', '诉讼', '退市', '停牌', '商誉减值'
        ]

        positive_count = sum(1 for keyword in positive_keywords if keyword in text)
        negative_count = sum(1 for keyword in negative_keywords if keyword in text)

        if positive_count > negative_count:
            return 'positive'
        elif negative_count > positive_count:
            return 'negative'
        else:
            return 'neutral'

    def _calculate_sentiment_score(self, content: str, title: str) -> float:
        """
        计算情绪分数

        Args:
            content: 新闻内容
            title: 新闻标题

        Returns:
            情绪分数: -1.0 到 1.0
        """
        text = f"{title} {content}".lower()

        # 积极关键词权重
        positive_keywords = {
            '涨停': 1.0, '暴涨': 0.9, '大涨': 0.8, '飙升': 0.8,
            '创新高': 0.7, '突破': 0.6, '上涨': 0.5, '增长': 0.4,
            '利好': 0.6, '看好': 0.5, '推荐': 0.5, '买入': 0.6
        }

        # 消极关键词权重
        negative_keywords = {
            '跌停': -1.0, '暴跌': -0.9, '大跌': -0.8, '跳水': -0.8,
            '创新低': -0.7, '破位': -0.6, '下跌': -0.5, '下滑': -0.4,
            '利空': -0.6, '看空': -0.5, '卖出': -0.6, '警告': -0.5
        }

        score = 0.0

        # 计算积极分数
        for keyword, weight in positive_keywords.items():
            if keyword in text:
                score += weight

        # 计算消极分数
        for keyword, weight in negative_keywords.items():
            if keyword in text:
                score += weight

        # 归一化到 [-1.0, 1.0]
        return max(-1.0, min(1.0, score / 3.0))

    def _extract_keywords(self, content: str, title: str) -> List[str]:
        """
        提取关键词

        Args:
            content: 新闻内容
            title: 新闻标题

        Returns:
            关键词列表
        """
        text = f"{title} {content}"

        # 常见财经关键词
        common_keywords = [
            '股票', '公司', '市场', '投资', '业绩', '财报', '政策', '行业',
            '分析', '预测', '涨停', '跌停', '上涨', '下跌', '盈利', '亏损',
            '并购', '重组', '分红', '回购', '增持', '减持', '融资', 'IPO',
            '监管', '央行', '利率', '汇率', 'GDP', '通胀', '经济', '贸易',
            '科技', '互联网', '新能源', '医药', '房地产', '金融', '制造业'
        ]

        keywords = []
        for keyword in common_keywords:
            if keyword in text:
                keywords.append(keyword)

        return keywords[:10]  # 最多返回10个关键词

    def _assess_news_importance(self, content: str, title: str) -> str:
        """
        评估新闻重要性

        Args:
            content: 新闻内容
            title: 新闻标题

        Returns:
            重要性级别: high/medium/low
        """
        text = f"{title} {content}".lower()

        # 高重要性关键词
        high_importance_keywords = [
            '业绩', '财报', '年报', '季报', '重大', '公告', '监管', '政策',
            '并购', '重组', '退市', '停牌', '涨停', '跌停', '暴涨', '暴跌',
            '央行', '证监会', '交易所', '违规', '处罚', '立案', '调查'
        ]

        # 中等重要性关键词
        medium_importance_keywords = [
            '分析', '预测', '观点', '建议', '行业', '市场', '趋势', '机会',
            '研报', '评级', '目标价', '增持', '减持', '买入', '卖出',
            '合作', '签约', '中标', '获批', '分红', '回购'
        ]

        # 检查高重要性
        if any(keyword in text for keyword in high_importance_keywords):
            return 'high'

        # 检查中等重要性
        if any(keyword in text for keyword in medium_importance_keywords):
            return 'medium'

        return 'low'

    def _classify_news(self, content: str, title: str) -> str:
        """
        分类新闻

        Args:
            content: 新闻内容
            title: 新闻标题

        Returns:
            新闻类别
        """
        text = f"{title} {content}".lower()

        # 公司公告
        if any(keyword in text for keyword in ['公告', '业绩', '财报', '年报', '季报']):
            return 'company_announcement'

        # 政策新闻
        if any(keyword in text for keyword in ['政策', '监管', '央行', '证监会', '国务院']):
            return 'policy_news'

        # 行业新闻
        if any(keyword in text for keyword in ['行业', '板块', '产业', '领域']):
            return 'industry_news'

        # 市场新闻
        if any(keyword in text for keyword in ['市场', '指数', '大盘', '沪指', '深成指']):
            return 'market_news'

        # 研究报告
        if any(keyword in text for keyword in ['研报', '分析', '评级', '目标价', '机构']):
            return 'research_report'

        return 'general'


# 全局提供器实例
_akshare_provider = None


def get_akshare_provider() -> AKShareProvider:
    """获取全局AKShare提供器实例"""
    global _akshare_provider
    if _akshare_provider is None:
        _akshare_provider = AKShareProvider()
    return _akshare_provider
