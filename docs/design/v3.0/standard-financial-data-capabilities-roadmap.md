# 股票分析系统通用数据能力路线图与现状对比

> 文档版本：v2.1  
> 更新时间：2026-06-28  
> 适用范围：Agent 工坊、Skill 生成器、股票分析系统、基本面/技术面/资金面/事件/风险/组合类 Agent

---

## 1. 背景

在 Agent 工坊和 Skill 生成过程中，已经发现一类共性问题：

- Agent 会从 Markdown 工具输出中抠数；
- Agent 会临时拼季度、半年报、年报数据；
- 不同 Agent 对同一指标采用不同口径；
- 关键数值计算容易落到 LLM 推理中，难以审计；
- Skill 生成器会把“已有弱覆盖能力”误判为“完全缺失”；
- 现有工具偏“分析报告型”，但股票分析系统需要更多“结构化数据能力原语”。

因此，高频、通用、强口径的数据能力应优先沉淀为标准 Runtime API 和标准工具，而不是让 Agent/Skill 每次临时生成。

推荐架构：

```text
标准 Runtime API
  ↓
标准工具 Tool
  ↓
领域 Skill / Evidence Bundle
  ↓
Agent 编排与报告
```

核心原则：

1. **标准工具负责数据和计算**：拉数、对齐、筛选、计算、覆盖率、warning。
2. **Skill 负责业务组合**：把多个标准工具组合成领域能力。
3. **Agent 负责选择、解释和报告**：不自行计算关键数值，不从 Markdown 中抠数。
4. **所有高复用能力必须结构化输出**：优先 JSON/dict/list，不依赖自然语言文本。
5. **所有数据能力必须显式返回覆盖率、样本数、数据源和缺失说明**。
6. **in-flight / partial coverage 也要纳入能力盘点**：避免把“隐藏在文本工具里的弱能力”误判为“完全缺失”。
7. **工具选择必须有角色和路由策略**：Agent Builder 不能只把相似工具塞进 `required_tools` 让 LLM 临场猜；必须区分主入口、专项、补充、通用和降级工具，并把选择规则固化到版本配置、Prompt 和评估中。

---

## 2. 股票分析系统通用能力地图

股票分析系统不应只围绕单个 Agent（例如巴菲特 Agent）建设能力，而应按完整分析链路建设通用能力。

### 2.1 证券基础数据能力

目标能力：

```text
get_security_master
get_stock_profile
get_listing_status
get_trading_calendar
get_corporate_actions
get_name_change_history
```

覆盖内容：

- 股票代码标准化；
- 公司名称、交易所、上市日期；
- 行业分类；
- 退市/ST/风险警示；
- 复权因子；
- 分红送转；
- 更名历史；
- 停复牌信息。

优先级：P0。

现状：部分覆盖。`stock_basic_info`、`market_quotes`、交易日历缓存和若干工具已经覆盖一部分，但缺少统一结构化证券主数据 API。

---

### 2.2 行情与价格序列能力

目标能力：

```text
get_price_series
get_adjusted_price_series
get_intraday_price_series
get_market_snapshot
get_return_series
get_volatility_metrics
get_drawdown_metrics
```

覆盖内容：

- 日线/周线/月线 OHLCV；
- 前复权/后复权/不复权；
- 收益率序列；
- 波动率；
- 最大回撤；
- 成交额、换手率、振幅；
- 涨跌停状态。

优先级：P0。

现状：部分覆盖。已有 `get_stock_market_data_unified`、`get_stock_daily_quotes`、`get_external_historical_data` 等，但缺少标准化 `return_series`、`volatility_metrics`、`drawdown_metrics`。

---

### 2.3 技术指标能力

目标能力：

```text
get_moving_average_bundle
get_momentum_indicators
get_trend_indicators
get_volume_price_indicators
get_support_resistance_levels
get_breakout_signal_context
```

覆盖内容：

- MA/EMA；
- MACD；
- RSI；
- KDJ；
- Bollinger Bands；
- ATR；
- OBV；
- 量价背离；
- 均线多空排列；
- 支撑/压力位；
- 突破/跌破信号。

优先级：P0/P1。

现状：部分覆盖。已有 `get_technical_factor_bundle_tool`，提供 MA20、RSI14、KDJ、MACD 的结构化快照；但缺少完整历史序列、ATR/BOLL/OBV、支撑压力和突破上下文。

---

### 2.4 基本面与财务序列能力

目标能力：

```text
get_historical_financial_annual_series
get_profitability_stability_metrics
get_cashflow_quality_trend
get_debt_solvency_trend
get_margin_stability_metrics
get_capital_efficiency_trend
get_growth_quality_metrics
get_shareholder_return_history
get_business_segment_trend
```

覆盖内容：

- 5-10 年年报序列；
- 单季/TTM 财务序列；
- 营收、净利润、扣非净利润；
- 毛利率、净利率、费用率；
- ROE/ROA/ROIC；
- 经营现金流、自由现金流；
- 资产负债率、偿债能力；
- 杜邦分解；
- 主营业务结构；
- 分红、回购、股东回报。

优先级：P0/P1。

现状：P0 与 P1 第一版已覆盖。已完成结构化能力：

```text
get_historical_financial_annual_series
get_profitability_stability_metrics
get_cashflow_quality_trend
get_debt_solvency_trend
get_margin_stability_metrics
get_capital_efficiency_trend
get_growth_quality_metrics
get_historical_valuation_percentile
```

已有 `get_income_analysis`、`get_balance_sheet_analysis`、`get_cashflow_analysis`、`get_dividend_data`、`get_main_business` 等分析型工具，但多为 Markdown 输出，不适合作为长期结构化计算底座。

---

### 2.5 估值分析能力

目标能力：

```text
get_current_valuation_snapshot
get_historical_valuation_percentile
get_peer_valuation_comparison
get_industry_valuation_distribution
get_growth_adjusted_valuation
get_dividend_valuation_context
get_valuation_safety_margin_context
```

覆盖内容：

- PE/PE_TTM；
- PB/PB_MRQ；
- PS/PS_TTM；
- PCF；
- PEG；
- 股息率；
- 历史分位；
- 行业分位；
- 同业中位数；
- 估值通道；
- 质量调整估值。

优先级：P0。

现状：较强但仍不完整。已有：

```text
get_value_factor_bundle_tool
get_historical_valuation_percentile_tool
get_stock_fundamentals_unified（含隐藏 3 年文本分位）
summarize_industry_valuation
get_peer_comparison
```

缺口：行业估值分布结构化、成长质量调整估值、股息估值上下文、估值安全边际证据包。

---

### 2.6 行业与同业比较能力

目标能力：

```text
get_industry_classification
get_sector_constituents
get_peer_group
get_peer_relative_valuation
get_peer_relative_quality
get_peer_relative_growth
get_industry_fundamental_summary
get_industry_market_performance
```

覆盖内容：

- 行业分类；
- 板块成分股；
- 可比公司筛选；
- 行业估值中位数；
- 行业 ROE 分位；
- 行业毛利率分位；
- 行业成长分位；
- 行业涨跌幅；
- 行业资金流；
- 行业景气度。

优先级：P0/P1。

现状：部分覆盖。已有：

```text
get_sector_data
get_sector_analysis
search_sector
get_sector_daily
get_sector_constituents
get_peer_comparison
analyze_sector
analyze_sector_by_name
get_industry_peer_basic_info
summarize_industry_valuation
```

缺口：同业成长分位、行业市场表现、行业景气度。`get_peer_group`、`get_peer_relative_quality`、`get_industry_fundamental_summary` 已完成第一版。

---

### 2.7 资金流与筹码能力

目标能力：

```text
get_capital_flow_series
get_northbound_flow_context
get_main_fund_flow_context
get_margin_financing_context
get_chip_distribution_context
get_turnover_activity_metrics
```

覆盖内容：

- 主力资金流；
- 北向资金；
- 融资融券；
- 成交额变化；
- 换手率变化；
- 筹码集中度；
- 获利盘比例；
- 套牢盘分布；
- 成交密集区。

优先级：P1。若系统定位包含交易辅助，则部分能力应提升至 P0。

现状：部分覆盖。已有：

```text
get_fund_flow_data
get_north_flow
get_margin_trading
get_chip_distribution
get_chip_distribution_akshare_tool
get_chip_distribution_tushare_tool
```

缺口：主力资金上下文、换手活跃度指标、北向/融资融券上下文标准化。`get_capital_flow_series` 和 `get_chip_distribution_context` 已完成第一版；其中资金流当前优先读本地候选集合，本地未同步时返回 `no_data`。

---

### 2.8 新闻、公告与事件能力

目标能力：

```text
get_company_announcements
get_recent_news_events
get_event_timeline
get_earnings_calendar
get_dividend_calendar
get_risk_event_flags
get_policy_event_context
```

覆盖内容：

- 公司公告；
- 财报发布日期；
- 分红预案；
- 减持/增持；
- 诉讼/处罚；
- 重大合同；
- 资产重组；
- 高管变动；
- 政策事件；
- 舆情事件。

优先级：P1。其中公告和风险事件建议 P0。

现状：部分覆盖。已有：

```text
get_stock_news_headlines_unified
get_stock_news_details_unified
get_stock_news_unified
get_stock_news
get_external_stock_news
get_external_query_news
```

缺口：公告结构化、事件时间线、风险事件 flags、财报日历、分红日历、政策事件上下文。

---

### 2.9 情绪与文本分析能力

目标能力：

```text
get_news_sentiment_summary
get_social_sentiment_summary
get_analyst_opinion_summary
get_research_report_summary
get_market_attention_metrics
```

覆盖内容：

- 新闻情绪；
- 社媒情绪；
- 研报观点；
- 分析师评级；
- 目标价变化；
- 市场关注度；
- 舆情热度。

优先级：P2。

现状：弱覆盖。已有 `get_stock_sentiment_unified` 和新闻工具，但缺少标准化研报观点、分析师评级、目标价变化和关注度指标。

---

### 2.10 风险、组合与回测能力

目标能力：

```text
get_single_stock_risk_profile
get_portfolio_exposure
get_portfolio_risk_metrics
get_factor_exposure
get_position_attribution
run_strategy_backtest
run_signal_backtest
get_scenario_stress_test
```

覆盖内容：

- 个股波动率；
- 最大回撤；
- Beta；
- VaR；
- 行业暴露；
- 风格暴露；
- 持仓集中度；
- 盈亏归因；
- 信号回测；
- 策略回测；
- 压力测试。

优先级：P1/P2。若系统包含组合管理，则组合风险是 P0。

现状：弱覆盖。已有交易复盘、持仓查询、止盈止损提醒等工具，但缺少标准化风险画像、组合风险、因子暴露和回测能力。

---

## 3. 现有工具与目标能力对比

状态说明：

```text
✅ 已覆盖：已有结构化标准能力，基本满足目标。
🟡 部分覆盖：已有工具或数据，但输出形态/口径/结构化程度不足。
🔴 缺失：缺少明确标准能力。
```

| 能力域 | 目标状态 | 现有相关工具/接口 | 当前状态 | 主要缺口 |
|---|---|---|---|---|
| 证券基础数据 | 统一证券主数据、上市状态、交易所、行业、风险警示、公司行动 | `get_stock_basic_info`, `stock_basic_info`, `market_quotes`, 交易日历缓存 | 🟡 部分覆盖 | 缺 `get_security_master`、公司行动、停复牌、ST/退市状态统一接口 |
| 价格序列 | 复权价格序列、收益率、波动率、回撤 | `get_stock_market_data_unified`, `get_stock_daily_quotes`, `get_external_historical_data` | 🟡 部分覆盖 | 缺标准 `return_series`、`volatility_metrics`、`drawdown_metrics` |
| 技术指标 | MA/EMA/MACD/RSI/KDJ/BOLL/ATR/OBV/支撑压力 | `get_technical_factor_bundle_tool` | 🟡 部分覆盖 | 只有当前快照和少量指标，缺完整历史和支撑压力/突破上下文 |
| 长期财务序列 | 5-10 年结构化年报序列 | `get_historical_financial_annual_series_tool` | ✅ 已覆盖第一版 | 需增强字段覆盖率、重述版本、资本开支映射 |
| 盈利稳定性 | 结构化波动率、变异系数、增长稳定性 | `get_profitability_stability_metrics_tool` | ✅ 已覆盖第一版 | 需增加连续增长年数、异常年份、稳定性等级 |
| 现金流质量 | OCF/净利、FCF/净利、现金流率长期趋势 | `get_cashflow_quality_trend_tool`, `get_cashflow_analysis` | ✅ 已覆盖第一版 | 需完善资本开支、连续为正统计 |
| 偿债能力趋势 | 资产负债率、流动比率、现金债务覆盖长期趋势 | `get_debt_solvency_trend_tool`, `get_balance_sheet_analysis`, `get_quality_factor_bundle_tool` | ✅ 已覆盖第一版 | 需增强现金债务覆盖、利息保障等字段 |
| 利润率稳定性 | 毛利率、净利率、费用率稳定性 | `get_margin_stability_metrics_tool`, `get_profitability_stability_metrics_tool`, `get_quality_factor_bundle_tool` | ✅ 已覆盖第一版 | 需增强异常年份识别和稳定性评级 |
| 资本效率 | ROE/ROA/ROIC、周转率、杜邦趋势 | `get_capital_efficiency_trend_tool`, `get_quality_factor_bundle_tool`, 年报序列 | ✅ 已覆盖第一版 | 需增强完整杜邦分解和行业分位 |
| 股东回报 | 分红、回购、股息率、分红率历史 | `get_shareholder_return_metrics_tool`, `get_dividend_data` | ✅ 已覆盖第一版 | 已补结构化分红/股息率/连续性；回购数据源后续增强 |
| 主营结构 | 分产品/分地区收入和毛利趋势 | `get_business_segment_trend_tool`, `get_main_business` | ✅ 已覆盖第一版 | 已补结构化趋势；后续增强跨期分部名称归一化 |
| 当前估值 | PE/PB/PS/PEG/股息率当前快照 | `get_value_factor_bundle_tool`, `get_stock_valuation_context` | ✅ 已覆盖 | 可增强多源校验 |
| 历史估值分位 | PE/PB/PS/PCF 可配置窗口分位 | `get_historical_valuation_percentile_tool` | ✅ 已覆盖第一版 | 需本地缓存、行业分位、估值通道 |
| 行业估值 | 行业 PE/PB 分布、样本统计 | `summarize_industry_valuation`, `get_peer_comparison` | 🟡 部分覆盖 | 缺完整行业估值分布和样本过滤策略 |
| 同业质量 | ROE/毛利率/现金流质量行业分位 | `get_peer_relative_quality_tool`, `get_peer_comparison`, `get_industry_peer_basic_info` | ✅ 已覆盖第一版 | 需增强更多质量指标和行业分位解释 |
| 同业成长 | 营收/利润增长行业分位 | `get_peer_relative_growth_tool`, `get_peer_comparison` | ✅ 已覆盖第一版 | 已补 CAGR 同业分位，覆盖营收、净利润、经营现金流和自由现金流 |
| 行业市场表现 | 行业涨跌、资金、轮动 | `get_industry_market_performance_tool`, `get_sector_data`, `get_fund_flow_data`, `analyze_sector` | ✅ 已覆盖第一版 | 已补结构化行业表现 API；旧工具保留报告型输出 |
| 资金流 | 个股资金流序列、板块资金、北向、融资融券 | `get_capital_flow_series_tool`, `get_fund_flow_data`, `get_north_flow`, `get_margin_trading` | ✅ 已覆盖第一版 | 个股资金流优先读本地候选集合；本地缺失时回退 Tushare `moneyflow_ths`，后续可补 QMT L2 代理 |
| 筹码 | 筹码分布、获利盘、套牢盘 | `get_chip_distribution_context_tool`, `get_chip_distribution`, `get_chip_distribution_akshare_tool`, `get_chip_distribution_tushare_tool` | ✅ 已覆盖第一版 | 标准化上下文已完成；数据依赖外部 AkShare/Tushare，可用性随数据源变化 |
| 新闻 | 个股新闻、外部新闻 | `get_stock_news_unified`, `get_stock_news_headlines_unified`, `get_stock_news_details_unified` | 🟡 部分覆盖 | 缺事件分类、事件时间线、风险 flags |
| 公告事件 | 公告、财报日历、分红日历、诉讼处罚 | 新闻工具部分覆盖 | 🔴 缺失 | 缺公告结构化 API 和事件日历 |
| 情绪 | 新闻/社媒情绪、热度 | `get_stock_sentiment_unified` | 🟡 部分覆盖 | 缺研报观点、分析师评级、目标价变化 |
| 个股风险 | 波动率、回撤、Beta、VaR | `get_single_stock_risk_profile_tool`, `get_volatility_metrics_tool`, `get_drawdown_metrics_tool` | ✅ 已覆盖第一版 | 已覆盖收益分布、年化波动、最大回撤、下行波动；后续补 Beta/VaR |
| 组合风险 | 组合暴露、行业暴露、因子暴露 | 持仓/复盘工具局部存在 | 🔴 缺失 | 缺组合风险指标、归因、压力测试 |
| 回测 | 信号回测、策略回测 | 暂无标准工具 | 🔴 缺失 | 缺 `run_signal_backtest` / `run_strategy_backtest` |
| 筛选 | 条件选股、因子筛选 | `screen_stocks_by_criteria`, `batch_check_profit_consistency` | 🟡 部分覆盖 | 缺把新标准能力纳入筛选字段和统一排序口径 |

---

## 4. 已完成的第一批标准能力

实现位置：

- Runtime API：[standard_financial_apis.py](file:///c:/TradingAgentsCN/core/skill_runtime/standard_financial_apis.py)
- Agent 工具：[standard_financial_tools.py](file:///c:/TradingAgentsCN/core/tools/implementations/fundamentals/standard_financial_tools.py)

### 4.1 历史年报财务序列

Runtime API：

```text
get_historical_financial_annual_series(symbol, years=10, source=None)
```

工具：

```text
get_historical_financial_annual_series_tool
```

用途：

- 获取 5-10 年完整年报序列；
- 替代从 `get_income_analysis` Markdown 中拼趋势；
- 支撑基本面、长期财务质量、盈利稳定性、现金流质量分析。

当前状态：已完成第一版。

后续增强：

- 增加字段完整性分数；
- 增加年报重述/修订版本选择策略；
- 增加更多现金流字段和资本开支字段适配。

---

### 4.2 盈利稳定性指标

Runtime API：

```text
get_profitability_stability_metrics(symbol, years=10, source=None)
```

工具：

```text
get_profitability_stability_metrics_tool
```

用途：

- 计算营收、净利润、ROE、毛利率长期稳定性；
- 输出均值、中位数、最小值、最大值、标准差、变异系数；
- 支撑护城河证据、长期盈利质量、质量稳定性判断。

当前状态：已完成第一版。

---

### 4.3 现金流质量趋势

Runtime API：

```text
get_cashflow_quality_trend(symbol, years=10, source=None)
```

工具：

```text
get_cashflow_quality_trend_tool
```

用途：

- 计算经营现金流/净利润；
- 计算自由现金流/净利润；
- 计算经营现金流率、自由现金流率；
- 支撑利润含金量、现金流质量、自由现金流质量分析。

当前状态：已完成第一版。

---

### 4.4 历史估值分位

Runtime API：

```text
get_historical_valuation_percentile(symbol, metrics=None, lookback_years=5, as_of_date=None)
```

工具：

```text
get_historical_valuation_percentile_tool
```

用途：

- 结构化计算 PE_TTM/PB/PS_TTM/PCF_TTM 历史估值分位；
- 替代 `get_stock_fundamentals_unified` 中隐藏的 3 年文本分位输出；
- 支撑估值安全边际、估值通道、历史分位分析。

当前状态：已完成第一版。

### 4.5 P1 深度分析能力

本轮补齐的 P1 Runtime API：

```text
get_margin_stability_metrics(symbol, years=10, source=None)
get_capital_efficiency_trend(symbol, years=10, source=None)
get_growth_quality_metrics(symbol, years=10, source=None)
get_single_stock_risk_profile(symbol, start_date=None, end_date=None, period="daily", limit=1000)
get_industry_fundamental_summary(symbol, peer_limit=100)
get_capital_flow_series(symbol, start_date=None, end_date=None, limit=120)
get_chip_distribution_context(symbol, trade_date=None)
```

对应 Agent 工具：

```text
get_margin_stability_metrics_tool
get_capital_efficiency_trend_tool
get_growth_quality_metrics_tool
get_single_stock_risk_profile_tool
get_industry_fundamental_summary_tool
get_capital_flow_series_tool
get_chip_distribution_context_tool
```

用途：

- 补齐利润率稳定性、资本效率和成长质量，支撑护城河、长期经营质量和成长质量判断；
- 补齐个股风险画像，统一收益分布、波动、回撤、下行风险等价格风险证据；
- 补齐行业基本面摘要，统一同行样本统计和头部样本；
- 补齐资金流序列和筹码上下文，作为交易辅助和市场行为证据。

当前状态：已完成第一版。

约束说明：

- `get_capital_flow_series` 当前优先读取本地资金流候选集合；本地未同步时回退调用 Tushare `moneyflow_ths` 即时获取个股资金流，若 Tushare 不可用或无权限则返回 `no_data` 和 warning。
- `get_chip_distribution_context` 依赖外部 AkShare/Tushare 筹码接口；测试允许 `success`、`no_data` 或 `error`，但成功时会验证字段正常范围。

---

## 5. 全系统 P0/P1 建议能力清单

如果按股票分析系统最小完整底座，建议 P0 是以下能力；P1 是本轮增强分析深度的通用能力。

| P0/P1 能力 | 当前状态 | 说明 |
|---|---|---|
| `get_security_master` | ✅ 已覆盖第一版 | 统一证券主数据入口，基于本地 basic/quote 聚合 |
| `get_adjusted_price_series` | ✅ 已覆盖第一版 | 标准化价格序列，当前复权状态为 as_stored |
| `get_return_series` | ✅ 已覆盖第一版 | 基于价格序列计算收益率 |
| `get_volatility_metrics` | ✅ 已覆盖第一版 | 基于收益率计算波动率、年化波动率 |
| `get_drawdown_metrics` | ✅ 已覆盖第一版 | 基于价格序列计算最大回撤和回撤序列 |
| `get_historical_financial_annual_series` | ✅ 已覆盖第一版 | 长期年报序列 |
| `get_profitability_stability_metrics` | ✅ 已覆盖第一版 | 盈利稳定性 |
| `get_cashflow_quality_trend` | ✅ 已覆盖第一版 | 现金流质量 |
| `get_debt_solvency_trend` | ✅ 已覆盖第一版 | 偿债能力长期趋势 |
| `get_current_valuation_snapshot` | ✅ 已覆盖第一版 | 当前估值快照 |
| `get_historical_valuation_percentile` | ✅ 已覆盖第一版 | 历史估值分位 |
| `get_peer_group` | ✅ 已覆盖第一版 | 标准同行组，基于行业 basic_info 样本 |
| `get_peer_relative_valuation` | ✅ 已覆盖第一版 | 同业估值统计与分位 |
| `get_peer_relative_quality` | ✅ 已覆盖第一版 | 同业质量指标相对位置 |
| `get_company_announcements` | 🟡 第一版代理 | 当前基于新闻识别公告线索；新增事件时间线可优先读取本地公告集合 |
| `get_company_event_timeline` | ✅ 已覆盖第一版 | 本地公告/监管事件集合优先，缺失时回退新闻代理分类，输出事件类型和严重度 |
| `get_risk_event_flags` | 🟡 第一版代理 | 当前基于新闻关键词识别 flags，后续仍可增强正式监管事件源 |
| `get_margin_stability_metrics` | ✅ 已覆盖第一版 | 毛利率、净利率、营业利润率、费用率稳定性 |
| `get_capital_efficiency_trend` | ✅ 已覆盖第一版 | ROE/ROA/ROIC、资产周转率、权益乘数长期趋势 |
| `get_growth_quality_metrics` | ✅ 已覆盖第一版 | 营收、净利润、经营现金流、自由现金流 CAGR 与增长稳定性 |
| `get_single_stock_risk_profile` | ✅ 已覆盖第一版 | 收益分布、波动率、最大回撤、下行波动等个股价格风险画像 |
| `get_industry_fundamental_summary` | ✅ 已覆盖第一版 | 同行样本市值、PE/PB、ROE 等行业基本面统计 |
| `get_industry_market_performance` | ✅ 已覆盖第一版 | 结构化行业涨跌、同行表现、目标相对行业分位与行业资金流上下文 |
| `get_peer_relative_growth` | ✅ 已覆盖第一版 | 营收/净利润/经营现金流/自由现金流 CAGR 同业分位 |
| `get_technical_indicator_series` | ✅ 已覆盖第一版 | MA/MACD/RSI/KDJ/BOLL/ATR/OBV/支撑压力历史序列 |
| `get_capital_flow_series` | ✅ 已覆盖第一版 | 本地个股资金流序列；本地缺失时回退 Tushare moneyflow_ths |
| `get_chip_distribution_context` | ✅ 已覆盖第一版 | 筹码获利比例、成本区间和集中度标准化上下文 |

本批实现位置：

- Runtime API：[standard_financial_apis.py](file:///c:/TradingAgentsCN/core/skill_runtime/standard_financial_apis.py)
- Agent 工具：[standard_financial_tools.py](file:///c:/TradingAgentsCN/core/tools/implementations/fundamentals/standard_financial_tools.py)
- 测试：[test_standard_financial_apis.py](file:///c:/TradingAgentsCN/tests/core/skill_runtime/test_standard_financial_apis.py)

验证状态：

```text
python -m py_compile core/skill_runtime/data_access.py core/skill_runtime/sync_wrappers.py core/skill_runtime/standard_financial_apis.py core/skill_runtime/__init__.py core/tools/implementations/fundamentals/standard_financial_tools.py tests/core/skill_runtime/test_standard_financial_apis.py
pytest tests/core/skill_runtime/test_standard_financial_apis.py -q
# 9 passed，包含 600519 P0/P1/P2 第一版严格真实数据矩阵验证

python -c "from core.tools.registry import ToolRegistry; import core.tools.implementations; r=ToolRegistry(); expected=['get_company_event_timeline_tool','get_business_segment_trend_tool','get_shareholder_return_metrics_tool','get_portfolio_risk_profile_tool','get_margin_stability_metrics_tool','get_capital_efficiency_trend_tool','get_growth_quality_metrics_tool','get_single_stock_risk_profile_tool','get_industry_fundamental_summary_tool','get_industry_market_performance_tool','get_peer_relative_growth_tool','get_technical_indicator_series_tool','get_capital_flow_series_tool','get_chip_distribution_context_tool']; print('missing=', [x for x in expected if not r.has_tool(x)]); print('count=', len(r.list_all()))"
# missing=[]，工具总数 173
```

严格真实数据矩阵已验证：

```text
get_security_master：success，基础信息/行业非空
get_adjusted_price_series：success，local，242 条 2024 日线
get_return_series：success，241 条收益率，收益率范围合理
get_volatility_metrics：success，年化波动率约 27.49%，范围合理
get_drawdown_metrics：success，最大回撤约 -27.28%，范围合理
get_historical_financial_annual_series：success，5 年年报
get_profitability_stability_metrics：success，收入/净利等指标非空
get_cashflow_quality_trend：success，5 年趋势
get_debt_solvency_trend：success，5 年趋势，资产负债率范围合理
get_current_valuation_snapshot：success，PE/PB 范围合理
get_historical_valuation_percentile：success，PE_TTM/PB 样本数 >= 60，分位在 0-100
get_peer_group：success，同行样本 >= 5
get_peer_relative_valuation：success，同行估值样本 >= 5
get_peer_relative_quality：success/partial，PB 同行样本 >= 5
get_company_announcements：success，公告代理识别 >= 1
get_risk_event_flags：success，近期新闻样本 >= 1
get_margin_stability_metrics：success，毛利率样本 >= 3，利润率范围 0-100
get_capital_efficiency_trend：success，趋势样本 >= 3，ROE 范围合理
get_growth_quality_metrics：success，年度增长样本 >= 2
get_single_stock_risk_profile：success，收益样本 >= 20，最大回撤在 -1 到 0
get_industry_fundamental_summary：success，同行样本 >= 5，PB 样本 >= 5
get_capital_flow_series：success/no_data；若 success 则样本非空且交易日非空
get_chip_distribution_context：success/no_data/error；若 success 则获利比例 0-1、平均成本 > 0
```

本轮验证发现并修复：

1. 本地 `stock_daily_quotes.trade_date` 同时存在 `YYYYMMDD` 和 `YYYY-MM-DD` 两种格式，原查询只支持 `YYYYMMDD`，导致误判本地无数据。已修复为同时兼容两种日期格式。
2. 外部行情 DataFrame 的日期在 index 中，原标准化会丢失 index 日期，导致 fallback 后记录被过滤为空。已修复表格标准化逻辑，保留非 RangeIndex 的日期索引。

---

## 6. 各类 Agent 的目标能力配置

### 6.1 基本面 Agent

目标能力：

```text
get_historical_financial_annual_series
get_profitability_stability_metrics
get_cashflow_quality_trend
get_debt_solvency_trend
get_capital_efficiency_trend
get_business_segment_trend
```

当前建议工具：

```text
get_historical_financial_annual_series_tool
get_profitability_stability_metrics_tool
get_margin_stability_metrics_tool
get_capital_efficiency_trend_tool
get_growth_quality_metrics_tool
get_cashflow_quality_trend_tool
get_debt_solvency_trend_tool
get_quality_factor_bundle_tool
get_growth_cashflow_factor_bundle_tool
get_balance_sheet_analysis
get_cashflow_analysis
```

缺口：`get_business_segment_trend_tool`、结构化股东回报/分红回购长期趋势。`get_debt_solvency_trend_tool`、`get_capital_efficiency_trend_tool`、`get_margin_stability_metrics_tool`、`get_growth_quality_metrics_tool` 已完成第一版。

---

### 6.2 估值 Agent

目标能力：

```text
get_current_valuation_snapshot
get_historical_valuation_percentile
get_peer_relative_valuation
get_industry_valuation_distribution
get_growth_adjusted_valuation
```

当前建议工具：

```text
get_value_factor_bundle_tool
get_historical_valuation_percentile_tool
get_peer_comparison
summarize_industry_valuation
```

缺口：`get_industry_valuation_distribution`、`get_growth_adjusted_valuation`、质量调整估值上下文。

---

### 6.3 技术分析 Agent

目标能力：

```text
get_adjusted_price_series
get_moving_average_bundle
get_momentum_indicators
get_trend_indicators
get_support_resistance_levels
get_breakout_signal_context
```

当前建议工具：

```text
get_stock_market_data_unified
get_technical_factor_bundle_tool
get_index_technical
```

缺口：完整历史指标序列、支撑压力位、突破信号上下文、ATR/BOLL/OBV 等。

---

### 6.4 风险分析 Agent

目标能力：

```text
get_volatility_metrics
get_drawdown_metrics
get_risk_event_flags
get_debt_solvency_trend
get_single_stock_risk_profile
get_financial_risk_factor_bundle
```

当前建议工具：

```text
primary:
- get_financial_risk_factors

specialized:
- get_cashflow_quality_trend_tool
- get_risk_event_flags_tool
- get_debt_solvency_trend_tool
- get_single_stock_risk_profile_tool

supporting:
- get_cashflow_analysis
- get_balance_sheet_analysis
- get_quality_factor_bundle_tool

generic / fallback:
- get_stock_fundamentals_unified
- get_income_analysis
```

缺口：Beta/VaR、组合风险、正式公告/监管事件源。个股收益分布、波动、回撤、下行波动和新闻关键词风险 flags 已完成第一版。

治理要求：风险分析 Agent 不能只把上述工具平铺到 `required_tools`。如果 Agent 的核心职责是“财报风险信号识别 / 商誉、应收、现金流风险识别”，应将 `get_financial_risk_factors` 标记为主入口工具；`get_cashflow_analysis`、`get_balance_sheet_analysis`、`get_stock_fundamentals_unified` 只能补充或降级，不能替代主入口。

---

### 6.5 行业分析 Agent

目标能力：

```text
get_sector_constituents
get_industry_fundamental_summary
get_industry_market_performance
get_peer_relative_quality
get_peer_relative_growth
```

当前建议工具：

```text
get_sector_data
get_sector_analysis
get_sector_constituents
get_peer_group_tool
get_peer_relative_quality_tool
get_industry_fundamental_summary_tool
get_peer_comparison
analyze_sector
get_fund_flow_data
```

缺口：同业成长分位、行业市场表现、行业资金流和行业景气度。行业基本面汇总、标准同行组和同业质量分位已完成第一版。

---

### 6.6 交易辅助 Agent

目标能力：

```text
get_market_snapshot
get_technical_indicators
get_capital_flow_series
get_chip_distribution_context
get_turnover_activity_metrics
get_risk_event_flags
```

当前建议工具：

```text
get_stock_market_data_unified
get_technical_factor_bundle_tool
get_capital_flow_series_tool
get_chip_distribution_context_tool
get_risk_event_flags_tool
get_fund_flow_data
get_north_flow
get_margin_trading
get_chip_distribution
get_limit_stats
```

缺口：换手活跃度指标、主力资金上下文、北向/融资融券上下文增强。个股资金流序列、标准化筹码上下文和风险事件 flags 已完成第一版。

---

### 6.7 组合管理 Agent

目标能力：

```text
get_portfolio_exposure
get_portfolio_risk_metrics
get_factor_exposure
get_position_attribution
get_scenario_stress_test
```

当前建议工具：

```text
list_positions
get_position_analysis
trigger_position_analysis
交易复盘相关工具
```

缺口：组合暴露、行业暴露、因子暴露、归因、压力测试。

---

## 7. 实施顺序建议

### 第一阶段：补齐系统底座 P0

状态：**已完成第一版**。

已实现：

```text
1. get_security_master
2. get_adjusted_price_series
3. get_return_series
4. get_volatility_metrics
5. get_drawdown_metrics
6. get_debt_solvency_trend
7. get_peer_group
8. get_peer_relative_valuation
9. get_peer_relative_quality
10. get_company_announcements（新闻代理版）
11. get_risk_event_flags（新闻关键词版）
12. get_margin_stability_metrics
13. get_capital_efficiency_trend
14. get_growth_quality_metrics
15. get_single_stock_risk_profile
16. get_industry_fundamental_summary
17. get_capital_flow_series
18. get_chip_distribution_context
```

说明：价格风险底座、同业标准化、偿债趋势、P1 深度分析能力以及公告事件/主营结构/股东回报/组合风险第一版已经补齐。公告和风险事件当前优先读本地公告/监管事件集合，缺失时回退新闻代理；资金流当前优先读取本地候选集合，缺失时回退 Tushare `moneyflow_ths`。

---

### 第二阶段：增强分析深度 P1

状态：**已完成第一版**。

```text
get_margin_stability_metrics
get_capital_efficiency_trend
get_growth_quality_metrics
get_industry_fundamental_summary
get_capital_flow_series
get_chip_distribution_context
get_single_stock_risk_profile
```

目标：增强护城河、同业比较、成长质量、技术/资金面和风险画像。

---

### 第三阶段：沉淀高级聚合能力 P2

```text
get_moat_evidence_bundle
get_valuation_safety_margin_bundle
get_financial_health_evidence_bundle
get_technical_signal_bundle
get_event_risk_bundle
get_portfolio_risk_bundle
```

目标：将多个标准 API 组合为高层业务 Skill，减少 Agent 编排负担。

---

## 8. 不建议作为核心标准能力的工具形态

以下工具可以保留，但不建议作为长期结构化分析的主入口：

| 工具 | 问题 | 建议用法 |
|---|---|---|
| `get_stock_fundamentals_unified` | Markdown 输出，部分能力隐藏在文本中 | 总览展示，不作为结构化计算入口 |
| `get_income_analysis` | 默认混合季度/年报，输出 Markdown | 利润表文字摘要，不用于 5-10 年年报序列 |
| `get_cashflow_analysis` | 适合摘要，不适合作为长期结构化趋势主入口 | 补充解释 |
| `get_balance_sheet_analysis` | 适合摘要，不适合作为长期结构化趋势主入口 | 补充解释 |
| `get_peer_comparison` | 有价值，但偏报告型/当前横截面 | 作为同业对比入口，后续补结构化 peer relative API |
| `get_stock_market_data_unified` | 总览型市场数据工具 | 补充展示，不替代价格序列/风险指标标准 API |
| 新闻/情绪工具 | 噪声较多，不应影响核心财务质量判断 | 作为事件补充 |

---

## 9. Skill 生成器约束

后续 Skill 生成器应优先遵守：

1. 如果需求涉及长期年报序列，优先使用 `get_historical_financial_annual_series`。
2. 如果需求涉及盈利稳定性，优先使用 `get_profitability_stability_metrics`；如果重点是利润率和费用率，优先使用 `get_margin_stability_metrics`。
3. 如果需求涉及现金流质量，优先使用 `get_cashflow_quality_trend`。
4. 如果需求涉及资本效率、ROE/ROA/ROIC 或杜邦基础指标，优先使用 `get_capital_efficiency_trend`。
5. 如果需求涉及成长质量、收入/利润/现金流 CAGR 或增长稳定性，优先使用 `get_growth_quality_metrics`。
6. 如果需求涉及历史 PE/PB/PS/PCF 分位，优先使用 `get_historical_valuation_percentile`。
7. 如果需求涉及价格收益、波动、回撤，应优先使用 `get_return_series`、`get_volatility_metrics`、`get_drawdown_metrics` 或 `get_single_stock_risk_profile`，而不是自行从 K 线计算。
8. 如果需求涉及同业相对位置，应优先使用标准 peer relative API；如果需求涉及行业基本面背景，优先使用 `get_industry_fundamental_summary`。
9. 如果需求涉及资金面，优先使用 `get_capital_flow_series`；本地无资金流数据时应保留 `no_data` 和 warning，不要伪造。
10. 如果需求涉及筹码分布、成本集中度或获利盘比例，优先使用 `get_chip_distribution_context`。
11. 不允许从 `get_income_analysis` / `get_stock_fundamentals_unified` 的 Markdown 文本中解析关键数值作为计算依据。
12. 不允许 LLM 自行计算关键数值、评分、分位、权重、排序。
13. 如果标准 API 缺字段，必须返回 warning 或标记信息缺口，而不是猜测。

---

## 10. Agent Builder 工具路由治理改进

### 10.1 问题背景

近期在 Agent 工坊验证“财报风险信号识别”类 Agent 时，出现过以下现象：

```text
版本 required_tools 中同时存在专项风险工具和通用财务工具。
运行时 LLM 实际调用了 get_cashflow_analysis / get_balance_sheet_analysis 等通用或补充工具，
但没有调用预期主入口 get_financial_risk_factors / get_cashflow_quality_trend_tool / get_risk_event_flags_tool。
最终报告文字基本可读，但工具链没有按设计执行，输出格式也偏离了规格。
```

这说明问题不只是“是否绑定了工具”，而是**系统没有稳定表达每个工具在当前 Agent 里的角色**。当多个工具描述里都含有“现金流”“风险”“财务质量”“基本面”等相似字眼时，LLM 会把它们当成可互换工具，自行选择更熟悉或更泛化的工具。

### 10.2 根因分析

当前链路的主要弱点：

1. `required_tools` 是平铺列表，缺少角色和优先级。  
   例如 `get_financial_risk_factors`、`get_cashflow_quality_trend_tool`、`get_cashflow_analysis`、`get_stock_fundamentals_unified` 同时出现时，运行时只知道“都可用”，不知道谁是主入口、谁是补充、谁只能兜底。

2. Agent Builder 会在版本构建时自动合并部分默认工具。  
   对估值、基本面、风险类 Agent，这能提高可用性，但也会把大而全的通用工具混入专项 Agent，稀释主工具的选择权重。

3. 工具描述相似时，LLM 只能基于自然语言猜测。  
   `description`、`when_to_use`、`when_not_to_use` 有帮助，但不等价于确定性的工具路由策略。尤其当两个工具都宣称覆盖“现金流质量”时，LLM 不知道“结构化长期指标工具”应优先于“Markdown 摘要工具”。

4. 评估当前更关注输出文本质量，缺少工具路由验收。  
   如果报告覆盖了三大维度且结论合理，但没有调用主入口工具，评估器可能仍认为内容可接受，无法识别“工具链绕路”。

### 10.3 术语：不要只分通用/专用，要定义工具角色

后续不建议只把工具粗分为“通用工具”和“专用工具”。更稳定的做法是按当前 Agent 任务生成工具角色：

| 工具角色 | 含义 | 使用规则 |
|---|---|---|
| `primary` | 当前 Agent 的主入口工具，承担核心业务闭环 | 任务命中对应能力时必须优先调用；可作为首个或前置工具调用 |
| `specialized` | 某个子问题的确定性结构化工具 | 优先用于对应子能力，不被 Markdown 摘要或总览工具替代 |
| `supporting` | 补充证据、补字段、交叉验证工具 | 只能增强主工具结果，不能替代主工具完成核心判断 |
| `generic` | 大而全的总览工具 | 用于背景概览，不作为专项计算和专项风险识别主依据 |
| `fallback` | 降级工具 | 只有主工具无数据、不可用或规格允许降级时使用 |

示例：财报风险信号识别 Agent 的工具角色应类似：

```json
{
  "primary_tools": ["get_financial_risk_factors"],
  "specialized_tools": [
    "get_cashflow_quality_trend_tool",
    "get_risk_event_flags_tool",
    "get_debt_solvency_trend_tool"
  ],
  "supporting_tools": [
    "get_cashflow_analysis",
    "get_balance_sheet_analysis",
    "get_quality_factor_bundle_tool"
  ],
  "fallback_tools": [
    "get_stock_fundamentals_unified",
    "get_income_analysis"
  ]
}
```

### 10.4 目标改进：生成 `tool_selection_policy`

Agent Builder 后续构建版本时，不应只写：

```json
{
  "required_tools": ["tool_a", "tool_b", "tool_c"]
}
```

而应同时写入结构化工具路由策略：

```json
{
  "required_tools": ["get_financial_risk_factors", "get_cashflow_quality_trend_tool"],
  "tool_selection_policy": {
    "primary_tools": ["get_financial_risk_factors"],
    "required_first_call_tools": ["get_financial_risk_factors"],
    "specialized_tools": ["get_cashflow_quality_trend_tool", "get_risk_event_flags_tool"],
    "supporting_tools": ["get_cashflow_analysis", "get_balance_sheet_analysis"],
    "fallback_tools": ["get_stock_fundamentals_unified"],
    "substitution_rules": [
      {
        "capability": "financial_risk_signal_detection",
        "preferred": "get_financial_risk_factors",
        "not_replaced_by": [
          "get_stock_fundamentals_unified",
          "get_income_analysis",
          "get_cashflow_analysis",
          "get_balance_sheet_analysis"
        ]
      }
    ]
  }
}
```

这份策略应同步进入：

- `agent_versions.evaluation_policy.tool_selection_policy`；
- `agent_versions.agent_metadata.tool_selection_policy`；
- UniversalAgent 运行时配置中的 `metadata.tooling_contract`；
- Prompt 模板的 `tool_guidance` 和 `constraints`；
- 评估器的 tool trace 检查逻辑。

### 10.5 谁来区分工具角色

责任边界如下：

| 组件 | 责任 |
|---|---|
| 工具注册元数据 | 声明工具能力标签、适用场景、不适用场景、输出形态、是否结构化、是否总览型 |
| Capability Index | 按能力原语检索候选工具，而不是只按工具名关键词匹配 |
| Agent Builder | 根据 Agent 规格和能力需求生成 `tool_selection_policy`，决定 primary/specialized/supporting/generic/fallback |
| 运行时 LLM | 按 `tool_selection_policy` 调用工具，不自行把 supporting/generic 当 primary |
| 评估器 | 检查 tool trace 是否符合策略；主工具未调用、通用工具替代主工具时应判定为 revise 或 blocker |

关键点：**LLM 不应该是唯一决策者**。LLM 可以辅助理解业务目标，但最终工具角色必须由 Agent Builder 固化到版本配置。

### 10.6 相似工具描述时的确定性选择规则

当多个工具描述中出现相似字眼时，按以下规则处理：

1. **能力原语优先于关键词**  
   先判断任务需要的是“财务风险因子识别”“长期现金流质量趋势”“资产负债结构摘要”还是“总览基本面”，再匹配工具。不能因为工具描述都含“现金流”就认为等价。

2. **角色优先级固定**  
   同一能力下选择顺序为：

   ```text
   primary > specialized > supporting > generic > fallback
   ```

3. **结构化计算工具优先于 Markdown 报告工具**  
   需要数值、趋势、分位、评分、排序、稳定性指标时，优先使用结构化标准 API / Tool。报告型 Markdown 工具只能辅助解释。

4. **主入口不可被总览工具替代**  
   如果 `tool_selection_policy.primary_tools` 声明了主工具，除非主工具返回 `no_data` / `error` / 明确不适用，否则不能用 `get_stock_fundamentals_unified`、`get_income_analysis` 等总览工具替代。

5. **补充工具只能补证据**  
   `supporting` 工具可以用于交叉验证或补充说明，但最终报告必须标明主结论来自 primary/specialized 工具。

### 10.7 评估验收标准

后续 Agent 工坊评估应增加工具路由验收：

| 场景 | 期望结果 |
|---|---|
| `required_first_call_tools` 未调用 | 至少 `revise`，核心任务受影响时 `reject/blocker` |
| 使用 `generic/fallback` 替代 `primary`，且主工具未失败 | `tool_routing_violation` |
| 输出核心数值但 tool trace 中没有结构化计算工具 | `numeric_traceability_violation` |
| supporting 工具被用于主结论，primary 工具未调用 | `primary_tool_missing` |
| fallback 工具被使用但报告未说明降级原因 | `fallback_without_disclosure` |

示例验收：财报风险信号识别 Agent 至少应满足：

```text
必须调用：get_financial_risk_factors
现金流趋势场景优先调用：get_cashflow_quality_trend_tool
事件风险场景优先调用：get_risk_event_flags_tool
若调用 get_cashflow_analysis / get_balance_sheet_analysis，只能作为补充证据
若调用 get_stock_fundamentals_unified，必须说明它是总览/降级来源，不得替代主风险因子判断
```

### 10.8 实施任务

建议按以下顺序改进：

1. 为核心金融工具补充元数据字段或等价配置：`capability_tags`、`tool_role_hint`、`output_shape`、`aggregation_level`、`preferred_for`、`not_replacement_for`。
2. 改造 Agent Builder 的 `_select_required_tools`，不再只返回平铺工具列表，而是同时生成 `tool_selection_policy`。
3. 改造版本构建和 `sync_version_required_tools`，保存并同步 `tool_selection_policy`。
4. 改造 Prompt 模板生成，将工具路由表写入 `tool_guidance`，明确主工具、补充工具和 fallback 规则。
5. 改造 UniversalAgent 运行时配置，把 `default_tools` 从“所有 required_tools”调整为“primary + specialized 优先，supporting/fallback 后置”。
6. 改造评估器，读取 tool trace 并检查 `required_first_call_tools`、`substitution_rules` 和 fallback 披露。
7. 增加回归测试：构造含相似描述工具的版本，验证 LLM/运行时优先调用 primary 工具，且错误替代会被评估器识别。

---

## 11. 当前结论

当前系统已经有较多工具，但能力形态不均衡：

```text
报告型工具较多
结构化标准 API 明显增加
P0 底座、P1 深度分析能力以及公告事件/主营结构/股东回报/组合风险第一版已完成
回购数据源、公告正文抽取、组合 Beta/压力测试、主营分部跨期名称归一化仍是后续增强项
```

已经完成第一批结构化能力：

```text
长期年报序列
盈利稳定性
现金流质量趋势
历史估值分位
```

下一步从“股票分析系统通用底座”角度，最值得优先补：

```text
get_security_master
get_adjusted_price_series
get_return_series
get_volatility_metrics
get_drawdown_metrics
get_debt_solvency_trend
get_peer_relative_quality
get_company_announcements
get_risk_event_flags
```

这些补齐后，系统会从“多个分析工具集合”逐步升级为“标准化股票分析能力平台”。
