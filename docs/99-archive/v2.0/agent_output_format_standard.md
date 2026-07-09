# Agent 输出格式统一标准

## 📊 当前问题

通过代码分析发现，不同Agent的输出格式要求不一致：

1. **Manager类型Agent**：
   - `research_manager_v2`: 要求JSON格式 ✅
   - `review_manager_v2`: 要求JSON格式 ✅
   - `action_advisor_v2`: 要求JSON格式 ✅
   - `risk_manager_v2`: 解析JSON格式 ✅

2. **Researcher类型Agent**：
   - `bull_researcher_v2`: 要求"结构化方式输出"（未明确格式）⚠️
   - `bear_researcher_v2`: 要求"结构化方式输出"（未明确格式）⚠️

3. **Analyst类型Agent**：
   - `market_analyst_v2`: 要求"结构化方式输出"（未明确格式）⚠️
   - `fundamentals_analyst_v2`: 未明确格式要求 ⚠️

4. **格式定义错误**：
   - `research_manager_v2` 的 `output_format` 字段定义的是Markdown格式（研究总结报告）
   - 但实际代码期望的是JSON格式
   - 造成格式要求与实际需求不匹配

## 🎯 统一标准

### 原则

根据Agent的职责和输出用途，确定格式标准：

1. **需要结构化数据提取的Agent → JSON格式**
2. **纯文本报告输出的Agent → Markdown格式**

### Agent分类和格式标准

#### 1. Manager类型Agent → **JSON格式**

**原因**：
- 需要提取结构化字段（action, confidence, target_price, reasoning等）
- 后续处理需要解析这些字段
- 前端显示时会转换为Markdown

**包含的Agent**：
- `research_manager_v2` - 投资决策（需要action, confidence, target_price）
- `review_manager_v2` - 复盘总结（需要overall_score, strengths, weaknesses）
- `action_advisor_v2` - 操作建议（需要action, confidence）
- `risk_manager_v2` - 风险评估（需要risk_score, final_trade_decision）

**JSON结构要求**：
```json
{
    "action": "买入|持有|卖出",
    "confidence": 0-100整数,
    "target_price": 数字（可选）,
    "reasoning": "详细理由（200-500字）",
    ...
}
```

#### 2. Researcher类型Agent → **Markdown格式**

**原因**：
- 输出的是分析观点报告
- 主要是文本内容，不需要结构化提取
- 直接用于展示

**包含的Agent**：
- `bull_researcher_v2` - 看涨观点报告
- `bear_researcher_v2` - 看跌观点报告

**Markdown结构要求**：
- 使用Markdown格式
- 包含标题、列表、段落等
- 结构清晰，便于阅读

#### 3. Analyst类型Agent → **Markdown格式**

**原因**：
- 输出的是分析报告
- 主要是文本内容，不需要结构化提取
- 直接用于展示

**包含的Agent**：
- `market_analyst_v2` - 市场分析报告
- `fundamentals_analyst_v2` - 基本面分析报告
- `news_analyst_v2` - 新闻分析报告
- `social_analyst_v2` - 社交媒体分析报告
- `sector_analyst_v2` - 板块分析报告
- `index_analyst_v2` - 大盘分析报告

**Markdown结构要求**：
- 使用Markdown格式
- 包含标题、列表、表格等
- 结构清晰，便于阅读

## 📝 代码证据

### 1. report_formatter.py 的处理逻辑

```python
# 对于 investment_plan，会尝试解析JSON
if field == 'investment_plan':
    markdown_value = _convert_json_to_markdown(value.strip(), "investment")
    reports[field] = markdown_value
```

**说明**：系统期望 `investment_plan` 是JSON格式，然后转换为Markdown用于显示。

### 2. Manager Agent的默认解析

```python
def _parse_response(self, response: str) -> Dict[str, Any]:
    # 默认实现：直接返回文本
    return {
        "content": response,
        "success": True
    }
```

**说明**：Manager Agent默认返回文本，但实际应该返回JSON字符串，由report_formatter解析。

### 3. 其他Manager Agent的JSON要求

- `review_manager_v2`: 明确要求JSON格式
- `action_advisor_v2`: 明确要求JSON格式
- `risk_manager_v2`: 代码中解析JSON格式

## ✅ 修正方案

### research_manager_v2 的 output_format 字段

**当前（错误）**：
```
## 📊 研究总结报告

### 一、多空观点对比
...
```

**应该改为（正确）**：
```
**输出格式要求**：

请严格按照以下JSON格式输出投资计划：

```json
{
    "action": "买入|持有|卖出",
    "confidence": 0-100的整数（必需字段，表示对投资建议的信心度）,
    "target_price": 数字（可选字段，目标价格，必须基于报告中的真实数据）,
    "risk_score": 0-1的数字（可选字段，风险评分）,
    "reasoning": "字符串（必需字段，200-500字，详细的决策理由和分析依据）",
    "summary": "字符串（可选字段，投资计划摘要）",
    "risk_warning": "字符串（可选字段，风险提示）",
    "position_ratio": "字符串（可选字段，建议持仓比例）"
}
```

**字段说明**：
1. **action** (必需): 投资建议，只能是"买入"、"持有"或"卖出"
2. **confidence** (必需): 信心度，必须是0-100之间的整数（如：62、75、80），不是小数
3. **target_price** (可选): 目标价格，必须基于报告中的真实价格数据，严禁编造
4. **reasoning** (必需): 决策理由，200-500字，必须详细说明：
   - 为什么做出这个投资建议
   - 基于哪些分析依据（技术面、基本面、市场环境、看涨观点、看跌观点等）
   - 关键判断因素和逻辑推理过程
5. 其他字段为可选字段，根据需要填写

**重要提示**：
- 必须严格按照JSON格式输出，确保所有必需字段都存在
- confidence必须是整数，不是小数
- target_price必须基于报告中的真实数据，不能随意编造
- reasoning必须详细说明决策理由，不能使用默认值或模板文字
```

## 🔄 实施步骤

1. ✅ 分析当前格式要求（已完成）
2. ⏳ 确认统一标准（待用户确认）
3. ⏳ 修正 research_manager_v2 的 output_format 字段
4. ⏳ 检查其他Manager Agent的格式要求是否一致
5. ⏳ 更新文档说明

## 📋 注意事项

1. **格式转换**：
   - Manager Agent输出JSON格式
   - report_formatter会自动转换为Markdown用于前端显示
   - 不需要Agent自己输出Markdown

2. **向后兼容**：
   - 如果Agent输出的是Markdown格式，report_formatter会尝试解析JSON
   - 如果解析失败，会直接使用原文本
   - 但为了统一性，应该统一使用JSON格式

3. **字段提取**：
   - Manager Agent的JSON输出会被解析，提取关键字段
   - 这些字段用于后续处理和展示
   - 所以JSON格式是必需的

