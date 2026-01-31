# 合规术语修改清单

## 📋 完整术语替换对照表

### 1. 目标价格相关

| 原术语 | 合规术语 | 使用场景 |
|--------|---------|---------|
| 目标价 / 目标价位 | 价格分析区间 | 所有 Agent |
| target_price | price_analysis_range | JSON 字段名 |
| 第一目标价 / 第二目标价 | 第一参考价位区间 / 第二参考价位区间 | 操作建议师 |
| 止损价位 | 风险控制参考价位 | 所有 Agent |
| stop_loss_price | risk_reference_price | JSON 字段名 |
| 止盈价位 | 收益预期参考价位 | 所有 Agent |
| take_profit_price | profit_reference_price | JSON 字段名 |

### 2. 操作建议相关

| 原术语 | 合规术语 | 使用场景 |
|--------|---------|---------|
| 操作建议 | 持仓分析观点 / 分析观点 | 操作建议师 |
| action | analysis_view | JSON 字段名 |
| 买入 / 卖出 / 持有 | 看涨 / 看跌 / 中性 | 所有 Agent |
| 加仓 / 减仓 / 清仓 | 增持观点 / 减持观点 / 观望观点 | 操作建议师 |
| recommended_action | market_view | JSON 字段名 |
| 操作比例 | 仓位分析 | 操作建议师 |
| action_ratio | position_analysis | JSON 字段名 |

### 3. 交易相关术语（新增）

| 原术语 | 合规术语 | 使用场景 |
|--------|---------|---------|
| 交易方向 | 市场观点 / 分析方向 | 交易员 |
| 交易指令 | 交易分析 / 执行分析 | 交易员 |
| 交易计划 | 交易分析计划 / 执行分析计划 | 交易员 |
| trading_direction | market_view / analysis_direction | JSON 字段名 |
| trading_instruction | trading_analysis / execution_analysis | JSON 字段名 |
| trading_plan | trading_analysis_plan | JSON 字段名 |
| 生成具体的交易计划 | 生成交易分析计划 | 提示词 |
| 生成具体的交易指令 | 生成交易分析 | 提示词 |
| 确定交易方向 | 分析市场观点 | 提示词 |

## 🔧 已修改的文件

### 代码文件

1. ✅ `core/agents/adapters/position/action_advisor_v2.py`
   - "操作建议" → "持仓分析观点"
   - "目标价位" → "价格分析区间"
   - "止损价位" → "风险控制参考价位"

2. ✅ `core/agents/adapters/position/action_advisor.py`
   - "操作建议" → "持仓分析观点"
   - "目标价位" → "价格分析区间"

3. ✅ `core/agents/adapters/trader_v2.py`
   - "交易指令" → "交易分析"
   - "交易计划" → "交易分析计划"
   - "交易方向" → "市场观点"
   - "生成具体的交易计划" → "生成交易分析计划"

4. ✅ `core/agents/trader.py`
   - "交易指令" → "交易分析计划"
   - "生成具体交易指令" → "生成交易分析计划"

5. ✅ `core/agents/adapters/research_manager_v2.py`
   - "投资建议" → "市场观点"
   - "投资决策" → "市场分析"

6. ✅ `core/agents/adapters/risk_manager_v2.py`
   - "投资建议" → "市场观点"
   - "目标价格" → "价格分析区间"
   - "止损价格" → "风险控制参考价位"

### 脚本文件

7. ✅ `scripts/compliance/update_prompts_for_compliance.py`
   - 添加了交易相关术语的替换规则

### 文档文件

8. ✅ `docs/compliance/prompt_compliance_modification_plan.md`
   - 添加了交易相关术语的映射表

## 📝 需要更新的数据库模板

以下 Agent 类型的模板需要更新：

- `position_analysis` - 操作建议师 v1
- `position_analysis_v2` - 操作建议师 v2.0
- `trader_v2` - 交易员 v2.0
- `managers_v2` - 研究经理和风险经理 v2.0

## ✅ 检查清单

- [x] 代码中的降级提示词已修改
- [x] 术语替换映射表已更新
- [x] 交易相关术语已添加
- [ ] 数据库模板已更新（需要运行脚本）
- [ ] 前端显示逻辑已更新（如需要）
- [ ] 测试验证通过
