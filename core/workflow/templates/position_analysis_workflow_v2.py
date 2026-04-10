"""
持仓分析工作流模板 v2.0

多维度分析持仓情况，包含:
1. 技术面分析师 v2.0 - 分析趋势结构、技术信号与验证重点
2. 基本面分析师 v2.0 - 分析财务数据、估值水平、行业地位
3. 风险评估师 v2.0 - 评估持仓风险与情景变化
4. 持仓研究整合师 v2.0 - 综合分析形成研究判断与观察事项
"""

from ..models import (
    WorkflowDefinition,
    NodeDefinition,
    EdgeDefinition,
    NodeType,
    EdgeType,
    Position,
)


POSITION_ANALYSIS_WORKFLOW_V2 = WorkflowDefinition(
    id="position_analysis_v2",
    name="持仓研究流程 v2.0",
    description="基于 v2.0 Agent 架构的持仓研究流程。技术面研究与基本面研究并行执行，随后进行风险复核，最后由研究整合员汇总形成持仓研究观察。",
    version="2.0.0",
    is_template=True,
    tags=["v2.0", "持仓", "研究", "多维度", "风险复核"],
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
        # 技术面分析师 v2.0
        NodeDefinition(
            id="pa_technical_v2",
            type=NodeType.ANALYST,
            agent_id="pa_technical_v2",
            label="持仓技术面分析师 v2.0",
            position=Position(x=100, y=300),
            config={"output_field": "technical_analysis"},
        ),
        # 基本面分析师 v2.0
        NodeDefinition(
            id="pa_fundamental_v2",
            type=NodeType.ANALYST,
            agent_id="pa_fundamental_v2",
            label="持仓基本面分析师 v2.0",
            position=Position(x=300, y=300),
            config={"output_field": "fundamental_analysis"},
        ),
        # 合并节点（合并技术面和基本面分析结果）
        NodeDefinition(
            id="merge",
            type=NodeType.MERGE,
            label="合并分析结果",
            position=Position(x=300, y=450),
        ),
        # 风险评估师 v2.0（在技术面和基本面分析之后执行）
        NodeDefinition(
            id="pa_risk_v2",
            type=NodeType.ANALYST,
            agent_id="pa_risk_v2",
            label="持仓风险评估师 v2.0",
            position=Position(x=300, y=550),
            config={"output_field": "risk_analysis"},
        ),
        # 持仓研究整合师 v2.0
        NodeDefinition(
            id="pa_advisor_v2",
            type=NodeType.MANAGER,
            agent_id="pa_advisor_v2",
            label="持仓研究整合师 v2.0",
            position=Position(x=300, y=650),
            config={"output_field": "action_advice"},
        ),
        # 结束节点
        NodeDefinition(
            id="end",
            type=NodeType.END,
            label="结束",
            position=Position(x=300, y=750),
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
            target="pa_technical_v2",
            type=EdgeType.NORMAL,
        ),
        EdgeDefinition(
            id="edge_parallel_fundamental",
            source="parallel_start",
            target="pa_fundamental_v2",
            type=EdgeType.NORMAL,
        ),
        # 两个分析师 -> 合并（技术面和基本面并行执行后合并）
        EdgeDefinition(
            id="edge_technical_merge",
            source="pa_technical_v2",
            target="merge",
            type=EdgeType.NORMAL,
        ),
        EdgeDefinition(
            id="edge_fundamental_merge",
            source="pa_fundamental_v2",
            target="merge",
            type=EdgeType.NORMAL,
        ),
        # 合并 -> 风险评估师（在技术面和基本面分析之后执行）
        EdgeDefinition(
            id="edge_merge_risk",
            source="merge",
            target="pa_risk_v2",
            type=EdgeType.NORMAL,
        ),
        # 风险评估师 -> 持仓研究整合师
        EdgeDefinition(
            id="edge_risk_advisor",
            source="pa_risk_v2",
            target="pa_advisor_v2",
            type=EdgeType.NORMAL,
        ),
        # 持仓研究整合师 -> 结束
        EdgeDefinition(
            id="edge_advisor_end",
            source="pa_advisor_v2",
            target="end",
            type=EdgeType.NORMAL,
        ),
    ],
)
