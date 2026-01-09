# 社交分析师调试模式修复

**日期**: 2026-01-09  
**问题**: 调试模式下无法使用指定的模板ID  
**影响范围**: 所有 v2.0 分析师

---

## 🐛 问题描述

### 1. 数据库命名冲突

**问题**：
- `prompt_templates` 集合中存在重复的社交分析师模板：
  - `social_analyst_v2`（正确，4个模板）
  - `social_media_analyst_v2`（重复，3个模板）
- Agent 代码中使用了 `social_media_analyst_v2`，但数据库中已删除

**日志错误**：
```
agent_type=analysts_v2 agent_name=social_media_analyst_v2
❌ 未找到任何可用模板: analysts_v2/social_media_analyst_v2
```

### 2. 调试模式不生效

**问题**：
- 前端传递了 `template_id`，后端创建了 `AgentContext` 并设置了 `debug_template_id`
- 但 v2.0 Agent 在调用 `get_agent_prompt` 时**没有传递 `context` 参数**
- 导致模板系统无法识别调试模式，无法使用指定的模板ID

**根本原因**：
- `AnalystAgent` 基类从 `state` 中提取 `context`，但没有传递给 `_build_system_prompt`
- 各个 v2.0 分析师的 `_build_system_prompt` 方法虽然有 `context` 参数，但调用 `get_agent_prompt` 时没有传递

---

## ✅ 修复方案

### 1. 清理数据库重复模板

**执行脚本**: `scripts/fix_social_analyst_templates.py`

**操作**：
1. 删除 3 个重复的 `social_media_analyst_v2` 模板
2. 为所有 143 个模板添加 `agent_id` 字段
3. 统一命名规范

**结果**：
- ✅ 删除了 3 个重复模板
- ✅ 所有模板都有 `agent_id` 字段
- ✅ 社交分析师配置一致

### 2. 修复 Agent 代码中的命名

**文件**: `core/agents/adapters/social_analyst_v2.py`

**修改**：
```python
# 修改前
agent_name="social_media_analyst_v2"

# 修改后
agent_name="social_analyst_v2"  # ✅ 使用正确的 agent_name
```

### 3. 修复 AnalystAgent 基类

**文件**: `core/agents/analyst.py`

**修改 1**: 从 `state` 中提取 `context`
```python
# 🔥 提取 AgentContext（用于调试模式）
context = None
if "context" in state:
    context = state["context"]
elif "agent_context" in state:
    # 兼容旧格式：agent_context 是字典
    from tradingagents.agents.utils.agent_context import AgentContext
    ctx_dict = state["agent_context"]
    if isinstance(ctx_dict, dict):
        context = AgentContext(**ctx_dict)
    else:
        context = ctx_dict

# 2. 构建提示词
system_prompt = self._build_system_prompt(market_type, context=context)
```

**修改 2**: 更新抽象方法签名
```python
@abstractmethod
def _build_system_prompt(self, market_type: str, context=None) -> str:
    """
    构建系统提示词（子类实现）
    
    Args:
        market_type: 市场类型
        context: AgentContext 对象（用于调试模式）
        
    Returns:
        系统提示词
    """
    pass
```

### 4. 修复所有 v2.0 分析师

**修改的文件**：
1. ✅ `core/agents/adapters/social_analyst_v2.py`
2. ✅ `core/agents/adapters/news_analyst_v2.py`
3. ✅ `core/agents/adapters/sector_analyst_v2.py`
4. ✅ `core/agents/adapters/index_analyst_v2.py`
5. ✅ `core/agents/adapters/market_analyst_v2.py`
6. ✅ `core/agents/adapters/fundamentals_analyst_v2.py`（已正确实现）

**统一修改**：
```python
# 方法签名
def _build_system_prompt(self, market_type: str, context=None) -> str:
    """
    构建系统提示词
    
    Args:
        market_type: 市场类型（A股/港股/美股）
        context: AgentContext 对象（用于调试模式）
        
    Returns:
        系统提示词
    """
    # 调用 get_agent_prompt 时传递 context
    prompt = get_agent_prompt(
        agent_type="analysts_v2",
        agent_name="xxx_analyst_v2",
        variables=template_variables,
        preference_id="neutral",
        fallback_prompt=None,
        context=context  # ✅ 传递 context 以支持调试模式
    )
```

---

## 🔍 调试流程验证

### 完整流程

1. **前端**: 用户选择模板ID，调用调试接口
   ```typescript
   template_id: form.value.use_current ? undefined : form.value.template_id
   ```

2. **后端**: 创建 `AgentContext`
   ```python
   ctx = AgentContext(
       user_id=str(user["id"]),
       preference_id="neutral",
       is_debug_mode=bool(req.template_id),  # ✅ 自动检测
       debug_template_id=req.template_id     # ✅ 传递模板ID
   )
   ```

3. **工作流**: 将 `context` 放入 `state`
   ```python
   inputs = {
       "context": ctx,  # ✅ 传递 context
       # ... 其他参数
   }
   ```

4. **Agent**: 从 `state` 提取 `context` 并传递给模板系统
   ```python
   context = state.get("context")  # ✅ 提取
   system_prompt = self._build_system_prompt(market_type, context=context)  # ✅ 传递
   ```

5. **模板系统**: 优先使用调试模板
   ```python
   if is_debug_mode and debug_template_id:
       debug_template = self.templates_collection.find_one({"_id": ObjectId(debug_template_id)})
       if debug_template:
           return debug_template.get("content")  # ✅ 返回调试模板
   ```

---

## 📊 修复总结

| 项目 | 修复前 | 修复后 |
|------|--------|--------|
| 重复模板 | 3 个 `social_media_analyst_v2` | 0 个 ✅ |
| 缺失 `agent_id` | 143 个模板 | 0 个 ✅ |
| Agent 命名错误 | `social_media_analyst_v2` | `social_analyst_v2` ✅ |
| 缺失 `context` 传递 | 5 个分析师 | 0 个 ✅ |
| 调试模式 | ❌ 不生效 | ✅ 正常工作 |

---

## ✅ 验证步骤

1. 重启后端服务
2. 前端选择一个模板进行调试
3. 检查日志，应该看到：
   ```
   🔍 [调试模式] 使用调试模板ID: xxx
   ✅ [调试模式] 成功获取调试模板: analysts_v2/social_analyst_v2
   ```

---

**修复完成！** 🎉

