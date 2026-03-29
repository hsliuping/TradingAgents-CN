"""
交易日历工具模块

提供获取指定日期范围内交易日列表的功能。
A股优先使用 akshare 获取真实交易日历，失败则回退到周末过滤。
美股/港股使用周末过滤。
"""

import logging
from datetime import datetime, timedelta
from typing import List, Optional

logger = logging.getLogger(__name__)

_a_share_trade_dates_cache: Optional[set] = None


def _load_a_share_trade_dates() -> Optional[set]:
    """从 akshare 加载A股历史交易日历并缓存"""
    global _a_share_trade_dates_cache
    if _a_share_trade_dates_cache is not None:
        return _a_share_trade_dates_cache

    try:
        import akshare as ak
        df = ak.tool_trade_date_hist_sina()
        if df is not None and len(df) > 0:
            col = df.columns[0]
            dates = set()
            for val in df[col]:
                if hasattr(val, 'strftime'):
                    dates.add(val.strftime("%Y-%m-%d"))
                else:
                    dates.add(str(val)[:10])
            _a_share_trade_dates_cache = dates
            logger.info(f"已加载A股交易日历，共 {len(dates)} 个交易日")
            return dates
    except Exception as e:
        logger.warning(f"加载A股交易日历失败，将回退到周末过滤: {e}")
    return None


def _filter_weekdays(start: datetime, end: datetime) -> List[str]:
    """过滤出工作日（排除周六日）"""
    days = []
    current = start
    while current <= end:
        if current.weekday() < 5:
            days.append(current.strftime("%Y-%m-%d"))
        current += timedelta(days=1)
    return days


def get_trading_days(start_date: str, end_date: str, market_type: str = "A股") -> List[str]:
    """
    获取指定日期范围内的交易日列表。

    Args:
        start_date: 起始日期 YYYY-MM-DD
        end_date: 结束日期 YYYY-MM-DD
        market_type: 市场类型（A股/美股/港股）

    Returns:
        排序后的交易日字符串列表 ["2025-01-02", "2025-01-03", ...]
    """
    start_dt = datetime.strptime(start_date, "%Y-%m-%d")
    end_dt = datetime.strptime(end_date, "%Y-%m-%d")

    if start_dt > end_dt:
        return []

    today = datetime.now()
    if end_dt.date() > today.date():
        end_dt = today

    if market_type == "A股":
        trade_dates = _load_a_share_trade_dates()
        if trade_dates is not None:
            days = []
            current = start_dt
            while current <= end_dt:
                ds = current.strftime("%Y-%m-%d")
                if ds in trade_dates:
                    days.append(ds)
                current += timedelta(days=1)
            if days:
                return sorted(days)
            logger.warning("akshare 交易日历在该区间无数据，回退到周末过滤")

    return _filter_weekdays(start_dt, end_dt)
