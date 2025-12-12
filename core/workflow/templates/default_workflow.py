"""
默认工作流模板

完整的分析流程，包含所有分析师和研究员
基于 TradingAgents 论文设计：
1. 6个分析师并行分析（大盘、板块、市场、基本面、新闻、社交媒体）
2. 看多/看空研究员进行多轮辩论
3. 研究经理综合观点
4. 交易员制定策略
5. 风险经理把控风险
"""

from ..models import (
    WorkflowDefinition,
    NodeDefinition,
    EdgeDefinition,
    NodeType,
    EdgeType,
    Position,
)


DEFAULT_WORKFLOW = WorkflowDefinition(
    id="default_analysis",
    name="TradingAgents 完整分析流",
    description="基于 TradingAgents 论文设计的完整多智能体协作分析流程。包含6个专业分析师（大盘、板块、市场、基本面、新闻、社交媒体）并行分析，2个研究员（看多/看空）进行多轮辩论，研究经理综合评估，交易员制定策略，风险团队多轮辩论评估风险。辩论轮次根据分析深度动态调整。",
    version="1.0.0",
    is_template=True,
    tags=["完整", "多智能体", "辩论机制", "风险管理"],

    # 工作流配置 - 辩论轮次根据分析深度动态调整
    # 分析深度与辩论轮次对应关系:
    # 1级(快速): 多空辩论1轮, 风险辩论1轮
    # 2级(基础): 多空辩论1轮, 风险辩论1轮
    # 3级(标准): 多空辩论1轮, 风险辩论2轮 (推荐)
    # 4级(深度): 多空辩论2轮, 风险辩论2轮
    # 5级(全面): 多空辩论3轮, 风险辩论3轮
    config={
        "analysis_depth": 3,  # 默认分析深度: 3级(标准)
        "debate_rounds": "auto",  # 多空辩论轮数: auto=根据分析深度自动设置
        "risk_debate_rounds": "auto",  # 风险辩论轮数: auto=根据分析深度自动设置
        "parallel_timeout": 300,  # 并行执行超时（秒）
        "memory_enabled": True,  # 启用历史记忆
        "online_tools": True,  # 使用在线工具
        # 分析深度到轮次的映射（供执行引擎参考）
        "depth_rounds_mapping": {
            "1": {"debate": 1, "risk": 1, "name": "快速"},
            "2": {"debate": 1, "risk": 1, "name": "基础"},
            "3": {"debate": 1, "risk": 2, "name": "标准"},
            "4": {"debate": 2, "risk": 2, "name": "深度"},
            "5": {"debate": 3, "risk": 3, "name": "全面"},
        }
    },

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
            config={"description": "6个分析师同时分析不同维度的数据"},
        ),

        # 🆕 宏观分析师（优先位置）
        NodeDefinition(
            id="index_analyst",
            type=NodeType.ANALYST,
            agent_id="index_analyst",
            label="大盘分析师",
            position=Position(x=50, y=160),
            config={"focus": "大盘指数走势、市场环境、系统性风险"},
        ),
        NodeDefinition(
            id="sector_analyst",
            type=NodeType.ANALYST,
            agent_id="sector_analyst",
            label="板块分析师",
            position=Position(x=200, y=160),
            config={"focus": "行业趋势、板块轮动、同业对比"},
        ),

        # 个股分析师
        NodeDefinition(
            id="market_analyst",
            type=NodeType.ANALYST,
            agent_id="market_analyst",
            label="市场分析师",
            position=Position(x=350, y=160),
            config={"focus": "价格走势、技术指标、成交量"},
        ),
        NodeDefinition(
            id="fundamentals_analyst",
            type=NodeType.ANALYST,
            agent_id="fundamentals_analyst",
            label="基本面分析师",
            position=Position(x=500, y=160),
            config={"focus": "财务报表、估值指标、盈利能力"},
        ),
        NodeDefinition(
            id="news_analyst",
            type=NodeType.ANALYST,
            agent_id="news_analyst",
            label="新闻分析师",
            position=Position(x=650, y=160),
            config={"focus": "财经新闻、公告、行业动态"},
        ),
        NodeDefinition(
            id="social_analyst",
            type=NodeType.ANALYST,
            agent_id="social_analyst",
            label="社交媒体分析师",
            position=Position(x=800, y=160),
            config={"focus": "社交媒体情绪、舆论热度"},
        ),

        # 合并分析结果
        NodeDefinition(
            id="merge_analysts",
            type=NodeType.MERGE,
            label="汇总分析结果",
            position=Position(x=400, y=240),
            config={"description": "收集所有分析师的报告，准备进入辩论阶段"},
        ),

        # === 阶段3: 多空辩论（核心创新点）===
        # 轮次根据分析深度动态调整: 1-2级=1轮, 3级=1轮, 4级=2轮, 5级=3轮
        NodeDefinition(
            id="debate",
            type=NodeType.DEBATE,
            label="多空辩论",
            position=Position(x=400, y=320),
            config={
                "rounds": "auto",  # auto=根据工作流config.analysis_depth自动设置
                "rounds_ref": "config.depth_rounds_mapping.{analysis_depth}.debate",
                "description": "看多和看空研究员基于分析报告进行多轮辩论，轮次根据分析深度动态调整",
                "participants": ["bull_researcher", "bear_researcher"],
            },
        ),

        NodeDefinition(
            id="bull_researcher",
            type=NodeType.RESEARCHER,
            agent_id="bull_researcher",
            label="看多研究员 🐂",
            position=Position(x=250, y=400),
            config={"role": "bull", "focus": "寻找投资机会和上涨逻辑"},
        ),
        NodeDefinition(
            id="bear_researcher",
            type=NodeType.RESEARCHER,
            agent_id="bear_researcher",
            label="看空研究员 🐻",
            position=Position(x=550, y=400),
            config={"role": "bear", "focus": "识别风险因素和下跌可能"},
        ),

        # === 阶段4: 决策层 ===
        NodeDefinition(
            id="research_manager",
            type=NodeType.MANAGER,
            agent_id="research_manager",
            label="研究经理",
            position=Position(x=400, y=500),
            config={"description": "综合多空观点，形成投资建议"},
        ),

        NodeDefinition(
            id="trader",
            type=NodeType.TRADER,
            agent_id="trader",
            label="交易员",
            position=Position(x=400, y=580),
            config={"description": "制定具体交易策略和仓位"},
        ),

        # === 阶段5: 风险辩论（3个角色多轮讨论）===
        # 轮次根据分析深度动态调整: 1-2级=1轮, 3-4级=2轮, 5级=3轮
        NodeDefinition(
            id="risk_debate",
            type=NodeType.DEBATE,
            label="风险辩论",
            position=Position(x=400, y=660),
            config={
                "rounds": "auto",  # auto=根据工作流config.analysis_depth自动设置
                "rounds_ref": "config.depth_rounds_mapping.{analysis_depth}.risk",
                "description": "激进、保守、中性三个风险分析师从不同角度评估交易计划，轮次根据分析深度动态调整",
                "participants": ["risky_analyst", "safe_analyst", "neutral_analyst"],
            },
        ),

        NodeDefinition(
            id="risky_analyst",
            type=NodeType.RISK,
            agent_id="risky_analyst",
            label="激进分析师 🔥",
            position=Position(x=200, y=740),
            config={"role": "risky", "focus": "寻求高收益机会，容忍较高风险"},
        ),
        NodeDefinition(
            id="safe_analyst",
            type=NodeType.RISK,
            agent_id="safe_analyst",
            label="保守分析师 🛡️",
            position=Position(x=400, y=740),
            config={"role": "safe", "focus": "优先考虑资本保护，规避风险"},
        ),
        NodeDefinition(
            id="neutral_analyst",
            type=NodeType.RISK,
            agent_id="neutral_analyst",
            label="中性分析师 ⚖️",
            position=Position(x=600, y=740),
            config={"role": "neutral", "focus": "平衡收益与风险，寻求最优解"},
        ),

        # === 阶段6: 风险经理裁决 ===
        NodeDefinition(
            id="risk_manager",
            type=NodeType.MANAGER,
            agent_id="risk_manager",
            label="风险经理（裁判）",
            position=Position(x=400, y=840),
            config={"description": "综合三方观点，做出最终风险调整决策"},
        ),

        # === 结束 ===
        NodeDefinition(
            id="end",
            type=NodeType.END,
            label="输出最终决策",
            position=Position(x=400, y=920),
        ),
    ],

    edges=[
        # 开始 -> 并行分析
        EdgeDefinition(id="e_start", source="start", target="parallel_analysts"),

        # 并行分析 -> 6个分析师
        EdgeDefinition(id="e_p0", source="parallel_analysts", target="index_analyst"),
        EdgeDefinition(id="e_p1", source="parallel_analysts", target="sector_analyst"),
        EdgeDefinition(id="e_p2", source="parallel_analysts", target="market_analyst"),
        EdgeDefinition(id="e_p3", source="parallel_analysts", target="fundamentals_analyst"),
        EdgeDefinition(id="e_p4", source="parallel_analysts", target="news_analyst"),
        EdgeDefinition(id="e_p5", source="parallel_analysts", target="social_analyst"),

        # 6个分析师 -> 合并
        EdgeDefinition(id="e_m0", source="index_analyst", target="merge_analysts"),
        EdgeDefinition(id="e_m1", source="sector_analyst", target="merge_analysts"),
        EdgeDefinition(id="e_m2", source="market_analyst", target="merge_analysts"),
        EdgeDefinition(id="e_m3", source="fundamentals_analyst", target="merge_analysts"),
        EdgeDefinition(id="e_m4", source="news_analyst", target="merge_analysts"),
        EdgeDefinition(id="e_m5", source="social_analyst", target="merge_analysts"),

        # 合并 -> 辩论节点
        EdgeDefinition(id="e_debate", source="merge_analysts", target="debate"),

        # 辩论节点 <-> 研究员（双向，表示多轮辩论）
        EdgeDefinition(
            id="e_d1",
            source="debate",
            target="bull_researcher",
            label="辩论",
            animated=True,
        ),
        EdgeDefinition(
            id="e_d2",
            source="debate",
            target="bear_researcher",
            label="辩论",
            animated=True,
        ),
        EdgeDefinition(
            id="e_d3",
            source="bull_researcher",
            target="debate",
            label="回应",
            animated=True,
        ),
        EdgeDefinition(
            id="e_d4",
            source="bear_researcher",
            target="debate",
            label="回应",
            animated=True,
        ),

        # 辩论结束 -> 研究经理
        EdgeDefinition(id="e_mgr", source="debate", target="research_manager"),

        # 研究经理 -> 交易员
        EdgeDefinition(id="e_trader", source="research_manager", target="trader"),

        # 交易员 -> 风险辩论
        EdgeDefinition(id="e_to_risk_debate", source="trader", target="risk_debate"),

        # 风险辩论 <-> 三个风险分析师（多轮讨论）
        EdgeDefinition(
            id="e_rd1",
            source="risk_debate",
            target="risky_analyst",
            label="激进观点",
            animated=True,
        ),
        EdgeDefinition(
            id="e_rd2",
            source="risk_debate",
            target="safe_analyst",
            label="保守观点",
            animated=True,
        ),
        EdgeDefinition(
            id="e_rd3",
            source="risk_debate",
            target="neutral_analyst",
            label="中性观点",
            animated=True,
        ),
        EdgeDefinition(
            id="e_rd4",
            source="risky_analyst",
            target="risk_debate",
            label="反驳",
            animated=True,
        ),
        EdgeDefinition(
            id="e_rd5",
            source="safe_analyst",
            target="risk_debate",
            label="反驳",
            animated=True,
        ),
        EdgeDefinition(
            id="e_rd6",
            source="neutral_analyst",
            target="risk_debate",
            label="反驳",
            animated=True,
        ),

        # 风险辩论结束 -> 风险经理裁决
        EdgeDefinition(id="e_risk_judge", source="risk_debate", target="risk_manager"),

        # 风险经理 -> 结束
        EdgeDefinition(id="e_end", source="risk_manager", target="end"),
    ],
)

