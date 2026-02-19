"""
空白工作流模板

最简单的空白流程，只包含开始和结束节点。
用户可以在此基础上自由添加自定义节点，构建个性化的分析流程。

适用场景:
- 自定义分析流程
- 学习工作流构建
- 快速原型开发
"""

from ..models import (
    WorkflowDefinition,
    NodeDefinition,
    EdgeDefinition,
    NodeType,
    EdgeType,
    Position,
)


BLANK_WORKFLOW = WorkflowDefinition(
    id="blank_workflow",
    name="空白流程",
    description="最简单的空白工作流模板，只包含开始和结束节点。用户可以在此基础上自由添加自定义节点，构建个性化的分析流程。适合学习工作流构建或快速原型开发。",
    version="2.0.0",  # 使用 v2.0 版本，支持 v2.0 Agent
    is_template=True,
    tags=["空白", "自定义", "模板", "v2.0"],  # 添加 v2.0 标签以便在前端显示
    
    config={
        "description": "这是一个空白工作流模板，您可以添加任意节点",
        "usage": "点击画布添加节点，拖拽连接节点创建流程",
    },
    
    nodes=[
        # 开始节点
        NodeDefinition(
            id="start",
            type=NodeType.START,
            label="开始",
            position=Position(x=400, y=50),
            config={
                "description": "工作流起点",
            }
        ),
        
        # 结束节点
        NodeDefinition(
            id="end",
            type=NodeType.END,
            label="结束",
            position=Position(x=400, y=500),
            config={
                "description": "工作流终点",
            }
        ),
    ],
    
    edges=[
        # 开始 -> 结束 (默认直连，用户可以删除此边并添加中间节点)
        EdgeDefinition(
            id="e_start_end",
            source="start",
            target="end",
            type=EdgeType.NORMAL,
            config={
                "description": "默认连接，可以删除并添加中间节点",
                "style": "dashed",  # 虚线表示这是临时连接
            }
        ),
    ],
)

