"""
分析师工作流扩展

提供动态添加分析师节点到工作流的能力，
无需修改 tradingagents/graph/setup.py

用法:
    from core.workflow.analyst_extension import AnalystWorkflowExtension
    from core.agents.analyst_registry import get_analyst_registry
    
    # 注册新分析师
    registry = get_analyst_registry()
    registry.register("sector", SectorAnalystAgent)
    
    # 创建扩展
    extension = AnalystWorkflowExtension(registry)
    
    # 在工作流构建时应用扩展
    extension.extend_workflow(workflow, selected_analysts=["sector", "index"])
"""

from typing import Dict, List, Optional, Callable, Any, Set
from langgraph.graph import StateGraph, END

from ..agents.analyst_registry import AnalystRegistry, get_analyst_registry
from ..agents.config import AgentMetadata

# 导入日志
from tradingagents.utils.logging_init import get_logger
logger = get_logger("default")


class AnalystWorkflowExtension:
    """
    分析师工作流扩展器
    
    将注册表中的分析师动态添加到工作流中
    """
    
    def __init__(
        self,
        registry: Optional[AnalystRegistry] = None,
        llm = None,
        toolkit = None
    ):
        self.registry = registry or get_analyst_registry()
        self.llm = llm
        self.toolkit = toolkit
        self._created_nodes: Dict[str, Callable] = {}
    
    def set_dependencies(self, llm, toolkit):
        """设置 LLM 和 Toolkit 依赖"""
        self.llm = llm
        self.toolkit = toolkit
    
    def extend_workflow(
        self,
        workflow: StateGraph,
        selected_analysts: List[str],
        existing_nodes: Set[str],
        delete_node_factory: Callable,
    ) -> Dict[str, Dict[str, Any]]:
        """
        扩展工作流，添加注册表中的分析师节点
        
        Args:
            workflow: LangGraph StateGraph 实例
            selected_analysts: 选中的分析师列表（如 ["sector", "index"]）
            existing_nodes: 已存在的节点集合（避免重复添加）
            delete_node_factory: 创建消息删除节点的工厂函数
            
        Returns:
            添加的分析师信息 {analyst_id: {node_name, metadata, requires_tools}}
        """
        added_analysts = {}
        
        for analyst_id in selected_analysts:
            # 检查是否已存在
            if analyst_id in existing_nodes:
                logger.debug(f"📋 [扩展] 分析师 {analyst_id} 已存在，跳过")
                continue
            
            # 检查是否已在注册表中注册实现
            if not self.registry.is_registered(analyst_id):
                logger.debug(f"📋 [扩展] 分析师 {analyst_id} 未注册实现，跳过")
                continue
            
            # 获取元数据
            metadata = self.registry.get_analyst_metadata(analyst_id)
            if not metadata:
                logger.warning(f"⚠️ [扩展] 分析师 {analyst_id} 无元数据")
                continue
            
            # 创建节点
            node_func = self._create_analyst_node(analyst_id, metadata)
            if node_func is None:
                continue
            
            # 添加到工作流
            node_name = metadata.node_name or f"{analyst_id.capitalize()} Analyst"
            workflow.add_node(node_name, node_func)
            
            # 添加消息删除节点
            clear_name = f"Msg Clear {analyst_id.capitalize()}"
            workflow.add_node(clear_name, delete_node_factory())
            
            logger.info(f"✅ [扩展] 添加分析师节点: {node_name}")
            
            added_analysts[analyst_id] = {
                "node_name": node_name,
                "clear_name": clear_name,
                "metadata": metadata,
                "requires_tools": metadata.requires_tools,
                "output_field": metadata.output_field,
                "execution_order": metadata.execution_order,
            }
        
        return added_analysts
    
    def _create_analyst_node(
        self, 
        analyst_id: str, 
        metadata: AgentMetadata
    ) -> Optional[Callable]:
        """
        创建分析师节点函数
        """
        # 尝试从注册表获取工厂函数
        factory = self.registry.get_analyst_factory(analyst_id)
        if factory:
            return factory(self.llm, self.toolkit)
        
        # 尝试从注册表获取类
        agent_class = self.registry.get_analyst_class(analyst_id)
        if agent_class:
            agent = agent_class()
            if hasattr(agent, 'set_dependencies'):
                agent.set_dependencies(self.llm, self.toolkit)
            return lambda state, a=agent: a.execute(state)
        
        logger.warning(f"⚠️ [扩展] 无法创建分析师 {analyst_id} 的节点")
        return None
    
    def connect_analysts(
        self,
        workflow: StateGraph,
        added_analysts: Dict[str, Dict[str, Any]],
        entry_point: str,
        exit_point: str,
    ):
        """
        连接分析师节点（按执行顺序串联）
        
        Args:
            workflow: LangGraph StateGraph 实例
            added_analysts: extend_workflow 返回的分析师信息
            entry_point: 入口节点（连接到第一个分析师）
            exit_point: 出口节点（最后一个分析师连接到此）
        """
        if not added_analysts:
            return
        
        # 按执行顺序排序
        sorted_analysts = sorted(
            added_analysts.items(),
            key=lambda x: x[1]["execution_order"]
        )
        
        # 连接节点
        prev_clear = entry_point
        for i, (analyst_id, info) in enumerate(sorted_analysts):
            node_name = info["node_name"]
            clear_name = info["clear_name"]
            requires_tools = info["requires_tools"]
            
            # 入口连接
            if prev_clear != entry_point:
                workflow.add_edge(prev_clear, node_name)
            
            # 无工具调用的分析师：直接连接到清理节点
            if not requires_tools:
                workflow.add_edge(node_name, clear_name)
            # 有工具调用的分析师：需要工具循环（由原始 setup.py 处理）
            
            prev_clear = clear_name
        
        # 最后一个清理节点连接到出口
        if sorted_analysts:
            last_clear = sorted_analysts[-1][1]["clear_name"]
            workflow.add_edge(last_clear, exit_point)

