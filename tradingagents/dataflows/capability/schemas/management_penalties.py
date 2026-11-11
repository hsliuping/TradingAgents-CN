"""management_penalties 能力：违规处罚记录

粒度 stock_event：按公司 + 公告日期的事件明细。
单位口径：处罚金额为万元（tushare stk_penalty 原始口径）；
接入对侧数据源时必须核对单位并在实现内归一到本 Schema 声明单位。
"""

from ..schema import (
    GRAIN_STOCK_EVENT,
    CapabilityField,
    CapabilityParam,
    CapabilitySchema,
)
from . import register_schema

MANAGEMENT_PENALTIES_SCHEMA = CapabilitySchema(
    capability_id="management_penalties",
    grain=GRAIN_STOCK_EVENT,
    description="违规处罚记录（处罚类型/对象/金额/违规事由）",
    fields=[
        CapabilityField("ts_code", "str", True, "TS股票代码（如 600519.SH）"),
        CapabilityField("ann_date", "str", True, "公告日期 YYYYMMDD"),
        CapabilityField("penalty_type", "str", False, "处罚类型（警告/罚款/市场禁入等）"),
        CapabilityField("penalty_target", "str", False, "处罚对象（公司/个人）"),
        CapabilityField("penalty_amount", "float", False, "处罚金额（万元）"),
        CapabilityField("violation_type", "str", False, "违规类型"),
        CapabilityField("violation_content", "str", False, "违规事由"),
    ],
    params=[
        CapabilityParam("ts_code", "str", False, "TS股票代码"),
        CapabilityParam("ann_date", "str", False, "公告日期 YYYYMMDD"),
        CapabilityParam("start_date", "str", False, "公告开始日期 YYYYMMDD"),
        CapabilityParam("end_date", "str", False, "公告结束日期 YYYYMMDD"),
    ],
)

register_schema(MANAGEMENT_PENALTIES_SCHEMA)
