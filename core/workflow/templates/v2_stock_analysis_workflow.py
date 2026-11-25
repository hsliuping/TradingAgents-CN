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
    description="基于v2.0 Agent架构的单股研究分析流程。包含6个专业分析师并行收集证据，乐观与审慎两位情景研究员围绕核心论点展开多情景研究，研究经理形成平衡研究结论，研究整合员整理用户可读的整合意见，风险团队补充情景与约束，最终由风险评估师给出风险审阅结论与后续观察清单。",
    version="2.0.0",
    is_template=True,
    workflow_type="stock_analysis",
    tags=["v2.0", "完整分析", "多智能体", "多情景研究"],

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
            config={"description": "6个v2.0分析师并行分析宏观、行业、价格、财务、新闻与情绪证据"},
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
            config={"description": "收集所有分析师证据，进入多情景研究阶段"},
        ),

        # === 阶段3: 多情景研究（核心创新点）===
        NodeDefinition(
            id="debate",
            type=NodeType.DEBATE,
            label="多情景研究",
            position=Position(x=400, y=320),
            config={
                "rounds": "auto",
                "rounds_ref": "config.depth_rounds_mapping.{analysis_depth}.debate",
                "description": "乐观情景研究员与审慎情景研究员围绕研究证据、假设前提和失效条件进行多轮辩论",
                "participants": ["bull_researcher_v2", "bear_researcher_v2"],
            },
        ),

        NodeDefinition(
            id="bull_researcher_v2",
            type=NodeType.RESEARCHER,
            agent_id="bull_researcher_v2",
            label="乐观情景研究员 v2.0",
            position=Position(x=250, y=400),
            config={"stance": "bullish", "focus": "构建偏多论点，说明成立前提、证据链与潜在催化"},
        ),

        NodeDefinition(
            id="bear_researcher_v2",
            type=NodeType.RESEARCHER,
            agent_id="bear_researcher_v2",
            label="审慎情景研究员 v2.0",
            position=Position(x=550, y=400),
            config={"stance": "bearish", "focus": "构建偏审慎论证，识别脆弱点、反向证据与失效条件"},
        ),

        # === 阶段4: 研究经理综合评估 ===
        NodeDefinition(
            id="research_manager_v2",
            type=NodeType.MANAGER,
            agent_id="research_manager_v2",
            label="研究经理 v2.0",
            position=Position(x=400, y=480),
            config={
                "role": "综合多情景证据，形成平衡研究结论、关键分歧与观察重点",
                "delegated_agent_ids": ["chip_distribution_analyst_v2"],
            },
        ),

        # === 阶段5: 风险情景研究（3个风险分析师辩论）===
        NodeDefinition(
            id="risk_debate",
            type=NodeType.DEBATE,
            label="风险情景研究",
            position=Position(x=400, y=560),
            config={
                "rounds": "auto",
                "rounds_ref": "config.depth_rounds_mapping.{analysis_depth}.risk",
                "description": "高弹性、防御、基准三个风险分析师从不同稳健性框架审阅研究结论",
                "participants": ["risky_analyst_v2", "safe_analyst_v2", "neutral_analyst_v2"],
            },
        ),

        NodeDefinition(
            id="risky_analyst_v2",
            type=NodeType.RISK,
            agent_id="risky_analyst_v2",
            label="高弹性情景分析师 v2.0 🔥",
            position=Position(x=200, y=640),
            config={"role": "risky", "focus": "强调研究结论上修依赖的强化条件、催化证据与高要求前提"},
        ),

        NodeDefinition(
            id="safe_analyst_v2",
            type=NodeType.RISK,
            agent_id="safe_analyst_v2",
            label="防御情景分析师 v2.0 🛡️",
            position=Position(x=400, y=640),
            config={"role": "safe", "focus": "强调研究结论最脆弱的前提、关键风险来源与失效条件"},
        ),

        NodeDefinition(
            id="neutral_analyst_v2",
            type=NodeType.RISK,
            agent_id="neutral_analyst_v2",
            label="基准情景分析师 v2.0 ⚖️",
            position=Position(x=600, y=640),
            config={"role": "neutral", "focus": "比较证据质量、信息缺口与当前最稳妥的基准情景"},
        ),

        # === 阶段6: 风险评估师（裁决）===
        NodeDefinition(
            id="risk_manager_v2",
            type=NodeType.MANAGER,
            agent_id="risk_manager_v2",
            label="风险评估师 v2.0",
            position=Position(x=400, y=720),
            config={"role": "综合三方稳健性审阅，形成风险审阅结论、判断约束与调整条件"},
        ),

        # === 阶段7: 研究整合员（风险审阅后生成用户版结论）===
        NodeDefinition(
            id="trader_v2",
            type=NodeType.TRADER,
            agent_id="trader_v2",
            label="研究整合员 v2.0",
            position=Position(x=400, y=800),
            config={"role": "将风险审阅后的综合研究结论整理为用户可读的最终简报"},
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

        # === 阶段5: 研究经理 -> 风险辩论 ===
        EdgeDefinition(id="e_to_risk_debate", source="research_manager_v2", target="risk_debate"),

        # === 阶段6: 风险辩论 <-> 三个风险分析师（多轮讨论）===
        EdgeDefinition(
            id="e_rd1",
            source="risk_debate",
            target="risky_analyst_v2",
            label="高弹性情景",
            animated=True,
        ),
        EdgeDefinition(
            id="e_rd2",
            source="risk_debate",
            target="safe_analyst_v2",
            label="防御情景",
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

        # === 阶段6: 风险情景研究结束 -> 风险评估师裁决 ===
        EdgeDefinition(id="e_risk_judge", source="risk_debate", target="risk_manager_v2"),

        # === 阶段7: 风险评估师 -> 研究整合员 ===
        EdgeDefinition(id="e_trader", source="risk_manager_v2", target="trader_v2"),

        # === 阶段8: 研究整合员 -> 结束 ===
        EdgeDefinition(id="e_end", source="trader_v2", target="end"),
    ],
)

