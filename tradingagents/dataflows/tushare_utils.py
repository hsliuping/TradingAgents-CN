"""
旧 Tushare 工具模块兼容层。
"""

from tradingagents.dataflows.providers.china.tushare import (  # noqa: F401
    TushareProvider,
    get_tushare_provider,
)

__all__ = ["TushareProvider", "get_tushare_provider"]

