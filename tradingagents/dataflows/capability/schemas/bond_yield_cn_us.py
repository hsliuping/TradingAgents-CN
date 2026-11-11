"""bond_yield_cn_us 能力：中美国债收益率对比（东财）

粒度 market_daily：按日发布，中国/美国国债各期限收益率与 10Y-2Y 利差。

单位与口径：收益率为百分数值（如 4.1234 表示 4.1234%），
利差为百分点差值（源接口原生口径，非基点）。
"""

from ..schema import (
    GRAIN_MARKET_DAILY,
    CapabilityField,
    CapabilitySchema,
)
from . import register_schema

BOND_YIELD_CN_US_SCHEMA = CapabilitySchema(
    capability_id="bond_yield_cn_us",
    grain=GRAIN_MARKET_DAILY,
    description="东方财富-中美国债收益率对比（按日）",
    fields=[
        CapabilityField("trade_date", "str", True, "日期 YYYY-MM-DD"),
        CapabilityField("cn_yield_2y", "float", False, "中国国债2年期收益率（%）"),
        CapabilityField("cn_yield_5y", "float", False, "中国国债5年期收益率（%）"),
        CapabilityField("cn_yield_10y", "float", False, "中国国债10年期收益率（%）"),
        CapabilityField("cn_yield_30y", "float", False, "中国国债30年期收益率（%）"),
        CapabilityField("cn_10y_2y_spread", "float", False, "中国国债10年-2年利差（百分点）"),
        CapabilityField("us_yield_2y", "float", False, "美国国债2年期收益率（%）"),
        CapabilityField("us_yield_5y", "float", False, "美国国债5年期收益率（%）"),
        CapabilityField("us_yield_10y", "float", False, "美国国债10年期收益率（%）"),
        CapabilityField("us_yield_30y", "float", False, "美国国债30年期收益率（%）"),
    ],
    params=[],
)

register_schema(BOND_YIELD_CN_US_SCHEMA)
