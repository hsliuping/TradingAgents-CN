"""
持仓分析工作流模板

多维度分析持仓情况，包含:
1. 技术面分析师 - 分析K线走势、技术指标、支撑阻力
2. 基本面分析师 - 分析财务数据、估值水平、行业地位
3. 风险评估师 - 评估持仓风险、止损止盈建议
4. 操作建议师 - 综合分析给出操作建议
"""

from ..models import (
    WorkflowDefinition,
    NodeDefinition,
    EdgeDefinition,
    NodeType,
    EdgeType,
    Position,
)


POSITION_ANALYSIS_WORKFLOW = WorkflowDefinition(
    id="position_analysis",
    name="持仓分析流程",
    description="多维度分析持仓情况的完整流程。包含技术面分析、基本面分析、风险评估三个专业分析师并行分析，最后由操作建议师综合生成操作建议。",
    version="1.0.0",
    is_template=True,
    tags=["持仓", "分析", "多维度", "操作建议"],
    config={
        "workflow_type": "position_analysis",
        "parallel_analysts": True,
        "output_format": "structured_report",
    },
    nodes=[
        # 开始节点
        NodeDefinition(
            id="start",
            type=NodeType.START,
            label="开始",
            position=Position(x=300, y=50),
        ),
        # 并行开始节点
        NodeDefinition(
            id="parallel_start",
            type=NodeType.PARALLEL,
            label="并行分析开始",
            position=Position(x=300, y=150),
        ),
        # 技术面分析师
        NodeDefinition(
            id="pa_technical",
            type=NodeType.ANALYST,
            agent_id="pa_technical",
            label="持仓技术面分析师",
            position=Position(x=100, y=300),
            config={"output_field": "technical_analysis"},
        ),
        # 基本面分析师
        NodeDefinition(
            id="pa_fundamental",
            type=NodeType.ANALYST,
            agent_id="pa_fundamental",
            label="持仓基本面分析师",
            position=Position(x=300, y=300),
            config={"output_field": "fundamental_analysis"},
        ),
        # 风险评估师
        NodeDefinition(
            id="pa_risk",
            type=NodeType.ANALYST,
            agent_id="pa_risk",
            label="持仓风险评估师",
            position=Position(x=500, y=300),
            config={"output_field": "risk_analysis"},
        ),
        # 合并节点
        NodeDefinition(
            id="merge",
            type=NodeType.MERGE,
            label="合并分析结果",
            position=Position(x=300, y=450),
        ),
        # 操作建议师
        NodeDefinition(
            id="pa_advisor",
            type=NodeType.MANAGER,
            agent_id="pa_advisor",
            label="持仓操作建议师",
            position=Position(x=300, y=550),
            config={"output_field": "action_advice"},
        ),
        # 结束节点
        NodeDefinition(
            id="end",
            type=NodeType.END,
            label="结束",
            position=Position(x=300, y=650),
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
        # 并行开始 -> 三个分析师
        EdgeDefinition(
            id="edge_parallel_technical",
            source="parallel_start",
            target="pa_technical",
            type=EdgeType.NORMAL,
        ),
        EdgeDefinition(
            id="edge_parallel_fundamental",
            source="parallel_start",
            target="pa_fundamental",
            type=EdgeType.NORMAL,
        ),
        EdgeDefinition(
            id="edge_parallel_risk",
            source="parallel_start",
            target="pa_risk",
            type=EdgeType.NORMAL,
        ),
        # 三个分析师 -> 合并
        EdgeDefinition(
            id="edge_technical_merge",
            source="pa_technical",
            target="merge",
            type=EdgeType.NORMAL,
        ),
        EdgeDefinition(
            id="edge_fundamental_merge",
            source="pa_fundamental",
            target="merge",
            type=EdgeType.NORMAL,
        ),
        EdgeDefinition(
            id="edge_risk_merge",
            source="pa_risk",
            target="merge",
            type=EdgeType.NORMAL,
        ),
        # 合并 -> 操作建议师
        EdgeDefinition(
            id="edge_merge_advisor",
            source="merge",
            target="pa_advisor",
            type=EdgeType.NORMAL,
        ),
        # 操作建议师 -> 结束
        EdgeDefinition(
            id="edge_advisor_end",
            source="pa_advisor",
            target="end",
            type=EdgeType.NORMAL,
        ),
    ],
)

