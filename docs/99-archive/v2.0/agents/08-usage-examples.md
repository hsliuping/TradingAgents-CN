# 插件化架构使用示例

本文档展示如何使用新的插件化架构组件。

---

## 1. 数据库初始化

首先运行数据库初始化脚本：

```bash
# 激活虚拟环境
.\env\Scripts\activate

# 运行初始化脚本
python scripts/setup/init_plugin_architecture_db.py
```

**输出**:
```
============================================================
🚀 插件化架构数据库初始化
============================================================
📦 连接数据库: tradingagents
✅ 创建集合: tool_configs
✅ 创建集合: agent_configs
✅ 创建集合: workflow_definitions
✅ 创建集合: tool_agent_bindings
✅ 创建集合: agent_workflow_bindings
✅ 创建集合: agent_io_definitions
✅ 插入示例工具配置: get_stock_market_data_unified

============================================================
✅ 初始化完成!
   - 新建集合: 6
   - 已存在: 0
============================================================
```

---

## 2. 使用 BindingManager

### 2.1 工具-Agent 绑定

```python
from core.config import BindingManager

bm = BindingManager()

# 获取 Agent 的工具列表
tools = bm.get_tools_for_agent("market_analyst")
print(f"市场分析师的工具: {tools}")
# 输出: ['get_stock_market_data_unified']

# 绑定新工具到 Agent
success = bm.bind_tool(
    agent_id="market_analyst",
    tool_id="get_yfinance_data",
    priority=1
)
print(f"绑定成功: {success}")

# 再次获取工具列表（包含新绑定的工具）
tools = bm.get_tools_for_agent("market_analyst")
print(f"更新后的工具: {tools}")

# 解绑工具
bm.unbind_tool("market_analyst", "get_yfinance_data")
```

### 2.2 Agent-工作流 绑定

```python
# 获取工作流的 Agent 列表
agents = bm.get_agents_for_workflow("position_analysis")
print(f"持仓分析工作流的 Agent: {agents}")

# 绑定新 Agent 到工作流
bm.bind_agent(
    workflow_id="position_analysis",
    agent_id="pa_technical",
    order=10  # 执行顺序
)

# 工作流级别工具覆盖
tools = bm.get_tools_for_workflow_agent(
    workflow_id="position_analysis",
    agent_id="pa_technical"
)
```

### 2.3 Agent IO 定义

```python
# 获取 Agent 的输入输出定义
io_def = bm.get_agent_io_definition("pa_advisor")
print(f"Agent ID: {io_def['agent_id']}")
print(f"输入: {io_def['inputs']}")
print(f"输出: {io_def['outputs']}")
print(f"读取字段: {io_def['reads_from']}")

# 保存自定义 IO 定义
bm.save_agent_io_definition({
    "agent_id": "custom_agent",
    "inputs": [
        {"name": "ticker", "type": "string", "description": "股票代码", "required": True}
    ],
    "outputs": [
        {"name": "analysis_report", "type": "string", "description": "分析报告"}
    ],
    "reads_from": ["market_data", "news_data"]
})

# 获取所有 Agent 的 IO 定义
all_io_defs = bm.get_all_agent_io_definitions()
print(f"总共 {len(all_io_defs)} 个 Agent 的 IO 定义")
```

---

## 3. 使用 StateSchemaBuilder

### 3.1 构建工作流状态 Schema

```python
from core.state import StateSchemaBuilder, StateFieldDefinition, FieldType

builder = StateSchemaBuilder()

# 根据 Agent 列表构建状态 Schema
schema = builder.build_from_agents(
    workflow_id="position_analysis",
    agent_ids=["pa_technical", "pa_fundamental", "pa_risk", "pa_advisor"]
)

print(f"工作流: {schema.workflow_id}")
print(f"字段数: {len(schema.fields)}")
print(f"输入字段: {schema.input_fields}")
print(f"输出字段: {schema.output_fields}")
print(f"中间字段: {schema.intermediate_fields}")
print(f"依赖关系: {schema.agent_dependencies}")
```

### 3.2 添加自定义输入字段

```python
# 定义额外的输入字段
custom_inputs = [
    StateFieldDefinition(
        name="company_of_interest",
        type=FieldType.STRING,
        description="关注的公司股票代码",
        required=True,
        is_input=True
    ),
    StateFieldDefinition(
        name="risk_tolerance",
        type=FieldType.STRING,
        description="风险偏好",
        required=False,
        default="medium",
        is_input=True
    )
]

# 构建包含自定义输入的 Schema
schema = builder.build_from_agents(
    workflow_id="position_analysis",
    agent_ids=["pa_technical", "pa_fundamental", "pa_risk", "pa_advisor"],
    input_fields=custom_inputs
)
```

### 3.3 生成 TypedDict 类

```python
# 生成 LangGraph 使用的 TypedDict 类
state_class = builder.generate_typed_dict(schema)

print(f"状态类: {state_class}")
print(f"注解: {state_class.__annotations__}")

# 使用状态类创建 StateGraph
from langgraph.graph import StateGraph

graph = StateGraph(state_class)
# ... 添加节点和边
```

---

## 4. 使用 StateRegistry

### 4.1 获取或构建状态 Schema

```python
from core.state import StateRegistry

registry = StateRegistry()

# 获取或构建状态 Schema（自动缓存）
schema = registry.get_or_build(
    workflow_id="position_analysis",
    agent_ids=["pa_technical", "pa_fundamental", "pa_risk", "pa_advisor"]
)

# 再次获取（从缓存）
schema2 = registry.get_or_build(
    workflow_id="position_analysis",
    agent_ids=["pa_technical", "pa_fundamental", "pa_risk", "pa_advisor"]
)

assert schema is schema2  # 同一个对象
```

### 4.2 获取状态类

```python
# 获取 TypedDict 状态类
state_class = registry.get_state_class("position_analysis")

# 使用状态类
from langgraph.graph import StateGraph
graph = StateGraph(state_class)
```

### 4.3 查询字段来源

```python
# 获取字段的来源 Agent
source = registry.get_field_source("position_analysis", "technical_analysis")
print(f"technical_analysis 字段来自: {source}")
# 输出: pa_technical

# 列出所有工作流
workflows = registry.list_workflows()
print(f"已注册的工作流: {workflows}")
```

---

## 5. 使用 ToolRegistry

### 5.1 注册函数作为工具

```python
from core.tools.registry import ToolRegistry
from typing import Annotated

registry = ToolRegistry()

# 定义工具函数
def calculate_rsi(
    prices: Annotated[list, "价格列表"],
    period: Annotated[int, "周期"] = 14
) -> float:
    """计算RSI指标"""
    # 实现...
    return 50.0

# 注册函数
registry.register_function(
    tool_id="calculate_rsi",
    func=calculate_rsi,
    name="RSI计算器",
    category="technical",
    description="计算相对强弱指标",
    is_online=False
)

# 获取函数
func = registry.get_function("calculate_rsi")
result = func([100, 102, 101, 103], period=14)

# 获取 LangChain 工具
tool = registry.get_langchain_tool("calculate_rsi")
```

### 5.2 批量获取工具

```python
# 获取多个工具
tool_ids = ["get_stock_market_data_unified", "get_yfinance_data"]
tools = registry.get_langchain_tools(tool_ids)

# 绑定到 LLM
from langchain_openai import ChatOpenAI
llm = ChatOpenAI()
llm_with_tools = llm.bind_tools(tools)
```

---

## 6. 使用兼容层

### 6.1 注册旧工具

```python
from core.compat import LegacyToolkitAdapter
from core.tools.registry import ToolRegistry

registry = ToolRegistry()

# 自动注册所有旧 Toolkit 中的工具
count = LegacyToolkitAdapter.register_all(registry)
print(f"注册了 {count} 个旧工具")

# 获取工具映射表
mapping = LegacyToolkitAdapter.get_tool_mapping()
for old_name, config in mapping.items():
    print(f"{old_name} -> {config['id']}")
```

---

## 7. 完整示例：创建自定义工作流

```python
from core.state import StateRegistry, StateFieldDefinition, FieldType
from core.config import BindingManager
from langgraph.graph import StateGraph, END

# 1. 定义工作流的 Agent 列表
agent_ids = ["pa_technical", "pa_fundamental", "pa_risk", "pa_advisor"]

# 2. 获取状态 Schema
registry = StateRegistry()
schema = registry.get_or_build(
    workflow_id="my_position_analysis",
    agent_ids=agent_ids
)

# 3. 获取状态类
state_class = registry.get_state_class("my_position_analysis")

# 4. 创建 StateGraph
graph = StateGraph(state_class)

# 5. 添加节点（Agent）
for agent_id in agent_ids:
    # 获取 Agent 的工具
    bm = BindingManager()
    tools = bm.get_tools_for_agent(agent_id)
    
    # 创建 Agent 节点函数
    def agent_node(state):
        # Agent 逻辑...
        return state
    
    graph.add_node(agent_id, agent_node)

# 6. 添加边（执行顺序）
graph.set_entry_point("pa_technical")
graph.add_edge("pa_technical", "pa_fundamental")
graph.add_edge("pa_fundamental", "pa_risk")
graph.add_edge("pa_risk", "pa_advisor")
graph.add_edge("pa_advisor", END)

# 7. 编译并运行
app = graph.compile()
result = app.invoke({
    "messages": [],
    "company_of_interest": "AAPL"
})
```

---

## 8. 数据库配置示例

### 8.1 通过 MongoDB 配置工具绑定

```javascript
// 在 MongoDB 中插入工具-Agent 绑定
db.tool_agent_bindings.insertOne({
    "agent_id": "market_analyst",
    "tool_id": "get_yfinance_data",
    "priority": 1,
    "is_active": true,
    "created_at": new Date().toISOString(),
    "updated_at": new Date().toISOString()
})
```

### 8.2 通过 MongoDB 配置 Agent IO

```javascript
// 在 MongoDB 中插入 Agent IO 定义
db.agent_io_definitions.insertOne({
    "agent_id": "custom_analyst",
    "inputs": [
        {"name": "ticker", "type": "string", "description": "股票代码", "required": true}
    ],
    "outputs": [
        {"name": "custom_report", "type": "string", "description": "自定义报告"}
    ],
    "reads_from": ["market_data"],
    "created_at": new Date().toISOString(),
    "updated_at": new Date().toISOString()
})
```

---

## 总结

新的插件化架构提供了：

1. **灵活的绑定管理** - 工具、Agent、工作流可独立配置
2. **动态状态生成** - 根据 Agent 自动生成工作流状态
3. **向后兼容** - 兼容旧 Toolkit 和 AgentState
4. **数据库驱动** - 配置存储在 MongoDB，支持动态更新
5. **缓存优化** - 5分钟 TTL，提高性能

下一步可以开始**阶段2：工具层迁移**，将现有工具迁移到新架构。

