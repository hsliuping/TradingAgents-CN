"""
单智能体工作流模板

用于调试或执行单个 Agent 的工作流
"""

from typing import Any, Dict, Optional
from ..models import (
    WorkflowDefinition,
    NodeDefinition,
    EdgeDefinition,
    NodeType,
    EdgeType,
    Position,
)


def SingleAgentWorkflow(
    agent_id: str,
    config: Optional[Dict[str, Any]] = None
) -> WorkflowDefinition:
    """
    创建单智能体工作流模板
    
    Args:
        agent_id: 智能体 ID
        config: 工作流配置
        
    Returns:
        WorkflowDefinition: 工作流定义
    """
    config = config or {}
    
    # 提取 Agent 名称作为工作流名称的一部分
    agent_name = agent_id.replace("_", " ").title()
    
    return WorkflowDefinition(
        id=f"single_agent_{agent_id}",
        name=f"{agent_name} Workflow",
        description=f"Single agent workflow for {agent_id}",
        version="1.0.0",
        is_template=False,
        tags=["single", "debug", agent_id],
        config=config,
        
        nodes=[
            # 开始节点
            NodeDefinition(
                id="start",
                type=NodeType.START,
                label="开始",
                position=Position(x=0, y=0),
            ),
            
            # Agent 节点
            NodeDefinition(
                id=agent_id,
                type=NodeType.ANALYST,  # 假设都是分析师，如果不是可能需要调整
                agent_id=agent_id,
                label=agent_name,
                position=Position(x=200, y=0),
                config=config.get("agent_config", {})
            ),
            
            # 结束节点
            NodeDefinition(
                id="end",
                type=NodeType.END,
                label="结束",
                position=Position(x=400, y=0),
            )
        ],
        
        edges=[
            # Start -> Agent
            EdgeDefinition(
                id="edge_1",
                source="start",
                target=agent_id,
                type=EdgeType.NORMAL
            ),
            
            # Agent -> End
            EdgeDefinition(
                id="edge_2",
                source=agent_id,
                target="end",
                type=EdgeType.NORMAL
            )
        ]
    )
