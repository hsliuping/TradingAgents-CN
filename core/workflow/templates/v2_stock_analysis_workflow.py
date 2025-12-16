"""
v2.0 股票分析工作流模板

使用v2.0 Agent基类架构的完整股票分析流程
"""

from ..models import (
    WorkflowDefinition,
    NodeDefinition,
    EdgeDefinition,
    NodeType,
    EdgeType,
    Position,
)


V2_STOCK_ANALYSIS_WORKFLOW = WorkflowDefinition(
    id="v2_stock_analysis",
    name="v2.0 完整分析流",
    description="基于v2.0 Agent架构的完整多智能体协作分析流程。包含6个专业分析师（大盘、板块、市场、基本面、新闻、社交媒体）并行分析，2个研究员（看多/看空）进行多轮辩论，研究经理综合评估，交易员制定策略，风险经理把控风险。",
    version="2.0.0",
    is_template=True,
    tags=["v2.0", "完整分析", "多智能体", "辩论机制"],

    nodes=[
        # === 阶段1: 开始 ===
        NodeDefinition(
            id="start",
            type=NodeType.START,
            label="开始",
            position=Position(x=400, y=0),
        ),

        # === 阶段2: 并行分析（6个分析师同时工作）===
        NodeDefinition(
            id="parallel_analysts",
            type=NodeType.PARALLEL,
            label="并行分析开始",
            position=Position(x=400, y=80),
            config={"description": "6个v2.0分析师同时分析不同维度的数据"},
        ),

        # 🆕 宏观分析师（优先位置）
        NodeDefinition(
            id="index_analyst_v2",
            type=NodeType.ANALYST,
            agent_id="index_analyst_v2",
            label="大盘分析师 v2.0",
            position=Position(x=50, y=160),
            config={"focus": "大盘指数走势、市场环境、系统性风险"},
        ),
        NodeDefinition(
            id="sector_analyst_v2",
            type=NodeType.ANALYST,
            agent_id="sector_analyst_v2",
            label="板块分析师 v2.0",
            position=Position(x=200, y=160),
            config={"focus": "行业趋势、板块轮动、同业对比"},
        ),

        # 个股分析师
        NodeDefinition(
            id="market_analyst_v2",
            type=NodeType.ANALYST,
            agent_id="market_analyst_v2",
            label="市场分析师 v2.0",
            position=Position(x=350, y=160),
            config={"focus": "价格走势、技术指标、成交量"},
        ),
        NodeDefinition(
            id="fundamentals_analyst_v2",
            type=NodeType.ANALYST,
            agent_id="fundamentals_analyst_v2",
            label="基本面分析师 v2.0",
            position=Position(x=500, y=160),
            config={"focus": "财务报表、估值指标、盈利能力"},
        ),
        NodeDefinition(
            id="news_analyst_v2",
            type=NodeType.ANALYST,
            agent_id="news_analyst_v2",
            label="新闻分析师 v2.0",
            position=Position(x=650, y=160),
            config={"focus": "财经新闻、公告、行业动态"},
        ),
        NodeDefinition(
            id="social_analyst_v2",
            type=NodeType.ANALYST,
            agent_id="social_analyst_v2",
            label="社交媒体分析师 v2.0",
            position=Position(x=800, y=160),
            config={"focus": "社交媒体情绪、舆论热度"},
        ),

        # 合并分析结果
        NodeDefinition(
            id="merge_analysts",
            type=NodeType.MERGE,
            label="汇总分析结果",
            position=Position(x=400, y=240),
            config={"description": "收集所有v2.0分析师的报告，准备进入辩论阶段"},
        ),

        # === 阶段3: 多空辩论（核心创新点）===
        NodeDefinition(
            id="debate",
            type=NodeType.DEBATE,
            label="多空辩论",
            position=Position(x=400, y=320),
            config={
                "rounds": "auto",
                "rounds_ref": "config.depth_rounds_mapping.{analysis_depth}.debate",
                "description": "v2.0看多和看空研究员基于分析报告进行多轮辩论",
                "participants": ["bull_researcher_v2", "bear_researcher_v2"],
            },
        ),

        NodeDefinition(
            id="bull_researcher_v2",
            type=NodeType.RESEARCHER,
            agent_id="bull_researcher_v2",
            label="看多研究员 v2.0",
            position=Position(x=250, y=400),
            config={"stance": "bullish", "focus": "寻找买入理由和上涨潜力"},
        ),

        NodeDefinition(
            id="bear_researcher_v2",
            type=NodeType.RESEARCHER,
            agent_id="bear_researcher_v2",
            label="看空研究员 v2.0",
            position=Position(x=550, y=400),
            config={"stance": "bearish", "focus": "识别风险和下跌因素"},
        ),

        # === 阶段4: 研究经理综合评估 ===
        NodeDefinition(
            id="research_manager_v2",
            type=NodeType.MANAGER,
            agent_id="research_manager_v2",
            label="研究经理 v2.0",
            position=Position(x=400, y=480),
            config={"role": "综合看多看空观点，做出投资决策"},
        ),

        # === 阶段5: 交易员（先制定初步计划）===
        NodeDefinition(
            id="trader_v2",
            type=NodeType.TRADER,
            agent_id="trader_v2",
            label="交易员 v2.0",
            position=Position(x=400, y=560),
            config={"role": "根据研究结论制定初步交易计划"},
        ),

        # === 阶段6: 风险辩论（3个风险分析师辩论）===
        NodeDefinition(
            id="risk_debate",
            type=NodeType.DEBATE,
            label="风险辩论",
            position=Position(x=400, y=640),
            config={
                "rounds": "auto",
                "rounds_ref": "config.depth_rounds_mapping.{analysis_depth}.risk",
                "description": "激进、保守、中性三个风险分析师从不同角度评估交易计划",
                "participants": ["risky_analyst_v2", "safe_analyst_v2", "neutral_analyst_v2"],
            },
        ),

        NodeDefinition(
            id="risky_analyst_v2",
            type=NodeType.RISK,
            agent_id="risky_analyst_v2",
            label="激进分析师 v2.0 🔥",
            position=Position(x=200, y=720),
            config={"role": "risky", "focus": "寻求高收益机会，容忍较高风险"},
        ),

        NodeDefinition(
            id="safe_analyst_v2",
            type=NodeType.RISK,
            agent_id="safe_analyst_v2",
            label="保守分析师 v2.0 🛡️",
            position=Position(x=400, y=720),
            config={"role": "safe", "focus": "优先考虑资本保护，规避风险"},
        ),

        NodeDefinition(
            id="neutral_analyst_v2",
            type=NodeType.RISK,
            agent_id="neutral_analyst_v2",
            label="中性分析师 v2.0 ⚖️",
            position=Position(x=600, y=720),
            config={"role": "neutral", "focus": "平衡收益与风险，寻求最优解"},
        ),

        # === 阶段7: 风险经理（裁决）===
        NodeDefinition(
            id="risk_manager_v2",
            type=NodeType.MANAGER,
            agent_id="risk_manager_v2",
            label="风险经理 v2.0",
            position=Position(x=400, y=800),
            config={"role": "综合三方风险观点，形成最终风险评估和调整建议"},
        ),

        # === 阶段8: 结束 ===
        NodeDefinition(
            id="end",
            type=NodeType.END,
            label="结束",
            position=Position(x=400, y=880),
        ),
    ],
    
    edges=[
        # === 阶段1: 开始 -> 并行分析 ===
        EdgeDefinition(id="e_start", source="start", target="parallel_analysts"),

        # === 阶段2: 并行分析 -> 6个分析师 ===
        EdgeDefinition(id="e_p0", source="parallel_analysts", target="index_analyst_v2"),
        EdgeDefinition(id="e_p1", source="parallel_analysts", target="sector_analyst_v2"),
        EdgeDefinition(id="e_p2", source="parallel_analysts", target="market_analyst_v2"),
        EdgeDefinition(id="e_p3", source="parallel_analysts", target="fundamentals_analyst_v2"),
        EdgeDefinition(id="e_p4", source="parallel_analysts", target="news_analyst_v2"),
        EdgeDefinition(id="e_p5", source="parallel_analysts", target="social_analyst_v2"),

        # === 阶段2: 分析师 -> 合并节点 ===
        EdgeDefinition(id="e_m0", source="index_analyst_v2", target="merge_analysts"),
        EdgeDefinition(id="e_m1", source="sector_analyst_v2", target="merge_analysts"),
        EdgeDefinition(id="e_m2", source="market_analyst_v2", target="merge_analysts"),
        EdgeDefinition(id="e_m3", source="fundamentals_analyst_v2", target="merge_analysts"),
        EdgeDefinition(id="e_m4", source="news_analyst_v2", target="merge_analysts"),
        EdgeDefinition(id="e_m5", source="social_analyst_v2", target="merge_analysts"),

        # === 阶段3: 合并 -> 辩论节点 ===
        EdgeDefinition(id="e_debate", source="merge_analysts", target="debate"),

        # === 阶段3: 辩论节点 <-> 研究员（双向，表示多轮辩论）===
        EdgeDefinition(
            id="e_d1",
            source="debate",
            target="bull_researcher_v2",
            label="辩论",
            animated=True,
        ),
        EdgeDefinition(
            id="e_d2",
            source="debate",
            target="bear_researcher_v2",
            label="辩论",
            animated=True,
        ),
        EdgeDefinition(
            id="e_d3",
            source="bull_researcher_v2",
            target="debate",
            label="回应",
            animated=True,
        ),
        EdgeDefinition(
            id="e_d4",
            source="bear_researcher_v2",
            target="debate",
            label="回应",
            animated=True,
        ),

        # === 阶段4: 辩论结束 -> 研究经理 ===
        EdgeDefinition(id="e_mgr", source="debate", target="research_manager_v2"),

        # === 阶段5: 研究经理 -> 交易员 ===
        EdgeDefinition(id="e_trader", source="research_manager_v2", target="trader_v2"),

        # === 阶段6: 交易员 -> 风险辩论 ===
        EdgeDefinition(id="e_to_risk_debate", source="trader_v2", target="risk_debate"),

        # === 阶段6: 风险辩论 <-> 三个风险分析师（多轮讨论）===
        EdgeDefinition(
            id="e_rd1",
            source="risk_debate",
            target="risky_analyst_v2",
            label="激进观点",
            animated=True,
        ),
        EdgeDefinition(
            id="e_rd2",
            source="risk_debate",
            target="safe_analyst_v2",
            label="保守观点",
            animated=True,
        ),
        EdgeDefinition(
            id="e_rd3",
            source="risk_debate",
            target="neutral_analyst_v2",
            label="中性观点",
            animated=True,
        ),
        EdgeDefinition(
            id="e_rd4",
            source="risky_analyst_v2",
            target="risk_debate",
            label="反驳",
            animated=True,
        ),
        EdgeDefinition(
            id="e_rd5",
            source="safe_analyst_v2",
            target="risk_debate",
            label="反驳",
            animated=True,
        ),
        EdgeDefinition(
            id="e_rd6",
            source="neutral_analyst_v2",
            target="risk_debate",
            label="反驳",
            animated=True,
        ),

        # === 阶段7: 风险辩论结束 -> 风险经理裁决 ===
        EdgeDefinition(id="e_risk_judge", source="risk_debate", target="risk_manager_v2"),

        # === 阶段8: 风险经理 -> 结束 ===
        EdgeDefinition(id="e_end", source="risk_manager_v2", target="end"),
    ],
)

