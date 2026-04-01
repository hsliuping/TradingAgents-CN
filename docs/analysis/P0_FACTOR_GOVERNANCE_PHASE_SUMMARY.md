# P0 因子治理阶段总览

这份文档用于集中说明这一轮 P0 基本面因子治理已经完成了什么、各层之间现在是什么关系、哪些问题已经解决、哪些问题还保留在下一阶段。

它不是替代细节文档，而是把下面几份文档串成一条连续的演进路径：

- [docs/analysis/CANONICAL_FINANCIAL_PERIOD_LAYER.md](docs/analysis/CANONICAL_FINANCIAL_PERIOD_LAYER.md)
- [docs/analysis/P0_FACTOR_OUTPUT_SCHEMA.md](docs/analysis/P0_FACTOR_OUTPUT_SCHEMA.md)
- [docs/analysis/COMMON_FACTOR_CATALOG.md](docs/analysis/COMMON_FACTOR_CATALOG.md)

## 1. 这一轮治理要解决什么问题

最初的问题不是“缺几个指标”，而是“即使指标能算出来，也没有稳定的数据定义和治理约束”。当时主要有五类风险：

- 财务历史期数据虽然存在，但被旧结构埋在 `raw_data` 子表里，下游很难稳定消费
- runtime、screening、view、文档各自维护字段和口径，容易漂移
- 因子实现虽然能运行，但 fallback、单位换算、保守代理都主要藏在代码里
- `cautious` 字段返回 `null` 时，调用方不知道是实现缺口还是数据缺口
- catalog、schema、runtime 缺少统一校验链，后续迭代容易再次分叉

这一轮工作，本质上是在把“能算”提升成“可治理、可验证、可复用”。

## 2. 当前已经形成的分层

### 2.1 Canonical period layer

对应文档：

- [docs/analysis/CANONICAL_FINANCIAL_PERIOD_LAYER.md](docs/analysis/CANONICAL_FINANCIAL_PERIOD_LAYER.md)

这一层解决的是“原始财务数据如何变成统一 period record”的问题。

当前结论：

- `stock_financial_periods` 已经成为实际运行中的 canonical storage/access layer
- runtime bundle、snapshot、screening enrichment、screening view 都已经迁到这层消费
- 常用字段优先读 period 顶层平铺字段，必要时再回退到 `raw_data.*`

它已经解决了数据消费入口不统一的问题，但还没有变成正式版本化 schema。

### 2.2 P0 field schema layer

对应文档：

- [docs/analysis/P0_FACTOR_OUTPUT_SCHEMA.md](docs/analysis/P0_FACTOR_OUTPUT_SCHEMA.md)

这一层解决的是“P0 字段本身应该如何被定义”的问题。

当前 `factor_schema.py` 已经统一管理：

- bundle 归属
- display_name
- unit
- screening_unit
- data_quality_tier
- calculation_mode
- semantic_tags
- source_priority
- tax_estimation_strategy
- period_selection_strategy
- minimum_input_groups
- minimum_computable_conditions
- included_in_screening
- included_in_snapshot

这意味着 P0 字段不再只是“代码里顺手算出来的键名”，而是有一份集中、可复用的字段定义。

### 2.3 Factor catalog layer

对应文档：

- [docs/analysis/COMMON_FACTOR_CATALOG.md](docs/analysis/COMMON_FACTOR_CATALOG.md)

这一层解决的是“字段实现说明、依赖来源、回退规则、警告语义如何集中登记”的问题。

当前 `factor_catalog.py` 已经统一管理：

- `COMMON_FACTOR_CATALOG`
- `RECOMMENDED_FACTOR_PACKS`
- `RuntimeSemanticContract`
- schema/catalog/source/pack/runtime semantic alignment 校验函数

也就是说，catalog 现在不只是给人看的目录，而是治理链条中的一环。

## 3. 三层现在是如何联动的

当前已经形成下面这条明确链路：

1. canonical period layer 负责把多源财务数据整理成统一 period record
2. runtime 使用这层 period record 计算 P0 bundle、snapshot、diagnostics
3. factor_schema 定义字段级 contract
4. factor_catalog 定义实现说明和 runtime semantic contract
5. 验证脚本检查 schema、catalog、runtime contract、screening、snapshot 是否一致

这条链路的关键变化在于：

- 以前是一份代码逻辑加几份松散文档
- 现在是“实现层 + schema 层 + catalog 层 + 自动校验层”同时存在

## 4. 当前已经落地的治理能力

### 4.1 字段集合不再漂移

P0 的 `value_core`、`quality_core`、`growth_cashflow_core` 已经集中到 `factor_schema.py` 管理，screening、snapshot、验证脚本都不再各写一份字段表。

### 4.2 cautious 字段有了结构化诊断

当前已经覆盖：

- `piotroski_f_score`
- `altman_z_score`
- `beneish_m_score`

snapshot 和 screening 现在不只是返回 `null`，还会返回 `factor_diagnostics`，帮助区分“实现问题”和“真实数据缺口”。

### 4.3 semantic contract 已结构化

当前 `RuntimeSemanticContract` 已经不再只是自由文本说明，而是拆成固定类别：

- `direct_fields`
- `source_priority`
- `fallback_chain`
- `denominator_guards`
- `unit_conversions`
- `conservative_proxies`
- `availability_constraints`

这意味着校验已经可以检查“语义有没有写在正确类别里”，而不是只靠人工阅读描述。

### 4.4 source_priority 已进入声明式治理

当前 source 优先级已经不再只是 runtime 代码里的隐式 `_pick_first(...)` 顺序。

P0 范围内，`factor_schema.py` 和 `RuntimeSemanticContract` 现在都已经有 `source_priority`，并且由验证脚本强制检查：

- 是否缺登记
- schema 与 contract 是否一致

### 4.5 回归链路已经具备治理能力

当前 [scripts/validate_moutai_fundamental_factors.py](scripts/validate_moutai_fundamental_factors.py) 不再只是一个“看茅台能不能跑通”的演示脚本，而是已经具备以下治理职责：

- bundle 字段完整性检查
- metadata/schema 对齐检查
- snapshot diagnostics 检查
- screening diagnostics 检查
- catalog/schema 对齐检查
- catalog/runtime semantic alignment 检查
- schema/runtime semantic alignment 检查
- source_priority 覆盖检查
- source/helper legacy reference 检查
- factor pack 对齐检查

### 4.6 公式级策略已经开始进入结构化定义

当前已经完成第一批公式级策略结构化，并且最小输入组已经补齐到全量 P0 字段：

- `roic` 已显式登记 `tax_estimation_strategy`
- `revenue_yoy`、`net_profit_yoy`、`oper_profit_yoy` 已显式登记 `period_selection_strategy = same_period_last_year`
- `revenue_cagr_3y`、`profit_cagr_3y` 已显式登记 `period_selection_strategy = same_period_n_years_3`
- `working_capital_change` 已显式登记 `period_selection_strategy = previous_available_period`
- `revenue_ttm`、`n_cashflow_act` 这类直接字段已显式登记单字段 `minimum_input_groups`
- `net_working_capital`、`fcf`、`fcf_margin`、`ocf_yield` 等字段已显式登记最小输入组
- `revenue_yoy`、`profit_cagr_3y`、`beneish_m_score` 等字段已显式登记 `minimum_computable_conditions`
- `pe`、`pe_ttm`、`pb`、`dividend_yield`、`roe`、`roa`、`net_profit_ttm` 等剩余直接/回退字段也已补齐 `minimum_input_groups`
- 同比/CAGR 字段与谨慎评分字段的 `minimum_computable_conditions` 已开始统一成稳定短语，例如 `comparison_period available`、`total_assets != 0`
- `pe_ttm`、`pb`、`pb_mrq`、`dividend_yield`、`net_profit_ttm`、`fcf`、`interest_coverage`、`industry_pe_median` 等字段已开始显式登记 `warning_conditions`，用于表达“可算但需提示”的 soft warning
- 这些 soft warning 现在也开始同步登记 `warning_categories`，用于把 warning 结构化到 `fallback_used`、`proxy_used`、`low_sample_size`、`precision_degraded` 等稳定类别

这意味着“公式怎么选税率、怎么选对比期”不再只存在于实现函数里，而已经开始进入 schema 与 runtime contract 的共同治理范围。

进一步说，这一层现在已经能声明三类公式级门槛：

- 如何估税
- 如何选期
- 满足哪组最小输入、并满足哪些额外条件后才允许计算

并且这套门槛现在已经分成两层：

- 缺 `minimum_input_groups` 会失败
- 对 `cautious`、同比/CAGR/最近两期对比，以及带显式分母约束的字段，缺 `minimum_computable_conditions` 也会失败
- 对 fallback、conservative proxy 和 peer stat 这类“提醒但不阻断”的字段，缺 `warning_conditions` 或 `warning_categories` 都会失败

这意味着当前已经不只是“能不能算”的治理，还开始覆盖“虽然能算，但是否应该提醒调用方谨慎解释”的治理。

并且这层提示现在已经不只是 schema 声明：snapshot 与 screening 已开始输出 `factor_warnings`，可以把已命中的 soft warning 直接带给调用方；每条 warning 同时会带出 `warning_conditions` 与 `warning_categories`，避免消费方只能依赖字符串文本做判断。

这一层现在也已经延伸到用户面：

- stocks fundamentals / financials 接口会直接透出 `factor_warnings` 与 `factor_diagnostics`
- 股票详情页已开始展示与当前基本面快照直接相关的 warning / diagnostic
- 单股分析页也已开始复用同一套结构化提示做基本面口径预览
- 前端文案通过统一模块复用，避免 screening、详情页、分析页出现各写各的解释文本

## 5. 当前已经明确解决的问题

截至现在，下面这些问题已经从“隐患”变成“有明确治理约束”：

- P0 字段归属和输出集合漂移
- screening 与 snapshot 的字段注册漂移
- catalog 与 schema 的字段存在性漂移
- cautious 字段静默返回空值
- fallback、单位换算、保守代理只写在实现里
- 关键多源字段的来源优先级只存在于 runtime 代码中

## 6. 当前仍然没完全完成的部分

这轮工作已经把 P0 的基础治理框架搭起来，但还没有结束。当前剩余缺口主要有三类：

### 6.1 公式级策略仍不够结构化

例如：

- 税率估算规则
- 同比对比期选择规则
- CAGR 基期选择规则
- composite score 的最小可计算输入组合

这些语义现在已经形成首轮覆盖：P0 全量字段都已具备 `minimum_input_groups`，`minimum_computable_conditions` 已按需要登记到同比、CAGR、比率和谨慎评分等 hard gate 字段上，`warning_conditions` 与 `warning_categories` 也已开始覆盖 fallback、保守代理、样本偏小和精度下降等 soft warning 场景；但更细粒度的条件表达和非 P0 扩展还没完成。

### 6.2 治理范围仍主要限于 P0

当前做得最完整的是 P0 基本面因子。非 P0 因子包和技术因子，还没有接入同等级的 schema/contract/source_priority 治理链路。

### 6.3 还没有形成全仓库版本化定义层

虽然 P0 范围内已经具有声明式定义，但这还不是“覆盖全仓库、可版本化发布”的最终 schema 系统。

## 7. 当前最准确的状态描述

如果要用一句话概括当前状态，最准确的说法是：

- canonical period layer 已落地并已被主要下游消费
- P0 field schema 已成为单一事实来源
- factor catalog 已从说明文档升级为治理组件
- runtime semantic contract 已结构化并纳入自动校验
- source_priority 已在 P0 范围内进入声明式治理
- 验证脚本已经具备“字段治理回归”职责

但同时：

- 这还不是全仓库正式版本化的数据定义系统

## 8. 建议的后续顺序

如果继续往下推进，建议优先级如下：

1. 继续细化 `warning_conditions`、`warning_categories` 与 `minimum_computable_conditions` 的边界，把更多“分母近零”“样本偏小但可接受”“代理口径精度下降”这类情况继续结构化
2. 把同样的 calculation_mode、semantic_tags、source_priority 与公式级策略结构扩到非 P0 因子包
3. 把 P0 这套治理结构进一步抽象成可版本化的正式 schema/contract 系统
