# 迁移方案 (Migration Plan)

## 概述

本文档描述从当前架构迁移到插件化智能体架构的详细计划。采用渐进式迁移策略，确保系统稳定性和向后兼容。

## 当前架构问题

### 紧耦合点分析

| 位置 | 问题 | 影响 |
|------|------|------|
| `tradingagents/agents/utils/agent_utils.py` | Toolkit 类包含所有工具 | 工具无法独立管理 |
| `tradingagents/agents/analysts/*.py` | 工具列表硬编码 | Agent 无法动态配置工具 |
| `core/workflow/builder.py` | ANALYST_TOOL_MAPPING 硬编码 | 工作流无法动态配置 |
| `core/agents/config.py` | BUILTIN_AGENTS 静态定义 | Agent 配置无法动态修改 |
| `tradingagents/agents/utils/agent_states.py` | AgentState 字段硬编码 | 新增 Agent 需修改状态类 |
| `core/workflow/builder.py` | WorkflowState 字段硬编码 | 不同工作流无法有不同状态 |
| Agent 实现 | 输入输出字段隐式约定 | 无法验证数据依赖关系 |

## 迁移策略

采用**渐进式迁移**，分6个阶段执行：

```
阶段1: 基础设施 → 阶段2: 工具层 → 阶段3: Agent层 → 阶段4: 状态层 → 阶段5: Workflow层 → 阶段6: 清理
     (2天)           (3天)          (3天)          (2天)           (2天)            (2天)
```

### 新增：状态层改造

状态层改造解决 Agent 之间数据传递的问题：

1. **Agent IO 声明**：每个 Agent 声明输入/输出字段
2. **动态状态生成**：Workflow 根据 Agent 列表自动生成状态 Schema
3. **依赖验证**：自动检查 Agent 之间的数据依赖关系

## 阶段1: 基础设施准备（2天）

### 1.1 数据库集合创建

```bash
# 执行初始化脚本
python scripts/init_plugin_architecture_db.py
```

**创建集合：**
- `tool_configs`
- `agent_configs`
- `workflow_definitions`
- `tool_agent_bindings`
- `agent_workflow_bindings`

### 1.2 配置管理器

创建 `core/config/binding_manager.py`：

```python
class BindingManager:
    """统一绑定管理器"""
    
    def get_tools_for_agent(self, agent_id: str) -> List[str]
    def get_agents_for_workflow(self, workflow_id: str) -> List[str]
    def bind_tool(self, agent_id: str, tool_id: str, priority: int)
    def bind_agent(self, workflow_id: str, agent_id: str, order: int)
```

### 1.3 兼容层

创建兼容层，允许新旧代码共存：

```python
# core/compat/legacy_adapter.py
class LegacyToolkitAdapter:
    """将旧 Toolkit 适配到新 ToolRegistry"""
    
    @classmethod
    def register_all(cls):
        """将 Toolkit 中的工具注册到新 Registry"""
        pass
```

**交付物：**
- [ ] 数据库集合和索引
- [ ] `core/config/binding_manager.py`
- [ ] `core/compat/legacy_adapter.py`
- [ ] 初始化脚本

## 阶段2: 工具层迁移（3天）

### 2.1 创建工具目录结构

```
core/tools/
├── market/
│   └── stock_data.py
├── news/
│   └── finnhub.py
├── fundamentals/
│   └── financial.py
└── social/
    └── sentiment.py
```

### 2.2 迁移工具实现

从 `Toolkit` 类迁移工具到独立文件：

**迁移前（旧）：**
```python
# tradingagents/agents/utils/agent_utils.py
class Toolkit:
    @staticmethod
    @tool
    def get_stock_market_data_unified(...):
        return interface.get_stock_data_unified(...)
```

**迁移后（新）：**
```python
# core/tools/market/stock_data.py
from core.tools.decorators import register_tool
from tradingagents.dataflows.interface import get_stock_data_unified

@register_tool(
    id="get_stock_market_data_unified",
    name="统一股票市场数据",
    category="market"
)
def get_stock_market_data_unified(ticker: str, start_date: str, end_date: str):
    return get_stock_data_unified(ticker, start_date, end_date)
```

### 2.3 工具映射表

| 旧工具方法 | 新工具ID | 分类 |
|-----------|---------|------|
| `Toolkit.get_stock_market_data_unified` | `get_stock_market_data_unified` | market |
| `Toolkit.get_YFin_data_online` | `get_yfinance_data` | market |
| `Toolkit.get_finnhub_news` | `get_finnhub_news` | news |
| `Toolkit.get_reddit_news` | `get_reddit_news` | news |
| `Toolkit.get_reddit_stock_info` | `get_reddit_stock_sentiment` | social |
| `Toolkit.get_SEC_filings_analysis` | `get_sec_filings` | fundamentals |
| `Toolkit.get_simfin_balance_sheet` | `get_balance_sheet` | fundamentals |
| `Toolkit.get_simfin_cashflow` | `get_cashflow` | fundamentals |
| `Toolkit.get_simfin_income_stmt` | `get_income_statement` | fundamentals |

### 2.4 增强 ToolRegistry

更新 `core/tools/registry.py` 支持：
- 函数注册（`register_function`）
- LangChain 工具转换（`get_langchain_tool`）
- 批量获取（`get_by_ids`）

**交付物：**
- [ ] 工具目录结构
- [ ] 15+ 个独立工具文件
- [ ] 增强的 ToolRegistry
- [ ] 工具加载器 ToolLoader
- [ ] 工具配置导入数据库

## 阶段3: Agent层迁移（3天）

### 3.1 增强 BaseAgent

更新 `core/agents/base.py`：

```python
class BaseAgent(ABC):
    def __init__(self, agent_id: str, llm, tool_ids: List[str] = None):
        self._tool_ids = tool_ids or self._load_tools_from_config()
        self._tools = self._create_tools()
    
    def _load_tools_from_config(self) -> List[str]:
        """从配置/数据库动态加载工具"""
        pass
```

### 3.2 迁移现有 Agent

**迁移顺序（按复杂度）：**

1. **持仓分析 Agent**（新创建，直接用新架构）
   - `pa_technical_analyst`
   - `pa_fundamental_analyst`
   - `pa_risk_assessor`
   - `pa_action_advisor`

2. **分析师 Agent**
   - `market_analyst`
   - `news_analyst`
   - `fundamentals_analyst`
   - `social_analyst`

3. **研究员/交易员 Agent**
   - `bull_researcher`
   - `bear_researcher`
   - `risky_trader`
   - `risk_manager`

### 3.3 Agent 迁移示例

**迁移前（旧）：**
```python
# tradingagents/agents/analysts/market_analyst.py
def create_market_analyst(llm, toolkit):
    def market_analyst_node(state):
        # 工具硬编码
        tools = [toolkit.get_stock_market_data_unified]
        chain = prompt | llm.bind_tools(tools)
        # ...
    return market_analyst_node
```

**迁移后（新）：**
```python
# core/agents/analysts/market_analyst.py
from core.agents.base import BaseAgent
from core.agents.decorators import register_agent

@register_agent(
    id="market_analyst",
    name="市场分析师",
    category="analysts",
    tools=["get_stock_market_data_unified"],  # 可被配置覆盖
)
class MarketAnalyst(BaseAgent):
    def execute(self, state: dict) -> dict:
        # 工具从配置动态加载
        chain = prompt | self.llm.bind_tools(self.tools)
        # ...
```

**交付物：**
- [ ] 增强的 BaseAgent（支持 IO 声明）
- [ ] AgentFactory
- [ ] 12+ 个迁移后的 Agent
- [ ] Agent 配置导入数据库
- [ ] 工具绑定配置
- [ ] Agent IO 定义（inputs/outputs/reads_from）

## 阶段4: 状态层迁移（2天）

### 4.1 创建状态层组件

创建 `core/state/` 目录结构：

```
core/state/
├── __init__.py
├── models.py          # StateFieldDefinition, AgentIODefinition
├── builder.py         # StateSchemaBuilder
├── registry.py        # StateFieldRegistry
└── validators.py      # 状态验证器
```

### 4.2 实现状态模型

创建 `core/state/models.py`：

```python
from pydantic import BaseModel
from typing import List, Optional, Any
from enum import Enum

class FieldType(str, Enum):
    STRING = "string"
    INT = "int"
    FLOAT = "float"
    BOOL = "bool"
    LIST = "list"
    DICT = "dict"
    MESSAGES = "messages"

class StateFieldDefinition(BaseModel):
    """状态字段定义"""
    name: str
    type: FieldType
    description: str = ""
    default: Optional[Any] = None
    required: bool = False
    reducer: Optional[str] = None  # "add", "merge", None

class AgentIODefinition(BaseModel):
    """Agent 输入输出定义"""
    agent_id: str
    inputs: List[StateFieldDefinition] = []
    outputs: List[StateFieldDefinition] = []
    reads_from: List[str] = []  # 依赖其他 Agent 的输出字段
```

### 4.3 实现 StateSchemaBuilder

创建 `core/state/builder.py`：

```python
from typing import Type, Dict, List
from langgraph.graph import MessagesState
from core.state.models import StateFieldDefinition, FieldType

class StateSchemaBuilder:
    """动态构建状态 Schema"""

    TYPE_MAPPING = {
        FieldType.STRING: str,
        FieldType.INT: int,
        FieldType.FLOAT: float,
        FieldType.BOOL: bool,
        FieldType.LIST: list,
        FieldType.DICT: dict,
    }

    def build_for_workflow(self, agent_ids: List[str]) -> Type:
        """根据工作流的 Agent 列表构建状态 Schema"""
        all_fields = self._collect_fields(agent_ids)
        return self._create_state_class(all_fields)

    def _collect_fields(self, agent_ids: List[str]) -> Dict[str, StateFieldDefinition]:
        """收集所有 Agent 的输入输出字段"""
        fields = self._get_base_fields()

        for agent_id in agent_ids:
            io_def = AgentRegistry().get_io_definition(agent_id)
            if io_def:
                for field in io_def.inputs + io_def.outputs:
                    if field.name not in fields:
                        fields[field.name] = field

        return fields

    def _create_state_class(self, fields: Dict[str, StateFieldDefinition]) -> Type:
        """动态创建状态类"""
        # 使用 type() 动态创建类，包含 __annotations__
        pass
```

### 4.4 数据库集合

创建 `agent_io_definitions` 集合：

```javascript
// Collection: agent_io_definitions
{
    "agent_id": "market_analyst",
    "inputs": [
        {"name": "company_of_interest", "type": "string", "required": true},
        {"name": "trade_date", "type": "string"}
    ],
    "outputs": [
        {"name": "market_report", "type": "string", "description": "市场分析报告"}
    ],
    "reads_from": []
}

// 索引
db.agent_io_definitions.createIndex({ "agent_id": 1 }, { unique: true })
```

### 4.5 迁移现有 Agent IO 定义

内置 Agent 的 IO 定义映射表：

| Agent ID | 输入 | 输出 | 依赖 |
|----------|------|------|------|
| market_analyst | company_of_interest, trade_date | market_report | - |
| news_analyst | company_of_interest, trade_date | news_report | - |
| fundamentals_analyst | company_of_interest | fundamentals_report | - |
| social_analyst | company_of_interest | sentiment_report | - |
| bull_researcher | - | bull_report | market_report, news_report, fundamentals_report |
| bear_researcher | - | bear_report | market_report, news_report, fundamentals_report |
| trader | - | investment_plan | bull_report, bear_report |
| pa_technical | company_of_interest, trade_date | technical_analysis | - |
| pa_fundamental | company_of_interest | fundamental_analysis | - |
| pa_risk | company_of_interest | risk_analysis | - |
| pa_advisor | company_of_interest | action_advice | technical_analysis, fundamental_analysis, risk_analysis |

### 4.6 兼容模式

更新 `WorkflowBuilder` 支持兼容模式：

```python
# core/workflow/builder.py
def _get_state_schema(self, workflow):
    if workflow.config.get("use_dynamic_state", False):
        # 新模式：动态生成
        return self.state_builder.build_for_workflow(workflow.agent_ids)
    else:
        # 兼容模式：使用旧的 AgentState
        return self._get_default_state_schema()
```

**交付物：**
- [ ] `core/state/models.py` - 状态模型定义
- [ ] `core/state/builder.py` - 动态状态 Schema 构建器
- [ ] `core/state/registry.py` - 状态字段注册中心
- [ ] `core/state/validators.py` - 依赖关系验证器
- [ ] `agent_io_definitions` 数据库集合
- [ ] 11+ 个 Agent 的 IO 定义导入脚本
- [ ] WorkflowBuilder 兼容模式支持

## 阶段5: Workflow层迁移（2天）

### 5.1 更新 WorkflowBuilder

移除硬编码映射，改为从配置加载：

**迁移前：**
```python
# core/workflow/builder.py
ANALYST_TOOL_MAPPING = {
    "market_analyst": "market",  # 硬编码
}

def get_tool_nodes(self):
    toolkit = self.get_toolkit()
    return {
        "market": ToolNode([toolkit.get_stock_market_data_unified]),  # 硬编码
    }
```

**迁移后：**
```python
# core/workflow/builder.py
def _load_agents(self, workflow: WorkflowDefinition):
    """从配置动态加载 Agent"""
    for agent_id in workflow.agents:
        # 从数据库获取工具覆盖
        tool_ids = self.binding_manager.get_tools_for_workflow_agent(
            workflow.id, agent_id
        )
        agents[agent_id] = self.agent_factory.create(agent_id, tool_ids)
```

### 5.2 工作流配置迁移

将现有工作流定义导入数据库：

| 工作流 | ID | Agent 数量 |
|--------|-----|-----------|
| TradingAgents完整分析 | `full_stock_analysis` | 8 |
| 持仓分析工作流 | `position_analysis` | 4 |
| 快速诊断工作流 | `quick_diagnosis` | 2 |

**交付物：**
- [ ] 更新的 WorkflowBuilder
- [ ] 更新的 WorkflowEngine
- [ ] 工作流配置导入数据库
- [ ] Agent-Workflow 绑定配置
- [ ] 状态 Schema 动态生成集成

### 5.3 更新 WorkflowEngine

更新 `core/workflow/engine.py` 使用动态状态：

```python
# core/workflow/engine.py
class WorkflowEngine:
    def __init__(self, state_builder: StateSchemaBuilder = None):
        self.state_builder = state_builder or StateSchemaBuilder()

    def execute(self, workflow_id: str, inputs: dict):
        workflow = self._load_workflow(workflow_id)

        # 动态生成状态 Schema
        state_schema = self.state_builder.build_for_workflow(
            [node.agent_id for node in workflow.nodes if node.agent_id]
        )

        # 验证输入字段
        self._validate_inputs(inputs, state_schema)

        # 构建并执行 LangGraph
        graph = self._build_graph(workflow, state_schema)
        return graph.invoke(inputs)
```

**交付物：**
- [ ] 更新的 WorkflowBuilder
- [ ] 更新的 WorkflowEngine（支持动态状态）
- [ ] 工作流配置导入数据库
- [ ] Agent-Workflow 绑定配置
- [ ] 状态 Schema 动态生成集成

## 阶段6: 清理和优化（2天）

### 6.1 废弃代码标记

```python
# tradingagents/agents/utils/agent_utils.py
import warnings

class Toolkit:
    """
    @deprecated: 请使用 core.tools 模块的独立工具
    """
    def __init__(self):
        warnings.warn(
            "Toolkit 类已废弃，请使用 core.tools 模块",
            DeprecationWarning
        )
```

```python
# tradingagents/agents/utils/agent_states.py
import warnings

class AgentState:
    """
    @deprecated: 请使用 core.state 模块的动态状态生成
    """
    def __init__(self):
        warnings.warn(
            "AgentState 类已废弃，请使用 StateSchemaBuilder 动态生成",
            DeprecationWarning
        )
```

### 6.2 文档更新

- 更新 API 文档
- 更新开发者指南
- 添加迁移说明
- 添加状态层使用指南

### 6.3 性能优化

- 工具/Agent 缓存
- 数据库查询优化
- 编译后工作流缓存
- **状态 Schema 缓存**

**交付物：**
- [ ] 废弃代码标记（Toolkit、AgentState）
- [ ] 更新的文档
- [ ] 性能优化
- [ ] 测试用例

## 迁移时间表

```
Week 1
├── Day 1-2: 阶段1 - 基础设施准备
│   ├── 创建数据库集合（含 agent_io_definitions）
│   ├── 实现 BindingManager
│   └── 创建兼容层
│
├── Day 3-5: 阶段2 - 工具层迁移
│   ├── 创建工具目录结构
│   ├── 迁移工具实现
│   └── 增强 ToolRegistry

Week 2
├── Day 1-3: 阶段3 - Agent层迁移
│   ├── 增强 BaseAgent（支持 IO 声明）
│   ├── 迁移现有 Agent
│   └── 配置工具绑定和 IO 定义
│
├── Day 4-5: 阶段4 - 状态层迁移
│   ├── 实现 StateSchemaBuilder
│   ├── 创建状态字段注册中心
│   └── 导入 Agent IO 定义

Week 3
├── Day 1-2: 阶段5 - Workflow层迁移
│   ├── 更新 WorkflowBuilder（动态状态）
│   ├── 更新 WorkflowEngine
│   └── 迁移工作流配置
│
├── Day 3-4: 阶段6 - 清理和优化
│   ├── 废弃代码标记
│   ├── 文档更新
│   └── 性能优化
│
├── Day 5: 测试和修复
│   ├── 集成测试
│   ├── 性能测试
│   └── Bug 修复
```

## 风险和缓解

| 风险 | 影响 | 缓解措施 |
|------|------|---------|
| 工具行为差异 | 分析结果不一致 | 对比测试，保持实现一致 |
| 配置加载性能 | 响应延迟 | 缓存机制，批量加载 |
| 数据库连接失败 | 系统不可用 | 降级到代码配置 |
| Agent 执行异常 | 工作流中断 | 错误处理，重试机制 |
| **状态字段缺失** | Agent 执行失败 | IO 定义验证，依赖检查 |
| **状态类型不匹配** | 数据传递错误 | 类型验证，运行时检查 |

## 回滚方案

每个阶段完成后创建标签：

```bash
git tag v2.0-phase1-complete
git tag v2.0-phase2-complete
git tag v2.0-phase3-complete
git tag v2.0-phase4-complete  # 状态层
git tag v2.0-phase5-complete
git tag v2.0-phase6-complete
```

如需回滚：
```bash
git checkout v2.0-phase4-complete
# 恢复数据库配置
python scripts/rollback_plugin_architecture.py --phase 4
```

## 验收标准

### 功能验收

- [ ] 工具可通过 API 动态配置
- [ ] Agent 可通过 API 动态绑定工具
- [ ] Workflow 可通过 API 动态编排 Agent
- [ ] **Agent IO 定义可通过 API 配置**
- [ ] **状态 Schema 根据 Agent 列表动态生成**
- [ ] **Agent 依赖关系可自动验证**
- [ ] 现有功能正常工作（向后兼容）

### 性能验收

- [ ] 工作流执行时间 < 原有时间 * 1.1
- [ ] 配置加载时间 < 100ms
- [ ] **状态 Schema 生成时间 < 50ms**
- [ ] 内存使用增加 < 10%

### 代码质量

- [ ] 单元测试覆盖率 > 80%
- [ ] 无 P0/P1 Bug
- [ ] 代码审查通过

### 状态层验收

- [ ] 所有内置 Agent 有 IO 定义
- [ ] 动态状态 Schema 可正确生成
- [ ] 状态字段类型验证通过
- [ ] 依赖缺失时有明确错误提示
- [ ] 兼容模式可正常回退到旧 AgentState

## 总结

迁移方案的核心是：

1. **渐进式迁移**：6个阶段，每阶段独立可验证
2. **向后兼容**：通过兼容层支持新旧代码共存
3. **风险可控**：每阶段有回滚方案
4. **测试保障**：充分的测试覆盖
5. **状态解耦**：Agent 声明 IO，Workflow 动态生成状态

