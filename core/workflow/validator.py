"""
工作流验证器

验证工作流定义的正确性
"""

from typing import List, Optional

from .models import (
    WorkflowDefinition,
    NodeDefinition,
    NodeType,
    EdgeType,
)


class ValidationError:
    """验证错误"""
    
    def __init__(self, code: str, message: str, node_id: Optional[str] = None):
        self.code = code
        self.message = message
        self.node_id = node_id
    
    def __str__(self):
        if self.node_id:
            return f"[{self.code}] 节点 '{self.node_id}': {self.message}"
        return f"[{self.code}] {self.message}"


class ValidationResult:
    """验证结果"""
    
    def __init__(self):
        self.errors: List[ValidationError] = []
        self.warnings: List[ValidationError] = []
    
    @property
    def is_valid(self) -> bool:
        return len(self.errors) == 0
    
    def add_error(self, code: str, message: str, node_id: Optional[str] = None):
        self.errors.append(ValidationError(code, message, node_id))
    
    def add_warning(self, code: str, message: str, node_id: Optional[str] = None):
        self.warnings.append(ValidationError(code, message, node_id))


class WorkflowValidator:
    """
    工作流验证器

    检查:
    - 必须有一个开始节点
    - 必须有至少一个结束节点
    - 所有节点必须可达
    - 智能体节点必须有 agent_id
    - 条件节点必须有条件表达式
    - 边的源和目标必须存在
    """

    def validate(self, definition: WorkflowDefinition, strict: bool = True) -> ValidationResult:
        """
        验证工作流定义

        Args:
            definition: 工作流定义
            strict: 是否严格验证（执行前验证需要 strict=True，保存时可以 strict=False）
        """
        result = ValidationResult()

        self._validate_basic_structure(definition, result, strict)

        # 只有在有节点时才进行后续验证
        if definition.nodes:
            self._validate_nodes(definition, result)
            self._validate_edges(definition, result)
            self._validate_connectivity(definition, result)

        return result

    def validate_for_save(self, definition: WorkflowDefinition) -> ValidationResult:
        """保存时验证 (宽松模式，允许空工作流)"""
        return self.validate(definition, strict=False)

    def validate_for_execute(self, definition: WorkflowDefinition) -> ValidationResult:
        """执行前验证 (严格模式，必须完整)"""
        return self.validate(definition, strict=True)

    def _validate_basic_structure(
        self,
        definition: WorkflowDefinition,
        result: ValidationResult,
        strict: bool = True
    ) -> None:
        """验证基本结构"""
        if not definition.id:
            result.add_error("MISSING_ID", "工作流缺少 ID")

        if not definition.name:
            result.add_error("MISSING_NAME", "工作流缺少名称")

        # 空节点检查：只在严格模式下报错
        if not definition.nodes:
            if strict:
                result.add_error("NO_NODES", "工作流没有节点")
            return

        # 检查开始节点
        start_nodes = [n for n in definition.nodes if n.type == NodeType.START]
        if len(start_nodes) == 0:
            if strict:
                result.add_error("NO_START", "工作流缺少开始节点")
        elif len(start_nodes) > 1:
            result.add_error("MULTIPLE_START", "工作流有多个开始节点")

        # 检查结束节点
        end_nodes = [n for n in definition.nodes if n.type == NodeType.END]
        if len(end_nodes) == 0:
            if strict:
                result.add_error("NO_END", "工作流缺少结束节点")
    
    def _validate_nodes(
        self,
        definition: WorkflowDefinition,
        result: ValidationResult
    ) -> None:
        """验证节点"""
        node_ids = set()
        
        for node in definition.nodes:
            # 检查 ID 唯一性
            if node.id in node_ids:
                result.add_error("DUPLICATE_NODE_ID", f"重复的节点 ID", node.id)
            node_ids.add(node.id)
            
            # 检查智能体节点 (不包括 DEBATE 节点，它是协调节点不需要 agent_id)
            if node.type in (NodeType.ANALYST, NodeType.RESEARCHER,
                           NodeType.TRADER, NodeType.RISK, NodeType.MANAGER):
                if not node.agent_id:
                    result.add_error("MISSING_AGENT_ID", "智能体节点缺少 agent_id", node.id)
            
            # 检查条件节点
            if node.type == NodeType.CONDITION:
                if not node.condition:
                    result.add_warning("MISSING_CONDITION", "条件节点缺少条件表达式", node.id)
    
    def _validate_edges(
        self,
        definition: WorkflowDefinition,
        result: ValidationResult
    ) -> None:
        """验证边"""
        node_ids = {n.id for n in definition.nodes}
        edge_ids = set()
        
        for edge in definition.edges:
            # 检查 ID 唯一性
            if edge.id in edge_ids:
                result.add_error("DUPLICATE_EDGE_ID", f"重复的边 ID: {edge.id}")
            edge_ids.add(edge.id)
            
            # 检查源节点存在
            if edge.source not in node_ids:
                result.add_error("INVALID_SOURCE", f"边的源节点不存在: {edge.source}")
            
            # 检查目标节点存在
            if edge.target not in node_ids:
                result.add_error("INVALID_TARGET", f"边的目标节点不存在: {edge.target}")
            
            # 检查条件边
            if edge.type == EdgeType.CONDITIONAL and not edge.condition:
                result.add_warning("MISSING_EDGE_CONDITION", f"条件边缺少条件: {edge.id}")
    
    def _validate_connectivity(
        self,
        definition: WorkflowDefinition,
        result: ValidationResult
    ) -> None:
        """验证连通性"""
        if not definition.nodes:
            return
        
        # 从开始节点进行 BFS
        start_node = definition.get_start_node()
        if not start_node:
            return
        
        visited = set()
        queue = [start_node.id]
        
        while queue:
            node_id = queue.pop(0)
            if node_id in visited:
                continue
            visited.add(node_id)
            
            # 获取所有出边
            for edge in definition.get_edges_from(node_id):
                if edge.target not in visited:
                    queue.append(edge.target)
        
        # 检查未访问的节点 (排除 START 和 END)
        all_node_ids = {n.id for n in definition.nodes}
        unreachable = all_node_ids - visited
        
        for node_id in unreachable:
            node = definition.get_node(node_id)
            if node and node.type not in (NodeType.START, NodeType.END):
                result.add_warning("UNREACHABLE_NODE", "节点不可达", node_id)

