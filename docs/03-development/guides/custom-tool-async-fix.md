# 自定义工具异步函数修复说明

## 问题描述

当注册自定义工具时，如果工具函数是异步的（`async def`），在 LangChain 工具调用时会返回协程对象而不是实际结果：

```
<coroutine object register_custom_tool.<locals>.wrapper at 0x000001E281ED0900>
```

## 问题原因

1. **自定义工具使用异步 HTTP 请求**：`GenericHttpTool.execute()` 是异步函数
2. **注册时直接使用异步 wrapper**：`async def wrapper(**kwargs)` 
3. **LangChain 工具需要同步函数**：`StructuredTool.from_function()` 期望同步函数
4. **调用时返回协程对象**：因为函数是异步的，调用时返回协程而不是执行结果

## 解决方案

在 `register_custom_tool()` 函数中，创建一个**同步包装函数**，内部处理异步代码的执行：

```python
def sync_wrapper(**kwargs):
    """同步包装函数，用于 LangChain 工具调用"""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # 如果事件循环正在运行，在新线程中运行异步代码
            # ... 使用 threading.Thread ...
        else:
            # 事件循环存在但未运行，直接使用
            return loop.run_until_complete(tool_instance.execute(**kwargs))
    except RuntimeError:
        # 没有事件循环，创建新的（最常见的情况）
        return asyncio.run(tool_instance.execute(**kwargs))
```

## 修复后的行为

1. ✅ **工具注册时**：创建同步包装函数
2. ✅ **LangChain 调用时**：调用同步函数
3. ✅ **内部执行**：同步函数内部运行异步代码
4. ✅ **返回结果**：返回实际的工具执行结果，而不是协程对象

## 使用示例

### 注册自定义工具

```python
from core.tools.custom_tool import CustomToolDefinition, HttpToolConfig, register_custom_tool
from core.tools.config import ToolParameter

# 定义工具
tool_def = CustomToolDefinition(
    id="my_custom_tool",
    name="我的工具",
    description="工具描述",
    category="market",
    parameters=[
        ToolParameter(name="param1", type="string", description="参数1", required=True)
    ],
    implementation=HttpToolConfig(
        url="https://api.example.com/data/{param1}",
        method="GET"
    )
)

# 注册（现在是同步包装函数）
await register_custom_tool(tool_def)
```

### 在 Agent 中使用

```python
from core.agents import create_agent

agent = create_agent(
    agent_id="market_analyst",
    llm=llm_instance,
    tool_ids=["my_custom_tool"]
)

# 执行时，工具会正常返回结果，而不是协程对象
result = agent.execute(state)
```

## 技术细节

### 事件循环处理

修复代码处理了三种情况：

1. **没有事件循环**（最常见）：
   ```python
   return asyncio.run(tool_instance.execute(**kwargs))
   ```

2. **事件循环存在但未运行**：
   ```python
   return loop.run_until_complete(tool_instance.execute(**kwargs))
   ```

3. **事件循环正在运行**（异步上下文中）：
   ```python
   # 在新线程中创建新的事件循环并运行
   thread = threading.Thread(target=run_async, daemon=True)
   thread.start()
   thread.join(timeout=...)
   ```

### 超时保护

为了防止工具执行时间过长，添加了超时保护：

```python
thread.join(timeout=definition.timeout + 10)
if thread.is_alive():
    raise TimeoutError(f"工具执行超时（超过 {definition.timeout + 10} 秒）")
```

## 验证修复

修复后，工具调用应该返回实际结果：

```python
# ✅ 修复后：返回实际结果
result = tool.invoke({"param1": "value"})
print(result)  # {"data": "actual result"}

# ❌ 修复前：返回协程对象
result = tool.invoke({"param1": "value"})
print(result)  # <coroutine object ...>
```

## 相关文件

- `core/tools/custom_tool.py` - 自定义工具实现
- `core/tools/registry.py` - 工具注册表
- `core/agents/base.py` - Agent 基类（工具调用）

## 注意事项

1. **性能影响**：如果事件循环正在运行，会在新线程中运行异步代码，可能有轻微性能开销
2. **超时设置**：确保工具的 `timeout` 设置合理，避免长时间阻塞
3. **错误处理**：工具执行错误会被正确传播，不会丢失异常信息
