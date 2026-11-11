"""stock_industry 能力：股票所属行业（单条属性）

粒度 reference：参考快照，无时间粒度（个股→行业的静态映射）。
返回 Dict 单条形状（ts_code/industry 两个标量键），门面包装为单行
DataFrame 后标准化（见 facade 降级语义表）。
行业口径为 tushare stock_basic 的 industry 字段（申万口径前生），
接入对侧数据源时必须核对行业分类口径。
"""

from ..schema import (
    GRAIN_REFERENCE,
    CapabilityField,
    CapabilityParam,
    CapabilitySchema,
)
from . import register_schema

STOCK_INDUSTRY_SCHEMA = CapabilitySchema(
    capability_id="stock_industry",
    grain=GRAIN_REFERENCE,
    description="股票所属行业（单条属性，tushare stock_basic 行业口径）",
    fields=[
        CapabilityField("ts_code", "str", True, "股票代码（TS 格式，实现内规范化入参）"),
        CapabilityField("industry", "str", True, "所属行业名称（如 银行）"),
    ],
    params=[
        CapabilityParam("ts_code", "str", True, "股票代码（6 位代码或 TS 格式，实现内规范化）"),
    ],
)

register_schema(STOCK_INDUSTRY_SCHEMA)
