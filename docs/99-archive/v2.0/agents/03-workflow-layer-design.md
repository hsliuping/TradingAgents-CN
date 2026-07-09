# Workflow 层设计 (Workflow Layer Design)

## 概述

Workflow 层负责管理工作流的定义、Agent 编排和执行。本设计实现 Workflow 与 Agent 的动态组装，支持运行时配置工作流包含哪些 Agent 以及执行顺序。

## 设计目标

1. **动态编排**：Workflow 包含的 Agent 由配置决定
2. **灵活流程**：支持串行、并行、条件分支等执行模式
3. **可视化**：工作流定义可在 Web 界面可视化编辑
4. **版本控制**：支持工作流版本管理

## 目录结构

```
core/workflow/
├── __init__.py
├── registry.py          # Workflow 注册中心
├── builder.py           # Workflow 构建器（增强）
├── engine.py            # Workflow 执行引擎（增强）
├── models.py            # 数据模型
├── validators.py        # 验证器
│
├── templates/           # 预定义工作流模板
│   ├── __init__.py
│   ├── full_analysis.py     # 完整分析工作流
│   ├── position_analysis.py # 持仓分析工作流
│   └── quick_diagnosis.py   # 快速诊断工作流
│
└── nodes/               # 节点类型
    ├── __init__.py
    ├── agent_node.py    # Agent 节点
    ├── tool_node.py     # 工具节点
    ├── router_node.py   # 路由节点
    └── aggregator_node.py # 聚合节点
```

## 核心数据模型

### WorkflowDefinition

```python
# core/workflow/models.py
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from enum import Enum

class NodeType(str, Enum):
    AGENT = "agent"           # Agent 节点
    TOOL = "tool"             # 工具节点
    ROUTER = "router"         # 路由节点
    AGGREGATOR = "aggregator" # 聚合节点
    START = "start"           # 开始节点
    END = "end"               # 结束节点

class ExecutionMode(str, Enum):
    SEQUENTIAL = "sequential"  # 串行
    PARALLEL = "parallel"      # 并行
    CONDITIONAL = "conditional" # 条件

class NodeDefinition(BaseModel):
    """节点定义"""
    id: str                          # 节点ID
    type: NodeType                   # 节点类型
    agent_id: Optional[str] = None   # Agent ID（type=agent时）
    tool_id: Optional[str] = None    # 工具ID（type=tool时）
    config: Dict[str, Any] = {}      # 节点配置
    position: Dict[str, float] = {}  # UI 位置

class EdgeDefinition(BaseModel):
    """边定义"""
    id: str
    source: str                      # 源节点ID
    target: str                      # 目标节点ID
    condition: Optional[str] = None  # 条件表达式

class WorkflowDefinition(BaseModel):
    """工作流定义"""
    id: str                          # 工作流ID
    name: str                        # 名称
    description: str                 # 描述
    version: str = "1.0.0"           # 版本
    category: str = "custom"         # 分类
    
    # 节点和边
    nodes: List[NodeDefinition] = []
    edges: List[EdgeDefinition] = []
    
    # Agent 绑定配置
    agents: List[str] = []           # Agent ID 列表
    agent_tool_overrides: Dict[str, List[str]] = {}  # 工具覆盖配置
    
    # 执行配置
    execution_mode: ExecutionMode = ExecutionMode.SEQUENTIAL
    parallel_groups: List[List[str]] = []  # 并行组
    
    # 状态
    enabled: bool = True
    is_builtin: bool = False
    
    # 元数据
    tags: List[str] = []
    config: Dict[str, Any] = {}
```

### WorkflowMetadata

```python
class WorkflowMetadata(BaseModel):
    """工作流元数据（精简版，用于列表展示）"""
    id: str
    name: str
    description: str
    category: str
    version: str
    agent_count: int
    enabled: bool
    is_builtin: bool
    tags: List[str] = []
```

## 核心接口

### 1. WorkflowRegistry 注册中心

```python
# core/workflow/registry.py
from typing import Dict, List, Optional
from core.workflow.models import WorkflowDefinition, WorkflowMetadata

class WorkflowRegistry:
    """Workflow 注册中心（单例模式）"""
    
    _instance = None
    _workflows: Dict[str, WorkflowDefinition] = {}
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def register(self, workflow: WorkflowDefinition) -> None:
        """注册工作流"""
        self._workflows[workflow.id] = workflow
    
    def get(self, workflow_id: str) -> Optional[WorkflowDefinition]:
        """获取工作流定义"""
        return self._workflows.get(workflow_id)
    
    def list_all(self) -> List[WorkflowMetadata]:
        """列出所有工作流"""
        return [self._to_metadata(w) for w in self._workflows.values()]
    
    def list_by_category(self, category: str) -> List[WorkflowMetadata]:
        """按分类列出"""
        return [
            self._to_metadata(w) 
            for w in self._workflows.values() 
            if w.category == category
        ]
    
    def _to_metadata(self, w: WorkflowDefinition) -> WorkflowMetadata:
        return WorkflowMetadata(
            id=w.id,
            name=w.name,
            description=w.description,
            category=w.category,
            version=w.version,
            agent_count=len(w.agents),
            enabled=w.enabled,
            is_builtin=w.is_builtin,
            tags=w.tags
        )
```

### 2. WorkflowBuilder 构建器

```python
# core/workflow/builder.py
from typing import Dict, Any, List
from langgraph.graph import StateGraph, END
from core.workflow.models import WorkflowDefinition, ExecutionMode
from core.agents.factory import AgentFactory
from core.config.binding_manager import BindingManager

class WorkflowBuilder:
    """工作流构建器 - 将 WorkflowDefinition 转换为 LangGraph"""

    def __init__(self, llm):
        self.llm = llm
        self.agent_factory = AgentFactory(llm)
        self.binding_manager = BindingManager()

    def build(self, workflow: WorkflowDefinition) -> StateGraph:
        """
        构建工作流

        Args:
            workflow: 工作流定义

        Returns:
            LangGraph StateGraph
        """
        # 1. 加载 Agent 配置
        agents = self._load_agents(workflow)

        # 2. 创建状态图
        graph = StateGraph(self._get_state_schema(workflow))

        # 3. 添加节点
        for agent_id, agent in agents.items():
            graph.add_node(agent_id, agent.create_node())

        # 4. 添加边
        self._add_edges(graph, workflow, agents)

        # 5. 设置入口
        graph.set_entry_point(workflow.agents[0])

        return graph.compile()

    def _load_agents(self, workflow: WorkflowDefinition) -> Dict[str, Any]:
        """加载工作流的 Agent"""
        agents = {}

        for agent_id in workflow.agents:
            # 获取工具覆盖配置
            tool_ids = workflow.agent_tool_overrides.get(agent_id)

            # 如果没有覆盖，从数据库加载绑定
            if not tool_ids:
                bindings = self.binding_manager.get_tools_for_workflow_agent(
                    workflow.id, agent_id
                )
                if bindings:
                    tool_ids = [b["tool_id"] for b in bindings]

            # 创建 Agent 实例
            agents[agent_id] = self.agent_factory.create(agent_id, tool_ids)

        return agents

    def _add_edges(self, graph: StateGraph, workflow: WorkflowDefinition, agents: dict):
        """添加边"""
        if workflow.execution_mode == ExecutionMode.SEQUENTIAL:
            # 串行执行
            for i, agent_id in enumerate(workflow.agents[:-1]):
                graph.add_edge(agent_id, workflow.agents[i + 1])
            graph.add_edge(workflow.agents[-1], END)

        elif workflow.execution_mode == ExecutionMode.PARALLEL:
            # 并行执行 - 使用并行组
            for group in workflow.parallel_groups:
                # 添加并行组内的节点
                for agent_id in group:
                    # 并行节点之后的聚合逻辑
                    pass

        # 条件分支通过边定义处理
        for edge in workflow.edges:
            if edge.condition:
                # 条件边
                graph.add_conditional_edges(
                    edge.source,
                    self._create_condition(edge.condition),
                    {True: edge.target, False: END}
                )
            else:
                graph.add_edge(edge.source, edge.target)
```

### 3. WorkflowEngine 执行引擎

```python
# core/workflow/engine.py
from typing import Dict, Any, Optional
from core.workflow.registry import WorkflowRegistry
from core.workflow.builder import WorkflowBuilder
from core.workflow.models import WorkflowDefinition

class WorkflowEngine:
    """工作流执行引擎"""

    def __init__(self, llm):
        self.llm = llm
        self.registry = WorkflowRegistry()
        self.builder = WorkflowBuilder(llm)
        self._compiled_workflows: Dict[str, Any] = {}

    def execute(
        self,
        workflow_id: str,
        input_state: Dict[str, Any],
        config: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        执行工作流

        Args:
            workflow_id: 工作流ID
            input_state: 输入状态
            config: 运行时配置

        Returns:
            执行结果
        """
        # 1. 获取工作流定义
        workflow = self._get_workflow(workflow_id)
        if not workflow:
            raise ValueError(f"未找到工作流: {workflow_id}")

        # 2. 获取或构建编译后的工作流
        compiled = self._get_compiled(workflow)

        # 3. 执行
        result = compiled.invoke(input_state, config)

        return result

    def _get_workflow(self, workflow_id: str) -> Optional[WorkflowDefinition]:
        """获取工作流定义（优先从数据库，其次从 Registry）"""
        # 尝试从数据库加载
        from app.core.database import get_mongo_db
        db = get_mongo_db()
        doc = db.workflow_definitions.find_one({"workflow_id": workflow_id})

        if doc:
            return WorkflowDefinition(**doc)

        # 降级：从 Registry 加载
        return self.registry.get(workflow_id)

    def _get_compiled(self, workflow: WorkflowDefinition):
        """获取编译后的工作流"""
        cache_key = f"{workflow.id}:{workflow.version}"

        if cache_key not in self._compiled_workflows:
            self._compiled_workflows[cache_key] = self.builder.build(workflow)

        return self._compiled_workflows[cache_key]

    def invalidate_cache(self, workflow_id: str = None):
        """清除缓存"""
        if workflow_id:
            keys_to_remove = [k for k in self._compiled_workflows if k.startswith(workflow_id)]
            for k in keys_to_remove:
                del self._compiled_workflows[k]
        else:
            self._compiled_workflows.clear()
```

## Agent-Workflow 绑定

### 数据库配置表

```javascript
// Collection: agent_workflow_bindings
{
    "_id": ObjectId(),
    "workflow_id": "position_analysis",
    "agent_id": "pa_technical_analyst",
    "order": 1,                  // 执行顺序
    "parallel_group": null,      // 并行组（null 表示串行）
    "tool_overrides": [          // 工具覆盖（可选）
        "get_stock_market_data_unified",
        "get_technical_indicators"
    ],
    "config": {},                // 特定配置
    "enabled": true,
    "created_at": ISODate(),
    "updated_at": ISODate()
}
```

### AgentWorkflowBindingManager

```python
# core/config/binding_manager.py (扩展)

class AgentWorkflowBindingManager:
    """Agent-Workflow 绑定管理器"""

    def __init__(self):
        self.db = get_mongo_db()
        self.collection = self.db.agent_workflow_bindings

    def get_agents_for_workflow(self, workflow_id: str) -> List[Dict[str, Any]]:
        """获取工作流的 Agent 列表"""
        bindings = self.collection.find({
            "workflow_id": workflow_id,
            "enabled": True
        }).sort("order", 1)

        return list(bindings)

    def get_tools_for_workflow_agent(
        self,
        workflow_id: str,
        agent_id: str
    ) -> List[str]:
        """获取工作流中某个 Agent 的工具覆盖"""
        binding = self.collection.find_one({
            "workflow_id": workflow_id,
            "agent_id": agent_id,
            "enabled": True
        })

        if binding and binding.get("tool_overrides"):
            return binding["tool_overrides"]
        return []

    def bind_agent(
        self,
        workflow_id: str,
        agent_id: str,
        order: int,
        parallel_group: str = None,
        tool_overrides: List[str] = None
    ) -> None:
        """绑定 Agent 到工作流"""
        self.collection.update_one(
            {"workflow_id": workflow_id, "agent_id": agent_id},
            {"$set": {
                "workflow_id": workflow_id,
                "agent_id": agent_id,
                "order": order,
                "parallel_group": parallel_group,
                "tool_overrides": tool_overrides or [],
                "enabled": True,
                "updated_at": datetime.utcnow()
            }},
            upsert=True
        )
```

## 预定义工作流示例

### 持仓分析工作流

```python
# core/workflow/templates/position_analysis.py
from core.workflow.models import WorkflowDefinition, ExecutionMode

POSITION_ANALYSIS_WORKFLOW = WorkflowDefinition(
    id="position_analysis",
    name="持仓分析工作流",
    description="对持仓股票进行多维度分析",
    version="1.0.0",
    category="position",

    agents=[
        "pa_technical_analyst",
        "pa_fundamental_analyst",
        "pa_risk_assessor",
        "pa_action_advisor"
    ],

    execution_mode=ExecutionMode.PARALLEL,
    parallel_groups=[
        ["pa_technical_analyst", "pa_fundamental_analyst", "pa_risk_assessor"]
    ],
    # pa_action_advisor 在并行组执行完后串行执行

    agent_tool_overrides={
        "pa_technical_analyst": ["get_stock_market_data_unified", "get_technical_indicators"],
        "pa_fundamental_analyst": ["get_financial_data", "get_company_info"],
        "pa_risk_assessor": ["get_stock_market_data_unified", "get_portfolio_risk"],
    },

    is_builtin=True,
    tags=["position", "analysis", "multi-agent"]
)
```

## API 接口

```
# Workflow CRUD
GET    /api/v1/workflows                    # 列出所有工作流
GET    /api/v1/workflows/{id}               # 获取工作流详情
POST   /api/v1/workflows                    # 创建工作流
PUT    /api/v1/workflows/{id}               # 更新工作流
DELETE /api/v1/workflows/{id}               # 删除工作流

# Agent 绑定
GET    /api/v1/workflows/{id}/agents        # 获取工作流的 Agent 列表
POST   /api/v1/workflows/{id}/agents        # 绑定 Agent
DELETE /api/v1/workflows/{id}/agents/{agent_id}  # 解绑 Agent
PUT    /api/v1/workflows/{id}/agents        # 批量更新 Agent 绑定

# 执行
POST   /api/v1/workflows/{id}/execute       # 执行工作流
GET    /api/v1/workflows/{id}/executions    # 获取执行历史
```

## 总结

Workflow 层设计的核心是：

1. **动态编排**：Agent 列表从配置/数据库加载
2. **灵活流程**：支持串行、并行、条件分支
3. **工具覆盖**：可在工作流级别覆盖 Agent 的工具配置
4. **缓存机制**：编译后的工作流缓存复用
5. **版本管理**：支持工作流版本控制

