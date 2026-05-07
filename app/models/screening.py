"""
股票筛选相关的数据模型
"""

from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional, Union
from enum import Enum

from core.skill_runtime.factor_schema import P0_PUBLIC_SCREENING_FIELDS, get_factor_field_schema


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


_NUMERIC_OPERATORS = [
    OperatorType.GT,
    OperatorType.LT,
    OperatorType.GTE,
    OperatorType.LTE,
    OperatorType.BETWEEN,
]
_STRING_OPERATORS = [
    OperatorType.EQ,
    OperatorType.NE,
    OperatorType.IN,
    OperatorType.NOT_IN,
    OperatorType.CONTAINS,
]
_BOOLEAN_OPERATORS = [OperatorType.EQ, OperatorType.NE]


def _get_supported_operators(data_type: str) -> List[OperatorType]:
    if data_type == "number":
        return list(_NUMERIC_OPERATORS)
    if data_type == "boolean":
        return list(_BOOLEAN_OPERATORS)
    return list(_STRING_OPERATORS)


def _build_p0_screening_field_info() -> Dict[str, "FieldInfo"]:
    field_info_map: Dict[str, FieldInfo] = {}
    for field_name in P0_PUBLIC_SCREENING_FIELDS:
        schema = get_factor_field_schema(field_name)
        if schema is None:
            continue
        field_info_map[field_name] = FieldInfo(
            name=schema.field_name,
            display_name=schema.display_name,
            field_type=FieldType.FUNDAMENTAL,
            data_type=schema.data_type,
            description=schema.description,
            unit=schema.screening_unit or schema.unit or None,
            supported_operators=_get_supported_operators(schema.data_type),
        )
    return field_info_map


def _dedupe_fields(fields: List[str]) -> List[str]:
    return list(dict.fromkeys(fields))


# 预定义的字段信息
BASIC_FIELDS_INFO = {
    "keyword": FieldInfo(
        name="keyword",
        display_name="关键词",
        field_type=FieldType.BASIC,
        data_type="string",
        description="股票代码或名称",
        supported_operators=[OperatorType.CONTAINS]
    ),
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
    "ps_ttm": FieldInfo(
        name="ps_ttm",
        display_name="滚动市销率",
        field_type=FieldType.FUNDAMENTAL,
        data_type="number",
        description="滚动市销率(PS TTM)",
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
    "roa": FieldInfo(
        name="roa",
        display_name="总资产收益率",
        field_type=FieldType.FUNDAMENTAL,
        data_type="number",
        description="总资产收益率(ROA，%)",
        unit="%",
        supported_operators=[OperatorType.GT, OperatorType.LT, OperatorType.GTE, OperatorType.LTE, OperatorType.BETWEEN]
    ),
    "gross_margin": FieldInfo(
        name="gross_margin",
        display_name="毛利率",
        field_type=FieldType.FUNDAMENTAL,
        data_type="number",
        description="销售毛利率(%)",
        unit="%",
        supported_operators=[OperatorType.GT, OperatorType.LT, OperatorType.GTE, OperatorType.LTE, OperatorType.BETWEEN]
    ),
    "netprofit_margin": FieldInfo(
        name="netprofit_margin",
        display_name="净利率",
        field_type=FieldType.FUNDAMENTAL,
        data_type="number",
        description="销售净利率(%)",
        unit="%",
        supported_operators=[OperatorType.GT, OperatorType.LT, OperatorType.GTE, OperatorType.LTE, OperatorType.BETWEEN]
    ),
    "debt_to_assets": FieldInfo(
        name="debt_to_assets",
        display_name="资产负债率",
        field_type=FieldType.FUNDAMENTAL,
        data_type="number",
        description="资产负债率(%)",
        unit="%",
        supported_operators=[OperatorType.GT, OperatorType.LT, OperatorType.GTE, OperatorType.LTE, OperatorType.BETWEEN]
    ),
    "assets_to_eqt": FieldInfo(
        name="assets_to_eqt",
        display_name="权益乘数",
        field_type=FieldType.FUNDAMENTAL,
        data_type="number",
        description="权益乘数(总资产/股东权益)",
        unit="倍",
        supported_operators=[OperatorType.GT, OperatorType.LT, OperatorType.GTE, OperatorType.LTE, OperatorType.BETWEEN]
    ),
    "current_ratio": FieldInfo(
        name="current_ratio",
        display_name="流动比率",
        field_type=FieldType.FUNDAMENTAL,
        data_type="number",
        description="流动比率(流动资产/流动负债)",
        unit="倍",
        supported_operators=[OperatorType.GT, OperatorType.LT, OperatorType.GTE, OperatorType.LTE, OperatorType.BETWEEN]
    ),
    "quick_ratio": FieldInfo(
        name="quick_ratio",
        display_name="速动比率",
        field_type=FieldType.FUNDAMENTAL,
        data_type="number",
        description="速动比率",
        unit="倍",
        supported_operators=[OperatorType.GT, OperatorType.LT, OperatorType.GTE, OperatorType.LTE, OperatorType.BETWEEN]
    ),
    "cash_ratio": FieldInfo(
        name="cash_ratio",
        display_name="现金比率",
        field_type=FieldType.FUNDAMENTAL,
        data_type="number",
        description="现金比率",
        unit="倍",
        supported_operators=[OperatorType.GT, OperatorType.LT, OperatorType.GTE, OperatorType.LTE, OperatorType.BETWEEN]
    ),
    "dividend_yield": FieldInfo(
        name="dividend_yield",
        display_name="股息率",
        field_type=FieldType.FUNDAMENTAL,
        data_type="number",
        description="近12个月股息率(%)",
        unit="%",
        supported_operators=[OperatorType.GT, OperatorType.LT, OperatorType.GTE, OperatorType.LTE, OperatorType.BETWEEN]
    ),
    "peg": FieldInfo(
        name="peg",
        display_name="PEG",
        field_type=FieldType.FUNDAMENTAL,
        data_type="number",
        description="PEG=PE TTM/净利润同比增速",
        unit="倍/%",
        supported_operators=[OperatorType.GT, OperatorType.LT, OperatorType.GTE, OperatorType.LTE, OperatorType.BETWEEN]
    ),
    "roic": FieldInfo(
        name="roic",
        display_name="投入资本回报率",
        field_type=FieldType.FUNDAMENTAL,
        data_type="number",
        description="ROIC(保守代理口径，%)",
        unit="%",
        supported_operators=[OperatorType.GT, OperatorType.LT, OperatorType.GTE, OperatorType.LTE, OperatorType.BETWEEN]
    ),
    "cash_conversion": FieldInfo(
        name="cash_conversion",
        display_name="利润现金转换率",
        field_type=FieldType.FUNDAMENTAL,
        data_type="number",
        description="经营现金流/净利润",
        unit="倍",
        supported_operators=[OperatorType.GT, OperatorType.LT, OperatorType.GTE, OperatorType.LTE, OperatorType.BETWEEN]
    ),
    "accrual_ratio": FieldInfo(
        name="accrual_ratio",
        display_name="应计利润比率",
        field_type=FieldType.FUNDAMENTAL,
        data_type="number",
        description="(净利润-经营现金流)/总资产，百分比输出",
        unit="%",
        supported_operators=[OperatorType.GT, OperatorType.LT, OperatorType.GTE, OperatorType.LTE, OperatorType.BETWEEN]
    ),
    "asset_turnover": FieldInfo(
        name="asset_turnover",
        display_name="资产周转率",
        field_type=FieldType.FUNDAMENTAL,
        data_type="number",
        description="营收/总资产，当前使用最新总资产保守代理",
        unit="倍",
        supported_operators=[OperatorType.GT, OperatorType.LT, OperatorType.GTE, OperatorType.LTE, OperatorType.BETWEEN]
    ),
    "gross_profit_to_assets": FieldInfo(
        name="gross_profit_to_assets",
        display_name="毛利资产比",
        field_type=FieldType.FUNDAMENTAL,
        data_type="number",
        description="毛利润/总资产，百分比输出",
        unit="%",
        supported_operators=[OperatorType.GT, OperatorType.LT, OperatorType.GTE, OperatorType.LTE, OperatorType.BETWEEN]
    ),
    "interest_coverage": FieldInfo(
        name="interest_coverage",
        display_name="利息保障倍数",
        field_type=FieldType.FUNDAMENTAL,
        data_type="number",
        description="oper_profit/fin_exp 的保守代理口径",
        unit="倍",
        supported_operators=[OperatorType.GT, OperatorType.LT, OperatorType.GTE, OperatorType.LTE, OperatorType.BETWEEN]
    ),
    "inventory_turnover": FieldInfo(
        name="inventory_turnover",
        display_name="存货周转率",
        field_type=FieldType.FUNDAMENTAL,
        data_type="number",
        description="营业成本/存货，当前使用最新存货余额保守代理",
        unit="倍",
        supported_operators=[OperatorType.GT, OperatorType.LT, OperatorType.GTE, OperatorType.LTE, OperatorType.BETWEEN]
    ),
    "receivable_turnover": FieldInfo(
        name="receivable_turnover",
        display_name="应收账款周转率",
        field_type=FieldType.FUNDAMENTAL,
        data_type="number",
        description="营收/应收账款，当前使用最新应收账款余额保守代理",
        unit="倍",
        supported_operators=[OperatorType.GT, OperatorType.LT, OperatorType.GTE, OperatorType.LTE, OperatorType.BETWEEN]
    ),
    "net_cash_position": FieldInfo(
        name="net_cash_position",
        display_name="净现金头寸",
        field_type=FieldType.FUNDAMENTAL,
        data_type="number",
        description="(money_cap-total_ncl)/total_assets 的保守代理，百分比输出",
        unit="%",
        supported_operators=[OperatorType.GT, OperatorType.LT, OperatorType.GTE, OperatorType.LTE, OperatorType.BETWEEN]
    ),
    "piotroski_f_score": FieldInfo(
        name="piotroski_f_score",
        display_name="Piotroski F-Score",
        field_type=FieldType.FUNDAMENTAL,
        data_type="number",
        description="基于近两期财务信号的 9 分制质量评分",
        unit="分",
        supported_operators=[OperatorType.GT, OperatorType.LT, OperatorType.GTE, OperatorType.LTE, OperatorType.BETWEEN]
    ),
    "altman_z_score": FieldInfo(
        name="altman_z_score",
        display_name="Altman Z-Score",
        field_type=FieldType.FUNDAMENTAL,
        data_type="number",
        description="财务困境风险评分，当前使用 raw_data 中的留存收益与 EBIT 口径",
        unit="分",
        supported_operators=[OperatorType.GT, OperatorType.LT, OperatorType.GTE, OperatorType.LTE, OperatorType.BETWEEN]
    ),
    "beneish_m_score": FieldInfo(
        name="beneish_m_score",
        display_name="Beneish M-Score",
        field_type=FieldType.FUNDAMENTAL,
        data_type="number",
        description="盈余操纵风险评分，基于近两期 8 指标模型",
        unit="分",
        supported_operators=[OperatorType.GT, OperatorType.LT, OperatorType.GTE, OperatorType.LTE, OperatorType.BETWEEN]
    ),
    "revenue_ttm": FieldInfo(
        name="revenue_ttm",
        display_name="滚动营收",
        field_type=FieldType.FUNDAMENTAL,
        data_type="number",
        description="滚动12个月营业收入",
        unit="元",
        supported_operators=[OperatorType.GT, OperatorType.LT, OperatorType.GTE, OperatorType.LTE, OperatorType.BETWEEN]
    ),
    "revenue_yoy": FieldInfo(
        name="revenue_yoy",
        display_name="营收同比",
        field_type=FieldType.FUNDAMENTAL,
        data_type="number",
        description="最新报告期相对上年同季的营收同比增速",
        unit="%",
        supported_operators=[OperatorType.GT, OperatorType.LT, OperatorType.GTE, OperatorType.LTE, OperatorType.BETWEEN]
    ),
    "revenue_cagr_3y": FieldInfo(
        name="revenue_cagr_3y",
        display_name="营收三年复合增速",
        field_type=FieldType.FUNDAMENTAL,
        data_type="number",
        description="同季三年前对比的三年营收 CAGR",
        unit="%",
        supported_operators=[OperatorType.GT, OperatorType.LT, OperatorType.GTE, OperatorType.LTE, OperatorType.BETWEEN]
    ),
    "net_profit_ttm": FieldInfo(
        name="net_profit_ttm",
        display_name="滚动净利润",
        field_type=FieldType.FUNDAMENTAL,
        data_type="number",
        description="滚动12个月净利润",
        unit="元",
        supported_operators=[OperatorType.GT, OperatorType.LT, OperatorType.GTE, OperatorType.LTE, OperatorType.BETWEEN]
    ),
    "net_profit_yoy": FieldInfo(
        name="net_profit_yoy",
        display_name="净利润同比",
        field_type=FieldType.FUNDAMENTAL,
        data_type="number",
        description="最新报告期相对上年同季的净利润同比增速",
        unit="%",
        supported_operators=[OperatorType.GT, OperatorType.LT, OperatorType.GTE, OperatorType.LTE, OperatorType.BETWEEN]
    ),
    "profit_cagr_3y": FieldInfo(
        name="profit_cagr_3y",
        display_name="净利润三年复合增速",
        field_type=FieldType.FUNDAMENTAL,
        data_type="number",
        description="同季三年前对比的三年净利润 CAGR",
        unit="%",
        supported_operators=[OperatorType.GT, OperatorType.LT, OperatorType.GTE, OperatorType.LTE, OperatorType.BETWEEN]
    ),
    "oper_profit_yoy": FieldInfo(
        name="oper_profit_yoy",
        display_name="营业利润同比",
        field_type=FieldType.FUNDAMENTAL,
        data_type="number",
        description="最新报告期相对上年同季的营业利润同比增速",
        unit="%",
        supported_operators=[OperatorType.GT, OperatorType.LT, OperatorType.GTE, OperatorType.LTE, OperatorType.BETWEEN]
    ),
    "n_cashflow_act": FieldInfo(
        name="n_cashflow_act",
        display_name="经营现金流",
        field_type=FieldType.FUNDAMENTAL,
        data_type="number",
        description="经营活动产生的现金流量净额",
        unit="元",
        supported_operators=[OperatorType.GT, OperatorType.LT, OperatorType.GTE, OperatorType.LTE, OperatorType.BETWEEN]
    ),
    "fcf": FieldInfo(
        name="fcf",
        display_name="自由现金流",
        field_type=FieldType.FUNDAMENTAL,
        data_type="number",
        description="自由现金流(保守代理口径)=经营现金流+投资现金流",
        unit="元",
        supported_operators=[OperatorType.GT, OperatorType.LT, OperatorType.GTE, OperatorType.LTE, OperatorType.BETWEEN]
    ),
    "fcf_yield": FieldInfo(
        name="fcf_yield",
        display_name="自由现金流收益率",
        field_type=FieldType.FUNDAMENTAL,
        data_type="number",
        description="自由现金流收益率(%)",
        unit="%",
        supported_operators=[OperatorType.GT, OperatorType.LT, OperatorType.GTE, OperatorType.LTE, OperatorType.BETWEEN]
    ),
    "fcf_margin": FieldInfo(
        name="fcf_margin",
        display_name="自由现金流率",
        field_type=FieldType.FUNDAMENTAL,
        data_type="number",
        description="自由现金流/营收，百分比输出",
        unit="%",
        supported_operators=[OperatorType.GT, OperatorType.LT, OperatorType.GTE, OperatorType.LTE, OperatorType.BETWEEN]
    ),
    "ocf_yield": FieldInfo(
        name="ocf_yield",
        display_name="经营现金流收益率",
        field_type=FieldType.FUNDAMENTAL,
        data_type="number",
        description="经营现金流/总市值，百分比输出",
        unit="%",
        supported_operators=[OperatorType.GT, OperatorType.LT, OperatorType.GTE, OperatorType.LTE, OperatorType.BETWEEN]
    ),
    "report_period": FieldInfo(
        name="report_period",
        display_name="财报期",
        field_type=FieldType.FUNDAMENTAL,
        data_type="string",
        description="最新财报报告期，如 20250930",
        supported_operators=[OperatorType.EQ, OperatorType.NE, OperatorType.IN, OperatorType.NOT_IN]
    ),
    "net_working_capital": FieldInfo(
        name="net_working_capital",
        display_name="净营运资本",
        field_type=FieldType.FUNDAMENTAL,
        data_type="number",
        description="净营运资本(亿元)=流动资产-流动负债",
        unit="亿元",
        supported_operators=[OperatorType.GT, OperatorType.LT, OperatorType.GTE, OperatorType.LTE, OperatorType.BETWEEN]
    ),
    "working_capital_change": FieldInfo(
        name="working_capital_change",
        display_name="营运资本变动",
        field_type=FieldType.FUNDAMENTAL,
        data_type="number",
        description="最近两期净营运资本变化额",
        unit="亿元",
        supported_operators=[OperatorType.GT, OperatorType.LT, OperatorType.GTE, OperatorType.LTE, OperatorType.BETWEEN]
    ),
    "is_st": FieldInfo(
        name="is_st",
        display_name="ST状态",
        field_type=FieldType.BASIC,
        data_type="string",
        description="是否为ST或*ST股票",
        supported_operators=[OperatorType.EQ, OperatorType.NE]
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

    # 价格数据字段（现在在视图中，可以直接从数据库查询）
    "close": FieldInfo(
        name="close",
        display_name="收盘价",
        field_type=FieldType.FUNDAMENTAL,  # 改为 FUNDAMENTAL，因为现在在视图中可以直接查询
        data_type="number",
        description="最新收盘价",
        unit="元",
        supported_operators=[OperatorType.GT, OperatorType.LT, OperatorType.GTE, OperatorType.LTE, OperatorType.BETWEEN]
    ),
    "pct_chg": FieldInfo(
        name="pct_chg",
        display_name="涨跌幅",
        field_type=FieldType.FUNDAMENTAL,  # 改为 FUNDAMENTAL，因为现在在视图中可以直接查询
        data_type="number",
        description="涨跌幅",
        unit="%",
        supported_operators=[OperatorType.GT, OperatorType.LT, OperatorType.GTE, OperatorType.LTE, OperatorType.BETWEEN]
    ),
    "amount": FieldInfo(
        name="amount",
        display_name="成交额",
        field_type=FieldType.FUNDAMENTAL,  # 改为 FUNDAMENTAL，因为现在在视图中可以直接查询
        data_type="number",
        description="成交额",
        unit="元",
        supported_operators=[OperatorType.GT, OperatorType.LT, OperatorType.GTE, OperatorType.LTE, OperatorType.BETWEEN]
    ),
    "volume": FieldInfo(
        name="volume",
        display_name="成交量",
        field_type=FieldType.FUNDAMENTAL,  # 改为 FUNDAMENTAL，因为现在在视图中可以直接查询
        data_type="number",
        description="成交量",
        unit="手",
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


# P0 公共基本面字段统一从 factor_schema 派生，避免与 runtime/schema 漂移。
BASIC_FIELDS_INFO.update(_build_p0_screening_field_info())


SCREENING_FINANCIAL_CATEGORY_FIELDS = _dedupe_fields(
    ["total_mv", "circ_mv", *P0_PUBLIC_SCREENING_FIELDS, "report_period", "is_st"]
)

