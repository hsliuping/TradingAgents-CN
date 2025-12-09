# tradingagents/core/contracts/analysts.py
"""
分析师数据契约定义

定义各类分析师 Agent 的输入/输出字段和依赖关系
"""

from tradingagents.core.engine.data_contract import (
    AgentDataContract,
    DataAccess,
    DataLayer,
)


# =========================================
# 市场分析师 (Market Analyst)
# =========================================
MARKET_ANALYST_CONTRACT = AgentDataContract(
    agent_id="market_analyst",
    description="技术面分析师 - 分析价格走势、技术指标",
    inputs=[
        DataAccess(
            layer=DataLayer.CONTEXT,
            fields=["ticker", "company_name", "trade_date"],
            required=True
        ),
        DataAccess(
            layer=DataLayer.RAW_DATA,
            fields=["price_data"],
            required=True
        ),
    ],
    outputs=[
        DataAccess(
            layer=DataLayer.ANALYSIS_DATA,
            fields=["technical"]
        ),
        DataAccess(
            layer=DataLayer.REPORTS,
            fields=["market_report"]
        ),
    ],
    depends_on=set()  # 第一阶段，无依赖
)


# =========================================
# 新闻分析师 (News Analyst)
# =========================================
NEWS_ANALYST_CONTRACT = AgentDataContract(
    agent_id="news_analyst",
    description="新闻分析师 - 分析新闻舆情、市场热点",
    inputs=[
        DataAccess(
            layer=DataLayer.CONTEXT,
            fields=["ticker", "company_name", "trade_date"],
            required=True
        ),
        DataAccess(
            layer=DataLayer.RAW_DATA,
            fields=["news_data"],
            required=False  # 新闻可能没有
        ),
    ],
    outputs=[
        DataAccess(
            layer=DataLayer.ANALYSIS_DATA,
            fields=["news_sentiment"]
        ),
        DataAccess(
            layer=DataLayer.REPORTS,
            fields=["news_report"]
        ),
    ],
    depends_on=set()
)


# =========================================
# 社媒/情绪分析师 (Sentiment Analyst)
# =========================================
SENTIMENT_ANALYST_CONTRACT = AgentDataContract(
    agent_id="sentiment_analyst",
    description="情绪分析师 - 分析社交媒体情绪、投资者情绪",
    inputs=[
        DataAccess(
            layer=DataLayer.CONTEXT,
            fields=["ticker", "company_name", "trade_date"],
            required=True
        ),
        DataAccess(
            layer=DataLayer.RAW_DATA,
            fields=["social_data"],
            required=False
        ),
    ],
    outputs=[
        DataAccess(
            layer=DataLayer.ANALYSIS_DATA,
            fields=["sentiment"]
        ),
        DataAccess(
            layer=DataLayer.REPORTS,
            fields=["sentiment_report"]
        ),
    ],
    depends_on=set()
)


# =========================================
# 基本面分析师 (Fundamentals Analyst)
# =========================================
FUNDAMENTALS_ANALYST_CONTRACT = AgentDataContract(
    agent_id="fundamentals_analyst",
    description="基本面分析师 - 分析财务数据、估值指标",
    inputs=[
        DataAccess(
            layer=DataLayer.CONTEXT,
            fields=["ticker", "company_name", "trade_date"],
            required=True
        ),
        DataAccess(
            layer=DataLayer.RAW_DATA,
            fields=["financial_data"],
            required=True
        ),
    ],
    outputs=[
        DataAccess(
            layer=DataLayer.ANALYSIS_DATA,
            fields=["valuation"]
        ),
        DataAccess(
            layer=DataLayer.REPORTS,
            fields=["fundamentals_report"]
        ),
    ],
    depends_on=set()
)


# =========================================
# 板块分析师 (Sector Analyst)
# =========================================
SECTOR_ANALYST_CONTRACT = AgentDataContract(
    agent_id="sector_analyst",
    description="板块分析师 - 分析行业趋势、板块轮动、同业对比",
    inputs=[
        DataAccess(
            layer=DataLayer.CONTEXT,
            fields=["ticker", "company_name", "trade_date"],
            required=True
        ),
        DataAccess(
            layer=DataLayer.RAW_DATA,
            fields=["sector_data", "fund_flow_data"],
            required=False
        ),
    ],
    outputs=[
        DataAccess(
            layer=DataLayer.ANALYSIS_DATA,
            fields=["sector_ranking", "fund_flow_metrics"]
        ),
        DataAccess(
            layer=DataLayer.REPORTS,
            fields=["sector_report"]
        ),
    ],
    depends_on=set()
)


# =========================================
# 大盘/指数分析师 (Index Analyst)
# =========================================
INDEX_ANALYST_CONTRACT = AgentDataContract(
    agent_id="index_analyst",
    description="大盘分析师 - 分析指数走势、市场环境、系统性风险",
    inputs=[
        DataAccess(
            layer=DataLayer.CONTEXT,
            fields=["trade_date", "market_type"],
            required=True
        ),
        DataAccess(
            layer=DataLayer.RAW_DATA,
            fields=["index_data"],
            required=False
        ),
    ],
    outputs=[
        DataAccess(
            layer=DataLayer.ANALYSIS_DATA,
            fields=["market_breadth"]
        ),
        DataAccess(
            layer=DataLayer.REPORTS,
            fields=["index_report"]
        ),
    ],
    depends_on=set()
)


# =========================================
# 分析师契约汇总
# =========================================
ANALYST_CONTRACTS = {
    "market_analyst": MARKET_ANALYST_CONTRACT,
    "news_analyst": NEWS_ANALYST_CONTRACT,
    "sentiment_analyst": SENTIMENT_ANALYST_CONTRACT,
    "fundamentals_analyst": FUNDAMENTALS_ANALYST_CONTRACT,
    "sector_analyst": SECTOR_ANALYST_CONTRACT,
    "index_analyst": INDEX_ANALYST_CONTRACT,
}

