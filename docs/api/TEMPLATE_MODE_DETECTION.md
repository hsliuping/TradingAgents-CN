# 提示词模板模式检测

## 📋 概述

本文档说明如何判断当前流程是**正式分析流程**还是**调试模式**，以及两种模式下的模板选择逻辑。

---

## 🔍 判断方法

### 通过 `AgentContext` 判断

```python
from tradingagents.agents.utils.agent_context import AgentContext

# 检查是否为调试模式
is_debug_mode = context and getattr(context, 'is_debug_mode', False)
debug_template_id = context and getattr(context, 'debug_template_id', None)

if is_debug_mode and debug_template_id:
    print("✅ 调试模式")
else:
    print("❌ 正式流程")
```

---

## 🎯 两种模式的区别

### 1. 调试模式

**触发条件**:

- `is_debug_mode = True`
- `debug_template_id` 不为空

**创建方式**:

```python
# 调试接口 (app/routers/templates_debug.py)
ctx = AgentContext(
    user_id=str(user["id"]),
    preference_id="neutral",
    is_debug_mode=bool(req.template_id),  # ✅ True
    debug_template_id=req.template_id     # ✅ 指定模板ID
)
```

**模板选择**:

- ✅ 使用指定的调试模板
- ✅ **允许使用草稿状态的模板** (`status='draft'`)
- ✅ 不检查 `status` 字段
- ✅ 优先级最高

**查询条件**:

```python
template = templates_collection.find_one({
    "_id": ObjectId(debug_template_id)
    # 不检查 status 字段
})
```

---

### 2. 正式流程

**触发条件**:

- `is_debug_mode = False` (默认值)
- `debug_template_id = None` (默认值)

**创建方式**:

```python
# 正式分析流程 (app/services/analysis_service.py)
ctx = AgentContext(
    user_id=str(task.user_id),
    preference_id=risk_preference
    # ❌ 没有设置 is_debug_mode 和 debug_template_id
)
```

**模板选择**:

- ✅ 使用用户配置的模板（如果有）
- ✅ **只使用已发布状态的模板** (`status='active'`)
- ✅ 如果用户模板是草稿状态，跳过并使用系统模板
- ✅ 系统模板作为兜底

**查询条件**:

```python
# 用户模板
template = templates_collection.find_one({
    "_id": config["template_id"],
    "status": "active"  # 🔥 只使用已发布状态
})

# 系统模板
template = templates_collection.find_one({
    "agent_type": agent_type,
    "agent_name": agent_name,
    "preference_type": preference_id,
    "is_system": True,
    "status": "active"  # 🔥 只使用已发布状态
})
```

---

## 📊 优先级顺序

### 调试模式

```text
1. 调试模板 (debug_template_id)
   ├─ 允许草稿状态
   └─ 不检查 status 字段

2. 用户模板 (user_id + is_active=True)
   ├─ 只使用已发布状态
   └─ status='active'

3. 系统模板 (is_system=True)
   ├─ 只使用已发布状态
   └─ status='active'
```

### 正式流程

```text
1. 用户模板 (user_id + is_active=True)
   ├─ 只使用已发布状态
   └─ status='active'

2. 系统模板 (is_system=True)
   ├─ 只使用已发布状态
   └─ status='active'
```

---

## 🔄 流程图

```text
┌─────────────────────────────────────┐
│  接收到分析请求                      │
└──────────────┬──────────────────────┘
               │
               ▼
        ┌──────────────┐
        │ 检查 context │
        └──────┬───────┘
               │
       ┌───────┴────────┐
       │                │
       ▼                ▼
  is_debug_mode?   is_debug_mode?
  = True           = False
       │                │
       ▼                ▼
  ┌─────────┐      ┌─────────┐
  │ 调试模式 │      │ 正式流程 │
  └────┬────┘      └────┬────┘
       │                │
       ▼                ▼
  使用调试模板      使用用户/系统模板
  (允许草稿)        (只用已发布)
       │                │
       ▼                ▼
  返回模板内容      返回模板内容
```

---

## 💻 代码示例

### 示例 1: 调试模式

```python
from tradingagents.agents.utils.agent_context import AgentContext
from tradingagents.utils.template_client import get_template_client

# 创建调试模式的 AgentContext
ctx = AgentContext(
    user_id="user_123",
    preference_id="neutral",
    is_debug_mode=True,
    debug_template_id="69624892ae45e52f3a70130e"  # 草稿模板ID
)

# 获取模板
client = get_template_client()
template = client.get_effective_template(
    agent_type="researchers_v2",
    agent_name="bear_researcher_v2",
    context=ctx
)

# ✅ 返回草稿模板（status='draft'）
print(f"模板来源: {template.get('source')}")  # 'debug'
print(f"模板状态: 允许草稿")
```

### 示例 2: 正式流程

```python
from tradingagents.agents.utils.agent_context import AgentContext
from tradingagents.utils.template_client import get_template_client

# 创建正式流程的 AgentContext
ctx = AgentContext(
    user_id="user_123",
    preference_id="conservative"
    # is_debug_mode=False (默认值)
    # debug_template_id=None (默认值)
)

# 获取模板
client = get_template_client()
template = client.get_effective_template(
    agent_type="researchers_v2",
    agent_name="bear_researcher_v2",
    context=ctx
)

# ❌ 如果用户配置的模板是草稿状态，跳过并使用系统模板
# ✅ 只返回已发布状态的模板（status='active'）
print(f"模板来源: {template.get('source')}")  # 'user' 或 'system'
print(f"模板状态: 只使用已发布")
```

---

## 🎯 使用场景

### 调试场景

- ✅ 提示词模板调试页面
- ✅ 测试草稿模板
- ✅ 开发和调试

### 调试台能力补充（2026-03）

模板调试页面已经不再只是“看单个模板效果”，而是扩展为统一调试台。

当前页面包含三种模式：

- 单 Agent 调试：用于直接执行某个 Agent，并支持额外 `extra_state` 注入
- 完整工作流调试：用于跑整条工作流并查看各节点输出
- 调用记录：用于统一查看 Assistant、Workflow、Agent 三类调用记录

其中单 Agent 调试在 2026-03 已扩展为统一 Agent 调试入口，可直接覆盖：

- analyst
- researcher
- risk
- manager
- trader

其中调用记录模式支持：

- 平铺查看调用记录
- 按 root 调用链分组
- 锁定当前调用链
- 查看 manager/trader 类 Agent 的前置输入来源
- 从历史调用链一键回填到单 Agent 调试
- 对比来源节点与当前节点的 Request/Result

调试台当前还会直接展示并消费以下治理/契约信息：

- `maturity_level`
- `input_mode`
- `debug_replay_mode`
- `callable_surfaces`
- `input_contract[*].source`
- `input_contract[*].state_field`
- `input_contract[*].producer_hint`

因此，对依赖上游 state 的 Agent，当前表单已经不再只依赖 `debug_inputs` 推断，而是优先按照声明式 `input_contract` 渲染额外输入区。

对于研究经理、风险经理、交易员等依赖上游 state 的 Agent，推荐调试路径如下：

1. 先在调用记录模式定位目标调用
2. 查看“前置输入来源”，确认 bull_report、bear_report、investment_plan 等字段来自哪条上游 invocation
3. 如需重放，点击“跳转并回填调试”
4. 在单 Agent 调试模式直接修改或补充前置 state 后再次执行

这套流程的意义在于：

- 不必每次都完整重跑整条工作流
- 可以精确复现某个 manager/trader 节点的输入上下文
- 可以快速定位是上游输出错误，还是下游消费逻辑错误

### 正式场景

- ✅ 股票分析任务
- ✅ 定时任务
- ✅ 生产环境

---

**最后更新**: 2026-03-17
**相关文档**:

- `tradingagents/agents/utils/agent_context.py`
- `tradingagents/utils/template_client.py`
- `app/routers/templates_debug.py`
- `frontend/src/views/Settings/TemplateDebug.vue`
- `app/services/analysis_service.py`
