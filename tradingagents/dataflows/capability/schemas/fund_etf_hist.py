"""fund_etf_hist 能力：ETF 历史日线行情（东财）

粒度 fund_daily：单只 ETF 按日行情序列。

单位与口径：价格为元；成交量为手；成交额为元；振幅/涨跌幅/换手率为百分数值。
排序约定：trade_date 降序（最新在前）。
"""

from ..schema import (
    GRAIN_FUND_DAILY,
    CapabilityField,
    CapabilityParam,
    CapabilitySchema,
)
from . import register_schema

FUND_ETF_HIST_SCHEMA = CapabilitySchema(
    capability_id="fund_etf_hist",
    grain=GRAIN_FUND_DAILY,
    description="东方财富-ETF 历史日线行情（单基金按日）",
    fields=[
        CapabilityField("trade_date", "str", True, "交易日期 YYYY-MM-DD"),
        CapabilityField("open", "float", False, "开盘价（元）"),
        CapabilityField("high", "float", False, "最高价（元）"),
        CapabilityField("low", "float", False, "最低价（元）"),
        CapabilityField("close", "float", False, "收盘价（元）"),
        CapabilityField("volume", "float", False, "成交量（手）"),
        CapabilityField("amount", "float", False, "成交额（元）"),
        CapabilityField("amplitude", "float", False, "振幅（%）"),
        CapabilityField("pct_change", "float", False, "涨跌幅（%）"),
        CapabilityField("change", "float", False, "涨跌额（元）"),
        CapabilityField("turnover_rate", "float", False, "换手率（%）"),
    ],
    params=[
        CapabilityParam("symbol", "str", True, "基金代码（6位，如 159707）"),
        CapabilityParam("start_date", "str", False, "开始日期 YYYYMMDD"),
        CapabilityParam("end_date", "str", False, "结束日期 YYYYMMDD"),
    ],
)

register_schema(FUND_ETF_HIST_SCHEMA)
