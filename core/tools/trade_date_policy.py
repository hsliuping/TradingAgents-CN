from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from tradingagents.config.runtime_settings import get_timezone_name


def apply_stable_data_cutoff(date_str: str, cutoff_hour: int = 19) -> str:
    """在收盘后数据稳定前，将当日请求回退到上一自然日。"""
    if not date_str:
        return date_str

    clean = str(date_str).split()[0]
    fmt = '%Y-%m-%d' if '-' in clean else '%Y%m%d'

    try:
        requested_dt = datetime.strptime(clean, fmt)
    except Exception:
        return clean

    now = datetime.now(ZoneInfo(get_timezone_name()))
    today = now.date()

    max_stable_date = today if now.hour >= cutoff_hour else today - timedelta(days=1)
    effective_date = min(requested_dt.date(), max_stable_date)

    return effective_date.strftime(fmt)


def build_stable_data_cutoff_note(
    requested_date: str,
    effective_date: str,
    *,
    subject: str = "当日收盘后日频数据",
) -> str:
    """构造对用户可见的稳定数据回退说明。"""
    if not requested_date or not effective_date or str(requested_date) == str(effective_date):
        return ""

    return (
        f"当前尚无 {requested_date} 的{subject}，本次分析按前一可用交易日 "
        f"{effective_date} 的口径执行。"
    )