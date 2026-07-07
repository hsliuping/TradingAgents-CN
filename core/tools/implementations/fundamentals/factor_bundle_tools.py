"""标准化因子 bundle 工具。"""

import json
import logging
from typing import Annotated

from langchain_core.tools import tool

from core.skill_runtime import (
    get_fundamental_factor_snapshot,
    get_growth_cashflow_factor_bundle,
    get_quality_factor_bundle,
    get_value_factor_bundle,
)
from core.tools.base import register_tool

logger = logging.getLogger(__name__)


def _json_response(payload: dict) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, default=str)


@tool
@register_tool(
    tool_id="get_value_factor_bundle_tool",
    name="价值因子包",
    description=(
        "返回股票的 value_core 标准化价值因子包。"
        "适合一次性获取 PE、PE_TTM、PB、PB_MRQ、PS_TTM、股息率、PEG、行业 PE/PB 中位数等估值指标，"
        "并附带缺失因子、回退告警和计算说明。"
        "这里的“价值/估值因子”是横截面估值输入，不直接生成 DCF 目标价、历史估值分位或完整投资评级。"
    ),
    category="fundamentals",
    is_online=False,
    auto_register=True,
    timeout_tier="light",
    when_to_use=(
        "当 Agent 需要做估值判断、便宜/贵的初筛、PE/PB/PEG 横向比较、行业估值对比时使用。"
        "如果需求是获取价值类指标集合，而不是单独读某一个原始字段，优先绑定这个工具。"
    ),
    when_not_to_use=(
        "不适合做利润表趋势、偿债能力、现金流质量分析；"
        "也不适合做技术面判断、DCF 目标价或历史估值分位。需要质量因子请用 get_quality_factor_bundle_tool，"
        "需要成长/现金流请用 get_growth_cashflow_factor_bundle_tool，需要历史分位请用 get_historical_valuation_percentile_tool。"
    ),
    returns=(
        "返回 JSON 字符串，结构包含 symbol、name、industry、current_price、bundle=value_core、"
        "factors、factor_warnings、industry_samples、calculation_notes、missing_factors。"
        "factors 中重点字段包括 pe、pe_ttm、pb、pb_mrq、ps_ttm、dividend_yield、peg、industry_pe_median、industry_pb_median。"
    ),
    example="get_value_factor_bundle_tool(symbol='600519')",
    related_tools=[
        "get_quality_factor_bundle_tool",
        "get_growth_cashflow_factor_bundle_tool",
        "get_fundamental_factor_snapshot_tool",
        "get_peer_comparison",
    ],
)
def get_value_factor_bundle_tool(
    symbol: Annotated[str, "A 股股票代码，如 600519、000001"]
) -> str:
    """获取标准化价值因子包。

    Args:
        symbol: A 股股票代码，如 "600519"、"000001"

    Returns:
        str: JSON 字符串，字段说明——
            status: 状态（仅在异常时为 "error"）
            symbol: 标准化后的股票代码
            name: 股票名称
            industry: 所属行业
            current_price: 当前价格
            report_period: 报告期
            data_source: 数据来源
            bundle: 因子包标识，固定为 "value_core"
            factors: dict 价值因子集合——
                — pe: 市盈率
                — pe_ttm: TTM市盈率
                — pb: 市净率
                — pb_mrq: MRQ市净率
                — ps_ttm: TTM市销率
                — dividend_yield: 股息率
                — peg: PEG
                — industry_pe_median: 行业PE中位数
                — industry_pb_median: 行业PB中位数
            factor_warnings: dict 因子告警信息
            industry_samples: dict 行业样本数——
                — pe_count: PE样本数
                — pb_count: PB样本数
            calculation_notes: list[str] 计算说明
            missing_factors: list[str] 缺失因子列表
            message: 错误信息（仅 status="error" 时存在）
    """
    try:
        return _json_response(get_value_factor_bundle(symbol))
    except Exception as exc:
        logger.error("价值因子包获取失败: %s", exc, exc_info=True)
        return _json_response({"status": "error", "message": f"获取价值因子包失败: {exc}"})


@tool
@register_tool(
    tool_id="get_quality_factor_bundle_tool",
    name="质量因子包",
    description=(
        "返回股票的 quality_core 标准化质量因子包。"
        "适合一次性获取 ROE、ROA、毛利率、净利率、资产负债率、流动比率、ROIC、"
        "现金转换率、应计利润比率、利息保障倍数、Piotroski F-Score、Altman Z-Score、Beneish M-Score 等质量指标。"
        "这里的“质量”指公司基本面和财务报表质量，不是数据质量、报告质量、技术信号质量或产品质量。"
    ),
    category="fundamentals",
    is_online=False,
    auto_register=True,
    timeout_tier="light",
    when_to_use=(
        "当 Agent 需要判断企业盈利质量、财务健康度、偿债能力、利润含金量、"
        "盈余操纵风险或财务困境风险时使用。"
        "如果希望直接拿到一组质量类指标做评分、筛选或报告生成，优先绑定这个工具。"
    ),
    when_not_to_use=(
        "不适合做估值贵不贵的判断，也不适合输出 MA、RSI、MACD 这类技术指标。"
        "不用于数据质量检查、报告质量评审、技术信号质量或短线资金流向分析。"
        "需要估值因子请用 get_value_factor_bundle_tool，需要技术因子请用 get_technical_factor_bundle_tool。"
    ),
    returns=(
        "返回 JSON 字符串，结构包含 symbol、bundle=quality_core、factors、factor_diagnostics、"
        "factor_warnings、calculation_notes、missing_factors。"
        "factors 中重点字段包括 roe、roa、gross_margin、netprofit_margin、debt_to_assets、current_ratio、quick_ratio、cash_ratio、"
        "roic、cash_conversion、accrual_ratio、asset_turnover、gross_profit_to_assets、interest_coverage、inventory_turnover、"
        "receivable_turnover、net_cash_position、piotroski_f_score、altman_z_score、beneish_m_score。"
    ),
    example="get_quality_factor_bundle_tool(symbol='600519')",
    related_tools=[
        "get_value_factor_bundle_tool",
        "get_growth_cashflow_factor_bundle_tool",
        "get_fundamental_factor_snapshot_tool",
    ],
)
def get_quality_factor_bundle_tool(
    symbol: Annotated[str, "A 股股票代码，如 600519、000001"]
) -> str:
    """获取标准化质量因子包。

    Args:
        symbol: A 股股票代码，如 "600519"、"000001"

    Returns:
        str: JSON 字符串，字段说明——
            status: 状态（仅在异常时为 "error"）
            symbol: 标准化后的股票代码
            name: 股票名称
            industry: 所属行业
            current_price: 当前价格
            report_period: 报告期
            data_source: 数据来源
            bundle: 因子包标识，固定为 "quality_core"
            factors: dict 质量因子集合——
                — roe: 净资产收益率
                — roa: 总资产收益率
                — gross_margin: 毛利率
                — netprofit_margin: 净利率
                — debt_to_assets: 资产负债率
                — assets_to_eqt: 权益乘数
                — current_ratio: 流动比率
                — quick_ratio: 速动比率
                — cash_ratio: 现金比率
                — roic: 投入资本回报率
                — cash_conversion: 现金转换率（经营现金流/净利润）
                — accrual_ratio: 应计利润比率（%）
                — asset_turnover: 总资产周转率
                — gross_profit_to_assets: 毛利/总资产（%）
                — interest_coverage: 利息保障倍数
                — inventory_turnover: 存货周转率
                — receivable_turnover: 应收账款周转率
                — net_cash_position: 净现金状况
                — piotroski_f_score: Piotroski F-Score
                — altman_z_score: Altman Z-Score
                — beneish_m_score: Beneish M-Score
            factor_diagnostics: dict 因子诊断信息
            factor_warnings: dict 因子告警信息
            calculation_notes: list[str] 计算说明
            missing_factors: list[str] 缺失因子列表
            message: 错误信息（仅 status="error" 时存在）
    """
    try:
        return _json_response(get_quality_factor_bundle(symbol))
    except Exception as exc:
        logger.error("质量因子包获取失败: %s", exc, exc_info=True)
        return _json_response({"status": "error", "message": f"获取质量因子包失败: {exc}"})


@tool
@register_tool(
    tool_id="get_growth_cashflow_factor_bundle_tool",
    name="成长现金流因子包",
    description=(
        "返回股票的 growth_cashflow_core 标准化成长/现金流因子包。"
        "适合一次性获取营收同比、净利润同比、营业利润同比、三年 CAGR、TTM 营收、TTM 净利润、"
        "经营现金流、自由现金流、自由现金流收益率、经营现金流收益率、净营运资本等指标。"
        "可用于现金流恶化分析、经营现金流持续下滑识别、自由现金流长期为负识别、现金收入质量判断、"
        "利润含金量评估、财务风险信号识别和成长质量分析。"
    ),
    category="fundamentals",
    is_online=False,
    auto_register=True,
    timeout_tier="light",
    capability_tags=["growth_analysis", "cashflow_quality", "cashflow_deterioration", "operating_cashflow", "free_cashflow", "financial_risk"],
    tool_role_hint="specialized",
    output_shape="structured_json",
    preferred_for=["cashflow_quality_analysis", "financial_risk_signal_detection", "growth_quality_analysis", "valuation_analysis"],
    when_to_use=(
        "当 Agent 需要判断公司增长速度、现金流造血能力、自由现金流质量、"
        "经营现金流是否持续下滑、自由现金流是否长期为负、现金收入质量是否变差、"
        "营运资本变化时使用。适合成长分析、现金流健康度分析、现金流恶化风险识别和 PEG/成长估值的前置取数。"
    ),
    when_not_to_use=(
        "不适合单独做估值倍数比较，也不适合技术面择时。"
        "这里的现金流是财务报表口径的经营/自由现金流，不用于查询主力资金流、北向资金、成交资金流向或短线交易资金面。"
        "如果目标是 PE/PB/股息率等估值字段，优先用 get_value_factor_bundle_tool。"
    ),
    returns=(
        "返回 JSON 字符串，结构包含 symbol、bundle=growth_cashflow_core、factors、factor_warnings、"
        "calculation_notes、missing_factors。"
        "factors 中重点字段包括 revenue_yoy、net_profit_yoy、oper_profit_yoy、revenue_cagr_3y、profit_cagr_3y、"
        "revenue_ttm、net_profit_ttm、n_cashflow_act、fcf、fcf_yield、fcf_margin、ocf_yield、net_working_capital、working_capital_change。"
    ),
    example="get_growth_cashflow_factor_bundle_tool(symbol='600519')",
    related_tools=[
        "get_value_factor_bundle_tool",
        "get_quality_factor_bundle_tool",
        "get_fundamental_factor_snapshot_tool",
    ],
)
def get_growth_cashflow_factor_bundle_tool(
    symbol: Annotated[str, "A 股股票代码，如 600519、000001"]
) -> str:
    """获取标准化成长/现金流因子包。

    Args:
        symbol: A 股股票代码，如 "600519"、"000001"

    Returns:
        str: JSON 字符串，字段说明——
            status: 状态（仅在异常时为 "error"）
            symbol: 标准化后的股票代码
            name: 股票名称
            industry: 所属行业
            current_price: 当前价格
            report_period: 报告期
            data_source: 数据来源
            bundle: 因子包标识，固定为 "growth_cashflow_core"
            factors: dict 成长/现金流因子集合——
                — revenue_yoy: 营收同比增长率
                — net_profit_yoy: 净利润同比增长率
                — oper_profit_yoy: 营业利润同比增长率
                — revenue_cagr_3y: 营收3年CAGR
                — profit_cagr_3y: 净利润3年CAGR
                — revenue_ttm: TTM营收
                — net_profit_ttm: TTM净利润
                — n_cashflow_act: 经营现金流
                — fcf: 自由现金流
                — fcf_yield: 自由现金流收益率（%）
                — fcf_margin: 自由现金流利润率（%）
                — ocf_yield: 经营现金流收益率（%）
                — total_cur_assets: 流动资产
                — total_cur_liab: 流动负债
                — net_working_capital: 净营运资本
                — working_capital_change: 营运资本变化
            factor_warnings: dict 因子告警信息
            calculation_notes: list[str] 计算说明
            missing_factors: list[str] 缺失因子列表
            message: 错误信息（仅 status="error" 时存在）
    """
    try:
        return _json_response(get_growth_cashflow_factor_bundle(symbol))
    except Exception as exc:
        logger.error("成长现金流因子包获取失败: %s", exc, exc_info=True)
        return _json_response({"status": "error", "message": f"获取成长现金流因子包失败: {exc}"})


@tool
@register_tool(
    tool_id="get_fundamental_factor_snapshot_tool",
    name="标准化基本面因子快照",
    description=(
        "返回单只 A 股股票的标准化基本面因子总快照。"
        "这是一个聚合型工具，会同时给出 value_core、quality_core、growth_cashflow_core 三个因子包，"
        "适合 Agent 一次绑定后拿到大部分常用基本面指标，而不需要分别调用多个工具。"
    ),
    category="fundamentals",
    is_online=False,
    auto_register=True,
    timeout_tier="light",
    when_to_use=(
        "当 Agent 需要一次拿到完整的基本面因子快照，用于综合分析、报告生成、初步筛选、"
        "或后续再在 Prompt 中做多维解释时使用。"
    ),
    when_not_to_use=(
        "如果 Agent 只关心某一类指标，优先绑定更窄的 bundle 工具，避免拿太多无关字段。"
        "例如只做估值就用 get_value_factor_bundle_tool，只做财务质量就用 get_quality_factor_bundle_tool。"
    ),
    returns=(
        "返回 JSON 字符串，结构包含 symbol、name、industry、current_price、report_period、data_source、"
        "factors、factor_diagnostics、factor_warnings、missing_factors、bundles。"
        "bundles 下按 value_core、quality_core、growth_cashflow_core 分组，适合 Agent 直接消费。"
    ),
    example="get_fundamental_factor_snapshot_tool(symbol='600519')",
    related_tools=[
        "get_value_factor_bundle_tool",
        "get_quality_factor_bundle_tool",
        "get_growth_cashflow_factor_bundle_tool",
    ],
)
def get_fundamental_factor_snapshot_tool(
    symbol: Annotated[str, "A 股股票代码，如 600519、000001"]
) -> str:
    """获取标准化基本面因子快照。

    Args:
        symbol: A 股股票代码，如 "600519"、"000001"

    Returns:
        str: JSON 字符串，字段说明——
            status: 状态（仅在异常时为 "error"）
            symbol: 标准化后的股票代码
            name: 股票名称
            industry: 所属行业
            current_price: 当前价格
            report_period: 报告期
            data_source: 数据来源
            factors: dict 合并后的全部因子（value_core + quality_core + growth_cashflow_core）
            factor_diagnostics: dict 合并后的因子诊断信息
            factor_warnings: dict 合并后的因子告警信息
            missing_factors: list[str] 合并后的缺失因子列表（去重排序）
            bundles: dict 三个因子包分组——
                — value_core: dict 价值因子包（结构同 get_value_factor_bundle_tool 返回）
                — quality_core: dict 质量因子包（结构同 get_quality_factor_bundle_tool 返回）
                — growth_cashflow_core: dict 成长现金流因子包（结构同 get_growth_cashflow_factor_bundle_tool 返回）
            message: 错误信息（仅 status="error" 时存在）
    """
    try:
        snapshot = get_fundamental_factor_snapshot(symbol)
        return _json_response(snapshot)
    except Exception as exc:
        logger.error("标准化基本面因子快照获取失败: %s", exc, exc_info=True)
        return _json_response({"status": "error", "message": f"获取基本面因子快照失败: {exc}"})


__all__ = [
    "get_value_factor_bundle_tool",
    "get_quality_factor_bundle_tool",
    "get_growth_cashflow_factor_bundle_tool",
    "get_fundamental_factor_snapshot_tool",
]