"""financial_balance 能力：个股资产负债表（按报告期）

粒度 stock_period：一行一个报告期（end_date），按报告期降序返回。
单位口径：金额字段单位=元（与 tushare 原生一致）。
标准字段名沿用 tushare 资产负债表原生字段名，akshare（东财 EM）经 field_mapping 映射。

多源口径说明：
- tushare（主源）：balancesheet 接口逐报告期拉取，字段齐全；
- akshare（降级源）：东财 EM 资产负债表（stock_balance_sheet_by_report_em），
  大写字段经 field_mapping 映射为标准名，未覆盖字段门面补 NaN，消费方需容错；
- local（降级源）：MongoDB stock_financial_data 缓存的 balance_sheet 桶，
  字段名经 field_mapping 对齐 tushare 口径。
"""

from ..schema import (
    GRAIN_STOCK_PERIOD,
    CapabilityField,
    CapabilityParam,
    CapabilitySchema,
)
from . import register_schema

FINANCIAL_BALANCE_SCHEMA = CapabilitySchema(
    capability_id="financial_balance",
    grain=GRAIN_STOCK_PERIOD,
    description="个股资产负债表（按报告期：总资产/总负债/归母权益/流动资产/流动负债/货币资金）",
    fields=[
        CapabilityField("end_date", "str", True, "报告期 YYYYMMDD（如 20260930）"),
        CapabilityField("ann_date", "str", False, "公告日期 YYYYMMDD"),
        CapabilityField("f_ann_date", "str", False, "实际公告日期 YYYYMMDD"),
        CapabilityField("total_assets", "float", False, "资产总计（元）"),
        CapabilityField("total_liab", "float", False, "负债合计（元）"),
        CapabilityField("total_hldr_eqy_exc_min_int", "float", False, "归属母公司股东权益（不含少数股东，元）"),
        CapabilityField("total_cur_assets", "float", False, "流动资产合计（元）"),
        CapabilityField("total_cur_liab", "float", False, "流动负债合计（元）"),
        CapabilityField("money_cap", "float", False, "货币资金（元）"),
    ],
    params=[
        CapabilityParam("symbol", "str", True, "股票代码（6位数字，如 600519）"),
        CapabilityParam("limit", "int", False, "返回最近 N 个报告期（默认全部可用）"),
    ],
)

register_schema(FINANCIAL_BALANCE_SCHEMA)
