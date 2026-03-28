"""
旧 AKShare 工具模块兼容层。

当前项目的 AKShare 实现已迁移到 providers/china 与 providers/hk，
这里保留旧导入路径，主要服务于历史测试与调试脚本。
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any, Dict, Optional

import akshare as ak
import pandas as pd

from tradingagents.dataflows.providers.china.akshare import (
    AKShareProvider as AsyncAKShareProvider,
    get_akshare_provider as get_async_akshare_provider,
)
from tradingagents.dataflows.providers.hk.improved_hk import (
    get_hk_stock_data_akshare,
    get_hk_stock_info_akshare,
)


def _run_sync(coro):
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        raise RuntimeError("Cannot run compatibility sync wrapper inside an active event loop")

    return asyncio.run(coro)


class AKShareProvider:
    """
    旧同步接口包装器。
    """

    def __init__(self):
        self._provider = get_async_akshare_provider()
        self.connected = getattr(self._provider, "connected", True)

    def get_financial_data(self, symbol: str) -> Dict[str, Any]:
        return _run_sync(self._provider.get_financial_data(symbol))

    def get_stock_data(
        self,
        symbol: str,
        start_date: str,
        end_date: str,
        period: str = "daily",
    ) -> pd.DataFrame:
        return _run_sync(
            self._provider.get_historical_data(
                code=symbol,
                start_date=start_date,
                end_date=end_date,
                period=period,
            )
        )


def get_akshare_provider() -> AKShareProvider:
    return AKShareProvider()


def get_stock_news_em(symbol: str) -> pd.DataFrame:
    return ak.stock_news_em(symbol=symbol)


def get_china_stock_data_akshare(
    symbol: str,
    start_date: str,
    end_date: str,
    period: str = "daily",
) -> pd.DataFrame:
    provider = get_akshare_provider()
    return provider.get_stock_data(symbol, start_date, end_date, period=period)


def format_hk_stock_data_akshare(
    symbol: str,
    data: Optional[pd.DataFrame],
    start_date: Optional[str],
    end_date: Optional[str],
) -> str:
    if data is None or data.empty:
        return (
            f"# {symbol} 港股行情\n\n"
            "## ❌ 数据获取失败\n"
            "- 原因: AKShare 未返回可用日线数据\n"
            "- 建议: 稍后重试或切换其他数据源\n"
        )

    latest = data.iloc[-1]
    latest_date = latest.get("Date") or latest.get("date") or latest.get("时间")
    if isinstance(latest_date, datetime):
        latest_date = latest_date.strftime("%Y-%m-%d")

    open_price = latest.get("Open", latest.get("open"))
    high_price = latest.get("High", latest.get("high"))
    low_price = latest.get("Low", latest.get("low"))
    close_price = latest.get("Close", latest.get("close"))
    volume = latest.get("Volume", latest.get("volume"))

    return (
        f"# {symbol} 港股行情\n\n"
        "## 基本信息\n"
        f"- 市场: 港股\n"
        f"- 代码: {symbol}\n"
        f"- 区间: {start_date or 'N/A'} 至 {end_date or 'N/A'}\n"
        f"- 最新日期: {latest_date or 'N/A'}\n\n"
        "## 最新价格\n"
        f"- 开盘价: HK${open_price}\n"
        f"- 最高价: HK${high_price}\n"
        f"- 最低价: HK${low_price}\n"
        f"- 收盘价: HK${close_price}\n"
        f"- 成交量: {volume}\n"
    )


__all__ = [
    "AKShareProvider",
    "format_hk_stock_data_akshare",
    "get_akshare_provider",
    "get_china_stock_data_akshare",
    "get_hk_stock_data_akshare",
    "get_hk_stock_info_akshare",
    "get_stock_news_em",
]
