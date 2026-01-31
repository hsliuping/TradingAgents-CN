# 提示词合规修改总结

## ✅ 已完成的修改

### 1. 操作建议师 v2 (action_advisor_v2.py)
- ✅ 修改降级提示词
- ✅ "操作建议" → "持仓分析观点"
- ✅ "目标价位" → "价格分析区间"
- ✅ "止损价位" → "风险控制参考价位"
- ✅ "买入/卖出/持有" → "看涨/看跌/中性"
- ✅ 添加免责声明

### 2. 操作建议师 v1 (action_advisor.py)
- ✅ 修改降级提示词
- ✅ 字段名和术语全部合规化
- ✅ 添加免责声明

### 3. 交易员 v2 (trader_v2.py)
- ✅ 修改系统提示词
- ✅ "交易指令" → "交易分析计划"
- ✅ "买入/卖出/持有" → "看涨/看跌/中性"
- ✅ "目标价格" → "价格分析区间"
- ✅ 修改用户提示词中的任务要求
- ✅ 添加免责声明

### 4. 研究经理 v2 (research_manager_v2.py)
- ✅ 修改系统提示词
- ✅ "投资决策" → "市场分析"
- ✅ "投资建议" → "市场观点"
- ✅ 修改用户提示词
- ✅ 添加免责声明

### 5. 风险经理 v2 (risk_manager_v2.py)
- ✅ 修改系统提示词
- ✅ "最终交易决策" → "综合分析"
- ✅ 修改字段显示名称
- ✅ 添加 action 字段转换逻辑（操作建议 → 市场观点）
- ✅ 修改默认值
- ✅ 添加免责声明

### 6. Manager 基类 (manager.py)
- ✅ 修改日志输出
- ✅ "投资建议" → "市场观点"
- ✅ "目标价格" → "价格分析区间"

## 📋 术语替换对照表

| 原术语 | 合规术语 | 状态 |
|--------|---------|------|
| 目标价 / target_price | 价格分析区间 / price_analysis_range | ✅ |
| 操作建议 / action | 分析观点 / analysis_view | ✅ |
| 买入/卖出/持有 | 看涨/看跌/中性 | ✅ |
| 加仓/减仓/清仓 | 增持观点/减持观点/观望观点 | ✅ |
| 止损价位 | 风险控制参考价位 | ✅ |
| 止盈价位 | 收益预期参考价位 | ✅ |
| 投资建议 | 市场观点 | ✅ |
| 交易决策 | 综合分析 | ✅ |

## 🔄 下一步：更新数据库模板

代码中的降级提示词已修改完成，但**数据库中的模板也需要更新**。

### 执行步骤：

1. **预览修改内容**：
   ```bash
   python scripts/compliance/update_prompts_for_compliance.py preview
   ```

2. **更新数据库模板**：
   ```bash
   python scripts/compliance/update_prompts_for_compliance.py
   ```

3. **验证修改**：
   - 测试各个 Agent 的输出
   - 确认字段名已更新
   - 确认免责声明已添加

## 📝 修改的文件清单

### 代码文件（已完成）
- ✅ `core/agents/adapters/position/action_advisor_v2.py`
- ✅ `core/agents/adapters/position/action_advisor.py`
- ✅ `core/agents/adapters/trader_v2.py`
- ✅ `core/agents/adapters/research_manager_v2.py`
- ✅ `core/agents/adapters/risk_manager_v2.py`
- ✅ `core/agents/manager.py`

### 数据库模板（待更新）
- ⏳ `prompt_templates` 集合中的相关模板
  - `agent_type: "position_analysis_v2"`
  - `agent_type: "position_analysis"`
  - `agent_type: "trader_v2"`
  - `agent_type: "managers_v2"` (research_manager_v2)
  - `agent_type: "risk_manager_v2"`

## ⚠️ 注意事项

1. **向后兼容**：
   - 代码中添加了 action 字段的转换逻辑
   - 如果数据库模板返回旧字段名，会自动转换

2. **前端显示**：
   - 前端可能需要更新字段解析逻辑
   - 需要显示免责声明

3. **测试验证**：
   - 测试每个 Agent 的输出格式
   - 确认字段名正确
   - 确认免责声明显示

## 🔗 相关文档

- [详细修改方案](./prompt_compliance_modification_plan.md)
- [代码修改示例](./code_modification_examples.py)
- [修改脚本](../scripts/compliance/update_prompts_for_compliance.py)
