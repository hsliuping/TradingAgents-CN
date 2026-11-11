"""financial_indicators 能力：个股财务指标（按报告期）

粒度 stock_period：一行一个报告期（end_date），按报告期降序返回。
单位口径：roe/roe_dt/roa/grossprofit_margin/netprofit_margin/debt_to_assets 单位=%，
current_ratio 为倍数（无量纲）。

多源口径说明：
- tushare（主源）：fina_indicator 接口逐报告期拉取，字段齐全；
- local（降级源）：MongoDB stock_financial_data 缓存的
  financial_indicators/main_indicators 桶，字段名经 field_mapping 对齐 tushare 口径；
- akshare 不注册本能力：东财 EM 摘要接口（stock_financial_abstract）为
  「指标名×报告期」纵表，指标名集合随个股漂移，无法稳定映射为固定宽表列，
  不满足门面「一行一报告期」的粒度约束（宁缺勿造，降级链在此断开）。
"""

from ..schema import (
    GRAIN_STOCK_PERIOD,
    CapabilityField,
    CapabilityParam,
    CapabilitySchema,
)
from . import register_schema

FINANCIAL_INDICATORS_SCHEMA = CapabilitySchema(
    capability_id="financial_indicators",
    grain=GRAIN_STOCK_PERIOD,
    description="个股财务指标（按报告期：ROE/扣非ROE/ROA/毛利率/净利率/资产负债率/流动比率）",
    fields=[
        CapabilityField("end_date", "str", True, "报告期 YYYYMMDD（如 20260930）"),
        CapabilityField("ann_date", "str", False, "公告日期 YYYYMMDD"),
        CapabilityField("f_ann_date", "str", False, "实际公告日期 YYYYMMDD"),
        CapabilityField("roe", "float", False, "净资产收益率（%）"),
        CapabilityField("roe_dt", "float", False, "净资产收益率-扣除非经常损益（%）"),
        CapabilityField("roa", "float", False, "总资产报酬率（%）"),
        CapabilityField("grossprofit_margin", "float", False, "销售毛利率（%）"),
        CapabilityField("netprofit_margin", "float", False, "销售净利率（%）"),
        CapabilityField("debt_to_assets", "float", False, "资产负债率（%）"),
        CapabilityField("current_ratio", "float", False, "流动比率（倍）"),
    ],
    params=[
        CapabilityParam("symbol", "str", True, "股票代码（6位数字，如 600519）"),
        CapabilityParam("limit", "int", False, "返回最近 N 个报告期（默认全部可用）"),
    ],
)

register_schema(FINANCIAL_INDICATORS_SCHEMA)
