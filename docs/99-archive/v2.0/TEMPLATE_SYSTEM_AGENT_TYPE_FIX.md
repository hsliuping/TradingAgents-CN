# 模板系统 Agent 类型参数修复

## 🔴 问题现象

工作流执行时，模板系统无法找到提示词模板：
```
❌ 未找到任何可用模板: review_analysis/review_manager (preference=neutral)
⚠️ 无法获取模板，使用降级提示词
```

虽然数据库中明确有这些模板。

---

## 🎯 根本原因

**Agent 类型参数不匹配**：

| Agent | 当前使用 | 应该使用 | 数据库中的值 |
|------|---------|---------|-----------|
| review_manager_v2 | `review_analysis` | ❌ | `reviewers_v2` | ✅ |
| timing_analyst_v2 | `review_analysis` | ❌ | `reviewers_v2` | ✅ |
| position_analyst_v2 | `review_analysis` | ❌ | `reviewers_v2` | ✅ |
| emotion_analyst_v2 | `review_analysis` | ❌ | `reviewers_v2` | ✅ |
| attribution_analyst_v2 | `review_analysis` | ❌ | `reviewers_v2` | ✅ |

**前端定义的 Agent 类型映射**（来自 `TemplateManagement.vue`）：
```javascript
reviewers_v2: ['timing_analyst_v2','position_analyst_v2','emotion_analyst_v2','attribution_analyst_v2','review_manager_v2']
```

---

## ✅ 修复方案（已实施）

### 修复所有 v2.0 复盘 Agent

**修改的文件**：
1. `core/agents/adapters/review/review_manager_v2.py`
2. `core/agents/adapters/review/timing_analyst_v2.py`
3. `core/agents/adapters/review/position_analyst_v2.py`
4. `core/agents/adapters/review/emotion_analyst_v2.py`
5. `core/agents/adapters/review/attribution_analyst_v2.py`

**修改内容**：
```python
# 修改前
prompt = get_agent_prompt(
    agent_type="review_analysis",  # ❌ 错误
    agent_name="review_manager",   # ❌ 错误
    ...
)

# 修改后
prompt = get_agent_prompt(
    agent_type="reviewers_v2",     # ✅ 正确
    agent_name="review_manager_v2", # ✅ 正确
    ...
)
```

---

## 📋 修复清单

- [x] review_manager_v2 - 使用 `reviewers_v2` 和 `review_manager_v2`
- [x] timing_analyst_v2 - 使用 `reviewers_v2` 和 `timing_analyst_v2`
- [x] position_analyst_v2 - 使用 `reviewers_v2` 和 `position_analyst_v2`
- [x] emotion_analyst_v2 - 使用 `reviewers_v2` 和 `emotion_analyst_v2`
- [x] attribution_analyst_v2 - 使用 `reviewers_v2` 和 `attribution_analyst_v2`

---

## 🧪 验证方法

运行交易复盘流程，检查日志：
```
✅ 从模板系统获取复盘总结师提示词 (长度: XXXX)
✅ 从模板系统获取时机分析师提示词 (长度: XXXX)
✅ 从模板系统获取仓位分析师提示词 (长度: XXXX)
✅ 从模板系统获取情绪分析师提示词 (长度: XXXX)
✅ 从模板系统获取归因分析师提示词 (长度: XXXX)
```

如果看到这些日志，说明修复成功。

