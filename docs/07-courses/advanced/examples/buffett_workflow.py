"""
巴菲特价值投资工作流定义

本文件定义了一个基于巴菲特价值投资方法论的分析工作流。
工作流包含 8 个分析师并行分析、多空辩论、风险辩论、条件分支估值等环节。

使用方式：
1. 通过平台的"流程管理 → 从文件导入"功能导入此工作流
2. 或在编辑器中手动编排，参考本文件的节点和边定义

前置条件：
- 需要先在 Agent 工坊创建以下自定义 Agent：
  - moat_analyst_buffett（护城河分析师）
  - management_assessor_buffett（管理层评估师）
  - buffett_valuator（巴菲特估值师）
- 需要先在 Skill 工坊创建以下自定义 Skill：
  - get_roe_trend_analysis（ROE 趋势分析）
  - get_margin_of_safety（安全边际计算）
"""

from core.workflow.models import (
    WorkflowDefinition,
    NodeDefinition,
    EdgeDefinition,
    NodeType,
    EdgeType,
    Position,
)


BUFFETT_VALUE_INVESTING_WORKFLOW = WorkflowDefinition(
    id="buffett_value_investing",
    name="巴菲特价值投资工作流",
    description=(
        "基于巴菲特价值投资方法论的单股研究流程。"
        "8 个分析师并行分析（含护城河、管理层评估等巴菲特特色维度），"
        "多空研究员从巴菲特视角辩论，"
        "条件分支自动判断是否通过巴菲特初筛（护城河≥中等、ROE>15%、管理层≥良好），"
        "通过后进入巴菲特估值师计算安全边际，"
        "最终由研究整合员生成巴菲特风格投资建议。"
    ),
    version="1.0.0",
    is_template=True,
    workflow_type="stock_analysis",
    tags=["巴菲特", "价值投资", "护城河", "安全边际", "自定义流程"],

    # ── 工作流全局配置 ──
    config={
        "depth_rounds_mapping": {
            "1": {"debate": 1, "risk": 1},
            "2": {"debate": 1, "risk": 1},
            "3": {"debate": 1, "risk": 2},
            "4": {"debate": 2, "risk": 2},
            "5": {"debate": 3, "risk": 3},
        },
        # 巴菲特初筛条件
        "buffett_screening": {
            "moat_min": "中等",
            "roe_5yr_min": 15,
            "management_min": "良好",
        },
    },

    nodes=[
        # === 阶段 1: 开始 ===
        NodeDefinition(
            id="start",
            type=NodeType.START,
            label="开始",
            position=Position(x=400, y=0),
        ),

        # === 阶段 2: 并行分析（8 个分析师同时工作）===
        NodeDefinition(
            id="parallel_analysts",
            type=NodeType.PARALLEL,
            label="并行分析开始",
            position=Position(x=400, y=80),
            config={"description": "8 个分析师并行分析宏观、行业、财务、估值、护城河、管理层、新闻与情绪"},
        ),

        # 系统内置分析师（5 个）
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
            config={"focus": "行业趋势、板块轮动、同业对比（能力圈初筛）"},
        ),
        NodeDefinition(
            id="fundamentals_analyst_v2",
            type=NodeType.ANALYST,
            agent_id="fundamentals_analyst_v2",
            label="基本面分析师 v2.0",
            position=Position(x=350, y=160),
            config={"focus": "财务报表、ROE、利润稳定性、负债水平"},
        ),
        NodeDefinition(
            id="valuation_analyst_v2",
            type=NodeType.ANALYST,
            agent_id="valuation_analyst_v2",
            label="估值分析师 v2.0",
            position=Position(x=500, y=160),
            config={"focus": "PE/PB/DCF 估值、历史估值区间、同业对比"},
        ),
        NodeDefinition(
            id="news_analyst_v2",
            type=NodeType.ANALYST,
            agent_id="news_analyst_v2",
            label="新闻分析师 v2.0",
            position=Position(x=650, y=160),
            config={"focus": "财经新闻、公告、管理层公开表态"},
        ),
        NodeDefinition(
            id="social_analyst_v2",
            type=NodeType.ANALYST,
            agent_id="social_analyst_v2",
            label="社交媒体分析师 v2.0",
            position=Position(x=800, y=160),
            config={"focus": "社交媒体情绪、舆论热度"},
        ),

        # ★ 自定义分析师（2 个）—— 需通过 Agent 工坊创建
        NodeDefinition(
            id="moat_analyst_buffett",
            type=NodeType.ANALYST,
            agent_id="moat_analyst_buffett",
            label="护城河分析师 ★",
            position=Position(x=950, y=160),
            config={
                "focus": "品牌价值、成本优势、网络效应、转换成本、无形资产、规模优势",
                "dimensions": [
                    "品牌价值（定价权）",
                    "成本优势（规模效应）",
                    "网络效应",
                    "转换成本",
                    "无形资产（专利/牌照）",
                    "规模优势",
                ],
                "output_rating_field": "moat_rating",
                "rating_levels": ["无", "弱", "中等", "强", "极强"],
            },
        ),
        NodeDefinition(
            id="management_assessor_buffett",
            type=NodeType.ANALYST,
            agent_id="management_assessor_buffett",
            label="管理层评估师 ★",
            position=Position(x=1100, y=160),
            config={
                "focus": "资本配置能力、诚信度、股东导向、战略执行力、管理层稳定性",
                "dimensions": [
                    "资本配置能力",
                    "诚信度",
                    "股东导向",
                    "战略执行力",
                    "管理层稳定性",
                ],
                "output_rating_field": "management_rating",
                "rating_levels": ["差", "一般", "良好", "优秀"],
            },
        ),

        # 合并分析结果
        NodeDefinition(
            id="merge_analysts",
            type=NodeType.MERGE,
            label="汇总分析结果",
            position=Position(x=575, y=240),
            config={"description": "收集所有分析师证据，进入多空研究辩论阶段"},
        ),

        # === 阶段 3: 多空辩论（巴菲特视角）===
        NodeDefinition(
            id="debate",
            type=NodeType.DEBATE,
            label="多空辩论",
            position=Position(x=575, y=320),
            config={
                "rounds": "auto",
                "rounds_ref": "config.depth_rounds_mapping.{analysis_depth}.debate",
                "description": "乐观研究员与审慎研究员从巴菲特视角辩论：这是不是一家伟大的公司？",
                "participants": ["bull_researcher_v2", "bear_researcher_v2"],
            },
        ),

        NodeDefinition(
            id="bull_researcher_v2",
            type=NodeType.RESEARCHER,
            agent_id="bull_researcher_v2",
            label="乐观情景研究员 v2.0",
            position=Position(x=425, y=400),
            config={
                "stance": "bullish",
                "focus": "护城河来源与持久性、ROE 趋势验证、管理层优秀行为、10 年长期前景",
            },
        ),

        NodeDefinition(
            id="bear_researcher_v2",
            type=NodeType.RESEARCHER,
            agent_id="bear_researcher_v2",
            label="审慎情景研究员 v2.0",
            position=Position(x=725, y=400),
            config={
                "stance": "bearish",
                "focus": "护城河侵蚀风险、财务预警信号、管理层疑点、行业格局变化",
            },
        ),

        # === 阶段 4: 研究经理综合评估 ===
        NodeDefinition(
            id="research_manager_v2",
            type=NodeType.MANAGER,
            agent_id="research_manager_v2",
            label="研究经理 v2.0",
            position=Position(x=575, y=480),
            config={
                "role": "综合多空证据，应用巴菲特标准判断：伟大/好/普通/避开",
                "buffett_criteria": {
                    "great": "ROE>20%, 护城河强, 管理层优秀, 利润稳定增长",
                    "good": "ROE 15-20%, 护城河中等, 管理层良好",
                    "ordinary": "ROE<15% 或护城河弱",
                    "avoid": "亏损, 负债过高, 护城河收窄",
                },
            },
        ),

        # === 阶段 5: 风险辩论 ===
        NodeDefinition(
            id="risk_debate",
            type=NodeType.DEBATE,
            label="风险辩论",
            position=Position(x=575, y=560),
            config={
                "rounds": "auto",
                "rounds_ref": "config.depth_rounds_mapping.{analysis_depth}.risk",
                "description": "三方风险分析师审阅巴菲特判断的稳健性",
                "participants": ["risky_analyst_v2", "safe_analyst_v2", "neutral_analyst_v2"],
            },
        ),

        NodeDefinition(
            id="risky_analyst_v2",
            type=NodeType.RISK,
            agent_id="risky_analyst_v2",
            label="高弹性情景分析师 v2.0",
            position=Position(x=375, y=640),
            config={"focus": "护城河加深的催化条件、上行弹性"},
        ),
        NodeDefinition(
            id="safe_analyst_v2",
            type=NodeType.RISK,
            agent_id="safe_analyst_v2",
            label="防御情景分析师 v2.0",
            position=Position(x=575, y=640),
            config={"focus": "安全边际压力测试、最脆弱前提"},
        ),
        NodeDefinition(
            id="neutral_analyst_v2",
            type=NodeType.RISK,
            agent_id="neutral_analyst_v2",
            label="基准情景分析师 v2.0",
            position=Position(x=775, y=640),
            config={"focus": "基准情景下证据质量与信息缺口"},
        ),

        # === 阶段 6: 风险管理者裁决 ===
        NodeDefinition(
            id="risk_manager_v2",
            type=NodeType.MANAGER,
            agent_id="risk_manager_v2",
            label="风险管理者 v2.0",
            position=Position(x=575, y=720),
            config={"role": "综合三方审阅，形成风险治理结论"},
        ),

        # === 阶段 7: 条件分支 —— 巴菲特初筛 ===
        NodeDefinition(
            id="buffett_screening",
            type=NodeType.CONDITION,
            label="巴菲特初筛",
            position=Position(x=575, y=800),
            config={
                "description": "判断是否通过巴菲特初筛标准",
                "conditions": {
                    "pass": {
                        "expression": "moat_rating in ['中等','强','极强'] and roe_5yr_avg > 15 and management_rating in ['良好','优秀']",
                        "label": "通过",
                        "description": "护城河≥中等、5年平均ROE>15%、管理层≥良好",
                    },
                    "fail": {
                        "expression": "default_else",
                        "label": "不通过",
                        "description": "未通过巴菲特初筛，跳过估值环节",
                    },
                },
            },
        ),

        # === 阶段 8a: 通过 → 巴菲特估值师 ===
        NodeDefinition(
            id="buffett_valuator",
            type=NodeType.ANALYST,
            agent_id="buffett_valuator",
            label="巴菲特估值师 ★",
            position=Position(x=400, y=880),
            config={
                "focus": "Owner Earnings 计算、内在价值区间、安全边际",
                "owner_earnings_formula": "净利润 + 折旧摊销 - 资本支出 - 营运资金变化",
                "valuation_scenarios": ["保守", "基准", "乐观"],
                "margin_of_safety_thresholds": {
                    "attractive": 0.30,
                    "fair": 0.15,
                    "expensive": 0.0,
                },
            },
        ),

        # === 阶段 9: 研究整合员 ===
        NodeDefinition(
            id="trader_v2",
            type=NodeType.TRADER,
            agent_id="trader_v2",
            label="研究整合员 v2.0",
            position=Position(x=575, y=960),
            config={
                "role": "生成巴菲特风格投资建议",
                "output_format": "buffett_style",
            },
        ),

        # === 阶段 10: 结束 ===
        NodeDefinition(
            id="end",
            type=NodeType.END,
            label="结束",
            position=Position(x=575, y=1040),
        ),
    ],

    edges=[
        # 阶段 1: 开始 → 并行分析
        EdgeDefinition(id="e_start", source="start", target="parallel_analysts"),

        # 阶段 2: 并行 → 8 个分析师
        EdgeDefinition(id="e_p0", source="parallel_analysts", target="index_analyst_v2"),
        EdgeDefinition(id="e_p1", source="parallel_analysts", target="sector_analyst_v2"),
        EdgeDefinition(id="e_p2", source="parallel_analysts", target="fundamentals_analyst_v2"),
        EdgeDefinition(id="e_p3", source="parallel_analysts", target="valuation_analyst_v2"),
        EdgeDefinition(id="e_p4", source="parallel_analysts", target="news_analyst_v2"),
        EdgeDefinition(id="e_p5", source="parallel_analysts", target="social_analyst_v2"),
        EdgeDefinition(id="e_p6", source="parallel_analysts", target="moat_analyst_buffett"),
        EdgeDefinition(id="e_p7", source="parallel_analysts", target="management_assessor_buffett"),

        # 分析师 → 合并
        EdgeDefinition(id="e_m0", source="index_analyst_v2", target="merge_analysts"),
        EdgeDefinition(id="e_m1", source="sector_analyst_v2", target="merge_analysts"),
        EdgeDefinition(id="e_m2", source="fundamentals_analyst_v2", target="merge_analysts"),
        EdgeDefinition(id="e_m3", source="valuation_analyst_v2", target="merge_analysts"),
        EdgeDefinition(id="e_m4", source="news_analyst_v2", target="merge_analysts"),
        EdgeDefinition(id="e_m5", source="social_analyst_v2", target="merge_analysts"),
        EdgeDefinition(id="e_m6", source="moat_analyst_buffett", target="merge_analysts"),
        EdgeDefinition(id="e_m7", source="management_assessor_buffett", target="merge_analysts"),

        # 阶段 3: 合并 → 辩论
        EdgeDefinition(id="e_debate", source="merge_analysts", target="debate"),

        # 辩论 ↔ 研究员
        EdgeDefinition(id="e_d1", source="debate", target="bull_researcher_v2", label="辩论", animated=True),
        EdgeDefinition(id="e_d2", source="debate", target="bear_researcher_v2", label="辩论", animated=True),
        EdgeDefinition(id="e_d3", source="bull_researcher_v2", target="debate", label="回应", animated=True),
        EdgeDefinition(id="e_d4", source="bear_researcher_v2", target="debate", label="回应", animated=True),

        # 阶段 4: 辩论 → 研究经理
        EdgeDefinition(id="e_mgr", source="debate", target="research_manager_v2"),

        # 阶段 5: 研究经理 → 风险辩论
        EdgeDefinition(id="e_to_risk", source="research_manager_v2", target="risk_debate"),

        # 风险辩论 ↔ 三方分析师
        EdgeDefinition(id="e_rd1", source="risk_debate", target="risky_analyst_v2", label="激进", animated=True),
        EdgeDefinition(id="e_rd2", source="risk_debate", target="safe_analyst_v2", label="保守", animated=True),
        EdgeDefinition(id="e_rd3", source="risk_debate", target="neutral_analyst_v2", label="中性", animated=True),
        EdgeDefinition(id="e_rd4", source="risky_analyst_v2", target="risk_debate", label="反驳", animated=True),
        EdgeDefinition(id="e_rd5", source="safe_analyst_v2", target="risk_debate", label="反驳", animated=True),
        EdgeDefinition(id="e_rd6", source="neutral_analyst_v2", target="risk_debate", label="反驳", animated=True),

        # 阶段 6: 风险辩论 → 风险管理者
        EdgeDefinition(id="e_risk_judge", source="risk_debate", target="risk_manager_v2"),

        # 阶段 7: 风险管理者 → 条件分支
        EdgeDefinition(id="e_to_screening", source="risk_manager_v2", target="buffett_screening"),

        # 阶段 8: 条件分支 → 估值师（通过）或整合员（不通过）
        EdgeDefinition(
            id="e_screen_pass",
            source="buffett_screening",
            target="buffett_valuator",
            label="通过",
        ),
        EdgeDefinition(
            id="e_screen_fail",
            source="buffett_screening",
            target="trader_v2",
            label="不通过",
        ),

        # 阶段 9: 估值师 → 整合员
        EdgeDefinition(id="e_valuator_to_trader", source="buffett_valuator", target="trader_v2"),

        # 阶段 10: 整合员 → 结束
        EdgeDefinition(id="e_end", source="trader_v2", target="end"),
    ],
)
