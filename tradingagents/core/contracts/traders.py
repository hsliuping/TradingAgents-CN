# tradingagents/core/contracts/traders.py
"""
交易员和风控数据契约定义

定义交易员和风险管理 Agent 的输入/输出字段和依赖关系
"""

from tradingagents.core.engine.data_contract import (
    AgentDataContract,
    DataAccess,
    DataLayer,
)


# =========================================
# 交易员 (Trader)
# =========================================
TRADER_CONTRACT = AgentDataContract(
    agent_id="trader",
    description="交易员 - 根据研究结论和风险评估生成交易信号",
    inputs=[
        DataAccess(
            layer=DataLayer.CONTEXT,
            fields=["ticker", "company_name", "trade_date"],
            required=True
        ),
        DataAccess(
            layer=DataLayer.DECISIONS,
            fields=["investment_plan"],
            required=True
        ),
        DataAccess(
            layer=DataLayer.ANALYSIS_DATA,
            fields=["technical", "valuation"],
            required=False
        ),
    ],
    outputs=[
        DataAccess(
            layer=DataLayer.DECISIONS,
            fields=["trade_signal"]
        ),
    ],
    depends_on={"research_manager"}
)


# =========================================
# 激进风控 (Risky Risk Manager)
# =========================================
RISKY_RISK_CONTRACT = AgentDataContract(
    agent_id="risky_risk",
    description="激进风控 - 风险承受度高，倾向于更大的仓位和更激进的操作",
    inputs=[
        DataAccess(
            layer=DataLayer.CONTEXT,
            fields=["ticker", "company_name", "trade_date"],
            required=True
        ),
        DataAccess(
            layer=DataLayer.DECISIONS,
            fields=["trade_signal", "investment_plan"],
            required=True
        ),
        DataAccess(
            layer=DataLayer.ANALYSIS_DATA,
            fields=["technical"],
            required=False
        ),
    ],
    outputs=[
        DataAccess(
            layer=DataLayer.REPORTS,
            fields=["risky_risk_report"]
        ),
    ],
    depends_on={"trader"}
)


# =========================================
# 稳健风控 (Safe Risk Manager)
# =========================================
SAFE_RISK_CONTRACT = AgentDataContract(
    agent_id="safe_risk",
    description="稳健风控 - 风险承受度低，倾向于保守的仓位和谨慎的操作",
    inputs=[
        DataAccess(
            layer=DataLayer.CONTEXT,
            fields=["ticker", "company_name", "trade_date"],
            required=True
        ),
        DataAccess(
            layer=DataLayer.DECISIONS,
            fields=["trade_signal", "investment_plan"],
            required=True
        ),
        DataAccess(
            layer=DataLayer.ANALYSIS_DATA,
            fields=["technical"],
            required=False
        ),
    ],
    outputs=[
        DataAccess(
            layer=DataLayer.REPORTS,
            fields=["safe_risk_report"]
        ),
    ],
    depends_on={"trader"}
)


# =========================================
# 中性风控 (Neutral Risk Manager)
# =========================================
NEUTRAL_RISK_CONTRACT = AgentDataContract(
    agent_id="neutral_risk",
    description="中性风控 - 平衡风险和收益，倾向于适度的仓位",
    inputs=[
        DataAccess(
            layer=DataLayer.CONTEXT,
            fields=["ticker", "company_name", "trade_date"],
            required=True
        ),
        DataAccess(
            layer=DataLayer.DECISIONS,
            fields=["trade_signal", "investment_plan"],
            required=True
        ),
        DataAccess(
            layer=DataLayer.ANALYSIS_DATA,
            fields=["technical"],
            required=False
        ),
    ],
    outputs=[
        DataAccess(
            layer=DataLayer.REPORTS,
            fields=["neutral_risk_report"]
        ),
    ],
    depends_on={"trader"}
)


# =========================================
# 风控经理 (Risk Manager)
# =========================================
RISK_MANAGER_CONTRACT = AgentDataContract(
    agent_id="risk_manager",
    description="风控经理 - 综合三种风控意见，形成最终风险评估",
    inputs=[
        DataAccess(
            layer=DataLayer.CONTEXT,
            fields=["ticker", "company_name", "trade_date"],
            required=True
        ),
        DataAccess(
            layer=DataLayer.REPORTS,
            fields=["risky_risk_report", "safe_risk_report", "neutral_risk_report"],
            required=True
        ),
        DataAccess(
            layer=DataLayer.DECISIONS,
            fields=["trade_signal"],
            required=True
        ),
    ],
    outputs=[
        DataAccess(
            layer=DataLayer.DECISIONS,
            fields=["risk_assessment", "final_decision"]
        ),
    ],
    depends_on={"risky_risk", "safe_risk", "neutral_risk"}
)


# =========================================
# 交易员和风控契约汇总
# =========================================
TRADER_CONTRACTS = {
    "trader": TRADER_CONTRACT,
    "risky_risk": RISKY_RISK_CONTRACT,
    "safe_risk": SAFE_RISK_CONTRACT,
    "neutral_risk": NEUTRAL_RISK_CONTRACT,
    "risk_manager": RISK_MANAGER_CONTRACT,
}

