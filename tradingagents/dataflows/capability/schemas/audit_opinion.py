"""audit_opinion 能力：A股公司审计意见

粒度 stock_event：按公司 + 公告日期的事件明细。
单位口径：审计费用为元（tushare stk_audit 原始口径）；
接入对侧数据源时必须核对单位并在实现内归一到本 Schema 声明单位。
"""

from ..schema import (
    GRAIN_STOCK_EVENT,
    CapabilityField,
    CapabilityParam,
    CapabilitySchema,
)
from . import register_schema

AUDIT_OPINION_SCHEMA = CapabilitySchema(
    capability_id="audit_opinion",
    grain=GRAIN_STOCK_EVENT,
    description="A股公司审计意见（审计结果/费用/签字审计师/审计机构）",
    fields=[
        CapabilityField("ts_code", "str", True, "TS股票代码（如 600519.SH）"),
        CapabilityField("ann_date", "str", True, "公告日期 YYYYMMDD"),
        CapabilityField("report_period_end", "str", False, "报告期截止日 YYYYMMDD"),
        CapabilityField("audit_result", "str", False, "审计结果（标准无保留/带强调事项段等）"),
        CapabilityField("audit_fees", "float", False, "审计总费用（元）"),
        CapabilityField("audit_signer", "str", False, "签字审计师"),
        CapabilityField("audit_firm", "str", False, "审计机构"),
    ],
    params=[
        CapabilityParam("ts_code", "str", False, "TS股票代码"),
        CapabilityParam("ann_date", "str", False, "公告日期 YYYYMMDD"),
        CapabilityParam("start_date", "str", False, "公告开始日期 YYYYMMDD"),
        CapabilityParam("end_date", "str", False, "公告结束日期 YYYYMMDD"),
        CapabilityParam("period", "str", False, "报告期 YYYYMMDD"),
    ],
)

register_schema(AUDIT_OPINION_SCHEMA)
