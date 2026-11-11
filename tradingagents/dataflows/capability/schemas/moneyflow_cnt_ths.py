"""moneyflow_cnt_ths 能力：同花顺概念板块资金流向

粒度 index_daily：板块指数粒度按日时间序列。
单位口径：net_amount/net_buy_amount/net_sell_amount=亿元
（tushare moneyflow_cnt_ths 原始单位）；接入对侧数据源时必须核对单位。
实现注意：概念板块约 387 个/天，tushare 单次上限 5000 条，
范围查询超 12 天需分段拉取合并（provider 实现内处理）。
"""

from ..schema import (
    GRAIN_INDEX_DAILY,
    CapabilityField,
    CapabilityParam,
    CapabilitySchema,
)
from . import register_schema

MONEYFLOW_CNT_THS_SCHEMA = CapabilitySchema(
    capability_id="moneyflow_cnt_ths",
    grain=GRAIN_INDEX_DAILY,
    description="同花顺概念板块资金流向（净流入/买卖额/领涨股，支持单日与范围查询）",
    fields=[
        CapabilityField("ts_code", "str", True, "板块代码（TS 格式，如 886034.TI）"),
        CapabilityField("trade_date", "str", False, "交易日期 YYYYMMDD（范围查询返回）"),
        CapabilityField("name", "str", True, "概念名称（如 人工智能）"),
        CapabilityField("lead_stock", "str", False, "领涨股名称"),
        CapabilityField("close_price", "float", False, "板块指数收盘（点）"),
        CapabilityField("pct_change", "float", False, "涨跌幅（%）"),
        CapabilityField("net_amount", "float", True, "净流入金额（亿元）"),
        CapabilityField("net_buy_amount", "float", False, "买入金额（亿元）"),
        CapabilityField("net_sell_amount", "float", False, "卖出金额（亿元）"),
        CapabilityField("company_num", "int", False, "成分股数量"),
    ],
    params=[
        CapabilityParam("trade_date", "str", False, "交易日期 YYYYMMDD（单日查询）"),
        CapabilityParam("ts_code", "str", False, "板块代码（TS 格式，查单板块）"),
        CapabilityParam("start_date", "str", False, "开始日期 YYYYMMDD（范围查询）"),
        CapabilityParam("end_date", "str", False, "结束日期 YYYYMMDD（范围查询）"),
    ],
)

register_schema(MONEYFLOW_CNT_THS_SCHEMA)
