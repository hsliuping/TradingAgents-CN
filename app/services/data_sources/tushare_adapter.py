"""
Tushare data source adapter
"""
from typing import Optional, Dict
import logging
from datetime import datetime, timedelta
import pandas as pd

from .base import DataSourceAdapter

logger = logging.getLogger(__name__)


class TushareAdapter(DataSourceAdapter):
    """Tushare data source adapter"""

    def __init__(self):
        super().__init__()
        self._provider = None
        self._initialize()

    def _initialize(self):
        """Initialize Tushare provider"""
        try:
            from tradingagents.dataflows.providers.china.tushare import get_tushare_provider
            self._provider = get_tushare_provider()
        except Exception as e:
            logger.warning(f"Failed to initialize Tushare provider: {e}")
            self._provider = None

    @property
    def name(self) -> str:
        return "tushare"

    def _get_default_priority(self) -> int:
        return 3

    def get_token_source(self) -> Optional[str]:
        """获取 Token 来源"""
        if self._provider:
            return getattr(self._provider, "token_source", None)
        return None

    def is_available(self) -> bool:
        """Check whether Tushare is available"""
        if self._provider and not getattr(self._provider, "connected", False):
            try:
                self._provider.connect_sync()
            except Exception as e:
                logger.debug(f"Tushare: Auto-connect failed: {e}")

        if self._provider is None:
            return False

        # 自定义API模式下，self._provider.api 为 None 但仍然可用
        if getattr(self._provider, "use_custom_api", False) and getattr(self._provider, "connected", False):
            return True

        return (
            getattr(self._provider, "connected", False)
            and self._provider.api is not None
        )

    def get_stock_list(self) -> Optional[pd.DataFrame]:
        """Get stock list"""
        if self._provider and not self.is_available():
            logger.info("Tushare: Provider not connected, attempting to connect...")
            try:
                self._provider.connect_sync()
            except Exception as e:
                logger.warning(f"Tushare: Failed to connect: {e}")

        if not self.is_available():
            logger.warning("Tushare: Provider is not available")
            return None
        try:
            df = self._provider.get_stock_list_sync()
            if df is not None and not df.empty:
                logger.info(f"Tushare: Successfully fetched {len(df)} stocks")
                return df
        except Exception as e:
            logger.error(f"Tushare: Failed to fetch stock list: {e}")
        return None

    def get_daily_basic(self, trade_date: str) -> Optional[pd.DataFrame]:
        """Get daily basic financial data"""
        if not self.is_available():
            return None
        try:
            fields = "ts_code,total_mv,circ_mv,pe,pb,ps,turnover_rate,volume_ratio,pe_ttm,pb_mrq,ps_ttm,total_share,float_share"
            df = self._provider.api.daily_basic(trade_date=trade_date, fields=fields)
            if df is not None and not df.empty:
                logger.info(f"Tushare: Successfully fetched daily data for {trade_date}, {len(df)} records")
                return df
        except Exception as e:
            logger.error(f"Tushare: Failed to fetch daily data for {trade_date}: {e}")
        return None

    def get_realtime_quotes(self):
        """Get full-market near real-time quotes via Tushare rt_k fallback"""
        if not self.is_available():
            return None
        try:
            df = self._provider.api.rt_k(ts_code='3*.SZ,6*.SH,0*.SZ,9*.BJ')
            if df is None or getattr(df, 'empty', True):
                logger.warning('Tushare rt_k returned empty data')
                return None
            if 'ts_code' not in df.columns or 'close' not in df.columns:
                logger.error(f'Tushare rt_k missing columns: {list(df.columns)}')
                return None
            result: Dict[str, Dict[str, Optional[float]]] = {}
            for _, row in df.iterrows():
                ts_code = str(row.get('ts_code') or '')
                if not ts_code or '.' not in ts_code:
                    continue
                code6 = ts_code.split('.')[0].zfill(6)
                close = float(row.get('close')) if row.get('close') is not None else None
                pre_close = float(row.get('pre_close')) if row.get('pre_close') is not None else None
                amount = float(row.get('amount')) if row.get('amount') is not None else None
                pct_chg = None
                if 'pct_chg' in df.columns and row.get('pct_chg') is not None:
                    try:
                        pct_chg = float(row.get('pct_chg'))
                    except Exception:
                        pct_chg = None
                if pct_chg is None and close is not None and pre_close is not None and pre_close not in (0, 0.0):
                    try:
                        pct_chg = (close / pre_close - 1.0) * 100.0
                    except Exception:
                        pct_chg = None
                op = None
                hi = None
                lo = None
                vol = None
                try:
                    if 'open' in df.columns:
                        op = float(row.get('open')) if row.get('open') is not None else None
                    if 'high' in df.columns:
                        hi = float(row.get('high')) if row.get('high') is not None else None
                    if 'low' in df.columns:
                        lo = float(row.get('low')) if row.get('low') is not None else None
                    if 'vol' in df.columns:
                        vol = float(row.get('vol')) if row.get('vol') is not None else None
                        if vol is not None:
                            vol = vol * 100
                    elif 'volume' in df.columns:
                        vol = float(row.get('volume')) if row.get('volume') is not None else None
                        if vol is not None:
                            vol = vol * 100
                except Exception:
                    pass
                result[code6] = {'close': close, 'pct_chg': pct_chg, 'amount': amount, 'volume': vol, 'open': op, 'high': hi, 'low': lo, 'pre_close': pre_close}
            return result
        except Exception as e:
            logger.error(f'Failed to fetch realtime quotes from Tushare rt_k: {e}')
            return None

    def get_kline(self, code: str, period: str = "day", limit: int = 120, adj: Optional[str] = None):
        """Get K-line bars using tushare pro_bar"""
        if not self.is_available():
            return None
        try:
            from tushare.pro.data_pro import pro_bar
        except Exception:
            logger.error("Tushare pro_bar not available")
            return None
        try:
            prov = self._provider
            if prov is None or prov.api is None:
                return None
            ts_code = prov._normalize_ts_code(code) if hasattr(prov, "_normalize_ts_code") else code
            freq_map = {
                "day": "D", "week": "W", "month": "M",
                "5m": "5min", "15m": "15min", "30m": "30min", "60m": "60min",
            }
            freq = freq_map.get(period, "D")
            adj_arg = adj if adj in (None, "qfq", "hfq") else None
            if freq in ["5min", "15min", "30min", "60min"]:
                fields = "open,high,low,close,vol,amount,trade_date,trade_time"
            else:
                fields = "open,high,low,close,vol,amount,trade_date"
            df = pro_bar(ts_code=ts_code, api=prov.api, freq=freq, adj=adj_arg, limit=limit, fields=fields)
            if df is None or getattr(df, 'empty', True):
                return None
            items = []
            tcol = 'trade_time' if 'trade_time' in df.columns else 'trade_date' if 'trade_date' in df.columns else None
            if tcol is None:
                logger.error(f'Tushare pro_bar missing time column: {list(df.columns)}')
                return None
            df = df.sort_values(tcol)
            for _, row in df.iterrows():
                tval = row.get(tcol)
                try:
                    time_str = str(tval)
                    items.append({
                        "time": time_str,
                        "open": float(row.get('open')) if row.get('open') is not None else None,
                        "high": float(row.get('high')) if row.get('high') is not None else None,
                        "low": float(row.get('low')) if row.get('low') is not None else None,
                        "close": float(row.get('close')) if row.get('close') is not None else None,
                        "volume": float(row.get('vol')) if row.get('vol') is not None else None,
                        "amount": float(row.get('amount')) if row.get('amount') is not None else None,
                    })
                except Exception:
                    continue
            return items
        except Exception as e:
            logger.error(f"Failed to fetch kline from Tushare: {e}")
            return None

    def get_news(self, code: str, days: int = 2, limit: int = 50, include_announcements: bool = True):
        """Try to fetch news/announcements via tushare pro api"""
        if not self.is_available():
            return None
        api = self._provider.api if self._provider else None
        if api is None:
            return None
        items = []
        try:
            ts_code = self._provider._normalize_ts_code(code) if hasattr(self._provider, "_normalize_ts_code") else code
        except Exception:
            ts_code = code
        try:
            end = datetime.now()
            start = end - timedelta(days=max(1, days))
            start_str = start.strftime('%Y%m%d')
            end_str = end.strftime('%Y%m%d')
        except Exception:
            start_str = end_str = ""
        try:
            if include_announcements and hasattr(api, 'anns'):
                df_anns = api.anns(ts_code=ts_code, start_date=start_str, end_date=end_str)
                if df_anns is not None and not df_anns.empty:
                    for _, row in df_anns.head(limit).iterrows():
                        items.append({
                            "title": row.get('title') or row.get('ann_title') or '',
                            "source": "tushare",
                            "time": str(row.get('ann_date') or row.get('pub_date') or ''),
                            "url": row.get('url') or row.get('ann_url') or '',
                            "type": "announcement",
                        })
        except Exception:
            pass
        try:
            if hasattr(api, 'news'):
                df_news = api.news(ts_code=ts_code, start_date=start_str, end_date=end_str)
                if df_news is not None and not df_news.empty:
                    for _, row in df_news.head(max(0, limit - len(items))).iterrows():
                        items.append({
                            "title": row.get('title') or '',
                            "source": row.get('src') or 'tushare',
                            "time": str(row.get('pub_time') or row.get('pub_date') or ''),
                            "url": row.get('url') or '',
                            "type": "news",
                        })
        except Exception:
            pass
        return items if items else None

    def find_latest_trade_date(self) -> Optional[str]:
        """Find latest trade date by probing Tushare"""
        if not self.is_available():
            return None
        try:
            today = datetime.now()
            for delta in range(0, 10):
                d = (today - timedelta(days=delta)).strftime("%Y%m%d")
                try:
                    db = self._provider.api.daily_basic(trade_date=d, fields="ts_code,total_mv")
                    if db is not None and not db.empty:
                        logger.info(f"Tushare: Found latest trade date: {d}")
                        return d
                except Exception:
                    continue
        except Exception as e:
            logger.error(f"Tushare: Failed to find latest trade date: {e}")
        return None