# 包含目标价和操作建议的 Agent 列表

本文档列出了系统中所有生成目标价和操作建议的 Agent。

## 📋 目录

1. [操作建议师 (Action Advisor)](#操作建议师-action-advisor)
2. [交易员 (Trader)](#交易员-trader)
3. [研究经理 (Research Manager)](#研究经理-research-manager)
4. [风险经理 (Risk Manager)](#风险经理-risk-manager)
5. [基本面分析师 (Fundamentals Analyst)](#基本面分析师-fundamentals-analyst)

---

## 操作建议师 (Action Advisor)

### Agent ID
- `pa_advisor` - 操作建议师 v1
- `pa_advisor_v2` - 操作建议师 v2.0

### 功能描述
综合技术面、基本面、风险评估，给出持仓操作建议。

### 输出字段
- `action_advice` - 操作建议

### 输出格式
```json
{
    "action": "持有|加仓|减仓|清仓",
    "action_ratio": 0-100的百分比,
    "target_price": 目标价位,
    "stop_loss_price": 止损价位,
    "take_profit_price": 止盈价位,
    "confidence": 0-100的信心度,
    "risk_level": "低|中|高",
    "summary": "综合评价",
    "reasoning": "操作依据",
    "risk_assessment": "详细风险评估（300-500字）",
    "opportunity_assessment": "详细机会评估（300-500字）",
    "detailed_analysis": "详细分析（200字以内）"
}
```

### 关键提示词内容
- ✅ **目标价位** (`target_price`)
- ✅ **止损价位** (`stop_loss_price`)
- ✅ **止盈价位** (`take_profit_price`)
- ✅ **操作建议** (`action`: 持有/加仓/减仓/清仓)
- ✅ **操作比例** (`action_ratio`)

### 相关文件
- `core/agents/adapters/position/action_advisor.py` - v1 实现
- `core/agents/adapters/position/action_advisor_v2.py` - v2.0 实现
- `scripts/init_position_analysis_templates.py` - 模板初始化

---

## 交易员 (Trader)

### Agent ID
- `trader` - 交易员 v1
- `trader_v2` - 交易员 v2.0

### 功能描述
基于投资计划生成具体的交易指令，包含目标价格和操作建议。

### 输出字段
- `trading_plan` - 交易计划

### 输出格式
交易计划中包含：
- ✅ **目标价格** (`target_price`) - 参考投资计划中的 target_price
- ✅ **买入价/卖出价** - 具体操作价格
- ✅ **操作建议** - 买入/持有/卖出
- ✅ **仓位比例** (`position_ratio`)

### 关键提示词内容
```
请在您的分析中包含以下关键信息：
1. **投资建议**: 明确的买入/持有/卖出决策
2. **目标价位**: 基于分析的合理目标价格 - 🚨 强制要求提供具体数值
   - 买入建议：提供目标价位和预期涨幅
   - 持有建议：提供合理价格区间（如：¥XX-XX）
   - 卖出建议：提供止损价位和目标卖出价
3. **置信度**: 对决策的信心程度(0-1之间)
4. **风险评分**: 投资风险等级(0-1之间)
5. **详细推理**: 支持决策的具体理由
```

### 相关文件
- `core/agents/trader.py` - TraderAgent 基类
- `core/agents/adapters/trader_v2.py` - v2.0 实现

---

## 研究经理 (Research Manager)

### Agent ID
- `research_manager` - 研究经理 v1
- `research_manager_v2` - 研究经理 v2.0

### 功能描述
综合看涨和看跌观点，做出投资决策，生成投资计划。

### 输出字段
- `investment_plan` - 投资计划

### 输出格式
```json
{
    "action": "买入|持有|卖出",
    "confidence": 0-100的整数（信心度，必需字段）,
    "target_price": 目标价格（数字，可选）,
    "risk_score": 0-1的风险评分（可选）,
    "reasoning": "详细的决策理由和分析依据（200-500字，必需字段）",
    "summary": "投资计划摘要（可选）",
    "risk_warning": "风险提示（可选）",
    "position_ratio": "建议持仓比例（可选）"
}
```

### 关键提示词内容
- ✅ **目标价格** (`target_price`)
- ✅ **投资建议** (`action`: 买入/持有/卖出)
- ✅ **信心度** (`confidence`)
- ✅ **建议持仓比例** (`position_ratio`)

### 相关文件
- `core/agents/manager.py` - ManagerAgent 基类
- `core/agents/adapters/research_manager_v2.py` - v2.0 实现

---

## 风险经理 (Risk Manager)

### Agent ID
- `risk_manager` - 风险经理 v1
- `risk_manager_v2` - 风险经理 v2.0

### 功能描述
综合各方风险观点，生成最终交易决策，包含目标价和操作建议。

### 输出字段
- `risk_assessment` - 风险评估
- `final_trade_decision` - 最终交易决策

### 输出格式
```json
{
    "risk_level": "低/中/高",
    "risk_score": 0.0-1.0之间的数字,
    "reasoning": "详细的风险评估理由（200-500字）",
    "key_risks": ["风险1", "风险2", "风险3"],
    "risk_control": "风险控制措施建议",
    "investment_adjustment": "对投资计划的调整建议",
    "final_trade_decision": {
        "action": "买入/持有/卖出",
        "confidence": 0-100之间的整数,
        "target_price": 目标价格（数字）,
        "stop_loss": 止损价格（数字）,
        "position_ratio": "建议仓位比例（如5%、10%）",
        "reasoning": "最终交易决策的综合推理（300-600字）",
        "summary": "一句话总结（50字以内）",
        "risk_warning": "关键风险提示（100字以内）"
    }
}
```

### 关键提示词内容
- ✅ **目标价格** (`final_trade_decision.target_price`)
- ✅ **止损价格** (`final_trade_decision.stop_loss`)
- ✅ **操作建议** (`final_trade_decision.action`: 买入/持有/卖出)
- ✅ **仓位比例** (`final_trade_decision.position_ratio`)

### 相关文件
- `core/agents/manager.py` - ManagerAgent 基类
- `core/agents/adapters/risk_manager_v2.py` - v2.0 实现

---

## 基本面分析师 (Fundamentals Analyst)

### Agent ID
- `fundamentals_analyst` - 基本面分析师 v1
- `fundamentals_analyst_v2` - 基本面分析师 v2.0

### 功能描述
进行基本面分析，可能包含目标价位建议。

### 输出字段
- `fundamentals_report` - 基本面分析报告

### 关键提示词内容
```
📊 分析要求：
- 基于真实数据进行深度基本面分析
- 计算并提供合理价位区间（使用{currency_name}{currency_symbol}）
- 分析当前股价是否被低估或高估
- 提供基于基本面的目标价位建议
- 包含PE、PB、PEG等估值指标分析
- 结合市场特点进行分析

必须生成完整的基本面分析报告，包含：
- 公司基本信息和财务数据分析
- PE、PB、PEG等估值指标分析
- 当前股价是否被低估或高估的判断
- 合理价位区间和目标价位建议
- 基于基本面的投资建议（买入/持有/卖出）
```

### 相关文件
- `core/agents/analyst.py` - AnalystAgent 基类
- `core/agents/adapters/fundamental_analyst_v2.py` - v2.0 实现

---

## 📊 总结表格

| Agent ID | Agent 名称 | 目标价 | 操作建议 | 止损价 | 输出字段 |
|---------|-----------|--------|---------|--------|---------|
| `pa_advisor` | 操作建议师 | ✅ | ✅ (持有/加仓/减仓/清仓) | ✅ | `action_advice` |
| `pa_advisor_v2` | 操作建议师 v2.0 | ✅ | ✅ (持有/加仓/减仓/清仓) | ✅ | `action_advice` |
| `trader` | 交易员 | ✅ | ✅ (买入/持有/卖出) | ✅ | `trading_plan` |
| `trader_v2` | 交易员 v2.0 | ✅ | ✅ (买入/持有/卖出) | ✅ | `trading_plan` |
| `research_manager` | 研究经理 | ✅ | ✅ (买入/持有/卖出) | ❌ | `investment_plan` |
| `research_manager_v2` | 研究经理 v2.0 | ✅ | ✅ (买入/持有/卖出) | ❌ | `investment_plan` |
| `risk_manager` | 风险经理 | ✅ | ✅ (买入/持有/卖出) | ✅ | `final_trade_decision` |
| `risk_manager_v2` | 风险经理 v2.0 | ✅ | ✅ (买入/持有/卖出) | ✅ | `final_trade_decision` |
| `fundamentals_analyst` | 基本面分析师 | ✅ (目标价位建议) | ✅ (买入/持有/卖出) | ❌ | `fundamentals_report` |
| `fundamentals_analyst_v2` | 基本面分析师 v2.0 | ✅ (目标价位建议) | ✅ (买入/持有/卖出) | ❌ | `fundamentals_report` |

---

## 🔍 查找提示词模板

### 在数据库中查找
```javascript
// MongoDB 查询
db.prompt_templates.find({
    $or: [
        { "content.system_prompt": /目标价/ },
        { "content.system_prompt": /target_price/ },
        { "content.analysis_requirements": /目标价/ },
        { "content.output_format": /target_price/ }
    ]
})
```

### 在代码中查找
```bash
# 搜索包含目标价的提示词
grep -r "目标价\|target_price" --include="*.py" core/agents/

# 搜索包含操作建议的提示词
grep -r "操作建议\|action.*advice\|investment.*recommendation" --include="*.py" core/agents/
```

---

## 📝 注意事项

1. **操作建议格式**：
   - 持仓分析场景：`持有/加仓/减仓/清仓`
   - 投资决策场景：`买入/持有/卖出`

2. **目标价字段名**：
   - 大多数 Agent 使用 `target_price`
   - 操作建议师可能使用 `target_price`、`第一目标价`、`第二目标价`

3. **提示词来源**：
   - 优先从数据库模板系统读取 (`prompt_templates` 集合)
   - 如果模板不存在，使用代码中的降级提示词 (`fallback_prompt`)

4. **版本差异**：
   - v1 Agent 使用旧版提示词格式
   - v2.0 Agent 使用新版提示词格式，支持更多字段

---

## 相关文档

- [Agent 系统设计文档](../design/v2.0/agents/02-agent-layer-design.md)
- [提示词模板系统](../design/v1.0.1/AGENT_TEMPLATE_SPECIFICATIONS.md)
- [持仓分析系统](../design/v2.0/portfolio-trade-review-engine-integration.md)
