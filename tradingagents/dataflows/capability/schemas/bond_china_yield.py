"""bond_china_yield 能力：中国债券信息网国债及其他债券收益率曲线

粒度 market_daily：按日发布，含多条曲线（国债/中短期票据/商业银行普通债等），
curve_name 字段区分；工具侧按 curve_name 过滤后取 trade_date 最新一条。

单位与口径：收益率为百分数值（如 2.1234 表示 2.1234%）。
"""

from ..schema import (
    GRAIN_MARKET_DAILY,
    CapabilityField,
    CapabilitySchema,
)
from . import register_schema

BOND_CHINA_YIELD_SCHEMA = CapabilitySchema(
    capability_id="bond_china_yield",
    grain=GRAIN_MARKET_DAILY,
    description="中国债券信息网-国债及其他债券收益率曲线（多曲线按日）",
    fields=[
        CapabilityField("trade_date", "str", True, "日期 YYYY-MM-DD"),
        CapabilityField("curve_name", "str", True, "曲线名称（如 中债国债收益率曲线）"),
        CapabilityField("yield_3m", "float", False, "3月期到期收益率（%）"),
        CapabilityField("yield_6m", "float", False, "6月期到期收益率（%）"),
        CapabilityField("yield_1y", "float", False, "1年期到期收益率（%）"),
        CapabilityField("yield_3y", "float", False, "3年期到期收益率（%）"),
        CapabilityField("yield_5y", "float", False, "5年期到期收益率（%）"),
        CapabilityField("yield_7y", "float", False, "7年期到期收益率（%）"),
        CapabilityField("yield_10y", "float", False, "10年期到期收益率（%）"),
        CapabilityField("yield_30y", "float", False, "30年期到期收益率（%）"),
    ],
    params=[],
)

register_schema(BOND_CHINA_YIELD_SCHEMA)
