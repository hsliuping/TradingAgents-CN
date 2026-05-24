"""
BaoStock data source adapter
"""
from typing import Optional
import logging
from datetime import datetime, timedelta
import pandas as pd

from .base import DataSourceAdapter
from .baostock_utils import baostock_session, find_last_trade_date, relogin

logger = logging.getLogger(__name__)

# 全市场逐只拉取估值非常慢，且 Windows 长连接易触发 WinError 10038
_BULK_VALUATION_MAX_STOCKS = 300
_RELOGIN_INTERVAL = 100
_CONSECUTIVE_FAIL_ABORT = 30


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
            with baostock_session():
                lg = bs.login()
                if lg.error_code != '0':
                    logger.error(f"BaoStock: Login failed: {lg.error_msg}")
                    return None
                try:
                    return self._fetch_stock_list_locked(bs)
                finally:
                    bs.logout()
        except Exception as e:
            logger.error(f"BaoStock: Failed to fetch stock list: {e}")
            return None

    def _fetch_stock_list_locked(self, bs) -> Optional[pd.DataFrame]:
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
        except Exception as e:
            logger.error(f"BaoStock: Failed to fetch stock list: {e}")
            return None

    def get_daily_basic(self, trade_date: str, max_stocks: int = None) -> Optional[pd.DataFrame]:
        """
        获取每日基础数据（包含PE、PB、总市值等）

        Args:
            trade_date: 交易日期 (YYYYMMDD)
            max_stocks: 最大处理股票数量；None 时使用保守上限，避免全市场逐只拉取
        """
        if not self.is_available():
            return None
        if max_stocks is None:
            max_stocks = _BULK_VALUATION_MAX_STOCKS
        try:
            import baostock as bs

            resolved_date = find_last_trade_date()
            if resolved_date and resolved_date != trade_date:
                logger.warning(
                    "BaoStock: 请求日期 %s 可能非交易日，改用最近交易日 %s",
                    trade_date,
                    resolved_date,
                )
                trade_date = resolved_date

            logger.info(f"BaoStock: Attempting to get valuation data for {trade_date}")
            with baostock_session():
                lg = bs.login()
                if lg.error_code != '0':
                    logger.error(f"BaoStock: Login failed: {lg.error_msg}")
                    return None
                return self._fetch_daily_basic_locked(bs, trade_date, max_stocks)
        except Exception as e:
            logger.error(f"BaoStock: Failed to fetch valuation data for {trade_date}: {e}")
            return None

    def _fetch_daily_basic_locked(self, bs, trade_date: str, max_stocks: int) -> Optional[pd.DataFrame]:
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
                consecutive_failures = 0
                formatted_date = f"{trade_date[:4]}-{trade_date[4:6]}-{trade_date[6:8]}"
                for stock in stock_list:
                    if max_stocks and processed_count >= max_stocks:
                        break
                    code = stock[0] if len(stock) > 0 else ''
                    name = stock[1] if len(stock) > 1 else ''
                    stock_type = stock[4] if len(stock) > 4 else '0'
                    status = stock[5] if len(stock) > 5 else '0'
                    if stock_type == '1' and status == '1':
                        if processed_count > 0 and processed_count % _RELOGIN_INTERVAL == 0:
                            relogin(bs)
                        try:
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
                                    total_mv = None

                                    basic_data.append({
                                        'ts_code': ts_code,
                                        'trade_date': trade_date,
                                        'name': name,
                                        'pe': pe_ttm,
                                        'pb': pb_mrq,
                                        'ps': ps_ttm,
                                        'pcf': pcf_ttm,
                                        'close': close_price,
                                        'total_mv': total_mv,
                                        'turnover_rate': None,
                                    })
                                    processed_count += 1
                                    consecutive_failures = 0

                                    if processed_count % 50 == 0:
                                        progress_pct = (processed_count / total_stocks) * 100
                                        logger.info(
                                            "📈 BaoStock 同步进度: %s/%s (%.1f%%) - 最新: %s(%s)",
                                            processed_count,
                                            total_stocks,
                                            progress_pct,
                                            name,
                                            ts_code,
                                        )
                                else:
                                    failed_count += 1
                                    consecutive_failures += 1
                            else:
                                failed_count += 1
                                consecutive_failures += 1
                        except OSError as e:
                            failed_count += 1
                            consecutive_failures += 1
                            if "10038" in str(e) or "套接字" in str(e):
                                logger.warning("BaoStock: socket error, attempting relogin: %s", e)
                                relogin(bs)
                            if consecutive_failures >= _CONSECUTIVE_FAIL_ABORT:
                                logger.error(
                                    "BaoStock: 连续 %s 次失败，中止批量估值拉取（可能为非交易日或连接已损坏）",
                                    consecutive_failures,
                                )
                                break
                        except Exception as e:
                            failed_count += 1
                            consecutive_failures += 1
                            if failed_count % 50 == 0:
                                logger.warning(f"⚠️ BaoStock: 已有 {failed_count} 只股票获取失败")
                            logger.debug(f"BaoStock: Failed to get valuation for {code}: {e}")
                            if consecutive_failures >= _CONSECUTIVE_FAIL_ABORT:
                                break
                            continue
                if basic_data:
                    df = pd.DataFrame(basic_data)
                    logger.info(f"✅ BaoStock 同步完成: 成功 {len(df)} 只，失败 {failed_count} 只，日期 {trade_date}")
                    return df
                logger.warning(
                    "⚠️ BaoStock: 未获取到任何估值数据（失败 %s 只，日期 %s）。"
                    "全市场批量估值请优先使用 AKShare/Tushare。",
                    failed_count,
                    trade_date,
                )
                return None
        finally:
            try:
                bs.logout()
            except Exception:
                pass

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
        """BaoStock not used for K-line here; return None to allow fallback"""
        if not self.is_available():
            return None
        return None

    def get_news(self, code: str, days: int = 2, limit: int = 50, include_announcements: bool = True):
        """BaoStock does not provide news in this adapter; return None"""
        if not self.is_available():
            return None
        return None

        """Placeholder: BaoStock  does not provide full-market realtime snapshot in our adapter.
        Return None to allow fallback to higher-priority sources.
        """

    def find_latest_trade_date(self) -> Optional[str]:
        trade_date = find_last_trade_date()
        logger.info("BaoStock: resolved latest trade date: %s", trade_date)
        return trade_date

