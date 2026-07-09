# 工作流引擎设计

## 📋 概述

工作流引擎是实现"可视化定义流程"的核心模块，负责：
1. 工作流定义的存储和管理
2. 从 JSON 定义动态构建 LangGraph
3. 工作流的执行和状态管理

---

## 🗂️ 数据模型

### WorkflowDefinition (工作流定义)

```python
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from enum import Enum
from datetime import datetime

class NodeType(str, Enum):
    """节点类型"""
    ANALYST = "analyst"           # 分析师节点
    RESEARCHER = "researcher"     # 研究员节点
    TRADER = "trader"             # 交易员节点
    RISK = "risk"                 # 风险评估节点
    MANAGER = "manager"           # 管理者节点
    CONDITION = "condition"       # 条件判断节点
    PARALLEL = "parallel"         # 并行执行节点
    MERGE = "merge"               # 合并节点

class NodeDefinition(BaseModel):
    """节点定义"""
    id: str = Field(..., description="节点唯一ID")
    type: NodeType = Field(..., description="节点类型")
    agent_id: str = Field(..., description="关联的智能体ID")
    name: str = Field(..., description="节点显示名称")
    position: Dict[str, float] = Field(default_factory=lambda: {"x": 0, "y": 0})
    config: Dict[str, Any] = Field(default_factory=dict, description="节点配置")
    
class EdgeDefinition(BaseModel):
    """边定义"""
    id: str = Field(..., description="边唯一ID")
    source: str = Field(..., description="源节点ID")
    target: str = Field(..., description="目标节点ID")
    source_handle: Optional[str] = None  # 源节点连接点
    target_handle: Optional[str] = None  # 目标节点连接点
    condition: Optional[str] = None      # 条件表达式 (用于条件边)
    label: Optional[str] = None          # 边标签

class WorkflowVariable(BaseModel):
    """工作流变量"""
    name: str
    type: str  # string, number, boolean, list
    default: Any = None
    description: str = ""

class WorkflowDefinition(BaseModel):
    """工作流定义"""
    id: str = Field(..., description="工作流唯一ID")
    name: str = Field(..., description="工作流名称")
    description: str = Field(default="", description="工作流描述")
    version: str = Field(default="1.0.0", description="版本号")
    
    # 图结构
    nodes: List[NodeDefinition] = Field(default_factory=list)
    edges: List[EdgeDefinition] = Field(default_factory=list)
    
    # 配置
    variables: List[WorkflowVariable] = Field(default_factory=list)
    settings: Dict[str, Any] = Field(default_factory=dict)
    
    # 元数据
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    created_by: Optional[str] = None
    is_template: bool = False  # 是否为模板
    is_active: bool = True
    
    # 授权
    license_tier: str = "free"  # free, basic, pro, enterprise
```

---

## 🔧 核心类设计

### WorkflowEngine (工作流引擎)

```python
class WorkflowEngine:
    """工作流引擎 - 核心编排器"""
    
    def __init__(
        self,
        agent_registry: AgentRegistry,
        llm_client: UnifiedLLMClient,
        license_manager: LicenseManager
    ):
        self.agent_registry = agent_registry
        self.llm_client = llm_client
        self.license_manager = license_manager
        self.builder = WorkflowBuilder(agent_registry)
    
    async def execute(
        self,
        workflow_id: str,
        input_data: Dict[str, Any],
        user_id: str,
        callbacks: Optional[WorkflowCallbacks] = None
    ) -> WorkflowResult:
        """执行工作流"""
        # 1. 加载工作流定义
        definition = await self.load_workflow(workflow_id)
        
        # 2. 检查授权
        self.license_manager.check_workflow_access(user_id, definition)
        
        # 3. 构建 LangGraph
        graph = self.builder.build(definition)
        
        # 4. 准备初始状态
        initial_state = self._prepare_state(definition, input_data)
        
        # 5. 执行图
        result = await self._execute_graph(graph, initial_state, callbacks)
        
        return result
```

### WorkflowBuilder (图构建器)

```python
class WorkflowBuilder:
    """从 WorkflowDefinition 构建 LangGraph"""
    
    def __init__(self, agent_registry: AgentRegistry):
        self.agent_registry = agent_registry
    
    def build(self, definition: WorkflowDefinition) -> CompiledGraph:
        """构建可执行的图"""
        from langgraph.graph import StateGraph, END, START
        
        # 创建状态图
        workflow = StateGraph(DynamicAgentState)
        
        # 添加节点
        for node_def in definition.nodes:
            node_func = self._create_node_function(node_def)
            workflow.add_node(node_def.id, node_func)
        
        # 添加边
        for edge in definition.edges:
            if edge.condition:
                # 条件边
                workflow.add_conditional_edges(
                    edge.source,
                    self._create_condition(edge.condition),
                    {edge.target: edge.target}
                )
            else:
                # 普通边
                workflow.add_edge(edge.source, edge.target)
        
        # 设置入口和出口
        self._set_entry_exit(workflow, definition)
        
        return workflow.compile()
```

---

## 📝 预设工作流模板

### default.json (默认分析流程)

```json
{
  "id": "default_analysis",
  "name": "默认分析流程",
  "description": "标准的多智能体股票分析流程",
  "version": "1.0.0",
  "license_tier": "free",
  "nodes": [
    {"id": "market", "type": "analyst", "agent_id": "market_analyst", "name": "市场分析师"},
    {"id": "news", "type": "analyst", "agent_id": "news_analyst", "name": "新闻分析师"},
    {"id": "fundamentals", "type": "analyst", "agent_id": "fundamentals_analyst", "name": "基本面分析师"},
    {"id": "social", "type": "analyst", "agent_id": "social_analyst", "name": "社交媒体分析师"},
    {"id": "bull", "type": "researcher", "agent_id": "bull_researcher", "name": "看涨研究员"},
    {"id": "bear", "type": "researcher", "agent_id": "bear_researcher", "name": "看跌研究员"},
    {"id": "research_mgr", "type": "manager", "agent_id": "research_manager", "name": "研究经理"},
    {"id": "trader", "type": "trader", "agent_id": "trader", "name": "交易员"},
    {"id": "risk_team", "type": "parallel", "agent_id": "risk_parallel", "name": "风险评估团队"},
    {"id": "risk_mgr", "type": "manager", "agent_id": "risk_manager", "name": "风险经理"}
  ],
  "edges": [
    {"id": "e1", "source": "START", "target": "market"},
    {"id": "e2", "source": "market", "target": "news"},
    {"id": "e3", "source": "news", "target": "fundamentals"},
    {"id": "e4", "source": "fundamentals", "target": "social"},
    {"id": "e5", "source": "social", "target": "bull"},
    {"id": "e6", "source": "bull", "target": "bear", "condition": "debate_continue"},
    {"id": "e7", "source": "bear", "target": "bull", "condition": "debate_continue"},
    {"id": "e8", "source": "bull", "target": "research_mgr", "condition": "debate_end"},
    {"id": "e9", "source": "bear", "target": "research_mgr", "condition": "debate_end"},
    {"id": "e10", "source": "research_mgr", "target": "trader"},
    {"id": "e11", "source": "trader", "target": "risk_team"},
    {"id": "e12", "source": "risk_team", "target": "risk_mgr"},
    {"id": "e13", "source": "risk_mgr", "target": "END"}
  ]
}
```

