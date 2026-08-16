"""
板块分析工具

提供板块表现分析、轮动识别、同业对比等功能
这些工具用于 SectorAnalystV2 分析师
"""

import logging
from typing import Annotated
from langchain_core.tools import tool

from core.tools.base import register_tool
from core.tools.context import get_current_analysis_data_source

logger = logging.getLogger(__name__)


def _resolve_sector_analysis_source() -> str:
    """获取当前行业分析工具应使用的数据源。"""
    current_source = get_current_analysis_data_source()
    if current_source == "qmt":
        return "qmt"
    return "tushare"


def _is_tushare_available() -> bool:
    """检查 Tushare 数据源是否可用。"""
    try:
        from app.services.data_sources.tushare_adapter import TushareAdapter
        return TushareAdapter().is_available()
    except Exception:
        return False


def _is_qmt_available() -> bool:
    """检查 QMT 数据源是否可用。"""
    try:
        from app.services.data_sources.qmt_adapter import QMTAdapter
        return QMTAdapter().is_available()
    except Exception:
        return False


def _tushare_unavailable_msg(dimensions: str) -> str:
    """Tushare 不可用且 QMT 无法替代时的统一提示。"""
    return (
        f"⚠️ 当前 Tushare 数据源不可用，{dimensions}数据仅 Tushare 提供，QMT 不支持此维度。"
        f"请优先参考 get_sector_analysis 工具返回的 QMT 行业分析数据。"
    )


@tool
@register_tool(
    tool_id="get_sector_data",
    name="板块数据",
    description="获取股票所属板块的表现数据并分析行业趋势，返回板块涨跌幅、成交额、领涨股、资金流向等板块趋势数据信息",
    category="market",
    is_online=True,
    auto_register=True,
    capability_tags=["sector_data", "sector_performance", "industry_trend", "sector_ranking", "industry_analysis"],
    tool_role_hint="specialized",
    output_shape="markdown",
    preferred_for=["sector_performance_analysis", "industry_trend_evaluation", "sector_ranking_review"],
)
def get_sector_data(
    ticker: Annotated[str, "股票代码（如 000001 或 000001.SZ）"],
    trade_date: Annotated[str, "交易日期，格式：YYYY-MM-DD"],
    lookback_days: Annotated[int, "回看天数，默认20天"] = 20
) -> str:
    """
    获取股票所属板块的表现数据

    分析股票所属行业板块的近期表现，包括涨跌幅、资金流向、板块排名等。

    Args:
        ticker: 股票代码（如 000001 或 000001.SZ）
        trade_date: 交易日期（格式：YYYY-MM-DD）
        lookback_days: 回看天数（默认20天）

    Returns:
        str: 板块表现分析报告
    """
    try:
        from core.tools.sector_tools import get_sector_performance_sync
        return get_sector_performance_sync(ticker, trade_date, lookback_days)
    except Exception as e:
        logger.error(f"获取板块数据失败: {e}")
        # Tushare 失败时尝试 QMT 降级
        if _is_qmt_available():
            logger.info("Tushare 获取板块数据失败，尝试 QMT 降级")
            try:
                from core.tools.qmt_market_tools import get_sector_analysis_qmt_enhanced
                report = get_sector_analysis_qmt_enhanced(ticker, trade_date, lookback_days)
                return f"📊 以下数据基于 QMT 行情口径（Tushare 不可用时的降级数据）\n\n{report}"
            except Exception as qmt_e:
                return f"❌ 获取板块数据失败: Tushare={e}, QMT降级={qmt_e}"
        return f"❌ 获取板块数据失败: {e}"


@tool
@register_tool(
    tool_id="get_fund_flow_data",
    name="资金流向",
    description=(
        "获取板块资金流向数据，分析主力资金动向、板块资金净流入/流出和板块轮动。"
        "这里的“资金流向”指交易市场资金面，不是财务报表中的经营现金流、投资现金流、筹资现金流或自由现金流。"
    ),
    category="market",
    is_online=True,
    auto_register=True,
    capability_tags=["fund_flow", "capital_flow", "sector_rotation", "main_capital", "liquidity_flow"],
    tool_role_hint="specialized",
    output_shape="markdown",
    preferred_for=["sector_capital_flow_analysis", "sector_rotation_identification", "main_capital_tracking"],
    when_to_use="当需要板块资金流、主力资金流入流出、行业轮动资金面证据时使用。",
    when_not_to_use="不用于现金流量表分析、现金流恶化、利润含金量、财务风险或个股财务现金流质量判断；这些需求应使用现金流/财务风险工具。",
)
def get_fund_flow_data(
    trade_date: Annotated[str, "交易日期，格式：YYYY-MM-DD"],
    top_n: Annotated[int, "返回前N个板块，默认10"] = 10,
    lookback_days: Annotated[int, "回溯天数，1=仅当天，30=最近一个月累计，默认1"] = 1
) -> str:
    """
    获取板块资金流向数据

    分析各板块的资金流入流出情况，识别主力资金动向和板块轮动趋势。
    支持单日快照（lookback_days=1）和多日累计聚合（lookback_days>1）两种模式。

    Args:
        trade_date: 截止交易日期（格式：YYYY-MM-DD）
        top_n: 返回前N个板块（默认10）
        lookback_days: 回溯天数，1=仅当天，30=最近一个月累计（默认1）

    Returns:
        str: 板块资金流向分析报告
    """
    try:
        from core.tools.sector_tools import get_sector_rotation_sync
        return get_sector_rotation_sync(trade_date, top_n, lookback_days)
    except Exception as e:
        logger.error(f"获取资金流向失败: {e}")
        if not _is_tushare_available():
            return _tushare_unavailable_msg("板块资金流向")
        return f"❌ 获取资金流向失败: {e}"


@tool
@register_tool(
    tool_id="get_peer_comparison",
    name="同业对比",
    description="获取同行业股票对比数据分析个股在行业中的位置，返回同业市值、PE、PB、ROE、涨跌幅排名等同业对比表",
    category="market",
    is_online=True,
    auto_register=True,
    capability_tags=["peer_comparison", "industry_ranking", "competitor_analysis", "competitive_positioning"],
    tool_role_hint="specialized",
    output_shape="markdown",
    preferred_for=["peer_comparison_analysis", "industry_ranking_evaluation", "competitive_positioning"],
)
def get_peer_comparison(
    ticker: Annotated[str, "股票代码（如 000001 或 000001.SZ）"],
    trade_date: Annotated[str, "交易日期，格式：YYYY-MM-DD"],
    top_n: Annotated[int, "返回前N个同业股票，默认10"] = 10
) -> str:
    """
    获取同行业股票对比数据

    分析目标股票在同行业中的表现排名，包括涨跌幅、市值、估值等维度的对比。

    Args:
        ticker: 股票代码（如 000001 或 000001.SZ）
        trade_date: 交易日期（格式：YYYY-MM-DD）
        top_n: 返回前N个同业股票（默认10）

    Returns:
        str: 同业对比分析报告
    """
    try:
        from core.tools.sector_tools import get_peer_comparison_sync
        return get_peer_comparison_sync(ticker, trade_date, top_n)
    except Exception as e:
        logger.error(f"获取同业对比失败: {e}")
        # Tushare 失败时尝试 QMT 降级
        if _is_qmt_available():
            logger.info("Tushare 获取同业对比失败，尝试 QMT 降级")
            try:
                from core.tools.qmt_market_tools import get_sector_analysis_qmt_enhanced
                report = get_sector_analysis_qmt_enhanced(ticker, trade_date, 20, top_n)
                return f"📊 以下数据基于 QMT 行情口径（Tushare 不可用时的降级数据）\n\n{report}"
            except Exception as qmt_e:
                return f"❌ 获取同业对比失败: Tushare={e}, QMT降级={qmt_e}"
        return f"❌ 获取同业对比失败: {e}"


@tool
@register_tool(
    tool_id="get_industry_top_companies",
    name="同行业TOP公司",
    description="获取同行业市值排名前N的公司列表，适合快速了解行业竞争格局和同业对比",
    category="market",
    is_online=True,
    auto_register=True,
    capability_tags=["industry_top_companies", "industry_leaders", "competitive_landscape", "market_cap_ranking", "moat_analysis"],
    tool_role_hint="specialized",
    output_shape="markdown",
    preferred_for=["industry_leader_identification", "competitive_landscape_overview", "market_cap_ranking_review"],
)
def get_industry_top_companies(
    ticker: Annotated[str, "股票代码（如 600519 或 600519.SH）"],
    top_n: Annotated[int, "返回前N家同行业公司，默认5"] = 5
) -> str:
    """
    获取同行业 TOP N 公司列表（轻量版）

    自动识别股票所属行业，按市值排序返回前N家同行业公司，
    包含代码、名称、市值、PE、PB 等关键指标。
    不需要传交易日期，自动取最新交易日数据。

    Args:
        ticker: 股票代码（如 600519 或 600519.SH）
        top_n: 返回前N家同行业公司（默认5）

    Returns:
        str: 同行业 TOP N 公司简表
    """
    try:
        from core.tools.sector_tools import get_industry_top_companies_sync
        return get_industry_top_companies_sync(ticker, top_n)
    except Exception as e:
        logger.error(f"获取同行业TOP公司失败: {e}")
        return f"❌ 获取同行业TOP公司失败: {e}"


@tool
@register_tool(
    tool_id="analyze_sector",
    name="综合板块分析",
    description="综合分析股票所属板块包括表现轮动同业对比等，返回板块表现、轮动信号、同业对比、资金流向等综合分析报告",
    category="market",
    is_online=True,
    auto_register=True,
    capability_tags=["sector_analysis", "sector_performance", "sector_rotation", "peer_comparison", "comprehensive_sector"],
    tool_role_hint="general",
    output_shape="markdown",
    preferred_for=["comprehensive_sector_analysis", "multi_dimension_sector_evaluation", "integrated_industry_review"],
)
def analyze_sector(
    ticker: Annotated[str, "股票代码（如 000001 或 000001.SZ）"],
    trade_date: Annotated[str, "交易日期，格式：YYYY-MM-DD"]
) -> str:
    """
    综合板块分析

    整合板块表现、资金流向、同业对比等多维度数据，给出综合板块分析报告。

    Args:
        ticker: 股票代码（如 000001 或 000001.SZ）
        trade_date: 交易日期（格式：YYYY-MM-DD）

    Returns:
        str: 综合板块分析报告
    """
    try:
        from core.tools.sector_tools import analyze_sector_sync
        return analyze_sector_sync(ticker, trade_date)
    except Exception as e:
        logger.error(f"综合板块分析失败: {e}")
        # Tushare 失败时尝试 QMT 降级
        if _is_qmt_available():
            logger.info("Tushare 综合板块分析失败，尝试 QMT 降级")
            try:
                from core.tools.qmt_market_tools import get_sector_analysis_qmt_enhanced
                report = get_sector_analysis_qmt_enhanced(ticker, trade_date, 20, 10)
                return f"📊 以下数据基于 QMT 行情口径（Tushare 不可用时的降级数据）\n\n{report}"
            except Exception as qmt_e:
                return f"❌ 综合板块分析失败: Tushare={e}, QMT降级={qmt_e}"
        return f"❌ 综合板块分析失败: {e}"


@tool
@register_tool(
    tool_id="get_sector_analysis",
    name="统一行业分析",
    description="根据当前分析数据源自动选择 QMT 或 Tushare 路径，返回统一的行业分析结果。",
    category="market",
    is_online=True,
    auto_register=True,
    capability_tags=["sector_analysis", "unified_analysis", "sector_performance", "data_source_routing", "comprehensive_industry"],
    tool_role_hint="general",
    output_shape="markdown",
    preferred_for=["unified_sector_analysis", "multi_source_sector_evaluation", "comprehensive_industry_report"],
)
def get_sector_analysis(
    ticker: Annotated[str, "股票代码（如 000001 或 000001.SZ）"],
    trade_date: Annotated[str, "交易日期，格式：YYYY-MM-DD"],
    lookback_days: Annotated[int, "回看天数，默认20天"] = 20,
    top_n: Annotated[int, "返回前N个结果，默认10"] = 10
) -> str:
    """统一的行业分析工具，自动按当前数据源（QMT 或 Tushare）路由，返回整合后的行业分析报告。

    Args:
        ticker: 股票代码（如 000001 或 000001.SZ）
        trade_date: 交易日期，格式 YYYY-MM-DD
        lookback_days: 回看天数，默认 20
        top_n: 返回前 N 个结果，默认 10

    Returns:
        str: Markdown 格式的行业分析报告，由多个分节拼接而成，分节包括 —
            ## 板块表现：板块行情与涨跌表现
            ## 板块资金流向：板块资金流入流出排名
            ## 同业对比：同行业个股对比
        QMT 或 Tushare 失败时返回以 "❌" 开头的错误说明字符串
    """
    source = _resolve_sector_analysis_source()

    if source == "qmt":
        try:
            from core.tools.qmt_market_tools import get_sector_analysis_qmt_enhanced
            return get_sector_analysis_qmt_enhanced(ticker, trade_date, lookback_days, top_n)
        except Exception as e:
            logger.error(f"QMT 行业分析失败: {e}")
            # QMT 失败时尝试 Tushare
            if _is_tushare_available():
                logger.info("QMT 行业分析失败，尝试 Tushare 降级")
                try:
                    from core.tools.sector_tools import analyze_sector_sync
                    return analyze_sector_sync(ticker, trade_date)
                except Exception as ts_e:
                    return f"❌ 行业分析失败: QMT={e}, Tushare={ts_e}"
            return f"❌ QMT 行业分析失败: {e}"

    sections = []
    tool_calls = [
        ("板块表现", lambda: get_sector_data.invoke({"ticker": ticker, "trade_date": trade_date, "lookback_days": lookback_days})),
        ("板块资金流向", lambda: get_fund_flow_data.invoke({"trade_date": trade_date, "top_n": top_n, "lookback_days": 1})),
        ("同业对比", lambda: get_peer_comparison.invoke({"ticker": ticker, "trade_date": trade_date, "top_n": top_n})),
    ]

    for title, producer in tool_calls:
        try:
            content = producer()
        except Exception as exc:
            logger.error(f"统一行业分析组装失败 [{title}]: {exc}")
            content = f"❌ {title} 获取失败: {exc}"
        sections.append(f"## {title}\n{content}")

    return "\n\n".join(sections)


# ============================================================
# 板块级别工具（以板块名称为入口，无需 ticker）
# ============================================================

@tool
@register_tool(
    tool_id="search_sector",
    name="板块搜索",
    description="按名称关键词搜索A股板块（行业/概念/地域），返回匹配的板块列表",
    category="market",
    is_online=True,
    auto_register=True,
    capability_tags=["sector_search", "sector_lookup", "industry_classification", "concept_classification"],
    tool_role_hint="specialized",
    output_shape="markdown",
    preferred_for=["sector_lookup", "industry_classification_search", "sector_code_discovery"],
    when_to_use="当用户提到板块、行业、概念等关键词，需要先查找板块代码时使用",
)
def search_sector_tool(
    keyword: Annotated[str, "板块名称关键词（如 光伏、半导体、白酒、新能源）"],
    sector_type: Annotated[str, "板块类型: N=行业板块 I=行业指数 S=概念 R=地域，默认N"] = "N",
) -> str:
    """
    按名称关键词搜索同花顺板块

    返回匹配的板块列表，包含板块代码、名称、成分股数量。

    Args:
        keyword: 板块名称关键词
        sector_type: 板块类型（N=行业, S=概念, R=地域）

    Returns:
        str: 板块搜索结果
    """
    try:
        from core.tools.sector_tools import search_sector_sync
        return search_sector_sync(keyword, sector_type)
    except Exception as e:
        logger.error(f"板块搜索失败: {e}")
        if not _is_tushare_available():
            return _tushare_unavailable_msg("板块搜索（同花顺板块列表）")
        return f"❌ 板块搜索失败: {e}"


@tool
@register_tool(
    tool_id="get_sector_daily",
    name="板块行情",
    description="获取板块指数的日线行情数据，包括涨跌幅、成交量、换手率、市值等",
    category="market",
    is_online=True,
    auto_register=True,
    capability_tags=["sector_daily", "sector_quote", "sector_index", "sector_trend", "sector_volume"],
    tool_role_hint="specialized",
    output_shape="markdown",
    preferred_for=["sector_index_quote", "sector_daily_performance", "sector_trend_review"],
    when_to_use="当用户想了解某个板块的近期走势、涨跌情况时使用",
)
def get_sector_daily_tool(
    sector_name: Annotated[str, "板块名称关键词（如 光伏、半导体、白酒）"],
    trade_date: Annotated[str, "交易日期，格式：YYYY-MM-DD"],
    lookback_days: Annotated[int, "回看天数，默认20天"] = 20,
) -> str:
    """
    获取板块指数日线行情

    Args:
        sector_name: 板块名称关键词
        trade_date: 交易日期
        lookback_days: 回看天数

    Returns:
        str: 板块行情报告
    """
    try:
        from core.tools.sector_tools import get_sector_daily_sync
        return get_sector_daily_sync(sector_name, trade_date, lookback_days)
    except Exception as e:
        logger.error(f"板块行情获取失败: {e}")
        if not _is_tushare_available():
            return _tushare_unavailable_msg("板块行情（同花顺板块指数日线）")
        return f"❌ 板块行情获取失败: {e}"


@tool
@register_tool(
    tool_id="get_sector_constituents",
    name="板块成分股",
    description="获取板块的成分股列表及其市值与估值排名，返回成分股代码、名称、市值、PE、PB、涨跌幅等排序表数据信息",
    category="market",
    is_online=True,
    auto_register=True,
    capability_tags=["sector_constituents", "sector_members", "sector_leaders", "constituent_ranking"],
    tool_role_hint="specialized",
    output_shape="markdown",
    preferred_for=["sector_member_listing", "sector_leader_identification", "constituent_ranking_review"],
    when_to_use="当用户想知道某个板块有哪些股票、龙头股是哪些时使用",
)
def get_sector_constituents_tool(
    sector_name: Annotated[str, "板块名称关键词（如 光伏、半导体、白酒）"],
    trade_date: Annotated[str, "交易日期，格式：YYYY-MM-DD"],
    top_n: Annotated[int, "返回前N只成分股，默认15"] = 15,
) -> str:
    """
    获取板块成分股列表及表现

    Args:
        sector_name: 板块名称关键词
        trade_date: 交易日期
        top_n: 返回前N只成分股

    Returns:
        str: 板块成分股报告
    """
    try:
        from core.tools.sector_tools import get_sector_constituents_sync
        return get_sector_constituents_sync(sector_name, trade_date, top_n)
    except Exception as e:
        logger.error(f"板块成分股获取失败: {e}")
        if not _is_tushare_available():
            return _tushare_unavailable_msg("板块成分股（同花顺板块成分列表）")
        return f"❌ 板块成分股获取失败: {e}"


@tool
@register_tool(
    tool_id="analyze_sector_by_name",
    name="板块综合分析",
    description="按板块名称进行综合分析，整合板块行情、成分股龙头、全市场资金流向",
    category="market",
    is_online=True,
    auto_register=True,
    capability_tags=["sector_analysis", "sector_comprehensive", "sector_performance", "fund_flow", "sector_leaders"],
    tool_role_hint="general",
    output_shape="markdown",
    preferred_for=["sector_comprehensive_analysis", "sector_investment_opportunity", "multi_dimension_sector_review"],
    when_to_use="当用户问某个板块的投资机会、板块分析、行业前景时使用",
)
def analyze_sector_by_name_tool(
    sector_name: Annotated[str, "板块名称关键词（如 光伏、半导体、白酒、新能源汽车）"],
    trade_date: Annotated[str, "交易日期，格式：YYYY-MM-DD"],
) -> str:
    """
    板块综合分析（以板块名称为入口）

    Args:
        sector_name: 板块名称关键词
        trade_date: 交易日期

    Returns:
        str: 板块综合分析报告
    """
    try:
        from core.tools.sector_tools import analyze_sector_by_name_sync
        return analyze_sector_by_name_sync(sector_name, trade_date)
    except Exception as e:
        logger.error(f"板块综合分析失败: {e}")
        if not _is_tushare_available():
            return _tushare_unavailable_msg("板块综合分析（同花顺板块体系）")
        return f"❌ 板块综合分析失败: {e}"
