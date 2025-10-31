"""
股票筛选相关的数据模型
"""

from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional, Union
from enum import Enum


class OperatorType(str, Enum):
    """筛选操作符类型"""
    GT = ">"           # 大于
    LT = "<"           # 小于
    GTE = ">="         # 大于等于
    LTE = "<="         # 小于等于
    EQ = "=="          # 等于
    NE = "!="          # 不等于
    BETWEEN = "between"  # 区间
    IN = "in"          # 包含于
    NOT_IN = "not_in"  # 不包含于
    CONTAINS = "contains"  # 字符串包含
    CROSS_UP = "cross_up"    # 技术指标：向上穿越
    CROSS_DOWN = "cross_down"  # 技术指标：向下穿越


class FieldType(str, Enum):
    """字段类型"""
    BASIC = "basic"        # 基础信息字段
    TECHNICAL = "technical"  # 技术指标字段
    FUNDAMENTAL = "fundamental"  # 基本面字段


class ScreeningCondition(BaseModel):
    """单个筛选条件"""
    field: str = Field(..., description="字段名")
    operator: OperatorType = Field(..., description="操作符")
    value: Union[float, int, str, List[Union[float, int, str]]] = Field(..., description="筛选值")
    field_type: Optional[FieldType] = Field(None, description="字段类型")
    
    class Config:
        use_enum_values = True


class ScreeningRequest(BaseModel):
    """筛选请求"""
    market: str = Field("CN", description="市场：CN/HK/US")
    date: Optional[str] = Field(None, description="交易日YYYY-MM-DD，缺省为最新")
    adj: str = Field("qfq", description="复权口径：qfq/hfq/none")
    
    # 筛选条件
    conditions: List[ScreeningCondition] = Field(default_factory=list, description="筛选条件列表")
    
    # 排序和分页
    order_by: Optional[List[Dict[str, str]]] = Field(None, description="排序条件")
    limit: int = Field(50, ge=1, le=500, description="返回数量限制")
    offset: int = Field(0, ge=0, description="偏移量")
    
    # 优化选项
    use_database_optimization: bool = Field(True, description="是否使用数据库优化")


class ScreeningResponse(BaseModel):
    """筛选响应"""
    total: int = Field(..., description="总数量")
    items: List[Dict[str, Any]] = Field(..., description="筛选结果")
    took_ms: Optional[int] = Field(None, description="耗时(毫秒)")
    optimization_used: Optional[str] = Field(None, description="使用的优化方式")
    source: Optional[str] = Field(None, description="数据源")


class FieldInfo(BaseModel):
    """字段信息"""
    name: str = Field(..., description="字段名")
    display_name: str = Field(..., description="显示名称")
    field_type: FieldType = Field(..., description="字段类型")
    data_type: str = Field(..., description="数据类型: number/string/date")
    description: str = Field("", description="字段描述")
    unit: Optional[str] = Field(None, description="单位")
    
    # 数值字段的统计信息
    min_value: Optional[float] = Field(None, description="最小值")
    max_value: Optional[float] = Field(None, description="最大值")
    avg_value: Optional[float] = Field(None, description="平均值")
    
    # 枚举字段的可选值
    available_values: Optional[List[str]] = Field(None, description="可选值列表")
    
    # 支持的操作符
    supported_operators: List[OperatorType] = Field(default_factory=list, description="支持的操作符")


class FieldStatistics(BaseModel):
    """字段统计信息"""
    field: str = Field(..., description="字段名")
    count: int = Field(..., description="有效数据数量")
    min_value: Optional[float] = Field(None, description="最小值")
    max_value: Optional[float] = Field(None, description="最大值")
    avg_value: Optional[float] = Field(None, description="平均值")
    median_value: Optional[float] = Field(None, description="中位数")
    std_value: Optional[float] = Field(None, description="标准差")


# 预定义的字段信息
BASIC_FIELDS_INFO = {
    "symbol": FieldInfo(
        name="symbol",
        display_name="股票代码",
        field_type=FieldType.BASIC,
        data_type="string",
        description="6位股票代码",
        supported_operators=[OperatorType.EQ, OperatorType.NE, OperatorType.IN, OperatorType.NOT_IN, OperatorType.CONTAINS]
    ),
    "code": FieldInfo(  # 兼容旧字段
        name="code",
        display_name="股票代码(已废弃)",
        field_type=FieldType.BASIC,
        data_type="string",
        description="6位股票代码(已废弃,使用symbol)",
        supported_operators=[OperatorType.EQ, OperatorType.NE, OperatorType.IN, OperatorType.NOT_IN, OperatorType.CONTAINS]
    ),
    "name": FieldInfo(
        name="name",
        display_name="股票名称",
        field_type=FieldType.BASIC,
        data_type="string",
        description="股票简称",
        supported_operators=[OperatorType.CONTAINS, OperatorType.EQ, OperatorType.NE]
    ),
    "industry": FieldInfo(
        name="industry",
        display_name="所属行业",
        field_type=FieldType.BASIC,
        data_type="string",
        description="申万行业分类",
        supported_operators=[OperatorType.EQ, OperatorType.NE, OperatorType.IN, OperatorType.NOT_IN, OperatorType.CONTAINS]
    ),
    "area": FieldInfo(
        name="area",
        display_name="所属地区",
        field_type=FieldType.BASIC,
        data_type="string",
        description="公司注册地区",
        supported_operators=[OperatorType.EQ, OperatorType.NE, OperatorType.IN, OperatorType.NOT_IN]
    ),
    "market": FieldInfo(
        name="market",
        display_name="所属市场",
        field_type=FieldType.BASIC,
        data_type="string",
        description="交易市场",
        supported_operators=[OperatorType.EQ, OperatorType.NE, OperatorType.IN, OperatorType.NOT_IN]
    ),
    "total_mv": FieldInfo(
        name="total_mv",
        display_name="总市值",
        field_type=FieldType.FUNDAMENTAL,
        data_type="number",
        description="总市值",
        unit="亿元",
        supported_operators=[OperatorType.GT, OperatorType.LT, OperatorType.GTE, OperatorType.LTE, OperatorType.BETWEEN]
    ),
    "circ_mv": FieldInfo(
        name="circ_mv",
        display_name="流通市值",
        field_type=FieldType.FUNDAMENTAL,
        data_type="number",
        description="流通市值",
        unit="亿元",
        supported_operators=[OperatorType.GT, OperatorType.LT, OperatorType.GTE, OperatorType.LTE, OperatorType.BETWEEN]
    ),
    "pe": FieldInfo(
        name="pe",
        display_name="市盈率",
        field_type=FieldType.FUNDAMENTAL,
        data_type="number",
        description="市盈率(PE)",
        unit="倍",
        supported_operators=[OperatorType.GT, OperatorType.LT, OperatorType.GTE, OperatorType.LTE, OperatorType.BETWEEN]
    ),
    "pb": FieldInfo(
        name="pb",
        display_name="市净率",
        field_type=FieldType.FUNDAMENTAL,
        data_type="number",
        description="市净率(PB)",
        unit="倍",
        supported_operators=[OperatorType.GT, OperatorType.LT, OperatorType.GTE, OperatorType.LTE, OperatorType.BETWEEN]
    ),
    "pe_ttm": FieldInfo(
        name="pe_ttm",
        display_name="滚动市盈率",
        field_type=FieldType.FUNDAMENTAL,
        data_type="number",
        description="滚动市盈率(PE TTM)",
        unit="倍",
        supported_operators=[OperatorType.GT, OperatorType.LT, OperatorType.GTE, OperatorType.LTE, OperatorType.BETWEEN]
    ),
    "pb_mrq": FieldInfo(
        name="pb_mrq",
        display_name="最新市净率",
        field_type=FieldType.FUNDAMENTAL,
        data_type="number",
        description="最新市净率(PB MRQ)",
        unit="倍",
        supported_operators=[OperatorType.GT, OperatorType.LT, OperatorType.GTE, OperatorType.LTE, OperatorType.BETWEEN]
    ),
    "roe": FieldInfo(
        name="roe",
        display_name="净资产收益率",
        field_type=FieldType.FUNDAMENTAL,
        data_type="number",
        description="净资产收益率(最近一期，%)",
        unit="%",
        supported_operators=[OperatorType.GT, OperatorType.LT, OperatorType.GTE, OperatorType.LTE, OperatorType.BETWEEN]
    ),
    "turnover_rate": FieldInfo(
        name="turnover_rate",
        display_name="换手率",
        field_type=FieldType.TECHNICAL,
        data_type="number",
        description="换手率",
        unit="%",
        supported_operators=[OperatorType.GT, OperatorType.LT, OperatorType.GTE, OperatorType.LTE, OperatorType.BETWEEN]
    ),
    "volume_ratio": FieldInfo(
        name="volume_ratio",
        display_name="量比",
        field_type=FieldType.TECHNICAL,
        data_type="number",
        description="量比",
        unit="倍",
        supported_operators=[OperatorType.GT, OperatorType.LT, OperatorType.GTE, OperatorType.LTE, OperatorType.BETWEEN]
    ),

    # 价格数据字段
    "close": FieldInfo(
        name="close",
        display_name="收盘价",
        field_type=FieldType.TECHNICAL,
        data_type="number",
        description="最新收盘价",
        unit="元",
        supported_operators=[OperatorType.GT, OperatorType.LT, OperatorType.GTE, OperatorType.LTE, OperatorType.BETWEEN]
    ),
    "pct_chg": FieldInfo(
        name="pct_chg",
        display_name="涨跌幅",
        field_type=FieldType.TECHNICAL,
        data_type="number",
        description="涨跌幅",
        unit="%",
        supported_operators=[OperatorType.GT, OperatorType.LT, OperatorType.GTE, OperatorType.LTE, OperatorType.BETWEEN]
    ),
    "amount": FieldInfo(
        name="amount",
        display_name="成交额",
        field_type=FieldType.TECHNICAL,
        data_type="number",
        description="成交额",
        unit="万元",
        supported_operators=[OperatorType.GT, OperatorType.LT, OperatorType.GTE, OperatorType.LTE, OperatorType.BETWEEN]
    ),

    # 技术指标字段
    "ma20": FieldInfo(
        name="ma20",
        display_name="20日均线",
        field_type=FieldType.TECHNICAL,
        data_type="number",
        description="20日移动平均线",
        unit="元",
        supported_operators=[OperatorType.GT, OperatorType.LT, OperatorType.GTE, OperatorType.LTE, OperatorType.BETWEEN]
    ),
    "rsi14": FieldInfo(
        name="rsi14",
        display_name="RSI指标",
        field_type=FieldType.TECHNICAL,
        data_type="number",
        description="14日相对强弱指标",
        unit="",
        supported_operators=[OperatorType.GT, OperatorType.LT, OperatorType.GTE, OperatorType.LTE, OperatorType.BETWEEN]
    ),
    "kdj_k": FieldInfo(
        name="kdj_k",
        display_name="KDJ-K",
        field_type=FieldType.TECHNICAL,
        data_type="number",
        description="KDJ指标K值",
        unit="",
        supported_operators=[OperatorType.GT, OperatorType.LT, OperatorType.GTE, OperatorType.LTE, OperatorType.BETWEEN]
    ),
    "kdj_d": FieldInfo(
        name="kdj_d",
        display_name="KDJ-D",
        field_type=FieldType.TECHNICAL,
        data_type="number",
        description="KDJ指标D值",
        unit="",
        supported_operators=[OperatorType.GT, OperatorType.LT, OperatorType.GTE, OperatorType.LTE, OperatorType.BETWEEN]
    ),
    "kdj_j": FieldInfo(
        name="kdj_j",
        display_name="KDJ-J",
        field_type=FieldType.TECHNICAL,
        data_type="number",
        description="KDJ指标J值",
        unit="",
        supported_operators=[OperatorType.GT, OperatorType.LT, OperatorType.GTE, OperatorType.LTE, OperatorType.BETWEEN]
    ),
    "dif": FieldInfo(
        name="dif",
        display_name="MACD-DIF",
        field_type=FieldType.TECHNICAL,
        data_type="number",
        description="MACD指标DIF值",
        unit="",
        supported_operators=[OperatorType.GT, OperatorType.LT, OperatorType.GTE, OperatorType.LTE, OperatorType.BETWEEN]
    ),
    "dea": FieldInfo(
        name="dea",
        display_name="MACD-DEA",
        field_type=FieldType.TECHNICAL,
        data_type="number",
        description="MACD指标DEA值",
        unit="",
        supported_operators=[OperatorType.GT, OperatorType.LT, OperatorType.GTE, OperatorType.LTE, OperatorType.BETWEEN]
    ),
    "macd_hist": FieldInfo(
        name="macd_hist",
        display_name="MACD柱状图",
        field_type=FieldType.TECHNICAL,
        data_type="number",
        description="MACD柱状图值",
        unit="",
        supported_operators=[OperatorType.GT, OperatorType.LT, OperatorType.GTE, OperatorType.LTE, OperatorType.BETWEEN]
    ),
}
