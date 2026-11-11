"""fund_etf_spot 能力：ETF 场内实时行情快照（东财）

粒度 reference：全市场 ETF 实时快照，无时间粒度。
工具侧按 fund_code 过滤目标 ETF 行。

单位与口径：价格为元；成交量为手；成交额为元；涨跌幅为百分数值。
"""

from ..schema import (
    GRAIN_REFERENCE,
    CapabilityField,
    CapabilitySchema,
)
from . import register_schema

FUND_ETF_SPOT_SCHEMA = CapabilitySchema(
    capability_id="fund_etf_spot",
    grain=GRAIN_REFERENCE,
    description="东方财富-ETF 场内实时行情快照（全市场）",
    fields=[
        CapabilityField("fund_code", "str", True, "基金代码（6位）"),
        CapabilityField("fund_name", "str", False, "基金简称"),
        CapabilityField("latest_price", "float", False, "最新价（元）"),
        CapabilityField("pct_change", "float", False, "涨跌幅（%）"),
        CapabilityField("volume", "float", False, "成交量（手）"),
        CapabilityField("amount", "float", False, "成交额（元）"),
    ],
    params=[],
)

register_schema(FUND_ETF_SPOT_SCHEMA)
