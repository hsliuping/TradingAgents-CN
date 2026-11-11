"""index_daily 能力：指数日线行情

粒度 index_daily：指数粒度按日时间序列。
单位口径：vol=手、amount=千元（tushare index_daily 原始单位）；
接入对侧数据源时必须核对单位并在实现内归一到本 Schema 声明单位
（如 akshare 东财接口成交额单位为元，实现内 /1000 归一）。

排序约定：返回按 trade_date 降序（最新在前）——tushare 原生降序，
对侧数据源在实现内归一排序，保证调用方 iloc[0] 取到最近交易日。
"""

from ..schema import (
    GRAIN_INDEX_DAILY,
    CapabilityField,
    CapabilityParam,
    CapabilitySchema,
)
from . import register_schema

INDEX_DAILY_SCHEMA = CapabilitySchema(
    capability_id="index_daily",
    grain=GRAIN_INDEX_DAILY,
    description="指数日线行情（OHLC/成交量/成交额，按 trade_date 降序）",
    fields=[
        CapabilityField("ts_code", "str", True, "指数代码（TS 格式，如 000001.SH）"),
        CapabilityField("trade_date", "str", True, "交易日期 YYYYMMDD"),
        CapabilityField("open", "float", False, "开盘价（点）"),
        CapabilityField("high", "float", False, "最高价（点）"),
        CapabilityField("low", "float", False, "最低价（点）"),
        CapabilityField("close", "float", True, "收盘价（点）"),
        CapabilityField("pre_close", "float", False, "昨收价（点）"),
        CapabilityField("change", "float", False, "涨跌额（点）"),
        CapabilityField("pct_chg", "float", False, "涨跌幅（%）"),
        CapabilityField("vol", "float", False, "成交量（手）"),
        CapabilityField("amount", "float", False, "成交额（千元）"),
    ],
    params=[
        CapabilityParam("ts_code", "str", True, "指数代码（TS 格式，如 000001.SH）"),
        CapabilityParam("start_date", "str", False, "开始日期 YYYYMMDD"),
        CapabilityParam("end_date", "str", False, "结束日期 YYYYMMDD"),
    ],
)

register_schema(INDEX_DAILY_SCHEMA)
