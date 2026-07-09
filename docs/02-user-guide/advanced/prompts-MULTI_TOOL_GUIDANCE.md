# 多工具调用指导

## 📋 概述

当一个 Agent 绑定了多个工具时，需要在提示词模板的 `tool_guidance` 字段中明确指导 LLM 如何使用这些工具。

## ⚠️ 重要提示

**在提示词中必须使用英文的工具 ID，不能使用中文的工具名称！**

- ✅ 正确：`get_stock_market_data_unified`
- ❌ 错误：`统一市场数据`

**原因**：LLM 调用工具时使用的是注册时的英文 ID，中文名称只是前端显示用的。

详细说明请参考：[工具名称 vs 工具 ID](./TOOL_NAME_VS_TOOL_ID.md)

---

## 🔧 工具绑定机制

### 1. 查看 Agent 绑定的工具

在 MongoDB 的 `tool_agent_bindings` 集合中查看：

```javascript
db.tool_agent_bindings.find({ agent_id: "sector_analyst_v2" })
```

示例输出：
```json
[
  {
    "agent_id": "sector_analyst_v2",
    "tool_id": "get_stock_market_data_unified",
    "priority": 1,
    "is_active": true
  },
  {
    "agent_id": "sector_analyst_v2",
    "tool_id": "get_stock_fundamentals_unified",
    "priority": 2,
    "is_active": true
  }
]
```

### 2. 工具名称变量

在提示词模板中，可以使用 `{tool_names}` 变量来动态插入工具名称列表。

---

## ✍️ 编写多工具调用指导

### 方式 1: 顺序调用（推荐）

适用于工具之间有依赖关系的场景。

```markdown
**工具使用指导**:

1. **第一步 - 获取市场数据**:
   调用 `get_stock_market_data_unified` 工具
   - 参数: ticker={ticker}, start_date={start_date}, end_date={current_date}
   - 用途: 获取股票的历史价格、成交量等市场数据

2. **第二步 - 获取基本面数据**:
   调用 `get_stock_fundamentals_unified` 工具
   - 参数: ticker={ticker}
   - 用途: 获取公司的财务报表、估值指标等基本面数据

3. **第三步 - 综合分析**:
   基于两个工具返回的数据，进行综合分析

⚠️ **严格要求**:
- 必须按顺序调用工具（使用英文工具 ID）
- 等待每个工具返回结果后再调用下一个
- 不允许假设或编造数据
```

**注意**：工具 ID 必须使用英文，如 `get_stock_market_data_unified`，不能使用中文名称"统一市场数据"。

### 方式 2: 并行调用

适用于工具之间无依赖关系的场景。

```markdown
**工具使用指导**:

请同时调用以下工具获取数据：

1. **市场数据工具**: `get_stock_market_data_unified`
   - 参数: ticker={ticker}, start_date={start_date}, end_date={current_date}

2. **基本面数据工具**: `get_stock_fundamentals_unified`
   - 参数: ticker={ticker}

3. **新闻数据工具**: `get_stock_news`
   - 参数: ticker={ticker}, limit=10

⚠️ **注意**: 等待所有工具返回结果后再进行分析
```

### 方式 3: 条件调用

根据情况选择性调用工具。

```markdown
**工具使用指导**:

根据分析需求选择合适的工具：

1. **基础分析** - 必须调用:
   - `get_stock_market_data_unified`: 获取价格和成交量数据

2. **深度分析** - 可选调用:
   - `get_stock_fundamentals_unified`: 如需财务分析
   - `get_stock_news`: 如需了解最新动态
   - `calculate_technical_indicators`: 如需技术指标

**调用策略**:
- 先调用基础工具
- 根据初步分析结果决定是否调用其他工具
```

---

## 📝 实际示例

### 示例 1: 行业分析师（2个工具）

**Agent**: `sector_analyst_v2`  
**绑定工具**: 
- `get_stock_market_data_unified`
- `get_industry_comparison_data`

**tool_guidance**:
```markdown
**工具调用指导**:

1. **获取个股数据**: 
   调用 `get_stock_market_data_unified` 工具
   - 参数: ticker={ticker}, start_date={start_date}, end_date={current_date}
   - 获取目标股票的市场表现数据

2. **获取行业对比数据**: 
   调用 `get_industry_comparison_data` 工具
   - 参数: ticker={ticker}, industry={industry}
   - 获取同行业其他公司的对比数据

3. **综合分析**:
   - 对比个股与行业平均水平
   - 分析行业地位和竞争优势
   - 提供基于行业对比的投资建议

⚠️ **严格要求**: 必须调用两个工具，不允许跳过任何步骤
```

### 示例 2: 综合分析师（3个工具）

**Agent**: `comprehensive_analyst_v2`  
**绑定工具**: 
- `get_stock_market_data_unified`
- `get_stock_fundamentals_unified`
- `get_stock_news`

**tool_guidance**:
```markdown
**工具调用指导**:

请按以下顺序调用工具：

1. **市场数据** (`get_stock_market_data_unified`):
   - 参数: ticker={ticker}, start_date={start_date}, end_date={current_date}
   - 分析: 价格走势、成交量、波动率

2. **基本面数据** (`get_stock_fundamentals_unified`):
   - 参数: ticker={ticker}
   - 分析: 财务指标、估值水平、盈利能力

3. **新闻数据** (`get_stock_news`):
   - 参数: ticker={ticker}, limit=10
   - 分析: 最新动态、市场情绪、重大事件

**综合分析框架**:
- 技术面（市场数据）
- 基本面（财务数据）
- 消息面（新闻数据）
- 三维度综合评估

⚠️ **注意**: 必须等待所有工具返回后再生成报告
```

---

## 🎯 最佳实践

### 1. 明确工具调用顺序
```markdown
✅ 好的示例:
1. 先调用 A 工具
2. 再调用 B 工具
3. 最后调用 C 工具

❌ 不好的示例:
使用 A、B、C 工具获取数据（没有明确顺序）
```

### 2. 说明每个工具的用途
```markdown
✅ 好的示例:
- `get_market_data`: 获取价格和成交量数据
- `get_fundamentals`: 获取财务报表数据

❌ 不好的示例:
调用所有可用工具
```

### 3. 提供参数示例
```markdown
✅ 好的示例:
调用 get_stock_data 工具
参数: ticker={ticker}, start_date={start_date}

❌ 不好的示例:
调用 get_stock_data 工具（没有说明参数）
```

---

## 🗄️ 数据库配置示例

### 为 Agent 绑定多个工具

在 MongoDB 中执行以下命令：

```javascript
// 示例：为行业分析师绑定2个工具
db.tool_agent_bindings.insertMany([
  {
    "agent_id": "sector_analyst_v2",
    "tool_id": "get_stock_market_data_unified",
    "priority": 1,  // 优先级：数字越小越优先
    "is_active": true,
    "created_at": new Date().toISOString(),
    "updated_at": new Date().toISOString()
  },
  {
    "agent_id": "sector_analyst_v2",
    "tool_id": "get_industry_comparison_data",
    "priority": 2,
    "is_active": true,
    "created_at": new Date().toISOString(),
    "updated_at": new Date().toISOString()
  }
])

// 查看绑定结果
db.tool_agent_bindings.find({ agent_id: "sector_analyst_v2" })
```

### 通过 API 配置工具绑定

```python
# 使用 BindingManager
from core.config import BindingManager

bm = BindingManager()

# 绑定第一个工具
bm.bind_tool(
    agent_id="sector_analyst_v2",
    tool_id="get_stock_market_data_unified",
    priority=1
)

# 绑定第二个工具
bm.bind_tool(
    agent_id="sector_analyst_v2",
    tool_id="get_industry_comparison_data",
    priority=2
)

# 查看绑定的工具
tools = bm.get_tools_for_agent("sector_analyst_v2")
print(f"绑定的工具: {tools}")
# 输出: ['get_stock_market_data_unified', 'get_industry_comparison_data']
```

---

## 💡 常见问题

### Q1: 工具调用顺序重要吗？

**A**: 取决于工具之间是否有依赖关系。

- **有依赖**: 必须按顺序调用（如：先获取数据，再分析数据）
- **无依赖**: 可以并行调用（如：同时获取市场数据和新闻数据）

### Q2: 如何让 LLM 只调用部分工具？

**A**: 在 `tool_guidance` 中使用条件语句：

```markdown
**工具调用策略**:

1. **必须调用**: `get_stock_market_data_unified`
2. **可选调用**:
   - 如需深度分析，调用 `get_stock_fundamentals_unified`
   - 如需了解最新动态，调用 `get_stock_news`
```

### Q3: 工具调用失败怎么办？

**A**: 在 `tool_guidance` 中添加错误处理指导：

```markdown
**错误处理**:

- 如果工具调用失败，说明原因并提供替代方案
- 不要假设数据，明确告知用户数据不可用
- 可以尝试调用备用工具（如果有）
```

### Q4: 如何动态显示工具名称？

**A**: 使用 `{tool_names}` 变量：

```markdown
**可用工具**: {tool_names}

请根据分析需求选择合适的工具进行调用。
```

系统会自动将 `{tool_names}` 替换为实际绑定的工具名称列表。

---

**最后更新**: 2026-01-09
**版本**: v1.0.1

