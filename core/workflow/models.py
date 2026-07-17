"""
工作流数据模型定义
"""

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class NodeType(str, Enum):
    """节点类型"""
    START = "start"
    END = "end"
    ANALYST = "analyst"
    RESEARCHER = "researcher"
    TRADER = "trader"
    RISK = "risk"
    MANAGER = "manager"
    CONDITION = "condition"
    PARALLEL = "parallel"       # 并行开始
    MERGE = "merge"             # 并行合并
    DEBATE = "debate"           # 辩论节点（多轮对抗）
    POST_PROCESSOR = "post_processor"  # 后处理器（报告生成等）


class EdgeType(str, Enum):
    """边类型"""
    NORMAL = "normal"
    CONDITIONAL = "conditional"


class Position(BaseModel):
    """节点位置"""
    x: float = 0
    y: float = 0


class NodeDefinition(BaseModel):
    """
    工作流节点定义
    """
    id: str                          # 节点唯一 ID
    type: NodeType                   # 节点类型
    agent_id: Optional[str] = None   # 关联的智能体 ID
    label: str = ""                  # 显示标签
    
    # 位置 (用于前端渲染)
    position: Position = Field(default_factory=Position)
    
    # 节点配置
    config: Dict[str, Any] = Field(default_factory=dict)
    
    # 条件节点专用
    condition: Optional[str] = None  # 条件表达式
    
    class Config:
        use_enum_values = True


class EdgeDefinition(BaseModel):
    """
    工作流边定义
    """
    id: str                          # 边唯一 ID
    source: str                      # 源节点 ID
    target: str                      # 目标节点 ID
    type: EdgeType = EdgeType.NORMAL
    
    # 条件边专用
    condition: Optional[str] = None  # 条件标签 (如 "true", "false")
    
    # 样式
    label: Optional[str] = None
    animated: bool = False
    
    class Config:
        use_enum_values = True


class OutputStrategy(str, Enum):
    """产出物组装策略"""
    AUTO = "auto"
    COLLECT_ALL = "collect_all"
    SPECIFIED = "specified"
    LAST_NODE = "last_node"


class OutputFieldConfig(BaseModel):
    """单个输出字段的配置"""
    field_name: str
    display_name: str = ""
    category: str = ""
    order: int = 0
    is_primary: bool = False
    format_hint: str = "markdown"    # markdown | json_to_markdown | plain


class WorkflowOutputConfig(BaseModel):
    """工作流产出物配置"""
    strategy: OutputStrategy = OutputStrategy.AUTO
    fields: List[OutputFieldConfig] = Field(default_factory=list)
    primary_field: str = ""

    class Config:
        use_enum_values = True


# ==================== 输入参数定义 ====================

class InputFieldType(str, Enum):
    """输入参数控件类型"""
    STRING = "string"          # 单行文本
    TEXTAREA = "textarea"      # 多行文本
    NUMBER = "number"          # 数字
    BOOLEAN = "boolean"        # 开关
    DATE = "date"              # 日期选择
    SELECT = "select"          # 下拉选择
    MULTISELECT = "multiselect"  # 多选


class InputFieldConfig(BaseModel):
    """单个输入参数定义"""
    name: str                                # 参数名（传给后端的 key）
    label: str = ""                          # 表单显示标签
    type: InputFieldType = InputFieldType.STRING
    required: bool = False
    default: Optional[Any] = None            # 默认值
    description: str = ""                    # 参数描述/提示
    placeholder: str = ""                    # 输入框占位提示
    options: Optional[List[Any]] = None      # 选项列表（select/multiselect 时使用）
    option_labels: Optional[List[str]] = None  # 选项显示名（与 options 一一对应）
    min: Optional[float] = None              # 数值最小值
    max: Optional[float] = None              # 数值最大值
    group: str = ""                          # 分组标签（如"基本参数"/"高级参数"）
    order: int = 0                           # 排序

    class Config:
        use_enum_values = True


class WorkflowInputConfig(BaseModel):
    """工作流输入参数配置"""
    fields: List[InputFieldConfig] = Field(default_factory=list)

    class Config:
        use_enum_values = True


class WorkflowDefinition(BaseModel):
    """
    工作流定义
    
    描述一个完整的分析工作流，可以序列化为 JSON 存储
    """
    id: str                          # 工作流唯一 ID
    name: str                        # 工作流名称
    description: str = ""            # 描述
    version: str = "1.0.0"
    
    # 节点和边
    nodes: List[NodeDefinition] = Field(default_factory=list)
    edges: List[EdgeDefinition] = Field(default_factory=list)
    
    # 元数据
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    created_by: Optional[str] = None
    
    # 配置
    config: Dict[str, Any] = Field(default_factory=dict)
    
    # 产出物配置
    output_config: WorkflowOutputConfig = Field(
        default_factory=WorkflowOutputConfig
    )

    # 🆕 输入参数配置（定义工作流需要哪些输入参数，用于动态生成执行表单）
    input_config: WorkflowInputConfig = Field(
        default_factory=WorkflowInputConfig
    )
    
    # 标签
    tags: List[str] = Field(default_factory=list)
    is_template: bool = False        # 是否为模板
    workflow_type: Optional[str] = None  # 流程类型（stock_analysis/etf_analysis/position_analysis/trade_review/portfolio_health/general）
    
    def get_node(self, node_id: str) -> Optional[NodeDefinition]:
        """获取节点"""
        for node in self.nodes:
            if node.id == node_id:
                return node
        return None
    
    def get_edges_from(self, node_id: str) -> List[EdgeDefinition]:
        """获取从指定节点出发的边"""
        return [e for e in self.edges if e.source == node_id]
    
    def get_edges_to(self, node_id: str) -> List[EdgeDefinition]:
        """获取指向指定节点的边"""
        return [e for e in self.edges if e.target == node_id]
    
    def get_start_node(self) -> Optional[NodeDefinition]:
        """获取开始节点"""
        for node in self.nodes:
            if node.type == NodeType.START:
                return node
        return None
    
    def get_end_nodes(self) -> List[NodeDefinition]:
        """获取结束节点"""
        return [n for n in self.nodes if n.type == NodeType.END]
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return self.model_dump()
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "WorkflowDefinition":
        """从字典创建"""
        return cls.model_validate(data)
    
    def to_json(self) -> str:
        """转换为 JSON 字符串"""
        return self.model_dump_json(indent=2)
    
    @classmethod
    def from_json(cls, json_str: str) -> "WorkflowDefinition":
        """从 JSON 字符串创建"""
        return cls.model_validate_json(json_str)


class WorkflowExecutionState(str, Enum):
    """工作流执行状态"""
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class WorkflowExecution(BaseModel):
    """
    工作流执行记录
    """
    id: str                          # 执行 ID
    workflow_id: str                 # 工作流 ID
    state: WorkflowExecutionState = WorkflowExecutionState.PENDING
    
    # 输入输出
    inputs: Dict[str, Any] = Field(default_factory=dict)
    outputs: Dict[str, Any] = Field(default_factory=dict)
    
    # 节点执行状态
    node_states: Dict[str, str] = Field(default_factory=dict)
    current_node: Optional[str] = None
    
    # 时间戳
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    
    # 错误信息
    error: Optional[str] = None
    
    class Config:
        use_enum_values = True

