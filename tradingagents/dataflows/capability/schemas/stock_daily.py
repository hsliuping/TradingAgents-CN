"""stock_daily 能力：个股日线行情（前复权）

粒度 stock_daily：单只股票按日 OHLC 行情序列。

数据口径：
- 复权：前复权 qfq（tushare 走 ts.pro_bar(adj='qfq')，akshare 走
  stock_zh_a_hist(adjust='qfq')，两源口径一致；ETF 在 tushare 侧自动
  分派 fund_daily 不复权）。
- 单位：volume=手、amount=千元（tushare 口径）；akshare 东财接口
  volume 单位为股、amount 单位为元，实现内 /100、/1000 归一。

标准字段命名约定：本能力两源适配器均委托各自 provider 高层方法
get_historical_data（保留复权/分批/重试/降级语义），标准名对齐两源
高层方法已标准化的共同输出命名（date/volume），与 index_daily 的
"标准名=tushare 裸接口原生名"（trade_date/vol）不同——委托对象不同，
命名基准随之不同。

排序约定：date 升序（最旧在前，最新在末，调用方 iloc[-1] 取最新）——
两源高层方法原生升序；与 index_daily 的降序约定相反，系有意为之，
消费方（如技术指标工具）按 iloc[-1] 取最新读数。
"""

from ..schema import (
    GRAIN_STOCK_DAILY,
    CapabilityField,
    CapabilityParam,
    CapabilitySchema,
)
from . import register_schema

STOCK_DAILY_SCHEMA = CapabilitySchema(
    capability_id="stock_daily",
    grain=GRAIN_STOCK_DAILY,
    description="个股日线行情（OHLC/成交量/成交额，前复权，按 date 升序）",
    fields=[
        CapabilityField("ts_code", "str", False, "股票代码（TS 格式，如 600519.SH；akshare 映射 full_symbol）"),
        CapabilityField("date", "date", True, "交易日期（datetime 类型）"),
        CapabilityField("open", "float", True, "开盘价（元，前复权）"),
        CapabilityField("high", "float", True, "最高价（元，前复权）"),
        CapabilityField("low", "float", True, "最低价（元，前复权）"),
        CapabilityField("close", "float", True, "收盘价（元，前复权）"),
        CapabilityField("pre_close", "float", False, "昨收价（元，前复权）"),
        CapabilityField("change", "float", False, "涨跌额（元）"),
        CapabilityField("pct_chg", "float", False, "涨跌幅（%）"),
        CapabilityField("volume", "float", False, "成交量（手；akshare 实现内 /100 归一）"),
        CapabilityField("amount", "float", False, "成交额（千元；akshare 实现内 /1000 归一）"),
    ],
    params=[
        CapabilityParam("symbol", "str", True, "股票代码（6位数字或带交易所后缀）"),
        CapabilityParam("start_date", "str", True, "开始日期 YYYY-MM-DD"),
        CapabilityParam("end_date", "str", False, "结束日期 YYYY-MM-DD（缺省时 akshare 实现内兜底为当天）"),
    ],
)

register_schema(STOCK_DAILY_SCHEMA)
