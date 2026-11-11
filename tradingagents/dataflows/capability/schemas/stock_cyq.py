"""stock_cyq 能力：个股筹码分布（东财）

粒度 stock_daily：个股按日筹码分布快照（接口返回最近约 90 个交易日）。

单位与口径：获利比例为 0-1 小数；成本为元；集中度为无量纲比值。
"""

from ..schema import (
    GRAIN_STOCK_DAILY,
    CapabilityField,
    CapabilityParam,
    CapabilitySchema,
)
from . import register_schema

STOCK_CYQ_SCHEMA = CapabilitySchema(
    capability_id="stock_cyq",
    grain=GRAIN_STOCK_DAILY,
    description="东方财富-个股筹码分布（按日，最近约90个交易日）",
    fields=[
        CapabilityField("trade_date", "str", True, "日期 YYYY-MM-DD"),
        CapabilityField("profit_ratio", "float", False, "获利比例（0-1）"),
        CapabilityField("avg_cost", "float", False, "平均成本（元）"),
        CapabilityField("cost_90_low", "float", False, "90%筹码成本下界（元）"),
        CapabilityField("cost_90_high", "float", False, "90%筹码成本上界（元）"),
        CapabilityField("concentration_90", "float", False, "90%筹码集中度"),
        CapabilityField("cost_70_low", "float", False, "70%筹码成本下界（元）"),
        CapabilityField("cost_70_high", "float", False, "70%筹码成本上界（元）"),
        CapabilityField("concentration_70", "float", False, "70%筹码集中度"),
    ],
    params=[
        CapabilityParam("symbol", "str", True, "股票代码（6位数字，如 000001）"),
    ],
)

register_schema(STOCK_CYQ_SCHEMA)
