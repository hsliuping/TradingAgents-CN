"""数据能力注册机制（capability）

数据源与工具解耦的中间层：
- 数据源以 @register_capability 声明式挂载已有实现（零改动）
- 工具层经 DataFacade 按"数据能力"查询，不感知具体数据源

用法：
    from tradingagents.dataflows.capability import register_capability
    from tradingagents.dataflows.capability import get_data_facade

    df = await get_data_facade().get_capability("margin").query(trade_date="20261023")

设计文档：docs/05-design/v4.0/data-architecture-problems-and-optimization.md 5.4
"""

from .schema import (
    GRAIN_FUND_DAILY,
    GRAIN_INDEX_DAILY,
    GRAIN_MARKET_DAILY,
    GRAIN_REFERENCE,
    GRAIN_STOCK_DAILY,
    GRAIN_STOCK_EVENT,
    CapabilityField,
    CapabilityParam,
    CapabilitySchema,
)
from .registry import CapabilityEntry, register_capability, registry
from .facade import CapabilityHandle, DataFacade, get_data_facade
from .sync import query_capability_sync

__all__ = [
    "GRAIN_FUND_DAILY",
    "GRAIN_INDEX_DAILY",
    "GRAIN_MARKET_DAILY",
    "GRAIN_REFERENCE",
    "GRAIN_STOCK_DAILY",
    "GRAIN_STOCK_EVENT",
    "CapabilityField",
    "CapabilityParam",
    "CapabilitySchema",
    "CapabilityEntry",
    "register_capability",
    "registry",
    "CapabilityHandle",
    "DataFacade",
    "get_data_facade",
    "query_capability_sync",
]
