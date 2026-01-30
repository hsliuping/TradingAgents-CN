# 提示词合规修改方案

## 📋 背景

为避免证监会监管风险，需要修改提示词中涉及"目标价格"和"操作建议"的表述，使其符合合规要求。

## 🎯 合规原则

1. **不直接给出投资建议**：避免使用"买入/卖出/持有"等直接操作指令
2. **不给出具体目标价**：避免给出明确的"目标价格"
3. **提供分析参考**：改为提供"分析观点"、"参考区间"等
4. **添加免责声明**：明确这是分析参考，不构成投资建议

## 📝 修改映射表

### 1. 目标价格相关术语

| 原表述 | 合规表述 | 说明 |
|--------|---------|------|
| `target_price` / `目标价` / `目标价位` | `price_analysis_range` / `估值区间` / `价格分析区间` | 改为区间而非具体价格 |
| `第一目标价` / `第二目标价` | `第一参考价位区间` / `第二参考价位区间` | 改为区间表述 |
| `止损价位` / `stop_loss_price` | `风险参考价位` / `风险控制参考价位` | 改为风险提示而非操作指令 |
| `止盈价位` / `take_profit_price` | `收益参考价位` / `收益预期参考价位` | 改为预期分析而非操作指令 |

### 2. 操作建议相关术语

| 原表述 | 合规表述 | 说明 |
|--------|---------|------|
| `action` / `操作建议` | `analysis_view` / `持仓分析观点` | 改为分析观点 |
| `买入/卖出/持有` | `看涨/看跌/中性` | 改为市场观点而非操作指令 |
| `加仓/减仓/清仓` | `增持观点/减持观点/观望观点` | 改为持仓观点而非操作指令 |
| `recommended_action` | `market_view` / `市场观点` | 改为市场观点 |
| `操作比例` / `action_ratio` | `仓位分析` / `position_analysis` | 改为分析而非建议 |

### 3. 字段名修改

| 原字段名 | 合规字段名 | 说明 |
|---------|-----------|------|
| `target_price` | `price_analysis_range` | 价格分析区间 |
| `stop_loss_price` | `risk_reference_price` | 风险参考价位 |
| `take_profit_price` | `profit_reference_price` | 收益参考价位 |
| `action` | `analysis_view` | 分析观点 |
| `action_ratio` | `position_analysis` | 仓位分析 |
| `recommended_action` | `market_view` | 市场观点 |

## 🔧 具体修改方案

### 方案一：操作建议师 (pa_advisor / pa_advisor_v2)

#### 修改前
```json
{
    "action": "持有|加仓|减仓|清仓",
    "action_ratio": 0-100的百分比,
    "target_price": 目标价位,
    "stop_loss_price": 止损价位,
    "take_profit_price": 止盈价位
}
```

#### 修改后
```json
{
    "analysis_view": "看涨|看跌|中性",
    "position_analysis": "当前持仓分析（如：建议关注/建议谨慎/建议观望）",
    "price_analysis_range": {
        "lower_bound": 价格区间下限,
        "upper_bound": 价格区间上限,
        "current_position": "当前价格在区间中的位置分析"
    },
    "risk_reference_price": "风险控制参考价位（仅供参考，不构成操作建议）",
    "profit_reference_price": "收益预期参考价位（仅供参考，不构成操作建议）",
    "disclaimer": "本分析仅供参考，不构成投资建议。投资有风险，决策需谨慎。"
}
```

### 方案二：交易员 (trader / trader_v2)

#### 修改前
```
请在您的分析中包含以下关键信息：
1. **投资建议**: 明确的买入/持有/卖出决策
2. **目标价位**: 基于分析的合理目标价格
```

#### 修改后
```
请在您的分析中包含以下关键信息：
1. **市场观点**: 基于分析的市场观点（看涨/看跌/中性）
2. **价格分析区间**: 基于技术面和基本面的价格分析区间（不构成目标价）
3. **风险提示**: 主要风险因素和风险控制参考价位（仅供参考）
4. **收益预期**: 基于分析的收益预期参考价位（仅供参考，不构成投资建议）

**重要提示**：
- 本分析仅供参考，不构成投资建议
- 所有价格区间均为分析参考，不构成操作目标
- 投资决策需结合个人风险承受能力，谨慎决策
```

### 方案三：研究经理 (research_manager / research_manager_v2)

#### 修改前
```json
{
    "action": "买入|持有|卖出",
    "target_price": 目标价格,
    "position_ratio": "建议持仓比例"
}
```

#### 修改后
```json
{
    "market_view": "看涨|看跌|中性",
    "price_analysis_range": {
        "valuation_range": "估值区间（基于基本面分析）",
        "technical_range": "技术分析价位区间",
        "comprehensive_range": "综合分析价位区间"
    },
    "position_analysis": "仓位分析（基于风险收益比的分析，不构成操作建议）",
    "disclaimer": "本分析仅供参考，不构成投资建议。投资有风险，决策需谨慎。"
}
```

### 方案四：风险经理 (risk_manager / risk_manager_v2)

#### 修改前
```json
{
    "final_trade_decision": {
        "action": "买入/持有/卖出",
        "target_price": 目标价格,
        "stop_loss": 止损价格
    }
}
```

#### 修改后
```json
{
    "comprehensive_analysis": {
        "market_view": "看涨|看跌|中性",
        "price_analysis_range": {
            "lower_bound": 价格区间下限,
            "upper_bound": 价格区间上限
        },
        "risk_reference_price": "风险控制参考价位（仅供参考）",
        "position_analysis": "仓位分析（不构成操作建议）"
    },
    "disclaimer": "本分析仅供参考，不构成投资建议。投资有风险，决策需谨慎。"
}
```

## 📋 需要修改的文件清单

### 1. Agent 代码文件

- [ ] `core/agents/adapters/position/action_advisor.py`
- [ ] `core/agents/adapters/position/action_advisor_v2.py`
- [ ] `core/agents/trader.py`
- [ ] `core/agents/adapters/trader_v2.py`
- [ ] `core/agents/manager.py`
- [ ] `core/agents/adapters/research_manager_v2.py`
- [ ] `core/agents/adapters/risk_manager_v2.py`

### 2. 提示词模板文件

- [ ] `scripts/init_position_analysis_templates.py`
- [ ] `scripts/update_pa_advisor_v2_template.py`
- [ ] 数据库中的 `prompt_templates` 集合

### 3. 配置文件

- [ ] `core/agents/config.py` - Agent 元数据中的描述

## 🔍 修改步骤

### 步骤 1：更新代码中的降级提示词

修改所有 Agent 类中的 `fallback_prompt`，将：
- "目标价" → "价格分析区间"
- "操作建议" → "分析观点"
- "买入/卖出/持有" → "看涨/看跌/中性"

### 步骤 2：更新数据库模板

更新 MongoDB 中 `prompt_templates` 集合的所有相关模板：
- `agent_type: "position_analysis"` 或 `"position_analysis_v2"`
- `agent_type: "trader_v2"`
- `agent_type: "research_manager_v2"`
- `agent_type: "risk_manager_v2"`

### 步骤 3：添加免责声明

在所有提示词末尾添加：
```
**免责声明**：
本分析报告仅供参考，不构成投资建议。所有价格区间、市场观点均为分析参考，
不构成买卖操作建议。投资有风险，决策需谨慎。投资者应根据自身情况，结合
专业投资顾问意见，独立做出投资决策。
```

### 步骤 4：更新输出格式

修改 JSON 输出格式，将字段名改为合规表述。

### 步骤 5：更新前端解析逻辑

修改前端代码中对这些字段的解析和显示逻辑。

## ⚠️ 注意事项

1. **保持功能完整性**：虽然表述改变，但分析功能应保持完整
2. **向后兼容**：考虑是否需要支持旧字段名的兼容处理
3. **用户提示**：在前端明确提示这是"分析参考"而非"投资建议"
4. **日志记录**：记录修改历史，便于追踪和审计

## 📊 修改优先级

### 高优先级（立即修改）
1. ✅ 操作建议师 (pa_advisor_v2) - 最直接涉及操作建议
2. ✅ 交易员 (trader_v2) - 直接涉及交易指令
3. ✅ 风险经理 (risk_manager_v2) - 涉及最终决策

### 中优先级（尽快修改）
4. ⚠️ 研究经理 (research_manager_v2) - 涉及投资计划
5. ⚠️ 基本面分析师 - 涉及目标价位建议

### 低优先级（后续修改）
6. 📝 其他分析师 Agent - 间接涉及

## 🔗 相关文档

- [证监会相关规定](https://www.csrc.gov.cn/) - 需要查阅最新监管要求
- [证券投资咨询业务管理办法](https://www.csrc.gov.cn/) - 相关法规参考

## 📝 修改检查清单

- [ ] 所有"目标价"改为"价格分析区间"
- [ ] 所有"操作建议"改为"分析观点"
- [ ] 所有"买入/卖出/持有"改为"看涨/看跌/中性"
- [ ] 添加免责声明
- [ ] 更新 JSON 字段名
- [ ] 更新前端显示逻辑
- [ ] 更新文档
- [ ] 测试验证
