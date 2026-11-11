"""ths_daily 能力：同花顺板块日线行情

粒度 index_daily：板块指数粒度按日时间序列（同花顺板块即 TI 指数）。
单位口径：vol=手（同花顺原始单位）、total_mv/float_mv=万元、
turnover_rate=%；接入对侧数据源时必须核对单位并在实现内归一。

排序约定：返回按 trade_date 降序（tushare 原生），调用方按需自行排序。
"""

from ..schema import (
    GRAIN_INDEX_DAILY,
    CapabilityField,
    CapabilityParam,
    CapabilitySchema,
)
from . import register_schema

THS_DAILY_SCHEMA = CapabilitySchema(
    capability_id="ths_daily",
    grain=GRAIN_INDEX_DAILY,
    description="同花顺板块日线行情（OHLC/涨跌幅/换手/市值，按 ts_code 查单板块）",
    fields=[
        CapabilityField("ts_code", "str", True, "板块代码（TS 格式，如 885691.TI）"),
        CapabilityField("trade_date", "str", True, "交易日期 YYYYMMDD"),
        CapabilityField("open", "float", False, "开盘价（点）"),
        CapabilityField("close", "float", False, "收盘价（点）"),
        CapabilityField("high", "float", False, "最高价（点）"),
        CapabilityField("low", "float", False, "最低价（点）"),
        CapabilityField("avg_price", "float", False, "均价（点）"),
        CapabilityField("change", "float", False, "涨跌额（点）"),
        CapabilityField("pct_change", "float", False, "涨跌幅（%）"),
        CapabilityField("vol", "float", False, "成交量（手）"),
        CapabilityField("turnover_rate", "float", False, "换手率（%）"),
        CapabilityField("total_mv", "float", False, "总市值（万元）"),
        CapabilityField("float_mv", "float", False, "流通市值（万元）"),
    ],
    params=[
        CapabilityParam("ts_code", "str", True, "板块代码（TS 格式，如 885691.TI）"),
        CapabilityParam("start_date", "str", False, "开始日期 YYYYMMDD"),
        CapabilityParam("end_date", "str", False, "结束日期 YYYYMMDD"),
    ],
)

register_schema(THS_DAILY_SCHEMA)
