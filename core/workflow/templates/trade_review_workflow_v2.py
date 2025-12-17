"""
交易复盘工作流模板 v2.0

多维度分析交易操作，包含:
1. 时机分析师 v2.0 - 分析买卖时机
2. 仓位分析师 v2.0 - 分析仓位管理
3. 情绪分析师 v2.0 - 分析情绪控制
4. 归因分析师 v2.0 - 分析收益来源
5. 复盘总结师 v2.0 - 综合总结报告
"""

from ..models import (
    WorkflowDefinition,
    NodeDefinition,
    EdgeDefinition,
    NodeType,
    EdgeType,
    Position,
)


TRADE_REVIEW_WORKFLOW_V2 = WorkflowDefinition(
    id="trade_review_v2",
    name="交易复盘分析流程 v2.0",
    description="基于 v2.0 Agent 架构的交易复盘流程。包含时机分析、仓位分析、情绪分析、归因分析四个专业分析师并行分析，最后由复盘总结师综合生成报告。",
    version="2.0.0",
    is_template=True,
    tags=["v2.0", "复盘", "交易分析", "多维度", "并行分析"],
    config={
        "workflow_type": "trade_review",
        "parallel_analysts": True,
        "output_format": "structured_report",
    },
    nodes=[
        # 开始节点
        NodeDefinition(
            id="start",
            type=NodeType.START,
            label="开始",
            position=Position(x=400, y=50),
        ),
        # 并行开始节点
        NodeDefinition(
            id="parallel_start",
            type=NodeType.PARALLEL,
            label="并行分析开始",
            position=Position(x=400, y=150),
        ),
        # 时机分析师 v2.0
        NodeDefinition(
            id="timing_analyst_v2",
            type=NodeType.ANALYST,
            agent_id="timing_analyst_v2",
            label="时机分析师 v2.0",
            position=Position(x=100, y=300),
            config={"output_field": "timing_analysis"},
        ),
        # 仓位分析师 v2.0
        NodeDefinition(
            id="position_analyst_v2",
            type=NodeType.ANALYST,
            agent_id="position_analyst_v2",
            label="仓位分析师 v2.0",
            position=Position(x=300, y=300),
            config={"output_field": "position_analysis"},
        ),
        # 情绪分析师 v2.0
        NodeDefinition(
            id="emotion_analyst_v2",
            type=NodeType.ANALYST,
            agent_id="emotion_analyst_v2",
            label="情绪分析师 v2.0",
            position=Position(x=500, y=300),
            config={"output_field": "emotion_analysis"},
        ),
        # 归因分析师 v2.0
        NodeDefinition(
            id="attribution_analyst_v2",
            type=NodeType.ANALYST,
            agent_id="attribution_analyst_v2",
            label="归因分析师 v2.0",
            position=Position(x=700, y=300),
            config={"output_field": "attribution_analysis"},
        ),
        # 合并节点
        NodeDefinition(
            id="merge",
            type=NodeType.MERGE,
            label="合并分析结果",
            position=Position(x=400, y=450),
        ),
        # 复盘总结师 v2.0
        NodeDefinition(
            id="review_manager_v2",
            type=NodeType.MANAGER,
            agent_id="review_manager_v2",
            label="复盘总结师 v2.0",
            position=Position(x=400, y=550),
            config={"output_field": "review_summary"},
        ),
        # 结束节点
        NodeDefinition(
            id="end",
            type=NodeType.END,
            label="结束",
            position=Position(x=400, y=650),
        ),
    ],
    edges=[
        # 开始 -> 并行开始
        EdgeDefinition(
            id="edge_start_parallel",
            source="start",
            target="parallel_start",
            type=EdgeType.NORMAL,
        ),
        # 并行开始 -> 四个分析师
        EdgeDefinition(
            id="edge_parallel_timing",
            source="parallel_start",
            target="timing_analyst_v2",
            type=EdgeType.NORMAL,
        ),
        EdgeDefinition(
            id="edge_parallel_position",
            source="parallel_start",
            target="position_analyst_v2",
            type=EdgeType.NORMAL,
        ),
        EdgeDefinition(
            id="edge_parallel_emotion",
            source="parallel_start",
            target="emotion_analyst_v2",
            type=EdgeType.NORMAL,
        ),
        EdgeDefinition(
            id="edge_parallel_attribution",
            source="parallel_start",
            target="attribution_analyst_v2",
            type=EdgeType.NORMAL,
        ),
        # 四个分析师 -> 合并
        EdgeDefinition(
            id="edge_timing_merge",
            source="timing_analyst_v2",
            target="merge",
            type=EdgeType.NORMAL,
        ),
        EdgeDefinition(
            id="edge_position_merge",
            source="position_analyst_v2",
            target="merge",
            type=EdgeType.NORMAL,
        ),
        EdgeDefinition(
            id="edge_emotion_merge",
            source="emotion_analyst_v2",
            target="merge",
            type=EdgeType.NORMAL,
        ),
        EdgeDefinition(
            id="edge_attribution_merge",
            source="attribution_analyst_v2",
            target="merge",
            type=EdgeType.NORMAL,
        ),
        # 合并 -> 复盘总结师
        EdgeDefinition(
            id="edge_merge_manager",
            source="merge",
            target="review_manager_v2",
            type=EdgeType.NORMAL,
        ),
        # 复盘总结师 -> 结束
        EdgeDefinition(
            id="edge_manager_end",
            source="review_manager_v2",
            target="end",
            type=EdgeType.NORMAL,
        ),
    ],
)
