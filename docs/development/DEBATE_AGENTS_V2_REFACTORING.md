# 辩论 Agents v2.0 改造总结

## 📋 改造目标

将风险辩论相关的 4 个 Agent 改造为支持多轮辩论和缓存系统：

1. **RiskyAnalystV2** - 激进风险分析师
2. **SafeAnalystV2** - 保守风险分析师
3. **NeutralAnalystV2** - 中性风险分析师
4. **RiskManagerV2** - 风险管理者（主持人）

---

## ✅ 已完成的改造

### 1. RiskyAnalystV2（激进风险分析师）

**文件**: `core/agents/adapters/risky_analyst_v2.py`

**改造内容**:
- ✅ 添加了 `history_field = "risky_history"`
- ✅ 添加了 `opponent_history_fields = ["safe_history", "neutral_history"]`
- ✅ 修改了 `_build_user_prompt` 方法：
  - 从 `risk_debate_state` 中提取辩论历史
  - 添加了 `history`, `current_safe_response`, `current_neutral_response` 到模板变量
  - 更新了 fallback_prompt 以匹配旧版实现
- ✅ 修改了 `execute` 方法：
  - 获取辩论状态
  - 格式化论点为 `"Risky Analyst: {opinion}"`
  - 更新辩论状态（history, risky_history, count, latest_speaker）
  - 返回 `risky_opinion` 和 `risk_debate_state`

### 2. SafeAnalystV2（保守风险分析师）

**文件**: `core/agents/adapters/safe_analyst_v2.py`

**改造内容**:
- ✅ 添加了 `history_field = "safe_history"`
- ✅ 添加了 `opponent_history_fields = ["risky_history", "neutral_history"]`
- ✅ 修改了 `_build_user_prompt` 方法：
  - 从 `risk_debate_state` 中提取辩论历史
  - 添加了 `history`, `current_risky_response`, `current_neutral_response` 到模板变量
  - 更新了 fallback_prompt 以匹配旧版实现
- ✅ 修改了 `execute` 方法：
  - 获取辩论状态
  - 格式化论点为 `"Safe Analyst: {opinion}"`
  - 更新辩论状态（history, safe_history, count, latest_speaker）
  - 返回 `safe_opinion` 和 `risk_debate_state`

### 3. NeutralAnalystV2（中性风险分析师）

**文件**: `core/agents/adapters/neutral_analyst_v2.py`

**改造内容**:
- ✅ 添加了 `history_field = "neutral_history"`
- ✅ 添加了 `opponent_history_fields = ["risky_history", "safe_history"]`
- ✅ 修改了 `_build_user_prompt` 方法：
  - 从 `risk_debate_state` 中提取辩论历史
  - 添加了 `history`, `current_risky_response`, `current_safe_response` 到模板变量
  - 更新了 fallback_prompt 以匹配旧版实现
- ✅ 修改了 `execute` 方法：
  - 获取辩论状态
  - 格式化论点为 `"Neutral Analyst: {opinion}"`
  - 更新辩论状态（history, neutral_history, count, latest_speaker）
  - 返回 `neutral_opinion` 和 `risk_debate_state`

### 4. RiskManagerV2（风险管理者）

**文件**: `core/agents/adapters/risk_manager_v2.py`

**改造内容**:
- ✅ 已经正确实现（无需修改）
- ✅ `execute` 方法调用父类方法并添加 `risk_debate_state` 输出
- ✅ 包含 `judge_decision` 字段
- ✅ 包含 `final_trade_decision` 字段

---

## 🔑 关键改造点

### 1. 辩论状态结构

```python
risk_debate_state = {
    "history": "",                    # 完整辩论历史
    "risky_history": "",              # 激进分析师历史
    "safe_history": "",               # 保守分析师历史
    "neutral_history": "",            # 中性分析师历史
    "latest_speaker": "Risky",        # 最后发言者
    "current_risky_response": "",     # 当前激进观点
    "current_safe_response": "",      # 当前保守观点
    "current_neutral_response": "",   # 当前中性观点
    "count": 0,                       # 辩论轮数
    "judge_decision": ""              # 主持人决策（仅 RiskManager 输出）
}
```

### 2. 论点格式化

每个 Agent 的论点都格式化为：
```python
argument = f"{AgentName}: {opinion}"
```

例如：
- `"Risky Analyst: 我认为应该激进操作..."`
- `"Safe Analyst: 我认为应该保守操作..."`
- `"Neutral Analyst: 我认为应该平衡操作..."`

### 3. 辩论历史更新

每个 Agent 在 execute 方法中都会：
1. 获取当前辩论状态
2. 格式化自己的论点
3. 更新 `history`（追加自己的论点）
4. 更新自己的 `{role}_history`（追加自己的论点）
5. 更新 `latest_speaker`
6. 更新 `count`（递增）
7. 返回更新后的 `risk_debate_state`

---

## 📝 下一步工作

1. **测试辩论流程**:
   - 测试单轮辩论
   - 测试多轮辩论
   - 验证辩论状态传递

2. **集成缓存系统**:
   - 在工作流中添加缓存检查
   - 避免重复分析

3. **优化提示词模板**:
   - 确保模板系统中有正确的辩论提示词
   - 测试 fallback_prompt 的效果

---

**最后更新**: 2026-01-15  
**改造状态**: ✅ 完成

