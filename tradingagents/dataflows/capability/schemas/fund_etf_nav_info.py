"""fund_etf_nav_info 能力：场内交易基金历史净值明细（天天基金）

粒度 fund_daily：单只基金按日净值序列。

单位与口径：净值为元；日增长率为百分数值；申赎状态为源接口中文枚举。
排序约定：nav_date 降序（最新在前）。
"""

from ..schema import (
    GRAIN_FUND_DAILY,
    CapabilityField,
    CapabilityParam,
    CapabilitySchema,
)
from . import register_schema

FUND_ETF_NAV_INFO_SCHEMA = CapabilitySchema(
    capability_id="fund_etf_nav_info",
    grain=GRAIN_FUND_DAILY,
    description="天天基金-场内交易基金历史净值明细（单基金按日）",
    fields=[
        CapabilityField("nav_date", "str", True, "净值日期 YYYY-MM-DD"),
        CapabilityField("unit_nav", "float", False, "单位净值（元）"),
        CapabilityField("accum_nav", "float", False, "累计净值（元）"),
        CapabilityField("daily_growth", "float", False, "日增长率（%）"),
        CapabilityField("purchase_status", "str", False, "申购状态"),
        CapabilityField("redeem_status", "str", False, "赎回状态"),
    ],
    params=[
        CapabilityParam("fund", "str", True, "基金代码（6位，如 511280）"),
        CapabilityParam("start_date", "str", False, "开始日期 YYYYMMDD"),
        CapabilityParam("end_date", "str", False, "结束日期 YYYYMMDD"),
    ],
)

register_schema(FUND_ETF_NAV_INFO_SCHEMA)
