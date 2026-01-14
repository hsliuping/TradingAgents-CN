# BUILTIN_TOOLS vs @register_tool 的区别和关系

## 📋 概述

项目中存在两种工具注册方式，它们有不同的职责和使用场景。

## 🔧 两种注册方式

### 1. `BUILTIN_TOOLS` (core/tools/config.py)

**性质**: 静态元数据配置

**位置**: `core/tools/config.py`

**作用**:
- 定义工具的**完整元数据**，包括：
  - 工具ID、名称、描述
  - **参数列表**（`parameters`）- 这是关键！
  - 类别、数据源、图标、颜色等
- 用于前端展示、API查询、工具发现
- 提供工具参数的完整定义

**示例**:
```python
"get_north_flow": ToolMetadata(
    id="get_north_flow",
    name="北向资金流向",
    description="获取沪深港通北向资金流向数据，分析外资动向",
    category=ToolCategory.MARKET,
    parameters=[
        ToolParameter(name="trade_date", type="string", description="交易日期，格式：YYYY-MM-DD", required=True),
        ToolParameter(name="lookback_days", type="integer", description="回看天数，默认10天", required=False, default=10),
    ],
)
```

### 2. `@register_tool` 装饰器 (工具实现文件)

**性质**: 运行时函数注册

**位置**: `core/tools/implementations/**/*.py`

**作用**:
- 注册**实际的函数实现**
- 将函数绑定到工具ID
- 让工具可以被调用执行

**示例（旧方式，不推荐）**:
```python
@tool
@register_tool(
    tool_id="get_north_flow",
    name="北向资金流向",
    description="获取沪深港通北向资金流向数据，分析外资动向",
    category="market",
    is_online=True,
    auto_register=True
)
def get_north_flow(
    trade_date: Annotated[str, "交易日期，格式：YYYY-MM-DD"],
    lookback_days: Annotated[int, "回看天数，默认10天"] = 10
) -> str:
    # 实际实现...
```

**示例（新方式，支持 parameters）**:
```python
from core.tools.config import ToolParameter

@tool
@register_tool(
    tool_id="get_north_flow",
    name="北向资金流向",
    description="获取沪深港通北向资金流向数据，分析外资动向",
    category="market",
    is_online=True,
    auto_register=True,
    parameters=[  # 🔑 新增：可以直接传递参数定义
        ToolParameter(name="trade_date", type="string", description="交易日期，格式：YYYY-MM-DD", required=True),
        ToolParameter(name="lookback_days", type="integer", description="回看天数，默认10天", required=False, default=10),
    ]
)
def get_north_flow(
    trade_date: Annotated[str, "交易日期，格式：YYYY-MM-DD"],
    lookback_days: Annotated[int, "回看天数，默认10天"] = 10
) -> str:
    # 实际实现...
```

## 🔄 两者的关系和工作流程

### 加载顺序

1. **第一步**: `ToolRegistry._load_builtin_tools()`
   - 从 `BUILTIN_TOOLS` 加载所有工具的元数据（包括参数）
   - 此时只有元数据，没有函数实现

2. **第二步**: `ToolRegistry._load_tool_implementations()`
   - 通过 `ToolLoader` 自动发现和加载工具实现文件
   - 调用 `@register_tool` 装饰器注册函数

### 注册逻辑 (registry.py:116-164)

```python
def register_function(self, tool_id: str, func: Callable, ...):
    # 如果工具已注册但没有函数实现，则添加函数实现
    if tool_id in self._tools:
        if tool_id not in self._functions:
            # ✅ 元数据已存在（来自 BUILTIN_TOOLS），只添加函数实现
            self._functions[tool_id] = func
            return
    
    # ❌ 如果工具不在 BUILTIN_TOOLS 中，创建新元数据
    # 但此时不会包含 parameters 信息！
    metadata = ToolMetadata(
        id=tool_id,
        name=name,
        description=description,
        # ⚠️ 注意：这里没有 parameters！
    )
```

## ⚠️ 关键问题

### 问题1: 参数信息丢失

如果工具**只在 `@register_tool` 中注册**，而没有在 `BUILTIN_TOOLS` 中定义：
- ✅ 函数可以正常调用
- ❌ **参数信息会丢失**（`parameters` 为空列表）
- ❌ 前端无法显示参数
- ❌ API 无法返回参数信息
- ❌ 提示词生成时无法获取参数信息

### 问题2: 参数不一致

如果 `BUILTIN_TOOLS` 中的参数定义与函数签名不一致：
- 可能导致调用错误
- 提示词中的参数说明可能不正确

## ✅ 最佳实践

### 方式1：推荐做法 - 两者都要有（参数在 BUILTIN_TOOLS 中定义）

1. **在 `BUILTIN_TOOLS` 中定义完整元数据**（包括所有参数）
2. **在实现文件中使用 `@register_tool` 注册函数**

**优点**:
- 参数定义集中管理
- 前端和API可以统一获取参数信息
- 提示词生成时可以获取参数信息

### 方式2：新方式 - 在 @register_tool 中传递 parameters

如果工具没有在 `BUILTIN_TOOLS` 中定义，可以在 `@register_tool` 中直接传递 `parameters`：

```python
from core.tools.config import ToolParameter

@register_tool(
    tool_id="my_custom_tool",
    name="我的自定义工具",
    description="工具描述",
    category="custom",
    parameters=[  # 🔑 直接传递参数定义
        ToolParameter(name="param1", type="string", description="参数1", required=True),
        ToolParameter(name="param2", type="integer", description="参数2", required=False, default=10),
    ]
)
def my_custom_tool(param1: str, param2: int = 10) -> str:
    return f"Result: {param1} - {param2}"
```

**优点**:
- 工具定义自包含，不需要在 `BUILTIN_TOOLS` 中定义
- 适合临时工具或自定义工具

**缺点**:
- 如果工具需要在多个地方使用，还是建议在 `BUILTIN_TOOLS` 中定义

### 参数定义规范

**在 `BUILTIN_TOOLS` 中**:
```python
parameters=[
    ToolParameter(
        name="trade_date", 
        type="string", 
        description="交易日期，格式：YYYY-MM-DD",  # 包含格式说明
        required=True
    ),
    ToolParameter(
        name="lookback_days", 
        type="integer", 
        description="回看天数，默认10天",  # 包含默认值说明
        required=False, 
        default=10
    ),
]
```

**在函数签名中**:
```python
def get_north_flow(
    trade_date: Annotated[str, "交易日期，格式：YYYY-MM-DD"],
    lookback_days: Annotated[int, "回看天数，默认10天"] = 10
) -> str:
```

### 一致性检查

确保：
- ✅ `BUILTIN_TOOLS` 中的参数名与函数参数名一致
- ✅ 参数类型一致（string/integer）
- ✅ 必需/可选一致
- ✅ 默认值一致

## 📝 总结

| 特性 | BUILTIN_TOOLS | @register_tool |
|------|---------------|----------------|
| **职责** | 元数据定义 | 函数实现注册 |
| **参数信息** | ✅ 完整定义 | ❌ 不包含 |
| **加载时机** | 初始化时 | 运行时 |
| **用途** | 前端展示、API查询 | 函数调用 |
| **必需性** | ✅ 必需（用于参数信息） | ✅ 必需（用于函数调用） |

**结论**: 两者都需要，且参数定义应该在 `BUILTIN_TOOLS` 中完整定义！

