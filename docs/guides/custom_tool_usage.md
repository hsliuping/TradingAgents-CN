# 自定义工具使用指南

本文档详细说明如何在 TradingAgentsCN 项目中使用自定义工具，包括工具的定义、注册、调用以及返回数据的处理方式。

## 📋 目录

1. [工具的定义和注册](#工具的定义和注册)
2. [工具在提示词中的调用](#工具在提示词中的调用)
3. [工具返回数据的处理](#工具返回数据的处理)
4. [完整示例](#完整示例)

---

## 工具的定义和注册

### 1. 创建自定义工具定义

自定义工具通过 `CustomToolDefinition` 来定义，支持基于 HTTP 的工具实现。

```python
from core.tools.custom_tool import CustomToolDefinition, HttpToolConfig
from core.tools.config import ToolParameter

# 定义工具参数
parameters = [
    ToolParameter(
        name="ticker",
        type="string",
        description="股票代码",
        required=True
    ),
    ToolParameter(
        name="date",
        type="string",
        description="查询日期，格式：YYYY-MM-DD",
        required=False
    )
]

# 定义 HTTP 配置
http_config = HttpToolConfig(
    url="https://api.example.com/stock/{ticker}",
    method="GET",
    headers={
        "Authorization": "Bearer YOUR_API_KEY"
    }
)

# 创建工具定义
tool_definition = CustomToolDefinition(
    id="get_stock_info_custom",
    name="获取股票信息",
    description="通过自定义API获取股票的基本信息",
    category="market",
    parameters=parameters,
    implementation=http_config,
    is_online=True,
    timeout=30
)
```

### 2. 注册自定义工具

#### 方式一：通过 API 注册（推荐）

```python
# 通过 API 端点注册
POST /api/tools/custom
Content-Type: application/json

{
    "id": "get_stock_info_custom",
    "name": "获取股票信息",
    "description": "通过自定义API获取股票的基本信息",
    "category": "market",
    "parameters": [
        {
            "name": "ticker",
            "type": "string",
            "description": "股票代码",
            "required": true
        }
    ],
    "implementation": {
        "url": "https://api.example.com/stock/{ticker}",
        "method": "GET",
        "headers": {
            "Authorization": "Bearer YOUR_API_KEY"
        }
    },
    "is_online": true,
    "timeout": 30
}
```

#### 方式二：通过代码注册

```python
from core.tools.custom_tool import register_custom_tool

# 注册工具
await register_custom_tool(tool_definition)
```

### 3. 绑定工具到 Agent

工具需要绑定到 Agent 才能被使用。绑定方式有两种：

#### 方式一：通过数据库配置（推荐）

在 MongoDB 的 `tool_agent_bindings` 集合中添加绑定关系：

```json
{
    "agent_id": "market_analyst",
    "tool_id": "get_stock_info_custom",
    "enabled": true,
    "priority": 1
}
```

#### 方式二：在创建 Agent 时指定

```python
from core.agents import create_agent

agent = create_agent(
    agent_id="market_analyst",
    llm=llm_instance,
    tool_ids=["get_stock_info_custom", "other_tool_id"]
)
```

---

## 工具在提示词中的调用

### 1. LLM 如何知道可以调用工具？

当 Agent 使用 `invoke_with_tools` 方法时，工具会自动绑定到 LLM：

```python
# 在 BaseAgent.invoke_with_tools() 中
if self._langchain_tools:
    llm_with_tools = self._llm.bind_tools(self._langchain_tools)
    # LLM 现在知道可以调用这些工具
```

**关键点**：
- 工具通过 `bind_tools()` 方法绑定到 LLM
- LLM 会自动识别工具的名称、描述和参数
- **你不需要在提示词中明确告诉 LLM 如何调用工具**
- LLM 会根据工具的描述和当前任务，自主决定是否调用工具

### 2. 提示词中的工具调用

在提示词中，你只需要：

1. **描述任务需求**：告诉 LLM 需要做什么
2. **提及可用数据源**：可以简单提到有哪些数据可用（可选）

**示例提示词**：

```python
system_prompt = """你是一位专业的市场分析师。

你的任务是分析股票的市场表现。

你可以使用以下工具获取数据：
- get_stock_info_custom: 获取股票基本信息
- get_market_data: 获取市场数据

请根据用户的需求，调用合适的工具获取数据，然后进行分析。"""

user_prompt = """请分析股票 000001 在 2025-01-30 的市场表现。"""
```

**重要说明**：
- ✅ **不需要**在提示词中详细说明如何调用工具（LLM 会自动理解）
- ✅ **可以**简单提及有哪些工具可用（帮助 LLM 理解上下文）
- ✅ **应该**明确说明任务目标（让 LLM 知道何时调用工具）

### 3. LLM 的工具调用流程

```
1. LLM 接收提示词
   ↓
2. LLM 分析任务需求
   ↓
3. LLM 决定是否需要调用工具
   ↓
4. 如果需要，LLM 返回 tool_calls：
   {
       "tool_calls": [
           {
               "name": "get_stock_info_custom",
               "args": {"ticker": "000001", "date": "2025-01-30"},
               "id": "call_abc123"
           }
       ]
   }
   ↓
5. Agent 执行工具调用
   ↓
6. 工具返回结果
   ↓
7. 结果被添加到消息历史
   ↓
8. LLM 再次调用，基于工具结果生成报告
```

---

## 工具返回数据的处理

### 1. 工具返回数据的格式

工具可以返回任何可序列化的数据：

```python
# 字符串
return "股票代码: 000001, 价格: 10.50"

# 字典
return {
    "ticker": "000001",
    "price": 10.50,
    "volume": 1000000
}

# 列表
return [
    {"date": "2025-01-30", "price": 10.50},
    {"date": "2025-01-29", "price": 10.30}
]
```

### 2. 工具结果如何传递给后续提示词

工具返回的数据会被自动包装成 `ToolMessage` 并添加到消息历史中：

```python
# 在 BaseAgent._execute_tool_calls() 中
tool_messages.append(ToolMessage(
    content=str(tool_result),  # 工具返回的结果被转换为字符串
    tool_call_id=tool_id        # 关联到对应的工具调用
))

# 消息历史更新
current_messages = current_messages + [response] + tool_messages
```

**消息历史结构**：

```
[
    SystemMessage(content="你是市场分析师..."),
    HumanMessage(content="请分析股票 000001..."),
    AIMessage(
        content="",
        tool_calls=[{
            "name": "get_stock_info_custom",
            "args": {"ticker": "000001"},
            "id": "call_abc123"
        }]
    ),
    ToolMessage(
        content='{"ticker": "000001", "price": 10.50, "volume": 1000000}',
        tool_call_id="call_abc123"
    ),
    HumanMessage(content="工具调用已完成，请生成分析报告...")
]
```

### 3. LLM 如何看到工具返回的数据？

当 LLM 再次被调用时，它会看到完整的消息历史，包括：

1. **之前的对话**（SystemMessage、HumanMessage）
2. **工具调用请求**（AIMessage with tool_calls）
3. **工具执行结果**（ToolMessage）
4. **分析提示词**（HumanMessage）

LLM 会自动理解：
- 哪些工具被调用了
- 工具返回了什么数据
- 如何基于这些数据生成报告

### 4. 在提示词中引用工具数据

**方式一：让 LLM 自动提取（推荐）**

```python
analysis_prompt = """工具调用已完成，所有需要的数据都已获取。

现在请直接撰写详细的中文分析报告，不要再调用任何工具。

报告要求：
1. 基于上述工具返回的真实数据进行分析
2. 结构清晰，逻辑严谨
3. 结论明确，有理有据
4. 使用中文输出
"""
```

LLM 会自动从 ToolMessage 中提取数据并进行分析。

**方式二：在提示词中明确说明数据结构（可选）**

```python
analysis_prompt = """工具调用已完成。

工具返回的数据结构：
- get_stock_info_custom: 返回股票基本信息（ticker, price, volume等）
- get_market_data: 返回市场数据（market_index, trend等）

请基于这些数据生成分析报告。"""
```

---

## 完整示例

### 示例：创建一个股票价格查询工具

#### 1. 定义工具

```python
from core.tools.custom_tool import CustomToolDefinition, HttpToolConfig
from core.tools.config import ToolParameter

# 定义参数
parameters = [
    ToolParameter(
        name="ticker",
        type="string",
        description="股票代码，如 000001",
        required=True
    )
]

# HTTP 配置
http_config = HttpToolConfig(
    url="https://api.example.com/stock/{ticker}/price",
    method="GET",
    headers={
        "X-API-Key": "your_api_key_here"
    }
)

# 创建定义
tool_def = CustomToolDefinition(
    id="get_stock_price_custom",
    name="获取股票价格",
    description="通过自定义API获取股票的当前价格",
    category="market",
    parameters=parameters,
    implementation=http_config,
    is_online=True
)
```

#### 2. 注册工具

```python
from core.tools.custom_tool import register_custom_tool

# 注册
await register_custom_tool(tool_def)
```

#### 3. 绑定到 Agent

在 MongoDB 中添加绑定：

```json
{
    "agent_id": "market_analyst",
    "tool_id": "get_stock_price_custom",
    "enabled": true
}
```

#### 4. 在 Agent 中使用

```python
from core.agents import create_agent
from langchain_openai import ChatOpenAI

# 创建 LLM
llm = ChatOpenAI(model="gpt-4")

# 创建 Agent（工具会自动从数据库加载）
agent = create_agent(
    agent_id="market_analyst",
    llm=llm
)

# 执行分析
state = {
    "ticker": "000001",
    "analysis_date": "2025-01-30"
}

result = agent.execute(state)
# result 包含 market_report，其中包含了基于工具数据的分析报告
```

#### 5. 工具调用流程

```
1. Agent 构建提示词：
   SystemMessage: "你是市场分析师，可以使用 get_stock_price_custom 获取股票价格"
   HumanMessage: "请分析股票 000001 的价格"

2. LLM 决定调用工具：
   AIMessage(tool_calls=[{
       "name": "get_stock_price_custom",
       "args": {"ticker": "000001"},
       "id": "call_123"
   }])

3. Agent 执行工具：
   HTTP GET https://api.example.com/stock/000001/price
   返回: {"ticker": "000001", "price": 10.50, "currency": "CNY"}

4. 工具结果添加到消息历史：
   ToolMessage(
       content='{"ticker": "000001", "price": 10.50, "currency": "CNY"}',
       tool_call_id="call_123"
   )

5. LLM 再次调用（不绑定工具）：
   HumanMessage: "工具调用已完成，请生成分析报告"
   
6. LLM 生成报告：
   "根据工具返回的数据，股票 000001 的当前价格为 10.50 元..."
```

---

## 常见问题

### Q1: 工具返回的数据格式有什么要求？

**A**: 工具可以返回任何可序列化的数据（字符串、字典、列表等）。返回的数据会被自动转换为字符串并包装成 `ToolMessage`。建议返回结构化的 JSON 数据，便于 LLM 理解。

### Q2: 如何在提示词中明确告诉 LLM 使用某个工具？

**A**: 通常不需要。LLM 会根据工具的描述和任务需求自动决定是否调用工具。如果确实需要，可以在提示词中简单提及工具名称和用途。

### Q3: 工具返回的数据如何在后续提示词中使用？

**A**: 工具返回的数据会自动添加到消息历史中（作为 `ToolMessage`）。后续的 LLM 调用会看到这些数据，并自动提取和使用。你只需要在提示词中说明"基于工具返回的数据进行分析"即可。

### Q4: 可以一次调用多个工具吗？

**A**: 可以。LLM 可以在一次响应中返回多个 `tool_calls`，Agent 会并行执行这些工具调用。

### Q5: 工具调用失败怎么办？

**A**: 如果工具执行失败，会返回错误信息作为 `ToolMessage` 的内容。LLM 会看到错误信息，并可以决定是否重试或使用其他方式完成任务。

---

## 相关文档

- [工具系统设计文档](../design/v2.0/agents/01-tool-layer-design.md)
- [Agent 系统设计文档](../design/v2.0/agents/02-agent-layer-design.md)
- [工具配置管理](../technical/tool-config-management.md)
