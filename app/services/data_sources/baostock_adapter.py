"""
BaoStock data source adapter
"""
from typing import Optional
import logging
from datetime import datetime, timedelta
import pandas as pd

from .base import DataSourceAdapter

logger = logging.getLogger(__name__)


class BaoStockAdapter(DataSourceAdapter):
    """BaoStockdata source adapter"""

    def __init__(self):
        super().__init__()  # 调用父类初始化

    @property
    def name(self) -> str:
        return "baostock"

    def _get_default_priority(self) -> int:
        return 1  # lowest priority (数字越大优先级越高)

    def is_available(self) -> bool:
        try:
            import baostock as bs  # noqa: F401
            return True
        except ImportError:
            return False

    def get_stock_list(self) -> Optional[pd.DataFrame]:
        if not self.is_available():
            return None
        try:
            import baostock as bs
            lg = bs.login()
            if lg.error_code != '0':
                logger.error(f"BaoStock: Login failed: {lg.error_msg}")
                return None
            try:
                logger.info("BaoStock: Querying stock basic info...")
                rs = bs.query_stock_basic()
                if rs.error_code != '0':
                    logger.error(f"BaoStock: Query failed: {rs.error_msg}")
                    return None
                data_list = []
                while (rs.error_code == '0') & rs.next():
                    data_list.append(rs.get_row_data())
                if not data_list:
                    return None
                df = pd.DataFrame(data_list, columns=rs.fields)
                df = df[df['type'] == '1']
                df['symbol'] = df['code'].str.replace(r'^(sh|sz)\.', '', regex=True)
                df['ts_code'] = (
                    df['code'].str.replace('sh.', '').str.replace('sz.', '')
                    + df['code'].str.extract(r'^(sh|sz)\.').iloc[:, 0].str.upper().str.replace('SH', '.SH').str.replace('SZ', '.SZ')
                )
                df['name'] = df['code_name']
                df['area'] = ''

                # 获取行业信息
                logger.info("BaoStock: Querying stock industry info...")
                industry_rs = bs.query_stock_industry()
                if industry_rs.error_code == '0':
                    industry_list = []
                    while (industry_rs.error_code == '0') & industry_rs.next():
                        industry_list.append(industry_rs.get_row_data())
                    if industry_list:
                        industry_df = pd.DataFrame(industry_list, columns=industry_rs.fields)

                        # 去掉行业编码前缀（如 "I65软件和信息技术服务业" -> "软件和信息技术服务业"）
                        def clean_industry_name(industry_str):
                            if not industry_str or pd.isna(industry_str):
                                return ''
                            # 使用正则表达式去掉前面的字母和数字编码（如 I65、C31 等）
                            import re
                            cleaned = re.sub(r'^[A-Z]\d+', '', str(industry_str))
                            return cleaned.strip()

                        industry_df['industry_clean'] = industry_df['industry'].apply(clean_industry_name)

                        # 创建行业映射字典 {code: industry_clean}
                        industry_map = dict(zip(industry_df['code'], industry_df['industry_clean']))
                        # 将行业信息合并到主DataFrame
                        df['industry'] = df['code'].map(industry_map).fillna('')
                        logger.info(f"BaoStock: Successfully mapped industry info for {len(industry_map)} stocks")
                    else:
                        df['industry'] = ''
                        logger.warning("BaoStock: No industry data returned")
                else:
                    df['industry'] = ''
                    logger.warning(f"BaoStock: Failed to query industry info: {industry_rs.error_msg}")

                df['market'] = '\u4e3b\u677f'
                df['list_date'] = ''
                logger.info(f"BaoStock: Successfully fetched {len(df)} stocks")
                return df[['symbol', 'name', 'ts_code', 'area', 'industry', 'market', 'list_date']]
            finally:
                bs.logout()
        except Exception as e:
            logger.error(f"BaoStock: Failed to fetch stock list: {e}")
            return None

    def get_daily_basic(self, trade_date: str, max_stocks: int = None) -> Optional[pd.DataFrame]:
        """
        获取每日基础数据（包含PE、PB、总市值等）

        Args:
            trade_date: 交易日期 (YYYYMMDD)
            max_stocks: 最大处理股票数量，None表示处理所有股票
        """
        if not self.is_available():
            return None
        try:
            import baostock as bs
            logger.info(f"BaoStock: Attempting to get valuation data for {trade_date}")
            lg = bs.login()
            if lg.error_code != '0':
                logger.error(f"BaoStock: Login failed: {lg.error_msg}")
                return None
            try:
                logger.info("BaoStock: Querying stock basic info...")
                rs = bs.query_stock_basic()
                if rs.error_code != '0':
                    logger.error(f"BaoStock: Query stock list failed: {rs.error_msg}")
                    return None
                stock_list = []
                while (rs.error_code == '0') & rs.next():
                    stock_list.append(rs.get_row_data())
                if not stock_list:
                    logger.warning("BaoStock: No stocks found")
                    return None

                total_stocks = len([s for s in stock_list if len(s) > 5 and s[4] == '1' and s[5] == '1'])
                logger.info(f"📊 BaoStock: 找到 {total_stocks} 只活跃股票，开始处理{'全部' if max_stocks is None else f'前 {max_stocks} 只'}...")

                basic_data = []
                processed_count = 0
                failed_count = 0
                for stock in stock_list:
                    if max_stocks and processed_count >= max_stocks:
                        break
                    code = stock[0] if len(stock) > 0 else ''
                    name = stock[1] if len(stock) > 1 else ''
                    stock_type = stock[4] if len(stock) > 4 else '0'
                    status = stock[5] if len(stock) > 5 else '0'
                    if stock_type == '1' and status == '1':
                        try:
                            formatted_date = f"{trade_date[:4]}-{trade_date[4:6]}-{trade_date[6:8]}"
                            # 🔥 获取估值数据和总股本
                            rs_valuation = bs.query_history_k_data_plus(
                                code,
                                "date,code,close,peTTM,pbMRQ,psTTM,pcfNcfTTM,isST",
                                start_date=formatted_date,
                                end_date=formatted_date,
                                frequency="d",
                                adjustflag="3",
                            )
                            if rs_valuation.error_code == '0':
                                valuation_data = []
                                while (rs_valuation.error_code == '0') & rs_valuation.next():
                                    valuation_data.append(rs_valuation.get_row_data())
                                if valuation_data:
                                    row = valuation_data[0]
                                    symbol = code.replace('sh.', '').replace('sz.', '')
                                    ts_code = f"{symbol}.SH" if code.startswith('sh.') else f"{symbol}.SZ"
                                    pe_ttm = self._safe_float(row[3]) if len(row) > 3 else None
                                    pb_mrq = self._safe_float(row[4]) if len(row) > 4 else None
                                    ps_ttm = self._safe_float(row[5]) if len(row) > 5 else None
                                    pcf_ttm = self._safe_float(row[6]) if len(row) > 6 else None
                                    close_price = self._safe_float(row[2]) if len(row) > 2 else None

                                    # 🔥 BaoStock 不直接提供总市值和总股本
                                    # 为了避免同步超时，这里不调用额外的 API 获取总股本
                                    # total_mv 留空，后续可以通过其他数据源补充
                                    total_mv = None

                                    basic_data.append({
                                        'ts_code': ts_code,
                                        'trade_date': trade_date,
                                        'name': name,
                                        'pe': pe_ttm,  # 🔥 市盈率（TTM）
                                        'pb': pb_mrq,  # 🔥 市净率（MRQ）
                                        'ps': ps_ttm,  # 市销率
                                        'pcf': pcf_ttm,  # 市现率
                                        'close': close_price,
                                        'total_mv': total_mv,  # ⚠️ BaoStock 不提供，留空
                                        'turnover_rate': None,  # ⚠️ BaoStock 不提供
                                    })
                                    processed_count += 1

                                    # 🔥 每处理50只股票输出一次进度日志
                                    if processed_count % 50 == 0:
                                        progress_pct = (processed_count / total_stocks) * 100
                                        logger.info(f"📈 BaoStock 同步进度: {processed_count}/{total_stocks} ({progress_pct:.1f}%) - 最新: {name}({ts_code})")
                                else:
                                    failed_count += 1
                            else:
                                failed_count += 1
                        except Exception as e:
                            failed_count += 1
                            if failed_count % 50 == 0:
                                logger.warning(f"⚠️ BaoStock: 已有 {failed_count} 只股票获取失败")
                            logger.debug(f"BaoStock: Failed to get valuation for {code}: {e}")
                            continue
                if basic_data:
                    df = pd.DataFrame(basic_data)
                    logger.info(f"✅ BaoStock 同步完成: 成功 {len(df)} 只，失败 {failed_count} 只，日期 {trade_date}")
                    return df
                else:
                    logger.warning(f"⚠️ BaoStock: 未获取到任何估值数据（失败 {failed_count} 只）")
                    return None
            finally:
                bs.logout()
        except Exception as e:
            logger.error(f"BaoStock: Failed to fetch valuation data for {trade_date}: {e}")
            return None

    def _safe_float(self, value) -> Optional[float]:
        try:
            if value is None or value == '' or value == 'None':
                return None
            return float(value)
        except (ValueError, TypeError):
            return None


    def get_realtime_quotes(self):
        """Placeholder: BaoStock does not provide full-market realtime snapshot in our adapter.
        Return None to allow fallback to higher-priority sources.
        """
        if not self.is_available():
            return None
        return None

    def get_kline(self, code: str, period: str = "day", limit: int = 120, adj: Optional[str] = None):
        """BaoStock K线数据获取（A股日线/周线/月线/分钟线）"""
        if not self.is_available():
            return None
        try:
            import baostock as bs

            code6 = str(code).zfill(6)
            # 构造 BaoStock 格式代码: sh.601127 / sz.000001
            if code6.startswith(('6', '9')):
                bs_code = f"sh.{code6}"
            else:
                bs_code = f"sz.{code6}"

            # 周期映射
            freq_map = {"day": "d", "week": "w", "month": "m", "5m": "5", "15m": "15", "30m": "30", "60m": "60"}
            if period not in freq_map:
                logger.warning(f"BaoStock: 不支持的周期 {period}")
                return None
            frequency = freq_map[period]

            # 复权映射: None/none -> 3(不复权), qfq -> 2(前复权), hfq -> 1(后复权)
            adj_map = {None: "3", "none": "3", "": "3", "qfq": "2", "hfq": "1"}
            adjustflag = adj_map.get(adj, "3")

            # 计算日期范围（多取一些以覆盖 limit）
            end_date = datetime.now()
            if frequency in ("d", "w", "m"):
                start_date = end_date - timedelta(days=max(limit * 3, 365))
            else:
                # 分钟线：每天约 4 小时交易 = 48 根 5 分钟 K 线
                bars_per_day = {
                    "5": 48, "15": 16, "30": 8, "60": 4
                }.get(frequency, 48)
                days_needed = max(limit // bars_per_day + 5, 5)
                start_date = end_date - timedelta(days=days_needed)

            start_str = start_date.strftime("%Y-%m-%d")
            end_str = end_date.strftime("%Y-%m-%d")

            fields = "date,open,high,low,close,volume,amount"
            lg = bs.login()
            if lg.error_code != '0':
                logger.error(f"BaoStock: Login failed: {lg.error_msg}")
                return None
            try:
                rs = bs.query_history_k_data_plus(
                    bs_code, fields,
                    start_date=start_str,
                    end_date=end_str,
                    frequency=frequency,
                    adjustflag=adjustflag,
                )
                if rs.error_code != '0':
                    logger.error(f"BaoStock: K线查询失败: {rs.error_msg}")
                    return None

                data_list = []
                while (rs.error_code == '0') and rs.next():
                    data_list.append(rs.get_row_data())

                if not data_list:
                    logger.info(f"BaoStock: {bs_code} 无K线数据")
                    return None

                items = []
                for row in data_list:
                    # row: [date, open, high, low, close, volume, amount]
                    date_str = row[0] if len(row) > 0 else ''
                    # 标准化日期格式：BaoStock 返回 YYYY-MM-DD
                    open_p = self._safe_float(row[1]) if len(row) > 1 else None
                    high_p = self._safe_float(row[2]) if len(row) > 2 else None
                    low_p = self._safe_float(row[3]) if len(row) > 3 else None
                    close_p = self._safe_float(row[4]) if len(row) > 4 else None
                    vol = self._safe_float(row[5]) if len(row) > 5 else None
                    amt = self._safe_float(row[6]) if len(row) > 6 else None
                    # 跳过无效数据
                    if close_p is None or open_p is None:
                        continue
                    items.append({
                        "time": date_str,
                        "open": open_p,
                        "high": high_p,
                        "low": low_p,
                        "close": close_p,
                        "volume": vol,
                        "amount": amt,
                    })

                if not items:
                    return None

                # 只返回最新的 limit 条
                items = items[-limit:]
                logger.info(f"✅ BaoStock: {bs_code} 获取 {len(items)} 条 {period} K线数据")
                return items
            finally:
                bs.logout()
        except Exception as e:
            logger.error(f"BaoStock get_kline failed for {code}: {e}")
            return None

    def get_news(self, code: str, days: int = 2, limit: int = 50, include_announcements: bool = True):
        """BaoStock does not provide news in this adapter; return None"""
        if not self.is_available():
            return None
        return None


    def find_latest_trade_date(self) -> Optional[str]:
        yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y%m%d")
        logger.info(f"BaoStock: Using yesterday as trade date: {yesterday}")
        return yesterday

