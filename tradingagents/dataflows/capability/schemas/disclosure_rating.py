"""disclosure_rating 能力：交易所信息披露考评结果

粒度 stock_event：按公司 + 考评年度的事件明细。
"""

from ..schema import (
    GRAIN_STOCK_EVENT,
    CapabilityField,
    CapabilityParam,
    CapabilitySchema,
)
from . import register_schema

DISCLOSURE_RATING_SCHEMA = CapabilitySchema(
    capability_id="disclosure_rating",
    grain=GRAIN_STOCK_EVENT,
    description="交易所信息披露考评结果（A/B/C/D）",
    fields=[
        CapabilityField("ts_code", "str", True, "TS股票代码（如 600519.SH）"),
        CapabilityField("report_period_end", "str", True, "考评年度/报告期 YYYYMMDD"),
        CapabilityField("disclosure_result", "str", False, "考评结果（A/B/C/D）"),
    ],
    params=[
        CapabilityParam("ts_code", "str", False, "TS股票代码"),
        CapabilityParam("end_date", "str", False, "报告期 YYYYMMDD"),
    ],
)

register_schema(DISCLOSURE_RATING_SCHEMA)
