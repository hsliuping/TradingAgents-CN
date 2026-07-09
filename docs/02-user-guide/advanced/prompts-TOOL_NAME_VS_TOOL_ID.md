# 工具名称 vs 工具 ID - 使用说明

## 📋 核心概念

每个工具有两个标识：

| 字段 | 类型 | 用途 | 示例 |
|------|------|------|------|
| **id** | 英文标识符 | LLM 调用工具时使用 | `get_stock_market_data_unified` |
| **name** | 中文显示名 | 前端界面显示 | `统一市场数据` |

---

## ⚠️ 重要结论

### 在提示词中必须使用英文的 `tool_id`，不能使用中文的 `name`！

**原因**：
1. LangChain 工具注册时使用的是 `tool_id`（英文）
2. LLM 调用工具时，必须使用注册时的名称
3. 中文名称只是用于前端显示，LLM 看不到

---

## 🔍 工具数据结构

### 后端定义（`core/tools/config.py`）

```python
BUILTIN_TOOLS = {
    "get_stock_market_data_unified": ToolMetadata(
        id="get_stock_market_data_unified",      # ← LLM 使用这个
        name="统一市场数据",                      # ← 前端显示这个
        description="获取股票市场数据（价格、成交量、技术指标）的统一接口",
        category=ToolCategory.MARKET,
        # ...
    )
}
```

### LangChain 工具注册（`core/tools/registry.py`）

```python
lc_tool = StructuredTool.from_function(
    func=func,
    name=tool_id,  # ← 使用英文 ID，如 "get_stock_market_data_unified"
    description=metadata.description
)
```

### 前端显示（`frontend/src/views/Workflow/AgentDetail.vue`）

```vue
<div class="tool-name">
  {{ tool.name }}  <!-- 显示中文名称：统一市场数据 -->
</div>
```

---

## ✅ 正确示例

### 示例 1: 单个工具

**前端显示**：
```
可用工具: 统一市场数据
```

**提示词中应该写**：
```markdown
**工具使用指导**:

调用 `get_stock_market_data_unified` 工具获取市场数据
参数: ticker={ticker}, start_date={start_date}, end_date={current_date}
```

### 示例 2: 多个工具

**前端显示**：
```
可用工具: 
- 统一市场数据
- 统一基本面数据
- 股票新闻
```

**提示词中应该写**：
```markdown
**工具使用指导**:

1. 调用 `get_stock_market_data_unified` 获取市场数据
2. 调用 `get_stock_fundamentals_unified` 获取基本面数据
3. 调用 `get_stock_news` 获取新闻数据
```

---

## ❌ 错误示例

### 错误 1: 使用中文名称

```markdown
❌ 错误：
调用 `统一市场数据` 工具

✅ 正确：
调用 `get_stock_market_data_unified` 工具
```

### 错误 2: 混用中英文

```markdown
❌ 错误：
使用 统一市场数据 (get_stock_market_data_unified) 工具

✅ 正确：
调用 `get_stock_market_data_unified` 工具
```

---

## 🔧 如何查找工具 ID

### 方法 1: 通过前端界面

1. 打开浏览器开发者工具（F12）
2. 在 Agent 详情页查看工具配置
3. 在 Network 标签中查看 API 响应
4. 找到 `id` 字段

### 方法 2: 通过 MongoDB

```javascript
// 查看所有工具的 ID 和名称
db.tool_configs.find({}, { tool_id: 1, name: 1, _id: 0 })
```

### 方法 3: 通过代码

查看 `core/tools/config.py` 中的 `BUILTIN_TOOLS` 定义。

---

## 📝 常用工具 ID 速查表

| 中文名称 | 工具 ID | 用途 |
|---------|---------|------|
| 统一市场数据 | `get_stock_market_data_unified` | 获取股票价格、成交量等市场数据 |
| 统一基本面数据 | `get_stock_fundamentals_unified` | 获取财务报表、估值指标等基本面数据 |
| 股票新闻 | `get_stock_news` | 获取股票相关新闻 |
| YFinance在线数据 | `get_YFin_data_online` | 从 Yahoo Finance 获取数据 |
| Tushare数据 | `get_tushare_data` | 从 Tushare 获取中国市场数据 |

---

## 💡 最佳实践

### 1. 编写提示词时

```markdown
**工具使用指导**:

调用 `get_stock_market_data_unified` 工具
- 参数: ticker={ticker}, start_date={start_date}
- 用途: 获取历史价格和成交量数据
```

### 2. 使用代码块标记工具名

使用反引号 `` ` `` 包裹工具 ID，使其更清晰：

```markdown
调用 `get_stock_market_data_unified` 工具
```

### 3. 提供工具用途说明

除了工具 ID，还要说明工具的用途：

```markdown
1. **市场数据**: 调用 `get_stock_market_data_unified` 获取价格走势
2. **基本面数据**: 调用 `get_stock_fundamentals_unified` 获取财务指标
```

---

**最后更新**: 2026-01-09  
**版本**: v1.0.1

