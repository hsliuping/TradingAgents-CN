"""
简单工作流模板

只包含基本的分析流程，适合快速分析
"""

from ..models import (
    WorkflowDefinition,
    NodeDefinition,
    EdgeDefinition,
    NodeType,
    EdgeType,
    Position,
)


SIMPLE_WORKFLOW = WorkflowDefinition(
    id="simple_analysis",
    name="快速分析流",
    description="轻量级分析流程，适合快速获取市场观点。包含市场分析师和新闻分析师并行分析，交易员直接给出建议。省略了研究员辩论和风险管理环节，执行速度更快，适合日常快速决策参考。",
    version="1.0.0",
    is_template=True,
    tags=["快速", "轻量", "日常"],
    
    nodes=[
        # 开始节点
        NodeDefinition(
            id="start",
            type=NodeType.START,
            label="开始",
            position=Position(x=250, y=0),
        ),
        
        # 市场分析师
        NodeDefinition(
            id="market_analyst",
            type=NodeType.ANALYST,
            agent_id="market_analyst",
            label="市场分析师",
            position=Position(x=100, y=100),
        ),
        
        # 新闻分析师
        NodeDefinition(
            id="news_analyst",
            type=NodeType.ANALYST,
            agent_id="news_analyst",
            label="新闻分析师",
            position=Position(x=400, y=100),
        ),
        
        # 交易员
        NodeDefinition(
            id="trader",
            type=NodeType.TRADER,
            agent_id="trader",
            label="交易员",
            position=Position(x=250, y=200),
        ),
        
        # 结束节点
        NodeDefinition(
            id="end",
            type=NodeType.END,
            label="结束",
            position=Position(x=250, y=300),
        ),
    ],
    
    edges=[
        # 开始 -> 市场分析师
        EdgeDefinition(
            id="e1",
            source="start",
            target="market_analyst",
        ),
        
        # 开始 -> 新闻分析师
        EdgeDefinition(
            id="e2",
            source="start",
            target="news_analyst",
        ),
        
        # 市场分析师 -> 交易员
        EdgeDefinition(
            id="e3",
            source="market_analyst",
            target="trader",
        ),
        
        # 新闻分析师 -> 交易员
        EdgeDefinition(
            id="e4",
            source="news_analyst",
            target="trader",
        ),
        
        # 交易员 -> 结束
        EdgeDefinition(
            id="e5",
            source="trader",
            target="end",
        ),
    ],
)

