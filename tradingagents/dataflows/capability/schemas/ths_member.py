"""ths_member 能力：同花顺板块成分股（双向查询）

粒度 reference：参考快照，无时间粒度（板块-成分股映射关系）。
双向语义：ts_code 入参=正向（板块→成分股），con_code 入参=反向（个股→所属板块），
两者至少传一；列 con_code/code 因 tushare 返回列差异两者并存，
接入对侧数据源时按返回实际列对齐。
"""

from ..schema import (
    GRAIN_REFERENCE,
    CapabilityField,
    CapabilityParam,
    CapabilitySchema,
)
from . import register_schema

THS_MEMBER_SCHEMA = CapabilitySchema(
    capability_id="ths_member",
    grain=GRAIN_REFERENCE,
    description="同花顺板块成分股（正向：板块→成分股；反向：个股→所属板块）",
    fields=[
        CapabilityField("ts_code", "str", True, "板块代码（TS 格式，如 885691.TI）"),
        CapabilityField("code", "str", False, "股票代码（部分返回形态为 code 列）"),
        CapabilityField("con_code", "str", False, "股票代码（tushare 原生列名）"),
        CapabilityField("name", "str", False, "股票名称"),
    ],
    params=[
        CapabilityParam("ts_code", "str", False, "板块代码（正向查询）"),
        CapabilityParam("con_code", "str", False, "股票代码（反向查询）"),
    ],
)

register_schema(THS_MEMBER_SCHEMA)
