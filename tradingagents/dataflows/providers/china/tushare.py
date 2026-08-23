"""
统一的Tushare数据提供器
合并app层和tradingagents层的所有优势功能
"""
import os
# 🔧 避免 Tushare 写用户主目录 tk.csv 导致权限错误
os.environ['TS_CACHE_DIR'] = os.path.join(os.path.dirname(__file__), '..', '..', '..', '..', 'data', 'tushare_cache')
os.environ['TS_DATA_DIR'] = os.environ['TS_CACHE_DIR']
os.environ['TEMP'] = os.environ['TS_CACHE_DIR']

from typing import Optional, Dict, Any, List, Union
from datetime import datetime, date, timedelta
import pandas as pd
import asyncio
import logging

from ..base_provider import BaseStockDataProvider
from tradingagents.config.providers_config import get_provider_config

# 尝试导入tushare
try:
    import tushare as ts
    TUSHARE_AVAILABLE = True
    # monkey patch upass 避免写 tk.csv
    try:
        from tushare import upass
        _orig_set_token = upass.set_token
        _orig_get_token = upass.get_token
        def _patched_set_token(token):
            os.environ['TUSHARE_TOKEN'] = token
        def _patched_get_token():
            return os.environ.get('TUSHARE_TOKEN', '')
        upass.set_token = _patched_set_token
        upass.get_token = _patched_get_token
    except Exception:
        pass
except ImportError:
    TUSHARE_AVAILABLE = False
    ts = None

logger = logging.getLogger(__name__)


class TushareProvider(BaseStockDataProvider):
    """
    统一的Tushare数据提供器
    合并app层和tradingagents层的所有优势功能
    """
    
    def __init__(self):
        super().__init__("Tushare")
        self.api = None
        self.config = get_provider_config("tushare")
        self.token_source = None  # 记录 Token 来源: 'database' 或 'env'
        self._event_loop_closed = False  # 🔥 标记事件循环是否已关闭

        if not TUSHARE_AVAILABLE:
            self.logger.error("❌ Tushare库未安装，请运行: pip install tushare")

    def is_event_loop_closed(self) -> bool:
        """
        检查事件循环是否已关闭

        Returns:
            True 如果事件循环已关闭，False 否则
        """
        return self._event_loop_closed

    def _get_token_from_database(self) -> Optional[str]:
        """
        从数据库读取 Tushare Token

        优先级：数据库配置 > 环境变量
        这样用户在 Web 后台修改配置后可以立即生效
        """
        try:
            self.logger.info("🔍 [DB查询] 开始从数据库读取 Token...")
            from app.core.database import get_mongo_db_sync
            db = get_mongo_db_sync()
            config_collection = db.system_configs

            # 获取最新的激活配置
            self.logger.info("🔍 [DB查询] 查询 is_active=True 的配置...")
            config_data = config_collection.find_one(
                {"is_active": True},
                sort=[("version", -1)]
            )

            if config_data:
                self.logger.info(f"✅ [DB查询] 找到激活配置，版本: {config_data.get('version')}")
                if config_data.get('data_source_configs'):
                    self.logger.info(f"✅ [DB查询] 配置中有 {len(config_data['data_source_configs'])} 个数据源")
                    for ds_config in config_data['data_source_configs']:
                        ds_type = ds_config.get('type')
                        self.logger.info(f"🔍 [DB查询] 检查数据源: {ds_type}")
                        if ds_type == 'tushare':
                            api_key = ds_config.get('api_key')
                            self.logger.info(f"✅ [DB查询] 找到 Tushare 配置，api_key 长度: {len(api_key) if api_key else 0}")
                            if api_key and not api_key.startswith("your_"):
                                self.logger.info(f"✅ [DB查询] Token 有效 (长度: {len(api_key)})")
                                return api_key
                            else:
                                self.logger.warning(f"⚠️ [DB查询] Token 无效或为占位符")
                else:
                    self.logger.warning("⚠️ [DB查询] 配置中没有 data_source_configs")
            else:
                self.logger.warning("⚠️ [DB查询] 未找到激活的配置")

            self.logger.info("⚠️ [DB查询] 数据库中未找到有效的 Tushare Token")
        except Exception as e:
            self.logger.error(f"❌ [DB查询] 从数据库读取 Token 失败: {e}")
            import traceback
            self.logger.error(f"❌ [DB查询] 堆栈跟踪:\n{traceback.format_exc()}")

        return None

    def _ensure_api_client(self, validate: bool = False) -> bool:
        """确保 Tushare API Client 已初始化。Tushare 是 HTTP API，不维护长连接。

        🔥 每次调用都会从数据库读取最新 Token（优先级：数据库 > 环境变量）；
        若与当前 API Client 使用的 Token 不一致，则自动重新初始化，
        保证用户在 Web 后台修改 Token 后立即生效，无需重启后端。
        """
        if not TUSHARE_AVAILABLE:
            self.logger.error("❌ Tushare库不可用")
            self.api = None
            self.connected = False
            return False

        try:
            # 🔥 每次调用重新读取 Token，避免缓存旧 Token
            db_token = self._get_token_from_database()
            env_token = self.config.get('token') or os.getenv("TUSHARE_TOKEN", "")
            token_candidates = []
            if db_token:
                token_candidates.append(("database", db_token.strip()))
            if env_token:
                token_candidates.append(("env", env_token.strip()))

            if not token_candidates:
                self.logger.error("❌ Tushare token未配置，请在 Web 后台或 .env 文件中配置 TUSHARE_TOKEN")
                self.api = None
                self.connected = False
                return False

            # 当前应使用的 Token（数据库优先）
            effective_token = token_candidates[0][1]

            # 🔥 Token 未变化且 API Client 已就绪：直接复用，避免不必要的重建
            if (
                self.api is not None
                and not validate
                and getattr(self, "_current_token", None) == effective_token
            ):
                self.connected = True
                return True

            # 🔥 Token 已变化：废弃旧 API Client，重新初始化
            if self.api is not None:
                self.logger.info("🔄 Tushare Token 已变更，重新初始化 API Client")

            for source, token in token_candidates:
                try:
                    self.logger.info(f"🔄 初始化 Tushare API Client (Token来源: {source})")
                    # 直接传入 token 给 pro_api，不调用 set_token 避免写 tk.csv 文件
                    # ts.set_token(token) 会把 token 缓存到 ~/tk.csv，在沙箱等受限环境会 Permission denied
                    api = ts.pro_api(token)

                    if validate:
                        test_data = api.stock_basic(list_status='L', limit=1)
                        if test_data is None or test_data.empty:
                            self.logger.warning(f"⚠️ Tushare Token 测试失败 (Token来源: {source})")
                            continue

                    self.api = api
                    self._current_token = token
                    self.connected = True
                    self.token_source = source
                    self.logger.info(f"✅ Tushare API Client 已就绪 (Token来源: {source})")
                    return True
                except Exception as e:
                    self.logger.warning(f"⚠️ 初始化 Tushare API Client 失败 (Token来源: {source}): {e}")
                    continue

            self.api = None
            self.connected = False
            return False

        except Exception as e:
            self.logger.error(f"❌ 初始化 Tushare API Client 失败: {e}")
            self.api = None
            self.connected = False
            return False

    def connect_sync(self) -> bool:
        """同步初始化 Tushare API Client（兼容旧接口）。"""
        return self._ensure_api_client(validate=True)

    async def connect(self) -> bool:
        """异步初始化 Tushare API Client（兼容旧接口）。"""
        return await asyncio.to_thread(self.connect_sync)
    
    def is_available(self) -> bool:
        """检查 Tushare API Client 是否可用。"""
        return self._ensure_api_client(validate=False)
    
    # ==================== 基础数据接口 ====================
    
    def get_stock_list_sync(self, market: str = None) -> Optional[pd.DataFrame]:
        """获取股票列表（同步版本），包含沪深+北交所"""
        if not self.is_available():
            return None

        try:
            df = self.api.stock_basic(
                list_status='L',
                exchange='SSE,SZSE,BSE',  # 沪深 + 北交所（不传则默认可能不含北交所）
                fields='ts_code,symbol,name,area,industry,market,exchange,list_date,is_hs'
            )
            if df is not None and not df.empty:
                self.logger.info(f"✅ 成功获取 {len(df)} 条股票数据")
                return df
            else:
                self.logger.warning("⚠️ Tushare API 返回空数据")
                return None
        except Exception as e:
            self.logger.error(f"❌ 获取股票列表失败: {e}")
            return None

    async def get_stock_list(self, market: str = None) -> Optional[List[Dict[str, Any]]]:
        """获取股票列表（异步版本）"""
        if not self.is_available():
            return None

        try:
            # 构建查询参数（默认包含沪深+北交所）
            params = {
                'list_status': 'L',  # 只获取上市股票
                'exchange': 'SSE,SZSE,BSE',  # 沪深 + 北交所
                'fields': 'ts_code,symbol,name,area,industry,market,exchange,list_date,is_hs'
            }
            
            if market:
                # 根据市场筛选
                if market == "CN":
                    params['exchange'] = 'SSE,SZSE,BSE'  # 沪深 + 北交所
                elif market == "HK":
                    return None  # Tushare港股需要单独处理
                elif market == "US":
                    return None  # Tushare不支持美股
            
            # 获取数据
            df = await asyncio.to_thread(self.api.stock_basic, **params)
            
            if df is None or df.empty:
                return None
            
            # 转换为标准格式
            stock_list = []
            for _, row in df.iterrows():
                stock_info = self.standardize_basic_info(row.to_dict())
                stock_list.append(stock_info)
            
            self.logger.info(f"✅ 获取股票列表: {len(stock_list)}只")
            return stock_list
            
        except Exception as e:
            self.logger.error(f"❌ 获取股票列表失败: {e}")
            return None
    
    async def get_stock_basic_info(self, symbol: str = None) -> Optional[Union[Dict[str, Any], List[Dict[str, Any]]]]:
        """获取股票基础信息"""
        if not self.is_available():
            return None
        
        try:
            if symbol:
                # 获取单个股票信息
                ts_code = self._normalize_ts_code(symbol)
                df = await asyncio.to_thread(
                    self.api.stock_basic,
                    ts_code=ts_code,
                    fields='ts_code,symbol,name,area,industry,market,exchange,list_date,is_hs,act_name,act_ent_type'
                )
                
                if df is None or df.empty:
                    return None
                
                return self.standardize_basic_info(df.iloc[0].to_dict())
            else:
                # 获取所有股票信息
                return await self.get_stock_list()
                
        except Exception as e:
            self.logger.error(f"❌ 获取股票基础信息失败 symbol={symbol}: {e}")
            return None
    
    async def get_stock_quotes(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        获取单只股票实时行情

        🔥 策略：使用 daily 接口获取最新一天的数据（不使用 rt_k 批量接口）
        - rt_k 接口是批量接口，单只股票调用浪费配额
        - daily 接口可以获取单只股票的最新日线数据，包含更多指标

        注意：此方法适合少量股票获取，大量股票建议使用 get_realtime_quotes_batch()
        """
        if not self.is_available():
            return None

        try:
            ts_code = self._normalize_ts_code(symbol)

            # 🔥 使用 daily 接口获取最新一天的数据（更节省配额）
            from datetime import datetime, timedelta

            # 获取最近3天的数据（考虑周末和节假日）
            end_date = datetime.now().strftime('%Y%m%d')
            start_date = (datetime.now() - timedelta(days=3)).strftime('%Y%m%d')

            df = await asyncio.to_thread(
                self.api.daily,
                ts_code=ts_code,
                start_date=start_date,
                end_date=end_date
            )

            if df is not None and not df.empty:
                # 取最新一天的数据
                row = df.iloc[0].to_dict()

                # 标准化字段
                quote_data = {
                    'ts_code': row.get('ts_code'),
                    'symbol': symbol,
                    'trade_date': row.get('trade_date'),
                    'open': row.get('open'),
                    'high': row.get('high'),
                    'low': row.get('low'),
                    'close': row.get('close'),  # 收盘价
                    'pre_close': row.get('pre_close'),
                    'change': row.get('change'),  # 涨跌额
                    'pct_chg': row.get('pct_chg'),  # 涨跌幅
                    'volume': row.get('vol'),  # 成交量（手）
                    'amount': row.get('amount'),  # 成交额（千元）
                }

                return self.standardize_quotes(quote_data)

            return None

        except Exception as e:
            # 检查是否为限流错误
            if self._is_rate_limit_error(str(e)):
                self.logger.error(f"❌ 获取实时行情失败（限流） symbol={symbol}: {e}")
                raise  # 抛出限流错误，让上层处理

            self.logger.error(f"❌ 获取实时行情失败 symbol={symbol}: {e}")
            return None

    async def get_realtime_quotes_batch(self) -> Optional[Dict[str, Dict[str, Any]]]:
        """
        批量获取全市场实时行情
        使用 rt_k 接口的通配符功能，一次性获取所有A股实时行情

        Returns:
            Dict[str, Dict]: {symbol: quote_data}
            例如: {'000001': {'close': 10.5, 'pct_chg': 1.2, ...}, ...}
        """
        if not self.is_available():
            return None

        try:
            # 使用通配符一次性获取全市场行情
            # 3*.SZ: 创业板  6*.SH: 上交所  0*.SZ: 深交所主板  4*.BJ,8*.BJ,9*.BJ: 北交所
            df = await asyncio.to_thread(
                self.api.rt_k,
                ts_code='3*.SZ,6*.SH,0*.SZ,4*.BJ,8*.BJ,9*.BJ'
            )

            if df is None or df.empty:
                self.logger.warning("⚠️ rt_k 接口返回空数据")
                return None

            self.logger.info(f"✅ 获取到 {len(df)} 只股票的实时行情")

            # 🔥 获取当前日期（UTC+8）
            from datetime import datetime, timezone, timedelta
            cn_tz = timezone(timedelta(hours=8))
            now_cn = datetime.now(cn_tz)
            trade_date = now_cn.strftime("%Y%m%d")  # 格式：20251114（与 Tushare 格式一致）

            # 转换为字典格式
            result = {}
            for _, row in df.iterrows():
                ts_code = row.get('ts_code')
                if not ts_code or '.' not in ts_code:
                    continue

                # 提取6位代码
                symbol = ts_code.split('.')[0]

                # 构建行情数据
                quote_data = {
                    'ts_code': ts_code,
                    'symbol': symbol,
                    'name': row.get('name'),
                    'open': row.get('open'),
                    'high': row.get('high'),
                    'low': row.get('low'),
                    'close': row.get('close'),  # 当前价
                    'pre_close': row.get('pre_close'),
                    'volume': row.get('vol'),  # 成交量（股）
                    'amount': row.get('amount'),  # 成交额（元）
                    'num': row.get('num'),  # 成交笔数
                    'trade_date': trade_date,  # 🔥 添加交易日期字段
                }

                # 计算涨跌幅
                if quote_data.get('close') and quote_data.get('pre_close'):
                    try:
                        close = float(quote_data['close'])
                        pre_close = float(quote_data['pre_close'])
                        if pre_close > 0:
                            pct_chg = ((close - pre_close) / pre_close) * 100
                            quote_data['pct_chg'] = round(pct_chg, 2)
                            quote_data['change'] = round(close - pre_close, 2)
                    except (ValueError, TypeError):
                        pass

                result[symbol] = quote_data

            return result

        except Exception as e:
            # 检查是否为限流错误
            if self._is_rate_limit_error(str(e)):
                self.logger.error(f"❌ 批量获取实时行情失败（限流）: {e}")
                raise  # 抛出限流错误，让上层处理

            self.logger.error(f"❌ 批量获取实时行情失败: {e}")
            return None

    def _is_rate_limit_error(self, error_msg: str) -> bool:
        """检测是否为 API 限流错误"""
        rate_limit_keywords = [
            "每分钟最多访问",
            "每分钟最多",
            "rate limit",
            "too many requests",
            "访问频率",
            "请求过于频繁"
        ]
        error_msg_lower = error_msg.lower()
        return any(keyword in error_msg_lower for keyword in rate_limit_keywords)
    
    async def get_historical_data(
        self,
        symbol: str,
        start_date: Union[str, date],
        end_date: Union[str, date] = None,
        period: str = "daily"
    ) -> Optional[pd.DataFrame]:
        """
        获取历史数据

        Args:
            symbol: 股票代码
            start_date: 开始日期
            end_date: 结束日期
            period: 数据周期 (daily/weekly/monthly)
        """
        if not self.is_available():
            availability_issues = []
            if not TUSHARE_AVAILABLE:
                availability_issues.append("Tushare库未安装")
            if self.api is None:
                availability_issues.append("Tushare API Client 未初始化")
            
            self.logger.warning(
                f"⚠️ [Tushare API调用] 无法调用 get_historical_data，Tushare API Client 不可用\n"
                f"   股票代码: {symbol}\n"
                f"   开始日期: {start_date}\n"
                f"   结束日期: {end_date}\n"
                f"   周期: {period}\n"
                f"   🔍 不可用原因: {', '.join(availability_issues) if availability_issues else '未知'}"
            )
            return None

        try:
            ts_code = self._normalize_ts_code(symbol)

            # 格式化日期
            start_str = self._format_date(start_date)
            end_str = self._format_date(end_date) if end_date else datetime.now().strftime('%Y%m%d')

            # 🔧 使用 pro_bar 接口获取前复权数据（与同花顺一致）
            # 注意：Tushare 的 daily/weekly/monthly 接口不支持复权
            # 必须使用 ts.pro_bar() 函数并指定 adj='qfq' 参数
            # ⚠️ ETF/基金（50/51/52/56/58/15/16 开头）pro_bar 不支持，需走 fund_daily 接口

            # 周期映射
            freq_map = {
                "daily": "D",
                "weekly": "W",
                "monthly": "M"
            }
            freq = freq_map.get(period, "D")

            is_etf = self._is_etf(ts_code)

            # ⏱️ 记录实际 API 调用时间（使用高精度计时）
            import time
            api_call_start = time.perf_counter()  # 使用 perf_counter 获得更高精度
            
            try:
                # 🔍 验证 API 对象是否有效
                if self.api is None:
                    self.logger.error("❌ [Tushare API调用] API 对象为 None，无法调用 Tushare 接口")
                    return None

                # 实际调用 Tushare API
                try:
                    if is_etf:
                        # ETF/基金走 fund_daily 接口（pro_bar 不支持 ETF）
                        self.logger.info(
                            f"📊 [Tushare API调用] 检测到ETF标的，使用 fund_daily 接口: {ts_code}"
                        )
                        df = await asyncio.to_thread(
                            self.api.fund_daily,
                            ts_code=ts_code,
                            start_date=start_str,
                            end_date=end_str,
                        )
                    else:
                        # 股票走 pro_bar 接口（支持复权）
                        df = await asyncio.to_thread(
                            ts.pro_bar,
                            ts_code=ts_code,
                            api=self.api,  # 传入 api 对象
                            start_date=start_str,
                            end_date=end_str,
                            freq=freq,
                            adj='qfq'  # 前复权（与同花顺一致）
                        )
                except RuntimeError as runtime_error:
                    # 🔥 捕获 "cannot schedule new futures after shutdown" 错误
                    if "shutdown" in str(runtime_error).lower():
                        self.logger.warning(f"⚠️ [Tushare API调用] 事件循环已关闭，停止获取数据: {symbol}")
                        self._event_loop_closed = True  # 🔥 设置标志
                        return None
                    raise  # 其他 RuntimeError 继续抛出
                api_call_duration = time.perf_counter() - api_call_start
                
                # 根据耗时判断是否真正执行了网络请求
                if api_call_duration < 0.01:  # 小于10毫秒，可能是快速失败
                    self.logger.warning(
                        f"⚠️ [Tushare API调用] ts.pro_bar() 执行完成（疑似快速失败）\n"
                        f"   耗时: {api_call_duration:.6f}秒（非常短，可能未执行网络请求）\n"
                        f"   返回类型: {type(df).__name__ if df is not None else 'None'}\n"
                        f"   返回数据: {'空DataFrame' if (df is not None and df.empty) else ('None' if df is None else f'{len(df)}行')}\n"
                        f"   💡 可能原因: Tushare 内部参数验证失败或快速失败逻辑"
                    )
                else:
                    self.logger.info(
                        f"✅ [Tushare API调用] ts.pro_bar() 执行完成\n"
                        f"   耗时: {api_call_duration:.6f}秒\n"
                        f"   返回类型: {type(df).__name__ if df is not None else 'None'}\n"
                        f"   返回数据: {'空DataFrame' if (df is not None and df.empty) else ('None' if df is None else f'{len(df)}行')}"
                    )
            except Exception as api_exception:
                api_call_duration = time.perf_counter() - api_call_start
                self.logger.error(
                    f"❌ [Tushare API调用] ts.pro_bar() 抛出异常\n"
                    f"   耗时: {api_call_duration:.6f}秒\n"
                    f"   异常类型: {type(api_exception).__name__}\n"
                    f"   异常信息: {str(api_exception)}\n"
                    f"   调用参数: ts_code={ts_code}, start_date={start_str}, end_date={end_str}, freq={freq}, adj=qfq"
                )
                raise  # 重新抛出异常，让上层处理

            if df is None or df.empty:
                self.logger.warning(
                    f"⚠️ Tushare API 返回空数据: symbol={symbol}, ts_code={ts_code}, "
                    f"period={period}, start={start_str}, end={end_str}"
                )
                self.logger.warning(
                    f"💡 可能原因: "
                    f"1) 该股票在此期间无交易数据 "
                    f"2) 日期范围不正确 "
                    f"3) 股票代码格式错误 "
                    f"4) Tushare API 限制或积分不足"
                )
                return None

            # 数据标准化
            df = self._standardize_historical_data(df)

            self.logger.info(f"✅ 获取{period}历史数据: {symbol} {len(df)}条记录 (前复权 qfq)")
            return df
            
        except Exception as e:
            import traceback
            error_details = traceback.format_exc()
            self.logger.error(
                f"❌ 获取历史数据失败 symbol={symbol}, period={period}\n"
                f"   参数: ts_code={ts_code if 'ts_code' in locals() else 'N/A'}, "
                f"start={start_str if 'start_str' in locals() else 'N/A'}, "
                f"end={end_str if 'end_str' in locals() else 'N/A'}\n"
                f"   错误类型: {type(e).__name__}\n"
                f"   错误信息: {str(e)}\n"
                f"   堆栈跟踪:\n{error_details}"
            )
            return None
    
    # ==================== 扩展接口 ====================
    
    async def get_daily_basic(self, trade_date: str) -> Optional[pd.DataFrame]:
        """获取每日基础财务数据"""
        if not self.is_available():
            return None
        
        try:
            date_str = trade_date.replace('-', '')
            df = await asyncio.to_thread(
                self.api.daily_basic,
                trade_date=date_str,
                fields='ts_code,total_mv,circ_mv,pe,pb,turnover_rate,volume_ratio,pe_ttm,pb_mrq'
            )
            
            if df is not None and not df.empty:
                self.logger.info(f"✅ 获取每日基础数据: {trade_date} {len(df)}条记录")
                return df
            
            return None
            
        except Exception as e:
            self.logger.error(f"❌ 获取每日基础数据失败 trade_date={trade_date}: {e}")
            return None

    async def get_valuation_history(
        self,
        code: str,
        start_date: str,
        end_date: str,
    ) -> Dict[str, Any]:
        """获取股票历史估值序列（PE_TTM、PB_MRQ、PS_TTM、PCF_TTM）。

        使用 Tushare daily_basic 的日期范围查询，一次调用获取全量数据。
        返回格式与 Baostock get_valuation_history 一致。
        """
        if not self.is_available():
            return {"source": "tushare", "data": []}

        try:
            ts_code = self._normalize_ts_code(code)
            start_str = start_date.replace('-', '')
            end_str = end_date.replace('-', '')
            df = await asyncio.to_thread(
                self.api.daily_basic,
                ts_code=ts_code,
                start_date=start_str,
                end_date=end_str,
                fields='ts_code,trade_date,close,pe_ttm,pb,ps_ttm,pcf_ncf_ttm',
            )
            if df is None or df.empty:
                self.logger.warning(f"⚠️ Tushare 估值历史为空: {code} {start_date}~{end_date}")
                return {"source": "tushare", "data": []}

            records: List[Dict[str, Any]] = []
            for _, row in df.iterrows():
                records.append({
                    "date": str(row.get("trade_date", "")),
                    "close": float(row["close"]) if pd.notna(row.get("close")) else None,
                    "pe_ttm": float(row["pe_ttm"]) if pd.notna(row.get("pe_ttm")) else None,
                    "pb_mrq": float(row["pb"]) if pd.notna(row.get("pb")) else None,
                    "ps_ttm": float(row["ps_ttm"]) if pd.notna(row.get("ps_ttm")) else None,
                    "pcf_ttm": float(row["pcf_ncf_ttm"]) if pd.notna(row.get("pcf_ncf_ttm")) else None,
                })
            self.logger.info(f"✅ Tushare 估值历史: {code} {start_date}~{end_date} → {len(records)}条")
            return {"source": "tushare", "data": records}
        except Exception as e:
            self.logger.error(f"❌ Tushare 估值历史失败 {code}: {e}")
            return {"source": "tushare", "data": []}
    
    async def find_latest_trade_date(self) -> Optional[str]:
        """查找最新交易日期"""
        if not self.is_available():
            return None
        
        try:
            today = datetime.now()
            for delta in range(0, 10):  # 最多回溯10天
                check_date = (today - timedelta(days=delta)).strftime('%Y%m%d')
                
                try:
                    df = await asyncio.to_thread(
                        self.api.daily_basic,
                        trade_date=check_date,
                        fields='ts_code',
                        limit=1
                    )
                    
                    if df is not None and not df.empty:
                        formatted_date = f"{check_date[:4]}-{check_date[4:6]}-{check_date[6:8]}"
                        self.logger.info(f"✅ 找到最新交易日期: {formatted_date}")
                        return formatted_date
                        
                except Exception:
                    continue
            
            return None
            
        except Exception as e:
            self.logger.error(f"❌ 查找最新交易日期失败: {e}")
            return None
    
    async def get_financial_data(self, symbol: str, report_type: str = "quarterly",
                                period: str = None, limit: Optional[int] = None) -> Optional[Dict[str, Any]]:
        """
        获取财务数据

        Args:
            symbol: 股票代码
            report_type: 报告类型 (quarterly/annual)
            period: 指定报告期 (YYYYMMDD格式)，为空则获取最新数据
            limit: 获取记录数量，None 表示拉取该股票可获取的全部报告期

        Returns:
            财务数据字典，包含利润表、资产负债表、现金流量表和财务指标
        """
        if not self.is_available():
            return None

        try:
            ts_code = self._normalize_ts_code(symbol)
            self.logger.debug(f"📊 获取Tushare财务数据: {ts_code}, 类型: {report_type}")

            # 构建查询参数
            query_params = {
                'ts_code': ts_code,
            }

            if limit is not None:
                query_params['limit'] = limit

            # 如果指定了报告期，添加期间参数
            if period:
                query_params['period'] = period

            financial_data = {}

            # 1. 获取利润表数据 (income statement)
            try:
                income_df = await asyncio.to_thread(
                    self.api.income,
                    **query_params
                )
                if income_df is not None and not income_df.empty:
                    financial_data['income_statement'] = income_df.to_dict('records')
                    self.logger.debug(f"✅ {ts_code} 利润表数据获取成功: {len(income_df)} 条记录")
                else:
                    self.logger.debug(f"⚠️ {ts_code} 利润表数据为空")
            except Exception as e:
                self.logger.warning(f"❌ 获取{ts_code}利润表数据失败: {e}")

            # 2. 获取资产负债表数据 (balance sheet)
            try:
                balance_df = await asyncio.to_thread(
                    self.api.balancesheet,
                    **query_params
                )
                if balance_df is not None and not balance_df.empty:
                    financial_data['balance_sheet'] = balance_df.to_dict('records')
                    self.logger.debug(f"✅ {ts_code} 资产负债表数据获取成功: {len(balance_df)} 条记录")
                else:
                    self.logger.debug(f"⚠️ {ts_code} 资产负债表数据为空")
            except Exception as e:
                self.logger.warning(f"❌ 获取{ts_code}资产负债表数据失败: {e}")

            # 3. 获取现金流量表数据 (cash flow statement)
            try:
                cashflow_df = await asyncio.to_thread(
                    self.api.cashflow,
                    **query_params
                )
                if cashflow_df is not None and not cashflow_df.empty:
                    financial_data['cashflow_statement'] = cashflow_df.to_dict('records')
                    self.logger.debug(f"✅ {ts_code} 现金流量表数据获取成功: {len(cashflow_df)} 条记录")
                else:
                    self.logger.debug(f"⚠️ {ts_code} 现金流量表数据为空")
            except Exception as e:
                self.logger.warning(f"❌ 获取{ts_code}现金流量表数据失败: {e}")

            # 4. 获取财务指标数据 (financial indicators)
            try:
                indicator_df = await asyncio.to_thread(
                    self.api.fina_indicator,
                    **query_params
                )
                if indicator_df is not None and not indicator_df.empty:
                    financial_data['financial_indicators'] = indicator_df.to_dict('records')
                    self.logger.debug(f"✅ {ts_code} 财务指标数据获取成功: {len(indicator_df)} 条记录")
                else:
                    self.logger.debug(f"⚠️ {ts_code} 财务指标数据为空")
            except Exception as e:
                self.logger.warning(f"❌ 获取{ts_code}财务指标数据失败: {e}")

            # 5. 获取主营业务构成数据 (可选)
            try:
                mainbz_df = await asyncio.to_thread(
                    self.api.fina_mainbz,
                    **query_params
                )
                if mainbz_df is not None and not mainbz_df.empty:
                    financial_data['main_business'] = mainbz_df.to_dict('records')
                    self.logger.debug(f"✅ {ts_code} 主营业务构成数据获取成功: {len(mainbz_df)} 条记录")
                else:
                    self.logger.debug(f"⚠️ {ts_code} 主营业务构成数据为空")
            except Exception as e:
                self.logger.debug(f"获取{ts_code}主营业务构成数据失败: {e}")  # 主营业务数据不是必需的，保持debug级别

            if financial_data:
                # 标准化财务数据
                standardized_data = self._standardize_tushare_financial_data(financial_data, ts_code)
                self.logger.info(f"✅ {ts_code} Tushare财务数据获取完成: {len(financial_data)} 个数据集")
                return standardized_data
            else:
                self.logger.warning(f"⚠️ {ts_code} 未获取到任何Tushare财务数据")
                return None

        except Exception as e:
            self.logger.error(f"❌ 获取Tushare财务数据失败 symbol={symbol}: {e}")
            return None

    async def get_dividend_data(self, symbol: str, limit: int = 10) -> Optional[List[Dict[str, Any]]]:
        """
        获取分红送股数据

        Args:
            symbol: 股票代码
            limit: 获取记录数量，默认10条

        Returns:
            分红送股记录列表，每条包含 ts_code, end_date, ann_date, div_proc,
            stk_div, stk_bo_rate, stk_co_rate, cash_div, cash_div_tax,
            record_date, ex_date, pay_date 等字段
        """
        if not self.is_available():
            return None

        try:
            ts_code = self._normalize_ts_code(symbol)
            self.logger.debug(f"💰 获取Tushare分红送股数据: {ts_code}")

            dividend_df = await asyncio.to_thread(
                self.api.dividend,
                ts_code=ts_code,
                fields='ts_code,end_date,ann_date,div_proc,stk_div,stk_bo_rate,stk_co_rate,'
                       'cash_div,cash_div_tax,record_date,ex_date,pay_date,div_listdate,'
                       'imp_ann_date,base_date,base_share'
            )

            if dividend_df is not None and not dividend_df.empty:
                # 只保留已实施的分红记录（排除预案等）
                # 按分红年度倒序排列
                dividend_df = dividend_df.sort_values('end_date', ascending=False)
                records = dividend_df.head(limit).to_dict('records')
                self.logger.info(f"✅ {ts_code} 分红送股数据获取成功: {len(records)} 条记录")
                return records
            else:
                self.logger.debug(f"⚠️ {ts_code} 分红送股数据为空")
                return []

        except Exception as e:
            self.logger.error(f"❌ 获取Tushare分红送股数据失败 symbol={symbol}: {e}")
            return None

    async def get_stock_news(self, symbol: str = None, limit: int = 10,
                           hours_back: int = 24, src: str = None) -> Optional[List[Dict[str, Any]]]:
        """
        获取股票新闻（需要Tushare新闻权限）

        Args:
            symbol: 股票代码，为None时获取市场新闻
            limit: 返回数量限制
            hours_back: 回溯小时数，默认24小时
            src: 新闻源，默认自动选择

        Returns:
            新闻列表
        """
        if not self.is_available():
            return None

        try:
            from datetime import datetime, timedelta

            # 计算时间范围
            end_time = datetime.now()
            start_time = end_time - timedelta(hours=hours_back)

            start_date = start_time.strftime('%Y-%m-%d %H:%M:%S')
            end_date = end_time.strftime('%Y-%m-%d %H:%M:%S')

            self.logger.debug(f"📰 获取Tushare新闻: symbol={symbol}, 时间范围={start_date} 到 {end_date}")

            # 支持的新闻源列表（按优先级排序）
            news_sources = [
                'sina',        # 新浪财经
                'eastmoney',   # 东方财富
                '10jqka',      # 同花顺
                'wallstreetcn', # 华尔街见闻
                'cls',         # 财联社
                'yicai',       # 第一财经
                'jinrongjie',  # 金融界
                'yuncaijing',  # 云财经
                'fenghuang'    # 凤凰新闻
            ]

            # 如果指定了数据源，优先使用
            if src and src in news_sources:
                sources_to_try = [src]
            else:
                sources_to_try = news_sources[:3]  # 默认尝试前3个源

            all_news = []

            for source in sources_to_try:
                try:
                    self.logger.debug(f"📰 尝试从 {source} 获取新闻...")

                    # 获取新闻数据
                    news_df = await asyncio.to_thread(
                        self.api.news,
                        src=source,
                        start_date=start_date,
                        end_date=end_date
                    )

                    if news_df is not None and not news_df.empty:
                        source_news = self._process_tushare_news(news_df, source, symbol, limit)
                        all_news.extend(source_news)

                        self.logger.info(f"✅ 从 {source} 获取到 {len(source_news)} 条新闻")

                        # 如果已经获取足够的新闻，停止尝试其他源
                        if len(all_news) >= limit:
                            break
                    else:
                        self.logger.debug(f"⚠️ {source} 未返回新闻数据")

                except Exception as e:
                    self.logger.debug(f"从 {source} 获取新闻失败: {e}")
                    continue

                # API限流
                await asyncio.sleep(0.2)

            # 去重和排序
            if all_news:
                # 按时间排序并去重
                unique_news = self._deduplicate_news(all_news)
                sorted_news = sorted(unique_news, key=lambda x: x.get('publish_time', datetime.min), reverse=True)

                # 限制返回数量
                final_news = sorted_news[:limit]

                self.logger.info(f"✅ Tushare新闻获取成功: {len(final_news)} 条（去重后）")
                return final_news
            else:
                self.logger.warning("⚠️ 未获取到任何Tushare新闻数据")
                return []

        except Exception as e:
            # 如果是权限问题，给出明确提示
            if any(keyword in str(e).lower() for keyword in ['权限', 'permission', 'unauthorized', 'access denied']):
                self.logger.warning(f"⚠️ Tushare新闻接口需要单独开通权限（付费功能）: {e}")
            elif "积分" in str(e) or "point" in str(e).lower():
                self.logger.warning(f"⚠️ Tushare积分不足，无法获取新闻数据: {e}")
            else:
                self.logger.error(f"❌ 获取Tushare新闻失败: {e}")
            return None

    def _process_tushare_news(self, news_df: pd.DataFrame, source: str,
                            symbol: str = None, limit: int = 10) -> List[Dict[str, Any]]:
        """处理Tushare新闻数据"""
        news_list = []

        # 限制处理数量
        df_limited = news_df.head(limit * 2)  # 多获取一些，用于过滤

        for _, row in df_limited.iterrows():
            news_item = {
                "title": str(row.get('title', '') or row.get('content', '')[:50] + '...'),
                "content": str(row.get('content', '')),
                "summary": self._generate_summary(row.get('content', '')),
                "url": "",  # Tushare新闻接口不提供URL
                "source": self._get_source_name(source),
                "author": "",
                "publish_time": self._parse_tushare_news_time(row.get('datetime', '')),
                "category": self._classify_tushare_news(row.get('channels', ''), row.get('content', '')),
                "sentiment": self._analyze_news_sentiment(row.get('content', ''), row.get('title', '')),
                "importance": self._assess_news_importance(row.get('content', ''), row.get('title', '')),
                "keywords": self._extract_keywords(row.get('content', ''), row.get('title', '')),
                "data_source": "tushare",
                "original_source": source
            }

            # 如果指定了股票代码，过滤相关新闻
            if symbol:
                if self._is_news_relevant_to_symbol(news_item, symbol):
                    news_list.append(news_item)
            else:
                news_list.append(news_item)

        return news_list

    def _get_source_name(self, source_code: str) -> str:
        """获取新闻源中文名称"""
        source_names = {
            'sina': '新浪财经',
            'eastmoney': '东方财富',
            '10jqka': '同花顺',
            'wallstreetcn': '华尔街见闻',
            'cls': '财联社',
            'yicai': '第一财经',
            'jinrongjie': '金融界',
            'yuncaijing': '云财经',
            'fenghuang': '凤凰新闻'
        }
        return source_names.get(source_code, source_code)

    def _generate_summary(self, content: str) -> str:
        """生成新闻摘要"""
        if not content:
            return ""

        content_str = str(content)
        if len(content_str) <= 200:
            return content_str

        # 简单的摘要生成：取前200个字符
        return content_str[:200] + "..."

    def _is_news_relevant_to_symbol(self, news_item: Dict[str, Any], symbol: str) -> bool:
        """判断新闻是否与股票相关"""
        content = news_item.get("content", "").lower()
        title = news_item.get("title", "").lower()

        # 标准化股票代码
        symbol_clean = symbol.replace('.SH', '').replace('.SZ', '').zfill(6)

        # 关键词匹配
        return any([
            symbol_clean in content,
            symbol_clean in title,
            symbol in content,
            symbol in title
        ])

    def _deduplicate_news(self, news_list: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """新闻去重"""
        seen_titles = set()
        unique_news = []

        for news in news_list:
            title = news.get('title', '')
            if title and title not in seen_titles:
                seen_titles.add(title)
                unique_news.append(news)

        return unique_news

    def _analyze_news_sentiment(self, content: str, title: str) -> str:
        """分析新闻情绪"""
        text = f"{title} {content}".lower()

        positive_keywords = ['利好', '上涨', '增长', '盈利', '突破', '创新高', '买入', '推荐']
        negative_keywords = ['利空', '下跌', '亏损', '风险', '暴跌', '卖出', '警告', '下调']

        positive_count = sum(1 for keyword in positive_keywords if keyword in text)
        negative_count = sum(1 for keyword in negative_keywords if keyword in text)

        if positive_count > negative_count:
            return 'positive'
        elif negative_count > positive_count:
            return 'negative'
        else:
            return 'neutral'

    def _assess_news_importance(self, content: str, title: str) -> str:
        """评估新闻重要性"""
        text = f"{title} {content}".lower()

        high_importance_keywords = ['业绩', '财报', '重大', '公告', '监管', '政策', '并购', '重组']
        medium_importance_keywords = ['分析', '预测', '观点', '建议', '行业', '市场']

        if any(keyword in text for keyword in high_importance_keywords):
            return 'high'
        elif any(keyword in text for keyword in medium_importance_keywords):
            return 'medium'
        else:
            return 'low'

    def _extract_keywords(self, content: str, title: str) -> List[str]:
        """提取关键词"""
        text = f"{title} {content}"

        # 简单的关键词提取
        keywords = []
        common_keywords = ['股票', '公司', '市场', '投资', '业绩', '财报', '政策', '行业', '分析', '预测']

        for keyword in common_keywords:
            if keyword in text:
                keywords.append(keyword)

        return keywords[:5]  # 最多返回5个关键词

    def _parse_tushare_news_time(self, time_str: str) -> Optional[datetime]:
        """解析Tushare新闻时间"""
        if not time_str:
            return datetime.utcnow()

        try:
            # Tushare时间格式: 2018-11-21 09:30:00
            return datetime.strptime(str(time_str), '%Y-%m-%d %H:%M:%S')
        except Exception as e:
            self.logger.debug(f"解析Tushare新闻时间失败: {e}")
            return datetime.utcnow()

    def _classify_tushare_news(self, channels: str, content: str) -> str:
        """分类Tushare新闻"""
        channels = str(channels).lower()
        content = str(content).lower()

        # 根据频道和内容关键词分类
        if any(keyword in channels or keyword in content for keyword in ['公告', '业绩', '财报']):
            return 'company_announcement'
        elif any(keyword in channels or keyword in content for keyword in ['政策', '监管', '央行']):
            return 'policy_news'
        elif any(keyword in channels or keyword in content for keyword in ['行业', '板块']):
            return 'industry_news'
        elif any(keyword in channels or keyword in content for keyword in ['市场', '指数', '大盘']):
            return 'market_news'
        else:
            return 'other'

    async def get_financial_data_by_period(self, symbol: str, start_period: str = None,
                                         end_period: str = None, report_type: str = "quarterly") -> Optional[List[Dict[str, Any]]]:
        """
        按时间范围获取财务数据

        Args:
            symbol: 股票代码
            start_period: 开始报告期 (YYYYMMDD)
            end_period: 结束报告期 (YYYYMMDD)
            report_type: 报告类型 (quarterly/annual)

        Returns:
            财务数据列表，按报告期倒序排列
        """
        if not self.is_available():
            return None

        try:
            ts_code = self._normalize_ts_code(symbol)
            self.logger.debug(f"📊 按期间获取Tushare财务数据: {ts_code}, {start_period} - {end_period}")

            # 构建查询参数
            query_params = {'ts_code': ts_code}

            if start_period:
                query_params['start_date'] = start_period
            if end_period:
                query_params['end_date'] = end_period

            # 获取利润表数据作为主要数据源
            income_df = await asyncio.to_thread(
                self.api.income,
                **query_params
            )

            if income_df is None or income_df.empty:
                self.logger.warning(f"⚠️ {ts_code} 指定期间无财务数据")
                return None

            # 按报告期分组获取完整财务数据
            financial_data_list = []

            for _, income_row in income_df.iterrows():
                period = income_row['end_date']

                # 获取该期间的完整财务数据
                period_data = await self.get_financial_data(
                    symbol=symbol,
                    period=period,
                    limit=1
                )

                if period_data:
                    financial_data_list.append(period_data)

                # API限流
                await asyncio.sleep(0.1)

            self.logger.info(f"✅ {ts_code} 按期间获取财务数据完成: {len(financial_data_list)} 个报告期")
            return financial_data_list

        except Exception as e:
            self.logger.error(f"❌ 按期间获取Tushare财务数据失败 symbol={symbol}: {e}")
            return None

    async def get_financial_indicators_only(self, symbol: str, limit: int = 4) -> Optional[Dict[str, Any]]:
        """
        仅获取财务指标数据（轻量级接口）

        Args:
            symbol: 股票代码
            limit: 获取记录数量

        Returns:
            财务指标数据
        """
        if not self.is_available():
            return None

        try:
            ts_code = self._normalize_ts_code(symbol)

            # 仅获取财务指标
            indicator_df = await asyncio.to_thread(
                self.api.fina_indicator,
                ts_code=ts_code,
                limit=limit
            )

            if indicator_df is not None and not indicator_df.empty:
                indicators = indicator_df.to_dict('records')

                return {
                    "symbol": symbol,
                    "ts_code": ts_code,
                    "financial_indicators": indicators,
                    "data_source": "tushare",
                    "updated_at": datetime.utcnow()
                }

            return None

        except Exception as e:
            self.logger.error(f"❌ 获取Tushare财务指标失败 symbol={symbol}: {e}")
            return None

    # ==================== 数据标准化方法 ====================

    def standardize_basic_info(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """标准化股票基础信息"""
        ts_code = raw_data.get('ts_code', '')
        symbol = raw_data.get('symbol', ts_code.split('.')[0] if '.' in ts_code else ts_code)

        return {
            # 基础字段
            "code": symbol,
            "name": raw_data.get('name', ''),
            "symbol": symbol,
            "full_symbol": ts_code,

            # 市场信息
            "market_info": self._determine_market_info_from_ts_code(ts_code),

            # 业务信息
            "area": self._safe_str(raw_data.get('area')),
            "industry": self._safe_str(raw_data.get('industry')),
            "market": raw_data.get('market'),  # 主板/创业板/科创板
            "list_date": self._format_date_output(raw_data.get('list_date')),

            # 港股通信息
            "is_hs": raw_data.get('is_hs'),

            # 实控人信息
            "act_name": raw_data.get('act_name'),
            "act_ent_type": raw_data.get('act_ent_type'),

            # 元数据
            "data_source": "tushare",
            "data_version": 1,
            "updated_at": datetime.utcnow()
        }

    def standardize_quotes(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """标准化实时行情数据"""
        ts_code = raw_data.get('ts_code', '')
        symbol = ts_code.split('.')[0] if '.' in ts_code else ts_code

        return {
            # 基础字段
            "code": symbol,
            "symbol": symbol,
            "full_symbol": ts_code,
            "market": self._determine_market(ts_code),

            # 价格数据
            "close": self._convert_to_float(raw_data.get('close')),
            "current_price": self._convert_to_float(raw_data.get('close')),
            "open": self._convert_to_float(raw_data.get('open')),
            "high": self._convert_to_float(raw_data.get('high')),
            "low": self._convert_to_float(raw_data.get('low')),
            "pre_close": self._convert_to_float(raw_data.get('pre_close')),

            # 变动数据
            "change": self._convert_to_float(raw_data.get('change')),
            "pct_chg": self._convert_to_float(raw_data.get('pct_chg')),

            # 成交数据
            # 🔥 成交量单位转换：Tushare 返回的是手，需要转换为股
            "volume": self._convert_to_float(raw_data.get('vol')) * 100 if raw_data.get('vol') else None,
            # 🔥 成交额单位转换：Tushare daily 接口返回的是千元，需要转换为元
            "amount": self._convert_to_float(raw_data.get('amount')) * 1000 if raw_data.get('amount') else None,

            # 财务指标
            "total_mv": self._convert_to_float(raw_data.get('total_mv')),
            "circ_mv": self._convert_to_float(raw_data.get('circ_mv')),
            "pe": self._convert_to_float(raw_data.get('pe')),
            "pb": self._convert_to_float(raw_data.get('pb')),
            "turnover_rate": self._convert_to_float(raw_data.get('turnover_rate')),

            # 时间数据
            "trade_date": self._format_date_output(raw_data.get('trade_date')),
            "timestamp": datetime.utcnow(),

            # 元数据
            "data_source": "tushare",
            "data_version": 1,
            "updated_at": datetime.utcnow()
        }

    # ==================== 辅助方法 ====================

    def _normalize_ts_code(self, symbol: str) -> str:
        """标准化为Tushare的ts_code格式"""
        if '.' in symbol:
            return symbol  # 已经是ts_code格式

        # 6位数字代码，需要添加后缀
        if symbol.isdigit() and len(symbol) == 6:
            # 上交所：60/68（A股）、50/51/52/58/56（ETF/LOF等）、11（国债/可转债）、90（B股）
            if symbol.startswith(('60', '68', '90', '50', '51', '52', '58', '56', '11')):
                return f"{symbol}.SH"  # 上交所
            # 深交所：00/30（A股）、15/16/12（ETF/LOF/可转债等）、20（B股）
            elif symbol.startswith(('00', '30', '20', '15', '16', '12')):
                return f"{symbol}.SZ"  # 深交所
            elif symbol.startswith(('8', '4', '92')):
                return f"{symbol}.BJ"  # 北交所
            else:
                return f"{symbol}.SZ"  # 默认深交所

        return symbol

    @staticmethod
    def _is_etf(ts_code: str) -> bool:
        """判断是否为ETF/基金类标的（pro_bar 不支持，需走 fund_daily）。

        上交所ETF: 50/51/52/56/58 开头
        深交所ETF: 15/16 开头
        """
        code = ts_code.split('.')[0] if '.' in ts_code else ts_code
        if not code.isdigit() or len(code) != 6:
            return False
        return code.startswith(('50', '51', '52', '56', '58', '15', '16'))

    def _determine_market_info_from_ts_code(self, ts_code: str) -> Dict[str, Any]:
        """根据ts_code确定市场信息"""
        if '.SH' in ts_code:
            return {
                "market": "CN",
                "exchange": "SSE",
                "exchange_name": "上海证券交易所",
                "currency": "CNY",
                "timezone": "Asia/Shanghai"
            }
        elif '.SZ' in ts_code:
            return {
                "market": "CN",
                "exchange": "SZSE",
                "exchange_name": "深圳证券交易所",
                "currency": "CNY",
                "timezone": "Asia/Shanghai"
            }
        elif '.BJ' in ts_code:
            return {
                "market": "CN",
                "exchange": "BSE",
                "exchange_name": "北京证券交易所",
                "currency": "CNY",
                "timezone": "Asia/Shanghai"
            }
        else:
            return {
                "market": "CN",
                "exchange": "UNKNOWN",
                "exchange_name": "未知交易所",
                "currency": "CNY",
                "timezone": "Asia/Shanghai"
            }

    def _determine_market(self, ts_code: str) -> str:
        """确定市场代码"""
        market_info = self._determine_market_info_from_ts_code(ts_code)
        return market_info.get("market", "CN")

    def _format_date(self, date_value: Union[str, date]) -> str:
        """格式化日期为Tushare格式 (YYYYMMDD)"""
        if isinstance(date_value, str):
            return date_value.replace('-', '')
        elif isinstance(date_value, date):
            return date_value.strftime('%Y%m%d')
        else:
            return str(date_value).replace('-', '')

    def _standardize_historical_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """标准化历史数据"""
        # 重命名列
        column_mapping = {
            'trade_date': 'date',
            'vol': 'volume'
        }
        df = df.rename(columns=column_mapping)

        # 格式化日期
        if 'date' in df.columns:
            df['date'] = pd.to_datetime(df['date'], format='%Y%m%d')
            df.set_index('date', inplace=True)

        # 按日期排序
        df = df.sort_index()

        return df

    def _standardize_tushare_financial_data(self, financial_data: Dict[str, Any], ts_code: str) -> Dict[str, Any]:
        """
        标准化Tushare财务数据

        Args:
            financial_data: 原始财务数据字典
            ts_code: Tushare股票代码

        Returns:
            标准化后的财务数据
        """
        try:
            # 优先使用“已披露”的最新报告，避免未来预约披露期覆盖当前可用财报。
            income_statements = financial_data.get('income_statement', []) or []
            balance_statements = financial_data.get('balance_sheet', []) or []
            cashflow_statements = financial_data.get('cashflow_statement', []) or []
            indicator_statements = financial_data.get('financial_indicators', []) or []

            latest_income = self._pick_latest_disclosed_record(income_statements)
            if not latest_income and income_statements:
                latest_income = income_statements[0]

            latest_period = str((latest_income or {}).get('end_date') or '')

            latest_balance = self._pick_record_by_period(balance_statements, latest_period)
            if not latest_balance:
                latest_balance = self._pick_latest_disclosed_record(balance_statements)
            if not latest_balance and balance_statements:
                latest_balance = balance_statements[0]

            latest_cashflow = self._pick_record_by_period(cashflow_statements, latest_period)
            if not latest_cashflow:
                latest_cashflow = self._pick_latest_disclosed_record(cashflow_statements)
            if not latest_cashflow and cashflow_statements:
                latest_cashflow = cashflow_statements[0]

            latest_indicator = self._pick_record_by_period(indicator_statements, latest_period)
            if not latest_indicator:
                latest_indicator = self._pick_latest_disclosed_record(indicator_statements)
            if not latest_indicator and indicator_statements:
                latest_indicator = indicator_statements[0]

            latest_income = latest_income or {}
            latest_balance = latest_balance or {}
            latest_cashflow = latest_cashflow or {}
            latest_indicator = latest_indicator or {}

            # 提取基础信息
            symbol = ts_code.split('.')[0] if '.' in ts_code else ts_code
            report_period = latest_income.get('end_date') or latest_balance.get('end_date') or latest_cashflow.get('end_date')
            ann_date = latest_income.get('ann_date') or latest_balance.get('ann_date') or latest_cashflow.get('ann_date')

            # 计算 TTM 数据
            revenue_ttm = self._calculate_ttm_from_tushare(income_statements, 'revenue')
            net_profit_ttm = self._calculate_ttm_from_tushare(income_statements, 'n_income_attr_p')

            standardized_data = {
                # 基础信息
                "symbol": symbol,
                "ts_code": ts_code,
                "report_period": report_period,
                "ann_date": ann_date,
                "report_type": self._determine_report_type(report_period),

                # 利润表核心指标
                "revenue": self._safe_float(latest_income.get('revenue')),  # 营业收入（原始报告期口径，A股季报通常为年初累计）
                "revenue_ttm": revenue_ttm,  # 营业收入（TTM）
                "oper_rev": self._safe_float(latest_income.get('oper_rev')),  # 营业收入
                "net_income": self._safe_float(latest_income.get('n_income')),  # 净利润（原始报告期口径，A股季报通常为年初累计）
                "net_profit": self._safe_float(latest_income.get('n_income_attr_p')),  # 归属母公司净利润（原始报告期口径，A股季报通常为年初累计）
                "net_profit_ttm": net_profit_ttm,  # 归属母公司净利润（TTM）
                "oper_profit": self._safe_float(latest_income.get('operate_profit')),  # 营业利润
                "total_profit": self._safe_float(latest_income.get('total_profit')),  # 利润总额
                "oper_cost": self._safe_float(latest_income.get('oper_cost')),  # 营业成本
                "oper_exp": self._safe_float(latest_income.get('oper_exp')),  # 营业费用
                "admin_exp": self._safe_float(latest_income.get('admin_exp')),  # 管理费用
                "fin_exp": self._safe_float(latest_income.get('fin_exp')),  # 财务费用
                "rd_exp": self._safe_float(latest_income.get('rd_exp')),  # 研发费用
                "credit_impa_loss": self._safe_float(latest_income.get('credit_impa_loss')),  # 信用减值损失（含坏账准备当期计提）
                "assets_impair_loss": self._safe_float(latest_income.get('assets_impair_loss')),  # 资产减值损失

                # 资产负债表核心指标
                "total_assets": self._safe_float(latest_balance.get('total_assets')),  # 总资产
                "total_liab": self._safe_float(latest_balance.get('total_liab')),  # 总负债
                "total_equity": self._safe_float(latest_balance.get('total_hldr_eqy_exc_min_int')),  # 股东权益
                "total_cur_assets": self._safe_float(latest_balance.get('total_cur_assets')),  # 流动资产
                "total_nca": self._safe_float(latest_balance.get('total_nca')),  # 非流动资产
                "total_cur_liab": self._safe_float(latest_balance.get('total_cur_liab')),  # 流动负债
                "total_ncl": self._safe_float(latest_balance.get('total_ncl')),  # 非流动负债
                "money_cap": self._safe_float(latest_balance.get('money_cap')),  # 货币资金
                "accounts_receiv": self._safe_float(latest_balance.get('accounts_receiv')),  # 应收账款
                "inventories": self._safe_float(latest_balance.get('inventories')),  # 存货
                "fix_assets": self._safe_float(latest_balance.get('fix_assets')),  # 固定资产
                "goodwill": self._safe_float(latest_balance.get('goodwill')),  # 商誉（并购溢价形成的无形资产，Q4年报通常才有完整数据）

                # 现金流量表核心指标
                "n_cashflow_act": self._safe_float(latest_cashflow.get('n_cashflow_act')),  # 经营活动现金流
                "n_cashflow_inv_act": self._safe_float(latest_cashflow.get('n_cashflow_inv_act')),  # 投资活动现金流
                "n_cashflow_fin_act": self._safe_float(latest_cashflow.get('n_cashflow_fin_act')),  # 筹资活动现金流
                "c_cash_equ_end_period": self._safe_float(latest_cashflow.get('c_cash_equ_end_period')),  # 期末现金
                "c_cash_equ_beg_period": self._safe_float(latest_cashflow.get('c_cash_equ_beg_period')),  # 期初现金

                # 财务指标
                "roe": self._safe_float(latest_indicator.get('roe')),  # 净资产收益率
                "roa": self._safe_float(latest_indicator.get('roa')),  # 总资产收益率
                "roe_waa": self._safe_float(latest_indicator.get('roe_waa')),  # 加权平均净资产收益率
                "roe_dt": self._safe_float(latest_indicator.get('roe_dt')),  # 净资产收益率(扣除非经常损益)
                "roa2": self._safe_float(latest_indicator.get('roa2')),  # 总资产收益率(扣除非经常损益)
                "gross_margin": self._safe_float(latest_indicator.get('grossprofit_margin')),  # 🔥 修复：使用 grossprofit_margin（销售毛利率%）而不是 gross_margin（毛利绝对值）
                "netprofit_margin": self._safe_float(latest_indicator.get('netprofit_margin')),  # 销售净利率
                "cogs_of_sales": self._safe_float(latest_indicator.get('cogs_of_sales')),  # 销售成本率
                "expense_of_sales": self._safe_float(latest_indicator.get('expense_of_sales')),  # 销售期间费用率
                "profit_to_gr": self._safe_float(latest_indicator.get('profit_to_gr')),  # 净利润/营业总收入
                "saleexp_to_gr": self._safe_float(latest_indicator.get('saleexp_to_gr')),  # 销售费用/营业总收入
                "adminexp_of_gr": self._safe_float(latest_indicator.get('adminexp_of_gr')),  # 管理费用/营业总收入
                "finaexp_of_gr": self._safe_float(latest_indicator.get('finaexp_of_gr')),  # 财务费用/营业总收入
                "debt_to_assets": self._safe_float(latest_indicator.get('debt_to_assets')),  # 资产负债率
                "assets_to_eqt": self._safe_float(latest_indicator.get('assets_to_eqt')),  # 权益乘数
                "dp_assets_to_eqt": self._safe_float(latest_indicator.get('dp_assets_to_eqt')),  # 权益乘数(杜邦分析)
                "ca_to_assets": self._safe_float(latest_indicator.get('ca_to_assets')),  # 流动资产/总资产
                "nca_to_assets": self._safe_float(latest_indicator.get('nca_to_assets')),  # 非流动资产/总资产
                "current_ratio": self._safe_float(latest_indicator.get('current_ratio')),  # 流动比率
                "quick_ratio": self._safe_float(latest_indicator.get('quick_ratio')),  # 速动比率
                "cash_ratio": self._safe_float(latest_indicator.get('cash_ratio')),  # 现金比率

                # 原始数据保留（用于详细分析）
                "raw_data": {
                    "income_statement": financial_data.get('income_statement', []),
                    "balance_sheet": financial_data.get('balance_sheet', []),
                    "cashflow_statement": financial_data.get('cashflow_statement', []),
                    "financial_indicators": financial_data.get('financial_indicators', []),
                    "main_business": financial_data.get('main_business', [])
                },

                # 元数据
                "data_source": "tushare",
                "updated_at": datetime.utcnow()
            }

            return standardized_data

        except Exception as e:
            self.logger.error(f"❌ 标准化Tushare财务数据失败: {e}")
            return {
                "symbol": ts_code.split('.')[0] if '.' in ts_code else ts_code,
                "data_source": "tushare",
                "updated_at": datetime.utcnow(),
                "error": str(e)
            }

    def _pick_record_by_period(self, statements: List[Dict[str, Any]], period: str) -> Optional[Dict[str, Any]]:
        """按报告期匹配记录。"""
        if not statements or not period:
            return None
        target = str(period)
        for record in statements:
            if str(record.get('end_date') or '') == target:
                return record
        return None

    def _pick_latest_disclosed_record(self, statements: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """
        选择已披露记录中报告期最新的一条。

        规则：
        1. 优先 ann_date/f_ann_date <= 今天 的记录
        2. 在可用记录中按 end_date 倒序选择最新
        """
        if not statements:
            return None

        today = datetime.utcnow().strftime('%Y%m%d')
        disclosed: List[Dict[str, Any]] = []

        for record in statements:
            ann_date = str(record.get('ann_date') or record.get('f_ann_date') or '').replace('-', '')
            end_date = str(record.get('end_date') or '').replace('-', '')

            if not end_date:
                continue

            # ann_date 缺失时，默认保留该记录，避免误删历史数据。
            if not ann_date or ann_date <= today:
                disclosed.append(record)

        if not disclosed:
            return None

        disclosed.sort(key=lambda rec: str(rec.get('end_date') or '').replace('-', ''), reverse=True)
        return disclosed[0]

    def _calculate_ttm_from_tushare(self, income_statements: list, field: str) -> Optional[float]:
        """
        从 Tushare 利润表数据计算 TTM（最近12个月）

        Tushare 利润表数据是累计值（从年初到报告期的累计）：
        - 2025Q1 (20250331): 2025年1-3月累计
        - 2025Q2 (20250630): 2025年1-6月累计
        - 2025Q3 (20250930): 2025年1-9月累计
        - 2025Q4 (20251231): 2025年1-12月累计（年报）

        TTM 计算公式：
        TTM = 去年同期之后的最近年报 + (本期累计 - 去年同期累计)

        例如：2025Q2 TTM = 2024年报 + (2025Q2 - 2024Q2)
                        = 2024年1-12月 + (2025年1-6月 - 2024年1-6月)
                        = 2024年7-12月 + 2025年1-6月
                        = 最近12个月

        Args:
            income_statements: 利润表数据列表（按报告期倒序）
            field: 字段名（'revenue' 或 'n_income_attr_p'）

        Returns:
            TTM 值，如果无法计算则返回 None
        """
        if not income_statements or len(income_statements) < 1:
            return None

        try:
            latest = income_statements[0]
            latest_period = latest.get('end_date')
            latest_value = self._safe_float(latest.get(field))

            if not latest_period or latest_value is None:
                return None

            # 判断最新期的类型
            month_day = latest_period[4:8]

            # 如果最新期是年报（1231），直接使用
            if month_day == '1231':
                self.logger.debug(f"✅ TTM计算: 使用年报数据 {latest_period} = {latest_value:.2f}")
                return latest_value

            # 如果是季报/半年报，需要计算 TTM = 基准期 + (本期累计 - 去年同期累计)

            # 1. 查找去年同期
            latest_year = latest_period[:4]
            last_year = str(int(latest_year) - 1)
            last_year_same_period = last_year + latest_period[4:]

            last_year_same = None
            for stmt in income_statements:
                if stmt.get('end_date') == last_year_same_period:
                    last_year_same = stmt
                    break

            if not last_year_same:
                # 缺少去年同期数据，无法准确计算 TTM
                self.logger.warning(f"⚠️ TTM计算失败: 缺少去年同期数据（需要: {last_year_same_period}，最新期: {latest_period}）")
                return None

            last_year_value = self._safe_float(last_year_same.get(field))
            if last_year_value is None:
                self.logger.warning(f"⚠️ TTM计算失败: 去年同期数据值为空（{last_year_same_period}）")
                return None

            # 2. 查找"去年同期之后的最近年报"作为基准期
            # 例如：如果最新期是 2025Q2，去年同期是 2024Q2，则查找 2024年报（20241231）
            base_period = None
            for stmt in income_statements:
                period = stmt.get('end_date')
                # 必须满足：在去年同期之后 且 是年报（1231）
                if period and period > last_year_same_period and period[4:8] == '1231':
                    base_period = stmt
                    break

            if not base_period:
                # 没有找到合适的年报，无法计算
                # 这种情况通常发生在：最新期是 2025Q1，但 2024年报还没公布
                self.logger.warning(f"⚠️ TTM计算失败: 缺少基准年报（需要在 {last_year_same_period} 之后的年报，最新期: {latest_period}）")
                return None

            base_value = self._safe_float(base_period.get(field))
            if base_value is None:
                self.logger.warning(f"⚠️ TTM计算失败: 基准年报数据值为空（{base_period.get('end_date')}）")
                return None

            # 3. 计算 TTM = 基准年报 + (本期累计 - 去年同期累计)
            ttm_value = base_value + (latest_value - last_year_value)

            self.logger.debug(
                f"✅ TTM计算: {base_period.get('end_date')}({base_value:.2f}) + "
                f"({latest_period}({latest_value:.2f}) - {last_year_same_period}({last_year_value:.2f})) = {ttm_value:.2f}"
            )

            return ttm_value

        except Exception as e:
            self.logger.warning(f"❌ TTM计算异常: {e}")
            return None

    def _determine_report_type(self, report_period: str) -> str:
        """根据报告期确定报告类型"""
        if not report_period:
            return "quarterly"

        try:
            # 报告期格式: YYYYMMDD
            month_day = report_period[4:8]
            if month_day == "1231":
                return "annual"  # 年报
            else:
                return "quarterly"  # 季报
        except:
            return "quarterly"

    def _safe_float(self, value) -> Optional[float]:
        """安全转换为浮点数，处理各种异常情况"""
        if value is None:
            return None

        try:
            # 处理字符串类型
            if isinstance(value, str):
                value = value.strip()
                if not value or value.lower() in ['nan', 'null', 'none', '--', '']:
                    return None
                # 移除可能的单位符号
                value = value.replace(',', '').replace('万', '').replace('亿', '')

            # 处理数值类型
            if isinstance(value, (int, float)):
                # 检查是否为NaN
                if isinstance(value, float) and (value != value):  # NaN检查
                    return None
                return float(value)

            # 尝试转换
            return float(value)

        except (ValueError, TypeError, AttributeError):
            return None

    def _calculate_gross_profit(self, revenue, oper_cost) -> Optional[float]:
        """安全计算毛利润"""
        revenue_float = self._safe_float(revenue)
        oper_cost_float = self._safe_float(oper_cost)

        if revenue_float is not None and oper_cost_float is not None:
            return revenue_float - oper_cost_float
        return None

    def _safe_str(self, value) -> Optional[str]:
        """安全转换为字符串，处理NaN值"""
        if value is None:
            return None
        if isinstance(value, float) and (value != value):  # 检查NaN
            return None
        return str(value) if value else None

    # ==================== 板块/行业数据接口 ====================

    async def get_ths_index_list(self, index_type: str = "N") -> Optional[pd.DataFrame]:
        """
        获取同花顺板块列表

        Args:
            index_type: 板块类型
                - N: 行业板块
                - S: 概念板块
                - R: 地域板块
                - I: 行业指数（需要6000积分）

        Returns:
            板块列表 DataFrame，包含 ts_code, name, count, exchange, list_date, type
        """
        if not self.is_available():
            return None

        try:
            df = await asyncio.to_thread(
                self.api.ths_index,
                type=index_type
            )
            if df is not None and not df.empty:
                self.logger.info(f"✅ 获取同花顺{index_type}型板块列表: {len(df)} 个")
                return df
            return None
        except Exception as e:
            self.logger.error(f"❌ 获取同花顺板块列表失败: {e}")
            return None

    async def get_ths_daily(self, ts_code: str, start_date: str = None,
                           end_date: str = None) -> Optional[pd.DataFrame]:
        """
        获取同花顺板块日线行情

        Args:
            ts_code: 板块代码（如 885691.TI 表示酿酒行业）
            start_date: 开始日期 YYYYMMDD
            end_date: 结束日期 YYYYMMDD

        Returns:
            板块日线数据 DataFrame，包含 ts_code, trade_date, open, close, high, low,
            avg_price, change, pct_change, vol, turnover_rate, total_mv, float_mv
        """
        if not self.is_available():
            return None

        try:
            params = {'ts_code': ts_code}
            if start_date:
                params['start_date'] = start_date.replace('-', '')
            if end_date:
                params['end_date'] = end_date.replace('-', '')

            df = await asyncio.to_thread(
                self.api.ths_daily,
                **params
            )
            if df is not None and not df.empty:
                self.logger.info(f"✅ 获取板块 {ts_code} 日线数据: {len(df)} 条")
                return df
            return None
        except Exception as e:
            self.logger.error(f"❌ 获取板块日线数据失败: {e}")
            return None

    async def get_ths_member(self, ts_code: str = None,
                            con_code: str = None) -> Optional[pd.DataFrame]:
        """
        获取同花顺板块成分股

        Args:
            ts_code: 板块代码（正向查询：板块→成分股）
            con_code: 股票代码（反向查询：个股→所属板块）

        Returns:
            DataFrame，包含 ts_code (板块代码), code (股票代码), name (股票名称)
        """
        if not self.is_available():
            return None

        try:
            params = {}
            if ts_code:
                params['ts_code'] = ts_code
            if con_code:
                params['con_code'] = con_code

            if not params:
                self.logger.warning("⚠️ get_ths_member 需要指定 ts_code 或 con_code")
                return None

            df = await asyncio.to_thread(
                self.api.ths_member,
                **params
            )
            if df is not None and not df.empty:
                if ts_code:
                    self.logger.info(f"✅ 获取板块 {ts_code} 成分股: {len(df)} 只")
                else:
                    self.logger.info(f"✅ 获取股票 {con_code} 所属板块: {len(df)} 个")
                return df
            return None
        except Exception as e:
            self.logger.error(f"❌ 获取板块成分股失败: {e}")
            return None

    async def get_moneyflow_ths(self, trade_date: str = None,
                               ts_code: str = None,
                               start_date: str = None,
                               end_date: str = None) -> Optional[pd.DataFrame]:
        """
        获取同花顺**个股**资金流向（注意：这是个股级别，不是板块级别）

        Args:
            trade_date: 交易日期 YYYYMMDD
            ts_code: 股票代码
            start_date: 开始日期 YYYYMMDD
            end_date: 结束日期 YYYYMMDD

        Returns:
            DataFrame，包含个股资金流向数据
            - net_amount: 净流入金额（万元）
            - net_amount_rate: 净流入占比
            - buy_elg_amount: 特大单买入金额
            - buy_lg_amount: 大单买入金额
            - buy_md_amount: 中单买入金额
            - buy_sm_amount: 小单买入金额
        """
        if not self.is_available():
            return None

        try:
            params = {}
            if trade_date:
                params['trade_date'] = trade_date.replace('-', '')
            if ts_code:
                params['ts_code'] = ts_code
            if start_date:
                params['start_date'] = start_date.replace('-', '')
            if end_date:
                params['end_date'] = end_date.replace('-', '')

            df = await asyncio.to_thread(
                self.api.moneyflow_ths,
                **params
            )
            if df is not None and not df.empty:
                self.logger.info(f"✅ 获取个股资金流向数据: {len(df)} 条")
                return df
            return None
        except Exception as e:
            self.logger.error(f"❌ 获取个股资金流向失败: {e}")
            return None

    async def get_moneyflow_ind_ths(self, trade_date: str = None,
                                    ts_code: str = None,
                                    start_date: str = None,
                                    end_date: str = None) -> Optional[pd.DataFrame]:
        """
        获取同花顺**行业板块**资金流向

        Args:
            trade_date: 交易日期 YYYYMMDD（单日查询）
            ts_code: 行业板块代码（如 881166.TI）
            start_date: 开始日期 YYYYMMDD（范围查询）
            end_date: 结束日期 YYYYMMDD（范围查询）

        Returns:
            DataFrame，包含行业板块资金流向数据
            - ts_code: 板块代码
            - industry: 行业名称
            - lead_stock: 领涨股
            - close: 板块指数收盘
            - pct_change: 涨跌幅(%)
            - net_amount: 净流入金额（亿元）
            - net_buy_amount: 买入金额（亿元）
            - net_sell_amount: 卖出金额（亿元）
            - company_num: 成分股数量
        """
        if not self.is_available():
            return None

        try:
            params = {}
            if trade_date:
                params['trade_date'] = trade_date.replace('-', '')
            if ts_code:
                params['ts_code'] = ts_code
            if start_date:
                params['start_date'] = start_date.replace('-', '')
            if end_date:
                params['end_date'] = end_date.replace('-', '')

            df = await asyncio.to_thread(
                self.api.moneyflow_ind_ths,
                **params
            )
            if df is not None and not df.empty:
                self.logger.info(f"✅ 获取行业板块资金流向: {len(df)} 条")
                return df
            return None
        except Exception as e:
            self.logger.error(f"❌ 获取行业板块资金流向失败: {e}")
            return None

    async def get_moneyflow_cnt_ths(self, trade_date: str = None,
                                    ts_code: str = None,
                                    start_date: str = None,
                                    end_date: str = None) -> Optional[pd.DataFrame]:
        """
        获取同花顺**概念板块**资金流向

        注意：单次最大5000条。概念板块约387个，如日期范围超过12天，
        会自动分段拉取后合并。

        Args:
            trade_date: 交易日期 YYYYMMDD（单日查询）
            ts_code: 概念板块代码（如 886034.TI）
            start_date: 开始日期 YYYYMMDD（范围查询）
            end_date: 结束日期 YYYYMMDD（范围查询）

        Returns:
            DataFrame，包含概念板块资金流向数据
            - ts_code: 板块代码
            - name: 概念名称
            - lead_stock: 领涨股
            - close_price: 板块指数收盘
            - pct_change: 涨跌幅(%)
            - net_amount: 净流入金额（亿元）
            - net_buy_amount: 买入金额（亿元）
            - net_sell_amount: 卖出金额（亿元）
            - company_num: 成分股数量
        """
        if not self.is_available():
            return None

        try:
            params = {}
            if trade_date:
                params['trade_date'] = trade_date.replace('-', '')
            if ts_code:
                params['ts_code'] = ts_code
            if start_date:
                params['start_date'] = start_date.replace('-', '')
            if end_date:
                params['end_date'] = end_date.replace('-', '')

            # 概念板块约387个/天，超12天（387*12=4644）接近5000限制
            # 如果是日期范围查询且跨度大，分段拉取
            need_split = (start_date and end_date and not trade_date and not ts_code)
            if need_split:
                from datetime import datetime, timedelta
                sd = datetime.strptime(params['start_date'], '%Y%m%d')
                ed = datetime.strptime(params['end_date'], '%Y%m%d')
                days_span = (ed - sd).days
                if days_span > 12:
                    # 分段拉取，每段 12 天
                    dfs = []
                    seg_start = sd
                    while seg_start <= ed:
                        seg_end = min(seg_start + timedelta(days=11), ed)
                        seg_params = {
                            'start_date': seg_start.strftime('%Y%m%d'),
                            'end_date': seg_end.strftime('%Y%m%d'),
                        }
                        df_seg = await asyncio.to_thread(
                            self.api.moneyflow_cnt_ths, **seg_params
                        )
                        if df_seg is not None and not df_seg.empty:
                            dfs.append(df_seg)
                        seg_start = seg_end + timedelta(days=1)
                    if dfs:
                        df = pd.concat(dfs, ignore_index=True)
                        self.logger.info(f"✅ 获取概念板块资金流向(分段): {len(df)} 条")
                        return df
                    return None

            df = await asyncio.to_thread(
                self.api.moneyflow_cnt_ths,
                **params
            )
            if df is not None and not df.empty:
                self.logger.info(f"✅ 获取概念板块资金流向: {len(df)} 条")
                return df
            return None
        except Exception as e:
            self.logger.error(f"❌ 获取概念板块资金流向失败: {e}")
            return None

    async def get_moneyflow_ind_ths(self, trade_date: str = None,
                                   ts_code: str = None) -> Optional[pd.DataFrame]:
        """
        获取同花顺行业资金流向

        Args:
            trade_date: 交易日期 YYYYMMDD
            ts_code: 行业代码

        Returns:
            DataFrame，包含行业资金流向数据
            - industry: 行业名称
            - pct_change: 行业指数涨跌幅
            - company_num: 成分股数量
            - net_buy_amount: 流入资金（亿元）
            - net_sell_amount: 流出资金（亿元）
            - net_amount: 净额（亿元）
        """
        if not self.is_available():
            return None

        try:
            params = {}
            if trade_date:
                params['trade_date'] = trade_date.replace('-', '')
            if ts_code:
                params['ts_code'] = ts_code

            df = await asyncio.to_thread(
                self.api.moneyflow_ind_ths,
                **params
            )
            if df is not None and not df.empty:
                self.logger.info(f"✅ 获取行业资金流向数据: {len(df)} 条")
                return df
            return None
        except Exception as e:
            self.logger.error(f"❌ 获取行业资金流向失败: {e}")
            return None

    def get_stock_industry_sync(self, ticker: str) -> Optional[str]:
        """
        同步获取股票所属行业（从 stock_basic 提取）

        Args:
            ticker: 股票代码（如 000001 或 000001.SZ）

        Returns:
            行业名称，如 "银行"
        """
        if not self.is_available():
            return None

        try:
            ts_code = self._normalize_ts_code(ticker)
            df = self.api.stock_basic(
                ts_code=ts_code,
                fields='ts_code,name,industry'
            )
            if df is not None and not df.empty:
                industry = df.iloc[0].get('industry')
                if industry:
                    self.logger.info(f"✅ 股票 {ticker} 所属行业: {industry}")
                    return str(industry)
            return None
        except Exception as e:
            self.logger.error(f"❌ 获取股票行业失败: {e}")
            return None

    async def get_stock_industry(self, ticker: str) -> Optional[str]:
        """异步获取股票所属行业"""
        return await asyncio.to_thread(self.get_stock_industry_sync, ticker)

    async def get_industry_stocks(self, industry: str) -> Optional[pd.DataFrame]:
        """
        获取某行业的所有股票（精确匹配）

        Args:
            industry: 行业名称（如 "银行"、"全国地产"）

        Returns:
            该行业所有股票的 DataFrame
        """
        if not self.is_available():
            return None

        try:
            # 获取所有股票，然后精确匹配行业
            df = await asyncio.to_thread(
                self.api.stock_basic,
                list_status='L',
                fields='ts_code,symbol,name,industry,market,list_date'
            )

            if df is None or df.empty:
                return None

            # 精确匹配行业名称
            result_df = df[df['industry'] == industry].copy()

            if not result_df.empty:
                self.logger.info(f"✅ 获取 {industry} 行业股票: {len(result_df)} 只")
                return result_df
            else:
                self.logger.warning(f"⚠️ 未找到 {industry} 行业的股票")
                return None

        except Exception as e:
            self.logger.error(f"❌ 获取行业股票列表失败: {e}")
            return None

    async def get_sector_stocks_daily_basic(self, industry: str,
                                            trade_date: str) -> Optional[pd.DataFrame]:
        """
        获取某行业所有股票的每日基础指标

        Args:
            industry: 行业名称
            trade_date: 交易日期

        Returns:
            包含 PE、PB、总市值等指标的 DataFrame
        """
        if not self.is_available():
            return None

        try:
            # 1. 获取行业股票列表
            stocks_df = await self.get_industry_stocks(industry)
            if stocks_df is None or stocks_df.empty:
                return None

            # 2. 获取当日 daily_basic 数据
            date_str = trade_date.replace('-', '')
            daily_df = await asyncio.to_thread(
                self.api.daily_basic,
                trade_date=date_str,
                fields='ts_code,trade_date,close,pe,pe_ttm,pb,ps,ps_ttm,dv_ratio,dv_ttm,total_mv,circ_mv,turnover_rate'
            )

            if daily_df is None or daily_df.empty:
                return None

            # 3. 筛选行业内股票
            industry_codes = set(stocks_df['ts_code'].tolist())
            result_df = daily_df[daily_df['ts_code'].isin(industry_codes)].copy()

            # 4. 合并股票名称
            result_df = result_df.merge(
                stocks_df[['ts_code', 'name']],
                on='ts_code',
                how='left'
            )

            self.logger.info(f"✅ 获取 {industry} 行业 {len(result_df)} 只股票的每日指标")
            return result_df

        except Exception as e:
            self.logger.error(f"❌ 获取行业股票每日指标失败: {e}")
            return None

    # ==================== 指数数据 API ====================

    async def get_index_basic(
        self,
        market: str = None,
        ts_code: str = None
    ) -> Optional[pd.DataFrame]:
        """
        获取指数基本信息

        Args:
            market: 交易所 (SSE上交所/SZSE深交所/SW申万/MSCI/CSI中证)
            ts_code: 指数代码

        Returns:
            DataFrame 包含: ts_code, name, market, category, base_date, base_point
        """
        if not self.is_available():
            return None

        try:
            params = {}
            if market:
                params['market'] = market
            if ts_code:
                params['ts_code'] = ts_code

            df = self.api.index_basic(**params)
            self.logger.info(f"✅ 获取指数基本信息: {len(df)} 条")
            return df
        except Exception as e:
            self.logger.error(f"❌ 获取指数基本信息失败: {e}")
            return None

    async def get_index_daily(
        self,
        ts_code: str,
        start_date: str = None,
        end_date: str = None,
        use_cache: bool = True
    ) -> Optional[pd.DataFrame]:
        """
        获取指数日线行情（带缓存）

        Args:
            ts_code: 指数代码 (如 000001.SH)
            start_date: 开始日期 YYYYMMDD
            end_date: 结束日期 YYYYMMDD
            use_cache: 是否使用缓存（默认True）

        Returns:
            DataFrame 包含: trade_date, open, high, low, close, vol, amount, pct_chg
        """
        if not self.is_available():
            return None

        # 尝试从缓存获取
        cache_key = f"index_daily_{ts_code}_{start_date}_{end_date}"
        if use_cache:
            try:
                from tradingagents.dataflows.cache import get_cache
                cache = get_cache()
                # 指数日线数据缓存24小时有效
                cached_key = cache.find_cached_stock_data(
                    symbol=ts_code,
                    start_date=start_date,
                    end_date=end_date,
                    data_source="tushare_index",
                    max_age_hours=24
                )
                if cached_key:
                    cached_data = cache.load_stock_data(cached_key)
                    if cached_data is not None and not cached_data.empty if hasattr(cached_data, 'empty') else cached_data:
                        self.logger.info(f"📦 从缓存获取指数 {ts_code} 日线: {len(cached_data)} 条")
                        return cached_data
            except Exception as e:
                self.logger.debug(f"⚠️ 缓存读取失败: {e}")

        try:
            params = {'ts_code': ts_code}
            if start_date:
                params['start_date'] = start_date
            if end_date:
                params['end_date'] = end_date

            df = self.api.index_daily(**params)
            self.logger.info(f"✅ 获取指数 {ts_code} 日线: {len(df)} 条")

            # 保存到缓存
            if use_cache and df is not None and not df.empty:
                try:
                    from tradingagents.dataflows.cache import get_cache
                    cache = get_cache()
                    cache.save_stock_data(
                        symbol=ts_code,
                        data=df,
                        start_date=start_date,
                        end_date=end_date,
                        data_source="tushare_index"
                    )
                    self.logger.debug(f"💾 指数 {ts_code} 日线已缓存")
                except Exception as e:
                    self.logger.debug(f"⚠️ 缓存保存失败: {e}")

            return df
        except Exception as e:
            self.logger.error(f"❌ 获取指数日线失败: {e}")
            return None

    async def get_index_dailybasic(
        self,
        ts_code: str = None,
        trade_date: str = None,
        use_cache: bool = True
    ) -> Optional[pd.DataFrame]:
        """
        获取大盘指数每日指标（带缓存）

        Args:
            ts_code: 指数代码
            trade_date: 交易日期 YYYYMMDD
            use_cache: 是否使用缓存（默认True）

        Returns:
            DataFrame 包含: ts_code, trade_date, pe, pe_ttm, pb,
                          turnover_rate, total_mv, float_mv
        """
        if not self.is_available():
            return None

        # 尝试从缓存获取
        cache_symbol = ts_code or f"all_{trade_date}"
        if use_cache:
            try:
                from tradingagents.dataflows.cache import get_cache
                cache = get_cache()
                cached_key = cache.find_cached_stock_data(
                    symbol=f"index_basic_{cache_symbol}",
                    start_date=trade_date,
                    end_date=trade_date,
                    data_source="tushare_index_basic",
                    max_age_hours=24
                )
                if cached_key:
                    cached_data = cache.load_stock_data(cached_key)
                    if cached_data is not None and not cached_data.empty if hasattr(cached_data, 'empty') else cached_data:
                        self.logger.info(f"📦 从缓存获取指数每日指标: {len(cached_data)} 条")
                        return cached_data
            except Exception as e:
                self.logger.debug(f"⚠️ 缓存读取失败: {e}")

        try:
            params = {}
            if ts_code:
                params['ts_code'] = ts_code
            if trade_date:
                params['trade_date'] = trade_date

            df = self.api.index_dailybasic(**params)
            self.logger.info(f"✅ 获取指数每日指标: {len(df)} 条")

            # 保存到缓存
            if use_cache and df is not None and not df.empty:
                try:
                    from tradingagents.dataflows.cache import get_cache
                    cache = get_cache()
                    cache.save_stock_data(
                        symbol=f"index_basic_{cache_symbol}",
                        data=df,
                        start_date=trade_date,
                        end_date=trade_date,
                        data_source="tushare_index_basic"
                    )
                except Exception as e:
                    self.logger.debug(f"⚠️ 缓存保存失败: {e}")

            return df
        except Exception as e:
            self.logger.error(f"❌ 获取指数每日指标失败: {e}")
            return None

    async def get_daily_info(
        self,
        trade_date: str,
        exchange: str = None,
        use_cache: bool = True
    ) -> Optional[pd.DataFrame]:
        """
        获取每日市场交易统计（带缓存）

        Args:
            trade_date: 交易日期 YYYYMMDD
            exchange: 交易所 (SSE/SZSE)
            use_cache: 是否使用缓存（默认True）

        Returns:
            DataFrame 包含: trade_date, ts_code, ts_name, com_count,
                          total_share, float_share, total_mv, float_mv,
                          amount, vol, up_count, down_count, etc.
        """
        if not self.is_available():
            return None

        # 尝试从缓存获取
        cache_symbol = f"daily_info_{trade_date}_{exchange or 'all'}"
        if use_cache:
            try:
                from tradingagents.dataflows.cache import get_cache
                cache = get_cache()
                cached_key = cache.find_cached_stock_data(
                    symbol=cache_symbol,
                    start_date=trade_date,
                    end_date=trade_date,
                    data_source="tushare_daily_info",
                    max_age_hours=24
                )
                if cached_key:
                    cached_data = cache.load_stock_data(cached_key)
                    if cached_data is not None and not cached_data.empty if hasattr(cached_data, 'empty') else cached_data:
                        self.logger.info(f"📦 从缓存获取市场交易统计: {len(cached_data)} 条")
                        return cached_data
            except Exception as e:
                self.logger.debug(f"⚠️ 缓存读取失败: {e}")

        try:
            params = {'trade_date': trade_date}
            if exchange:
                params['exchange'] = exchange

            df = self.api.daily_info(**params)
            self.logger.info(f"✅ 获取市场交易统计: {len(df)} 条")

            # 保存到缓存
            if use_cache and df is not None and not df.empty:
                try:
                    from tradingagents.dataflows.cache import get_cache
                    cache = get_cache()
                    cache.save_stock_data(
                        symbol=cache_symbol,
                        data=df,
                        start_date=trade_date,
                        end_date=trade_date,
                        data_source="tushare_daily_info"
                    )
                except Exception as e:
                    self.logger.debug(f"⚠️ 缓存保存失败: {e}")

            return df
        except Exception as e:
            self.logger.error(f"❌ 获取市场交易统计失败: {e}")
            return None

    async def get_index_weight(
        self,
        index_code: str,
        trade_date: str = None
    ) -> Optional[pd.DataFrame]:
        """
        获取指数成分和权重

        Args:
            index_code: 指数代码 (如 000300.SH)
            trade_date: 交易日期 YYYYMMDD

        Returns:
            DataFrame 包含: index_code, con_code, trade_date, weight
        """
        if not self.is_available():
            return None

        try:
            params = {'index_code': index_code}
            if trade_date:
                params['trade_date'] = trade_date

            df = self.api.index_weight(**params)
            self.logger.info(f"✅ 获取指数 {index_code} 成分权重: {len(df)} 条")
            return df
        except Exception as e:
            self.logger.error(f"❌ 获取指数成分权重失败: {e}")
            return None

    # ==================== 大盘分析相关接口 ====================

    async def get_hsgt_moneyflow(
        self,
        trade_date: str = None,
        start_date: str = None,
        end_date: str = None
    ) -> Optional[pd.DataFrame]:
        """
        获取沪深港通资金流向（北向资金）

        Args:
            trade_date: 交易日期 (YYYYMMDD)
            start_date: 开始日期 (YYYYMMDD)
            end_date: 结束日期 (YYYYMMDD)

        Returns:
            DataFrame 包含:
            - trade_date: 交易日期
            - ggt_ss: 港股通（沪）净流入
            - ggt_sz: 港股通（深）净流入
            - hgt: 沪股通净流入
            - sgt: 深股通净流入
            - north_money: 北向资金净流入（hgt+sgt）
            - south_money: 南向资金净流入（ggt_ss+ggt_sz）
        """
        if not self.is_available():
            return None

        try:
            params = {}
            if trade_date:
                params['trade_date'] = trade_date.replace('-', '')
            if start_date:
                params['start_date'] = start_date.replace('-', '')
            if end_date:
                params['end_date'] = end_date.replace('-', '')

            df = await asyncio.to_thread(
                self.api.moneyflow_hsgt,
                **params
            )

            logger.info(f"获取到的原始北向资金流向数据: {df}")
            if df is not None and not df.empty:
                # 计算北向和南向资金总量
                df['north_money'] = df['hgt'].fillna(0) + df['sgt'].fillna(0)
                df['south_money'] = df['ggt_ss'].fillna(0) + df['ggt_sz'].fillna(0)
                self.logger.info(f"✅ 获取沪深港通资金流向: {len(df)} 条")
                return df
            return None

        except Exception as e:
            self.logger.error(f"❌ 获取沪深港通资金流向失败: {e}")
            return None

    async def get_margin_detail(
        self,
        trade_date: str = None,
        start_date: str = None,
        end_date: str = None,
        exchange_id: str = None
    ) -> Optional[pd.DataFrame]:
        """
        获取融资融券交易汇总（两融余额）

        Args:
            trade_date: 交易日期 (YYYYMMDD)
            start_date: 开始日期 (YYYYMMDD)
            end_date: 结束日期 (YYYYMMDD)
            exchange_id: 交易所代码 (SSE上交所, SZSE深交所)

        Returns:
            DataFrame 包含:
            - trade_date: 交易日期
            - exchange_id: 交易所
            - rzye: 融资余额（元）
            - rzmre: 融资买入额（元）
            - rzche: 融资偿还额（元）
            - rqye: 融券余额（元）
            - rqmcl: 融券卖出量
            - rzrqye: 融资融券余额（元）
        """
        if not self.is_available():
            return None

        try:
            params = {}
            if trade_date:
                params['trade_date'] = trade_date.replace('-', '')
            if start_date:
                params['start_date'] = start_date.replace('-', '')
            if end_date:
                params['end_date'] = end_date.replace('-', '')
            if exchange_id:
                params['exchange_id'] = exchange_id

            df = await asyncio.to_thread(
                self.api.margin,
                **params
            )

            if df is not None and not df.empty:
                self.logger.info(f"✅ 获取融资融券数据: {len(df)} 条")
                return df
            return None

        except Exception as e:
            self.logger.error(f"❌ 获取融资融券数据失败: {e}")
            return None

    async def get_limit_list(
        self,
        trade_date: str,
        limit_type: str = None
    ) -> Optional[pd.DataFrame]:
        """
        获取涨跌停统计

        Args:
            trade_date: 交易日期 (YYYYMMDD)
            limit_type: 涨跌停类型 (U涨停, D跌停, Z炸板)

        Returns:
            DataFrame 包含:
            - trade_date: 交易日期
            - ts_code: 股票代码
            - name: 股票名称
            - limit: 涨跌停类型 (U/D/Z)
            - pct_chg: 涨跌幅
            - close: 收盘价
            - open_times: 打开次数
            - up_stat: 连板统计
        """
        if not self.is_available():
            return None

        try:
            params = {
                'trade_date': trade_date.replace('-', '')
            }
            if limit_type:
                params['limit_type'] = limit_type

            df = await asyncio.to_thread(
                self.api.limit_list_d,
                **params
            )

            if df is not None and not df.empty:
                self.logger.info(f"✅ 获取涨跌停统计: {len(df)} 条")
                return df
            return None

        except Exception as e:
            self.logger.error(f"❌ 获取涨跌停统计失败: {e}")
            return None

    async def get_stk_limit(
        self,
        trade_date: str
    ) -> Optional[pd.DataFrame]:
        """
        获取每日涨跌停价格

        Args:
            trade_date: 交易日期 (YYYYMMDD)

        Returns:
            DataFrame 包含涨跌停价格信息
        """
        if not self.is_available():
            return None

        try:
            df = await asyncio.to_thread(
                self.api.stk_limit,
                trade_date=trade_date.replace('-', '')
            )

            if df is not None and not df.empty:
                self.logger.info(f"✅ 获取涨跌停价格: {len(df)} 条")
                return df
            return None

        except Exception as e:
            self.logger.error(f"❌ 获取涨跌停价格失败: {e}")
            return None

    async def get_daily_stats(
        self,
        trade_date: str
    ) -> Optional[Dict[str, Any]]:
        """
        获取每日市场统计（涨跌家数与涨跌幅分布）

        通过 daily 接口聚合计算

        Args:
            trade_date: 交易日期 (YYYYMMDD)

        Returns:
            包含涨跌家数统计的字典
        """
        if not self.is_available():
            return None

        try:
            trade_date_clean = trade_date.replace('-', '')

            # 获取当日所有股票的涨跌幅
            df = await asyncio.to_thread(
                self.api.daily,
                trade_date=trade_date_clean
            )

            if df is None or df.empty:
                return None

            # 统计涨跌家数
            total = len(df)
            up_count = len(df[df['pct_chg'] > 0])
            down_count = len(df[df['pct_chg'] < 0])
            flat_count = len(df[df['pct_chg'] == 0])

            # 涨幅分布
            up_gt5 = len(df[df['pct_chg'] >= 5])
            up_3_5 = len(df[(df['pct_chg'] >= 3) & (df['pct_chg'] < 5)])
            down_gt5 = len(df[df['pct_chg'] <= -5])
            down_3_5 = len(df[(df['pct_chg'] <= -3) & (df['pct_chg'] > -5)])

            stats = {
                'trade_date': trade_date_clean,
                'total': total,
                'up_count': up_count,
                'down_count': down_count,
                'flat_count': flat_count,
                'up_ratio': up_count / total * 100 if total > 0 else 0,
                'down_ratio': down_count / total * 100 if total > 0 else 0,
                'up_gt5': up_gt5,
                'up_3_5': up_3_5,
                'down_gt5': down_gt5,
                'down_3_5': down_3_5,
            }

            self.logger.info(f"✅ 获取每日市场统计: 涨{up_count}/跌{down_count}/平{flat_count}")
            return stats

        except Exception as e:
            self.logger.error(f"❌ 获取每日市场统计失败: {e}")
            return None

    async def get_pledge_detail(
        self,
        ts_code: str = None,
        ann_date: str = None,
        start_date: str = None,
        end_date: str = None,
    ) -> Optional[pd.DataFrame]:
        """
        获取股权质押明细

        Args:
            ts_code: 股票代码（TS格式，如 600519.SH）
            ann_date: 公告日期 (YYYYMMDD)
            start_date: 公告开始日期 (YYYYMMDD)
            end_date: 公告结束日期 (YYYYMMDD)

        Returns:
            DataFrame 包含:
            - ts_code: TS股票代码
            - ann_date: 公告日期
            - holder_name: 股东名称
            - pledge_amount: 质押数量（万股）
            - start_date: 质押开始日期
            - end_date: 质押结束日期
            - is_release: 是否已解押
            - release_date: 解押日期
            - pledgor: 质押方
            - holding_amount: 持股总数（万股）
            - pledged_amount: 质押总数（万股）
            - p_total_ratio: 本次质押占总股本比例
            - h_total_ratio: 持股总数占总股本比例
            - is_buyback: 是否回购（0否 1是）
        """
        if not self.is_available():
            return None

        try:
            params = {}
            if ts_code:
                params['ts_code'] = ts_code
            if ann_date:
                params['ann_date'] = ann_date.replace('-', '')
            if start_date:
                params['start_date'] = start_date.replace('-', '')
            if end_date:
                params['end_date'] = end_date.replace('-', '')

            df = await asyncio.to_thread(
                self.api.pledge_detail,
                **params
            )

            if df is not None and not df.empty:
                self.logger.info(f"✅ 获取股权质押明细: {len(df)} 条 | ts_code={ts_code or 'all'}")
                return df
            return None

        except Exception as e:
            self.logger.error(f"❌ 获取股权质押明细失败: {e}")
            return None


    async def get_audit_opinion(
        self,
        ts_code: str = None,
        ann_date: str = None,
        start_date: str = None,
        end_date: str = None,
        period: str = None,
    ) -> Optional[pd.DataFrame]:
        """
        获取A股公司审计意见（stk_audit）

        Args:
            ts_code: 股票代码（TS格式，如 600519.SH）
            ann_date: 公告日期 (YYYYMMDD)
            start_date: 公告开始日期 (YYYYMMDD)
            end_date: 公告结束日期 (YYYYMMDD)
            period: 报告期 (YYYYMMDD)

        Returns:
            DataFrame 包含:
            - ts_code: TS股票代码
            - ann_date: 公告日期
            - end_date: 报告期截止日
            - audit_result: 审计结果
            - audit_fees: 审计总费用（元）
            - audit_sign: 审计师
            - audit_company: 审计机构
        """
        if not self.is_available():
            return None

        try:
            params = {}
            if ts_code:
                params['ts_code'] = ts_code
            if ann_date:
                params['ann_date'] = ann_date.replace('-', '')
            if start_date:
                params['start_date'] = start_date.replace('-', '')
            if end_date:
                params['end_date'] = end_date.replace('-', '')
            if period:
                params['period'] = period.replace('-', '')

            df = await asyncio.to_thread(
                self.api.stk_audit,
                **params
            )

            if df is not None and not df.empty:
                self.logger.info(f"✅ 获取审计意见: {len(df)} 条 | ts_code={ts_code or 'all'}")
                return df
            return None

        except Exception as e:
            self.logger.error(f"❌ 获取审计意见失败: {e}")
            return None

    async def get_disclosure_rating(
        self,
        ts_code: str = None,
        end_date: str = None,
    ) -> Optional[pd.DataFrame]:
        """
        获取交易所信息披露考评结果（disclosure_rating）

        Args:
            ts_code: 股票代码（TS格式，如 600519.SH）
            end_date: 报告期 (YYYYMMDD)

        Returns:
            DataFrame 包含:
            - ts_code: TS股票代码
            - end_date: 考评年度
            - disclosure_result: 考评结果（A/B/C/D）
        """
        if not self.is_available():
            return None

        try:
            params = {}
            if ts_code:
                params['ts_code'] = ts_code
            if end_date:
                params['end_date'] = end_date.replace('-', '')

            df = await asyncio.to_thread(
                self.api.disclosure_rating,
                **params
            )

            if df is not None and not df.empty:
                self.logger.info(f"✅ 获取信息披露评级: {len(df)} 条 | ts_code={ts_code or 'all'}")
                return df
            return None

        except Exception as e:
            self.logger.error(f"❌ 获取信息披露评级失败: {e}")
            return None

    async def get_equity_incentive(
        self,
        ts_code: str = None,
        ann_date: str = None,
        start_date: str = None,
        end_date: str = None,
    ) -> Optional[pd.DataFrame]:
        """
        获取股权激励计划明细（equity_incentive）

        Args:
            ts_code: 股票代码（TS格式，如 600519.SH）
            ann_date: 公告日期 (YYYYMMDD)
            start_date: 公告开始日期 (YYYYMMDD)
            end_date: 公告结束日期 (YYYYMMDD)

        Returns:
            DataFrame 包含:
            - ts_code: TS股票代码
            - ann_date: 公告日期
            - inc_plan: 激励方案
            - grant_num: 授予数量（万股）
            - grant_price: 授予价格
            - inc_duration: 激励年限（年）
            - inc_perf: 行权条件/业绩要求
            - stockholder_rt: 总股本占比
        """
        if not self.is_available():
            return None

        try:
            params = {}
            if ts_code:
                params['ts_code'] = ts_code
            if ann_date:
                params['ann_date'] = ann_date.replace('-', '')
            if start_date:
                params['start_date'] = start_date.replace('-', '')
            if end_date:
                params['end_date'] = end_date.replace('-', '')

            df = await asyncio.to_thread(
                self.api.equity_incentive,
                **params
            )

            if df is not None and not df.empty:
                self.logger.info(f"✅ 获取股权激励: {len(df)} 条 | ts_code={ts_code or 'all'}")
                return df
            return None

        except Exception as e:
            self.logger.error(f"❌ 获取股权激励失败: {e}")
            return None

    async def get_management_penalties(
        self,
        ts_code: str = None,
        ann_date: str = None,
        start_date: str = None,
        end_date: str = None,
    ) -> Optional[pd.DataFrame]:
        """
        获取违规处罚记录（stk_penalty）

        Args:
            ts_code: 股票代码（TS格式，如 600519.SH）
            ann_date: 公告日期 (YYYYMMDD)
            start_date: 公告开始日期 (YYYYMMDD)
            end_date: 公告结束日期 (YYYYMMDD)

        Returns:
            DataFrame 包含:
            - ts_code: TS股票代码
            - ann_date: 公告日期
            - punish_type: 处罚类型（警告/罚款/市场禁入等）
            - punish_object: 处罚对象（公司/个人）
            - punish_amount: 处罚金额（万元）
            - violat_type: 违规类型
            - violate_content: 违规事由
        """
        if not self.is_available():
            return None

        try:
            params = {}
            if ts_code:
                params['ts_code'] = ts_code
            if ann_date:
                params['ann_date'] = ann_date.replace('-', '')
            if start_date:
                params['start_date'] = start_date.replace('-', '')
            if end_date:
                params['end_date'] = end_date.replace('-', '')

            df = await asyncio.to_thread(
                self.api.stk_penalty,
                **params
            )

            if df is not None and not df.empty:
                self.logger.info(f"✅ 获取违规处罚: {len(df)} 条 | ts_code={ts_code or 'all'}")
                return df
            return None

        except Exception as e:
            self.logger.error(f"❌ 获取违规处罚失败: {e}")
            return None


# 全局提供器实例
_tushare_provider = None
_tushare_provider_initialized = False

def get_tushare_provider() -> TushareProvider:
    """获取全局 Tushare API Client 提供器实例。"""
    global _tushare_provider, _tushare_provider_initialized
    if _tushare_provider is None:
        _tushare_provider = TushareProvider()

    _tushare_provider_initialized = _tushare_provider.is_available()
    return _tushare_provider
