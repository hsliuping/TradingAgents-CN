"""
种子流程定义

预定义的分析模板，作为确定性保底机制。
每个种子流程包含：
- id: 唯一标识
- name: 显示名称
- description: 语义描述（用于 LLM 匹配）
- steps: 预定义的工具调用步骤（含占位符）
- extensible: 是否允许 LLM 追加步骤

一期：代码内嵌，类似 BUILTIN_TOOLS
二期：迁移至 MongoDB analysis_flow_templates 集合
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class SeedFlowStep(BaseModel):
    """种子流程步骤模板"""
    tool: str = Field(..., description="工具 ID")
    args_template: Dict[str, str] = Field(default_factory=dict, description="参数模板，支持 {ticker} {curr_date} {trade_date} 占位符")
    intent: str = Field("", description="步骤意图说明")
    depends_on: List[int] = Field(default_factory=list, description="依赖的步骤索引（0-based）")


class SeedFlow(BaseModel):
    """种子流程定义"""
    id: str = Field(..., description="唯一标识")
    name: str = Field(..., description="显示名称")
    description: str = Field(..., description="语义描述，用于 LLM 匹配")
    steps: List[SeedFlowStep] = Field(default_factory=list)
    extensible: bool = Field(True, description="是否允许 LLM 追加步骤")


# ============================================================
# 内置种子流程
# ============================================================

BUILTIN_SEED_FLOWS: Dict[str, SeedFlow] = {

    "earnings_disclosure_date": SeedFlow(
        id="earnings_disclosure_date",
        name="财报披露时间查询",
        description="查询某公司历年财报披露时间，推断当年年报大致披露窗口",
        steps=[
            SeedFlowStep(
                tool="get_stock_fundamentals_unified",
                args_template={"ticker": "{ticker}", "curr_date": "{curr_date}"},
                intent="获取财务数据，查看报告期与披露信息",
                depends_on=[],
            ),
            SeedFlowStep(
                tool="get_stock_news_unified",
                args_template={"ticker": "{ticker}", "curr_date": "{curr_date}"},
                intent="查询财报预约披露公告",
                depends_on=[],
            ),
        ],
        extensible=True,
    ),

    "stock_overview": SeedFlow(
        id="stock_overview",
        name="个股综合速览",
        description="个股综合速览，获取基本面、行情、新闻等综合信息，快速了解一只股票的整体状况",
        steps=[
            SeedFlowStep(
                tool="get_stock_fundamentals_unified",
                args_template={"ticker": "{ticker}", "curr_date": "{curr_date}"},
                intent="获取基本面数据（PE/PB/ROE/营收等）",
                depends_on=[],
            ),
            SeedFlowStep(
                tool="get_stock_market_data_unified",
                args_template={"ticker": "{ticker}", "start_date": "{curr_date}", "end_date": "{curr_date}"},
                intent="获取近期行情走势和成交量",
                depends_on=[],
            ),
            SeedFlowStep(
                tool="get_stock_news_unified",
                args_template={"ticker": "{ticker}", "curr_date": "{curr_date}"},
                intent="获取最新新闻动态",
                depends_on=[],
            ),
            SeedFlowStep(
                tool="get_technical_indicators",
                args_template={"ticker": "{ticker}", "indicators": "macd,rsi_14,boll,kdj", "end_date": "{curr_date}"},
                intent="获取技术指标（MACD/RSI/KDJ）判断短期走势",
                depends_on=[],
            ),
        ],
        extensible=True,
    ),

    "sector_screening": SeedFlow(
        id="sector_screening",
        name="板块分析",
        description="板块分析和板块内选股，查看某个板块的行情走势、成分股龙头、资金流向，分析板块投资机会",
        steps=[
            SeedFlowStep(
                tool="analyze_sector_by_name",
                args_template={"sector_name": "{sector_name}", "trade_date": "{trade_date}"},
                intent="综合分析板块行情、成分股龙头和资金流向",
                depends_on=[],
            ),
        ],
        extensible=True,
    ),

    "event_impact": SeedFlow(
        id="event_impact",
        name="事件影响分析",
        description="特定事件对相关股票或板块的影响分析，如政策变化、降准降息、行业事件等",
        steps=[
            SeedFlowStep(
                tool="get_stock_news_unified",
                args_template={"ticker": "{ticker}", "curr_date": "{curr_date}"},
                intent="获取事件相关新闻和公告",
                depends_on=[],
            ),
            SeedFlowStep(
                tool="get_sector_data",
                args_template={"ticker": "{ticker}", "trade_date": "{trade_date}"},
                intent="获取受影响板块的表现数据",
                depends_on=[],
            ),
            SeedFlowStep(
                tool="get_stock_market_data_unified",
                args_template={"ticker": "{ticker}", "start_date": "{curr_date}", "end_date": "{curr_date}"},
                intent="获取受影响个股的行情变化",
                depends_on=[],
            ),
        ],
        extensible=True,
    ),

    "peer_comparison": SeedFlow(
        id="peer_comparison",
        name="同业对比",
        description="同行业公司对比分析，比较两家或多家公司的基本面、估值、走势",
        steps=[
            SeedFlowStep(
                tool="get_peer_comparison",
                args_template={"ticker": "{ticker}", "trade_date": "{trade_date}"},
                intent="获取同业股票列表及对比数据",
                depends_on=[],
            ),
            SeedFlowStep(
                tool="get_stock_fundamentals_unified",
                args_template={"ticker": "{ticker}", "curr_date": "{curr_date}"},
                intent="获取主要公司基本面详情",
                depends_on=[],
            ),
        ],
        extensible=True,
    ),

    "concept_stock_analysis": SeedFlow(
        id="concept_stock_analysis",
        name="概念股分析",
        description="查询概念板块成分股、龙头股，分析概念股投资机会，如XX概念股有哪些、XX概念股龙头",
        steps=[
            SeedFlowStep(
                tool="get_sector_constituents",
                args_template={"sector_name": "{sector_name}", "trade_date": "{trade_date}", "top_n": "20"},
                intent="获取概念板块成分股列表及市值排名，找出龙头股",
                depends_on=[],
            ),
            SeedFlowStep(
                tool="get_sector_daily",
                args_template={"sector_name": "{sector_name}", "trade_date": "{trade_date}"},
                intent="获取概念板块指数近期走势和涨跌情况",
                depends_on=[],
            ),
        ],
        extensible=True,
    ),

    "stock_technical_analysis": SeedFlow(
        id="stock_technical_analysis",
        name="个股技术面分析",
        description="个股技术面分析，查看MACD、RSI、KDJ、BOLL等技术指标和K线走势，判断买卖信号和趋势",
        steps=[
            SeedFlowStep(
                tool="get_technical_indicators",
                args_template={"ticker": "{ticker}", "indicators": "macd,rsi_14,boll,kdj", "end_date": "{curr_date}"},
                intent="获取 MACD/RSI/KDJ/BOLL 等技术指标，判断趋势和超买超卖",
                depends_on=[],
            ),
            SeedFlowStep(
                tool="get_stock_market_data_unified",
                args_template={"ticker": "{ticker}", "start_date": "{curr_date}", "end_date": "{curr_date}"},
                intent="获取近期K线走势和成交量数据",
                depends_on=[],
            ),
        ],
        extensible=True,
    ),

    "market_overview": SeedFlow(
        id="market_overview",
        name="大盘市场分析",
        description="大盘走势分析、市场整体环境评估、今天大盘怎么样、市场情绪判断、涨跌停统计",
        steps=[
            SeedFlowStep(
                tool="get_china_market_overview",
                args_template={"curr_date": "{curr_date}"},
                intent="获取主要指数行情概览（上证、深证、创业板、科创50）",
                depends_on=[],
            ),
            SeedFlowStep(
                tool="get_limit_stats",
                args_template={"trade_date": "{trade_date}"},
                intent="获取涨跌停家数和涨跌家数，评估市场赚钱效应",
                depends_on=[],
            ),
            SeedFlowStep(
                tool="get_fund_flow_data",
                args_template={"trade_date": "{trade_date}"},
                intent="获取板块资金流向排名，了解热点板块",
                depends_on=[],
            ),
        ],
        extensible=True,
    ),

    "north_flow_analysis": SeedFlow(
        id="north_flow_analysis",
        name="北向资金分析",
        description="北向资金流向分析、外资动向、沪深港通资金流入流出、外资在买什么",
        steps=[
            SeedFlowStep(
                tool="get_north_flow",
                args_template={"trade_date": "{trade_date}"},
                intent="获取北向资金净流入/流出数据和趋势",
                depends_on=[],
            ),
            SeedFlowStep(
                tool="get_china_market_overview",
                args_template={"curr_date": "{curr_date}"},
                intent="获取大盘指数行情，配合分析外资对市场影响",
                depends_on=[],
            ),
        ],
        extensible=True,
    ),
}


def get_seed_flow(flow_id: str) -> Optional[SeedFlow]:
    """根据 ID 获取种子流程"""
    return BUILTIN_SEED_FLOWS.get(flow_id)


def list_seed_flows() -> List[SeedFlow]:
    """获取所有种子流程"""
    return list(BUILTIN_SEED_FLOWS.values())

