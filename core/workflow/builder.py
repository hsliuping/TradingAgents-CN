"""
工作流构建器

从 WorkflowDefinition 构建 LangGraph 图
"""

from typing import Any, Callable, Dict, Optional

from langgraph.graph import StateGraph, START, END

from .models import (
    WorkflowDefinition,
    NodeDefinition,
    EdgeDefinition,
    NodeType,
    EdgeType,
)
from ..agents import AgentRegistry, AgentFactory, AgentConfig


class WorkflowBuilder:
    """
    工作流构建器
    
    将 WorkflowDefinition 转换为可执行的 LangGraph
    
    用法:
        builder = WorkflowBuilder()
        graph = builder.build(workflow_definition)
        result = graph.invoke({"ticker": "AAPL", "trade_date": "2024-01-15"})
    """
    
    def __init__(
        self,
        registry: Optional[AgentRegistry] = None,
        factory: Optional[AgentFactory] = None,
        default_config: Optional[AgentConfig] = None,
    ):
        from ..agents.registry import get_registry
        
        self.registry = registry or get_registry()
        self.factory = factory or AgentFactory(self.registry)
        self.default_config = default_config or AgentConfig()
        
        self._agents: Dict[str, Any] = {}  # 缓存创建的智能体
    
    def build(
        self,
        definition: WorkflowDefinition,
        state_schema: Optional[type] = None,
    ):
        """
        构建 LangGraph 图
        
        Args:
            definition: 工作流定义
            state_schema: 状态模式 (默认使用通用字典)
            
        Returns:
            编译后的 LangGraph
        """
        # 使用默认状态模式
        if state_schema is None:
            state_schema = self._get_default_state_schema()
        
        # 创建图
        graph = StateGraph(state_schema)
        
        # 添加节点
        for node in definition.nodes:
            if node.type not in (NodeType.START, NodeType.END):
                node_func = self._create_node_function(node)
                graph.add_node(node.id, node_func)
        
        # 添加边
        self._add_edges(graph, definition)
        
        # 编译
        return graph.compile()
    
    def _get_default_state_schema(self) -> type:
        """获取默认状态模式"""
        from typing import TypedDict, Optional, List, Any
        
        class WorkflowState(TypedDict, total=False):
            # 基本信息
            company_of_interest: str
            trade_date: str
            
            # 分析报告
            market_report: Optional[str]
            fundamentals_report: Optional[str]
            news_report: Optional[str]
            sentiment_report: Optional[str]
            sector_report: Optional[str]
            index_report: Optional[str]
            
            # 研究结果
            bull_report: Optional[str]
            bear_report: Optional[str]
            
            # 最终决策
            final_decision: Optional[str]
            risk_assessment: Optional[str]
            
            # 消息历史
            messages: List[Any]
            
            # 元数据
            session_id: Optional[str]
            workflow_id: Optional[str]
        
        return WorkflowState
    
    def _create_node_function(self, node: NodeDefinition) -> Callable:
        """为节点创建执行函数"""
        
        if node.type == NodeType.CONDITION:
            return self._create_condition_node(node)
        elif node.type == NodeType.PARALLEL:
            return self._create_parallel_node(node)
        elif node.type == NodeType.MERGE:
            return self._create_merge_node(node)
        else:
            return self._create_agent_node(node)
    
    def _create_agent_node(self, node: NodeDefinition) -> Callable:
        """创建智能体节点"""
        agent_id = node.agent_id
        
        if agent_id is None:
            raise ValueError(f"节点 {node.id} 缺少 agent_id")
        
        # 合并节点配置
        config = AgentConfig(**{
            **self.default_config.model_dump(),
            **node.config
        })
        
        # 尝试创建智能体
        if self.registry.is_registered(agent_id):
            agent = self.factory.create(agent_id, config)
            self._agents[node.id] = agent
            return agent
        else:
            # 智能体未实现，返回占位函数
            def placeholder_node(state):
                return {
                    f"{agent_id}_report": f"[{agent_id}] 智能体未实现"
                }
            return placeholder_node
    
    def _create_condition_node(self, node: NodeDefinition) -> Callable:
        """创建条件节点"""
        condition_expr = node.condition or "True"
        
        def condition_node(state):
            # 评估条件
            try:
                result = eval(condition_expr, {"state": state})
                return {"_condition_result": bool(result)}
            except Exception as e:
                return {"_condition_result": True, "_condition_error": str(e)}
        
        return condition_node
    
    def _create_parallel_node(self, node: NodeDefinition) -> Callable:
        """创建并行节点 (标记开始)"""
        def parallel_node(state):
            return {"_parallel_start": node.id}
        return parallel_node
    
    def _create_merge_node(self, node: NodeDefinition) -> Callable:
        """创建合并节点"""
        def merge_node(state):
            return {"_parallel_end": node.id}
        return merge_node
    
    def _add_edges(self, graph: StateGraph, definition: WorkflowDefinition) -> None:
        """添加边到图"""
        start_node = definition.get_start_node()
        
        if start_node:
            # 从 START 连接到第一个节点
            start_edges = definition.get_edges_from(start_node.id)
            for edge in start_edges:
                graph.add_edge(START, edge.target)
        
        # 添加其他边
        for edge in definition.edges:
            source_node = definition.get_node(edge.source)
            target_node = definition.get_node(edge.target)
            
            if source_node is None or target_node is None:
                continue
            
            # 跳过 START 节点的边 (已处理)
            if source_node.type == NodeType.START:
                continue
            
            # 处理 END 节点
            if target_node.type == NodeType.END:
                graph.add_edge(edge.source, END)
            elif edge.type == EdgeType.CONDITIONAL:
                # 条件边需要特殊处理
                self._add_conditional_edge(graph, edge, definition)
            else:
                graph.add_edge(edge.source, edge.target)
    
    def _add_conditional_edge(
        self,
        graph: StateGraph,
        edge: EdgeDefinition,
        definition: WorkflowDefinition
    ) -> None:
        """添加条件边"""
        # 获取所有从同一源出发的条件边
        all_edges = definition.get_edges_from(edge.source)
        
        # 构建路由函数
        def route(state):
            result = state.get("_condition_result", True)
            for e in all_edges:
                if e.condition == "true" and result:
                    return e.target
                elif e.condition == "false" and not result:
                    return e.target
            # 默认走第一条边
            return all_edges[0].target if all_edges else END
        
        # 添加条件边
        targets = {e.target for e in all_edges}
        graph.add_conditional_edges(edge.source, route, list(targets))

