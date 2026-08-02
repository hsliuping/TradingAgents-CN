"""
v2.0 ETF 分析工作流模板

简化的 ETF 分析流程：ETF 分析师 + 市场分析师 + 新闻分析师，无牛熊辩论，单一风险分析
"""

from ..models import (
    WorkflowDefinition,
    NodeDefinition,
    EdgeDefinition,
    NodeType,
    Position,
)


V2_ETF_ANALYSIS_WORKFLOW = WorkflowDefinition(
    id="v2_etf_analysis",
    name="v2.0 ETF 分析流",
    description="ETF 专用分析流程。包含 ETF 分析师（净值、规模、跟踪误差）、市场分析师（技术面）、新闻分析师。无牛熊辩论，单一风险分析。",
    version="2.0.0",
    is_template=True,
    workflow_type="etf_analysis",
    tags=["v2.0", "ETF", "基金", "简化流程"],

    nodes=[
        NodeDefinition(
            id="start",
            type=NodeType.START,
            label="开始",
            position=Position(x=400, y=0),
        ),
        NodeDefinition(
            id="parallel_analysts",
            type=NodeType.PARALLEL,
            label="并行分析",
            position=Position(x=400, y=80),
            config={"description": "ETF 分析师、市场分析师、新闻分析师"},
        ),
        NodeDefinition(
            id="etf_analyst_v2",
            type=NodeType.ANALYST,
            agent_id="etf_analyst_v2",
            label="ETF 分析师 v2",
            position=Position(x=200, y=160),
            config={"focus": "净值、规模、费率、跟踪指数、跟踪误差"},
        ),
        NodeDefinition(
            id="market_analyst_v2",
            type=NodeType.ANALYST,
            agent_id="market_analyst_v2",
            label="市场分析师 v2",
            position=Position(x=400, y=160),
            config={"focus": "价格走势、技术指标"},
        ),
        NodeDefinition(
            id="news_analyst_v2",
            type=NodeType.ANALYST,
            agent_id="news_analyst_v2",
            label="新闻分析师 v2",
            position=Position(x=600, y=160),
            config={"focus": "ETF/指数相关新闻"},
        ),
        NodeDefinition(
            id="merge_analysts",
            type=NodeType.MERGE,
            label="汇总分析",
            position=Position(x=400, y=240),
            config={"description": "收集 ETF、市场、新闻分析报告"},
        ),
        NodeDefinition(
            id="research_manager_v2",
            type=NodeType.MANAGER,
            agent_id="research_manager_v2",
            label="研究经理 v2",
            position=Position(x=400, y=320),
            config={"role": "综合分析报告，形成研究结论"},
        ),
        NodeDefinition(
            id="trader_v2",
            type=NodeType.TRADER,
            agent_id="trader_v2",
            label="研究整合员 v2",
            position=Position(x=400, y=400),
            config={"role": "生成用户版研究简报"},
        ),
        NodeDefinition(
            id="safe_analyst_v2",
            type=NodeType.RISK,
            agent_id="safe_analyst_v2",
            label="风险分析师 v2",
            position=Position(x=400, y=480),
            config={"role": "safe", "focus": "跟踪误差、流动性、规模风险"},
        ),
        NodeDefinition(
            id="risk_manager_v2",
            type=NodeType.MANAGER,
            agent_id="risk_manager_v2",
            label="风险评估师 v2.0",
            position=Position(x=400, y=560),
            config={"role": "综合风险评估"},
        ),
        NodeDefinition(
            id="end",
            type=NodeType.END,
            label="结束",
            position=Position(x=400, y=640),
        ),
    ],

    edges=[
        EdgeDefinition(id="e_start", source="start", target="parallel_analysts"),
        EdgeDefinition(id="e_p0", source="parallel_analysts", target="etf_analyst_v2"),
        EdgeDefinition(id="e_p1", source="parallel_analysts", target="market_analyst_v2"),
        EdgeDefinition(id="e_p2", source="parallel_analysts", target="news_analyst_v2"),
        EdgeDefinition(id="e_m0", source="etf_analyst_v2", target="merge_analysts"),
        EdgeDefinition(id="e_m1", source="market_analyst_v2", target="merge_analysts"),
        EdgeDefinition(id="e_m2", source="news_analyst_v2", target="merge_analysts"),
        EdgeDefinition(id="e_mgr", source="merge_analysts", target="research_manager_v2"),
        EdgeDefinition(id="e_trader", source="research_manager_v2", target="trader_v2"),
        EdgeDefinition(id="e_risk", source="trader_v2", target="safe_analyst_v2"),
        EdgeDefinition(id="e_risk_mgr", source="safe_analyst_v2", target="risk_manager_v2"),
        EdgeDefinition(id="e_end", source="risk_manager_v2", target="end"),
    ],
)
