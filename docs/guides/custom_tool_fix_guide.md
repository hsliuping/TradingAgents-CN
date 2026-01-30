# 自定义工具协程对象问题修复指南

## 问题现象

工具调用时返回协程对象而不是实际结果：
```
<coroutine object register_custom_tool.<locals>.wrapper at 0x000001B88A23EFF0>
```

应该返回：
```json
{"ok":true,"time":"2026-01-30T14:56:23.227916"}
```

## 修复方案

### 1. 代码修复（已完成）

#### 1.1 同步包装函数 (`core/tools/custom_tool.py`)
- ✅ 创建了 `sync_wrapper` 同步包装函数
- ✅ 内部处理异步代码的执行（支持多种事件循环场景）
- ✅ 添加了验证，确保注册的是同步函数

#### 1.2 协程检测和处理 (`core/agents/base.py`)
- ✅ 在 `_execute_tool_calls` 中添加了协程对象检测
- ✅ 如果工具返回协程对象，自动等待完成
- ✅ 支持在事件循环运行时的处理

#### 1.3 工具注册验证 (`core/tools/registry.py`)
- ✅ 添加了异步函数检测和警告
- ✅ 帮助发现注册问题

### 2. 重新注册工具（需要执行）

**重要**：如果工具在修复之前就已经注册，需要重新注册才能使用新的同步包装函数。

#### 方式一：使用重新加载脚本（推荐）

```bash
python scripts/reload_custom_tools.py
```

这个脚本会：
1. 从数据库读取所有自定义工具
2. 使用新的同步包装函数重新注册
3. 验证注册结果

#### 方式二：通过 API 重新注册

```bash
# 删除旧工具（如果需要）
DELETE /api/tools/custom/{tool_id}

# 重新创建工具
POST /api/tools/custom
Content-Type: application/json

{
    "id": "test_heartbeat",
    "name": "服务器心跳",
    "description": "测试服务器心跳",
    "category": "test",
    "parameters": [...],
    "implementation": {...}
}
```

#### 方式三：在代码中重新注册

```python
from core.tools.custom_tool import CustomToolDefinition, register_custom_tool

# 重新注册工具
await register_custom_tool(tool_definition)
```

### 3. 验证修复

#### 3.1 检查工具函数类型

```python
from core.tools.registry import get_tool_registry
import inspect

registry = get_tool_registry()
func = registry.get_function("test_heartbeat")

if inspect.iscoroutinefunction(func):
    print("❌ 工具仍然是异步函数")
else:
    print("✅ 工具是同步函数")
```

#### 3.2 测试工具调用

```python
from core.tools.registry import get_tool_registry
import asyncio

registry = get_tool_registry()
tool = registry.get_langchain_tool("test_heartbeat")

# 测试调用
result = tool.invoke({})

# 检查结果
if asyncio.iscoroutine(result):
    print("❌ 返回的是协程对象")
else:
    print(f"✅ 返回实际结果: {result}")
```

## 修复后的行为

### 修复前
```
工具调用 → 返回协程对象 → 错误
```

### 修复后
```
工具调用 → 同步包装函数 → 执行异步代码 → 返回实际结果 ✅
```

或者（如果工具未重新注册）：
```
工具调用 → 返回协程对象 → 自动检测 → 等待完成 → 返回实际结果 ✅
```

## 注意事项

1. **重新注册工具**：修复前注册的工具需要重新注册
2. **Agent 重启**：如果 Agent 已经加载了工具，可能需要重启才能使用新注册的工具
3. **性能影响**：同步包装函数会在内部运行异步代码，可能有轻微性能开销
4. **超时设置**：确保工具的 `timeout` 设置合理

## 相关文件

- `core/tools/custom_tool.py` - 自定义工具实现（已修复）
- `core/agents/base.py` - Agent 基类（已添加协程检测）
- `core/tools/registry.py` - 工具注册表（已添加验证）
- `scripts/reload_custom_tools.py` - 重新加载脚本

## 故障排查

### 问题：重新注册后仍然返回协程对象

**可能原因**：
1. Agent 已经加载了旧工具，需要重启
2. 工具注册时出错，检查日志

**解决方法**：
1. 重启应用或重新创建 Agent
2. 检查工具注册日志
3. 运行验证脚本

### 问题：工具执行超时

**可能原因**：
1. HTTP 请求超时
2. 事件循环处理时间过长

**解决方法**：
1. 增加工具的 `timeout` 设置
2. 检查网络连接
3. 检查 API 响应时间
