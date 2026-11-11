"""stk_limit 能力：每日涨跌停价格

粒度 stock_daily：个股按日。
"""

from ..schema import (
    GRAIN_STOCK_DAILY,
    CapabilityField,
    CapabilityParam,
    CapabilitySchema,
)
from . import register_schema

STK_LIMIT_SCHEMA = CapabilitySchema(
    capability_id="stk_limit",
    grain=GRAIN_STOCK_DAILY,
    description="每日涨跌停价格（个股按日）",
    fields=[
        CapabilityField("trade_date", "str", True, "交易日期 YYYYMMDD"),
        CapabilityField("ts_code", "str", True, "股票代码（TS 格式，如 600519.SH）"),
        CapabilityField("up_limit_price", "float", True, "涨停价（元）"),
        CapabilityField("down_limit_price", "float", True, "跌停价（元）"),
    ],
    params=[
        CapabilityParam("trade_date", "str", True, "交易日期 YYYYMMDD"),
    ],
)

register_schema(STK_LIMIT_SCHEMA)
