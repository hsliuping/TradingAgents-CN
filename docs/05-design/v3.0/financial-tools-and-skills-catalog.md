# 财经领域工具与技能目录

> 文档版本：v1.0  
> 创建时间：2026-06-29  
> 适用范围：Agent 工坊、Skill 生成器、股票分析系统  

---

## 1. 设计原则

### 1.1 分层架构

```
┌──────────────────────────────────────────┐
│  Agent 编排层（选择、解释、报告）          │
├──────────────────────────────────────────┤
│  Skill 组合层（多工具组合为领域能力）       │
├──────────────────────────────────────────┤
│  工具层（数据拉取 + 确定性计算）            │
│  ├─ 手写工具：核心财务计算、风险评分、估值   │
│  └─ Agent 生成工具：轻量组合、适配、胶水     │
├──────────────────────────────────────────┤
│  Runtime API 层（标准数据原语）             │
└──────────────────────────────────────────┘
```

### 1.2 手写 vs 生成的分界

| 类别 | 手写实现 | Agent/Skill 生成器生成 |
|------|----------|------------------------|
| 核心计算逻辑 | ✅ 确定性公式，需审计追踪 | ❌ |
| 财务模型 | ✅ 估值模型、风险评分 | ❌ |
| 数据拉取适配 | ✅ 数据源对接、字段映射 | ❌ |
| 统计分析 | ✅ 回归、回测、模拟 | ❌ |
| 业务组合 | ❌ | ✅ 把多个已有工具拼成业务 Skill |
| 报告模板 | ❌ | ✅ 按用户要求调整输出风格 |
| 策略规则 | ❌ | ✅ 用户自定义选股/风控规则 |

**核心原则**：凡是涉及数值计算、公式推导、财务模型、统计推断的工具，必须手工编写。Agent 和 Skill 生成器只负责组合、编排、适配。

---

## 2. 工具实现状态总览

标记说明：

| 标记 | 含义 |
|------|------|
| ✅ | 已完成，可用 |
| 🟡 | 部分覆盖，需增强 |
| 🔴 | 缺失，待实现 |
| ⏳ | 设计中，即将实现 |

---

## 3. 估值模型

### 3.1 绝对估值

| 工具名称 | 工具 ID（建议） | 状态 | 说明 |
|----------|----------------|------|------|
| DCF 两阶段估值 | `get_dcf_valuation` | ✅ | 显式预测期 + 永续期；4 参数，3 情景(牛/基/熊)，敏感性矩阵 |
| DCF 三阶段估值 | `get_dcf_three_stage_valuation` | ✅ | 高增长→过渡→永续，适合成长股 |
| 股利贴现模型 | `get_ddm_valuation` | ✅ | 股利增长率模型；适合高分红股 |
| 剩余收益估值 | `get_residual_income_valuation` | ✅ | 基于账面价值 + 超额收益现值 |
| 经济增加值估值 | `get_eva_valuation` | ✅ | EVA = NOPAT - 资本成本 |
| 自由现金流计算 | `get_fcff_fcfe_calculation` | ✅ | FCFF/FCFE 标准计算，支撑 DCF |

### 3.2 相对估值

| 工具名称 | 工具 ID（建议） | 状态 | 说明 |
|----------|----------------|------|------|
| 可比公司估值 | `get_comparable_company_valuation` | ✅ | PE/PB/PS/EV/EBITDA 多口径 |
| 行业估值分布 | `get_industry_valuation_distribution` | ✅ | 已有 `summarize_industry_valuation`，需增强分位和分布图 |
| PEG 估值 | `get_peg_valuation` | ✅ | 含增长预估的 PEG 估值 |
| 格雷厄姆估值 | `get_graham_valuation` | ✅ | Graham Number：√(22.5 × EPS × BVPS) |
| 股息估值 | `get_dividend_valuation_context` | ✅ | 现有 `get_dividend_data`、`get_shareholder_return_metrics`，需补股息率估值 |

### 3.3 估值辅助

| 工具名称 | 工具 ID（建议） | 状态 | 说明 |
|----------|----------------|------|------|
| WACC 计算器 | `get_wacc_calculation` | ✅ | 债务成本 + 股权成本 + 资本结构权重；默认 Rf=2.5%, ERP=6%, 税率=25% |
| CAPM 股权成本 | `get_capm_cost_of_equity` | ✅ | Rf + β × ERP |
| 增长质量调整 | `get_growth_adjusted_valuation` | ✅ | 增长质量、持久性、可持续性调整 |

### 3.4 杜邦分析

| 工具名称 | 工具 ID（建议） | 状态 | 说明 |
|----------|----------------|------|------|
| 杜邦分析（3因子） | `get_dupont_analysis` | ✅ | ROE = 净利率 × 资产周转率 × 权益乘数 |
| 杜邦分析（5因子） | 同上 | ✅ | ROE = 税负 × 利息负担 × 经营利润率 × 周转率 × 杠杆 |

---

## 4. 风险评分与财务健康

### 4.1 经典评分模型

| 工具名称 | 工具 ID（建议） | 状态 | 说明 |
|----------|----------------|------|------|
| Altman Z-Score | `get_altman_zscore` | ✅ | 破产风险：1.2×X1 + 1.4×X2 + 3.3×X3 + 0.6×X4 + 1.0×X5；安全/灰色/破产 三区 |
| Beneish M-Score | `get_beneish_mscore` | ✅ | 盈余操纵概率：8 个财务指标加权，阈值 -1.78 |
| Piotroski F-Score | `get_piotroski_fscore` | ✅ | 基本面质量 0-9 分；盈利(4)/杠杆(3)/运营(2) 9 项 |
| Ohlson O-Score | `get_ohlson_oscore` | ✅ | Logit 破产预测模型 |
| 财务造假信号检测 | `get_financial_fraud_signals` | ✅ | 收入/应收/存货/现金流等 12+ 信号 |

### 4.2 盈利与现金流质量

| 工具名称 | 工具 ID（建议） | 状态 | 说明 |
|----------|----------------|------|------|
| 盈利质量评分 | `get_earnings_quality_score` | ✅ | 应计/现金流稳定性/盈利持续性/FCF覆盖/一次性项目 五维度 0-100 分 |
| 现金流质量深度 | `get_cashflow_quality_deep` | ✅ | 已有 `get_cashflow_quality_trend`，需补自由现金流/资本开支深度分析 |
| 商誉减值风险 | `get_goodwill_analysis` | ✅ | 商誉规模、占净资产比、减值风险 |
| 应收账款质量 | `get_receivables_quality` | ✅ | 账龄结构、坏账计提、周转天数异常 |
| 存货质量 | `get_inventory_quality` | ✅ | 存货周转、跌价准备、库龄结构 |

### 4.3 偿债与流动性

| 工具名称 | 工具 ID（建议） | 状态 | 说明 |
|----------|----------------|------|------|
| 偿债能力综合 | `get_debt_solvency_trend` | ✅ | 资产负债率、流动/速动比率、利息保障 |
| 流动性压力测试 | `get_liquidity_stress_test` | ✅ | 短期偿债缺口、现金覆盖天数 |
| 债务结构分析 | `get_debt_structure_analysis` | ✅ | 长短债比、到期结构、利率敏感性 |

---

## 5. 投资组合管理

### 5.1 风险度量

| 工具名称 | 工具 ID（建议） | 状态 | 说明 |
|----------|----------------|------|------|
| VaR 计算（历史/参数法） | `get_var_calculation` | ✅ | 95%/99% 置信度 VaR + CVaR，支持历史模拟法和参数法 |
| CVaR（Expected Shortfall） | 同上 | ✅ | 尾部风险度量 |
| Beta 计算 | `get_beta_calculation` | ✅ | 相对基准的 Beta + Alpha 年化 + R² |
| 最大回撤分析 | `get_drawdown_metrics` | ✅ | 已完成第一版 |
| 波动率分析 | `get_volatility_metrics` | ✅ | 已完成第一版 |
| 投资组合风险画像 | `get_portfolio_risk_profile` | ✅ | 已有 `get_portfolio_risk_profile_tool`，需增强 |

### 5.2 优化与模拟

| 工具名称 | 工具 ID（建议） | 状态 | 说明 |
|----------|----------------|------|------|
| 有效前沿 | `get_efficient_frontier` | ✅ | Markowitz 均值-方差优化 |
| 蒙特卡洛模拟 | `get_monte_carlo_simulation` | ✅ | 价格路径模拟、组合收益分布 |
| 压力测试 | `get_portfolio_stress_test` | ✅ | 预设场景（2008、2015、2020等）测算 |
| 情景分析 | `get_scenario_analysis` | ✅ | 用户自定义多情景分析 |

### 5.3 归因分析

| 工具名称 | 工具 ID（建议） | 状态 | 说明 |
|----------|----------------|------|------|
| 因子归因 | `get_factor_attribution` | ✅ | Fama-French 三/五因子归因 |
| Brinson 归因 | `get_brinson_attribution` | ✅ | 配置效应 + 选择效应 + 交互效应 |
| 行业归因 | `get_sector_attribution` | ✅ | 行业配置贡献 vs 行业选股贡献 |

### 5.4 绩效评估

| 工具名称 | 工具 ID（建议） | 状态 | 说明 |
|----------|----------------|------|------|
| 夏普比率 | `get_sharpe_ratio` | ✅ | (Rp - Rf) / σp；含索提诺比率、卡尔玛比率、年化收益/波动/最大回撤 |
| 索提诺比率 | `get_sortino_ratio` | ✅ | 下行风险调整收益 |
| 特雷诺比率 | `get_treynor_ratio` | ✅ | (Rp - Rf) / βp |
| 信息比率 | `get_information_ratio` | ✅ | 相对基准的超额收益 / 跟踪误差 |
| Calmar 比率 | `get_calmar_ratio` | ✅ | 年化收益 / 最大回撤 |
| 詹森 Alpha | `get_jensen_alpha` | ✅ | CAPM 超额收益 |

---

## 6. 技术分析

### 6.1 趋势与动量

| 工具名称 | 工具 ID（建议） | 状态 | 说明 |
|----------|----------------|------|------|
| 技术指标序列 | `get_technical_indicator_series` | ✅ | MA/MACD/RSI/KDJ/BOLL/ATR 历史序列 |
| 交叉信号检测 | `get_crossover_signals` | ✅ | MA/MACD/KDJ 金叉死叉 + 零轴穿越 + 价格突破均线 + 均线多空排列 |
| ADX 趋势强度 | `get_adx_trend_strength` | ✅ | 趋势强度指标，含 +DI/-DI |
| MACD 背离检测 | `get_macd_divergence` | ✅ | 顶背离/底背离自动识别 |
| RSI 背离检测 | `get_rsi_divergence` | ✅ | 顶背离/底背离自动识别 |

### 6.2 形态识别

| 工具名称 | 工具 ID（建议） | 状态 | 说明 |
|----------|----------------|------|------|
| K 线形态识别 | `get_candlestick_patterns` | ✅ | 锤子线、吞没、十字星、晨星/黄昏之星、三兵/三鸦等 25+ 形态 |
| 经典技术形态 | `get_chart_patterns` | ✅ | 头肩顶底、双顶双底、三角、旗形、楔形 |
| 斐波那契回调 | `get_fibonacci_retracement` | ✅ | 0.236/0.382/0.5/0.618/0.786 回调位 |
| 斐波那契扩展 | `get_fibonacci_extension` | ✅ | 1.272/1.618 等扩展位 |

### 6.3 支撑压力

| 工具名称 | 工具 ID（建议） | 状态 | 说明 |
|----------|----------------|------|------|
| 支撑压力位计算 | `get_support_resistance_levels` | ✅ | 枢轴点(Pivot) + 历史极值聚类，各输出 3 档支撑/压力 |
| 枢轴点（Pivot Points） | `get_pivot_points` | ✅ | 传统/斐波那契/Woodie/Camarilla |
| 成交量分布（Volume Profile） | `get_volume_profile` | ✅ | 按价格分布的成交量 |

### 6.4 成交量分析

| 工具名称 | 工具 ID（建议） | 状态 | 说明 |
|----------|----------------|------|------|
| 成交量加权均价 VWAP | `get_vwap` | ✅ | 日内/日间 VWAP |
| 能量潮 OBV | `get_obv_analysis` | ✅ | 成交量趋势确认 |
| 量价背离 | `get_volume_price_divergence` | ✅ | 价升量缩/价跌量增等背离 |
| 换手率分析 | `get_turnover_analysis` | ✅ | 换手率趋势、异常放量/缩量 |

---

## 7. 宏观经济

### 7.1 利率与债券

| 工具名称 | 工具 ID（建议） | 状态 | 说明 |
|----------|----------------|------|------|
| 收益率曲线分析 | `get_yield_curve_analysis` | ✅ | 期限结构、利差、倒挂检测 |
| 债券收益率计算 | `get_bond_yield_calculation` | ✅ | YTM/YTC/Current Yield |
| 债券久期与凸性 | `get_bond_duration_convexity` | ✅ | Macaulay/修正久期、凸性 |
| 信用利差分析 | `get_credit_spread_analysis` | ✅ | 不同评级债券的信用利差 |

### 7.2 宏观指标

| 工具名称 | 工具 ID（建议） | 状态 | 说明 |
|----------|----------------|------|------|
| 宏观指标仪表盘 | `get_macro_dashboard` | ✅ | GDP/CPI/PMI/M2/社融/利率 汇总 |
| 货币环境分析 | `get_monetary_environment` | ✅ | 利率周期、准备金率、公开市场操作 |
| 经济周期定位 | `get_economic_cycle_position` | ✅ | 美林时钟：复苏/过热/滞涨/衰退 |
| 行业轮动信号 | `get_sector_rotation_signals` | ✅ | 基于经济周期的行业配置建议 |

---

## 8. 事件分析

| 工具名称 | 工具 ID（建议） | 状态 | 说明 |
|----------|----------------|------|------|
| 事件研究法 | `get_event_study` | ✅ | CAR（累计异常收益）/ BHAR 计算 |
| 公告影响分析 | `get_announcement_impact` | ✅ | 已有新闻工具，需补定量影响分析 |
| 业绩预告分析 | `get_earnings_surprise_analysis` | ✅ | 预告 vs 实际，超预期/低于预期 |
| 除权除息分析 | `get_corporate_action_analysis` | 🔴 | 分红、送转、配股影响 |
| 减持/增持分析 | `get_insider_trading_analysis` | 🔴 | 高管/大股东增减持跟踪 |

---

## 9. 市场微观结构

| 工具名称 | 工具 ID（建议） | 状态 | 说明 |
|----------|----------------|------|------|
| 订单流分析 | `get_order_flow_analysis` | 🔴 | 大单/中单/小单流向（需 L2 数据） |
| 融资融券分析 | `get_margin_trading_analysis` | ✅ | 已有 `get_margin_trading`，需补趋势和信号 |
| 北向资金分析 | `get_northbound_analysis` | ✅ | 已有 `get_north_flow`，需补累计趋势和行业分布 |
| 限售解禁日历 | `get_lockup_expiry_calendar` | 🔴 | 未来解禁规模和时间表 |

---

## 10. 筛选与排序

| 工具名称 | 工具 ID（建议） | 状态 | 说明 |
|----------|----------------|------|------|
| 多因子选股 | `get_multi_factor_screening` | ✅ | 已有 `screen_stocks_by_criteria`，需增强因子组合 |
| 格雷厄姆式筛选 | `get_graham_screen` | ✅ | 低PE + 低PB + 低负债 + 正盈利 |
| 成长股筛选 | `get_growth_stock_screen` | ✅ | 高增长 + 高ROE + 合理估值 |
| 红利股筛选 | `get_dividend_stock_screen` | ✅ | 高股息率 + 连续分红 + 现金流稳定 |
| 困境反转筛选 | `get_turnaround_screen` | ✅ | 低估值 + 盈利改善 + 现金流回升 |

---

## 11. 衍生品

| 工具名称 | 工具 ID（建议） | 状态 | 说明 |
|----------|----------------|------|------|
| 期权定价（Black-Scholes） | `get_black_scholes_price` | ✅ | 欧式期权定价 |
| 隐含波动率 | `get_implied_volatility` | ✅ | 从期权价格反推隐含波动率 |
| 希腊字母计算 | `get_option_greeks` | ✅ | Delta/Gamma/Theta/Vega/Rho |
| 期权策略盈亏图 | `get_option_strategy_pnl` | ✅ | 价差、跨式、宽跨式等组合策略 |

---

## 12. 统计与计量

| 工具名称 | 工具 ID（建议） | 状态 | 说明 |
|----------|----------------|------|------|
| 相关性矩阵 | `get_correlation_matrix` | ✅ | 多资产收益率相关性 |
| 协整检验 | `get_cointegration_test` | ✅ | 配对交易基础 |
| 滚动回归 | `get_rolling_regression` | ✅ | 滚动 Beta/Alpha 估计 |
| 正态性检验 | `get_normality_test` | ✅ | Jarque-Bera / Shapiro-Wilk |
| 平稳性检验 | `get_stationarity_test` | ✅ | ADF 单位根检验 |
| GARCH 波动率建模 | `get_garch_volatility` | ✅ | 波动率聚集效应 |

---

## 13. 实施优先级

### P0：立即实现（本阶段）

基础薄弱的最高频能力，Agent 经常需要但系统没有：

```
1. get_dcf_valuation              DCF 两阶段估值 ✅
2. get_wacc_calculation           WACC 计算器 ✅
3. get_altman_zscore              Altman Z-Score ✅
4. get_piotroski_fscore           Piotroski F-Score ✅
5. get_beneish_mscore             Beneish M-Score ✅
6. get_earnings_quality_score     盈利质量评分 ✅
7. get_beta_calculation           Beta 计算 ✅
8. get_sharpe_ratio               夏普比率 ✅
9. get_var_calculation            VaR 计算 ✅
10. get_candlestick_patterns      K 线形态识别 ✅
11. get_support_resistance_levels 支撑压力位计算 ✅
12. get_crossover_signals         均线/MACD/KDJ 交叉信号 ✅
```

### P1：第二阶段（已完成 ✅）

```
13. get_efficient_frontier          有效前沿 ✅
14. get_monte_carlo_simulation      蒙特卡洛模拟 ✅
15. get_factor_attribution          因子归因 ✅
16. get_financial_fraud_signals     财务造假信号 ✅
17. get_chart_patterns              经典技术形态 ✅
18. get_fibonacci_retracement       斐波那契回调 ✅
19. get_yield_curve_analysis        收益率曲线 ✅
20. get_macro_dashboard             宏观仪表盘 ✅
21. get_event_study                 事件研究法 ✅
22. get_multi_factor_screening      多因子选股 ✅
23. get_comparable_company_valuation 可比公司估值 ✅
```

### P2：第三阶段（已完成 ✅）

```
24. get_ddm_valuation              股利贴现模型 ✅
25. get_residual_income_valuation  剩余收益估值 ✅
26. get_black_scholes_price        期权定价 ✅
27. get_implied_volatility         隐含波动率 ✅
28. get_brinson_attribution        Brinson 归因 ✅
29. get_economic_cycle_position    经济周期定位 ✅
30. get_sector_rotation_signals    行业轮动信号 ✅
31. get_correlation_matrix         相关性矩阵 ✅
32. get_cointegration_test         协整检验 ✅
```

### 后续（已完成）

```
33. get_dcf_three_stage_valuation  DCF 三阶段估值 ✅
34. get_eva_valuation              EVA 经济增加值 ✅
35. get_fcff_fcfe_calculation      自由现金流计算 ✅
36. get_peg_valuation              PEG 估值 ✅
37. get_graham_valuation           格雷厄姆估值 ✅
38. get_capm_cost_of_equity        CAPM 股权成本 ✅
39. get_growth_adjusted_valuation  增长质量调整 ✅
40. get_ohlson_oscore              Ohlson O-Score ✅
41. get_receivables_quality        应收账款质量 ✅
42. get_inventory_quality          存货质量 ✅
43. get_liquidity_stress_test      流动性压力测试 ✅
44. get_debt_structure_analysis    债务结构分析 ✅
45. get_sortino_ratio              Sortino 比率 ✅
46. get_treynor_ratio              Treynor 比率 ✅
47. get_information_ratio          信息比率 ✅
48. get_calmar_ratio               Calmar 比率 ✅
49. get_jensen_alpha               Jensen Alpha ✅
50. get_portfolio_stress_test      组合压力测试 ✅
51. get_scenario_analysis          情景分析 ✅
52. get_sector_attribution         行业归因 ✅
53. get_adx_trend_strength         ADX 趋势强度 ✅
54. get_macd_divergence            MACD 背离 ✅
55. get_rsi_divergence             RSI 背离 ✅
56. get_volume_price_divergence    量价背离 ✅
57. get_vwap                       成交量加权均价 ✅
58. get_obv_analysis               能量潮 ✅
59. get_turnover_analysis          换手率分析 ✅
60. get_pivot_points               枢轴点 ✅
61. get_volume_profile             成交量分布 ✅
62. get_fibonacci_extension        斐波那契扩展 ✅
63. get_correlation_matrix         相关性矩阵 ✅
64. get_cointegration_test         协整检验 ✅
65. get_rolling_regression         滚动回归 ✅
66. get_normality_test             正态性检验 ✅
67. get_stationarity_test          平稳性检验 ✅
68. get_garch_volatility           GARCH 波动率 ✅
69. get_graham_screen              格雷厄姆筛选 ✅
70. get_growth_stock_screen        成长股筛选 ✅
71. get_dividend_stock_screen      红利股筛选 ✅
72. get_turnaround_screen          困境反转筛选 ✅
73. get_option_greeks              希腊字母计算 ✅
74. get_option_strategy_pnl        期权策略盈亏 ✅
75. get_economic_cycle_position    经济周期定位 ✅
76. get_monetary_environment       货币环境分析 ✅
77. get_sector_rotation_signals    行业轮动信号 ✅
78. get_bond_yield_calculation     债券收益率计算 ✅
79. get_credit_spread_analysis     信用利差分析 ✅
80. get_bond_duration_convexity    债券久期与凸性 ✅
81. get_dividend_valuation_context 股息率估值 ✅
82. get_industry_valuation_distribution 行业估值分布 ✅
83. get_cashflow_quality_deep      现金流质量深度 ✅
84. get_earnings_surprise_analysis 业绩预告分析 ✅
```

---

## 14. 工具文件组织

```
core/tools/implementations/
├── fundamentals/
│   ├── financial_tools.py          # 现有基本面工具
│   ├── standard_financial_tools.py # 标准财务 API 工具
│   ├── factor_bundle_tools.py      # 因子包工具
│   ├── stock_fundamentals.py       # 财报明细
│   └── valuation/                  # 估值模型（新建）
│       ├── __init__.py
│       ├── dcf_valuation.py        # DCF 估值
│       ├── wacc_calculator.py      # WACC 计算
│       ├── comparable_valuation.py # 可比公司估值
│       └── graham_valuation.py     # 格雷厄姆估值
├── risk/
│   ├── __init__.py
│   ├── altman_zscore.py            # Altman Z-Score
│   ├── beneish_mscore.py           # Beneish M-Score
│   ├── piotroski_fscore.py         # Piotroski F-Score
│   ├── earnings_quality.py         # 盈利质量评分
│   ├── fraud_detection.py          # 财务造假信号
│   ├── var_calculation.py          # VaR/CVaR
│   └── beta_calculation.py         # Beta
├── portfolio/
│   ├── __init__.py
│   ├── efficient_frontier.py       # 有效前沿
│   ├── monte_carlo.py              # 蒙特卡洛模拟
│   ├── factor_attribution.py       # 因子归因
│   ├── performance_ratios.py       # 夏普/索提诺/特雷诺
│   └── stress_test.py              # 压力测试
├── technical/
│   ├── __init__.py                  # 指标计算库（纯函数）
│   ├── indicators.py                # MA/EMA/MACD/RSI/BOLL/ATR/KDJ
│   ├── candlestick_patterns.py      # K 线形态识别 ✅
│   ├── crossover_signals.py         # 金叉/死叉交叉信号 ✅
    ├── chart_patterns.py            # 经典形态（头肩顶底等）
    ├── fibonacci_tools.py           # 斐波那契回调/扩展
    ├── support_resistance.py        # 支撑压力位
    └── volume_analysis.py           # 成交量分析
├── macro/
│   ├── __init__.py
│   ├── yield_curve.py              # 收益率曲线
│   ├── macro_dashboard.py          # 宏观仪表盘
│   └── bond_calculator.py          # 债券计算
├── event/
│   ├── __init__.py
│   └── event_study.py              # 事件研究法
├── derivatives/
│   ├── __init__.py
│   └── options.py                  # 期权定价/Greeks
├── statistics/
│   ├── __init__.py
│   ├── correlation.py              # 相关性矩阵
│   ├── cointegration.py            # 协整检验
│   └── regression.py               # 滚动回归
└── screening/
    ├── __init__.py
    └── factor_screens.py           # 多因子/格雷厄姆/成长/红利筛选
```

---

## 15. 工具元数据规范

每个手写工具必须包含以下元数据：

```python
{
    "tool_id": "get_dcf_valuation",
    "display_name": "DCF 两阶段估值",
    "description": "基于自由现金流的两阶段贴现估值模型",
    "category": "valuation",
    "capability_tags": ["dcf_valuation", "intrinsic_value", "absolute_valuation"],
    "tool_role_hint": "specialized",  # primary | specialized | supporting | generic | fallback
    "output_shape": "structured_json",  # structured_json | semi_structured | markdown_report
    "preferred_for": ["intrinsic_value_estimation", "long_term_valuation"],
    "not_replacement_for": [],
    "parameters": [...],
    "expected_output": {...},
    "data_sources": ["stock_financial_data", "stock_daily_quotes"],
    "formulas_documented": True,  # 公式是否在代码注释中完整记录
    "depends_on": ["get_wacc_calculation"],  # 依赖的其他工具
    "is_hand_written": True,  # 标记为手写工具
}
```

---

## 16. 与现有工具的关系

### 16.1 不替代现有工具

本目录中的新工具是对现有工具的**能力增强**，不替代已有工具：

- `get_income_analysis`、`get_balance_sheet_analysis`、`get_cashflow_analysis` 仍是有效的概要工具
- `get_stock_fundamentals_unified` 仍是有效的总览工具
- 新工具是通过**结构化、公式化、可审计**的方式提供更深层能力

### 16.2 与 Skill 生成器的关系

Skill 生成器按以下优先级使用工具：

1. **能力原语匹配**：先查能力标签，匹配到的手写工具优先使用
2. **结构化优先**：同能力下，结构化输出优先于 Markdown 报告
3. **手写优先**：同能力下，手写工具优先于 Agent 生成工具
4. **Skill 只做组合**：Skill 生成器不应生成计算逻辑，只组合已有工具

---

## 17. 更新日志

| 日期 | 版本 | 变更 |
|------|------|------|
| 2026-06-29 | v1.0 | 初始版本，完成全部 7 个领域工具目录 |
