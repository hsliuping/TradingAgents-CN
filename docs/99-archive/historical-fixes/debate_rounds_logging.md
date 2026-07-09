# 辩论轮次日志追踪

## 问题描述

用户选择了4级深度分析（应该有2轮投资辩论和2轮风险讨论），但实际执行时只进行了1轮。

## 修复内容

### 1. 核心问题修复

**文件**: `tradingagents/graph/trading_graph.py` (第262行)

**问题**: `ConditionalLogic` 初始化时没有传递配置参数

```python
# ❌ 修复前
self.conditional_logic = ConditionalLogic()  # 使用默认值 1

# ✅ 修复后
self.conditional_logic = ConditionalLogic(
    max_debate_rounds=self.config.get("max_debate_rounds", 1),
    max_risk_discuss_rounds=self.config.get("max_risk_discuss_rounds", 1)
)
```

### 2. 添加详细日志追踪

#### 2.1 条件控制日志

**文件**: `tradingagents/graph/conditional_logic.py`

**投资辩论控制** (`should_continue_debate`):
```python
logger.info(f"🔍 [投资辩论控制] 当前发言次数: {current_count}, 最大次数: {max_count} (配置轮次: {self.max_debate_rounds})")
logger.info(f"🔍 [投资辩论控制] 当前发言者: {current_speaker}")
logger.info(f"🔄 [投资辩论控制] 继续辩论 -> {next_speaker}")
logger.info(f"✅ [投资辩论控制] 达到最大次数，结束辩论 -> Research Manager")
```

**风险讨论控制** (`should_continue_risk_analysis`):
```python
logger.info(f"🔍 [风险讨论控制] 当前发言次数: {current_count}, 最大次数: {max_count} (配置轮次: {self.max_risk_discuss_rounds})")
logger.info(f"🔍 [风险讨论控制] 最后发言者: {latest_speaker}")
logger.info(f"🔄 [风险讨论控制] 继续讨论 -> {next_speaker}")
logger.info(f"✅ [风险讨论控制] 达到最大次数，结束讨论 -> Risk Judge")
```

#### 2.2 研究员发言日志

**多头研究员** (`tradingagents/agents/researchers/bull_researcher.py`):
```python
logger.info(f"🐂 [多头研究员] 发言完成，计数: {old_count} -> {new_count}")
```

**空头研究员** (`tradingagents/agents/researchers/bear_researcher.py`):
```python
logger.info(f"🐻 [空头研究员] 发言完成，计数: {old_count} -> {new_count}")
```

#### 2.3 风险分析师发言日志

**激进风险分析师** (`tradingagents/agents/risk_mgmt/aggresive_debator.py`):
```python
logger.info(f"🔥 [激进风险分析师] 发言完成，计数: {old_count} -> {new_count}")
```

**保守风险分析师** (`tradingagents/agents/risk_mgmt/conservative_debator.py`):
```python
logger.info(f"🛡️ [保守风险分析师] 发言完成，计数: {old_count} -> {new_count}")
```

**中性风险分析师** (`tradingagents/agents/risk_mgmt/neutral_debator.py`):
```python
logger.info(f"⚖️ [中性风险分析师] 发言完成，计数: {old_count} -> {new_count}")
```

## 如何分析日志

### 1. 查看配置是否正确传递

搜索日志中的配置信息：
```powershell
Get-Content logs/tradingagents.log | Select-String "ConditionalLogic.*初始化|辩论轮次|风险讨论轮次"
```

期望看到：
```
🔧 [ConditionalLogic] 初始化完成:
   - max_debate_rounds: 2
   - max_risk_discuss_rounds: 2
```

### 2. 追踪投资辩论流程

搜索投资辩论相关日志：
```powershell
Get-Content logs/tradingagents.log | Select-String "投资辩论控制|多头研究员|空头研究员"
```

**4级深度分析的期望流程**（2轮 = 4次发言）：
```
🐂 [多头研究员] 发言完成，计数: 0 -> 1
🔍 [投资辩论控制] 当前发言次数: 1, 最大次数: 4 (配置轮次: 2)
🔄 [投资辩论控制] 继续辩论 -> Bear Researcher

🐻 [空头研究员] 发言完成，计数: 1 -> 2
🔍 [投资辩论控制] 当前发言次数: 2, 最大次数: 4 (配置轮次: 2)
🔄 [投资辩论控制] 继续辩论 -> Bull Researcher

🐂 [多头研究员] 发言完成，计数: 2 -> 3
🔍 [投资辩论控制] 当前发言次数: 3, 最大次数: 4 (配置轮次: 2)
🔄 [投资辩论控制] 继续辩论 -> Bear Researcher

🐻 [空头研究员] 发言完成，计数: 3 -> 4
🔍 [投资辩论控制] 当前发言次数: 4, 最大次数: 4 (配置轮次: 2)
✅ [投资辩论控制] 达到最大次数，结束辩论 -> Research Manager
```

### 3. 追踪风险讨论流程

搜索风险讨论相关日志：
```powershell
Get-Content logs/tradingagents.log | Select-String "风险讨论控制|激进风险|保守风险|中性风险"
```

**4级深度分析的期望流程**（2轮 = 6次发言）：
```
🔥 [激进风险分析师] 发言完成，计数: 0 -> 1
🔍 [风险讨论控制] 当前发言次数: 1, 最大次数: 6 (配置轮次: 2)
🔄 [风险讨论控制] 继续讨论 -> Safe Analyst

🛡️ [保守风险分析师] 发言完成，计数: 1 -> 2
🔍 [风险讨论控制] 当前发言次数: 2, 最大次数: 6 (配置轮次: 2)
🔄 [风险讨论控制] 继续讨论 -> Neutral Analyst

⚖️ [中性风险分析师] 发言完成，计数: 2 -> 3
🔍 [风险讨论控制] 当前发言次数: 3, 最大次数: 6 (配置轮次: 2)
🔄 [风险讨论控制] 继续讨论 -> Risky Analyst

🔥 [激进风险分析师] 发言完成，计数: 3 -> 4
🔍 [风险讨论控制] 当前发言次数: 4, 最大次数: 6 (配置轮次: 2)
🔄 [风险讨论控制] 继续讨论 -> Safe Analyst

🛡️ [保守风险分析师] 发言完成，计数: 4 -> 5
🔍 [风险讨论控制] 当前发言次数: 5, 最大次数: 6 (配置轮次: 2)
🔄 [风险讨论控制] 继续讨论 -> Neutral Analyst

⚖️ [中性风险分析师] 发言完成，计数: 5 -> 6
🔍 [风险讨论控制] 当前发言次数: 6, 最大次数: 6 (配置轮次: 2)
✅ [风险讨论控制] 达到最大次数，结束讨论 -> Risk Judge
```

## 常见问题诊断

### 问题1: 配置显示正确但只执行1轮

**可能原因**:
1. `ConditionalLogic` 没有接收到配置参数（已修复）
2. 图结构中的条件判断逻辑有误

**诊断方法**:
查看 `ConditionalLogic` 初始化日志，确认 `max_debate_rounds` 和 `max_risk_discuss_rounds` 的值

### 问题2: 计数器没有递增

**可能原因**:
1. 研究员/分析师没有正确更新 `count` 字段
2. 状态没有正确传递

**诊断方法**:
查看每个研究员/分析师的发言日志，确认计数是否递增

### 问题3: 提前结束辩论

**可能原因**:
1. 条件判断逻辑错误（`>=` vs `>`）
2. `max_count` 计算错误

**诊断方法**:
查看条件控制日志，对比 `current_count` 和 `max_count`

## 测试验证

运行测试验证修复：
```bash
# 测试配置传递
pytest tests/test_conditional_logic_config.py -v

# 测试辩论流程
pytest tests/test_debate_flow_simulation.py -v

# 测试研究深度映射
pytest tests/test_research_depth_mapping.py -v
```

## 总结

通过添加详细的日志追踪，我们可以：
1. ✅ 确认配置是否正确传递到 `ConditionalLogic`
2. ✅ 追踪每次发言的计数变化
3. ✅ 验证条件判断逻辑是否正确
4. ✅ 快速定位辩论提前结束的原因

现在重新运行4级深度分析，日志会清晰显示整个辩论流程！

