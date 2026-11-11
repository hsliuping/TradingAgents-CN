"""equity_incentive 能力：股权激励计划明细

粒度 stock_event：按公司 + 公告日期的事件明细。
单位口径：授予数量为万股、总股本占比为 %（tushare equity_incentive 原始口径）；
接入对侧数据源时必须核对单位并在实现内归一到本 Schema 声明单位。
"""

from ..schema import (
    GRAIN_STOCK_EVENT,
    CapabilityField,
    CapabilityParam,
    CapabilitySchema,
)
from . import register_schema

EQUITY_INCENTIVE_SCHEMA = CapabilitySchema(
    capability_id="equity_incentive",
    grain=GRAIN_STOCK_EVENT,
    description="股权激励计划明细（方案/授予量/授予价/年限/业绩条件）",
    fields=[
        CapabilityField("ts_code", "str", True, "TS股票代码（如 600519.SH）"),
        CapabilityField("ann_date", "str", True, "公告日期 YYYYMMDD"),
        CapabilityField("incentive_plan", "str", False, "激励方案"),
        CapabilityField("grant_volume", "float", False, "授予数量（万股）"),
        CapabilityField("grant_price", "float", False, "授予价格（元）"),
        CapabilityField("incentive_years", "float", False, "激励年限（年）"),
        CapabilityField("performance_condition", "str", False, "行权条件/业绩要求"),
        CapabilityField("total_share_ratio", "float", False, "总股本占比（%）"),
    ],
    params=[
        CapabilityParam("ts_code", "str", False, "TS股票代码"),
        CapabilityParam("ann_date", "str", False, "公告日期 YYYYMMDD"),
        CapabilityParam("start_date", "str", False, "公告开始日期 YYYYMMDD"),
        CapabilityParam("end_date", "str", False, "公告结束日期 YYYYMMDD"),
    ],
)

register_schema(EQUITY_INCENTIVE_SCHEMA)
