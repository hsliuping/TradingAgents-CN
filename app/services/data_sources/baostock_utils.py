"""
BaoStock 共享工具：全局锁 + 最近交易日探测。

BaoStock Python SDK 使用单连接 socket，Windows 下多线程/长连接并发 login 会触发 WinError 10038。
"""
from __future__ import annotations

import logging
import threading
from contextlib import contextmanager
from datetime import datetime, timedelta
from typing import Iterator, Optional

logger = logging.getLogger(__name__)

_BAOSTOCK_LOCK = threading.Lock()


@contextmanager
def baostock_session() -> Iterator[None]:
    """串行化 BaoStock 调用，避免多线程争用同一 socket。"""
    _BAOSTOCK_LOCK.acquire()
    try:
        yield
    finally:
        _BAOSTOCK_LOCK.release()


def find_last_trade_date(days_back: int = 30) -> Optional[str]:
    """
    返回最近一个 A 股交易日，格式 YYYYMMDD。
    优先用 BaoStock 交易日历；失败则回退到最近工作日。
    """
    try:
        import baostock as bs

        with baostock_session():
            lg = bs.login()
            if lg.error_code != "0":
                logger.warning("BaoStock: login failed when resolving trade date: %s", lg.error_msg)
                return _fallback_weekday_trade_date(days_back)
            try:
                end = datetime.now().strftime("%Y-%m-%d")
                start = (datetime.now() - timedelta(days=days_back)).strftime("%Y-%m-%d")
                rs = bs.query_trade_dates(start_date=start, end_date=end)
                if rs.error_code != "0":
                    return _fallback_weekday_trade_date(days_back)

                trade_days: list[str] = []
                while rs.error_code == "0" and rs.next():
                    row = rs.get_row_data()
                    if len(row) >= 2 and row[1] == "1":
                        trade_days.append(row[0])
                if trade_days:
                    return trade_days[-1].replace("-", "")
            finally:
                bs.logout()
    except Exception as exc:
        logger.warning("BaoStock: resolve trade date failed: %s", exc)

    return _fallback_weekday_trade_date(days_back)


def _fallback_weekday_trade_date(days_back: int) -> str:
    """跳过周末，返回最近工作日（YYYYMMDD）。"""
    for delta in range(1, max(days_back, 7) + 1):
        day = datetime.now() - timedelta(days=delta)
        if day.weekday() < 5:
            return day.strftime("%Y%m%d")
    return (datetime.now() - timedelta(days=1)).strftime("%Y%m%d")


def relogin(bs_module) -> bool:
    """Socket 异常后尝试重新登录。"""
    try:
        try:
            bs_module.logout()
        except Exception:
            pass
        lg = bs_module.login()
        return lg.error_code == "0"
    except Exception as exc:
        logger.warning("BaoStock: relogin failed: %s", exc)
        return False
