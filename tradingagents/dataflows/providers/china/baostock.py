#!/usr/bin/env python3
"""
BaoStock统一数据提供器
实现BaseStockDataProvider接口，提供标准化的BaoStock数据访问
"""
import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, List, Optional, Union
import pandas as pd

from ..base_provider import BaseStockDataProvider

logger = logging.getLogger(__name__)


class BaoStockProvider(BaseStockDataProvider):
    """BaoStock统一数据提供器"""
    
    def __init__(self):
        """初始化BaoStock提供器"""
        super().__init__("baostock")
        self.bs = None
        self.connected = False
        self._init_baostock()
    
    def _init_baostock(self):
        """初始化BaoStock连接"""
        try:
            import baostock as bs
            self.bs = bs
            logger.info("🔧 BaoStock模块加载成功")
            self.connected = True
        except ImportError as e:
            logger.error(f"❌ BaoStock模块未安装: {e}")
            self.connected = False
        except Exception as e:
            logger.error(f"❌ BaoStock初始化失败: {e}")
            self.connected = False
    
    async def connect(self) -> bool:
        """连接到BaoStock数据源"""
        return await self.test_connection()

    async def test_connection(self) -> bool:
        """测试BaoStock连接"""
        if not self.connected or not self.bs:
            return False
        
        try:
            # 异步测试登录
            def test_login():
                lg = self.bs.login()
                if lg.error_code != '0':
                    raise Exception(f"登录失败: {lg.error_msg}")
                self.bs.logout()
                return True
            
            await asyncio.to_thread(test_login)
            logger.info("✅ BaoStock连接测试成功")
            return True
        except Exception as e:
            logger.error(f"❌ BaoStock连接测试失败: {e}")
            return False
    
    def get_stock_list_sync(self) -> Optional[pd.DataFrame]:
        """获取股票列表（同步版本）"""
        if not self.connected:
            return None

        try:
            logger.info("📋 获取BaoStock股票列表（同步）...")

            lg = self.bs.login()
            if lg.error_code != '0':
                logger.error(f"BaoStock登录失败: {lg.error_msg}")
                return None

            try:
                rs = self.bs.query_stock_basic()
                if rs.error_code != '0':
                    logger.error(f"BaoStock查询失败: {rs.error_msg}")
                    return None

                data_list = []
                while (rs.error_code == '0') & rs.next():
                    data_list.append(rs.get_row_data())

                if not data_list:
                    logger.warning("⚠️ BaoStock股票列表为空")
                    return None

                # 转换为DataFrame
                import pandas as pd
                df = pd.DataFrame(data_list, columns=rs.fields)

                # 只保留股票类型（type=1）
                df = df[df['type'] == '1']

                logger.info(f"✅ BaoStock股票列表获取成功: {len(df)}只股票")
                return df

            finally:
                self.bs.logout()

        except Exception as e:
            logger.error(f"❌ BaoStock获取股票列表失败: {e}")
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
            logger.info("📋 获取BaoStock股票列表...")
            
            def fetch_stock_list():
                lg = self.bs.login()
                if lg.error_code != '0':
                    raise Exception(f"登录失败: {lg.error_msg}")
                
                try:
                    rs = self.bs.query_stock_basic()
                    if rs.error_code != '0':
                        raise Exception(f"查询失败: {rs.error_msg}")
                    
                    data_list = []
                    while (rs.error_code == '0') & rs.next():
                        data_list.append(rs.get_row_data())
                    
                    return data_list, rs.fields
                finally:
                    self.bs.logout()
            
            data_list, fields = await asyncio.to_thread(fetch_stock_list)
            
            if not data_list:
                logger.warning("⚠️ BaoStock股票列表为空")
                return []
            
            # 转换为标准格式
            stock_list = []
            for row in data_list:
                if len(row) >= 6:
                    code = row[0]  # code
                    name = row[1]  # code_name
                    stock_type = row[4] if len(row) > 4 else '0'  # type
                    status = row[5] if len(row) > 5 else '0'  # status
                    
                    # 只保留A股股票 (type=1, status=1)
                    if stock_type == '1' and status == '1':
                        # 转换代码格式 sh.600000 -> 600000
                        clean_code = code.replace('sh.', '').replace('sz.', '')
                        stock_list.append({
                            "code": clean_code,
                            "name": str(name),
                            "source": "baostock"
                        })
            
            logger.info(f"✅ BaoStock股票列表获取成功: {len(stock_list)}只股票")
            return stock_list
            
        except Exception as e:
            logger.error(f"❌ BaoStock获取股票列表失败: {e}")
            return []
    
    async def get_stock_basic_info(self, code: str) -> Dict[str, Any]:
        """
        获取股票基础信息

        Args:
            code: 股票代码

        Returns:
            标准化的股票基础信息
        """
        if not self.connected:
            return {}

        try:
            # 获取详细信息
            basic_info = await self._get_stock_info_detail(code)

            # 标准化数据
            return {
                "code": code,
                "name": basic_info.get("name", f"股票{code}"),
                "industry": basic_info.get("industry", "未知"),
                "area": basic_info.get("area", "未知"),
                "list_date": basic_info.get("list_date", ""),
                "full_symbol": self._get_full_symbol(code),
                "market_info": self._get_market_info(code),
                "data_source": "baostock",
                "last_sync": datetime.now(timezone.utc),
                "sync_status": "success"
            }

        except Exception as e:
            logger.error(f"❌ BaoStock获取{code}基础信息失败: {e}")
            return {}

    async def get_valuation_data(self, code: str, trade_date: Optional[str] = None) -> Dict[str, Any]:
        """
        获取股票估值数据（PE、PB、PS、PCF等）

        Args:
            code: 股票代码
            trade_date: 交易日期 (YYYY-MM-DD)，默认为最近交易日

        Returns:
            估值数据字典，包含 pe_ttm, pb_mrq, ps_ttm, pcf_ttm, close, total_shares 等
        """
        if not self.connected:
            return {}

        try:
            # 如果没有指定日期，使用最近5天（确保能获取到最新交易日数据）
            if not trade_date:
                end_date = datetime.now().strftime('%Y-%m-%d')
                start_date = (datetime.now() - timedelta(days=5)).strftime('%Y-%m-%d')
            else:
                start_date = trade_date
                end_date = trade_date

            logger.debug(f"📊 获取{code}估值数据: {start_date} 到 {end_date}")

            def fetch_valuation_data():
                bs_code = self._to_baostock_code(code)
                lg = self.bs.login()
                if lg.error_code != '0':
                    raise Exception(f"登录失败: {lg.error_msg}")

                try:
                    # 🔥 获取估值指标：peTTM, pbMRQ, psTTM, pcfNcfTTM
                    rs = self.bs.query_history_k_data_plus(
                        code=bs_code,
                        fields="date,code,close,peTTM,pbMRQ,psTTM,pcfNcfTTM",
                        start_date=start_date,
                        end_date=end_date,
                        frequency="d",
                        adjustflag="3"  # 不复权
                    )

                    if rs.error_code != '0':
                        raise Exception(f"查询失败: {rs.error_msg}")

                    data_list = []
                    while (rs.error_code == '0') & rs.next():
                        data_list.append(rs.get_row_data())

                    return data_list, rs.fields
                finally:
                    self.bs.logout()

            data_list, fields = await asyncio.to_thread(fetch_valuation_data)

            if not data_list:
                logger.warning(f"⚠️ {code}估值数据为空")
                return {}

            # 取最新一条数据
            latest_row = data_list[-1]

            # 解析数据（fields: date, code, close, peTTM, pbMRQ, psTTM, pcfNcfTTM）
            valuation_data = {
                "date": latest_row[0] if len(latest_row) > 0 else None,
                "code": code,
                "close": self._safe_float(latest_row[2]) if len(latest_row) > 2 else None,
                "pe_ttm": self._safe_float(latest_row[3]) if len(latest_row) > 3 else None,
                "pb_mrq": self._safe_float(latest_row[4]) if len(latest_row) > 4 else None,
                "ps_ttm": self._safe_float(latest_row[5]) if len(latest_row) > 5 else None,
                "pcf_ttm": self._safe_float(latest_row[6]) if len(latest_row) > 6 else None,
            }

            logger.debug(f"✅ {code}估值数据获取成功: PE={valuation_data['pe_ttm']}, PB={valuation_data['pb_mrq']}")
            return valuation_data

        except Exception as e:
            logger.error(f"❌ BaoStock获取{code}估值数据失败: {e}")
            return {}
    
    async def _get_stock_info_detail(self, code: str) -> Dict[str, Any]:
        """获取股票详细信息"""
        try:
            def fetch_stock_info():
                bs_code = self._to_baostock_code(code)
                lg = self.bs.login()
                if lg.error_code != '0':
                    raise Exception(f"登录失败: {lg.error_msg}")
                
                try:
                    rs = self.bs.query_stock_basic(code=bs_code)
                    if rs.error_code != '0':
                        return {"code": code, "name": f"股票{code}"}
                    
                    data_list = []
                    while (rs.error_code == '0') & rs.next():
                        data_list.append(rs.get_row_data())
                    
                    if not data_list:
                        return {"code": code, "name": f"股票{code}"}
                    
                    row = data_list[0]
                    return {
                        "code": code,
                        "name": str(row[1]) if len(row) > 1 else f"股票{code}",  # code_name
                        "list_date": str(row[2]) if len(row) > 2 else "",  # ipoDate
                        "industry": "未知",  # BaoStock基础信息不包含行业
                        "area": "未知"  # BaoStock基础信息不包含地区
                    }
                finally:
                    self.bs.logout()
            
            return await asyncio.to_thread(fetch_stock_info)
            
        except Exception as e:
            logger.debug(f"获取{code}详细信息失败: {e}")
            return {"code": code, "name": f"股票{code}", "industry": "未知", "area": "未知"}
    
    async def get_stock_quotes(self, code: str) -> Dict[str, Any]:
        """
        获取股票实时行情
        
        Args:
            code: 股票代码
            
        Returns:
            标准化的行情数据
        """
        if not self.connected:
            return {}
        
        try:
            # BaoStock没有实时行情接口，使用最新日K线数据
            quotes_data = await self._get_latest_kline_data(code)
            
            if not quotes_data:
                return {}
            
            # 标准化数据
            return {
                "code": code,
                "name": quotes_data.get("name", f"股票{code}"),
                "price": quotes_data.get("close", 0),
                "change": quotes_data.get("change", 0),
                "change_percent": quotes_data.get("change_percent", 0),
                "volume": quotes_data.get("volume", 0),
                "amount": quotes_data.get("amount", 0),
                "open": quotes_data.get("open", 0),
                "high": quotes_data.get("high", 0),
                "low": quotes_data.get("low", 0),
                "pre_close": quotes_data.get("preclose", 0),
                "full_symbol": self._get_full_symbol(code),
                "market_info": self._get_market_info(code),
                "data_source": "baostock",
                "last_sync": datetime.now(timezone.utc),
                "sync_status": "success"
            }
            
        except Exception as e:
            logger.error(f"❌ BaoStock获取{code}行情失败: {e}")
            return {}
    
    async def _get_latest_kline_data(self, code: str) -> Dict[str, Any]:
        """获取最新K线数据作为行情"""
        try:
            def fetch_latest_kline():
                bs_code = self._to_baostock_code(code)
                lg = self.bs.login()
                if lg.error_code != '0':
                    raise Exception(f"登录失败: {lg.error_msg}")
                
                try:
                    # 获取最近5天的数据
                    end_date = datetime.now().strftime('%Y-%m-%d')
                    start_date = (datetime.now() - timedelta(days=5)).strftime('%Y-%m-%d')
                    
                    rs = self.bs.query_history_k_data_plus(
                        code=bs_code,
                        fields="date,code,open,high,low,close,preclose,volume,amount,pctChg",
                        start_date=start_date,
                        end_date=end_date,
                        frequency="d",
                        adjustflag="3"
                    )
                    
                    if rs.error_code != '0':
                        return {}
                    
                    data_list = []
                    while (rs.error_code == '0') & rs.next():
                        data_list.append(rs.get_row_data())
                    
                    if not data_list:
                        return {}
                    
                    # 取最新一条数据
                    latest_row = data_list[-1]
                    return {
                        "name": f"股票{code}",
                        "open": self._safe_float(latest_row[2]),
                        "high": self._safe_float(latest_row[3]),
                        "low": self._safe_float(latest_row[4]),
                        "close": self._safe_float(latest_row[5]),
                        "preclose": self._safe_float(latest_row[6]),
                        "volume": self._safe_int(latest_row[7]),
                        "amount": self._safe_float(latest_row[8]),
                        "change_percent": self._safe_float(latest_row[9]),
                        "change": self._safe_float(latest_row[5]) - self._safe_float(latest_row[6])
                    }
                finally:
                    self.bs.logout()
            
            return await asyncio.to_thread(fetch_latest_kline)
            
        except Exception as e:
            logger.debug(f"获取{code}最新K线数据失败: {e}")
            return {}
    
    def _to_baostock_code(self, symbol: str) -> str:
        """转换为BaoStock代码格式"""
        s = str(symbol).strip().upper()
        # 处理 600519.SH / 000001.SZ / 600519 / 000001
        if s.endswith('.SH') or s.endswith('.SZ'):
            code, exch = s.split('.')
            prefix = 'sh' if exch == 'SH' else 'sz'
            return f"{prefix}.{code}"
        # 6 开头上交所，否则深交所（简化规则）
        if len(s) >= 6 and s[0] == '6':
            return f"sh.{s[:6]}"
        return f"sz.{s[:6]}"
    
    def _determine_market(self, code: str) -> str:
        """确定股票所属市场"""
        if code.startswith('6'):
            return "上海证券交易所"
        elif code.startswith('0') or code.startswith('3'):
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
        if code.startswith(('6', '9')):  # 上海证券交易所（增加9开头的B股）
            return f"{code}.SS"
        elif code.startswith(('0', '3', '2')):  # 深圳证券交易所（增加2开头的B股）
            return f"{code}.SZ"
        elif code.startswith(('8', '4')):  # 北京证券交易所（增加4开头的新三板）
            return f"{code}.BJ"
        else:
            # 无法识别的代码，返回原始代码（确保不为空）
            return code if code else ""
    
    def _get_market_info(self, code: str) -> Dict[str, Any]:
        """获取市场信息"""
        if code.startswith('6'):
            return {
                "market_type": "CN",
                "exchange": "SSE",
                "exchange_name": "上海证券交易所",
                "currency": "CNY",
                "timezone": "Asia/Shanghai"
            }
        elif code.startswith('0') or code.startswith('3'):
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
    
    def _safe_float(self, value: Any) -> float:
        """安全转换为浮点数"""
        try:
            if value is None or value == '' or value == 'None':
                return 0.0
            return float(value)
        except (ValueError, TypeError):
            return 0.0
    
    def _safe_int(self, value: Any) -> int:
        """安全转换为整数"""
        try:
            if value is None or value == '' or value == 'None':
                return 0
            return int(float(value))
        except (ValueError, TypeError):
            return 0
    
    def _safe_str(self, value: Any) -> str:
        """安全转换为字符串"""
        try:
            if value is None:
                return ""
            return str(value)
        except:
            return ""

    async def get_historical_data(self, code: str, start_date: str, end_date: str,
                                period: str = "daily") -> Optional[pd.DataFrame]:
        """
        获取历史数据

        Args:
            code: 股票代码
            start_date: 开始日期 (YYYY-MM-DD)
            end_date: 结束日期 (YYYY-MM-DD)
            period: 数据周期 (daily, weekly, monthly)

        Returns:
            历史数据DataFrame
        """
        if not self.connected:
            return None

        try:
            logger.info(f"📊 获取BaoStock历史数据: {code} ({start_date} 到 {end_date})")

            # 转换周期参数
            frequency_map = {
                "daily": "d",
                "weekly": "w",
                "monthly": "m"
            }
            bs_frequency = frequency_map.get(period, "d")

            def fetch_historical_data():
                bs_code = self._to_baostock_code(code)
                lg = self.bs.login()
                if lg.error_code != '0':
                    raise Exception(f"登录失败: {lg.error_msg}")

                try:
                    # 根据频率选择不同的字段（周线和月线支持的字段较少）
                    if bs_frequency == "d":
                        fields_str = "date,code,open,high,low,close,preclose,volume,amount,adjustflag,turn,tradestatus,pctChg,peTTM,pbMRQ,psTTM,pcfNcfTTM,isST"
                    else:
                        # 周线和月线只支持基础字段
                        fields_str = "date,code,open,high,low,close,volume,amount,pctChg"

                    rs = self.bs.query_history_k_data_plus(
                        code=bs_code,
                        fields=fields_str,
                        start_date=start_date,
                        end_date=end_date,
                        frequency=bs_frequency,
                        adjustflag="2"  # 前复权
                    )

                    if rs.error_code != '0':
                        raise Exception(f"查询失败: {rs.error_msg}")

                    data_list = []
                    while (rs.error_code == '0') & rs.next():
                        data_list.append(rs.get_row_data())

                    return data_list, rs.fields
                finally:
                    self.bs.logout()

            data_list, fields = await asyncio.to_thread(fetch_historical_data)

            if not data_list:
                logger.warning(f"⚠️ BaoStock历史数据为空: {code}")
                return None

            # 转换为DataFrame
            df = pd.DataFrame(data_list, columns=fields)

            # 数据类型转换
            numeric_cols = [
                'open', 'high', 'low', 'close', 'preclose', 'volume', 'amount',
                'pctChg', 'turn', 'peTTM', 'pbMRQ', 'psTTM', 'pcfNcfTTM'
            ]
            for col in numeric_cols:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce')

            # 如果没有preclose字段，使用前一日收盘价估算
            if 'preclose' not in df.columns and len(df) > 0:
                df['preclose'] = df['close'].shift(1)
                df.loc[0, 'preclose'] = df.loc[0, 'close']  # 第一行使用当日收盘价

            # 标准化列名
            df = df.rename(columns={
                'pctChg': 'change_percent',
                'peTTM': 'pe',
                'pbMRQ': 'pb',
                'psTTM': 'ps',
                'pcfNcfTTM': 'pcf_ttm',
            })

            # 添加标准化字段
            df['股票代码'] = code
            df['full_symbol'] = self._get_full_symbol(code)

            logger.info(f"✅ BaoStock历史数据获取成功: {code}, {len(df)}条记录")
            return df

        except Exception as e:
            logger.error(f"❌ BaoStock获取{code}历史数据失败: {e}")
            return None

    async def get_financial_data(self, code: str, year: Optional[int] = None,
                               quarter: Optional[int] = None) -> Dict[str, Any]:
        """
        获取财务数据

        Args:
            code: 股票代码
            year: 年份
            quarter: 季度

        Returns:
            财务数据字典
        """
        if not self.connected:
            return {}

        try:
            logger.info(f"💰 获取BaoStock财务数据: {code}")

            # 如果没有指定年份和季度，使用当前年份的最新季度
            if year is None:
                year = datetime.now().year
            if quarter is None:
                current_month = datetime.now().month
                quarter = (current_month - 1) // 3 + 1

            financial_data = {}

            # 1. 获取盈利能力数据
            try:
                profit_data = await self._get_profit_data(code, year, quarter)
                if profit_data:
                    financial_data['profit_data'] = profit_data
                    logger.debug(f"✅ {code}盈利能力数据获取成功")
            except Exception as e:
                logger.debug(f"获取{code}盈利能力数据失败: {e}")

            # 2. 获取营运能力数据
            try:
                operation_data = await self._get_operation_data(code, year, quarter)
                if operation_data:
                    financial_data['operation_data'] = operation_data
                    logger.debug(f"✅ {code}营运能力数据获取成功")
            except Exception as e:
                logger.debug(f"获取{code}营运能力数据失败: {e}")

            # 3. 获取成长能力数据
            try:
                growth_data = await self._get_growth_data(code, year, quarter)
                if growth_data:
                    financial_data['growth_data'] = growth_data
                    logger.debug(f"✅ {code}成长能力数据获取成功")
            except Exception as e:
                logger.debug(f"获取{code}成长能力数据失败: {e}")

            # 4. 获取偿债能力数据
            try:
                balance_data = await self._get_balance_data(code, year, quarter)
                if balance_data:
                    financial_data['balance_data'] = balance_data
                    logger.debug(f"✅ {code}偿债能力数据获取成功")
            except Exception as e:
                logger.debug(f"获取{code}偿债能力数据失败: {e}")

            # 5. 获取现金流量数据
            try:
                cash_flow_data = await self._get_cash_flow_data(code, year, quarter)
                if cash_flow_data:
                    financial_data['cash_flow_data'] = cash_flow_data
                    logger.debug(f"✅ {code}现金流量数据获取成功")
            except Exception as e:
                logger.debug(f"获取{code}现金流量数据失败: {e}")

            if financial_data:
                logger.info(f"✅ BaoStock财务数据获取成功: {code}, {len(financial_data)}个数据集")
            else:
                logger.warning(f"⚠️ BaoStock财务数据为空: {code}")

            return financial_data

        except Exception as e:
            logger.error(f"❌ BaoStock获取{code}财务数据失败: {e}")
            return {}

    async def _get_profit_data(self, code: str, year: int, quarter: int) -> Optional[Dict[str, Any]]:
        """获取盈利能力数据"""
        try:
            def fetch_profit_data():
                bs_code = self._to_baostock_code(code)
                lg = self.bs.login()
                if lg.error_code != '0':
                    raise Exception(f"登录失败: {lg.error_msg}")

                try:
                    rs = self.bs.query_profit_data(code=bs_code, year=year, quarter=quarter)
                    if rs.error_code != '0':
                        return None

                    data_list = []
                    while (rs.error_code == '0') & rs.next():
                        data_list.append(rs.get_row_data())

                    return data_list, rs.fields
                finally:
                    self.bs.logout()

            result = await asyncio.to_thread(fetch_profit_data)
            if not result or not result[0]:
                return None

            data_list, fields = result
            df = pd.DataFrame(data_list, columns=fields)
            return df.to_dict('records')[0] if not df.empty else None

        except Exception as e:
            logger.debug(f"获取{code}盈利能力数据失败: {e}")
            return None

    async def _get_operation_data(self, code: str, year: int, quarter: int) -> Optional[Dict[str, Any]]:
        """获取营运能力数据"""
        try:
            def fetch_operation_data():
                bs_code = self._to_baostock_code(code)
                lg = self.bs.login()
                if lg.error_code != '0':
                    raise Exception(f"登录失败: {lg.error_msg}")

                try:
                    rs = self.bs.query_operation_data(code=bs_code, year=year, quarter=quarter)
                    if rs.error_code != '0':
                        return None

                    data_list = []
                    while (rs.error_code == '0') & rs.next():
                        data_list.append(rs.get_row_data())

                    return data_list, rs.fields
                finally:
                    self.bs.logout()

            result = await asyncio.to_thread(fetch_operation_data)
            if not result or not result[0]:
                return None

            data_list, fields = result
            df = pd.DataFrame(data_list, columns=fields)
            return df.to_dict('records')[0] if not df.empty else None

        except Exception as e:
            logger.debug(f"获取{code}营运能力数据失败: {e}")
            return None

    async def _get_growth_data(self, code: str, year: int, quarter: int) -> Optional[Dict[str, Any]]:
        """获取成长能力数据"""
        try:
            def fetch_growth_data():
                bs_code = self._to_baostock_code(code)
                lg = self.bs.login()
                if lg.error_code != '0':
                    raise Exception(f"登录失败: {lg.error_msg}")

                try:
                    rs = self.bs.query_growth_data(code=bs_code, year=year, quarter=quarter)
                    if rs.error_code != '0':
                        return None

                    data_list = []
                    while (rs.error_code == '0') & rs.next():
                        data_list.append(rs.get_row_data())

                    return data_list, rs.fields
                finally:
                    self.bs.logout()

            result = await asyncio.to_thread(fetch_growth_data)
            if not result or not result[0]:
                return None

            data_list, fields = result
            df = pd.DataFrame(data_list, columns=fields)
            return df.to_dict('records')[0] if not df.empty else None

        except Exception as e:
            logger.debug(f"获取{code}成长能力数据失败: {e}")
            return None

    async def _get_balance_data(self, code: str, year: int, quarter: int) -> Optional[Dict[str, Any]]:
        """获取偿债能力数据"""
        try:
            def fetch_balance_data():
                bs_code = self._to_baostock_code(code)
                lg = self.bs.login()
                if lg.error_code != '0':
                    raise Exception(f"登录失败: {lg.error_msg}")

                try:
                    rs = self.bs.query_balance_data(code=bs_code, year=year, quarter=quarter)
                    if rs.error_code != '0':
                        return None

                    data_list = []
                    while (rs.error_code == '0') & rs.next():
                        data_list.append(rs.get_row_data())

                    return data_list, rs.fields
                finally:
                    self.bs.logout()

            result = await asyncio.to_thread(fetch_balance_data)
            if not result or not result[0]:
                return None

            data_list, fields = result
            df = pd.DataFrame(data_list, columns=fields)
            return df.to_dict('records')[0] if not df.empty else None

        except Exception as e:
            logger.debug(f"获取{code}偿债能力数据失败: {e}")
            return None

    async def _get_cash_flow_data(self, code: str, year: int, quarter: int) -> Optional[Dict[str, Any]]:
        """获取现金流量数据"""
        try:
            def fetch_cash_flow_data():
                bs_code = self._to_baostock_code(code)
                lg = self.bs.login()
                if lg.error_code != '0':
                    raise Exception(f"登录失败: {lg.error_msg}")

                try:
                    rs = self.bs.query_cash_flow_data(code=bs_code, year=year, quarter=quarter)
                    if rs.error_code != '0':
                        return None

                    data_list = []
                    while (rs.error_code == '0') & rs.next():
                        data_list.append(rs.get_row_data())

                    return data_list, rs.fields
                finally:
                    self.bs.logout()

            result = await asyncio.to_thread(fetch_cash_flow_data)
            if not result or not result[0]:
                return None

            data_list, fields = result
            df = pd.DataFrame(data_list, columns=fields)
            return df.to_dict('records')[0] if not df.empty else None

        except Exception as e:
            logger.debug(f"获取{code}现金流量数据失败: {e}")
            return None


# 全局提供器实例
_baostock_provider = None


def get_baostock_provider() -> BaoStockProvider:
    """获取全局BaoStock提供器实例"""
    global _baostock_provider
    if _baostock_provider is None:
        _baostock_provider = BaoStockProvider()
    return _baostock_provider
