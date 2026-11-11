"""daily_stats 能力：全市场每日涨跌家数统计

粒度 market_daily：全市场单条聚合记录，每交易日一行（Dict 形状返回，门面包装为单行 DataFrame）。
单位口径：up_ratio/down_ratio=%（0-100）、total/家数=家（实现内归一，与工具展示口径一致）。

双源口径说明：
- tushare（主源）：daily 接口全市场日线逐股聚合，11 字段齐全，total=成交个股数；
- akshare（降级源）：乐咕乐股赚钱效应快照（stock_market_activity_legu），
  仅覆盖最新一个交易日（快照日与请求日不一致时返回 None 降级），
  total=上涨+下跌+平盘+停牌（与 legu 自身"活跃度"分母同口径），
  涨跌幅分布 4 桶（up_gt5/up_3_5/down_gt5/down_3_5）快照无逐股明细无法聚合
  → 不输出，均为可选字段，门面补 NaN，消费方需容错。
"""

from ..schema import (
    GRAIN_MARKET_DAILY,
    CapabilityField,
    CapabilityParam,
    CapabilitySchema,
)
from . import register_schema

DAILY_STATS_SCHEMA = CapabilitySchema(
    capability_id="daily_stats",
    grain=GRAIN_MARKET_DAILY,
    description="全市场每日涨跌家数统计（单条聚合：涨跌平家数、涨跌占比%、涨跌幅分布家数）",
    fields=[
        CapabilityField("trade_date", "str", True, "交易日期 YYYYMMDD"),
        CapabilityField("total", "int", False, "全市场股票总数（家）"),
        CapabilityField("up_count", "int", False, "上涨家数（家）"),
        CapabilityField("down_count", "int", False, "下跌家数（家）"),
        CapabilityField("flat_count", "int", False, "平盘家数（家）"),
        CapabilityField("up_ratio", "float", False, "上涨占比（%）"),
        CapabilityField("down_ratio", "float", False, "下跌占比（%）"),
        CapabilityField("up_gt5", "int", False, "涨幅>5% 家数（家）"),
        CapabilityField("up_3_5", "int", False, "涨幅3-5% 家数（家）"),
        CapabilityField("down_gt5", "int", False, "跌幅>5% 家数（家）"),
        CapabilityField("down_3_5", "int", False, "跌幅3-5% 家数（家）"),
    ],
    params=[
        CapabilityParam("trade_date", "str", True, "交易日期 YYYYMMDD"),
    ],
)

register_schema(DAILY_STATS_SCHEMA)
