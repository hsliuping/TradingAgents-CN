# 风险分析师使用深度模型修复

## 📋 问题描述

### 背景
风险分析师（`risky_analyst_v2`, `safe_analyst_v2`, `neutral_analyst_v2`）需要处理大量分析报告：

1. **投资计划** - `{{investment_plan}}`
2. **看涨观点** - `{{bull_opinion}}`
3. **看跌观点** - `{{bear_opinion}}`
4. **激进/保守风险观点** - `{{risky_opinion}}`, `{{safe_opinion}}`
5. **大盘环境分析** - `{{index_report}}`
6. **行业板块分析** - `{{sector_report}}`
7. **市场技术分析** - `{{market_report}}`
8. **基本面分析** - `{{fundamentals_report}}`
9. **新闻事件分析** - `{{news_report}}`
10. **市场情绪分析** - `{{sentiment_report}}`

这些内容加起来可能有 **几千到上万字**，需要更强的模型来处理。

### 问题
在 v2.0 引擎中，风险分析师使用的是**快速模型**（`quick_think_llm`），而不是**深度模型**（`deep_think_llm`）。

**原始代码**（`core/workflow/builder.py` 第 1231-1239 行）：
```python
llm_type = "quick"  # 默认使用快速模型
if agent_id in ["research_manager_v2", "risk_manager_v2", "research_manager", "risk_manager"]:
    llm_type = "deep"  # 研究经理和风险经理使用深度模型
else:
    logger.info(f"[智能体创建] 🔧 {agent_id} 使用快速分析模型 (quick_think_llm)")
```

**问题**：
- ✅ `research_manager_v2` - 使用深度模型
- ✅ `risk_manager_v2` - 使用深度模型
- ❌ `risky_analyst_v2` - 使用**快速模型**（应该用深度模型！）
- ❌ `safe_analyst_v2` - 使用**快速模型**（应该用深度模型！）
- ❌ `neutral_analyst_v2` - 使用**快速模型**（应该用深度模型！）

---

## ✅ 解决方案

### 修改位置

#### 1. 模型分配逻辑
`core/workflow/builder.py` - 两处需要修改：

1. **第 1231-1245 行** - v2.0 Agent 创建逻辑
2. **第 1377-1389 行** - 旧版 Agent 创建逻辑（遗留适配器）

#### 2. 风险分析师 stance 属性
三个风险分析师缺少 `stance` 属性，导致基类调用 `_build_system_prompt(self.stance)` 时报错：

- `core/agents/adapters/risky_analyst_v2.py`
- `core/agents/adapters/safe_analyst_v2.py`
- `core/agents/adapters/neutral_analyst_v2.py`

### 修改内容

#### 1. 添加 stance 属性（修复 missing argument 错误）

**问题**：基类 `ResearcherAgent` 在 `execute()` 方法中调用 `self._build_system_prompt(self.stance)`，但风险分析师没有定义 `stance` 属性。

**修复**：在三个风险分析师类中添加 `stance` 属性：

```python
# risky_analyst_v2.py
class RiskyAnalystV2(ResearcherAgent):
    # ...

    # 研究立场（风险分析师使用 "risky"）
    stance = "risky"

    # 输出字段名
    output_field = "risky_opinion"
```

```python
# safe_analyst_v2.py
class SafeAnalystV2(ResearcherAgent):
    # ...

    # 研究立场（风险分析师使用 "safe"）
    stance = "safe"

    # 输出字段名
    output_field = "safe_opinion"
```

```python
# neutral_analyst_v2.py
class NeutralAnalystV2(ResearcherAgent):
    # ...

    # 研究立场（风险分析师使用 "neutral"）
    stance = "neutral"

    # 输出字段名
    output_field = "neutral_opinion"
```

#### 2. v2.0 Agent 创建逻辑（第 1231-1245 行）

**修改后**：
```python
# 🔥 关键修复：根据 agent_id 判断应该使用 quick 还是 deep LLM
# 使用深度模型的 Agent：
# 1. 管理者（research_manager, risk_manager）- 需要综合大量信息做决策
# 2. 风险分析师（risky/safe/neutral_analyst_v2）- 需要处理大量分析报告
# 其他 agent（普通分析师、研究员）使用快速模型
llm_type = "quick"  # 默认使用快速模型
if agent_id in [
    "research_manager_v2", "risk_manager_v2",  # v2.0 管理者
    "risky_analyst_v2", "safe_analyst_v2", "neutral_analyst_v2",  # v2.0 风险分析师
    "research_manager", "risk_manager"  # 旧版管理者
]:
    llm_type = "deep"  # 使用深度模型
    logger.info(f"[智能体创建] 🔧 {agent_id} 使用深度分析模型 (deep_think_llm)")
else:
    logger.info(f"[智能体创建] 🔧 {agent_id} 使用快速分析模型 (quick_think_llm)")
```

#### 3. 旧版 Agent 创建逻辑（第 1377-1389 行）

**修改后**：
```python
# 🔥 关键修复：根据 agent_id 判断应该使用 quick 还是 deep LLM
# 使用深度模型的 Agent：
# 1. 管理者（research_manager, risk_manager）- 需要综合大量信息做决策
# 2. 风险分析师（risky/safe/neutral_analyst）- 需要处理大量分析报告
llm_type = "quick"  # 默认使用快速模型
if agent_id in [
    "research_manager", "risk_manager",  # 管理者
    "risky_analyst", "safe_analyst", "neutral_analyst"  # 旧版风险分析师
]:
    llm_type = "deep"  # 使用深度模型
    logger.info(f"[遗留适配器] 🔧 {agent_id} 使用深度分析模型 (deep_think_llm)")
else:
    logger.info(f"[遗留适配器] 🔧 {agent_id} 使用快速分析模型 (quick_think_llm)")
```

---

## 🎯 影响范围

### 受影响的 Agent

**v2.0 风险分析师**：
- `risky_analyst_v2` - 激进风险分析师
- `safe_analyst_v2` - 保守风险分析师
- `neutral_analyst_v2` - 中性风险分析师

**旧版风险分析师**：
- `risky_analyst` - 激进风险分析师（旧版）
- `safe_analyst` - 保守风险分析师（旧版）
- `neutral_analyst` - 中性风险分析师（旧版）

### 模型分配规则

| Agent 类型 | 模型类型 | 原因 |
|-----------|---------|------|
| **管理者** | 深度模型 | 需要综合大量信息做决策 |
| `research_manager_v2` | `deep_think_llm` | 综合所有分析师报告，制定投资计划 |
| `risk_manager_v2` | `deep_think_llm` | 综合所有风险观点，形成最终风险评估 |
| **风险分析师** | 深度模型 | 需要处理大量分析报告 |
| `risky_analyst_v2` | `deep_think_llm` | 分析 10+ 个报告，从激进角度评估风险 |
| `safe_analyst_v2` | `deep_think_llm` | 分析 10+ 个报告，从保守角度评估风险 |
| `neutral_analyst_v2` | `deep_think_llm` | 分析 10+ 个报告，从中性角度评估风险 |
| **普通分析师** | 快速模型 | 只处理单一维度的数据 |
| `index_analyst_v2` | `quick_think_llm` | 只分析大盘指数数据 |
| `sector_analyst_v2` | `quick_think_llm` | 只分析行业板块数据 |
| `market_analyst_v2` | `quick_think_llm` | 只分析市场技术数据 |
| `fundamentals_analyst_v2` | `quick_think_llm` | 只分析基本面数据 |
| `news_analyst_v2` | `quick_think_llm` | 只分析新闻数据 |
| `sentiment_analyst_v2` | `quick_think_llm` | 只分析情绪数据 |

---

## 📊 预期效果

### 性能提升
- ✅ 风险分析师能够更好地处理大量分析报告
- ✅ 提高风险评估的准确性和深度
- ✅ 减少因上下文过长导致的分析质量下降

### 成本影响
- ⚠️ 风险分析师调用深度模型，成本会增加
- 💡 但风险评估是关键环节，值得使用更好的模型

---

## 🧪 测试建议

1. **运行完整分析流程**，观察日志中风险分析师使用的模型：
   ```
   [智能体创建] 🔧 risky_analyst_v2 使用深度分析模型 (deep_think_llm)
   [智能体创建] 🔧 safe_analyst_v2 使用深度分析模型 (deep_think_llm)
   [智能体创建] 🔧 neutral_analyst_v2 使用深度分析模型 (deep_think_llm)
   ```

2. **对比分析质量**：
   - 修复前：风险分析师使用快速模型（如 `qwen-turbo`）
   - 修复后：风险分析师使用深度模型（如 `qwen-max`）

3. **检查成本**：
   - 监控 LLM API 调用成本变化

---

**修复日期**: 2026-01-11  
**修复人员**: AI Assistant  
**相关文件**: `core/workflow/builder.py`

