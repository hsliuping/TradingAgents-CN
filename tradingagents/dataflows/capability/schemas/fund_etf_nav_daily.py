"""fund_etf_nav_daily 能力：场内交易基金净值快照（天天基金）

粒度 reference：全市场场内基金当期净值快照，无时间粒度。
源接口的净值列名带动态日期后缀（如 "2026-10-24-单位净值"），
provider 实现内先归一为固定中文列名（取最新披露日）再经 field_mapping 改名。

单位与口径：净值/市价为元；增长率/折价率为百分数值。
"""

from ..schema import (
    GRAIN_REFERENCE,
    CapabilityField,
    CapabilitySchema,
)
from . import register_schema

FUND_ETF_NAV_DAILY_SCHEMA = CapabilitySchema(
    capability_id="fund_etf_nav_daily",
    grain=GRAIN_REFERENCE,
    description="天天基金-场内交易基金净值快照（全市场，最新披露日）",
    fields=[
        CapabilityField("fund_code", "str", True, "基金代码（6位）"),
        CapabilityField("fund_name", "str", False, "基金简称"),
        CapabilityField("fund_type", "str", False, "基金类型"),
        CapabilityField("unit_nav", "float", False, "单位净值（元）"),
        CapabilityField("accum_nav", "float", False, "累计净值（元）"),
        CapabilityField("nav_change_value", "float", False, "净值增长值（元）"),
        CapabilityField("growth_rate", "float", False, "净值增长率（%）"),
        CapabilityField("market_price", "float", False, "市价（元）"),
        CapabilityField("discount_rate", "float", False, "折价率（%）"),
    ],
    params=[],
)

register_schema(FUND_ETF_NAV_DAILY_SCHEMA)
