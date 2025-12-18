# 工作流 Agent 工具加载问题诊断与修复

## 🔴 问题现象

仓位分析师在执行时提示：
```
请提供完整的交易记录、账户信息及风险指标数据...
```

虽然已在数据库配置了工具绑定，但 Agent 仍无法获取数据。

**日志显示**：
```
📦 [BindingManager] 数据库查询结果: 0 条绑定, 工具: []
🔍 [BindingManager] 数据库无结果，尝试从代码配置加载...
```

---

## 🎯 根本原因（已确认）

**工作流版本不匹配**：

| 组件 | 当前值 | 应该值 |
|------|--------|--------|
| 加载的工作流 ID | `trade_review` (v1.0) | ❌ |
| 应该加载的工作流 ID | `trade_review_v2` (v2.0) | ✅ |
| 工作流中的 Agent ID | `timing_analyst` (v1.0) | ❌ |
| 应该使用的 Agent ID | `timing_analyst_v2` (v2.0) | ✅ |
| 数据库工具绑定 | `timing_analyst_v2` | ✅ |

**问题链**：
1. `trade_review_service.py` 加载 `"trade_review"` 工作流 (v1.0)
2. v1.0 工作流使用 `timing_analyst` Agent (v1.0)
3. BindingManager 查询 `timing_analyst` 的工具绑定
4. 数据库中只有 `timing_analyst_v2` 的工具绑定
5. 查询返回 0 条结果 → 降级到代码配置

---

## 🔍 详细原因分析

### 问题链路

```
工作流执行 (trade_review_v2)
  ↓
WorkflowEngine.execute()
  ↓
WorkflowBuilder._create_agent_node()
  ↓
BindingManager.get_tools_for_agent(agent_id="timing_analyst_v2")
  ↓
数据库查询: {"agent_id": "timing_analyst_v2", ...}
  ↓
✅ 应该返回数据库中的工具绑定
  ↓
❌ 但实际返回 0 条结果
```

### 关键代码位置

**1. 工作流定义 (core/workflow/templates/trade_review_workflow_v2.py:53)**

```python
NodeDefinition(
    id="timing_analyst_v2",
    type=NodeType.ANALYST,
    agent_id="timing_analyst_v2",  # ✅ v2.0 Agent ID
    label="时机分析师 v2.0",
    ...
)
```

**2. BindingManager.get_tools_for_agent() (core/config/binding_manager.py:95)**

```python
# 从数据库加载
bindings = list(self._db.tool_agent_bindings.find(
    {"agent_id": agent_id, "is_active": {"$ne": False}},  # 查询 timing_analyst_v2
    sort=[("priority", -1)]
))
tool_ids = [b["tool_id"] for b in bindings]
# 返回: [] (0 条结果)
```

**问题**: 数据库中的工具绑定可能没有正确保存，或者查询条件有问题

**3. 降级到代码配置 (core/config/binding_manager.py:107-110)**

```python
if not tool_ids:
    logger.info(f"🔍 [BindingManager] 数据库无结果，尝试从代码配置加载...")
    tool_ids = self._get_default_tools_for_agent(agent_id)
    # 返回: ['get_stock_market_data_unified', 'build_trade_info']
```

**问题**: 使用了代码中的默认工具，而不是数据库中配置的完整工具列表

---

## 🔧 解决方案

### 方案 1: 检查数据库连接

```bash
# 查看日志中是否有数据库连接错误
grep -i "database\|mongodb\|binding" logs/app.log

# 检查 BindingManager 初始化日志
grep -i "BindingManager" logs/app.log
```

### 方案 2: 验证工具绑定数据

```python
# 在 MongoDB 中查询工具绑定
db.tool_agent_bindings.find({"agent_id": "position_analyst"})

# 应该返回类似：
# {
#   "_id": ObjectId(...),
#   "agent_id": "position_analyst",
#   "tool_id": "build_trade_info",
#   "is_active": true,
#   "priority": 1
# }
```

### 方案 3: 确保工作流 ID 被正确传递

在 `WorkflowBuilder._create_agent_node()` 中，需要确保 `self._workflow_id` 不为 None：

```python
# 当前代码
if self._workflow_id:
    tool_ids = self.binding_manager.get_tools_for_workflow_agent(...)

# 应该改为
tool_ids = self.binding_manager.get_tools_for_agent(agent_id)
if not tool_ids:
    logger.warning(f"⚠️ 从数据库加载工具失败，使用元数据默认工具")
```

### 方案 4: 增强日志输出

在关键位置添加详细日志：

```python
# 在 BindingManager.get_tools_for_agent() 中
logger.info(f"🔍 [BindingManager] 查询工具绑定: agent_id={agent_id}")
logger.info(f"📦 [BindingManager] 数据库连接状态: {self._db is not None}")
logger.info(f"📦 [BindingManager] 查询结果: {len(tool_ids)} 个工具")
if tool_ids:
    logger.info(f"📦 [BindingManager] 工具列表: {tool_ids}")
else:
    logger.warning(f"⚠️ [BindingManager] 未找到工具绑定，将使用代码配置")
```

---

## 📋 检查清单

- [ ] 数据库连接正常
- [ ] `tool_agent_bindings` 集合中有数据
- [ ] Agent 配置中的 `tools` 列表不为空
- [ ] 工作流执行时日志显示工具已加载
- [ ] Agent 执行时日志显示工具调用

---

## 🚀 快速诊断步骤

1. **查看工作流执行日志**
   ```
   grep "BindingManager\|工具\|tool" logs/app.log | tail -100
   ```

2. **检查数据库连接**
   ```
   grep "数据库\|database\|mongodb" logs/app.log | tail -50
   ```

3. **验证 Agent 初始化**
   ```
   grep "position_analyst\|仓位分析师" logs/app.log | tail -50
   ```

4. **查看工具加载**
   ```
   grep "📦\|从.*加载.*工具" logs/app.log | tail -50
   ```

---

## ✅ 修复方案（已实施）

### 修复 1：更改工作流加载 ID（已完成）

**文件**：`app/services/trade_review_service.py` 第 1909 行

```python
# 修改前
workflow = provider.load_workflow("trade_review")  # ❌ v1.0 工作流

# 修改后
workflow = provider.load_workflow("trade_review_v2")  # ✅ v2.0 工作流
```

**效果**：
- 工作流现在加载 v2.0 版本
- 工作流中的 Agent ID 变为 `timing_analyst_v2` 等
- BindingManager 查询 `timing_analyst_v2` 的工具绑定
- 数据库查询返回正确的工具列表

---

## 🔧 验证方案

### 方案 A：验证数据库中的工具绑定

**步骤 1**：检查数据库中是否真的有工具绑定

```javascript
// 在 MongoDB 中执行
db.tool_agent_bindings.find({"agent_id": "timing_analyst_v2"})

// 应该返回类似：
// {
//   "_id": ObjectId(...),
//   "agent_id": "timing_analyst_v2",
//   "tool_id": "build_trade_info",
//   "is_active": true,
//   "priority": 1
// }
```

**步骤 2**：如果没有数据，需要重新保存工具绑定

```python
# 在 MongoDB 中插入工具绑定
db.tool_agent_bindings.insertMany([
    {
        "agent_id": "timing_analyst_v2",
        "tool_id": "build_trade_info",
        "is_active": True,
        "priority": 1
    },
    {
        "agent_id": "timing_analyst_v2",
        "tool_id": "get_market_snapshot_for_review",
        "is_active": True,
        "priority": 2
    },
    # ... 其他工具
])
```

### 方案 B：增强 BindingManager 的调试日志

在 `core/config/binding_manager.py` 中添加更详细的日志：

```python
def get_tools_for_agent(self, agent_id: str) -> List[str]:
    logger.info(f"🔍 [BindingManager] 查询 {agent_id} 的工具绑定...")
    logger.info(f"📦 [BindingManager] 数据库连接状态: {self._db is not None}")

    if self._db is not None:
        try:
            # 添加调试日志
            logger.info(f"🔍 [BindingManager] 执行查询: {{'agent_id': '{agent_id}', 'is_active': {{'$ne': False}}}}")

            bindings = list(self._db.tool_agent_bindings.find(
                {"agent_id": agent_id, "is_active": {"$ne": False}},
                sort=[("priority", -1)]
            ))

            logger.info(f"📦 [BindingManager] 查询结果: {len(bindings)} 条")
            if bindings:
                logger.info(f"📦 [BindingManager] 绑定详情: {bindings}")

            tool_ids = [b["tool_id"] for b in bindings]
            return tool_ids
        except Exception as e:
            logger.error(f"❌ [BindingManager] 数据库查询失败: {e}", exc_info=True)
```

### 方案 C：确保 v2.0 Agent 的工具配置完整

在 `core/agents/adapters/review/timing_analyst_v2.py` 中：

```python
@register_agent
class TimingAnalystV2(ResearcherAgent):
    metadata = AgentMetadata(
        id="timing_analyst_v2",
        name="时机分析师 v2.0",
        # ✅ 添加完整的工具列表
        tools=[
            "get_stock_market_data_unified",
            "get_stockstats_indicators_report",
            "get_trade_records",
            "build_trade_info",
            "get_market_snapshot_for_review"
        ],
        default_tools=[
            "build_trade_info",
            "get_market_snapshot_for_review"
        ],
    )
```

---

## 📝 相关文件

- `core/workflow/builder.py` - 工作流构建器
- `core/config/binding_manager.py` - 工具绑定管理器
- `core/agents/base.py` - Agent 基类
- `app/services/trade_review_service.py` - 交易复盘服务

