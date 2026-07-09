# 常用分析因子目录

这份清单的目标不是做一份泛化的量化因子百科，而是把当前仓库里已经有稳定数据支撑、适合直接固化成工具或 Skill 的常用因子先收拢出来。

适用场景：

- 手工实现基本面 / 技术面 Skill
- 限制生成式 Skill 只在白名单因子内组合
- 工作流、Agent、筛选系统复用统一字段定义

对应代码入口：

- [core/skill_runtime/factor_catalog.py](core/skill_runtime/factor_catalog.py)
- [core/skill_runtime/factor_schema.py](core/skill_runtime/factor_schema.py)
- [core/skill_runtime/data_access.py](core/skill_runtime/data_access.py)
- [core/tools/implementations/technical/indicators.py](core/tools/implementations/technical/indicators.py)

当前还新增了一条代码约束：

- `factor_catalog.py` 中的 `implementation_level`
- `factor_schema.py` 中的 `data_quality_tier`

这两层现在已经有自动一致性校验，用于避免 catalog 和 schema 对同一字段给出相互冲突的稳定性判断。

同样，P0 的 `value_core`、`quality_core`、`growth_cashflow_core` 推荐 pack 现在也直接从 `factor_schema.py` 的 bundle 字段集合派生，不再在 `factor_catalog.py` 里手写维护第二份字段列表。

另外，P0 基本面字段在 `factor_catalog.py` 中的 `primary_sources` 与 `helper_functions` 也开始统一迁到 `stock_financial_periods` / `get_stock_financial_periods` 口径，并已有自动校验防止继续引用旧的 `stock_financial_data` / `get_stock_financial_data` 描述。

现在又补了一层更细的约束：

- `factor_catalog.py` 中部分关键 P0 字段的 `fallback_rules` 与 `warnings`
- `fundamental_factors.py` 中已经落地的真实回退语义与保守口径说明

这两层现在也已有自动语义校验，用来防止实现已经变更，但 catalog 里的文字说明还停留在旧口径。

当前这层约束已经从“部分关键字段”扩展到“全量 P0 字段覆盖”：

- 每个 P0 字段都必须在 runtime semantic contract 中有登记
- 一旦 schema 新增字段但 contract 未同步补上，验证脚本会直接失败

而且这层 contract 不再只是 `fallback_rules` / `warnings` 的自由文本片段，而是收敛成固定类别：

- `direct_fields`：这个字段在 catalog 中应该声明哪些直接输入字段或输入组合
- `fallback_chain`：真实实现里存在的回退链条
- `denominator_guards`：分母、平均值代理、余额代理这类分母约束
- `unit_conversions`：单位换算语义，例如亿元到元
- `conservative_proxies`：保守代理口径，例如用最新余额替代平均余额
- `availability_constraints`：什么条件下必须返回空值或不能计算

这意味着现在的校验已经不只是检查“有没有写说明”，而是在检查“说明被写在了正确的语义类别里”。

相关设计说明：

- [docs/analysis/CANONICAL_FINANCIAL_PERIOD_LAYER.md](docs/analysis/CANONICAL_FINANCIAL_PERIOD_LAYER.md)
- [docs/analysis/P0_FACTOR_OUTPUT_SCHEMA.md](docs/analysis/P0_FACTOR_OUTPUT_SCHEMA.md)
- [docs/analysis/P0_FACTOR_GOVERNANCE_PHASE_SUMMARY.md](docs/analysis/P0_FACTOR_GOVERNANCE_PHASE_SUMMARY.md)

## 0. 当前数据定义层状态

截至当前版本，仓库已经落地了一层“财务 period 规范化层”，但它还不是完全独立、可版本化的最终定义层。

当前已经完成的部分：

- 旧的 `stock_financial_data` 混合结构，已经可以展开为统一的 `stock_financial_periods`
- period 记录会把多源财务子表按报告期对齐，并平铺出统一字段，如 `revenue`、`net_profit`、`ebit`、`total_equity`、`money_cap`
- 原始报表仍保留在 `raw_data.income_statement`、`raw_data.balance_sheet`、`raw_data.cashflow_statement`、`raw_data.financial_indicators`
- runtime、筛选富化、筛选视图目前都已经迁移到 period 层消费

当前还没有完全完成的部分：

- 还没有把 canonical schema 独立抽成正式 schema 文件或版本化契约
- 字段单位、缺失策略、source 优先级，已经在 P0 范围内进入声明式定义，但还没有扩展成覆盖全仓库的正式版本化契约
- 一些 `cautious` 因子还缺少统一的 `unavailable_reason` 或数据质量标签

所以，当前最准确的表述是：

- 已经有“可运行的数据定义层雏形”
- 但还不是“独立成体系的正式定义层”

## 1. 推荐分层

建议以后做 Skill 时，把因子按 4 层来管：

1. `ready`
直接字段，已有本地数据可拿，适合直接实现。

2. `derived`
基于现有字段的派生值，逻辑清楚，适合写成稳定代码，不适合让模型临场发明。

3. `time_series`
依赖历史序列计算，适合统一走日线 + 指标计算模块。

4. `cautious`
字段覆盖率或口径不稳定，能做，但不应默认作为阻断性依赖。

## 2. 第一批优先固化的因子包

### 2.1 价值因子

- `pe_ttm`
- `pb`
- `ps_ttm`
- `dividend_yield`
- `industry_pe_median`
- `industry_pb_median`

### 2.2 质量因子

- `roe`
- `roa`
- `gross_margin`
- `netprofit_margin`
- `debt_to_assets`
- `current_ratio`
- `quick_ratio`
- `cash_ratio`

### 2.3 成长 / 现金流因子

- `revenue_ttm`
- `net_profit_ttm`
- `n_cashflow_act`
- `net_working_capital`

### 2.4 技术因子

- `ma20`
- `ma60`
- `rsi14`
- `kdj_k`
- `kdj_d`
- `kdj_j`
- `dif`
- `dea`
- `macd_hist`

### 2.5 交易活跃度因子

- `pct_chg`
- `turnover_rate`
- `volume_ratio`

## 3. 常用因子公式速查表

这部分优先列“实现时最常用、最容易出现口径歧义”的公式。

### 3.1 估值因子公式

| 因子 | 常用公式 | 说明 |
| ------ | ---------- | ------ |
| `pe` | `总市值 / 归母净利润` 或 `股价 / 每股收益(EPS)` | 静态 PE，注意利润口径要统一 |
| `pe_ttm` | `总市值 / 归母净利润TTM` | 更常用，优先于静态 PE |
| `pb` | `总市值 / 归母净资产` 或 `股价 / 每股净资产(BPS)` | 金融、重资产行业常用 |
| `pb_mrq` | `总市值 / 最新归母净资产` | 最新期口径 PB |
| `ps_ttm` | `总市值 / 营业收入TTM` | 适合利润不稳定公司 |
| `dividend_yield` | `过去12个月现金分红 / 当前市值` | 或 `每股股息 / 当前股价` |
| `peg` | `pe_ttm / 净利润增长率` | 增长率通常用 `%` 数值，如 20 表示 20% |
| `ev` | `总市值 + 有息负债 - 货币资金` | 企业价值 |
| `ev_ebitda` | `EV / EBITDA` | 跨资本结构比较常用 |
| `ev_ebit` | `EV / EBIT` | 比 EV/EBITDA 更保守 |
| `ev_fcf` | `EV / 自由现金流` | 现金流估值 |
| `fcf_yield` | `自由现金流 / 总市值` | 越高通常越便宜 |
| `ocf_yield` | `经营现金流净额TTM / 总市值` | 经营现金流收益率 |
| `shareholder_yield` | `股息率 + 回购率 - 股权摊薄率` | 适合资本配置分析 |
| `price_to_cfo` | `总市值 / 经营现金流净额TTM` | 与 PE 形成互补 |

### 3.2 质量与财务健康因子公式

| 因子 | 常用公式 | 说明 |
| ------ | ---------- | ------ |
| `roe` | `归母净利润 / 平均归母净资产` | 常用百分比表示 |
| `roa` | `净利润 / 平均总资产` | 衡量资产效率 |
| `roic` | `NOPAT / 投入资本` | `NOPAT = EBIT × (1 - 税率)` |
| `croic` | `经营现金流 / 投入资本` | 现金回报率 |
| `gross_margin` | `(营业收入 - 营业成本) / 营业收入` | 毛利率 |
| `netprofit_margin` | `净利润 / 营业收入` | 净利率 |
| `gross_profit_to_assets` | `毛利润 / 平均总资产` | 商业模式质量因子 |
| `asset_turnover` | `营业收入 / 平均总资产` | 资产周转率 |
| `inventory_turnover` | `营业成本 / 平均存货` | 存货周转率；当前仓库先用最新存货余额做保守代理 |
| `receivable_turnover` | `营业收入 / 平均应收账款` | 回款效率；当前仓库先用最新应收账款余额做保守代理 |
| `cash_conversion` | `经营现金流净额 / 净利润` | 利润含金量 |
| `accrual_ratio` | `(净利润 - 经营现金流净额) / 平均总资产` | 越高通常越差 |
| `debt_to_assets` | `总负债 / 总资产` | 资产负债率 |
| `assets_to_eqt` | `总资产 / 股东权益` | 权益乘数 |
| `current_ratio` | `流动资产 / 流动负债` | 流动比率 |
| `quick_ratio` | `(流动资产 - 存货) / 流动负债` | 速动比率 |
| `cash_ratio` | `(货币资金 + 现金等价物) / 流动负债` | 现金比率 |
| `interest_coverage` | `EBIT / 利息费用` | 利息保障倍数；当前仓库优先用 `ebit / fin_exp`，当净财务费用为负时回退 raw income 中的 `int_exp` / `fin_exp_int_exp` |
| `piotroski_f_score` | `9 个财务信号加总` | 经典价值因子组合评分；当前仓库按近两期 9 项信号保守实现 |
| `altman_z_score` | `1.2A + 1.4B + 3.3C + 0.6D + 1.0E` | 财务困境评分；当前仓库使用 raw_data 中 `undistr_porfit` 与 `ebit` 口径 |
| `beneish_m_score` | `-4.84 + 0.92DSRI + 0.528GMI + ...` | 盈余操纵风险识别；当前仓库按近两期 8 指标模型保守实现 |

### 3.3 成长与现金流因子公式

| 因子 | 常用公式 | 说明 |
| ------ | ---------- | ------ |
| `revenue_yoy` | `(本期营收 - 上年同期营收) / 上年同期营收` | 营收同比 |
| `net_profit_yoy` | `(本期净利润 - 上年同期净利润) / 上年同期净利润` | 净利润同比 |
| `operating_profit_yoy` | `(本期营业利润 - 上年同期营业利润) / 上年同期营业利润` | 营业利润同比 |
| `fcf_growth` | `(本期自由现金流 - 上期自由现金流) / 上期自由现金流` | 自由现金流增长 |
| `revenue_cagr_3y` | `(营收_t / 营收_t-3)^(1/3) - 1` | 三年复合增速 |
| `profit_cagr_3y` | `(净利润_t / 净利润_t-3)^(1/3) - 1` | 三年利润复合增速 |
| `margin_trend` | `本期利润率 - 基准期利润率` | 可按 1Y/3Y 看趋势 |
| `roe_stability` | `1 / std(ROE)` 或 `std(ROE)` | 实现时需统一方向 |
| `revenue_ttm` | `最近4个季度营收之和` | 滚动营收 |
| `net_profit_ttm` | `最近4个季度净利润之和` | 滚动净利润 |
| `n_cashflow_act` | `经营活动现金流量净额` | 原始财务字段 |
| `fcf` | `经营现金流净额 - 资本开支` | 自由现金流 |
| `fcf_margin` | `自由现金流 / 营业收入` | 现金流率 |
| `capex_ratio` | `资本开支 / 营业收入` | 重资产投入强度 |
| `cash_dividend_payout` | `现金分红 / 归母净利润` | 分红支付率 |
| `buyback_ratio` | `回购金额 / 总市值` | 回购强度 |
| `net_cash_position` | `(货币资金 - 有息负债) / 总资产` 或绝对额 | 当前仓库先用 `(money_cap - total_ncl) / total_assets` 做保守代理 |
| `net_working_capital` | `流动资产 - 流动负债` | 净营运资本 |
| `working_capital_change` | `本期净营运资本 - 上期净营运资本` | 营运资本变化 |

### 3.4 风险、波动与稳健性因子公式

| 因子 | 常用公式 | 说明 |
| ------ | ---------- | ------ |
| `beta_60d` | `cov(r_i, r_m) / var(r_m)` | 相对市场敏感度 |
| `volatility_20d` | `std(日收益率, 20日)` | 可年化为 `std × sqrt(252)` |
| `volatility_60d` | `std(日收益率, 60日)` | 中期波动率 |
| `max_drawdown_120d` | `min(当前净值/历史峰值 - 1)` | 最大回撤 |
| `atr_pct` | `ATR(n) / 收盘价` | 标准化波动强度 |
| `downside_volatility` | `std(负收益率)` | 下行波动率 |
| `distance_to_52w_high` | `当前价 / 52周最高价 - 1` | 越接近 0 表示越接近新高 |
| `distance_to_52w_low` | `当前价 / 52周最低价 - 1` | 困境股常用 |
| `regulatory_risk_score` | `规则评分模型` | 通常不是单一公式，而是事件打分 |
| `litigation_risk_score` | `规则评分模型` | 同上 |

### 3.5 趋势、动量与技术因子公式

| 因子 | 常用公式 | 说明 |
| ------ | ---------- | ------ |
| `momentum_20d` | `close_t / close_t-20 - 1` | 20 日动量 |
| `momentum_60d` | `close_t / close_t-60 - 1` | 60 日动量 |
| `momentum_120d` | `close_t / close_t-120 - 1` | 120 日动量 |
| `relative_strength_vs_index` | `个股收益率 - 基准指数收益率` | 或比值形式 |
| `ma20` | `最近20日收盘价均值` | 20 日均线 |
| `ma60` | `最近60日收盘价均值` | 60 日均线 |
| `price_above_ma20` | `当前价 / MA20 - 1` | 偏离率 |
| `price_above_ma60` | `当前价 / MA60 - 1` | 偏离率 |
| `rsi14` | `100 - 100 / (1 + RS)` | `RS = 平均上涨幅 / 平均下跌幅` |
| `dif` | `EMA12 - EMA26` | MACD-DIF |
| `dea` | `EMA(DIF, 9)` | MACD-DEA |
| `macd_hist` | `DIF - DEA` 或 `2 × (DIF - DEA)` | 实现时需统一口径 |
| `kdj_k` | `SMA(RSV, m1, 1)` | KDJ-K |
| `kdj_d` | `SMA(K, m2, 1)` | KDJ-D |
| `kdj_j` | `3K - 2D` | KDJ-J |
| `boll_width` | `(上轨 - 下轨) / 中轨` | 布林带宽度 |
| `adx` | `EMA(DX, n)` | 趋势强度 |
| `obv` | `累计成交量方向和` | 量价因子 |
| `vwap_deviation` | `当前价 / VWAP - 1` | 偏离成交均价 |

### 3.6 交易活跃度、资金流与筹码因子公式

| 因子 | 常用公式 | 说明 |
| ------ | ---------- | ------ |
| `pct_chg` | `(今收 - 昨收) / 昨收` | 涨跌幅 |
| `turnover_rate` | `成交量 / 自由流通股本` | 换手率 |
| `volume_ratio` | `当前时段成交量 / 过去若干日同时间平均成交量` | 量比 |
| `northbound_net_buy` | `北向买入额 - 北向卖出额` | 北向净买入 |
| `northbound_holding_change` | `(本期持股 - 上期持股) / 上期持股` | 持股变化率 |
| `main_fund_flow` | `主力流入额 - 主力流出额` | 需统一口径 |
| `margin_financing_ratio` | `融资余额 / 流通市值` | 融资强度 |
| `short_interest_ratio` | `融券余额 / 流通市值` 或 `卖空股数/日均成交量` | 市场不同口径不同 |
| `chip_concentration` | `高密度筹码区持仓占比` | 依赖筹码分布数据 |
| `shareholder_count_change` | `(本期股东户数 - 上期股东户数) / 上期股东户数` | A 股常用 |
| `unlock_pressure` | `未来解禁市值 / 当前流通市值` | 解禁压力 |

### 3.7 事件、预期差、行业景气与宏观映射

| 因子 | 常用公式 | 说明 |
| ------ | ---------- | ------ |
| `earnings_surprise` | `(实际业绩 - 一致预期) / 一致预期` | 业绩超预期幅度 |
| `guidance_change` | `本次指引 - 上次指引` | 管理层指引变化 |
| `dividend_change` | `本次分红率 - 上次分红率` | 分红变化 |
| `buyback_announcement_strength` | `回购上限金额 / 总市值` | 公告强度 |
| `major_contract_ratio` | `重大订单金额 / 最近12个月营收` | 订单弹性 |
| `industry_revenue_growth` | `(行业收入_t - 行业收入_t-1) / 行业收入_t-1` | 行业景气 |
| `industry_margin_trend` | `行业利润率_t - 行业利润率_t-k` | 行业利润率趋势 |
| `commodity_spread` | `产品价格 - 原材料价格` | 典型周期因子 |
| `capacity_utilization_proxy` | `产量 / 名义产能` 或代理指标 | 常需行业数据 |
| `inventory_cycle_signal` | `库存同比 - 销量同比` 或相关组合 | 库存周期 |
| `pmi_exposure_score` | `业务结构加权映射` | 通常为模型评分 |
| `export_dependency` | `出口收入 / 总收入` | 外需敏感度 |
| `real_rate_sensitivity` | `回归系数` | 对实际利率敏感度 |
| `yield_curve_sensitivity` | `回归系数` | 对期限利差敏感度 |
| `credit_spread_sensitivity` | `回归系数` | 对信用利差敏感度 |
| `fx_sensitivity` | `回归系数` 或 `外币收入占比` | 汇率敏感度 |
| `commodity_beta` | `股票收益率对商品收益率回归系数` | 商品价格 beta |

## 4. 第二批建议补充的高价值因子

这一层不再受“当前仓库已有数据”限制，只考虑常用、有用、值得长期补齐的数据方向。

建议把这些因子理解为“中期数据建设目标”，后续可以逐批补齐数据源和实现，而不是一次性全上。

### 3.1 进阶估值因子

- `peg`
市盈率结合利润增长率，适合成长股估值。

- `ev_ebitda`
企业价值/EBITDA，适合资本结构差异较大的公司横向比较。

- `ev_ebit`
比 EV/EBITDA 更保守，适合利润质量要求更高的场景。

- `ev_fcf`
企业价值/自由现金流，适合现金流导向估值。

- `fcf_yield`
自由现金流收益率，适合作为价值因子的核心补充。

- `ocf_yield`
经营现金流收益率，适合做盈利质量与估值交叉验证。

- `shareholder_yield`
股东总收益率，综合股息、回购、减持摊薄影响。

- `price_to_cfo`
股价/经营现金流，适合利润波动较大的公司。

- `enterprise_value`
企业价值本身不是筛选因子，但几乎所有 EV 类估值都依赖它，值得标准化。

### 3.2 盈利质量与财务质量因子

- `roic`
投入资本回报率，比 ROE 更适合跨资本结构比较。

- `croic`
现金回报率，适合判断“利润是否真能转成现金”。

- `gross_profit_to_assets`
毛利/总资产，适合看商业模式质量。

- `asset_turnover`
总资产周转率，反映经营效率。

- `inventory_turnover`
存货周转率，适合制造、消费行业。

- `receivable_turnover`
应收账款周转率，适合判断回款质量。

- `cash_conversion`
净利润到经营现金流的转换能力。

- `accrual_ratio`
应计利润比例，常用于识别利润含金量偏低。

- `interest_coverage`
利息保障倍数，适合高负债行业风险识别。

- `piotroski_f_score`
经典财务健康评分，适合作为价值策略增强项。

### 3.3 成长与经营趋势因子

- `revenue_yoy`
营收同比增长率。

- `net_profit_yoy`
净利润同比增长率。

- `operating_profit_yoy`
营业利润同比增长率。

- `fcf_growth`
自由现金流增长率，比利润增长更稳健。

- `revenue_cagr_3y`
三年营收复合增长率。

- `profit_cagr_3y`
三年净利润复合增长率。

- `margin_trend`
毛利率/净利率趋势因子，适合看经营改善而不是单点快照。

- `roe_stability`
ROE 稳定性，适合区分“偶然高 ROE”和“长期高 ROE”。

- `earnings_revision`
盈利预测上修/下修，常用于中短期 alpha。

- `analyst_expectation_gap`
业绩预期差，财报前后很有用。

### 3.4 现金流与资本配置因子

- `fcf_margin`
自由现金流率，适合判断业务自我造血能力。

- `capex_ratio`
资本开支占收入比，适合区分轻资产/重资产周期。

- `cash_dividend_payout`
现金分红支付率。

- `buyback_ratio`
回购比例，适合资本配置分析。

- `net_cash_position`
净现金/净债务状态，适合作为风险和估值修正因子。

- `working_capital_change`
营运资本变动，适合识别“利润靠占款堆出来”的问题。

### 3.5 风险与稳健性因子

- `beta_60d`
60 日 beta，适合组合风险暴露管理。

- `volatility_20d`
20 日波动率。

- `volatility_60d`
60 日波动率。

- `max_drawdown_120d`
120 日最大回撤。

- `atr_pct`
ATR 占价格比，适合统一不同价格股票的波动强度。

- `downside_volatility`
下行波动率，比普通波动率更贴近风险感知。

- `distance_to_52w_high`
距离 52 周高点，兼具趋势和拥挤度意义。

- `distance_to_52w_low`
距离 52 周低点，适合均值回归和困境股筛选。

- `altman_z_score`
财务困境风险指标。

- `beneish_m_score`
盈余操纵风险筛查。

### 3.6 趋势、动量与技术扩展因子

- `momentum_20d`
20 日动量。

- `momentum_60d`
60 日动量。

- `momentum_120d`
120 日动量。

- `relative_strength_vs_index`
相对指数强弱，适合做板块轮动和个股强势识别。

- `price_above_ma20`
价格相对 MA20 偏离度。

- `price_above_ma60`
价格相对 MA60 偏离度。

- `boll_width`
布林带宽度，适合识别压缩与扩张。

- `adx`
趋势强度指标。

- `obv`
能量潮，量价联动指标。

- `vwap_deviation`
价格偏离成交量加权均价的程度。

### 3.7 资金流与筹码因子

- `northbound_net_buy`
北向资金净流入。

- `northbound_holding_change`
北向持股变化率。

- `main_fund_flow`
主力资金净流入。

- `margin_financing_ratio`
融资余额占流通市值比。

- `short_interest_ratio`
融券/卖空压力指标。

- `chip_concentration`
筹码集中度。

- `shareholder_count_change`
股东户数变化，A 股里非常常用。

- `unlock_pressure`
限售解禁压力。

### 3.8 事件驱动与预期差因子

- `earnings_surprise`
业绩超预期/低预期幅度。

- `guidance_change`
管理层业绩指引变化。

- `dividend_change`
分红方案变化。

- `buyback_announcement_strength`
回购公告强度。

- `major_contract_ratio`
重大订单金额占收入比。

- `regulatory_risk_score`
监管风险评分。

- `litigation_risk_score`
诉讼/处罚风险评分。

### 3.9 行业与景气度因子

- `industry_revenue_growth`
行业收入增速。

- `industry_margin_trend`
行业利润率趋势。

- `commodity_spread`
关键原材料价差，对化工、有色、航运等很重要。

- `capacity_utilization_proxy`
产能利用率代理因子。

- `inventory_cycle_signal`
库存周期信号。

- `pmi_exposure_score`
对 PMI 景气变化的敏感度。

- `export_dependency`
出口依赖度，适合外需链公司。

### 3.10 宏观与利率敏感因子

- `real_rate_sensitivity`
实际利率敏感度，适合高估值成长股。

- `yield_curve_sensitivity`
收益率曲线敏感度，适合金融和地产。

- `credit_spread_sensitivity`
信用利差敏感度。

- `fx_sensitivity`
汇率敏感度，适合出口链公司。

- `commodity_beta`
商品价格 beta，适合资源股和中游制造。

## 5. 建议优先补数的方向

如果后面要补数据，我建议优先级按“通用性 + 决策价值 + 实现成本”来排：

### 4.1 P0：最值得先补

- `peg`
- `roic`
- `fcf_yield`
- `revenue_yoy`
- `net_profit_yoy`
- `momentum_60d`
- `relative_strength_vs_index`
- `northbound_net_buy`
- `shareholder_count_change`
- `earnings_surprise`

### 4.2 P1：第二批增强

- `ev_ebitda`
- `ev_fcf`
- `cash_conversion`
- `accrual_ratio`
- `volatility_60d`
- `max_drawdown_120d`
- `main_fund_flow`
- `unlock_pressure`
- `industry_revenue_growth`
- `commodity_spread`

### 4.3 P2：高价值但更依赖外部口径

- `shareholder_yield`
- `croic`
- `piotroski_f_score`
- `altman_z_score`
- `beneish_m_score`
- `guidance_change`
- `credit_spread_sensitivity`
- `fx_sensitivity`

## 6. 对应的数据建设建议

如果不受当前数据限制，后续建议把数据建设分成 6 条线：

1. `一致预期线`
分析师预测、盈利预测修正、业绩预期差。

2. `资金行为线`
北向资金、主力资金、融资融券、回购、减持。

3. `财务质量线`
自由现金流、资本开支、应计利润、ROIC、CROIC。

4. `事件线`
财报、分红、回购、订单、诉讼、监管处罚。

5. `行业景气线`
商品价格、库存、产能、行业销量、行业开工率。

6. `宏观映射线`
利率、汇率、信用利差、PMI、地产销售、社融等。

## 7. 数据和实现建议

### 3.1 直接字段型

优先从以下 helper 读取：

- `get_stock_basic_info`
- `get_stock_valuation_context`
- `get_market_quotes`
- `get_stock_financial_periods`

说明：

- `get_stock_financial_periods` 是当前基本面因子默认应依赖的 canonical period 入口
- `get_stock_financial_data` 目前更适合作为历史兼容或原始快照回查入口，不应再作为新的跨期因子默认读取层

适合实现为：

- 单因子读取工具
- 基本面因子批量聚合工具
- 选股筛选字段映射

### 3.2 派生型

优先通过现有 helper 组合，不要让模型自由发挥公式：

- `industry_pe_median` -> `summarize_industry_valuation(..., metric='pe')`
- `industry_pb_median` -> `summarize_industry_valuation(..., metric='pb')`
- `net_working_capital` -> `total_cur_assets - total_cur_liab`

### 3.3 时序型

统一实现路径：

1. `get_stock_daily_quotes` 读取历史 K 线
2. 转成 DataFrame
3. 调用 [core/tools/implementations/technical/indicators.py](core/tools/implementations/technical/indicators.py) 里的统一指标实现

这样可以避免每个 Skill 自己再写一套 RSI / MACD / KDJ。

## 8. 不建议继续靠生成式 Skill 试错的部分

以下内容最适合改成“固定模板 + 固定 helper + 固定输出结构”：

- PE / PB / PS / 股息率 / 行业对比
- ROE / 毛利率 / 资产负债率 / 流动比率
- MA / RSI / KDJ / MACD
- 简单派生指标，如净营运资本

原因很直接：

- 字段已经存在
- helper 已经存在
- 公式固定
- 输出结构稳定
- 失败通常不是因为“不会写代码”，而是模型误判字段口径或乱选数据源

## 8.1 当前基本面 canonical 层的最小共识

如果后续还要继续补因子，实现时建议默认依赖下面这套共识，而不要再直接围绕来源表写逻辑：

1. 财务主读取层默认使用 `stock_financial_periods`
2. period 记录的平铺字段优先作为统一读取口径
3. 需要来源细节时，再回退到 `raw_data.*` 子结构
4. `stock_financial_data` 不再视为新的业务语义层，而更接近历史快照和原始归档层
5. 对缺字段但仍可保守估算的因子，允许定义回退链；对无法可靠估算的因子，应明确标记为 `cautious`

当前已经开始补的结构化约束：

1. `factor_schema.py` 可以标记字段的 `data_quality_tier`
2. `get_fundamental_factor_snapshot` 会为部分 `cautious` 字段输出 `factor_diagnostics`
3. 当 `beneish_m_score` 缺值时，不再只返回 `null`，还会附带 `data_quality_state`、`unavailable_reason` 和 `missing_inputs`

## 9. 建议的后续落地方式

建议后续不要再按“一个自然语言需求 -> 一个新 Skill”去长，而是按下面顺序做：

1. 先把高频因子做成标准库函数
2. 再把标准库函数组合成专题工具
3. 生成式 Skill 只负责拼装，不负责发明基础因子实现

比较合理的专题工具示例：

1. `get_value_factor_bundle`
输出 PE / PB / PS / 股息率 / 行业估值对比。

2. `get_quality_factor_bundle`
输出 ROE / ROA / 毛利率 / 净利率 / 资产负债率 / 流动比率。

3. `get_technical_factor_bundle`
输出 MA / RSI / KDJ / MACD。

4. `get_factor_snapshot`
按股票返回一份标准结构化因子快照，供 Agent、筛选、报告复用。

## 10. 可参考的开源项目

下面这些项目不是都能直接拿来即用，但都适合参考它们的字段口径、因子实现方式或数据管线设计。

### 10.1 Python 因子与量化库

1. `pandas-ta`
技术指标非常全，适合参考 RSI、MACD、ADX、ATR、OBV、VWAP 这类时序因子的实现。

2. `TA-Lib`
老牌技术指标库，很多平台和量化框架都在复用它的口径。

3. `vectorbt`
偏研究和回测，适合参考指标批量化、向量化实现方式。

4. `backtrader`
偏回测框架，但内置指标体系可以参考。

5. `qlib`
微软开源的量化研究平台，因子表达、特征工程、数据管线都值得参考。

6. `alphalens`
不提供因子计算本身，但非常适合做因子有效性检验和核查。

7. `zipline` / `pyfolio`
虽然偏老，但因子研究和回测体系仍有参考价值。

### 10.2 多因子 / alpha 因子方向

1. `alphagen`
偏自动挖掘 alpha 表达式，适合参考“因子表达式系统”而不是直接照搬。

2. `WorldQuant 101 Formulaic Alphas` 各类开源复现仓库
适合参考横截面、时序 rank、delay、ts_std、ts_rank 这类因子操作子。

3. `qlib contrib alpha` 相关社区实现
适合参考数据字段标准化和因子组合方式。

### 10.3 基本面和财务因子方向

1. `Quantopian Pipeline` 生态的开源资料
虽然原平台没了，但很多基本面因子定义值得参考。

2. 各类 `fundamental factor investing` 开源 notebook / repo
适合参考 ROE、ROIC、FCF Yield、Accrual Ratio、Piotroski F-Score、Altman Z-Score 的实现口径。

### 10.4 对你们最有参考价值的不是“整库拿来”，而是三类能力

1. 指标计算内核：优先参考 `pandas-ta`、`TA-Lib`
2. 因子研究框架：优先参考 `qlib`、`alphalens`
3. 表达式和因子 DSL：优先参考 `WorldQuant alpha` 复现项目、`qlib`

## 11. 下一步建议

如果要把这份目录继续做实，我建议后续按下面顺序推进：

1. 先做 `P0` 因子的统一字段定义和输出 schema。
2. 再补 `价值 / 质量 / 技术 / 资金流` 四个专题 bundle。
3. 最后再让生成式 Skill 只做 bundle 级拼装，而不是底层因子实现。
