# 自定义工具快速参考

## 🎯 核心问题解答

### Q1: 工具在提示词中怎么调用？

**答案：你不需要在提示词中明确调用工具！**

工具通过 `llm.bind_tools(tools)` 自动绑定到 LLM，LLM 会根据任务需求**自主决定**是否调用工具。

**提示词写法**：

```python
# ✅ 好的写法：简洁明了
system_prompt = """你是市场分析师。
你可以使用 get_stock_info_custom 工具获取股票数据。
请根据用户需求，调用合适的工具获取数据后进行分析。"""

user_prompt = """请分析股票 000001 的市场表现。"""
```

```python
# ❌ 不好的写法：过于详细
system_prompt = """你必须调用 get_stock_info_custom(ticker="000001")...
工具返回格式是 JSON，包含 price、volume 字段..."""
```

### Q2: 工具返回的数据如何体现在后续提示词中？

**答案：自动传递，无需手动处理！**

1. **工具执行后**，返回结果自动包装成 `ToolMessage`
2. **添加到消息历史**：`messages = messages + [AIMessage] + [ToolMessage]`
3. **LLM 再次调用时**，会看到完整的消息历史，包括工具返回的数据
4. **LLM 自动提取**工具数据并生成报告

**流程示意**：

```
用户请求
  ↓
LLM 决定调用工具 → AIMessage(tool_calls=[...])
  ↓
执行工具 → ToolMessage(content="工具返回的数据")
  ↓
添加到消息历史
  ↓
LLM 再次调用（看到工具数据）
  ↓
生成分析报告
```

**在提示词中引用工具数据**：

```python
# ✅ 推荐：让 LLM 自动提取
analysis_prompt = """工具调用已完成，所有数据都已获取。
请基于上述工具返回的真实数据，直接撰写详细的分析报告。"""

# ✅ 可选：简单说明数据结构
analysis_prompt = """工具返回的数据包含：
- get_stock_info_custom: 股票基本信息（价格、成交量等）
请基于这些数据生成报告。"""
```

---

## 📝 完整示例

### 1. 创建自定义工具

```python
from core.tools.custom_tool import CustomToolDefinition, HttpToolConfig
from core.tools.config import ToolParameter

tool_def = CustomToolDefinition(
    id="my_custom_tool",
    name="我的自定义工具",
    description="工具的功能描述",
    category="market",
    parameters=[
        ToolParameter(name="param1", type="string", description="参数1", required=True)
    ],
    implementation=HttpToolConfig(
        url="https://api.example.com/data/{param1}",
        method="GET"
    )
)

await register_custom_tool(tool_def)
```

### 2. 绑定到 Agent

在 MongoDB `tool_agent_bindings` 集合中添加：

```json
{
    "agent_id": "market_analyst",
    "tool_id": "my_custom_tool",
    "enabled": true
}
```

### 3. 在 Agent 中使用

```python
from core.agents import create_agent

agent = create_agent(
    agent_id="market_analyst",
    llm=llm_instance,
    tool_ids=["my_custom_tool"]  # 工具会自动加载
)

# Agent 执行时：
# 1. LLM 看到提示词和可用工具
# 2. LLM 决定调用 my_custom_tool(param1="value")
# 3. 工具执行，返回数据
# 4. 数据自动添加到消息历史
# 5. LLM 看到工具数据，生成报告
result = agent.execute(state)
```

---

## 🔑 关键要点

1. **工具调用是自动的**：通过 `bind_tools()` 绑定，LLM 自主决定
2. **数据传递是自动的**：工具结果自动添加到消息历史
3. **提示词要简洁**：只需说明任务和目标，不需要详细说明如何调用工具
4. **返回数据要清晰**：建议返回结构化的 JSON，便于 LLM 理解

---

## 📚 更多信息

- 详细文档：[custom_tool_usage.md](./custom_tool_usage.md)
- 代码示例：[examples/custom_tool_example.py](../../examples/custom_tool_example.py)
