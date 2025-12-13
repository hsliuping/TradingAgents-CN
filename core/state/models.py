"""
状态层数据模型

定义 Agent IO 和状态字段的数据结构
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from enum import Enum


class FieldType(str, Enum):
    """字段类型"""
    STRING = "string"
    NUMBER = "number"
    BOOLEAN = "boolean"
    OBJECT = "object"
    ARRAY = "array"
    LIST_MESSAGES = "list[BaseMessage]"  # LangGraph 消息列表


class StateFieldDefinition(BaseModel):
    """
    状态字段定义
    
    用于描述工作流状态中的单个字段
    """
    name: str                           # 字段名称
    type: FieldType = FieldType.STRING  # 字段类型
    description: str = ""               # 字段描述
    required: bool = False              # 是否必需
    default: Optional[Any] = None       # 默认值
    
    # 来源信息
    source_agent: Optional[str] = None  # 产生该字段的 Agent ID
    is_input: bool = False              # 是否为工作流输入字段
    is_output: bool = False             # 是否为工作流输出字段


class AgentIODefinition(BaseModel):
    """
    Agent 输入输出定义
    
    声明 Agent 需要读取的字段和产出的字段
    """
    agent_id: str                       # Agent ID
    
    # 输入定义
    inputs: List[StateFieldDefinition] = Field(default_factory=list)
    
    # 输出定义
    outputs: List[StateFieldDefinition] = Field(default_factory=list)
    
    # 读取其他 Agent 的输出
    reads_from: List[str] = Field(default_factory=list)  # 字段名列表
    
    # 元数据
    version: str = "1.0.0"
    description: str = ""
    
    def get_required_fields(self) -> List[str]:
        """获取必需的输入字段名"""
        return [f.name for f in self.inputs if f.required]
    
    def get_output_field_names(self) -> List[str]:
        """获取输出字段名"""
        return [f.name for f in self.outputs]
    
    def validate_state(self, state: Dict[str, Any]) -> List[str]:
        """
        验证状态是否满足 Agent 的输入要求
        
        Returns:
            缺失字段列表
        """
        missing = []
        
        # 检查必需输入
        for field in self.inputs:
            if field.required and field.name not in state:
                missing.append(field.name)
        
        # 检查 reads_from 字段
        for field_name in self.reads_from:
            if field_name not in state:
                missing.append(field_name)
        
        return missing


class WorkflowStateSchema(BaseModel):
    """
    工作流状态 Schema
    
    描述整个工作流的状态结构
    """
    workflow_id: str                    # 工作流 ID
    fields: Dict[str, StateFieldDefinition] = Field(default_factory=dict)
    
    # 字段分类
    input_fields: List[str] = Field(default_factory=list)   # 输入字段
    output_fields: List[str] = Field(default_factory=list)  # 输出字段
    intermediate_fields: List[str] = Field(default_factory=list)  # 中间字段
    
    # Agent 依赖图
    agent_dependencies: Dict[str, List[str]] = Field(default_factory=dict)
    
    def get_field(self, name: str) -> Optional[StateFieldDefinition]:
        """获取字段定义"""
        return self.fields.get(name)

    def add_field(self, field: StateFieldDefinition) -> None:
        """添加字段"""
        self.fields[field.name] = field

        if field.is_input:
            self.input_fields.append(field.name)
        if field.is_output:
            self.output_fields.append(field.name)
        if not field.is_input and not field.is_output:
            self.intermediate_fields.append(field.name)

    def get_input_field_objects(self) -> List[StateFieldDefinition]:
        """获取输入字段对象列表"""
        return [self.fields[name] for name in self.input_fields if name in self.fields]

    def get_output_field_objects(self) -> List[StateFieldDefinition]:
        """获取输出字段对象列表"""
        return [self.fields[name] for name in self.output_fields if name in self.fields]

    def get_intermediate_field_objects(self) -> List[StateFieldDefinition]:
        """获取中间字段对象列表"""
        return [self.fields[name] for name in self.intermediate_fields if name in self.fields]
    
    def get_execution_order(self, agent_ids: List[str]) -> List[str]:
        """
        根据依赖关系计算执行顺序（拓扑排序）

        Args:
            agent_ids: 参与的 Agent ID 列表

        Returns:
            排序后的 Agent ID 列表
        """
        # 使用 Kahn 算法进行拓扑排序
        from collections import defaultdict, deque

        # 构建依赖图和入度表
        in_degree = {agent_id: 0 for agent_id in agent_ids}
        graph = defaultdict(list)  # agent_id -> [依赖它的 agent_ids]

        # 构建反向依赖图（谁依赖谁）
        for agent_id in agent_ids:
            deps = self.agent_dependencies.get(agent_id, [])
            # deps 是字段名列表，需要找到产生这些字段的 agent
            for dep_field in deps:
                # 查找产生该字段的 agent
                dep_agent = None
                for field_name, field_def in self.fields.items():
                    if field_name == dep_field and field_def.source_agent:
                        dep_agent = field_def.source_agent
                        break

                # 如果找到了依赖的 agent，建立依赖关系
                if dep_agent and dep_agent in agent_ids:
                    graph[dep_agent].append(agent_id)
                    in_degree[agent_id] += 1

        # Kahn 算法
        queue = deque([agent_id for agent_id in agent_ids if in_degree[agent_id] == 0])
        result = []

        while queue:
            agent_id = queue.popleft()
            result.append(agent_id)

            # 减少依赖该 agent 的其他 agent 的入度
            for dependent in graph[agent_id]:
                in_degree[dependent] -= 1
                if in_degree[dependent] == 0:
                    queue.append(dependent)

        # 如果结果长度不等于输入长度，说明有循环依赖
        if len(result) != len(agent_ids):
            # 回退到简单排序
            return sorted(agent_ids, key=lambda x: len(self.agent_dependencies.get(x, [])))

        return result

