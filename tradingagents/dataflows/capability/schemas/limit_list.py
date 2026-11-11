"""limit_list 能力：涨跌停统计（涨停/跌停/炸板个股清单）

粒度 stock_event：按日的个股事件流。
"""

from ..schema import (
    GRAIN_STOCK_EVENT,
    CapabilityField,
    CapabilityParam,
    CapabilitySchema,
)
from . import register_schema

LIMIT_LIST_SCHEMA = CapabilitySchema(
    capability_id="limit_list",
    grain=GRAIN_STOCK_EVENT,
    description="涨跌停统计（涨停/跌停/炸板个股清单，按日事件流）",
    fields=[
        CapabilityField("trade_date", "str", True, "交易日期 YYYYMMDD"),
        CapabilityField("ts_code", "str", True, "股票代码（TS 格式，如 600519.SH）"),
        CapabilityField("stock_name", "str", False, "股票名称"),
        CapabilityField("limit_type", "str", True, "涨跌停类型（U涨停 / D跌停 / Z炸板）"),
        CapabilityField("pct_chg", "float", False, "涨跌幅（%）"),
        CapabilityField("close_price", "float", False, "收盘价（元）"),
        CapabilityField("open_times", "float", False, "打开次数（次）"),
        CapabilityField("limit_streak", "str", False, "连板统计（如 3连板）"),
    ],
    params=[
        CapabilityParam("trade_date", "str", True, "交易日期 YYYYMMDD"),
        CapabilityParam("limit_type", "str", False, "涨跌停类型过滤（U/D/Z）"),
    ],
)

register_schema(LIMIT_LIST_SCHEMA)
