# Agent 输出格式历史说明

> ⚠️ **重要说明**：本文档主要说明系统早期版本（v1）Agent 的输出格式。当前 v3.0 已全面转向研究辅助定位：v2 系列 Agent 不再输出目标价、买入/卖出/加仓/减仓/清仓等交易指令，统一使用"乐观 / 审慎 / 中性"表达研究结论倾向。以下内容中涉及 v1 的部分仅作历史参考，实际生产环境请以 v2/v3 的研究简报和风险审阅输出为准。

## 📋 目录

1. [持仓研究观察 (Action Advisor)](#持仓研究观察-action-advisor)
2. [研究整合员 (Research Integrator)](#研究整合员-research-integrator)
3. [研究经理 (Research Manager)](#研究经理-research-manager)
4. [风险评估师 (Risk Assessor)](#风险评估师-risk-assessor)
5. [基本面分析师 (Fundamentals Analyst)](#基本面分析师-fundamentals-analyst)

---

## 持仓研究观察 (Action Advisor)

### Agent ID
- `pa_advisor` - 操作建议师 v1（旧版，已封堵入口）
- `pa_advisor_v2` - 持仓研究观察 v2.0

### 功能描述
综合技术面、基本面、风险审阅，为持仓股票生成研究观察与风险跟踪参考，不给出具体操作指令。

### 输出字段
- `action_advice` - 持仓研究观察

### 输出格式（v2 研究取向）
```json
{
    "action": "乐观|审慎|中性",
    "confidence": 0-1的信心度,
    "price_analysis_range": "观察区间或验证区间",
    "stop_loss_price": "风险关注价格",
    "take_profit_price": "收益关注价格",
    "risk_level": "低|中|高",
    "summary": "研究观察摘要",
    "reasoning": "研究依据",
    "risk_assessment": "详细风险审阅（300-500字）",
    "key_evidence": ["核心证据清单"],
    "watch_items": ["后续观察事项"]
}
```

### 关键提示词内容（v2）
- ✅ **研究结论倾向** (`action`: 乐观/审慎/中性)
- ✅ **观察区间** (`price_analysis_range`)
- ✅ **风险关注价格** (`stop_loss_price`)
- ✅ **收益关注价格** (`take_profit_price`)
- ✅ **后续观察事项** (`watch_items`)

### 相关文件
- `core/agents/adapters/position/action_advisor.py` - v1 实现
- `core/agents/adapters/position/action_advisor_v2.py` - v2.0 实现
- `scripts/init_position_analysis_templates.py` - 模板初始化

---

## 研究整合员 (Trader)

### Agent ID
- `trader` - 研究整合员 v1（旧版，已封堵入口）
- `trader_v2` - 研究整合员 v2.0

### 功能描述
基于多方研究证据生成用户版研究简报，输出研究观察而非交易指令。

### 输出字段
- `trading_plan` / `investment_plan` - 研究简报

### 输出格式（v2）
研究简报中包含：
- ✅ **研究结论倾向** - 乐观 / 审慎 / 中性
- ✅ **核心研究证据** - 支撑判断的关键事实与数据
- ✅ **关键风险** - 可能推翻判断的失效条件
- ✅ **后续观察事项** - 需要跟踪的验证信号
- ✅ **免责声明** - 明确说明仅供学习研究参考

### 关键提示词内容（v2）
```
请在您的分析中包含以下关键信息：
1. **一句话结论**: 使用"乐观/审慎/中性"表达研究结论倾向
2. **核心依据**: 基于证据的研究推理，禁止目标价、买入/卖出等交易指令
3. **关键风险**: 可能推翻当前判断的失效条件
4. **后续观察**: 需要持续跟踪的验证事项
5. **免责声明**: 明确说明本分析不构成投资建议
```

### 相关文件
- `core/agents/trader.py` - TraderAgent 基类
- `core/agents/adapters/trader_v2.py` - v2.0 实现

---

## 研究经理 (Research Manager)

### Agent ID
- `research_manager` - 研究经理 v1（旧版，已封堵入口）
- `research_manager_v2` - 研究经理 v2.0

### 功能描述
综合乐观情景和审慎情景研究观点，形成研究判断，生成研究观察汇总。

### 输出字段
- `investment_plan` - 研究观察汇总

### 输出格式（v2）
```json
{
    "analysis_view": "乐观|审慎|中性",
    "confidence": 0-1的浮点数（信心度，必需字段）,
    "risk_score": 0-1的风险评分（可选）,
    "reasoning": "详细的研究推理和分析依据（200-500字，必需字段）",
    "summary": "研究观察摘要（可选）",
    "risk_warning": "风险提示（可选）",
    "core_evidence": ["核心证据清单"],
    "info_gaps": ["信息缺口"]
}
```

### 关键提示词内容（v2）
- ✅ **研究结论倾向** (`analysis_view`: 乐观/审慎/中性)
- ✅ **信心度** (`confidence`)
- ✅ **核心证据** (`core_evidence`)
- ✅ **信息缺口** (`info_gaps`)

### 相关文件
- `core/agents/manager.py` - ManagerAgent 基类
- `core/agents/adapters/research_manager_v2.py` - v2.0 实现

---

## 风险评估师 (Risk Manager)

### Agent ID
- `risk_manager` - 风险经理 v1（旧版，已封堵入口）
- `risk_manager_v2` - 风险评估师 v2.0

### 功能描述
综合各方稳健性审阅意见，生成风险审阅结论，输出研究结论倾向与风险观察。

### 输出字段
- `risk_assessment` - 风险审阅
- `final_trade_decision` - 综合研究结论

### 输出格式（v2）
```json
{
    "risk_level": "低/中/高",
    "risk_score": 0.0-1.0之间的数字,
    "reasoning": "详细的风险审阅理由（200-500字）",
    "key_risks": ["风险1", "风险2", "风险3"],
    "risk_control": "风险审阅与后续观察要求",
    "investment_adjustment": "乐观/审慎/中性（研究结论倾向）",
    "final_trade_decision": {
        "analysis_view": "乐观/审慎/中性",
        "confidence": 0-1之间的浮点数,
        "price_analysis_range": "观察区间或验证区间（可为空）",
        "risk_reference_price": "关键失效位或验证位（可为空）",
        "risk_exposure_ratio": "风险承受前提或跟踪要求（不能写仓位建议）",
        "reasoning": "综合研究结论的推理（300-600字）",
        "summary": "一句话总结（50字以内）",
        "risk_warning": "关键风险提示（100字以内）"
    }
}
```

### 关键提示词内容（v2）
- ✅ **研究结论倾向** (`final_trade_decision.analysis_view`: 乐观/审慎/中性)
- ✅ **关键失效位** (`final_trade_decision.risk_reference_price`)
- ✅ **观察区间** (`final_trade_decision.price_analysis_range`)
- ✅ **风险承受前提** (`final_trade_decision.risk_exposure_ratio`)

### 相关文件
- `core/agents/manager.py` - ManagerAgent 基类
- `core/agents/adapters/risk_manager_v2.py` - v2.0 实现

---

## 基本面分析师 (Fundamentals Analyst)

### Agent ID
- `fundamentals_analyst` - 基本面分析师 v1（旧版，已封堵入口）
- `fundamentals_analyst_v2` - 基本面分析师 v2.0

### 功能描述
进行基本面分析，输出事实性研究和估值观察，不提供目标价位或操作建议。

### 输出字段
- `fundamentals_report` - 基本面研究报告

### 关键提示词内容（v2）
```
📊 分析要求：
- 基于真实数据进行深度基本面分析
- 引用真实估值指标（PE、PB、PEG、ROE、ROA 等）说明事实
- 分析当前估值水平和基本面趋势
- 不得输出目标价位、合理价位区间、买入/卖出/持有等交易指令
- 只输出研究观察，使用"乐观/审慎/中性"表达研究结论倾向

必须生成完整的基本面研究报告，包含：
- 公司基本信息和财务数据分析
- PE、PB、PEG等估值指标分析
- 基本面趋势判断
- 关键风险与信息缺口
- 后续观察事项
```

### 相关文件
- `core/agents/analyst.py` - AnalystAgent 基类
- `core/agents/adapters/fundamental_analyst_v2.py` - v2.0 实现

---

## 📊 总结表格

| Agent ID | Agent 名称 | 关键验证价位 | 研究结论倾向 | 风险关注价格 | 输出字段 |
|---------|-----------|--------------|--------------|--------------|---------|
| `pa_advisor` | 操作建议师（v1 旧版） | ✅ | ✅ (持有/加仓/减仓/清仓) | ✅ | `action_advice` |
| `pa_advisor_v2` | 持仓研究观察员 v2.0 | ✅（观察区间） | ✅ (乐观/审慎/中性) | ✅（风险关注价格） | `action_advice` |
| `trader` | 交易员（v1 旧版） | ✅ | ✅ (买入/持有/卖出) | ✅ | `trading_plan` |
| `trader_v2` | 研究整合员 v2.0 | ❌ | ✅ (乐观/审慎/中性) | ❌ | `investment_plan` |
| `research_manager` | 研究经理（v1 旧版） | ✅ | ✅ (买入/持有/卖出) | ❌ | `investment_plan` |
| `research_manager_v2` | 研究经理 v2.0 | ❌ | ✅ (乐观/审慎/中性) | ❌ | `investment_plan` |
| `risk_manager` | 风险经理（v1 旧版） | ✅ | ✅ (买入/持有/卖出) | ✅ | `final_trade_decision` |
| `risk_manager_v2` | 风险评估师 v2.0 | ✅（观察区间/验证位） | ✅ (乐观/审慎/中性) | ✅（风险关注价格/失效位） | `final_trade_decision` |
| `fundamentals_analyst` | 基本面分析师（v1 旧版） | ✅ (目标价位建议) | ✅ (买入/持有/卖出) | ❌ | `fundamentals_report` |
| `fundamentals_analyst_v2` | 基本面分析师 v2.0 | ❌ | ✅ (乐观/审慎/中性) | ❌ | `fundamentals_report` |

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

1. **研究结论倾向格式（v2）**：
   - 持仓分析场景：`乐观/审慎/中性`
   - 投资决策场景：`乐观/审慎/中性`

2. **关键验证价位字段名（v2）**：
   - 风险审阅输出使用 `price_analysis_range`（观察区间）和 `risk_reference_price`（关键失效位/验证位）
   - 持仓分析可能使用 `target_price` 字段，但仅作为观察区间，不表示目标价

3. **重要提醒**：
   - v1 旧版 Agent 已封堵入口，不再执行
   - 当前生产环境仅使用 v2 系列 Agent，输出研究观察而非交易指令

4. **提示词来源**：
   - 优先从数据库模板系统读取 (`prompt_templates` 集合)
   - 如果模板不存在，使用代码中的降级提示词 (`fallback_prompt`)

5. **版本差异**：
   - v1 Agent 使用旧版提示词格式
   - v2.0 Agent 使用新版提示词格式，支持更多字段

---

## 相关文档

- [Agent 系统设计文档](../design/v2.0/agents/02-agent-layer-design.md)
- [提示词模板系统](../design/v1.0.1/AGENT_TEMPLATE_SPECIFICATIONS.md)
- [持仓分析系统](../design/v2.0/portfolio-trade-review-engine-integration.md)
