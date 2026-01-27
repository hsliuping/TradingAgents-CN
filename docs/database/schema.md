# TradingAgents-CN Pro 数据库表结构

**生成时间**: 2026-01-27 10:15:31

**数据库**: tradingagents

**集合数量**: 72

---

## 📋 集合目录

- [agent_configs](#agent_configs) (47 条记录)
- [agent_io_definitions](#agent_io_definitions) (0 条记录)
- [agent_workflow_bindings](#agent_workflow_bindings) (0 条记录)
- [analysis_reports](#analysis_reports) (209 条记录)
- [analysis_tasks](#analysis_tasks) (108 条记录)
- [capital_transactions](#capital_transactions) (15 条记录)
- [datasource_groupings](#datasource_groupings) (12 条记录)
- [email_records](#email_records) (162 条记录)
- [financial_data_cache](#financial_data_cache) (4 条记录)
- [imported_data](#imported_data) (1 条记录)
- [license_cache](#license_cache) (3 条记录)
- [llm_providers](#llm_providers) (10 条记录)
- [market_categories](#market_categories) (3 条记录)
- [market_quotes](#market_quotes) (5,804 条记录)
- [market_quotes_hk](#market_quotes_hk) (0 条记录)
- [market_quotes_us](#market_quotes_us) (0 条记录)
- [model_catalog](#model_catalog) (10 条记录)
- [notifications](#notifications) (149 条记录)
- [operation_logs](#operation_logs) (4,905 条记录)
- [paper_accounts](#paper_accounts) (5 条记录)
- [paper_market_rules](#paper_market_rules) (3 条记录)
- [paper_orders](#paper_orders) (7 条记录)
- [paper_positions](#paper_positions) (5 条记录)
- [paper_trades](#paper_trades) (24 条记录)
- [platform_configs](#platform_configs) (4 条记录)
- [portfolio_analysis_reports](#portfolio_analysis_reports) (12 条记录)
- [position_analysis_reports](#position_analysis_reports) (82 条记录)
- [position_changes](#position_changes) (8 条记录)
- [prompt_templates](#prompt_templates) (146 条记录)
- [quotes_ingestion_status](#quotes_ingestion_status) (1 条记录)
- [real_accounts](#real_accounts) (1 条记录)
- [real_positions](#real_positions) (9 条记录)
- [scheduled_analysis_configs](#scheduled_analysis_configs) (1 条记录)
- [scheduled_analysis_history](#scheduled_analysis_history) (2 条记录)
- [scheduler_executions](#scheduler_executions) (779 条记录)
- [scheduler_history](#scheduler_history) (73 条记录)
- [scheduler_metadata](#scheduler_metadata) (1 条记录)
- [smtp_config](#smtp_config) (1 条记录)
- [social_media_messages](#social_media_messages) (6 条记录)
- [stock_basic_info](#stock_basic_info) (16,458 条记录)
- [stock_basic_info_hk](#stock_basic_info_hk) (40 条记录)
- [stock_basic_info_us](#stock_basic_info_us) (0 条记录)
- [stock_daily_quotes](#stock_daily_quotes) (10,899 条记录)
- [stock_daily_quotes_hk](#stock_daily_quotes_hk) (0 条记录)
- [stock_daily_quotes_us](#stock_daily_quotes_us) (0 条记录)
- [stock_financial_data](#stock_financial_data) (51 条记录)
- [stock_financial_data_hk](#stock_financial_data_hk) (0 条记录)
- [stock_financial_data_us](#stock_financial_data_us) (0 条记录)
- [stock_news](#stock_news) (625 条记录)
- [stock_news_hk](#stock_news_hk) (0 条记录)
- [stock_news_us](#stock_news_us) (0 条记录)
- [stock_screening_view](#stock_screening_view) (16,458 条记录)
- [sync_status](#sync_status) (1 条记录)
- [system_configs](#system_configs) (47 条记录)
- [template_history](#template_history) (364 条记录)
- [token_usage](#token_usage) (8,300 条记录)
- [tool_agent_bindings](#tool_agent_bindings) (38 条记录)
- [tool_configs](#tool_configs) (1 条记录)
- [trade_reviews](#trade_reviews) (130 条记录)
- [trading_system_evaluations](#trading_system_evaluations) (4 条记录)
- [trading_system_versions](#trading_system_versions) (3 条记录)
- [trading_systems](#trading_systems) (2 条记录)
- [unified_analysis_tasks](#unified_analysis_tasks) (302 条记录)
- [user_favorites](#user_favorites) (3 条记录)
- [user_sessions](#user_sessions) (218 条记录)
- [user_tags](#user_tags) (4 条记录)
- [user_template_configs](#user_template_configs) (48 条记录)
- [users](#users) (1 条记录)
- [watchlist_groups](#watchlist_groups) (1 条记录)
- [workflow_definitions](#workflow_definitions) (0 条记录)
- [workflow_history](#workflow_history) (28 条记录)
- [workflows](#workflows) (2 条记录)

---

## agent_configs

**文档数量**: 47

**分析样本**: 47 条

### 字段列表

| 字段路径 | 类型 | 出现率 | 示例值 |
|---------|------|--------|--------|
| `_id` | ObjectId | 100.0% | - |
| `agent_id` | string | 100.0% | market_analyst_v2 |
| `category` | string | 78.7% | analyst |
| `color` | string | 53.2% | #2ecc71 |
| `config` | object | 100.0% | - |
| `config.max_iterations` | integer | 78.7% | 3 |
| `config.temperature` | float | 100.0% | 0.2 |
| `config.timeout` | integer | 78.7% | 300 |
| `created_at` | string | 25.5% | 2025-12-15T10:51:19.328129 |
| `default_tools` | array<string>, array | 100.0% | - |
| `description` | string | 78.7% | v2.0 架构的市场分析师，支持动态工具绑定 |
| `enabled` | boolean | 78.7% | True |
| `execution_order` | integer | 53.2% | 10 |
| `icon` | string | 53.2% | 📈 |
| `input_fields` | array | 59.6% | - |
| `inputs` | array<object> | 4.3% | - |
| `is_active` | boolean | 53.2% | True |
| `license_tier` | string | 59.6% | free |
| `max_tool_calls` | integer | 74.5% | 3 |
| `metadata` | object | 19.1% | - |
| `metadata.is_builtin` | boolean | 19.1% | True |
| `metadata.license_tier` | string | 19.1% | free |
| `name` | string | 78.7% | 市场分析师 v2 |
| `node_name` | string | 53.2% | Market Analyst v2 |
| `output_field` | string | 53.2% | market_analysis |
| `output_fields` | array | 59.6% | - |
| `outputs` | array<object> | 4.3% | - |
| `prompt_template_name` | null, string | 78.7% | bull_researcher_v2 |
| `prompt_template_type` | null, string | 78.7% | general |
| `report_label` | string | 53.2% | 【市场分析 v2】 |
| `required_tools` | array | 78.7% | - |
| `requires_tools` | boolean | 53.2% | True |
| `tags` | array<string>, array | 59.6% | - |
| `tools` | array<string>, array | 74.5% | - |
| `updated_at` | string | 100.0% | 2026-01-18T03:04:29.957285 |
| `version` | string | 19.1% | 2.0.0 |

---

## agent_io_definitions

**文档数量**: 0

**分析样本**: 0 条

---

## agent_workflow_bindings

**文档数量**: 0

**分析样本**: 0 条

---

## analysis_reports

**文档数量**: 209

**分析样本**: 100 条

### 字段列表

| 字段路径 | 类型 | 出现率 | 示例值 |
|---------|------|--------|--------|
| `_id` | ObjectId | 100.0% | - |
| `analysis_date` | string, datetime | 100.0% | 2025-12-11 |
| `analysis_id` | string | 100.0% | 600519_20251211_113346 |
| `analysts` | array<string>, array | 100.0% | - |
| `confidence_score` | float, integer | 100.0% | 0.9 |
| `created_at` | datetime | 100.0% | 2025-12-11T11:33:46.977000 |
| `decision` | object | 82.0% | - |
| `decision.action` | string | 78.0% | 卖出 |
| `decision.confidence` | float, integer | 78.0% | 0.9 |
| `decision.position_ratio` | string | 7.0% | 5% |
| `decision.reasoning` | string | 78.0% | 批价倒挂、聪明钱撤离、技术破位在即，基本面已透支估值，当前为风险释放前夜，必须果断减仓以规避后... |
| `decision.risk_score` | float | 78.0% | 0.85 |
| `decision.risk_warning` | string | 7.0% | 警惕销售持续下滑、债务展期失败及信用评级下调风险，若跌破¥4.60支撑位，可能开启深度回调。 |
| `decision.stop_loss` | float | 7.0% | 4.6 |
| `decision.summary` | string | 7.0% | 估值触底但基本面承压，建议小仓位持有，严守止损，静待反转信号。 |
| `decision.target_price` | float | 78.0% | 1320.0 |
| `deep_model` | string | 39.0% | qwen-plus |
| `engine` | string | 69.0% | unified |
| `execution_time` | float, integer | 82.0% | 438.751234 |
| `key_points` | array<string>, array | 82.0% | - |
| `market_type` | string | 100.0% | A股 |
| `model_info` | string | 100.0% | ChatDashScopeOpenAI:qwen-plus |
| `performance_metrics` | object | 43.0% | - |
| `performance_metrics.average_node_time` | float | 21.0% | 22.1 |
| `performance_metrics.category_timings` | object | 21.0% | - |
| `performance_metrics.category_timings.analyst_team` | object | 21.0% | - |
| `performance_metrics.category_timings.message_clearing` | object | 21.0% | - |
| `performance_metrics.category_timings.other` | object | 21.0% | - |
| `performance_metrics.category_timings.research_team` | object | 21.0% | - |
| `performance_metrics.category_timings.risk_management_team` | object | 21.0% | - |
| `performance_metrics.category_timings.tool_calls` | object | 21.0% | - |
| `performance_metrics.category_timings.trader_team` | object | 21.0% | - |
| `performance_metrics.fastest_node` | object | 21.0% | - |
| `performance_metrics.fastest_node.name` | string | 21.0% | Index Analyst Analyst |
| `performance_metrics.fastest_node.time` | float | 21.0% | 0.0 |
| `performance_metrics.llm_config` | object | 21.0% | - |
| `performance_metrics.llm_config.deep_think_model` | string | 21.0% | qwen-plus |
| `performance_metrics.llm_config.provider` | string | 21.0% | dashscope |
| `performance_metrics.llm_config.quick_think_model` | string | 21.0% | qwen-flash |
| `performance_metrics.node_count` | integer | 21.0% | 19 |
| `performance_metrics.node_timings` | object | 21.0% | - |
| `performance_metrics.node_timings.Bear Researcher` | float | 21.0% | 66.39 |
| `performance_metrics.node_timings.Bull Researcher` | float | 21.0% | 35.15 |
| `performance_metrics.node_timings.Fundamentals Analyst` | float | 21.0% | 0.01 |
| `performance_metrics.node_timings.Index Analyst Analyst` | float | 13.0% | 0.0 |
| `performance_metrics.node_timings.Market Analyst` | float | 21.0% | 0.03 |
| `performance_metrics.node_timings.Msg Clear Fundamentals` | float | 21.0% | 42.87 |
| `performance_metrics.node_timings.Msg Clear Index Analyst` | float | 13.0% | 38.24 |
| `performance_metrics.node_timings.Msg Clear Market` | float | 21.0% | 2.31 |
| `performance_metrics.node_timings.Msg Clear News` | float | 17.0% | 29.24 |
| `performance_metrics.node_timings.Msg Clear Sector Analyst` | float | 13.0% | 15.63 |
| `performance_metrics.node_timings.Msg Clear Social` | float | 9.0% | 77.58 |
| `performance_metrics.node_timings.Neutral Analyst` | float | 21.0% | 87.43 |
| `performance_metrics.node_timings.News Analyst` | float | 17.0% | 0.01 |
| `performance_metrics.node_timings.Research Manager` | float | 21.0% | 37.66 |
| `performance_metrics.node_timings.Risk Judge` | float | 21.0% | 0.04 |
| `performance_metrics.node_timings.Risky Analyst` | float | 21.0% | 14.37 |
| `performance_metrics.node_timings.Safe Analyst` | float | 21.0% | 14.98 |
| `performance_metrics.node_timings.Sector Analyst Analyst` | float | 13.0% | 0.01 |
| `performance_metrics.node_timings.Social Analyst` | float | 9.0% | 0.02 |
| `performance_metrics.node_timings.Trader` | float | 21.0% | 11.94 |
| `performance_metrics.node_timings.tools_fundamentals` | float | 21.0% | 23.56 |
| `performance_metrics.node_timings.tools_social` | float | 9.0% | 1.0 |
| `performance_metrics.slowest_node` | object | 21.0% | - |
| `performance_metrics.slowest_node.name` | string | 21.0% | Neutral Analyst |
| `performance_metrics.slowest_node.time` | float | 21.0% | 87.43 |
| `performance_metrics.total_time` | float | 21.0% | 437.51 |
| `performance_metrics.total_time_minutes` | float | 21.0% | 7.29 |
| `quick_model` | string | 39.0% | qwen-flash |
| `recommendation` | string | 100.0% | 投资建议：卖出。目标价格：1320.0元。决策依据：批价倒挂、聪明钱撤离、技术破位在即，基本面... |
| `reports` | object | 100.0% | - |
| `reports.bear_report` | string | 10.0% | # **看跌观点报告：平安银行（000001）风险评估与投资警示**  
**分析日期：202... |
| `reports.bear_researcher` | string | 78.0% | Bear Analyst: ### **看跌分析师回应：贵州茅台——不是“确定性”，而是“高估... |
| `reports.bull_report` | string | 8.0% | # **看涨分析报告：平安银行（000001）——价值洼地中的“现金牛”与成长型龙头**

*... |
| `reports.bull_researcher` | string | 63.0% | Bull Analyst: ### **看涨分析师回应：贵州茅台——不是“高估”，而是“被低估... |
| `reports.final_trade_decision` | string | 87.0% | ### **最终决策：卖出**

---

#### 📌 **明确指令：立即执行“分步减仓”计... |
| `reports.fundamentals_report` | string | 96.0% | # **贵州茅台（600519）基本面分析报告**  
**分析日期：2025年12月11日*... |
| `reports.index_report` | string | 57.0% | # 📊 大盘分析报告（2025年12月11日）  
**分析师：中性客观大盘/指数分析师** ... |
| `reports.investment_plan` | string | 96.0% | 我们刚刚经历了一场高水平的辩论，双方都展现了极强的逻辑与数据支撑。看涨方用“国家符号”“金融化... |
| `reports.market_report` | string | 96.0% | # **贵州茅台（600519）技术分析报告**  
**分析日期：2025-12-11**
... |
| `reports.neutral_analyst` | string | 78.0% | Neutral Analyst: 你听好了，我来谈谈。

我们一直在争论“该不该清仓”、“要不... |
| `reports.neutral_opinion` | string | 10.0% | # **中性风险分析师评估报告**  
## **平安银行（股票代码：000001）投资计划综... |
| `reports.news_report` | string | 89.0% | ### **贵州茅台（600519）新闻分析报告**  
**发布日期：2025年12月11日... |
| `reports.research_team_decision` | string, object | 85.0% | 我们刚刚经历了一场高水平的辩论，双方都展现了极强的逻辑与数据支撑。看涨方用“国家符号”“金融化... |
| `reports.research_team_decision.content` | string | 2.0% | 我们来做一个冷静、理性、基于事实的最终决策。

---

### 📌 **最终投资建议：买入（... |
| `reports.research_team_decision.success` | boolean | 2.0% | True |
| `reports.risk_assessment` | string | 10.0% | # **平安银行（000001）风险评估报告**  
> **分析日期：2025年12月17日... |
| `reports.risk_management_decision` | string | 85.0% | ### **最终决策：卖出**

---

#### 📌 **明确指令：立即执行“分步减仓”计... |
| `reports.risky_analyst` | string | 80.0% | Risky Analyst: 你听好了，别再拿什么“稳健”“持有观望”当挡箭牌了。

现在摆在... |
| `reports.risky_opinion` | string | 10.0% | ---

# 🔥 **激进风险分析师报告：平安银行（股票代码：000001）——从“价值陷阱”... |
| `reports.safe_analyst` | string | 78.0% | Safe Analyst: 你听好了，激进分析师，别以为把“恐惧”包装成“勇气”，就能让危险变... |
| `reports.safe_opinion` | string | 10.0% | ---

# **保守风险分析师评估报告**  
**投资标的：平安银行（股票代码：未提供，分... |
| `reports.sector_report` | string | 67.0% | # 📊 **白酒板块综合分析报告（2025年12月11日）**

---

## 一、板块表现... |
| `reports.sentiment_report` | string | 58.0% | ### 万科A（000002）投资者情绪分析报告

#### 一、市场情绪概况
根据当前数据，... |
| `reports.trader_investment_plan` | string | 81.0% | 最终交易建议: **持有（但立即执行逢高减仓策略）**

---

### 1. **投资建议... |
| `research_depth` | string | 100.0% | 基础 |
| `risk_level` | string | 100.0% | 中等 |
| `source` | string | 100.0% | api |
| `status` | string | 100.0% | completed |
| `stock_code` | string | 54.0% | 601668 |
| `stock_name` | string | 100.0% | 贵州茅台 |
| `stock_symbol` | string | 100.0% | 600519 |
| `summary` | string | 100.0% | 最终决策：卖出

---

 📌 明确指令：立即执行“分步减仓”计划，3个交易日内完成现有仓位... |
| `task_id` | string | 82.0% | 4ccf64de-d5dd-4abb-978c-784806268746 |
| `timestamp` | datetime | 100.0% | 2025-12-11T11:33:46.977000 |
| `tokens_used` | integer | 82.0% | 0 |
| `updated_at` | datetime | 100.0% | 2025-12-11T11:33:46.977000 |
| `user_id` | string, ObjectId | 61.0% | 6915d05ac52e760d74ed36a2 |

---

## analysis_tasks

**文档数量**: 108

**分析样本**: 100 条

### 字段列表

| 字段路径 | 类型 | 出现率 | 示例值 |
|---------|------|--------|--------|
| `_id` | ObjectId | 100.0% | - |
| `completed_at` | datetime | 93.0% | 2025-12-03T11:49:24.925000 |
| `created_at` | datetime | 100.0% | 2025-12-03T11:46:01.724000 |
| `current_step` | string | 52.0% | result_processing |
| `error_message` | string | 1.0% | RedisProgressTracker.mark_completed() takes 1 p... |
| `last_error` | string | 11.0% | ❌ 股票代码无效

不支持的市场类型: CN

💡 请选择支持的市场类型：A股、港股、美股 |
| `message` | string | 52.0% | 处理分析结果... |
| `progress` | integer | 100.0% | 100 |
| `result` | object | 74.0% | - |
| `result.analysis_date` | null, string | 74.0% | 2025-12-03 |
| `result.analysis_id` | string | 74.0% | 300750_20251203_114924 |
| `result.confidence_score` | float | 74.0% | 0.7 |
| `result.decision` | object | 74.0% | - |
| `result.decision.action` | string | 69.0% | 持有 |
| `result.decision.confidence` | float | 69.0% | 0.7 |
| `result.decision.reasoning` | string | 69.0% | 宁德时代作为新能源电池行业的龙头企业，具备长期增长潜力和技术优势。尽管短期面临市场调整和竞争压... |
| `result.decision.risk_score` | float | 69.0% | 0.6 |
| `result.decision.target_price` | null, float | 69.0% | 370.0 |
| `result.detailed_analysis` | object | 74.0% | - |
| `result.detailed_analysis.action` | string | 45.0% | 持有 |
| `result.detailed_analysis.confidence` | float | 43.0% | 0.7 |
| `result.detailed_analysis.model_info` | string | 43.0% | ChatDashScopeOpenAI:qwen-max |
| `result.detailed_analysis.reasoning` | string | 47.0% | 宁德时代作为新能源电池行业的龙头企业，具备长期增长潜力和技术优势。尽管短期面临市场调整和竞争压... |
| `result.detailed_analysis.risk_score` | float | 43.0% | 0.6 |
| `result.detailed_analysis.target_price` | float | 43.0% | 370.0 |
| `result.execution_time` | float, integer | 74.0% | 200.965165 |
| `result.key_points` | array | 74.0% | - |
| `result.recommendation` | string | 74.0% | 投资建议：持有。目标价格：370.0元。决策依据：宁德时代作为新能源电池行业的龙头企业，具备长... |
| `result.reports` | object | 74.0% | - |
| `result.reports.bear_researcher` | string | 55.0% | Bear Analyst: ### 看跌分析师：宁德时代（300750）的看跌立场论证

**... |
| `result.reports.bull_researcher` | string | 57.0% | Bull Analyst: 当然，作为一名看涨分析师，我将基于宁德时代当前的市场表现、基本面、... |
| `result.reports.final_trade_decision` | string | 69.0% | ### 风险管理决策

#### 1. 总结关键论点
- **激进分析师**：
  - **增... |
| `result.reports.fundamentals_report` | string | 69.0% | ### 宁德时代（股票代码：300750）基本面分析报告

#### 一、公司基本信息
- *... |
| `result.reports.index_report` | string | 21.0% | # 📊 大盘/指数综合分析报告  
📅 **分析日期：2025年12月11日**  
📍 **... |
| `result.reports.investment_plan` | string | 69.0% | ### 投资决策总结

#### 看涨分析师的关键观点：
1. **增长潜力**：宁德时代作为... |
| `result.reports.market_report` | string | 69.0% | # **宁德时代（300750）技术分析报告**  
**分析日期：2025-12-03** ... |
| `result.reports.neutral_analyst` | string | 55.0% | Neutral Analyst: 我理解激进分析师和安全分析师各自的立场，但他们的观点都存在明... |
| `result.reports.news_report` | string | 55.0% | ### 1. 新闻事件总结

最新新闻显示，机器人板块迎来利好催化，汽车零件ETF（15930... |
| `result.reports.research_team_decision` | string | 65.0% | ### 投资决策总结

#### 看涨分析师的关键观点：
1. **增长潜力**：宁德时代作为... |
| `result.reports.risk_management_decision` | string | 65.0% | ### 风险管理决策

#### 1. 总结关键论点
- **激进分析师**：
  - **增... |
| `result.reports.risky_analyst` | string | 65.0% | Risky Analyst: 我完全理解保守和中性分析师的担忧，但我要说的是，他们的观点太保守... |
| `result.reports.safe_analyst` | string | 63.0% | Safe Analyst: 我完全理解激进分析师的乐观情绪，但我要指出的是，他的分析中存在几个... |
| `result.reports.sector_report` | string | 21.0% | ---

# 📊 **白酒板块综合分析报告（2025年12月11日）**

> **分析对象：... |
| `result.reports.sentiment_report` | string | 2.0% | ### 平安银行（000001）情绪分析报告（2025-12-11）

#### 一、市场情绪... |
| `result.reports.trader_investment_plan` | string | 65.0% | 最终交易建议: **持有**

**目标价位**: ¥370 - ¥380（1个月）；¥380... |
| `result.risk_level` | string | 74.0% | 中等 |
| `result.stock_code` | string | 74.0% | 300750 |
| `result.stock_symbol` | string | 74.0% | 300750 |
| `result.summary` | string | 74.0% | 风险管理决策

 1. 总结关键论点
- 激进分析师：
  - 增长潜力：宁德时代作为新能源电... |
| `result.tokens_used` | integer | 74.0% | 0 |
| `started_at` | datetime | 52.0% | 2025-12-03T11:46:02.240000 |
| `status` | string | 100.0% | completed |
| `stock_code` | string | 100.0% | 300750 |
| `stock_name` | string | 100.0% | 宁德时代 |
| `stock_symbol` | string | 100.0% | 300750 |
| `task_id` | string | 100.0% | c27608cb-0826-47c0-934d-18898ce6a268 |
| `updated_at` | datetime | 94.0% | 2025-12-03T11:49:24.925000 |
| `user_id` | string | 100.0% | 6915d05ac52e760d74ed36a2 |

---

## capital_transactions

**文档数量**: 15

**分析样本**: 15 条

### 字段列表

| 字段路径 | 类型 | 出现率 | 示例值 |
|---------|------|--------|--------|
| `_id` | ObjectId | 100.0% | - |
| `amount` | float | 100.0% | 100000.0 |
| `balance_after` | float | 100.0% | 100000.0 |
| `balance_before` | float | 100.0% | 0.0 |
| `created_at` | datetime | 100.0% | 2025-12-04T11:12:35.694000 |
| `currency` | string | 100.0% | CNY |
| `description` | string | 100.0% | 初始资金 100,000.00 CNY |
| `transaction_type` | string | 100.0% | initial |
| `user_id` | string | 100.0% | 6915d05ac52e760d74ed36a2 |

---

## datasource_groupings

**文档数量**: 12

**分析样本**: 12 条

### 字段列表

| 字段路径 | 类型 | 出现率 | 示例值 |
|---------|------|--------|--------|
| `_id` | ObjectId | 100.0% | - |
| `created_at` | datetime | 100.0% | 2025-08-19T01:06:23.193000 |
| `data_source_name` | string | 100.0% | AKShare |
| `enabled` | boolean | 100.0% | True |
| `market_category_id` | string | 100.0% | a_shares |
| `priority` | integer | 100.0% | 2 |
| `updated_at` | datetime | 100.0% | 2025-10-30T13:49:03.070000 |

---

## email_records

**文档数量**: 162

**分析样本**: 100 条

### 字段列表

| 字段路径 | 类型 | 出现率 | 示例值 |
|---------|------|--------|--------|
| `_id` | string | 100.0% | 4e1d0acd-7675-4165-bbc8-e8101d29535f |
| `created_at` | string | 100.0% | 2025-12-07T12:38:27.562478+08:00 |
| `email_type` | string | 100.0% | test_email |
| `error_message` | null, string | 100.0% | SMTP发送失败 |
| `max_retries` | integer | 100.0% | 3 |
| `reference_id` | null, string | 100.0% | 95748a25-de86-472d-a555-a73fa95aa900 |
| `reference_type` | null | 100.0% | - |
| `retry_count` | integer | 100.0% | 0 |
| `sent_at` | null, string | 100.0% | 2025-12-07T12:38:35.114913+08:00 |
| `status` | string | 100.0% | sent |
| `subject` | string | 100.0% | TradingAgents-CN 通知 |
| `template_name` | string | 100.0% | test_email |
| `to_email` | string | 100.0% | 107213551@qq.com |
| `user_id` | string | 100.0% | 6915d05ac52e760d74ed36a2 |

---

## financial_data_cache

**文档数量**: 4

**分析样本**: 4 条

### 字段列表

| 字段路径 | 类型 | 出现率 | 示例值 |
|---------|------|--------|--------|
| `_id` | ObjectId | 100.0% | - |
| `cache_type` | string | 100.0% | raw_financial_data |
| `financial_data` | object | 100.0% | - |
| `financial_data.main_indicators` | array<object> | 100.0% | - |
| `stock_info` | object | 100.0% | - |
| `stock_info.area` | string | 100.0% | 未知 |
| `stock_info.code` | string | 100.0% | 002146 |
| `stock_info.data_source` | string | 100.0% | akshare |
| `stock_info.full_symbol` | string | 100.0% | 002146.SZ |
| `stock_info.industry` | string | 100.0% | 未知 |
| `stock_info.last_sync` | datetime | 100.0% | 2025-11-04T09:54:14.285000 |
| `stock_info.list_date` | string | 100.0% | 20070808 |
| `stock_info.market` | string | 100.0% | 深圳证券交易所 |
| `stock_info.market_info` | object | 100.0% | - |
| `stock_info.market_info.currency` | string | 100.0% | CNY |
| `stock_info.market_info.exchange` | string | 100.0% | SZSE |
| `stock_info.market_info.exchange_name` | string | 100.0% | 深圳证券交易所 |
| `stock_info.market_info.market_type` | string | 100.0% | CN |
| `stock_info.market_info.timezone` | string | 100.0% | Asia/Shanghai |
| `stock_info.name` | string | 100.0% | 荣盛发展 |
| `stock_info.sync_status` | string | 100.0% | success |
| `symbol` | string | 100.0% | 002146 |
| `updated_at` | datetime | 100.0% | 2025-11-04T17:54:14.307000 |

---

## imported_data

**文档数量**: 1

**分析样本**: 1 条

### 字段列表

| 字段路径 | 类型 | 出现率 | 示例值 |
|---------|------|--------|--------|
| `_id` | ObjectId | 100.0% | - |
| `data` | object | 100.0% | - |
| `data.analysis_results` | array | 100.0% | - |
| `data.analysis_tasks` | array<object> | 100.0% | - |
| `data.datasource_groupings` | array<object> | 100.0% | - |
| `data.debate_records` | array | 100.0% | - |
| `data.llm_providers` | array<object> | 100.0% | - |
| `data.market_categories` | array<object> | 100.0% | - |
| `data.model_catalog` | array<object> | 100.0% | - |
| `data.platform_configs` | array<object> | 100.0% | - |
| `data.system_configs` | array<object> | 100.0% | - |
| `data.user_configs` | array | 100.0% | - |
| `data.user_tags` | array<object> | 100.0% | - |
| `data.users` | array<object> | 100.0% | - |
| `export_info` | object | 100.0% | - |
| `export_info.collections` | array<string> | 100.0% | - |
| `export_info.created_at` | string | 100.0% | 2025-11-11T11:56:07.776033 |
| `export_info.format` | string | 100.0% | json |

---

## license_cache

**文档数量**: 3

**分析样本**: 3 条

### 字段列表

| 字段路径 | 类型 | 出现率 | 示例值 |
|---------|------|--------|--------|
| `_id` | ObjectId | 100.0% | - |
| `cache_expires_at` | datetime | 100.0% | 2026-01-18T17:53:48.293000 |
| `device_registered` | boolean | 100.0% | False |
| `email` | string | 100.0% | hsliup@163.com |
| `features` | array<string> | 100.0% | - |
| `machine_id` | string | 100.0% | 94c67460bfa6a51ccbf818d48bfc2c52ca4d37cb2aa9602... |
| `plan` | string | 100.0% | trial |
| `pro_expire_at` | null, string | 100.0% | 2026-12-07T09:50:48.503000 |
| `token_hash` | string | 100.0% | 93f0f743aa06041a8ecc92b198e49d1689b7acbb1db32fe... |
| `trial_end_at` | string | 100.0% | 2026-02-04T15:37:42.885971 |
| `updated_at` | datetime | 100.0% | 2026-01-11T17:53:48.293000 |
| `verified_at` | datetime | 100.0% | 2026-01-11T17:53:48.293000 |

---

## llm_providers

**文档数量**: 10

**分析样本**: 10 条

### 字段列表

| 字段路径 | 类型 | 出现率 | 示例值 |
|---------|------|--------|--------|
| `_id` | ObjectId | 100.0% | - |
| `aggregator_type` | null | 50.0% | - |
| `api_doc_url` | string | 100.0% | https://platform.openai.com/docs |
| `api_key` | string | 100.0% |  |
| `api_secret` | null, string | 70.0% |  |
| `created_at` | datetime | 100.0% | 2025-08-18T08:56:05.447000 |
| `default_base_url` | string | 100.0% | https://api.openai.com/v1 |
| `description` | string | 100.0% | OpenAI是人工智能领域的领先公司，提供GPT系列模型 |
| `display_name` | string | 100.0% | OpenAI |
| `embedding_model` | null, string | 40.0% | text-embedding-v4 |
| `extra_config` | object | 100.0% | - |
| `extra_config.has_api_key` | string, boolean | 40.0% | True |
| `extra_config.has_api_secret` | string, boolean | 40.0% | False |
| `extra_config.migrated_at` | string, datetime | 50.0% | 2025-08-18T12:31:27.795000 |
| `extra_config.migrated_from` | string | 20.0% | environment |
| `extra_config.source` | string | 60.0% | database |
| `is_active` | boolean | 100.0% | False |
| `is_aggregator` | boolean | 50.0% | False |
| `logo_url` | null | 70.0% | - |
| `model_name_format` | null | 50.0% | - |
| `name` | string | 100.0% | openai |
| `supported_features` | array<string> | 100.0% | - |
| `updated_at` | datetime | 100.0% | 2025-08-18T11:22:13.672000 |
| `website` | string | 100.0% | https://openai.com |

---

## market_categories

**文档数量**: 3

**分析样本**: 3 条

### 字段列表

| 字段路径 | 类型 | 出现率 | 示例值 |
|---------|------|--------|--------|
| `_id` | ObjectId | 100.0% | - |
| `created_at` | datetime | 100.0% | 2025-08-19T01:05:29.089000 |
| `description` | string | 100.0% | 中国A股市场数据源 |
| `display_name` | string | 100.0% | A股 |
| `enabled` | boolean | 100.0% | True |
| `id` | string | 100.0% | a_shares |
| `name` | string | 100.0% | a_shares |
| `sort_order` | integer | 100.0% | 1 |
| `updated_at` | datetime | 100.0% | 2025-08-19T01:05:29.089000 |

---

## market_quotes

**文档数量**: 5,804

**分析样本**: 100 条

### 字段列表

| 字段路径 | 类型 | 出现率 | 示例值 |
|---------|------|--------|--------|
| `_id` | ObjectId | 100.0% | - |
| `amount` | float | 100.0% | 981119838.0 |
| `change` | float | 99.0% | -0.08 |
| `change_percent` | float | 1.0% | -0.43 |
| `circ_mv` | null | 1.0% | - |
| `close` | float | 100.0% | 10.94 |
| `code` | string | 100.0% | 000001 |
| `current_price` | float | 1.0% | 10.99 |
| `data_source` | string | 1.0% | local |
| `data_version` | integer | 1.0% | 1 |
| `full_symbol` | string | 1.0% | 000001.SZ |
| `high` | null | 100.0% | - |
| `last_sync` | datetime | 1.0% | 2026-01-11T05:14:11.494000 |
| `low` | null | 100.0% | - |
| `market` | string | 1.0% | CN |
| `market_info` | object | 1.0% | - |
| `market_info.currency` | string | 1.0% | CNY |
| `market_info.exchange` | string | 1.0% | SZSE |
| `market_info.exchange_name` | string | 1.0% | 深圳证券交易所 |
| `market_info.market_type` | string | 1.0% | CN |
| `market_info.timezone` | string | 1.0% | Asia/Shanghai |
| `name` | string | 100.0% | 股票000001 |
| `num` | integer | 100.0% | 46871 |
| `open` | null | 100.0% | - |
| `pb` | null | 1.0% | - |
| `pct_chg` | float | 100.0% | -0.182 |
| `pe` | null | 1.0% | - |
| `pe_ttm` | null | 1.0% | - |
| `pre_close` | null | 100.0% | - |
| `price` | float | 1.0% | 11.46 |
| `symbol` | string | 100.0% | 000001 |
| `sync_status` | string | 1.0% | success |
| `timestamp` | string | 1.0% | 2026-01-25 11:44:36 |
| `total_mv` | null | 1.0% | - |
| `trade_date` | string | 100.0% | 20260127 |
| `ts_code` | string | 100.0% | 000001.SZ |
| `turnover_rate` | null | 1.0% | - |
| `updated_at` | datetime | 100.0% | 2026-01-27T08:12:37.458000 |
| `volume` | null | 100.0% | - |
| `volume_ratio` | float | 1.0% | 1.02 |

---

## market_quotes_hk

**文档数量**: 0

**分析样本**: 0 条

---

## market_quotes_us

**文档数量**: 0

**分析样本**: 0 条

---

## model_catalog

**文档数量**: 10

**分析样本**: 10 条

### 字段列表

| 字段路径 | 类型 | 出现率 | 示例值 |
|---------|------|--------|--------|
| `_id` | ObjectId | 100.0% | - |
| `created_at` | datetime | 100.0% | 2026-01-18T02:18:13.117000 |
| `models` | array<object> | 100.0% | - |
| `provider` | string | 100.0% | dashscope |
| `provider_name` | string | 100.0% | 通义千问 |
| `updated_at` | datetime | 100.0% | 2026-01-18T02:18:13.121000 |

---

## notifications

**文档数量**: 149

**分析样本**: 100 条

### 字段列表

| 字段路径 | 类型 | 出现率 | 示例值 |
|---------|------|--------|--------|
| `_id` | ObjectId | 100.0% | - |
| `content` | string | 100.0% | ---

 风险管理委员会主席决策报告  
主题：关于荣盛发展的最终投资建议  
日期：202... |
| `created_at` | datetime | 100.0% | 2025-11-04T09:59:25.090000 |
| `link` | string | 100.0% | /stocks/002146 |
| `metadata` | object | 100.0% | - |
| `metadata.analysis_date` | string | 4.0% | 2025-12-03 |
| `metadata.failed` | integer | 4.0% | 0 |
| `metadata.stocks` | array<object>, array | 4.0% | - |
| `metadata.success` | integer | 4.0% | 4 |
| `metadata.total` | integer | 4.0% | 4 |
| `severity` | string | 100.0% | info |
| `source` | string | 100.0% | analysis |
| `status` | string | 100.0% | unread |
| `title` | string | 100.0% | 002146 分析完成 |
| `type` | string | 100.0% | analysis |
| `user_id` | string | 100.0% | 6909bbda40956de8421064ff |

---

## operation_logs

**文档数量**: 4,905

**分析样本**: 100 条

### 字段列表

| 字段路径 | 类型 | 出现率 | 示例值 |
|---------|------|--------|--------|
| `_id` | ObjectId | 100.0% | - |
| `action` | string | 100.0% | 用户登录 |
| `action_type` | string | 100.0% | user_login |
| `created_at` | datetime | 100.0% | 2025-11-04T09:01:44.470000 |
| `details` | object | 100.0% | - |
| `details.changed_keys` | array<string> | 1.0% | - |
| `details.login_method` | string | 9.0% | password |
| `details.method` | string | 85.0% | POST |
| `details.path` | string | 85.0% | /api/screening/run |
| `details.provider_id` | string | 1.0% | 68f9dea2b011bd68cbf19ca0 |
| `details.query_params` | null | 85.0% | - |
| `details.reason` | string | 5.0% | 用户名或密码错误 |
| `details.status_code` | integer | 85.0% | 200 |
| `duration_ms` | null, integer | 100.0% | 37 |
| `error_message` | null, string | 100.0% | 用户名或密码错误 |
| `ip_address` | null, string | 100.0% | 127.0.0.1 |
| `session_id` | null | 100.0% | - |
| `success` | boolean | 100.0% | False |
| `timestamp` | datetime | 100.0% | 2025-11-04T09:01:44.470000 |
| `user_agent` | null, string | 100.0% | Mozilla/5.0 (Windows NT 10.0; Win64; x64) Apple... |
| `user_id` | string | 100.0% | unknown |
| `username` | string | 100.0% | admin |

---

## paper_accounts

**文档数量**: 5

**分析样本**: 5 条

### 字段列表

| 字段路径 | 类型 | 出现率 | 示例值 |
|---------|------|--------|--------|
| `_id` | ObjectId | 100.0% | - |
| `cash` | object | 100.0% | - |
| `cash.CNY` | float | 100.0% | 960859.0 |
| `cash.HKD` | float | 100.0% | 1000000.0 |
| `cash.USD` | float | 100.0% | 100000.0 |
| `created_at` | string | 100.0% | 2025-11-04T09:01:54.685379 |
| `realized_pnl` | object | 100.0% | - |
| `realized_pnl.CNY` | float | 100.0% | 0.0 |
| `realized_pnl.HKD` | float | 100.0% | 0.0 |
| `realized_pnl.USD` | float | 100.0% | 0.0 |
| `settings` | object | 80.0% | - |
| `settings.auto_currency_conversion` | boolean | 80.0% | False |
| `settings.default_market` | string | 80.0% | CN |
| `updated_at` | string | 100.0% | 2025-11-12T07:32:57.854884 |
| `user_id` | string | 100.0% | 6909bbda40956de8421064ff |

---

## paper_market_rules

**文档数量**: 3

**分析样本**: 3 条

### 字段列表

| 字段路径 | 类型 | 出现率 | 示例值 |
|---------|------|--------|--------|
| `_id` | ObjectId | 100.0% | - |
| `currency` | string | 100.0% | CNY |
| `market` | string | 100.0% | CN |
| `market_name` | string | 100.0% | A股市场 |
| `rules` | object | 100.0% | - |
| `rules.commission` | object | 100.0% | - |
| `rules.commission.min` | float | 100.0% | 5.0 |
| `rules.commission.rate` | float | 100.0% | 0.0003 |
| `rules.commission.sec_fee_rate` | float | 33.3% | 2.78e-05 |
| `rules.commission.settlement_fee_rate` | float | 33.3% | 2e-05 |
| `rules.commission.stamp_duty_rate` | float | 66.7% | 0.001 |
| `rules.commission.trading_fee_rate` | float | 33.3% | 5e-05 |
| `rules.commission.transaction_levy_rate` | float | 33.3% | 5e-05 |
| `rules.commission.transfer_fee_rate` | float | 33.3% | 2e-05 |
| `rules.lot_size` | null, integer | 100.0% | 100 |
| `rules.min_price_tick` | float | 100.0% | 0.01 |
| `rules.price_limit` | object | 100.0% | - |
| `rules.price_limit.down_limit` | float | 33.3% | -10.0 |
| `rules.price_limit.enabled` | boolean | 100.0% | True |
| `rules.price_limit.kcb_down_limit` | float | 33.3% | -20.0 |
| `rules.price_limit.kcb_up_limit` | float | 33.3% | 20.0 |
| `rules.price_limit.st_down_limit` | float | 33.3% | -5.0 |
| `rules.price_limit.st_up_limit` | float | 33.3% | 5.0 |
| `rules.price_limit.up_limit` | float | 33.3% | 10.0 |
| `rules.short_selling` | object | 100.0% | - |
| `rules.short_selling.enabled` | boolean | 100.0% | False |
| `rules.short_selling.margin_requirement` | float | 33.3% | 1.4 |
| `rules.short_selling.min_account_equity` | integer | 33.3% | 25000 |
| `rules.short_selling.pdt_rule` | boolean | 33.3% | True |
| `rules.t_plus` | integer | 100.0% | 1 |
| `rules.trading_hours` | object | 100.0% | - |
| `rules.trading_hours.call_auction` | array<object> | 66.7% | - |
| `rules.trading_hours.extended_hours` | object | 33.3% | - |
| `rules.trading_hours.sessions` | array<object> | 100.0% | - |
| `rules.trading_hours.timezone` | string | 100.0% | Asia/Shanghai |

---

## paper_orders

**文档数量**: 7

**分析样本**: 7 条

### 字段列表

| 字段路径 | 类型 | 出现率 | 示例值 |
|---------|------|--------|--------|
| `_id` | ObjectId | 100.0% | - |
| `amount` | float | 100.0% | 14530.0 |
| `code` | string | 100.0% | 09988 |
| `commission` | float | 100.0% | 6.1 |
| `created_at` | string | 100.0% | 2025-12-19T09:18:07.512691 |
| `currency` | string | 100.0% | HKD |
| `filled_at` | string | 100.0% | 2025-12-19T09:18:07.512691 |
| `market` | string | 100.0% | HK |
| `price` | float | 100.0% | 145.3000030517578 |
| `quantity` | integer | 100.0% | 100 |
| `side` | string | 100.0% | buy |
| `status` | string | 100.0% | filled |
| `user_id` | string | 100.0% | 6915d05ac52e760d74ed36a2 |

---

## paper_positions

**文档数量**: 5

**分析样本**: 5 条

### 字段列表

| 字段路径 | 类型 | 出现率 | 示例值 |
|---------|------|--------|--------|
| `_id` | ObjectId | 100.0% | - |
| `available_qty` | integer | 100.0% | 100 |
| `avg_cost` | float | 100.0% | 145.3000030517578 |
| `code` | string | 100.0% | 09988 |
| `currency` | string | 100.0% | HKD |
| `frozen_qty` | integer | 100.0% | 0 |
| `market` | string | 100.0% | HK |
| `name` | string | 100.0% | 港股09988 |
| `quantity` | integer | 100.0% | 100 |
| `updated_at` | string | 100.0% | 2025-12-19T09:18:07.512691 |
| `user_id` | string | 100.0% | 6915d05ac52e760d74ed36a2 |

---

## paper_trades

**文档数量**: 24

**分析样本**: 24 条

### 字段列表

| 字段路径 | 类型 | 出现率 | 示例值 |
|---------|------|--------|--------|
| `_id` | ObjectId | 100.0% | - |
| `amount` | float | 100.0% | 37895.0 |
| `analysis_id` | string | 4.2% | 00700_20251112_111929 |
| `code` | string | 100.0% | 300750 |
| `commission` | float | 100.0% | 11.37 |
| `currency` | string | 100.0% | CNY |
| `market` | string | 100.0% | CN |
| `pnl` | float | 100.0% | 0.0 |
| `price` | float | 100.0% | 378.95 |
| `quantity` | integer | 100.0% | 100 |
| `side` | string | 100.0% | buy |
| `timestamp` | string | 100.0% | 2025-11-04T09:47:48.820170 |
| `user_id` | string | 100.0% | 6909bbda40956de8421064ff |

---

## platform_configs

**文档数量**: 4

**分析样本**: 4 条

### 字段列表

| 字段路径 | 类型 | 出现率 | 示例值 |
|---------|------|--------|--------|
| `_id` | ObjectId | 100.0% | - |
| `api_key` | string | 100.0% |  |
| `config_data` | object | 100.0% | - |
| `config_data.max_tokens` | integer | 50.0% | 2000 |
| `config_data.model` | string | 50.0% | deepseek-chat |
| `config_data.priority` | integer | 50.0% | 1 |
| `config_data.temperature` | float | 50.0% | 0.7 |
| `config_type` | string | 100.0% | llm |
| `created_at` | datetime | 100.0% | 2025-08-14T01:47:14.528000 |
| `is_active` | boolean | 100.0% | True |
| `provider` | string | 100.0% | deepseek |
| `updated_at` | datetime | 100.0% | 2025-08-14T01:47:14.528000 |

---

## portfolio_analysis_reports

**文档数量**: 12

**分析样本**: 12 条

### 字段列表

| 字段路径 | 类型 | 出现率 | 示例值 |
|---------|------|--------|--------|
| `_id` | ObjectId | 100.0% | - |
| `ai_analysis` | object | 100.0% | - |
| `ai_analysis.detailed_report` | string | 100.0% |  |
| `ai_analysis.strengths` | array<string>, array | 100.0% | - |
| `ai_analysis.suggestions` | array<string>, array | 100.0% | - |
| `ai_analysis.summary` | string | 100.0% | AI分析暂时不可用: 模型 qwen-plus 的API地址未配置，请在设置页面配置 |
| `ai_analysis.weaknesses` | array<string>, array | 100.0% | - |
| `analysis_date` | string | 100.0% | 2025-12-05 |
| `analysis_id` | string | 100.0% | 169a2e85-6db0-4c64-9f32-b8e77afda3f1 |
| `analysis_type` | string | 100.0% | portfolio_health |
| `concentration_analysis` | object | 100.0% | - |
| `concentration_analysis.hhi_index` | float | 100.0% | 3874.89 |
| `concentration_analysis.industry_count` | integer | 100.0% | 0 |
| `concentration_analysis.stock_count` | integer | 33.3% | 1 |
| `concentration_analysis.top1_pct` | float | 100.0% | 52.17 |
| `concentration_analysis.top3_pct` | float | 100.0% | 100.0 |
| `concentration_analysis.top5_pct` | float | 100.0% | 100.0 |
| `created_at` | datetime | 100.0% | 2025-12-05T13:57:56.446000 |
| `error_message` | null, string | 100.0% | 'ConcentrationAnalysis' object has no attribute... |
| `execution_time` | float | 100.0% | 0.075573 |
| `health_score` | float | 100.0% | 40.0 |
| `industry_distribution` | array<object> | 100.0% | - |
| `portfolio_snapshot` | object | 100.0% | - |
| `portfolio_snapshot.account` | object | 100.0% | - |
| `portfolio_snapshot.account.cash` | float | 100.0% | 985001.0 |
| `portfolio_snapshot.account.cash_ratio` | float | 100.0% | 97.57 |
| `portfolio_snapshot.account.currency` | string | 100.0% | CNY |
| `portfolio_snapshot.account.initial_capital` | float | 100.0% | 1000000.0 |
| `portfolio_snapshot.account.net_capital` | float | 100.0% | 1009500.0 |
| `portfolio_snapshot.account.position_ratio` | float | 100.0% | 2.43 |
| `portfolio_snapshot.account.positions_value` | float | 100.0% | 24509.0 |
| `portfolio_snapshot.account.total_assets` | float | 100.0% | 1009510.0 |
| `portfolio_snapshot.account.total_profit` | float | 100.0% | 10.0 |
| `portfolio_snapshot.account.total_profit_pct` | float | 100.0% | 0.0 |
| `portfolio_snapshot.positions` | array<object> | 100.0% | - |
| `portfolio_snapshot.total_cost` | float | 100.0% | 24499.0 |
| `portfolio_snapshot.total_positions` | integer | 100.0% | 3 |
| `portfolio_snapshot.total_value` | float | 100.0% | 24509.0 |
| `portfolio_snapshot.unrealized_pnl` | float | 100.0% | 10.0 |
| `portfolio_snapshot.unrealized_pnl_pct` | float | 100.0% | 0.04 |
| `risk_level` | string | 100.0% | 高 |
| `status` | string | 100.0% | completed |
| `timestamp` | datetime | 100.0% | 2025-12-05T13:57:56.446000 |
| `tokens_used` | integer | 100.0% | 0 |
| `user_id` | string | 100.0% | 6915d05ac52e760d74ed36a2 |

---

## position_analysis_reports

**文档数量**: 82

**分析样本**: 82 条

### 字段列表

| 字段路径 | 类型 | 出现率 | 示例值 |
|---------|------|--------|--------|
| `_id` | ObjectId | 100.0% | - |
| `ai_analysis` | object | 100.0% | - |
| `ai_analysis.action` | string | 100.0% | hold |
| `ai_analysis.action_reason` | string | 100.0% | AI分析暂时不可用: Connection error. |
| `ai_analysis.confidence` | float | 100.0% | 0.0 |
| `ai_analysis.detailed_analysis` | string | 100.0% |  |
| `ai_analysis.opportunity_assessment` | string | 100.0% |  |
| `ai_analysis.price_targets` | object | 100.0% | - |
| `ai_analysis.price_targets.breakeven_price` | float, null | 100.0% | 64.0967 |
| `ai_analysis.price_targets.stop_loss_pct` | float, null | 100.0% | -6.39 |
| `ai_analysis.price_targets.stop_loss_price` | float, null | 100.0% | 60.0 |
| `ai_analysis.price_targets.take_profit_pct` | float, null | 100.0% | 6.09 |
| `ai_analysis.price_targets.take_profit_price` | float, null | 100.0% | 68.0 |
| `ai_analysis.recommendation` | string | 73.2% |  |
| `ai_analysis.risk_assessment` | string | 100.0% |  |
| `ai_analysis.risk_metrics` | null, object | 100.0% | - |
| `ai_analysis.risk_metrics.available_add_amount` | float | 22.0% | 283671.0 |
| `ai_analysis.risk_metrics.max_loss_amount` | float | 22.0% | 1225.54 |
| `ai_analysis.risk_metrics.max_loss_impact_pct` | float | 22.0% | 0.12 |
| `ai_analysis.risk_metrics.position_pct` | float | 22.0% | 1.9 |
| `ai_analysis.risk_metrics.position_value` | float | 22.0% | 19179.0 |
| `ai_analysis.risk_metrics.risk_level` | string | 22.0% | low |
| `ai_analysis.risk_metrics.risk_summary` | string | 22.0% | 仓位1.9%较轻，有较大加仓空间 |
| `ai_analysis.source` | string | 73.2% | legacy |
| `ai_analysis.suggested_amount` | float, null | 100.0% | 63930.0 |
| `ai_analysis.suggested_quantity` | null, integer | 100.0% | 1000 |
| `ai_analysis.summary` | string | 73.2% |  |
| `analysis_id` | string | 100.0% | 3ded6e11-968a-417a-9a01-84b73b09b5e7 |
| `created_at` | datetime | 100.0% | 2025-12-05T09:03:10.371000 |
| `error_message` | null, string | 100.0% | 未找到 000001 的持仓记录 |
| `execution_time` | float | 100.0% | 66.353807 |
| `position_id` | string | 100.0% | 600660_CN |
| `position_snapshot` | null, object | 100.0% | - |
| `position_snapshot.code` | string | 95.1% | 600660 |
| `position_snapshot.cost_pct` | null | 79.3% | - |
| `position_snapshot.cost_price` | float | 95.1% | 64.0967 |
| `position_snapshot.cost_value` | null | 79.3% | - |
| `position_snapshot.current_price` | float | 95.1% | 63.84 |
| `position_snapshot.holding_days` | integer | 95.1% | 1 |
| `position_snapshot.industry` | string | 95.1% | 汽车配件 |
| `position_snapshot.market` | string | 95.1% | CN |
| `position_snapshot.market_value` | float | 95.1% | 19152.0 |
| `position_snapshot.name` | string | 95.1% | 福耀玻璃 |
| `position_snapshot.position_pct` | float | 95.1% | 1.9 |
| `position_snapshot.quantity` | integer | 95.1% | 300 |
| `position_snapshot.total_capital` | float | 95.1% | 1009500.0 |
| `position_snapshot.unrealized_pnl` | float | 95.1% | -77.0 |
| `position_snapshot.unrealized_pnl_pct` | float | 95.1% | -0.4 |
| `status` | string | 100.0% | completed |
| `stock_analysis_task_id` | null, string | 100.0% | 5a5a8939-5bde-448e-a5d6-c3184ea7ea6d |
| `user_id` | string | 100.0% | 6915d05ac52e760d74ed36a2 |

---

## position_changes

**文档数量**: 8

**分析样本**: 8 条

### 字段列表

| 字段路径 | 类型 | 出现率 | 示例值 |
|---------|------|--------|--------|
| `_id` | ObjectId | 100.0% | - |
| `cash_change` | float | 100.0% | 37742.86 |
| `change_type` | string | 100.0% | sell |
| `code` | string | 100.0% | 300750 |
| `cost_price_after` | float | 100.0% | 377.4286 |
| `cost_price_before` | float | 100.0% | 377.4286 |
| `cost_value_after` | float | 100.0% | 0.0 |
| `cost_value_before` | float | 100.0% | 37742.86 |
| `created_at` | datetime | 100.0% | 2025-12-18T10:08:01.116000 |
| `currency` | string | 100.0% | CNY |
| `description` | string | 100.0% | 清仓: -100股 @ 379.00 |
| `market` | string | 100.0% | CN |
| `name` | string | 100.0% | 宁德时代 |
| `position_id` | string | 100.0% | 6943d0f5918ef93d3789ca18 |
| `quantity_after` | integer | 100.0% | 0 |
| `quantity_before` | integer | 100.0% | 100 |
| `quantity_change` | integer | 100.0% | -100 |
| `realized_profit` | null, float | 100.0% | 157.14 |
| `trade_price` | null, float | 100.0% | 379.0 |
| `trade_time` | datetime | 100.0% | 2025-12-18T10:07:32.696000 |
| `user_id` | string | 100.0% | 6915d05ac52e760d74ed36a2 |

---

## prompt_templates

**文档数量**: 146

**分析样本**: 100 条

### 字段列表

| 字段路径 | 类型 | 出现率 | 示例值 |
|---------|------|--------|--------|
| `_id` | ObjectId | 100.0% | - |
| `agent_id` | string | 100.0% | fundamentals_analyst |
| `agent_name` | string | 100.0% | fundamentals_analyst |
| `agent_type` | string | 100.0% | analysts |
| `base_template_id` | null, ObjectId | 100.0% | - |
| `base_version` | null, integer | 100.0% | 1 |
| `constraints` | string | 6.0% | **⚠️ 重要约束**：
- **必须严格基于用户提示词中提供的实时分析报告进行分析**（包括... |
| `content` | object | 100.0% | - |
| `content.analysis_requirements` | string | 100.0% | 📊 分析要求：
- 基于真实数据进行深度基本面分析
- 计算并提供合理价位区间（使用{curr... |
| `content.constraints` | string | 100.0% | 必须基于真实数据进行分析，不允许假设或编造信息。

⚠️ **重要约束**：本报告由AI自动生... |
| `content.output_format` | string | 100.0% | 请以清晰、结构化的中文格式输出分析结果。 |
| `content.system_prompt` | string | 100.0% | 你是一位专业的股票基本面分析师。
⚠️ 绝对强制要求：你必须调用工具获取真实数据！不允许任何假... |
| `content.tool_guidance` | string | 100.0% | 🔴 立即调用 get_stock_fundamentals_unified 工具
参数：tic... |
| `content.user_prompt` | string | 40.0% | 请综合分析 {{company_name}}（{{ticker}}）的投资机会：

股票代码：... |
| `created_at` | datetime | 100.0% | 2025-11-16T05:26:42.149000 |
| `created_by` | null, ObjectId | 100.0% | - |
| `is_system` | boolean | 100.0% | True |
| `preference_type` | string | 100.0% | neutral |
| `remark` | string | 88.0% |  |
| `status` | string | 100.0% | active |
| `template_name` | string | 100.0% | System Neutral Template |
| `updated_at` | datetime | 100.0% | 2026-01-18T07:46:12.443000 |
| `version` | float, integer | 100.0% | 1 |

---

## quotes_ingestion_status

**文档数量**: 1

**分析样本**: 1 条

### 字段列表

| 字段路径 | 类型 | 出现率 | 示例值 |
|---------|------|--------|--------|
| `_id` | ObjectId | 100.0% | - |
| `data_source` | string | 100.0% | tushare |
| `error_message` | string | 100.0% | 未获取到行情数据 |
| `interval_seconds` | integer | 100.0% | 360 |
| `job` | string | 100.0% | quotes_ingestion |
| `last_sync_time` | datetime | 100.0% | 2026-01-27T07:06:36.739000 |
| `last_sync_time_iso` | string | 100.0% | 2026-01-27T15:06:36.739606+08:00 |
| `records_count` | integer | 100.0% | 0 |
| `success` | boolean | 100.0% | False |
| `updated_at` | datetime | 100.0% | 2026-01-27T07:06:36.739000 |

---

## real_accounts

**文档数量**: 1

**分析样本**: 1 条

### 字段列表

| 字段路径 | 类型 | 出现率 | 示例值 |
|---------|------|--------|--------|
| `_id` | ObjectId | 100.0% | - |
| `cash` | object | 100.0% | - |
| `cash.CNY` | float | 100.0% | 1007630.72 |
| `cash.HKD` | float | 100.0% | 1000000.0 |
| `cash.USD` | float | 100.0% | 1000000.0 |
| `created_at` | datetime | 100.0% | 2025-12-05T07:35:57.421000 |
| `initial_capital` | object | 100.0% | - |
| `initial_capital.CNY` | float | 100.0% | 1000000.0 |
| `initial_capital.HKD` | float | 100.0% | 1000000.0 |
| `initial_capital.USD` | float | 100.0% | 1000000.0 |
| `settings` | object | 100.0% | - |
| `settings.default_market` | string | 100.0% | CN |
| `settings.max_loss_pct` | float | 100.0% | 10.0 |
| `settings.max_position_pct` | float | 100.0% | 30.0 |
| `total_deposit` | object | 100.0% | - |
| `total_deposit.CNY` | float | 100.0% | 10000.0 |
| `total_deposit.HKD` | float | 100.0% | 0.0 |
| `total_deposit.USD` | float | 100.0% | 0.0 |
| `total_withdraw` | object | 100.0% | - |
| `total_withdraw.CNY` | float | 100.0% | 500.0 |
| `total_withdraw.HKD` | float | 100.0% | 0.0 |
| `total_withdraw.USD` | float | 100.0% | 0.0 |
| `updated_at` | datetime | 100.0% | 2026-01-26T04:53:18.435000 |
| `user_id` | string | 100.0% | 6915d05ac52e760d74ed36a2 |

---

## real_positions

**文档数量**: 9

**分析样本**: 9 条

### 字段列表

| 字段路径 | 类型 | 出现率 | 示例值 |
|---------|------|--------|--------|
| `_id` | ObjectId | 100.0% | - |
| `buy_date` | datetime | 100.0% | 2025-12-04T00:00:00 |
| `code` | string | 100.0% | 600660 |
| `cost_price` | float | 100.0% | 64.63 |
| `created_at` | datetime | 100.0% | 2025-12-05T07:44:52.169000 |
| `currency` | string | 100.0% | CNY |
| `industry` | null, string | 88.9% | 建筑工程 |
| `market` | string | 100.0% | CN |
| `name` | string | 100.0% | 福耀玻璃 |
| `notes` | null, string | 88.9% | 减仓:  |
| `quantity` | integer | 100.0% | 0 |
| `source` | string | 100.0% | manual |
| `updated_at` | datetime | 100.0% | 2025-12-05T14:31:04.802000 |
| `user_id` | string | 100.0% | 6915d05ac52e760d74ed36a2 |

---

## scheduled_analysis_configs

**文档数量**: 1

**分析样本**: 1 条

### 字段列表

| 字段路径 | 类型 | 出现率 | 示例值 |
|---------|------|--------|--------|
| `_id` | ObjectId | 100.0% | - |
| `created_at` | datetime | 100.0% | 2025-12-14T14:01:54.961000 |
| `default_analysis_depth` | integer | 100.0% | 3 |
| `default_deep_analysis_model` | string | 100.0% | qwen-max |
| `default_group_ids` | array<string> | 100.0% | - |
| `default_prompt_template_id` | null | 100.0% | - |
| `default_quick_analysis_model` | string | 100.0% | qwen-plus |
| `description` | string | 100.0% |  |
| `enabled` | boolean | 100.0% | True |
| `last_run_at` | datetime | 100.0% | 2026-01-07T03:23:56.927000 |
| `name` | string | 100.0% | test |
| `notify_on_complete` | boolean | 100.0% | True |
| `notify_on_error` | boolean | 100.0% | True |
| `send_email` | boolean | 100.0% | True |
| `time_slots` | array<object> | 100.0% | - |
| `updated_at` | datetime | 100.0% | 2026-01-07T02:42:15.702000 |
| `user_id` | string | 100.0% | 6915d05ac52e760d74ed36a2 |

---

## scheduled_analysis_history

**文档数量**: 2

**分析样本**: 2 条

### 字段列表

| 字段路径 | 类型 | 出现率 | 示例值 |
|---------|------|--------|--------|
| `_id` | ObjectId | 100.0% | - |
| `config_id` | string | 100.0% | 693ec352b7348143b413735a |
| `config_name` | string | 100.0% | test |
| `created_at` | datetime | 100.0% | 2026-01-07T03:00:00.469000 |
| `failed_count` | integer | 100.0% | 0 |
| `result_summary` | null | 100.0% | - |
| `status` | string | 100.0% | success |
| `success_count` | integer | 100.0% | 3 |
| `task_ids` | array<string> | 100.0% | - |
| `time_slot_name` | string | 100.0% | 收盘以后 |
| `total_count` | integer | 100.0% | 3 |

---

## scheduler_executions

**文档数量**: 779

**分析样本**: 100 条

### 字段列表

| 字段路径 | 类型 | 出现率 | 示例值 |
|---------|------|--------|--------|
| `_id` | ObjectId | 100.0% | - |
| `cancel_requested` | boolean | 1.0% | True |
| `current_item` | string | 2.0% | 920978 |
| `error_message` | string | 3.0% | 进程已手动终止 |
| `execution_time` | float, null | 100.0% | 0.018582 |
| `is_manual` | boolean | 100.0% | True |
| `job_id` | string | 100.0% | tushare_financial_sync |
| `job_name` | string | 100.0% | 财务数据同步（Tushare） |
| `processed_items` | integer | 2.0% | 5440 |
| `progress` | integer | 90.0% | 99 |
| `progress_message` | string | 3.0% | 正在同步 920978 财务数据 |
| `scheduled_time` | datetime | 100.0% | 2025-11-06T14:36:28.090000 |
| `status` | string | 100.0% | failed |
| `timestamp` | datetime | 100.0% | 2025-11-06T22:36:28.135000 |
| `total_items` | integer | 2.0% | 5449 |
| `updated_at` | datetime | 3.0% | 2025-11-07T08:16:27.540000 |

---

## scheduler_history

**文档数量**: 73

**分析样本**: 73 条

### 字段列表

| 字段路径 | 类型 | 出现率 | 示例值 |
|---------|------|--------|--------|
| `_id` | ObjectId | 100.0% | - |
| `action` | string | 100.0% | pause |
| `error_message` | null, string | 100.0% | 手动触发执行 (暂停状态: True) |
| `job_id` | string | 100.0% | basics_sync_service |
| `status` | string | 100.0% | success |
| `timestamp` | datetime | 100.0% | 2025-11-05T10:31:55.468000 |

---

## scheduler_metadata

**文档数量**: 1

**分析样本**: 1 条

### 字段列表

| 字段路径 | 类型 | 出现率 | 示例值 |
|---------|------|--------|--------|
| `_id` | ObjectId | 100.0% | - |
| `job_id` | string | 100.0% | watchlist_analysis |
| `updated_at` | datetime | 100.0% | 2025-12-03T17:00:27.015000 |

---

## smtp_config

**文档数量**: 1

**分析样本**: 1 条

### 字段列表

| 字段路径 | 类型 | 出现率 | 示例值 |
|---------|------|--------|--------|
| `_id` | string | 100.0% | default |
| `enabled` | boolean | 100.0% | True |
| `from_email` | string | 100.0% | no-reply@tradingagents.cn |
| `from_name` | string | 100.0% | TradingAgents-CN |
| `host` | string | 100.0% | smtp-relay.brevo.com |
| `password` | string | 100.0% | xsmtpsib-83a6491dc93e56e595378ab2ea3b8b59b9cda6... |
| `port` | integer | 100.0% | 587 |
| `updated_at` | string | 100.0% | 2025-12-07T12:30:50.803591+08:00 |
| `use_ssl` | boolean | 100.0% | False |
| `use_tls` | boolean | 100.0% | True |
| `username` | string | 100.0% | 9c3246001@smtp-brevo.com |

---

## social_media_messages

**文档数量**: 6

**分析样本**: 6 条

### 字段列表

| 字段路径 | 类型 | 出现率 | 示例值 |
|---------|------|--------|--------|
| `_id` | ObjectId | 100.0% | - |
| `author` | object | 100.0% | - |
| `author.author_id` | string | 100.0% | user_001 |
| `author.author_name` | string | 100.0% | 投资达人 |
| `author.avatar_url` | null, string | 100.0% | https://example.com/avatar.jpg |
| `author.followers_count` | integer | 100.0% | 100000 |
| `author.influence_score` | float | 100.0% | 85.5 |
| `author.verified` | boolean | 100.0% | True |
| `content` | string | 100.0% | 今天平安银行表现不错，技术面看有突破迹象，值得关注。 |
| `crawler_version` | string | 100.0% | 1.0 |
| `created_at` | datetime | 100.0% | 2026-01-01T14:03:40.604000 |
| `credibility` | string | 100.0% | high |
| `data_source` | string | 100.0% | manual |
| `engagement` | object | 100.0% | - |
| `engagement.comments` | integer | 100.0% | 30 |
| `engagement.engagement_rate` | float | 100.0% | 5.6 |
| `engagement.likes` | integer | 100.0% | 200 |
| `engagement.shares` | integer | 100.0% | 50 |
| `engagement.views` | integer | 100.0% | 5000 |
| `hashtags` | array<string> | 100.0% | - |
| `importance` | string | 100.0% | medium |
| `keywords` | array<string> | 100.0% | - |
| `language` | string | 100.0% | none |
| `location` | null | 100.0% | - |
| `market` | string | 100.0% | A股 |
| `media_urls` | array<string>, array | 100.0% | - |
| `message_id` | string | 100.0% | weibo_1234567890 |
| `message_type` | string | 100.0% | post |
| `platform` | string | 100.0% | weibo |
| `publish_time` | datetime | 100.0% | 2026-01-01T10:30:00 |
| `sentiment` | string | 100.0% | positive |
| `sentiment_score` | float | 100.0% | 0.7 |
| `symbol` | string | 100.0% | 000001 |
| `topics` | array<string> | 100.0% | - |
| `updated_at` | datetime | 100.0% | 2026-01-01T14:03:40.604000 |

---

## stock_basic_info

**文档数量**: 16,458

**分析样本**: 100 条

### 字段列表

| 字段路径 | 类型 | 出现率 | 示例值 |
|---------|------|--------|--------|
| `_id` | ObjectId | 100.0% | - |
| `area` | string | 100.0% | 深圳 |
| `category` | string | 100.0% | stock_cn |
| `circ_mv` | float | 100.0% | 2122.97271144 |
| `code` | string | 100.0% | 000001 |
| `float_share` | float | 100.0% | 1940560.0653 |
| `full_symbol` | string | 100.0% | 000001.SZ |
| `industry` | string | 100.0% | 银行 |
| `list_date` | string | 100.0% | 19910403 |
| `market` | string | 100.0% | 主板 |
| `name` | string | 100.0% | 平安银行 |
| `pb` | float | 100.0% | 0.4788 |
| `pe` | float | 100.0% | 4.7699 |
| `pe_ttm` | float | 66.0% | 4.9237 |
| `ps` | float | 100.0% | 1.4472 |
| `ps_ttm` | float | 100.0% | 1.5636 |
| `sec` | string | 2.0% | stock_cn |
| `source` | string | 100.0% | tushare |
| `sse` | string | 100.0% | 深圳证券交易所 |
| `symbol` | string | 100.0% | 000001 |
| `total_mv` | float | 100.0% | 2123.00745086 |
| `total_share` | float | 100.0% | 1940591.8198 |
| `turnover_rate` | float | 100.0% | 0.4607 |
| `updated_at` | datetime | 100.0% | 2026-01-27T17:16:41.950000 |
| `volume_ratio` | float | 100.0% | 1.26 |

---

## stock_basic_info_hk

**文档数量**: 40

**分析样本**: 40 条

### 字段列表

| 字段路径 | 类型 | 出现率 | 示例值 |
|---------|------|--------|--------|
| `_id` | ObjectId | 100.0% | - |
| `area` | string | 100.0% | 香港 |
| `code` | string | 100.0% | 00700 |
| `currency` | string | 100.0% | HKD |
| `exchange` | string | 100.0% | HKG |
| `market` | string | 100.0% | 香港交易所 |
| `name` | string | 100.0% | 港股0700.HK |
| `name_en` | string | 100.0% |  |
| `source` | string | 100.0% | yfinance |
| `updated_at` | datetime | 100.0% | 2025-11-08T14:33:46.390000 |

---

## stock_basic_info_us

**文档数量**: 0

**分析样本**: 0 条

---

## stock_daily_quotes

**文档数量**: 10,899

**分析样本**: 100 条

### 字段列表

| 字段路径 | 类型 | 出现率 | 示例值 |
|---------|------|--------|--------|
| `_id` | ObjectId | 100.0% | - |
| `amount` | float | 100.0% | 2005791408.0 |
| `change` | float | 100.0% | -0.05 |
| `close` | float | 100.0% | 10.96 |
| `code` | string | 100.0% | 000001 |
| `created_at` | datetime | 100.0% | 2025-11-12T13:15:11.579000 |
| `data_source` | string | 100.0% | tushare |
| `full_symbol` | string | 100.0% | 000001.SZ |
| `high` | float | 100.0% | 11.24 |
| `low` | float | 100.0% | 10.93 |
| `market` | string | 100.0% | CN |
| `open` | float | 100.0% | 11.0 |
| `pct_chg` | float | 100.0% | -0.4541 |
| `period` | string | 100.0% | daily |
| `pre_close` | float | 100.0% | 11.01 |
| `symbol` | string | 100.0% | 000001 |
| `trade_date` | string | 100.0% | 2024-11-12 |
| `updated_at` | datetime | 100.0% | 2025-11-12T13:15:11.579000 |
| `version` | integer | 100.0% | 1 |
| `volume` | float | 100.0% | 171766255.0 |

---

## stock_daily_quotes_hk

**文档数量**: 0

**分析样本**: 0 条

---

## stock_daily_quotes_us

**文档数量**: 0

**分析样本**: 0 条

---

## stock_financial_data

**文档数量**: 51

**分析样本**: 51 条

### 字段列表

| 字段路径 | 类型 | 出现率 | 示例值 |
|---------|------|--------|--------|
| `_id` | ObjectId | 100.0% | - |
| `accounts_receiv` | float, null | 45.1% | 9588403887.99 |
| `admin_exp` | float | 45.1% | 27649000000.0 |
| `adminexp_of_gr` | float | 45.1% | 27.4655 |
| `ann_date` | string | 45.1% | 20251025 |
| `assets_to_eqt` | float | 45.1% | 11.1342 |
| `c_cash_equ_beg_period` | float | 45.1% | 256946000000.0 |
| `c_cash_equ_end_period` | float | 45.1% | 234838000000.0 |
| `ca_to_assets` | float, null | 45.1% | 68.8887 |
| `cash_ratio` | float, null | 45.1% | 0.474 |
| `code` | string | 100.0% | 000001 |
| `cogs_of_sales` | float, null | 45.1% | 90.4156 |
| `created_at` | datetime | 100.0% | 2026-01-19T14:09:04.781000 |
| `current_ratio` | float, null | 45.1% | 1.3056 |
| `data_source` | string | 100.0% | tushare |
| `debt_to_assets` | float | 45.1% | 91.0187 |
| `dp_assets_to_eqt` | float | 45.1% | 11.3906 |
| `expense_of_sales` | float, null | 45.1% | 9.1324 |
| `fin_exp` | float, null | 45.1% | 5066422781.37 |
| `finaexp_of_gr` | float, null | 45.1% | 3.1393 |
| `fix_assets` | null, float | 45.1% | 7928000000.0 |
| `full_symbol` | string | 96.1% | 000001.SZ |
| `gross_margin` | float, null | 45.1% | 9.5844 |
| `inventories` | float, null | 45.1% | 423076154871.16 |
| `market` | string | 96.1% | CN |
| `money_cap` | float, null | 45.1% | 65677132971.18 |
| `n_cashflow_act` | float | 45.1% | 71783000000.0 |
| `n_cashflow_fin_act` | null | 45.1% | - |
| `n_cashflow_inv_act` | float | 45.1% | -13245000000.0 |
| `nca_to_assets` | float, null | 45.1% | 31.1113 |
| `net_income` | null, float | 100.0% | 38339000000.0 |
| `net_profit` | float | 45.1% | 38339000000.0 |
| `net_profit_ttm` | float, null | 45.1% | 4591449390.8 |
| `netprofit_margin` | float | 45.1% | 38.0846 |
| `oper_cost` | float, null | 45.1% | 145920289137.58 |
| `oper_exp` | null, float | 45.1% | 54571000000.0 |
| `oper_profit` | null | 45.1% | - |
| `oper_rev` | null | 45.1% | - |
| `profit_to_gr` | float | 45.1% | 38.0846 |
| `quick_ratio` | float, null | 45.1% | 0.6002 |
| `raw_data` | object | 45.1% | - |
| `raw_data.balance_sheet` | array<object> | 45.1% | - |
| `raw_data.cashflow_statement` | array<object> | 45.1% | - |
| `raw_data.financial_indicators` | array<object> | 45.1% | - |
| `raw_data.income_statement` | array<object> | 45.1% | - |
| `raw_data.main_business` | array<object> | 45.1% | - |
| `rd_exp` | float, null | 45.1% | 345237221.56 |
| `report_period` | string | 100.0% | 20250930 |
| `report_type` | string | 100.0% | quarterly |
| `revenue` | null, float | 100.0% | 100668000000.0 |
| `revenue_ttm` | float, null | 45.1% | 65377234740.4 |
| `roa` | float, null | 45.1% | -1.7282 |
| `roa2` | null | 45.1% | - |
| `roe` | float | 45.1% | 7.5711 |
| `roe_dt` | float | 45.1% | 7.5573 |
| `roe_waa` | float | 45.1% | 8.28 |
| `saleexp_to_gr` | float, null | 45.1% | 2.9873 |
| `symbol` | string | 100.0% | 000001 |
| `total_assets` | null, float | 100.0% | 5766764000000.0 |
| `total_cur_assets` | float, null | 45.1% | 782985589263.99 |
| `total_cur_liab` | float, null | 45.1% | 599690825407.5 |
| `total_equity` | null, float | 100.0% | 517930000000.0 |
| `total_liab` | float | 45.1% | 5248834000000.0 |
| `total_nca` | float, null | 45.1% | 353608976491.3 |
| `total_ncl` | float, null | 45.1% | 235873667768.61 |
| `total_profit` | float | 45.1% | 45920000000.0 |
| `ts_code` | string | 45.1% | 000001.SZ |
| `updated_at` | datetime | 100.0% | 2026-01-19T14:09:04.781000 |
| `version` | integer | 96.1% | 1 |

---

## stock_financial_data_hk

**文档数量**: 0

**分析样本**: 0 条

---

## stock_financial_data_us

**文档数量**: 0

**分析样本**: 0 条

---

## stock_news

**文档数量**: 625

**分析样本**: 100 条

### 字段列表

| 字段路径 | 类型 | 出现率 | 示例值 |
|---------|------|--------|--------|
| `_id` | ObjectId | 100.0% | - |
| `author` | string | 100.0% |  |
| `category` | string | 100.0% | general |
| `content` | string | 100.0% | 中芯国际116.28-1.42-7.64电子300059东方财富24.33-0.65-5.24... |
| `created_at` | datetime | 100.0% | 2025-11-20T03:12:08.758000 |
| `data_source` | string | 100.0% | akshare |
| `full_symbol` | string | 100.0% | 688981.SH |
| `importance` | string | 100.0% | low |
| `keywords` | array<string>, array | 100.0% | - |
| `market` | string | 100.0% | CN |
| `publish_time` | datetime | 100.0% | 2025-11-19T17:18:39 |
| `sentiment` | string | 100.0% | neutral |
| `sentiment_score` | float | 100.0% | 0.0 |
| `source` | string | 100.0% | 证券时报网 |
| `summary` | string | 100.0% |  |
| `symbol` | string | 100.0% | 688981 |
| `symbols` | array<string> | 100.0% | - |
| `title` | string | 100.0% | 主力动向：11月19日特大单净流出207.83亿元 |
| `updated_at` | datetime | 100.0% | 2025-11-20T03:12:08.758000 |
| `url` | string | 100.0% | http://finance.eastmoney.com/a/2025111935688562... |
| `version` | integer | 100.0% | 1 |

---

## stock_news_hk

**文档数量**: 0

**分析样本**: 0 条

---

## stock_news_us

**文档数量**: 0

**分析样本**: 0 条

---

## stock_screening_view

**文档数量**: 16,458

**分析样本**: 100 条

### 字段列表

| 字段路径 | 类型 | 出现率 | 示例值 |
|---------|------|--------|--------|
| `_id` | ObjectId | 100.0% | - |
| `amount` | float | 100.0% | 981119838.0 |
| `area` | string | 100.0% | 深圳 |
| `circ_mv` | float | 100.0% | 2122.97271144 |
| `close` | float | 100.0% | 10.94 |
| `code` | string | 100.0% | 000001 |
| `financial_updated_at` | datetime | 3.0% | 2026-01-19T14:09:04.781000 |
| `gross_margin` | float, null | 3.0% | 9.5844 |
| `high` | null | 100.0% | - |
| `industry` | string | 100.0% | 银行 |
| `list_date` | string | 100.0% | 19910403 |
| `low` | null | 100.0% | - |
| `market` | string | 100.0% | 主板 |
| `name` | string | 100.0% | 平安银行 |
| `netprofit_margin` | float | 3.0% | 38.0846 |
| `open` | null | 100.0% | - |
| `pb` | float | 100.0% | 0.4788 |
| `pct_chg` | float | 100.0% | -0.182 |
| `pe` | float | 100.0% | 4.7699 |
| `pe_ttm` | float | 66.0% | 4.9237 |
| `pre_close` | null | 100.0% | - |
| `quote_updated_at` | datetime | 100.0% | 2026-01-27T08:12:37.458000 |
| `report_period` | string | 3.0% | 20250930 |
| `roa` | float, null | 3.0% | -1.7282 |
| `roe` | float | 3.0% | 7.5711 |
| `source` | string | 100.0% | tushare |
| `total_mv` | float | 100.0% | 2123.00745086 |
| `trade_date` | string | 100.0% | 20260127 |
| `turnover_rate` | float | 100.0% | 0.4607 |
| `updated_at` | datetime | 100.0% | 2026-01-27T17:16:41.950000 |
| `volume` | null | 100.0% | - |
| `volume_ratio` | float | 100.0% | 1.26 |

---

## sync_status

**文档数量**: 1

**分析样本**: 1 条

### 字段列表

| 字段路径 | 类型 | 出现率 | 示例值 |
|---------|------|--------|--------|
| `_id` | ObjectId | 100.0% | - |
| `data_sources_used` | array<string> | 100.0% | - |
| `data_type` | string | 100.0% | stock_basics |
| `errors` | integer | 100.0% | 0 |
| `finished_at` | string | 100.0% | 2026-01-27T17:16:42.623659 |
| `inserted` | integer | 100.0% | 0 |
| `job` | string | 100.0% | stock_basics_multi_source |
| `last_trade_date` | string | 100.0% | 20260127 |
| `message` | null | 100.0% | - |
| `source_stats` | object | 100.0% | - |
| `started_at` | string | 100.0% | 2026-01-27T17:16:40.744044 |
| `status` | string | 100.0% | success |
| `total` | integer | 100.0% | 5473 |
| `updated` | integer | 100.0% | 5473 |

---

## system_configs

**文档数量**: 47

**分析样本**: 47 条

### 字段列表

| 字段路径 | 类型 | 出现率 | 示例值 |
|---------|------|--------|--------|
| `_id` | ObjectId | 100.0% | - |
| `config_name` | string | 100.0% | 默认配置 |
| `config_type` | string | 100.0% | imported |
| `created_at` | datetime | 100.0% | 2025-10-20T08:41:49.742000 |
| `created_by` | null | 100.0% | - |
| `data_source_configs` | array<object> | 100.0% | - |
| `database_configs` | array<object> | 100.0% | - |
| `default_data_source` | string | 100.0% | AKShare |
| `default_llm` | string | 100.0% | qwen3-max |
| `is_active` | boolean | 100.0% | False |
| `llm_configs` | array<object> | 100.0% | - |
| `system_settings` | object | 100.0% | - |
| `system_settings.app_timezone` | string | 100.0% | Asia/Shanghai |
| `system_settings.auto_create_dirs` | boolean | 38.3% | False |
| `system_settings.auto_save_usage` | boolean | 100.0% | False |
| `system_settings.cache_ttl` | integer | 100.0% | 3600 |
| `system_settings.cost_alert_threshold` | integer | 100.0% | 100 |
| `system_settings.currency_preference` | string | 100.0% | CNY |
| `system_settings.deep_analysis_model` | string | 100.0% | qwen-plus |
| `system_settings.default_analysis_timeout` | integer | 100.0% | 300 |
| `system_settings.default_embedding_model` | string | 36.2% | dashscope:text-embedding-v4 |
| `system_settings.default_model` | string | 100.0% | qwen-turbo |
| `system_settings.default_provider` | string | 100.0% | dashscope |
| `system_settings.enable_cache` | boolean | 100.0% | True |
| `system_settings.enable_cost_tracking` | boolean | 100.0% | True |
| `system_settings.enable_monitoring` | boolean | 100.0% | True |
| `system_settings.http_proxy` | string | 63.8% | 127.0.0.1:10809 |
| `system_settings.https_proxy` | string | 63.8% | 127.0.0.1:10809 |
| `system_settings.log_level` | string | 100.0% | INFO |
| `system_settings.max_concurrent_tasks` | integer | 100.0% | 3 |
| `system_settings.no_proxy` | string | 63.8% | localhost,127.0.0.1,eastmoney.com,push2.eastmon... |
| `system_settings.proxy_enabled` | boolean | 44.7% | False |
| `system_settings.queue_cleanup_interval_seconds` | integer | 100.0% | 60 |
| `system_settings.queue_poll_interval_seconds` | integer | 100.0% | 1 |
| `system_settings.quick_analysis_model` | string | 100.0% | qwen-turbo |
| `system_settings.sse_batch_max_idle_seconds` | integer | 100.0% | 600 |
| `system_settings.sse_batch_poll_interval_seconds` | integer | 100.0% | 2 |
| `system_settings.sse_heartbeat_interval_seconds` | integer | 100.0% | 10 |
| `system_settings.sse_poll_timeout_seconds` | integer | 100.0% | 1 |
| `system_settings.sse_task_max_idle_seconds` | integer | 100.0% | 300 |
| `system_settings.ta_china_min_api_interval_seconds` | float | 100.0% | 0.5 |
| `system_settings.ta_google_news_sleep_max_seconds` | integer | 100.0% | 6 |
| `system_settings.ta_google_news_sleep_min_seconds` | integer | 100.0% | 2 |
| `system_settings.ta_hk_cache_ttl_seconds` | integer | 100.0% | 86400 |
| `system_settings.ta_hk_max_retries` | integer | 100.0% | 3 |
| `system_settings.ta_hk_min_request_interval_seconds` | integer | 100.0% | 2 |
| `system_settings.ta_hk_rate_limit_wait_seconds` | integer | 100.0% | 60 |
| `system_settings.ta_hk_timeout_seconds` | integer | 100.0% | 60 |
| `system_settings.ta_us_min_api_interval_seconds` | integer | 100.0% | 1 |
| `system_settings.ta_use_app_cache` | boolean | 100.0% | True |
| `system_settings.worker_heartbeat_interval_seconds` | integer | 100.0% | 30 |
| `updated_at` | datetime | 100.0% | 2025-10-29T00:50:08.019000 |
| `updated_by` | null | 100.0% | - |
| `version` | integer | 100.0% | 18 |

---

## template_history

**文档数量**: 364

**分析样本**: 100 条

### 字段列表

| 字段路径 | 类型 | 出现率 | 示例值 |
|---------|------|--------|--------|
| `_id` | ObjectId | 100.0% | - |
| `change_description` | null, string | 100.0% | deleted |
| `change_type` | string | 100.0% | create |
| `content` | object | 100.0% | - |
| `content.analysis_requirements` | string | 100.0% | 📊 分析要求：
- 基于真实数据进行深度基本面分析
- 计算并提供合理价位区间（使用{curr... |
| `content.constraints` | string | 100.0% | 必须基于真实数据进行分析，不允许假设或编造信息。 |
| `content.output_format` | string | 100.0% | 请以清晰、结构化的中文格式输出分析结果。 |
| `content.system_prompt` | string | 100.0% | 你是一位专业的股票基本面分析师。
⚠️ 绝对强制要求：你必须调用工具获取真实数据！不允许任何假... |
| `content.tool_guidance` | string | 100.0% | 🔴 立即调用 get_stock_fundamentals_unified 工具
参数：tic... |
| `created_at` | datetime | 100.0% | 2025-11-16T09:34:02.135000 |
| `template_id` | ObjectId | 100.0% | - |
| `user_id` | null, ObjectId | 100.0% | - |
| `version` | integer | 100.0% | 1 |

---

## token_usage

**文档数量**: 8,300

**分析样本**: 100 条

### 字段列表

| 字段路径 | 类型 | 出现率 | 示例值 |
|---------|------|--------|--------|
| `_created_at` | datetime | 100.0% | 2025-11-04T09:53:40.097000 |
| `_id` | ObjectId | 100.0% | - |
| `analysis_type` | string | 100.0% | stock_analysis |
| `cost` | float | 100.0% | 0.000212 |
| `currency` | string | 100.0% | CNY |
| `input_tokens` | integer | 100.0% | 812 |
| `model_name` | string | 100.0% | qwen-flash |
| `output_tokens` | integer | 100.0% | 60 |
| `provider` | string | 100.0% | dashscope |
| `session_id` | string | 100.0% | dashscope_openai_980 |
| `timestamp` | string | 100.0% | 2025-11-04T17:53:40.097490+08:00 |

---

## tool_agent_bindings

**文档数量**: 38

**分析样本**: 38 条

### 字段列表

| 字段路径 | 类型 | 出现率 | 示例值 |
|---------|------|--------|--------|
| `_id` | ObjectId | 100.0% | - |
| `agent_id` | string | 100.0% | fundamentals_analyst_v2 |
| `created_at` | string | 100.0% | 2025-12-16T02:18:17.903738 |
| `is_active` | boolean | 100.0% | True |
| `priority` | integer | 100.0% | 1 |
| `tool_id` | string | 100.0% | get_stock_fundamentals_unified |
| `updated_at` | string | 100.0% | 2025-12-16T02:18:17.904490 |

---

## tool_configs

**文档数量**: 1

**分析样本**: 1 条

### 字段列表

| 字段路径 | 类型 | 出现率 | 示例值 |
|---------|------|--------|--------|
| `_id` | ObjectId | 100.0% | - |
| `category` | string | 100.0% | market |
| `config` | object | 100.0% | - |
| `config.cache_ttl` | integer | 100.0% | 600 |
| `config.retry_count` | integer | 100.0% | 5 |
| `config.timeout` | integer | 100.0% | 60 |
| `created_at` | string | 100.0% | 2025-12-13T13:10:58.056152 |
| `description` | string | 100.0% | 获取统一格式的股票市场数据 |
| `function_name` | string | 100.0% | get_stock_data_unified |
| `is_active` | boolean | 100.0% | True |
| `is_builtin` | boolean | 100.0% | True |
| `module_path` | string | 100.0% | tradingagents.dataflows.interface |
| `name` | string | 100.0% | 统一股票市场数据 |
| `parameters` | array<object> | 100.0% | - |
| `tool_id` | string | 100.0% | get_stock_market_data_unified |
| `updated_at` | string | 100.0% | 2025-12-14T01:30:25.734678 |

---

## trade_reviews

**文档数量**: 130

**分析样本**: 100 条

### 字段列表

| 字段路径 | 类型 | 出现率 | 示例值 |
|---------|------|--------|--------|
| `_id` | ObjectId | 100.0% | - |
| `ai_review` | object | 100.0% | - |
| `ai_review.actual_pnl` | float | 100.0% | 0.0 |
| `ai_review.avoided_loss` | float | 100.0% | 0.0 |
| `ai_review.discipline_score` | integer | 100.0% | 0 |
| `ai_review.emotion_analysis` | string | 100.0% |  |
| `ai_review.missed_profit` | float, integer | 100.0% | 0.0 |
| `ai_review.optimal_pnl` | float | 100.0% | 0.0 |
| `ai_review.overall_score` | integer | 100.0% | 50 |
| `ai_review.position_analysis` | string | 100.0% |  |
| `ai_review.position_score` | integer | 100.0% | 0 |
| `ai_review.strengths` | array<string>, array | 100.0% | - |
| `ai_review.suggestions` | array<string>, array | 100.0% | - |
| `ai_review.summary` | string, object | 100.0% | AI分析暂时不可用: Connection error. |
| `ai_review.summary.analysis_confidence` | string | 1.0% | medium |
| `ai_review.summary.benchmark_data_available` | boolean | 1.0% | False |
| `ai_review.summary.key_strengths` | array<string> | 1.0% | - |
| `ai_review.summary.overall_assessment` | string | 1.0% | 本次交易在极短持仓周期内实现极高收益率，表现出显著的个股选择能力与合理的操作节奏。尽管部分数据... |
| `ai_review.summary.potential_concerns` | array<string> | 1.0% | - |
| `ai_review.summary.stock_code` | string | 1.0% | 688111 |
| `ai_review.summary.total_profit_amount` | null | 1.0% | - |
| `ai_review.summary.total_return_rate` | float | 1.0% | 0.177 |
| `ai_review.summary.trading_period_days` | integer | 1.0% | 18 |
| `ai_review.timing_analysis` | string | 100.0% |  |
| `ai_review.timing_score` | integer | 100.0% | 0 |
| `ai_review.weaknesses` | array<string>, array | 100.0% | - |
| `created_at` | datetime | 100.0% | 2025-12-07T02:24:51.348000 |
| `error_message` | null | 100.0% | - |
| `execution_time` | float | 100.0% | 65.547329 |
| `is_case_study` | boolean | 100.0% | False |
| `market_snapshot` | object | 100.0% | - |
| `market_snapshot.buy_date_close` | float, null | 100.0% | 11.49 |
| `market_snapshot.buy_date_high` | float, null | 100.0% | 11.58 |
| `market_snapshot.buy_date_low` | float, null | 100.0% | 11.46 |
| `market_snapshot.buy_date_open` | float, null | 100.0% | 11.55 |
| `market_snapshot.kline_data` | array<object>, array | 100.0% | - |
| `market_snapshot.optimal_buy_price` | float, null | 100.0% | 11.46 |
| `market_snapshot.optimal_sell_price` | float, null | 100.0% | 11.58 |
| `market_snapshot.period_high` | float, null | 100.0% | 11.58 |
| `market_snapshot.period_high_date` | null, string | 100.0% | 2025-12-04 |
| `market_snapshot.period_low` | float, null | 100.0% | 11.46 |
| `market_snapshot.period_low_date` | null, string | 100.0% | 2025-12-04 |
| `market_snapshot.sell_date_close` | float, null | 100.0% | 11.49 |
| `market_snapshot.sell_date_high` | float, null | 100.0% | 11.58 |
| `market_snapshot.sell_date_low` | float, null | 100.0% | 11.46 |
| `market_snapshot.sell_date_open` | float, null | 100.0% | 11.55 |
| `review_id` | string | 100.0% | 4113eb45-5ab2-4d1e-9323-122a80d3f24c |
| `review_type` | string | 100.0% | complete_trade |
| `source` | string | 33.0% | paper |
| `status` | string | 100.0% | completed |
| `tags` | array<string>, array | 100.0% | - |
| `trade_info` | object | 100.0% | - |
| `trade_info.avg_buy_price` | float | 100.0% | 284.15 |
| `trade_info.avg_sell_price` | float | 100.0% | 0.0 |
| `trade_info.code` | string | 100.0% | AAPL |
| `trade_info.currency` | string | 100.0% | USD |
| `trade_info.current_price` | null | 4.0% | - |
| `trade_info.first_buy_date` | string | 100.0% | 2025-12-04T10:19:52.409188 |
| `trade_info.holding_days` | integer | 100.0% | 0 |
| `trade_info.is_holding` | boolean | 4.0% | False |
| `trade_info.last_sell_date` | string | 100.0% | 2025-12-04T10:19:52.409188 |
| `trade_info.market` | string | 100.0% | US |
| `trade_info.name` | null, string | 100.0% | 宁德时代 |
| `trade_info.realized_pnl` | float | 100.0% | 0.0 |
| `trade_info.realized_pnl_pct` | float | 100.0% | 0.0 |
| `trade_info.remaining_quantity` | integer | 4.0% | 0 |
| `trade_info.total_buy_amount` | float | 100.0% | 28415.0 |
| `trade_info.total_buy_quantity` | integer | 100.0% | 100 |
| `trade_info.total_commission` | float | 100.0% | 0.0 |
| `trade_info.total_sell_amount` | float | 100.0% | 0.0 |
| `trade_info.total_sell_quantity` | integer | 100.0% | 0 |
| `trade_info.trades` | array<object> | 100.0% | - |
| `trade_info.unrealized_pnl` | float | 4.0% | 0.0 |
| `trade_info.unrealized_pnl_pct` | float | 4.0% | 0.0 |
| `trading_system_id` | string | 29.0% | 694bc27bd639700ce1d9dbea |
| `trading_system_name` | string | 29.0% | 中线价值成长系统 |
| `user_id` | string | 100.0% | 6915d05ac52e760d74ed36a2 |

---

## trading_system_evaluations

**文档数量**: 4

**分析样本**: 4 条

### 字段列表

| 字段路径 | 类型 | 出现率 | 示例值 |
|---------|------|--------|--------|
| `_id` | ObjectId | 100.0% | - |
| `created_at` | datetime | 100.0% | 2026-01-04T07:33:05.905000 |
| `evaluation_id` | string | 100.0% | 695a17b1d029c82e91bee0dc |
| `evaluation_result` | object | 100.0% | - |
| `evaluation_result.detailed_analysis` | string | 100.0% | 该短线趋势追踪系统在选股、择时和纪律方面具备较好基础，尤其在流动性筛选和趋势信号设计上较为合理... |
| `evaluation_result.evaluation_date` | string | 100.0% | 2026-01-04T07:33:05.905534 |
| `evaluation_result.overall_score` | integer | 100.0% | 78 |
| `evaluation_result.strengths` | array<string> | 100.0% | - |
| `evaluation_result.suggestions` | array<string> | 100.0% | - |
| `evaluation_result.weaknesses` | array<string> | 100.0% | - |
| `system_id` | string | 100.0% | 694bc24fd639700ce1d9dbe8 |
| `system_name` | string | 100.0% | 短线趋势追踪系统 |
| `system_version` | string | 100.0% | 1.0.0 |
| `updated_at` | datetime | 100.0% | 2026-01-04T07:33:05.905000 |
| `user_id` | string | 100.0% | 6915d05ac52e760d74ed36a2 |

---

## trading_system_versions

**文档数量**: 3

**分析样本**: 3 条

### 字段列表

| 字段路径 | 类型 | 出现率 | 示例值 |
|---------|------|--------|--------|
| `_id` | ObjectId | 100.0% | - |
| `created_at` | datetime | 100.0% | 2026-01-27T01:43:35.833000 |
| `created_by` | string | 100.0% | 6915d05ac52e760d74ed36a2 |
| `improvement_summary` | string | 100.0% | 初始版本 |
| `snapshot` | object | 100.0% | - |
| `snapshot.created_at` | datetime | 100.0% | 2025-12-24T10:37:47.394000 |
| `snapshot.description` | string | 100.0% | 结合基本面和技术面，寻找价值被低估的成长股，适合上班族 |
| `snapshot.discipline` | object | 100.0% | - |
| `snapshot.discipline.must_do` | array<object> | 100.0% | - |
| `snapshot.discipline.must_not` | array<object> | 100.0% | - |
| `snapshot.discipline.violation_actions` | array | 100.0% | - |
| `snapshot.draft_data` | object | 66.7% | - |
| `snapshot.draft_data.description` | string | 66.7% | 结合基本面和技术面，寻找价值被低估的成长股，适合上班族 |
| `snapshot.draft_data.discipline` | object | 66.7% | - |
| `snapshot.draft_data.holding` | object | 66.7% | - |
| `snapshot.draft_data.name` | string | 66.7% | 中线价值成长系统 |
| `snapshot.draft_data.position` | object | 66.7% | - |
| `snapshot.draft_data.review` | object | 66.7% | - |
| `snapshot.draft_data.risk_management` | object | 66.7% | - |
| `snapshot.draft_data.risk_profile` | string | 66.7% | balanced |
| `snapshot.draft_data.stock_selection` | object | 66.7% | - |
| `snapshot.draft_data.style` | string | 66.7% | medium_term |
| `snapshot.draft_data.timing` | object | 66.7% | - |
| `snapshot.draft_updated_at` | datetime | 66.7% | 2026-01-27T02:05:13.161000 |
| `snapshot.holding` | object | 100.0% | - |
| `snapshot.holding.add_conditions` | array | 100.0% | - |
| `snapshot.holding.reduce_conditions` | array | 100.0% | - |
| `snapshot.holding.review_frequency` | string | 100.0% | weekly |
| `snapshot.holding.switch_conditions` | array | 100.0% | - |
| `snapshot.id` | string | 100.0% | 694bc27bd639700ce1d9dbea |
| `snapshot.is_active` | boolean | 100.0% | True |
| `snapshot.name` | string | 100.0% | 中线价值成长系统 |
| `snapshot.position` | object | 100.0% | - |
| `snapshot.position.max_holdings` | integer | 100.0% | 6 |
| `snapshot.position.max_per_stock` | float | 100.0% | 0.2 |
| `snapshot.position.min_holdings` | integer | 100.0% | 3 |
| `snapshot.position.scaling` | object | 100.0% | - |
| `snapshot.position.total_position` | object | 100.0% | - |
| `snapshot.review` | object | 100.0% | - |
| `snapshot.review.case_save` | object | 100.0% | - |
| `snapshot.review.checklist` | array<string> | 100.0% | - |
| `snapshot.review.frequency` | string | 100.0% | monthly |
| `snapshot.risk_management` | object | 100.0% | - |
| `snapshot.risk_management.logical_stop` | object | 100.0% | - |
| `snapshot.risk_management.stop_loss` | object | 100.0% | - |
| `snapshot.risk_management.take_profit` | object | 100.0% | - |
| `snapshot.risk_management.time_stop` | object | 100.0% | - |
| `snapshot.risk_profile` | string | 100.0% | balanced |
| `snapshot.status` | string | 100.0% | draft |
| `snapshot.stock_selection` | object | 100.0% | - |
| `snapshot.stock_selection.analysis_config` | object | 100.0% | - |
| `snapshot.stock_selection.bonus` | array | 100.0% | - |
| `snapshot.stock_selection.exclude` | array<object> | 100.0% | - |
| `snapshot.stock_selection.must_have` | array<object> | 100.0% | - |
| `snapshot.style` | string | 100.0% | medium_term |
| `snapshot.timing` | object | 100.0% | - |
| `snapshot.timing.confirmation` | array | 100.0% | - |
| `snapshot.timing.entry_signals` | array<object> | 100.0% | - |
| `snapshot.timing.market_condition` | object | 100.0% | - |
| `snapshot.timing.sector_condition` | object | 100.0% | - |
| `snapshot.updated_at` | datetime | 100.0% | 2026-01-27T01:20:59.434000 |
| `snapshot.user_id` | string | 100.0% | 6915d05ac52e760d74ed36a2 |
| `snapshot.version` | string | 100.0% | 1.0.0 |
| `system_id` | string | 100.0% | 694bc27bd639700ce1d9dbea |
| `version` | string | 100.0% | 2.0.0 |

---

## trading_systems

**文档数量**: 2

**分析样本**: 2 条

### 字段列表

| 字段路径 | 类型 | 出现率 | 示例值 |
|---------|------|--------|--------|
| `_id` | ObjectId | 100.0% | - |
| `created_at` | datetime | 100.0% | 2025-12-24T10:37:03.859000 |
| `description` | string | 100.0% | 基于技术面分析，捕捉短期趋势机会，适合有时间盯盘的投资者 |
| `discipline` | object | 100.0% | - |
| `discipline.must_do` | array<object> | 100.0% | - |
| `discipline.must_not` | array<object> | 100.0% | - |
| `discipline.violation_actions` | array | 50.0% | - |
| `holding` | object | 100.0% | - |
| `holding.add_conditions` | array<object>, array | 100.0% | - |
| `holding.reduce_conditions` | array<object>, array | 100.0% | - |
| `holding.review_frequency` | string | 100.0% | daily |
| `holding.switch_conditions` | array | 50.0% | - |
| `is_active` | boolean | 100.0% | False |
| `name` | string | 100.0% | 短线趋势追踪系统 |
| `position` | object | 100.0% | - |
| `position.max_holdings` | integer | 100.0% | 8 |
| `position.max_per_stock` | float | 100.0% | 0.15 |
| `position.min_holdings` | integer | 100.0% | 3 |
| `position.scaling` | object | 50.0% | - |
| `position.total_position` | object | 50.0% | - |
| `position.total_position.bear` | float | 50.0% | 0.2 |
| `position.total_position.bull` | float | 50.0% | 0.8 |
| `position.total_position.range` | float | 50.0% | 0.5 |
| `review` | object | 100.0% | - |
| `review.case_save` | object | 50.0% | - |
| `review.checklist` | array<string> | 100.0% | - |
| `review.frequency` | string | 100.0% | weekly |
| `risk_management` | object | 100.0% | - |
| `risk_management.logical_stop` | object | 50.0% | - |
| `risk_management.stop_loss` | object | 100.0% | - |
| `risk_management.stop_loss.description` | string | 100.0% | 固定7%止损 |
| `risk_management.stop_loss.percentage` | float | 100.0% | 0.07 |
| `risk_management.stop_loss.type` | string | 100.0% | percentage |
| `risk_management.take_profit` | object | 100.0% | - |
| `risk_management.take_profit.description` | string | 100.0% | 跌破5日均线止盈 |
| `risk_management.take_profit.type` | string | 100.0% | trailing |
| `risk_management.time_stop` | object | 50.0% | - |
| `risk_profile` | string | 100.0% | aggressive |
| `status` | string | 50.0% | published |
| `stock_selection` | object | 100.0% | - |
| `stock_selection.analysis_config` | object | 50.0% | - |
| `stock_selection.bonus` | array | 50.0% | - |
| `stock_selection.exclude` | array<object> | 100.0% | - |
| `stock_selection.must_have` | array<object> | 100.0% | - |
| `style` | string | 100.0% | short_term |
| `timing` | object | 100.0% | - |
| `timing.confirmation` | array | 50.0% | - |
| `timing.entry_signals` | array<object> | 100.0% | - |
| `timing.market_condition` | object | 50.0% | - |
| `timing.sector_condition` | object | 50.0% | - |
| `updated_at` | datetime | 100.0% | 2026-01-07T02:36:26.934000 |
| `user_id` | string | 100.0% | 6915d05ac52e760d74ed36a2 |
| `version` | string | 100.0% | 1.0.0 |

---

## unified_analysis_tasks

**文档数量**: 302

**分析样本**: 100 条

### 字段列表

| 字段路径 | 类型 | 出现率 | 示例值 |
|---------|------|--------|--------|
| `_id` | string, ObjectId | 100.0% | 69510ad65424624b0fea7c0d |
| `batch_id` | null | 100.0% | - |
| `completed_at` | null, string, datetime | 100.0% | 2025-12-28T19:34:46.991352+08:00 |
| `cost` | float | 100.0% | 0.0 |
| `created_at` | string | 100.0% | 2025-12-28T18:47:50.432552+08:00 |
| `current_step` | null, string | 100.0% | 使用 workflow 引擎执行 |
| `engine_type` | string | 100.0% | auto |
| `error_message` | null, string | 100.0% | 服务重启，任务已挂起。请手动恢复或取消任务。 |
| `execution_time` | float | 100.0% | 0.0 |
| `max_retries` | integer | 100.0% | 3 |
| `message` | null, string | 82.0% | 工作流执行完成 |
| `preference_type` | string | 100.0% | neutral |
| `progress` | integer | 100.0% | 0 |
| `result` | null, object | 100.0% | - |
| `result._debate_debate_count` | integer | 14.0% | 1 |
| `result._debate_risk_debate_count` | integer | 14.0% | 1 |
| `result._fundamentals_messages` | array | 15.0% | - |
| `result._market_messages` | array | 15.0% | - |
| `result._max_debate_rounds` | integer | 15.0% | 1 |
| `result._max_risk_rounds` | integer | 15.0% | 1 |
| `result._news_messages` | array | 15.0% | - |
| `result._social_messages` | array | 15.0% | - |
| `result.ai_analysis` | object | 53.0% | - |
| `result.ai_analysis.action` | string | 53.0% | hold |
| `result.ai_analysis.action_reason` | string | 53.0% | 工作流分析异常: object dict can't be used in 'await' e... |
| `result.ai_analysis.confidence` | float | 53.0% | 0.0 |
| `result.ai_analysis.detailed_analysis` | string | 53.0% |  |
| `result.ai_analysis.opportunity_assessment` | string | 53.0% |  |
| `result.ai_analysis.price_targets` | object | 53.0% | - |
| `result.ai_analysis.recommendation` | string | 53.0% |  |
| `result.ai_analysis.risk_assessment` | string | 53.0% |  |
| `result.ai_analysis.risk_metrics` | null | 53.0% | - |
| `result.ai_analysis.source` | string | 53.0% | legacy |
| `result.ai_analysis.suggested_amount` | null | 53.0% | - |
| `result.ai_analysis.suggested_quantity` | null | 53.0% | - |
| `result.ai_analysis.summary` | string | 53.0% |  |
| `result.ai_review` | object | 7.0% | - |
| `result.ai_review.actual_pnl` | float | 7.0% | 29900.0 |
| `result.ai_review.attribution_analysis` | string | 7.0% |  |
| `result.ai_review.attribution_score` | integer | 7.0% | 0 |
| `result.ai_review.avoided_loss` | float | 7.0% | 5600.0 |
| `result.ai_review.discipline_score` | integer | 7.0% | 85 |
| `result.ai_review.emotion_analysis` | string | 7.0% | 持仓期间波动较大，最终卖出时远离成本区，未见恐慌或冲动迹象，纪律性良好。 |
| `result.ai_review.emotion_score` | integer | 7.0% | 0 |
| `result.ai_review.missed_profit` | float | 7.0% | 30884.0 |
| `result.ai_review.optimal_pnl` | float | 7.0% | 60784.0 |
| `result.ai_review.overall_score` | integer | 7.0% | 78 |
| `result.ai_review.plan_adherence` | null, string | 7.0% | 本次交易在选股层面基本符合‘中线价值成长系统’要求，标的满足高ROE、高成长、低负债等基本面条... |
| `result.ai_review.plan_deviation` | null, string | 7.0% | 主要偏离在于止盈执行不力：股价最高上涨超25%，已接近第一目标位，但未按计划比例减持；同时全程... |
| `result.ai_review.position_analysis` | string | 7.0% | 全仓一次性买入800股，无分批操作，仓位管理果断但灵活性不足。 |
| `result.ai_review.position_score` | integer | 7.0% | 90 |
| `result.ai_review.strengths` | array<string> | 7.0% | - |
| `result.ai_review.suggestions` | array<string> | 7.0% | - |
| `result.ai_review.summary` | string | 7.0% | 持仓期间个股表现强劲，收益显著跑赢大盘，但未充分把握高点。 |
| `result.ai_review.timing_analysis` | string | 7.0% | 买在相对低位区域，卖在中期涨幅62%位置，但错过11月初冲高至372.98元机会，择时能力中上。 |
| `result.ai_review.timing_score` | integer | 7.0% | 70 |
| `result.ai_review.weaknesses` | array<string> | 7.0% | - |
| `result.analysis_date` | string, datetime | 25.0% | 2025-12-28T00:00:00 |
| `result.analysis_id` | string | 64.0% | 5b73d449-5f07-4f65-83b4-d2cdbd5ccaff |
| `result.analysts` | array<string>, array | 11.0% | - |
| `result.attribution_analysis` | string | 1.0% | ### 收益归因分析报告

#### 1. Beta收益分析
- **基准数据**：同期大盘收... |
| `result.bear_report` | string, object | 15.0% |  |
| `result.bear_report.content` | string | 14.0% | 好的，作为看跌分析师，我将基于您提供的所有报告，对平安银行（股票代码：000001）进行全面的... |
| `result.bear_report.stance` | string | 14.0% | bear |
| `result.bear_report.success` | boolean | 14.0% | True |
| `result.bull_report` | string, object | 15.0% |  |
| `result.bull_report.content` | string | 14.0% | ### **看涨分析报告：平安银行（000001）**

**尊敬的看跌分析师，您好。**

... |
| `result.bull_report.stance` | string | 14.0% | bull |
| `result.bull_report.success` | boolean | 14.0% | True |
| `result.code` | string | 61.0% | 601668 |
| `result.company_of_interest` | string | 14.0% | 000001 |
| `result.confidence_score` | float | 11.0% | 0.0 |
| `result.custom_prompt` | null | 14.0% | - |
| `result.decision` | object | 11.0% | - |
| `result.decision.action` | string | 11.0% | 持有 |
| `result.decision.confidence` | float | 9.0% | 0.7 |
| `result.decision.reasoning` | string | 11.0% | # **平安银行（000001）风险评估报告**  
**分析日期：2025年12月30日**... |
| `result.decision.risk_score` | float | 9.0% | 0.5 |
| `result.decision.summary` | string | 2.0% | # **平安银行（000001）风险评估报告**  
**分析日期：2025年12月30日**... |
| `result.decision.target_price` | null, float | 9.0% | 14.0 |
| `result.deep_analysis_model` | string | 14.0% | qwen-plus |
| `result.detailed_analysis` | object | 11.0% | - |
| `result.detailed_analysis._debate_debate_count` | integer | 6.0% | 1 |
| `result.detailed_analysis._debate_risk_debate_count` | integer | 6.0% | 1 |
| `result.detailed_analysis._fundamentals_messages` | array | 11.0% | - |
| `result.detailed_analysis._market_messages` | array | 11.0% | - |
| `result.detailed_analysis._max_debate_rounds` | integer | 11.0% | 1 |
| `result.detailed_analysis._max_risk_rounds` | integer | 11.0% | 1 |
| `result.detailed_analysis._news_messages` | array | 11.0% | - |
| `result.detailed_analysis._social_messages` | array | 11.0% | - |
| `result.detailed_analysis.analysis_date` | string, datetime | 7.0% | 2025-12-29T00:00:00 |
| `result.detailed_analysis.attribution_analysis` | string | 5.0% | ### 收益归因分析报告

#### 1. Beta收益分析  
大盘同期收益为 **{mar... |
| `result.detailed_analysis.bear_report` | string, object | 11.0% |  |
| `result.detailed_analysis.bull_report` | string, object | 11.0% |  |
| `result.detailed_analysis.code` | string | 5.0% | 688111 |
| `result.detailed_analysis.company_of_interest` | string | 6.0% | 000001 |
| `result.detailed_analysis.custom_prompt` | null | 6.0% | - |
| `result.detailed_analysis.deep_analysis_model` | string | 6.0% | qwen-plus |
| `result.detailed_analysis.emotion_analysis` | string | 5.0% | ### 情绪控制分析报告

基于您提供的交易行为特征数据，以下是对交易中情绪控制表现的客观分析... |
| `result.detailed_analysis.final_trade_decision` | string | 6.0% | # **平安银行（000001）风险评估报告**  
**分析日期：2025年12月30日**... |
| `result.detailed_analysis.fundamentals_report` | string | 11.0% | # **000001（平安银行）基本面分析报告**  
**分析日期：2025年12月29日*... |
| `result.detailed_analysis.fundamentals_tool_call_count` | integer | 11.0% | 0 |
| `result.detailed_analysis.include_risk` | boolean | 6.0% | True |
| `result.detailed_analysis.include_sentiment` | boolean | 6.0% | True |
| `result.detailed_analysis.index_report` | string | 6.0% | ### **2025年12月29日 大盘与指数综合分析报告**  
**——聚焦平安银行（00... |
| `result.detailed_analysis.investment_debate_state` | object | 11.0% | - |
| `result.detailed_analysis.investment_plan` | string, object | 11.0% |  |
| `result.detailed_analysis.language` | string | 6.0% | zh-CN |
| `result.detailed_analysis.lookback_days` | integer | 7.0% | 30 |
| `result.detailed_analysis.market` | string | 5.0% | CN |
| `result.detailed_analysis.market_report` | string | 11.0% | ## 📊 股票基本信息
- 公司名称：平安银行
- 股票代码：000001
- 所属市场：中国... |
| `result.detailed_analysis.market_snapshot` | object | 5.0% | - |
| `result.detailed_analysis.market_tool_call_count` | integer | 11.0% | 0 |
| `result.detailed_analysis.market_type` | string | 6.0% | A股 |
| `result.detailed_analysis.max_debate_rounds` | integer | 7.0% | 3 |
| `result.detailed_analysis.merge` | null | 5.0% | - |
| `result.detailed_analysis.merge_analysts` | null | 6.0% | - |
| `result.detailed_analysis.neutral_opinion` | string | 6.0% | # 📊 **中性风险分析师评估报告：平安银行（000001）投资计划综合分析**

> **分... |
| `result.detailed_analysis.news_report` | string | 11.0% | ### **平安银行（000001）新闻分析报告**  
**分析日期：2025年12月29日... |
| `result.detailed_analysis.news_tool_call_count` | integer | 11.0% | 0 |
| `result.detailed_analysis.parallel_analysts` | null | 6.0% | - |
| `result.detailed_analysis.parallel_start` | null | 5.0% | - |
| `result.detailed_analysis.position_analysis` | string | 5.0% | 根据您提供的账户信息和风险指标，我将以中性平衡的分析风格，对仓位管理策略进行客观评估。

##... |
| `result.detailed_analysis.quick_analysis_model` | string | 6.0% | qwen-flash |
| `result.detailed_analysis.research_depth` | string | 7.0% | 快速 |
| `result.detailed_analysis.review_id` | string | 5.0% | 9a9cb985-b8fc-4c67-a8f2-55cbb322cda7 |
| `result.detailed_analysis.review_summary` | string | 5.0% | ```json
{
    "overall_score": 68,
    "timing_... |
| `result.detailed_analysis.review_type` | string | 5.0% | complete_trade |
| `result.detailed_analysis.risk_assessment` | object | 6.0% | - |
| `result.detailed_analysis.risk_debate_state` | object | 11.0% | - |
| `result.detailed_analysis.risky_opinion` | string | 6.0% | ---

# 🚀 **激进风险分析师报告：平安银行（000001）——被错杀的“金融科技核弹”... |
| `result.detailed_analysis.safe_opinion` | string | 6.0% | ---

# **保守风险分析师评估报告**  
**股票代码：000001（平安银行）** ... |
| `result.detailed_analysis.sector_report` | string | 6.0% | **平安银行（000001）板块分析报告**  
**分析日期：2025年12月29日**

... |
| `result.detailed_analysis.selected_analysts` | array<string> | 6.0% | - |
| `result.detailed_analysis.sentiment_report` | string | 11.0% | # 000001（平安银行）社交媒体情绪分析报告  
**发布日期：2025年12月29日**... |
| `result.detailed_analysis.sentiment_tool_call_count` | integer | 11.0% | 0 |
| `result.detailed_analysis.stock_code` | string | 6.0% | 000001 |
| `result.detailed_analysis.structured_reports` | object | 11.0% | - |
| `result.detailed_analysis.symbol` | string | 6.0% | 000001 |
| `result.detailed_analysis.ticker` | string | 6.0% | 000001 |
| `result.detailed_analysis.timing_analysis` | string | 5.0% | ### 交易时机分析报告

#### 1. **买入时机评估**
- **买入均价计算**： ... |
| `result.detailed_analysis.trade_date` | string | 11.0% | 2025-12-29 |
| `result.detailed_analysis.trade_info` | object | 5.0% | - |
| `result.detailed_analysis.trader_investment_plan` | string, object | 11.0% |  |
| `result.detailed_analysis.trading_system` | object | 5.0% | - |
| `result.detailed_analysis.workflow_id` | null | 6.0% | - |
| `result.emotion_analysis` | string | 1.0% | ### 情绪控制分析报告

基于您提供的交易行为特征数据，以下是对交易中情绪控制表现的客观分析... |
| `result.error_message` | null | 53.0% | - |
| `result.execution_time` | float | 71.0% | 279.709196 |
| `result.final_trade_decision` | string | 14.0% | 好的，作为风险管理委员会主席，我已审阅了关于平安银行（000001.SZ）的完整辩论记录、交易... |
| `result.fundamentals_report` | string | 15.0% | # 平安银行（000001）基本面分析报告
**分析日期：2025年12月28日**

## ... |
| `result.fundamentals_tool_call_count` | integer | 15.0% | 0 |
| `result.include_risk` | boolean | 14.0% | True |
| `result.include_sentiment` | boolean | 14.0% | True |
| `result.index_report` | string | 14.0% | 

<｜DSML｜function_calls>
<｜DSML｜invoke name="ge... |
| `result.investment_debate_state` | object | 15.0% | - |
| `result.investment_debate_state.bear_history` | string | 15.0% |  |
| `result.investment_debate_state.bull_history` | string | 15.0% |  |
| `result.investment_debate_state.count` | integer | 15.0% | 0 |
| `result.investment_debate_state.current_response` | string, object | 15.0% |  |
| `result.investment_debate_state.history` | string | 15.0% |  |
| `result.investment_debate_state.judge_decision` | object | 14.0% | - |
| `result.investment_plan` | string, object | 15.0% |  |
| `result.investment_plan.content` | string | 14.0% | 好的，各位，作为投资组合经理，我已经仔细聆听了本轮关于平安银行的激烈辩论，并审阅了所有相关报告... |
| `result.investment_plan.success` | boolean | 14.0% | True |
| `result.key_points` | array | 11.0% | - |
| `result.language` | string | 14.0% | zh-CN |
| `result.lookback_days` | integer | 14.0% | 30 |
| `result.market` | string | 54.0% | CN |
| `result.market_report` | string | 15.0% | ## 📊 股票基本信息
- 公司名称：平安银行
- 股票代码：000001
- 所属市场：中国... |
| `result.market_snapshot` | object | 8.0% | - |
| `result.market_snapshot.buy_date_close` | float | 8.0% | 5.2 |
| `result.market_snapshot.buy_date_high` | float | 8.0% | 5.23 |
| `result.market_snapshot.buy_date_low` | float | 8.0% | 5.19 |
| `result.market_snapshot.buy_date_open` | float | 8.0% | 5.2 |
| `result.market_snapshot.kline_data` | array<object> | 8.0% | - |
| `result.market_snapshot.optimal_buy_price` | float | 8.0% | 5.19 |
| `result.market_snapshot.optimal_sell_price` | float | 8.0% | 5.23 |
| `result.market_snapshot.period_high` | float | 8.0% | 5.23 |
| `result.market_snapshot.period_high_date` | string | 8.0% | 2025-12-24 |
| `result.market_snapshot.period_low` | float | 8.0% | 5.19 |
| `result.market_snapshot.period_low_date` | string | 8.0% | 2025-12-24 |
| `result.market_snapshot.sell_date_close` | float | 8.0% | 5.2 |
| `result.market_snapshot.sell_date_high` | float | 8.0% | 5.23 |
| `result.market_snapshot.sell_date_low` | float | 8.0% | 5.19 |
| `result.market_snapshot.sell_date_open` | float | 8.0% | 5.2 |
| `result.market_tool_call_count` | integer | 15.0% | 0 |
| `result.market_type` | string | 14.0% | A股 |
| `result.max_debate_rounds` | integer | 14.0% | 3 |
| `result.merge` | null | 1.0% | - |
| `result.merge_analysts` | null | 14.0% | - |
| `result.name` | string | 7.0% | 金山办公 |
| `result.neutral_opinion` | string | 14.0% | # 中性风险分析报告：平安银行投资计划评估

**股票代码：** 000001.SZ  
**... |
| `result.news_report` | string | 15.0% | # 平安银行(000001)新闻分析报告
**分析日期：2025年12月28日**

## 1... |
| `result.news_tool_call_count` | integer | 15.0% | 0 |
| `result.parallel_analysts` | null | 14.0% | - |
| `result.parallel_start` | null | 1.0% | - |
| `result.position_analysis` | string | 1.0% | 好的，作为一名专业的仓位管理分析师，我将基于您提供的数据，以中性平衡的风格对仓位管理策略进行客... |
| `result.position_snapshot` | object | 53.0% | - |
| `result.position_snapshot.code` | string | 53.0% | 601668 |
| `result.position_snapshot.cost_pct` | null | 53.0% | - |
| `result.position_snapshot.cost_price` | float | 53.0% | 5.2583 |
| `result.position_snapshot.cost_value` | null | 53.0% | - |
| `result.position_snapshot.current_price` | float | 53.0% | 5.22 |
| `result.position_snapshot.holding_days` | integer | 53.0% | 26 |
| `result.position_snapshot.industry` | string | 53.0% | 建筑工程 |
| `result.position_snapshot.market` | string | 53.0% | CN |
| `result.position_snapshot.market_value` | float | 53.0% | 6269.22 |
| `result.position_snapshot.name` | string | 53.0% | 中国建筑 |
| `result.position_snapshot.position_pct` | float | 53.0% | 0.62 |
| `result.position_snapshot.quantity` | integer | 53.0% | 1201 |
| `result.position_snapshot.total_capital` | float | 53.0% | 1009500.0 |
| `result.position_snapshot.unrealized_pnl` | float | 53.0% | -46.0 |
| `result.position_snapshot.unrealized_pnl_pct` | float | 53.0% | -0.73 |
| `result.quick_analysis_model` | string | 14.0% | qwen-flash |
| `result.recommendation` | string | 11.0% | # **平安银行（000001）风险评估报告**  
**分析日期：2025年12月30日**... |
| `result.reports` | object | 11.0% | - |
| `result.reports.bear_report` | string | 2.0% | # **看跌观点报告：平安银行（000001）——在“估值幻觉”与“治理隐忧”中埋藏的系统性风... |
| `result.reports.bull_report` | string | 2.0% | ### **看涨分析报告：平安银行（000001）——在低谷中积蓄力量的优质龙头**

**分... |
| `result.reports.final_trade_decision` | string | 6.0% | # **平安银行（000001）风险评估报告**  
**分析日期：2025年12月30日**... |
| `result.reports.fundamentals_report` | string | 6.0% | # **000001（平安银行）基本面分析报告**  
**分析日期：2025年12月29日*... |
| `result.reports.index_report` | string | 3.0% | ### **2025年12月29日 大盘与指数综合分析报告**  
**——聚焦平安银行（00... |
| `result.reports.investment_plan` | string | 6.0% | 我们来做一个冷静、理性且基于真实数据的综合判断。

---

### 📌 **最终决策：买入（... |
| `result.reports.market_report` | string | 6.0% | ## 📊 股票基本信息
- 公司名称：平安银行
- 股票代码：000001
- 所属市场：中国... |
| `result.reports.news_report` | string | 6.0% | ### **平安银行（000001）新闻分析报告**  
**分析日期：2025年12月29日... |
| `result.reports.research_team_decision` | object | 6.0% | - |
| `result.reports.risk_management_decision` | string | 6.0% | # **平安银行（000001）风险评估报告**  
**分析日期：2025年12月30日**... |
| `result.reports.sector_report` | string | 6.0% | **平安银行（000001）板块分析报告**  
**分析日期：2025年12月29日**

... |
| `result.reports.sentiment_report` | string | 6.0% | # 000001（平安银行）社交媒体情绪分析报告  
**发布日期：2025年12月29日**... |
| `result.reports.trader_investment_plan` | string | 6.0% | **最终交易建议: 买入（分批建仓）**

---

### ✅ **投资建议：买入（分批建仓... |
| `result.research_depth` | string | 25.0% | 快速 |
| `result.review_id` | string | 8.0% | d8c3696e-9a32-4fd3-a623-b74725dc59dd |
| `result.review_summary` | string | 1.0% | ```json
{
    "overall_score": 58,
    "timing_... |
| `result.review_type` | string | 1.0% | complete_trade |
| `result.risk_assessment` | object | 14.0% | - |
| `result.risk_assessment.content` | string | 14.0% | 好的，作为风险管理委员会主席，我已审阅了关于平安银行（000001.SZ）的完整辩论记录、交易... |
| `result.risk_assessment.success` | boolean | 14.0% | True |
| `result.risk_debate_state` | object | 15.0% | - |
| `result.risk_debate_state.count` | integer | 15.0% | 0 |
| `result.risk_debate_state.current_neutral_response` | string | 15.0% |  |
| `result.risk_debate_state.current_risky_response` | string | 15.0% |  |
| `result.risk_debate_state.current_safe_response` | string | 15.0% |  |
| `result.risk_debate_state.history` | string | 15.0% |  |
| `result.risk_debate_state.judge_decision` | string | 14.0% | 好的，作为风险管理委员会主席，我已审阅了关于平安银行（000001.SZ）的完整辩论记录、交易... |
| `result.risk_debate_state.latest_speaker` | string | 15.0% | Judge |
| `result.risk_debate_state.neutral_history` | string | 15.0% |  |
| `result.risk_debate_state.risky_history` | string | 15.0% |  |
| `result.risk_debate_state.safe_history` | string | 15.0% |  |
| `result.risk_level` | string | 11.0% | 中等 |
| `result.risky_opinion` | string | 14.0% | ### **激进风险分析报告：平安银行投资计划评估**

**股票代码：** 000001.S... |
| `result.safe_opinion` | string | 14.0% | # 保守风险评估报告：平安银行投资计划

## 一、总体风险评估

**保守风险评分：7/10... |
| `result.sector_report` | string | 14.0% | 好的，作为一名中性客观的行业分析师，我将基于您提供的分析日期（2025-12-28）和股票标的... |
| `result.selected_analysts` | array<string> | 14.0% | - |
| `result.sentiment_report` | string | 15.0% | # 平安银行（000001）社交媒体情绪分析报告
**分析日期：2025年12月28日**

... |
| `result.sentiment_tool_call_count` | integer | 15.0% | 0 |
| `result.state` | object | 11.0% | - |
| `result.state._debate_debate_count` | integer | 6.0% | 1 |
| `result.state._debate_risk_debate_count` | integer | 6.0% | 1 |
| `result.state._fundamentals_messages` | array | 11.0% | - |
| `result.state._market_messages` | array | 11.0% | - |
| `result.state._max_debate_rounds` | integer | 11.0% | 1 |
| `result.state._max_risk_rounds` | integer | 11.0% | 1 |
| `result.state._news_messages` | array | 11.0% | - |
| `result.state._social_messages` | array | 11.0% | - |
| `result.state.analysis_date` | string, datetime | 7.0% | 2025-12-29T00:00:00 |
| `result.state.attribution_analysis` | string | 5.0% | ### 收益归因分析报告

#### 1. Beta收益分析  
大盘同期收益为 **{mar... |
| `result.state.bear_report` | string, object | 11.0% |  |
| `result.state.bull_report` | string, object | 11.0% |  |
| `result.state.code` | string | 5.0% | 688111 |
| `result.state.company_of_interest` | string | 6.0% | 000001 |
| `result.state.custom_prompt` | null | 6.0% | - |
| `result.state.deep_analysis_model` | string | 6.0% | qwen-plus |
| `result.state.emotion_analysis` | string | 5.0% | ### 情绪控制分析报告

基于您提供的交易行为特征数据，以下是对交易中情绪控制表现的客观分析... |
| `result.state.final_trade_decision` | string | 6.0% | # **平安银行（000001）风险评估报告**  
**分析日期：2025年12月30日**... |
| `result.state.fundamentals_report` | string | 11.0% | # **000001（平安银行）基本面分析报告**  
**分析日期：2025年12月29日*... |
| `result.state.fundamentals_tool_call_count` | integer | 11.0% | 0 |
| `result.state.include_risk` | boolean | 6.0% | True |
| `result.state.include_sentiment` | boolean | 6.0% | True |
| `result.state.index_report` | string | 6.0% | ### **2025年12月29日 大盘与指数综合分析报告**  
**——聚焦平安银行（00... |
| `result.state.investment_debate_state` | object | 11.0% | - |
| `result.state.investment_plan` | string, object | 11.0% |  |
| `result.state.language` | string | 6.0% | zh-CN |
| `result.state.lookback_days` | integer | 7.0% | 30 |
| `result.state.market` | string | 5.0% | CN |
| `result.state.market_report` | string | 11.0% | ## 📊 股票基本信息
- 公司名称：平安银行
- 股票代码：000001
- 所属市场：中国... |
| `result.state.market_snapshot` | object | 5.0% | - |
| `result.state.market_tool_call_count` | integer | 11.0% | 0 |
| `result.state.market_type` | string | 6.0% | A股 |
| `result.state.max_debate_rounds` | integer | 7.0% | 3 |
| `result.state.merge` | null | 5.0% | - |
| `result.state.merge_analysts` | null | 6.0% | - |
| `result.state.neutral_opinion` | string | 6.0% | # 📊 **中性风险分析师评估报告：平安银行（000001）投资计划综合分析**

> **分... |
| `result.state.news_report` | string | 11.0% | ### **平安银行（000001）新闻分析报告**  
**分析日期：2025年12月29日... |
| `result.state.news_tool_call_count` | integer | 11.0% | 0 |
| `result.state.parallel_analysts` | null | 6.0% | - |
| `result.state.parallel_start` | null | 5.0% | - |
| `result.state.position_analysis` | string | 5.0% | 根据您提供的账户信息和风险指标，我将以中性平衡的分析风格，对仓位管理策略进行客观评估。

##... |
| `result.state.quick_analysis_model` | string | 6.0% | qwen-flash |
| `result.state.research_depth` | string | 7.0% | 快速 |
| `result.state.review_id` | string | 5.0% | 9a9cb985-b8fc-4c67-a8f2-55cbb322cda7 |
| `result.state.review_summary` | string | 5.0% | ```json
{
    "overall_score": 68,
    "timing_... |
| `result.state.review_type` | string | 5.0% | complete_trade |
| `result.state.risk_assessment` | object | 6.0% | - |
| `result.state.risk_debate_state` | object | 11.0% | - |
| `result.state.risky_opinion` | string | 6.0% | ---

# 🚀 **激进风险分析师报告：平安银行（000001）——被错杀的“金融科技核弹”... |
| `result.state.safe_opinion` | string | 6.0% | ---

# **保守风险分析师评估报告**  
**股票代码：000001（平安银行）** ... |
| `result.state.sector_report` | string | 6.0% | **平安银行（000001）板块分析报告**  
**分析日期：2025年12月29日**

... |
| `result.state.selected_analysts` | array<string> | 6.0% | - |
| `result.state.sentiment_report` | string | 11.0% | # 000001（平安银行）社交媒体情绪分析报告  
**发布日期：2025年12月29日**... |
| `result.state.sentiment_tool_call_count` | integer | 11.0% | 0 |
| `result.state.stock_code` | string | 6.0% | 000001 |
| `result.state.structured_reports` | object | 11.0% | - |
| `result.state.symbol` | string | 6.0% | 000001 |
| `result.state.ticker` | string | 6.0% | 000001 |
| `result.state.timing_analysis` | string | 5.0% | ### 交易时机分析报告

#### 1. **买入时机评估**
- **买入均价计算**： ... |
| `result.state.trade_date` | string | 11.0% | 2025-12-29 |
| `result.state.trade_info` | object | 5.0% | - |
| `result.state.trader_investment_plan` | string, object | 11.0% |  |
| `result.state.trading_system` | object | 5.0% | - |
| `result.state.workflow_id` | null | 6.0% | - |
| `result.status` | string | 60.0% | completed |
| `result.stock_code` | null, string | 25.0% | 000001 |
| `result.stock_symbol` | null, string | 11.0% | 000001 |
| `result.structured_reports` | object | 15.0% | - |
| `result.structured_reports.bear_report` | object | 15.0% | - |
| `result.structured_reports.bull_report` | object | 15.0% | - |
| `result.structured_reports.final_trade_decision` | object | 14.0% | - |
| `result.structured_reports.fundamentals_report` | object | 15.0% | - |
| `result.structured_reports.index_report` | object | 14.0% | - |
| `result.structured_reports.investment_plan` | object | 15.0% | - |
| `result.structured_reports.market_report` | object | 15.0% | - |
| `result.structured_reports.news_report` | object | 15.0% | - |
| `result.structured_reports.sector_report` | object | 14.0% | - |
| `result.structured_reports.sentiment_report` | object | 15.0% | - |
| `result.structured_reports.trader_investment_plan` | object | 15.0% | - |
| `result.success` | boolean | 60.0% | True |
| `result.summary` | string | 11.0% | # **平安银行（000001）风险评估报告**  
**分析日期：2025年12月30日**... |
| `result.symbol` | string | 14.0% | 000001 |
| `result.task_id` | string | 60.0% | 2b8506a0-791c-4ceb-936e-80caa8699dc8 |
| `result.ticker` | string | 14.0% | 000001 |
| `result.timing_analysis` | string | 1.0% | ### 交易时机分析报告

#### 1. **买入时机评估**
- **分析**：由于缺乏具... |
| `result.tokens_used` | integer | 11.0% | 0 |
| `result.trade_date` | string | 15.0% | 2025-12-28 |
| `result.trade_info` | object | 8.0% | - |
| `result.trade_info.avg_buy_price` | float | 8.0% | 5.2583 |
| `result.trade_info.avg_sell_price` | float | 8.0% | 0.0 |
| `result.trade_info.code` | string | 8.0% | 601668 |
| `result.trade_info.currency` | string | 8.0% | CNY |
| `result.trade_info.current_price` | null, float | 8.0% | 5.15 |
| `result.trade_info.first_buy_date` | string | 8.0% | 2025-12-24T12:15:33.974000 |
| `result.trade_info.holding_days` | integer | 8.0% | 0 |
| `result.trade_info.is_holding` | boolean | 8.0% | True |
| `result.trade_info.last_sell_date` | string | 8.0% | 2025-12-24T12:15:33.974000 |
| `result.trade_info.market` | string | 8.0% | CN |
| `result.trade_info.name` | string | 8.0% | 中国建筑 |
| `result.trade_info.realized_pnl` | float | 8.0% | 0.0 |
| `result.trade_info.realized_pnl_pct` | float | 8.0% | 0.0 |
| `result.trade_info.remaining_quantity` | integer | 8.0% | 200 |
| `result.trade_info.total_buy_amount` | float | 8.0% | 1051.67 |
| `result.trade_info.total_buy_quantity` | integer | 8.0% | 200 |
| `result.trade_info.total_commission` | float | 8.0% | 0.0 |
| `result.trade_info.total_sell_amount` | float | 8.0% | 0.0 |
| `result.trade_info.total_sell_quantity` | integer | 8.0% | 0 |
| `result.trade_info.trades` | array<object> | 8.0% | - |
| `result.trade_info.unrealized_pnl` | float | 8.0% | -21.66 |
| `result.trade_info.unrealized_pnl_pct` | float | 8.0% | -2.06 |
| `result.trader_investment_plan` | string, object | 15.0% |  |
| `result.trader_investment_plan.content` | string | 14.0% | 好的，作为一名专业的交易员，我将基于您提供的所有资料，对平安银行（000001）进行分析并给出... |
| `result.trader_investment_plan.success` | boolean | 14.0% | True |
| `result.trading_system` | object | 1.0% | - |
| `result.trading_system._id` | ObjectId | 1.0% | - |
| `result.trading_system.created_at` | datetime | 1.0% | 2025-12-24T10:37:47.394000 |
| `result.trading_system.description` | string | 1.0% | 结合基本面和技术面，寻找价值被低估的成长股，适合上班族 |
| `result.trading_system.discipline` | object | 1.0% | - |
| `result.trading_system.holding` | object | 1.0% | - |
| `result.trading_system.is_active` | boolean | 1.0% | False |
| `result.trading_system.name` | string | 1.0% | 中线价值成长系统 |
| `result.trading_system.position` | object | 1.0% | - |
| `result.trading_system.review` | object | 1.0% | - |
| `result.trading_system.risk_management` | object | 1.0% | - |
| `result.trading_system.risk_profile` | string | 1.0% | balanced |
| `result.trading_system.stock_selection` | object | 1.0% | - |
| `result.trading_system.style` | string | 1.0% | medium_term |
| `result.trading_system.timing` | object | 1.0% | - |
| `result.trading_system.updated_at` | datetime | 1.0% | 2025-12-24T10:37:47.394000 |
| `result.trading_system.user_id` | string | 1.0% | 6915d05ac52e760d74ed36a2 |
| `result.trading_system.version` | string | 1.0% | 1.0.0 |
| `result.workflow_id` | null | 14.0% | - |
| `retry_count` | integer | 100.0% | 0 |
| `started_at` | null, string, datetime | 100.0% | 2025-12-28T19:34:46.928674+08:00 |
| `status` | string | 100.0% | suspended |
| `suspended_at` | datetime | 6.0% | 2026-01-22T08:23:11.388000 |
| `task_id` | string | 100.0% | acb6b6fc-6c9f-40c2-a9db-1d6ab7dc4ac2 |
| `task_params` | object | 100.0% | - |
| `task_params.analysis_date` | datetime | 28.0% | 2025-12-28T00:00:00 |
| `task_params.analysis_focus` | string | 55.0% | comprehensive |
| `task_params.code` | string | 68.0% | 601668 |
| `task_params.custom_prompt` | null | 28.0% | - |
| `task_params.deep_analysis_model` | string | 28.0% | qwen-plus |
| `task_params.include_add_position` | boolean | 55.0% | True |
| `task_params.include_risk` | boolean | 28.0% | True |
| `task_params.include_sentiment` | boolean | 28.0% | True |
| `task_params.investment_horizon` | string | 55.0% | medium |
| `task_params.language` | string | 28.0% | zh-CN |
| `task_params.market` | string | 61.0% | CN |
| `task_params.market_snapshot` | object | 6.0% | - |
| `task_params.market_snapshot.buy_date_close` | float | 6.0% | 305.55 |
| `task_params.market_snapshot.buy_date_high` | float | 6.0% | 310.0 |
| `task_params.market_snapshot.buy_date_low` | float | 6.0% | 303.39 |
| `task_params.market_snapshot.buy_date_open` | float | 6.0% | 308.0 |
| `task_params.market_snapshot.kline_data` | array<object> | 6.0% | - |
| `task_params.market_snapshot.optimal_buy_price` | float | 6.0% | 292.0 |
| `task_params.market_snapshot.optimal_sell_price` | float | 6.0% | 372.98 |
| `task_params.market_snapshot.period_high` | float | 6.0% | 372.98 |
| `task_params.market_snapshot.period_high_date` | string | 6.0% | 2025-11-03 |
| `task_params.market_snapshot.period_low` | float | 6.0% | 292.0 |
| `task_params.market_snapshot.period_low_date` | string | 6.0% | 2025-10-23 |
| `task_params.market_snapshot.sell_date_close` | float | 6.0% | 312.42 |
| `task_params.market_snapshot.sell_date_high` | float | 6.0% | 312.7 |
| `task_params.market_snapshot.sell_date_low` | float | 6.0% | 305.33 |
| `task_params.market_snapshot.sell_date_open` | float | 6.0% | 307.31 |
| `task_params.market_type` | string | 28.0% | A股 |
| `task_params.max_loss_pct` | float | 55.0% | 10.0 |
| `task_params.max_position_pct` | float | 55.0% | 30.0 |
| `task_params.parameters` | object | 4.0% | - |
| `task_params.parameters.analysis_date` | datetime | 4.0% | 2025-12-28T00:00:00 |
| `task_params.parameters.custom_prompt` | null | 4.0% | - |
| `task_params.parameters.deep_analysis_model` | string | 4.0% | qwen-plus |
| `task_params.parameters.engine` | string | 4.0% | v2 |
| `task_params.parameters.include_risk` | boolean | 4.0% | True |
| `task_params.parameters.include_sentiment` | boolean | 4.0% | True |
| `task_params.parameters.language` | string | 4.0% | zh-CN |
| `task_params.parameters.market_type` | string | 4.0% | A股 |
| `task_params.parameters.quick_analysis_model` | string | 4.0% | qwen-flash |
| `task_params.parameters.research_depth` | string | 4.0% | 快速 |
| `task_params.parameters.selected_analysts` | array<string> | 4.0% | - |
| `task_params.parameters.workflow_id` | null | 4.0% | - |
| `task_params.position_type` | string | 55.0% | real |
| `task_params.quick_analysis_model` | string | 28.0% | qwen-flash |
| `task_params.research_depth` | string | 83.0% | 快速 |
| `task_params.review_id` | string | 6.0% | 9a9cb985-b8fc-4c67-a8f2-55cbb322cda7 |
| `task_params.review_type` | string | 13.0% | complete_trade |
| `task_params.risk_tolerance` | string | 55.0% | medium |
| `task_params.selected_analysts` | array<string> | 28.0% | - |
| `task_params.source` | string | 7.0% | real |
| `task_params.stock_code` | string | 32.0% | 000001 |
| `task_params.symbol` | string | 32.0% | 000001 |
| `task_params.target_profit_pct` | float | 55.0% | 20.0 |
| `task_params.total_capital` | float | 55.0% | 1009500.0 |
| `task_params.trade_ids` | array<string> | 7.0% | - |
| `task_params.trade_info` | object | 6.0% | - |
| `task_params.trade_info.avg_buy_price` | float | 6.0% | 296.8021 |
| `task_params.trade_info.avg_sell_price` | float | 6.0% | 335.0 |
| `task_params.trade_info.code` | string | 6.0% | 688111 |
| `task_params.trade_info.currency` | string | 6.0% | CNY |
| `task_params.trade_info.current_price` | float, null | 6.0% | 5.15 |
| `task_params.trade_info.first_buy_date` | string | 6.0% | 2025-10-16T00:00:00 |
| `task_params.trade_info.holding_days` | integer | 6.0% | 62 |
| `task_params.trade_info.is_holding` | boolean | 6.0% | False |
| `task_params.trade_info.last_sell_date` | string | 6.0% | 2025-12-17T16:00:00 |
| `task_params.trade_info.market` | string | 6.0% | CN |
| `task_params.trade_info.name` | string | 6.0% | 金山办公 |
| `task_params.trade_info.realized_pnl` | float | 6.0% | 29900.0 |
| `task_params.trade_info.realized_pnl_pct` | float | 6.0% | 12.59 |
| `task_params.trade_info.remaining_quantity` | integer | 6.0% | 0 |
| `task_params.trade_info.total_buy_amount` | float | 6.0% | 237441.66 |
| `task_params.trade_info.total_buy_quantity` | integer | 6.0% | 800 |
| `task_params.trade_info.total_commission` | float | 6.0% | 0.0 |
| `task_params.trade_info.total_sell_amount` | float | 6.0% | 268000.0 |
| `task_params.trade_info.total_sell_quantity` | integer | 6.0% | 800 |
| `task_params.trade_info.trades` | array<object> | 6.0% | - |
| `task_params.trade_info.unrealized_pnl` | float | 6.0% | 0.0 |
| `task_params.trade_info.unrealized_pnl_pct` | float | 6.0% | 0.0 |
| `task_params.trading_system` | object | 6.0% | - |
| `task_params.trading_system._id` | ObjectId | 6.0% | - |
| `task_params.trading_system.created_at` | datetime | 6.0% | 2025-12-24T10:37:47.394000 |
| `task_params.trading_system.description` | string | 6.0% | 结合基本面和技术面，寻找价值被低估的成长股，适合上班族 |
| `task_params.trading_system.discipline` | object | 6.0% | - |
| `task_params.trading_system.holding` | object | 6.0% | - |
| `task_params.trading_system.is_active` | boolean | 6.0% | False |
| `task_params.trading_system.name` | string | 6.0% | 中线价值成长系统 |
| `task_params.trading_system.position` | object | 6.0% | - |
| `task_params.trading_system.review` | object | 6.0% | - |
| `task_params.trading_system.risk_management` | object | 6.0% | - |
| `task_params.trading_system.risk_profile` | string | 6.0% | balanced |
| `task_params.trading_system.stock_selection` | object | 6.0% | - |
| `task_params.trading_system.style` | string | 6.0% | medium_term |
| `task_params.trading_system.timing` | object | 6.0% | - |
| `task_params.trading_system.updated_at` | datetime | 6.0% | 2025-12-24T10:37:47.394000 |
| `task_params.trading_system.user_id` | string | 6.0% | 6915d05ac52e760d74ed36a2 |
| `task_params.trading_system.version` | string | 6.0% | 1.0.0 |
| `task_params.trading_system_id` | null, string | 7.0% | 694bc27bd639700ce1d9dbea |
| `task_params.use_workflow` | boolean | 7.0% | False |
| `task_params.workflow_id` | null | 28.0% | - |
| `task_type` | string | 100.0% | stock_analysis |
| `tokens_used` | integer | 100.0% | 0 |
| `updated_at` | datetime | 60.0% | 2025-12-29T16:47:07.048000 |
| `user_id` | ObjectId | 100.0% | - |
| `worker_id` | null | 100.0% | - |
| `workflow_id` | null, string | 100.0% | trade_review |

---

## user_favorites

**文档数量**: 3

**分析样本**: 3 条

### 字段列表

| 字段路径 | 类型 | 出现率 | 示例值 |
|---------|------|--------|--------|
| `_id` | ObjectId | 100.0% | - |
| `created_at` | datetime | 100.0% | 2025-11-04T09:02:23.215000 |
| `favorites` | array<object> | 100.0% | - |
| `updated_at` | datetime | 100.0% | 2025-11-04T09:51:49.577000 |
| `user_id` | string | 100.0% | 6909bbda40956de8421064ff |

---

## user_sessions

**文档数量**: 218

**分析样本**: 100 条

### 字段列表

| 字段路径 | 类型 | 出现率 | 示例值 |
|---------|------|--------|--------|
| `_id` | ObjectId | 100.0% | - |
| `created_at` | datetime | 100.0% | 2026-01-20T11:56:12.322000 |
| `expires_at` | datetime | 100.0% | 2026-01-27T11:56:12.322000 |
| `ip_address` | null, string | 100.0% | 127.0.0.1 |
| `last_activity` | datetime | 100.0% | 2026-01-20T11:56:12.322000 |
| `session_id` | string | 100.0% | Q9xTgf0D0ES9Yzv4V1raYwIEQjlYJDySy9p_D3l1UVQ |
| `user_agent` | null, string | 100.0% | Mozilla/5.0 (Windows NT 10.0; Win64; x64) Apple... |
| `user_id` | string | 100.0% | 6915d05ac52e760d74ed36a2 |

---

## user_tags

**文档数量**: 4

**分析样本**: 4 条

### 字段列表

| 字段路径 | 类型 | 出现率 | 示例值 |
|---------|------|--------|--------|
| `_id` | ObjectId | 100.0% | - |
| `color` | string | 100.0% | #409EFF |
| `created_at` | datetime | 100.0% | 2025-09-24T11:52:15.381000 |
| `name` | string | 100.0% | AI |
| `sort_order` | integer | 100.0% | 0 |
| `updated_at` | datetime | 100.0% | 2025-09-24T11:52:15.381000 |
| `user_id` | string | 100.0% | admin |

---

## user_template_configs

**文档数量**: 48

**分析样本**: 48 条

### 字段列表

| 字段路径 | 类型 | 出现率 | 示例值 |
|---------|------|--------|--------|
| `_id` | ObjectId | 100.0% | - |
| `agent_name` | string | 100.0% | fundamentals_analyst |
| `agent_type` | string | 100.0% | analysts |
| `created_at` | datetime | 100.0% | 2025-11-16T09:38:55.798000 |
| `is_active` | boolean | 100.0% | False |
| `preference_id` | null | 100.0% | - |
| `template_id` | ObjectId | 100.0% | - |
| `updated_at` | datetime | 100.0% | 2025-11-16T09:38:55.798000 |
| `user_id` | ObjectId | 100.0% | - |

---

## users

**文档数量**: 1

**分析样本**: 1 条

### 字段列表

| 字段路径 | 类型 | 出现率 | 示例值 |
|---------|------|--------|--------|
| `_id` | ObjectId | 100.0% | - |
| `app_token` | string | 100.0% | OBcEtrCdUnfuRS6FfUhCJuzBWF2R-Um-WvjCBWqWsOg |
| `concurrent_limit` | integer | 100.0% | 10 |
| `created_at` | datetime | 100.0% | 2025-11-13T12:34:34.881000 |
| `daily_quota` | integer | 100.0% | 10000 |
| `email` | string | 100.0% | 107213551@qq.com |
| `failed_analyses` | integer | 100.0% | 0 |
| `favorite_stocks` | array | 100.0% | - |
| `hashed_password` | string | 100.0% | 240be518fabd2724ddb6f04eeb1da5967448d7e831c08c8... |
| `is_active` | boolean | 100.0% | True |
| `is_admin` | boolean | 100.0% | True |
| `is_verified` | boolean | 100.0% | True |
| `last_login` | datetime | 100.0% | 2026-01-25T11:44:30.699000 |
| `license_email` | string | 100.0% | 107213551@qq.com |
| `license_plan` | string | 100.0% | pro |
| `preferences` | object | 100.0% | - |
| `preferences.analysis_complete_notification` | boolean | 100.0% | True |
| `preferences.auto_refresh` | boolean | 100.0% | True |
| `preferences.default_analysts` | array<string> | 100.0% | - |
| `preferences.default_depth` | string | 100.0% | 3 |
| `preferences.default_market` | string | 100.0% | A股 |
| `preferences.desktop_notifications` | boolean | 100.0% | True |
| `preferences.email_notifications` | object | 100.0% | - |
| `preferences.email_notifications.batch_analysis` | boolean | 100.0% | True |
| `preferences.email_notifications.email_address` | string | 100.0% | 107213551@qq.com |
| `preferences.email_notifications.enabled` | boolean | 100.0% | True |
| `preferences.email_notifications.format` | string | 100.0% | html |
| `preferences.email_notifications.important_signals` | boolean | 100.0% | False |
| `preferences.email_notifications.language` | string | 100.0% | zh |
| `preferences.email_notifications.quiet_hours_enabled` | boolean | 100.0% | False |
| `preferences.email_notifications.quiet_hours_end` | string | 100.0% | 08:00 |
| `preferences.email_notifications.quiet_hours_start` | string | 100.0% | 22:00 |
| `preferences.email_notifications.scheduled_analysis` | boolean | 100.0% | True |
| `preferences.email_notifications.single_analysis` | boolean | 100.0% | True |
| `preferences.email_notifications.system_notifications` | boolean | 100.0% | False |
| `preferences.language` | string | 100.0% | zh-CN |
| `preferences.notifications_enabled` | boolean | 100.0% | True |
| `preferences.refresh_interval` | integer | 100.0% | 30 |
| `preferences.risk_preference` | string | 100.0% | conservative |
| `preferences.sidebar_width` | integer | 100.0% | 240 |
| `preferences.system_maintenance_notification` | boolean | 100.0% | True |
| `preferences.ui_theme` | string | 100.0% | light |
| `successful_analyses` | integer | 100.0% | 0 |
| `total_analyses` | integer | 100.0% | 0 |
| `updated_at` | datetime | 100.0% | 2025-12-24T08:10:06.116000 |
| `username` | string | 100.0% | admin |

---

## watchlist_groups

**文档数量**: 1

**分析样本**: 1 条

### 字段列表

| 字段路径 | 类型 | 出现率 | 示例值 |
|---------|------|--------|--------|
| `_id` | ObjectId | 100.0% | - |
| `analysis_depth` | null | 100.0% | - |
| `color` | string | 100.0% | #409EFF |
| `created_at` | datetime | 100.0% | 2025-12-14T13:31:50.394000 |
| `deep_analysis_model` | null | 100.0% | - |
| `description` | string | 100.0% | test |
| `icon` | string | 100.0% | Folder |
| `is_active` | boolean | 100.0% | True |
| `name` | string | 100.0% | test1 |
| `prompt_template_id` | null | 100.0% | - |
| `quick_analysis_model` | null | 100.0% | - |
| `sort_order` | integer | 100.0% | 0 |
| `stock_codes` | array<string> | 100.0% | - |
| `updated_at` | datetime | 100.0% | 2026-01-07T03:42:53.255000 |
| `user_id` | string | 100.0% | 6915d05ac52e760d74ed36a2 |

---

## workflow_definitions

**文档数量**: 0

**分析样本**: 0 条

---

## workflow_history

**文档数量**: 28

**分析样本**: 28 条

### 字段列表

| 字段路径 | 类型 | 出现率 | 示例值 |
|---------|------|--------|--------|
| `_id` | ObjectId | 100.0% | - |
| `change_description` | null | 100.0% | - |
| `change_type` | string | 100.0% | update |
| `content` | object | 100.0% | - |
| `content.config` | object | 100.0% | - |
| `content.config.analysis_depth` | integer | 14.3% | 3 |
| `content.config.debate_rounds` | string | 14.3% | auto |
| `content.config.depth_rounds_mapping` | object | 14.3% | - |
| `content.config.memory_enabled` | boolean | 14.3% | True |
| `content.config.online_tools` | boolean | 14.3% | True |
| `content.config.output_format` | string | 35.7% | structured_report |
| `content.config.parallel_analysts` | boolean | 35.7% | True |
| `content.config.parallel_timeout` | integer | 14.3% | 300 |
| `content.config.risk_debate_rounds` | string | 14.3% | auto |
| `content.config.workflow_type` | string | 35.7% | trade_review |
| `content.created_at` | string | 100.0% | 2025-12-08T12:35:35.240345 |
| `content.created_by` | null | 100.0% | - |
| `content.description` | string | 100.0% | 基于 TradingAgents 论文设计的完整多智能体协作分析流程。包含4个专业分析师（市场... |
| `content.edges` | array<object> | 100.0% | - |
| `content.id` | string | 100.0% | 85caaed6-6ac8-4b56-b530-03ea4d0630ef |
| `content.is_system` | boolean | 100.0% | False |
| `content.is_template` | boolean | 100.0% | False |
| `content.name` | string | 100.0% | TradingAgents 完整分析流 - 我的版本 |
| `content.nodes` | array<object> | 100.0% | - |
| `content.tags` | array<string> | 100.0% | - |
| `content.updated_at` | string | 100.0% | 2025-12-11T21:15:23.181240 |
| `content.version` | string | 100.0% | 1.0.1 |
| `created_at` | string | 100.0% | 2025-12-11T21:15:23.186688 |
| `user_id` | null | 100.0% | - |
| `version` | string, integer | 100.0% | 1.0.1 |
| `workflow_id` | string | 100.0% | 85caaed6-6ac8-4b56-b530-03ea4d0630ef |

---

## workflows

**文档数量**: 2

**分析样本**: 2 条

### 字段列表

| 字段路径 | 类型 | 出现率 | 示例值 |
|---------|------|--------|--------|
| `_id` | ObjectId | 100.0% | - |
| `config` | object | 100.0% | - |
| `config.output_format` | string | 50.0% | structured_report |
| `config.parallel_analysts` | boolean | 50.0% | True |
| `config.workflow_type` | string | 50.0% | trade_review |
| `created_at` | string | 100.0% | 2025-12-12T14:06:25.592643 |
| `created_by` | null, string | 100.0% | system |
| `description` | string | 100.0% | 多维度分析交易操作的完整复盘流程。包含时机分析、仓位分析、情绪分析、归因分析四个专业分析师并行... |
| `edges` | array<object> | 100.0% | - |
| `id` | string | 100.0% | trade_review |
| `is_system` | boolean | 100.0% | True |
| `is_template` | boolean | 100.0% | True |
| `name` | string | 100.0% | 交易复盘分析流程 |
| `nodes` | array<object> | 100.0% | - |
| `tags` | array<string> | 100.0% | - |
| `updated_at` | string | 100.0% | 2025-12-12T14:06:25.592643 |
| `version` | string | 100.0% | 1.0.0 |

---

