# tradingagents/core/contracts/researchers.py
"""
研究员数据契约定义

定义研究员 Agent 的输入/输出字段和依赖关系
研究员需要读取所有分析师报告进行综合研判
"""

from tradingagents.core.engine.data_contract import (
    AgentDataContract,
    DataAccess,
    DataLayer,
)


# =========================================
# 看多研究员 (Bull Researcher)
# =========================================
BULL_RESEARCHER_CONTRACT = AgentDataContract(
    agent_id="bull_researcher",
    description="看多研究员 - 从乐观角度综合分析报告，寻找买入理由",
    inputs=[
        DataAccess(
            layer=DataLayer.CONTEXT,
            fields=["ticker", "company_name", "trade_date"],
            required=True
        ),
        # 读取所有分析师报告
        DataAccess(
            layer=DataLayer.REPORTS,
            fields=[
                "market_report",
                "news_report",
                "sentiment_report",
                "fundamentals_report",
                "sector_report",
                "index_report",
            ],
            required=False  # 部分报告可能不存在
        ),
        # 读取结构化分析数据
        DataAccess(
            layer=DataLayer.ANALYSIS_DATA,
            fields=["technical", "valuation", "sentiment"],
            required=False
        ),
    ],
    outputs=[
        DataAccess(
            layer=DataLayer.REPORTS,
            fields=["bull_report"]
        ),
    ],
    depends_on={
        "market_analyst",
        "news_analyst",
        "sentiment_analyst",
        "fundamentals_analyst",
    }
)


# =========================================
# 看空研究员 (Bear Researcher)
# =========================================
BEAR_RESEARCHER_CONTRACT = AgentDataContract(
    agent_id="bear_researcher",
    description="看空研究员 - 从谨慎角度综合分析报告，识别风险因素",
    inputs=[
        DataAccess(
            layer=DataLayer.CONTEXT,
            fields=["ticker", "company_name", "trade_date"],
            required=True
        ),
        DataAccess(
            layer=DataLayer.REPORTS,
            fields=[
                "market_report",
                "news_report",
                "sentiment_report",
                "fundamentals_report",
                "sector_report",
                "index_report",
            ],
            required=False
        ),
        DataAccess(
            layer=DataLayer.ANALYSIS_DATA,
            fields=["technical", "valuation", "sentiment"],
            required=False
        ),
    ],
    outputs=[
        DataAccess(
            layer=DataLayer.REPORTS,
            fields=["bear_report"]
        ),
    ],
    depends_on={
        "market_analyst",
        "news_analyst",
        "sentiment_analyst",
        "fundamentals_analyst",
    }
)


# =========================================
# 研究经理 (Research Manager)
# =========================================
RESEARCH_MANAGER_CONTRACT = AgentDataContract(
    agent_id="research_manager",
    description="研究经理 - 主持多空辩论，综合研判，形成投资建议",
    inputs=[
        DataAccess(
            layer=DataLayer.CONTEXT,
            fields=["ticker", "company_name", "trade_date"],
            required=True
        ),
        DataAccess(
            layer=DataLayer.REPORTS,
            fields=["bull_report", "bear_report"],
            required=True
        ),
    ],
    outputs=[
        DataAccess(
            layer=DataLayer.DECISIONS,
            fields=["investment_debate", "investment_plan"]
        ),
    ],
    depends_on={"bull_researcher", "bear_researcher"}
)


# =========================================
# 研究员契约汇总
# =========================================
RESEARCHER_CONTRACTS = {
    "bull_researcher": BULL_RESEARCHER_CONTRACT,
    "bear_researcher": BEAR_RESEARCHER_CONTRACT,
    "research_manager": RESEARCH_MANAGER_CONTRACT,
}

