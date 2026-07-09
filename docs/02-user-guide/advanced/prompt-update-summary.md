# 提示词更新总结

## 📋 更新概述

将旧版（v1.x）研究员的提示词内容完整迁移到新版（v2.0）的所有模板和代码中，确保辩论功能的完整支持。

**更新日期**: 2026-01-16

---

## ✅ 已完成的更新

### 1. 数据库模板更新

**更新脚本**: `scripts/update_researcher_prompts.py`

**更新规则**:
- `system_prompt`: 使用旧版的 system_prompt
- `user_prompt`: 使用旧版的 tool_guidance（因为旧版没有 user_prompt）
- `tool_guidance`: **保持新版不变**（避免与 user_prompt 重复）
- `analysis_requirements`: 使用旧版的 analysis_requirements
- `output_format`: 使用旧版的 output_format
- `constraints`: 使用旧版的 constraints

**更新的模板**:
- ✅ 看多研究员 v2.0 - 激进型
- ✅ 看多研究员 v2.0 - 中性型
- ✅ 看多研究员 v2.0 - 保守型
- ✅ 看空研究员 v2.0 - 激进型
- ✅ 看空研究员 v2.0 - 中性型
- ✅ 看空研究员 v2.0 - 保守型

**关键特性**:
- ✅ 包含辩论变量：`{history}`, `{current_response}`, `{past_memory_str}`
- ✅ 包含辩论参与要求：参与讨论、反驳对方、处理反思
- ✅ 所有偏好类型（aggressive、neutral、conservative）使用相同的旧版内容

---

### 2. 代码降级提示词更新

**更新文件**:
- ✅ `core/agents/adapters/bull_researcher_v2.py`
- ✅ `core/agents/adapters/bear_researcher_v2.py`

**更新内容**:

#### Bull Researcher V2

**System Prompt** (第 149-156 行):
```python
return """你是一位看涨分析师，负责为股票 {company_name}（股票代码：{ticker}）的投资建立强有力的论证。

⚠️ 重要提醒：当前分析的是 {market_name}，所有价格和估值请使用 {currency_name}（{currency_symbol}）作为单位。
⚠️ 在你的分析中，请始终使用公司名称"{company_name}"而不是股票代码"{ticker}"来称呼这家公司。

你的任务是构建基于证据的强有力案例，强调增长潜力、竞争优势和积极的市场指标。利用提供的研究和数据来解决担忧并有效反驳看跌论点。
"""
```

**User Prompt** (第 260-283 行):
```python
prompt = """基于提供的分析报告进行深度分析。
可用资源：
- 市场研究报告：{market_research_report}
- 社交媒体情绪报告：{sentiment_report}
- 最新世界事务新闻：{news_report}
- 公司基本面报告：{fundamentals_report}
- 辩论对话历史：{history}
- 最后的看跌论点：{current_response}
- 类似情况的反思和经验教训：{past_memory_str}
"""
```

#### Bear Researcher V2

**System Prompt** (第 147-154 行):
```python
return """你是一位看跌分析师，负责论证不投资股票 {company_name}（股票代码：{ticker}）的理由。

⚠️ 重要提醒：当前分析的是 {market_name}，所有价格和估值请使用 {currency_name}（{currency_symbol}）作为单位。
⚠️ 在你的分析中，请始终使用公司名称"{company_name}"而不是股票代码"{ticker}"来称呼这家公司。

你的目标是提出合理的论证，强调风险、挑战和负面指标。利用提供的研究和数据来突出潜在的不利因素并有效反驳看涨论点。
"""
```

**User Prompt** (第 253-276 行):
```python
prompt = """基于提供的分析报告进行深度分析。
可用资源：
- 市场研究报告：{market_research_report}
- 社交媒体情绪报告：{sentiment_report}
- 最新世界事务新闻：{news_report}
- 公司基本面报告：{fundamentals_report}
- 辩论对话历史：{history}
- 最后的看涨论点：{current_response}
- 类似情况的反思和经验教训：{past_memory_str}
"""
```

---

### 3. 日期字段修复

**修复脚本**: `scripts/fix_date_fields.py`

**问题**: 部分模板的 `updated_at` 字段是字符串类型，导致 API 调用 `isoformat()` 时报错

**修复结果**:
- ✅ 修复了 2 个模板的日期字段
- ✅ 所有日期字段现在都是 `datetime` 对象

---

## 🔍 验证结果

### 数据库验证

**验证脚本**: `scripts/verify_final_prompts.py`

**验证结果**:
```
✅ user_prompt 包含旧版辩论变量: True
✅ tool_guidance 保持新版简短内容: True
🎉 验证通过！提示词更新正确
```

### 代码验证

**诊断结果**:
```
No diagnostics found.
```

---

## 📝 关键变更说明

1. **user_prompt 来源**: 旧版的 `tool_guidance` → 新版的 `user_prompt`
2. **tool_guidance 保持**: 新版的 `tool_guidance` 保持简短，不重复 user_prompt 的内容
3. **辩论变量**: 所有模板和代码都包含 `{history}`, `{current_response}`, `{past_memory_str}`
4. **降级提示词**: 代码中的降级提示词与数据库模板保持一致
5. **偏好类型**: 所有偏好类型（aggressive、neutral、conservative）使用相同的旧版内容

---

## 🎯 下一步

1. ✅ 重启后端服务，清除缓存
2. ✅ 测试辩论功能是否正常工作
3. ✅ 验证 API 返回的提示词内容是否正确

---

**维护者**: TradingAgents-CN Pro Team  
**最后更新**: 2026-01-16

