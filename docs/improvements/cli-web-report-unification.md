# CLI 和 Web 端报告内容统一优化

## 📋 问题描述

用户反馈 CLI 命令行生成的报告内容和 Web 端生成的报告内容不一样，Web 端的内容少了一些团队决策分析部分。

## 🔍 问题分析

### CLI 端包含的完整报告结构：
- ✅ **I. 分析师团队报告** (Analyst Team Reports)
  - 市场分析师 (Market Analyst)
  - 社交媒体分析师 (Social Analyst) 
  - 新闻分析师 (News Analyst)
  - 基本面分析师 (Fundamentals Analyst)

- ✅ **II. 研究团队决策** (Research Team Decision)
  - 多头研究员 (Bull Researcher)
  - 空头研究员 (Bear Researcher) 
  - 研究经理决策 (Research Manager)

- ✅ **III. 交易团队计划** (Trading Team Plan)
  - 交易员计划 (Trader Plan)

- ✅ **IV. 风险管理团队决策** (Risk Management Team)
  - 激进分析师 (Aggressive Analyst)
  - 保守分析师 (Conservative Analyst)
  - 中性分析师 (Neutral Analyst)

- ✅ **V. 投资组合经理决策** (Portfolio Manager Decision)

### Web 端原来仅包含的简化报告结构：
- ✅ **基础分析模块**
  - 市场技术分析 (market_report)
  - 基本面分析 (fundamentals_report)
  - 市场情绪分析 (sentiment_report)
  - 新闻事件分析 (news_report)
  - 风险评估 (risk_assessment)
  - 投资建议 (investment_plan)

## 🛠️ 优化方案

### 1. 扩展 Web 端状态处理逻辑

**文件**: `web/utils/analysis_runner.py`

```python
# 处理各个分析模块的结果 - 包含完整的智能体团队分析
analysis_keys = [
    'market_report',
    'fundamentals_report', 
    'sentiment_report',
    'news_report',
    'risk_assessment',
    'investment_plan',
    # 添加缺失的团队决策数据，确保与CLI端一致
    'investment_debate_state',  # 研究团队辩论（多头/空头研究员）
    'trader_investment_plan',   # 交易团队计划
    'risk_debate_state',        # 风险管理团队决策
    'final_trade_decision'      # 最终交易决策
]
```

### 2. 增强 Web 端报告生成器

**文件**: `web/utils/report_exporter.py`

#### 添加团队决策报告生成方法：
- `_add_team_decision_reports()` - 添加完整的团队决策报告
- `_format_team_decision_content()` - 格式化团队决策内容

#### 新增报告部分：
- 🔬 研究团队决策
- 💼 交易团队计划  
- ⚖️ 风险管理团队决策
- 🎯 最终交易决策

### 3. 改进分模块报告保存

添加团队决策报告模块：
- `research_team_decision.md` - 研究团队决策报告
- `risk_management_decision.md` - 风险管理团队决策报告

## ✅ 优化结果

### 统一后的完整报告结构：

1. **🎯 投资决策摘要**
   - 投资建议、置信度、风险评分、目标价位

2. **📊 详细分析报告**
   - 📈 市场技术分析
   - 💰 基本面分析
   - 💭 市场情绪分析
   - 📰 新闻事件分析
   - ⚠️ 风险评估
   - 📋 投资建议

3. **🔬 研究团队决策** *(新增)*
   - 📈 多头研究员分析
   - 📉 空头研究员分析
   - 🎯 研究经理综合决策

4. **💼 交易团队计划** *(新增)*
   - 专业交易员制定的具体交易执行计划

5. **⚖️ 风险管理团队决策** *(新增)*
   - 🚀 激进分析师评估
   - 🛡️ 保守分析师评估
   - ⚖️ 中性分析师评估
   - 🎯 投资组合经理最终决策

6. **🎯 最终交易决策** *(新增)*
   - 综合所有团队分析后的最终投资决策

## 🎉 优化效果

- ✅ **内容一致性**: CLI 和 Web 端现在生成相同结构和内容的报告
- ✅ **完整性提升**: Web 端报告现在包含所有智能体团队的分析结果
- ✅ **用户体验**: 用户无论使用哪种方式都能获得完整的分析报告
- ✅ **模块化保存**: 支持将团队决策报告保存为独立的模块文件

## 📝 使用说明

优化后，Web 端生成的报告将包含：
- 完整的智能体团队分析过程
- 多头/空头研究员的辩论分析
- 风险管理团队的多角度评估
- 最终的综合投资决策

这确保了 CLI 和 Web 端用户都能获得相同质量和深度的分析报告。
