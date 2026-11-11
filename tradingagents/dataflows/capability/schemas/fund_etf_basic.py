"""fund_etf_basic 能力：ETF 基金静态档案（tushare fund_basic）

粒度 reference：单基金静态属性，无时间粒度。

单位与口径：费率为百分数值；最小申购金额为万元（tushare 原生口径）；
发行规模为万份 -> 归一为份（issue_amount * 10000，适配器内换算）。
日期字段保持 tushare 原生 YYYYMMDD 文本，由消费方经 _normalize_date 归一展示。
"""

from ..schema import (
    GRAIN_REFERENCE,
    CapabilityField,
    CapabilityParam,
    CapabilitySchema,
)
from . import register_schema

FUND_ETF_BASIC_SCHEMA = CapabilitySchema(
    capability_id="fund_etf_basic",
    grain=GRAIN_REFERENCE,
    description="Tushare-ETF 基金静态档案（fund_basic，单基金）",
    fields=[
        CapabilityField("fund_code", "str", True, "基金代码（6位）"),
        CapabilityField("name", "str", False, "基金简称"),
        CapabilityField("fund_type", "str", False, "基金类型"),
        CapabilityField("track_index", "str", False, "业绩比较基准/跟踪指数"),
        CapabilityField("management", "str", False, "基金管理人"),
        CapabilityField("custodian", "str", False, "基金托管人"),
        CapabilityField("management_fee", "float", False, "管理费率（%）"),
        CapabilityField("custodian_fee", "float", False, "托管费率（%）"),
        CapabilityField("found_date", "str", False, "成立日期"),
        CapabilityField("list_date", "str", False, "上市日期"),
        CapabilityField("issue_date", "str", False, "发行日期"),
        CapabilityField("due_date", "str", False, "到期日期"),
        CapabilityField("invest_type", "str", False, "投资类型"),
        CapabilityField("status", "str", False, "存续状态（L上市/D退市/I发行）"),
        CapabilityField("min_amount", "float", False, "最小申购金额（万元）"),
        CapabilityField("purchase_start_date", "str", False, "申购开始日"),
        CapabilityField("redemption_start_date", "str", False, "赎回开始日"),
        CapabilityField("fund_scale", "float", False, "发行规模（份）"),
    ],
    params=[
        CapabilityParam("symbol", "str", True, "基金代码（6位，如 510050）"),
    ],
)

register_schema(FUND_ETF_BASIC_SCHEMA)
