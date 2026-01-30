# 提示词合规修改总结

## 📋 修改目标

为避免证监会监管风险，需要将所有提示词中的：
- ❌ "目标价" / "目标价位" → ✅ "价格分析区间"
- ❌ "操作建议" / "买入/卖出/持有" → ✅ "分析观点" / "看涨/看跌/中性"
- ❌ "止损价位" / "止盈价位" → ✅ "风险控制参考价位" / "收益预期参考价位"

## 🎯 需要修改的 Agent

### 高优先级（立即修改）

1. **操作建议师 (pa_advisor_v2)**
   - 文件：`core/agents/adapters/position/action_advisor_v2.py`
   - 数据库模板：`agent_type: "position_analysis_v2"`

2. **交易员 (trader_v2)**
   - 文件：`core/agents/adapters/trader_v2.py`
   - 数据库模板：`agent_type: "trader_v2"`

3. **风险经理 (risk_manager_v2)**
   - 文件：`core/agents/adapters/risk_manager_v2.py`
   - 数据库模板：`agent_type: "risk_manager_v2"`

### 中优先级（尽快修改）

4. **研究经理 (research_manager_v2)**
   - 文件：`core/agents/adapters/research_manager_v2.py`
   - 数据库模板：`agent_type: "research_manager_v2"`

5. **操作建议师 v1 (pa_advisor)**
   - 文件：`core/agents/adapters/position/action_advisor.py`
   - 数据库模板：`agent_type: "position_analysis"`

## 📝 修改步骤

### 步骤 1：预览修改内容

```bash
cd scripts/compliance
python update_prompts_for_compliance.py preview
```

### 步骤 2：更新数据库模板

```bash
python update_prompts_for_compliance.py
```

### 步骤 3：修改代码中的降级提示词

参考 `docs/compliance/code_modification_examples.py` 中的示例，修改以下文件：

1. `core/agents/adapters/position/action_advisor_v2.py`
2. `core/agents/adapters/trader_v2.py`
3. `core/agents/adapters/risk_manager_v2.py`
4. `core/agents/adapters/research_manager_v2.py`
5. `core/agents/adapters/position/action_advisor.py`

### 步骤 4：更新前端解析逻辑

修改前端代码中对这些字段的解析和显示：
- `frontend/src/views/Analysis/SingleAnalysis.vue`
- `frontend/src/views/Reports/ReportDetail.vue`

### 步骤 5：测试验证

1. 测试每个 Agent 的输出格式
2. 验证前端显示是否正确
3. 确认免责声明已添加

## 🔍 术语替换对照表

| 原术语 | 合规术语 | 使用场景 |
|--------|---------|---------|
| 目标价 / target_price | 价格分析区间 / price_analysis_range | 所有 Agent |
| 操作建议 / action | 分析观点 / analysis_view | 操作建议师 |
| 买入/卖出/持有 | 看涨/看跌/中性 | 所有 Agent |
| 加仓/减仓/清仓 | 增持观点/减持观点/观望观点 | 操作建议师 |
| 止损价位 | 风险控制参考价位 | 所有 Agent |
| 止盈价位 | 收益预期参考价位 | 所有 Agent |

## ⚠️ 注意事项

1. **保持功能完整性**：虽然表述改变，但分析功能应保持完整
2. **向后兼容**：考虑是否需要支持旧字段名的兼容处理
3. **用户提示**：在前端明确提示这是"分析参考"而非"投资建议"
4. **日志记录**：记录修改历史，便于追踪和审计

## 📚 相关文档

- [详细修改方案](./prompt_compliance_modification_plan.md)
- [代码修改示例](./code_modification_examples.py)
- [修改脚本](../scripts/compliance/update_prompts_for_compliance.py)

## ✅ 检查清单

- [ ] 数据库模板已更新
- [ ] 代码中的降级提示词已更新
- [ ] 前端解析逻辑已更新
- [ ] 免责声明已添加
- [ ] 测试验证通过
- [ ] 文档已更新
