# P0 因子统一字段定义与输出 Schema

这份文档说明当前第一批 P0 基本面因子的统一字段定义，以及 bundle、snapshot、screening 三条输出链路应共享的最小 schema。

对应代码入口：

- [core/skill_runtime/factor_schema.py](core/skill_runtime/factor_schema.py)

相关阶段总览：

- [docs/analysis/P0_FACTOR_GOVERNANCE_PHASE_SUMMARY.md](docs/analysis/P0_FACTOR_GOVERNANCE_PHASE_SUMMARY.md)

## 1. 为什么要单独抽这一层

在这一轮重构之前，下面几份定义是分散维护的：

- runtime bundle 自己维护字段列表
- 验证脚本自己维护字段列表
- screening metadata 自己维护字段注册
- 文档再单独维护一份说明

这会带来两个问题：

- 同一个字段是否属于 P0、属于哪个 bundle，容易在不同地方写出不同版本
- 新增或调整字段时，验证脚本和文档很容易漏改

现在新增的 `core/skill_runtime/factor_schema.py`，就是先把 P0 这一层的统一字段定义收口起来。

## 2. 当前统一管理的内容

当前这份 schema 主要统一了四类信息：

- `P0_VALUE_FIELDS`
- `P0_QUALITY_FIELDS`
- `P0_GROWTH_CASHFLOW_FIELDS`
- `P0_SNAPSHOT_ONLY_FIELDS`

同时派生出：

- `P0_PUBLIC_SCREENING_FIELDS`
- `P0_FACTOR_FIELD_SCHEMA`
- `get_p0_snapshot_schema()`

## 3. 三个 bundle 的标准字段集合

### 3.1 value_core

- `pe`
- `pe_ttm`
- `pb`
- `pb_mrq`
- `ps_ttm`
- `dividend_yield`
- `peg`
- `industry_pe_median`
- `industry_pb_median`

### 3.2 quality_core

- `roe`
- `roa`
- `gross_margin`
- `netprofit_margin`
- `debt_to_assets`
- `assets_to_eqt`
- `current_ratio`
- `quick_ratio`
- `cash_ratio`
- `roic`
- `cash_conversion`
- `accrual_ratio`
- `asset_turnover`
- `gross_profit_to_assets`
- `interest_coverage`
- `inventory_turnover`
- `receivable_turnover`
- `net_cash_position`
- `piotroski_f_score`
- `altman_z_score`
- `beneish_m_score`

### 3.3 growth_cashflow_core

- `revenue_yoy`
- `net_profit_yoy`
- `oper_profit_yoy`
- `revenue_cagr_3y`
- `profit_cagr_3y`
- `revenue_ttm`
- `net_profit_ttm`
- `n_cashflow_act`
- `fcf`
- `fcf_yield`
- `fcf_margin`
- `ocf_yield`
- `net_working_capital`
- `working_capital_change`

## 4. snapshot 与 screening 的差异

当前约定如下：

- snapshot 可以包含全部 P0 字段
- screening 只暴露 `P0_PUBLIC_SCREENING_FIELDS`
- 当前 `industry_pe_median` 和 `industry_pb_median` 属于 snapshot-only 字段，不作为公共筛选字段

这样做的原因是：

- 行业中位数更适合做解释和对比，不适合直接做数据库筛选字段
- screening 字段要优先保证稳定性和可索引/可查询性

## 5. 单字段 schema 里目前包含什么

`P0_FACTOR_FIELD_SCHEMA` 中每个字段当前统一记录：

- `field_name`
- `display_name`
- `bundle`
- `data_type`
- `unit`
- `description`
- `screening_unit`（可选，用于 screening 链路的展示单位覆盖）
- `source_priority`（可选，声明多源字段在 runtime 中的优先读取顺序）
- `calculation_mode`（字段计算模式，如 `direct`、`fallback`、`ratio`、`period_compare`、`composite_score`）
- `tax_estimation_strategy`（可选，声明公式中税率如何估算）
- `period_selection_strategy`（可选，声明同比、CAGR、最近两期差额等场景如何选取对比期）
- `minimum_input_groups`（可选，声明字段至少满足哪一组输入即可进入计算）
- `minimum_computable_conditions`（可选，声明进入计算前仍需满足的附加条件，例如“comparison_period available”或“total_assets != 0”）
- `warning_conditions`（可选，声明命中后应给出 soft warning、但不阻断计算的条件）
- `warning_categories`（可选，声明 soft warning 的结构化类别，例如 `fallback_used`、`proxy_used`、`low_sample_size`、`precision_degraded`）
- `semantic_tags`（字段语义标签，如 `fallback_chain`、`denominator_guard`、`unit_conversion`、`conservative_proxy`、`availability_guard`）
- `included_in_screening`
- `included_in_snapshot`

这一层目前已经足够支撑：

- 验证脚本
- 文档同步
- bundle 输出约束
- 后续 report/schema 生成
- screening 基本面字段 metadata 自动对齐
- cautious 字段的结构化诊断输出
- schema 与 runtime semantic contract 的结构化联动校验

## 6. 当前还没有纳入的内容

这份 schema 和当前 snapshot 现在还没有完全覆盖以下内容：

- 更细粒度、全量覆盖的公式级约束，目前已经开始覆盖最小输入组、税率估算、period 选择，但还没有扩展到全部非 P0 因子
- 非 P0 因子的同类结构化语义定义

其中当前已经补上的部分是：

- `piotroski_f_score`、`altman_z_score`、`beneish_m_score` 这类 `cautious` 字段，snapshot 会输出 `factor_diagnostics`
- 诊断项当前至少包含 `data_quality_tier`、`data_quality_state`、`unavailable_reason`、`missing_inputs`
- `factor_schema.py` 现在已经显式记录 `calculation_mode` 与 `semantic_tags`
- `factor_schema.py` 现在可以为多源字段显式记录 `source_priority`
- `factor_schema.py` 现在已经开始为代表性字段显式记录 `tax_estimation_strategy` 与 `period_selection_strategy`
- `factor_schema.py` 现在已经为全量 P0 字段显式记录 `minimum_input_groups`，并为需要额外门槛的字段登记标准化的 `minimum_computable_conditions`
- `factor_schema.py` 现在也已经开始为回退使用、保守代理、行业样本偏小这类“不阻断但应提示”的场景登记 `warning_conditions`
- `factor_schema.py` 现在已经开始为 soft warning 同步登记 `warning_categories`，避免下游只能靠 warning 文本做字符串判断
- `factor_catalog.py` 中的 `RuntimeSemanticContract` 已与 `factor_schema.py` 建立自动一致性校验
- P0 字段当前已统一具备 `source_priority` 覆盖，缺少登记会被验证脚本直接判为失败
- P0 字段当前也已统一具备 `minimum_input_groups` 覆盖，schema 或 runtime contract 任一侧漏登记都会被验证脚本直接判为失败
- 对于 `cautious`、同比/CAGR/最近两期对比字段，以及带显式分母保护的字段，`minimum_computable_conditions` 当前已纳入硬校验
- 对于 fallback、conservative proxy 和 peer stat 这类适合“提醒但不阻断”的字段，`warning_conditions` 与 `warning_categories` 当前都已纳入硬校验

但这还不是完整覆盖，原因是：

- 目前只有部分 `cautious` 字段接入了结构化诊断
- source_priority 虽然已经覆盖全量 P0 字段，但目前仍只治理 P0 范围，还没有扩展到更广范围的来源优先级治理
- 一些实现细节仍是文本级 contract，而不是更细的可执行公式契约

其中 source 优先级这一项，当前已经扩展为全量 P0 字段覆盖。对于直接字段，它主要表达“字段别名与嵌套路径的读取优先级”；对于派生或组合字段，它主要表达“关键输入来源与比较期来源的优先顺序”。

这些内容仍处在“P0 内已形成首轮结构化、但更大范围仍部分实现内嵌”的阶段。

## 6.1 最小输入组、可计算条件与警告条件现在如何理解

这三类字段的目标，是把“字段为什么能算 / 为什么不能算 / 为什么虽然算出来了但需要提示”的规则，也从实现代码里抬到声明层。

- `minimum_input_groups` 表示“满足其中任意一组，就具备进入计算的最低输入”
- `minimum_computable_conditions` 表示“即便输入组满足，仍然需要满足的条件”
- `warning_conditions` 表示“即便已经算出来，只要命中这些条件，仍应给出 soft warning”
- `warning_categories` 表示“这条 soft warning 属于哪一类结构化语义”

例如：

- `revenue_ttm` 这类直接字段，会登记单字段输入组
- `net_working_capital` 会登记 `total_cur_assets + total_cur_liab`
- `revenue_yoy` 会登记当前期与上年同期收入输入组，并附带 `comparison_period available`、`prior_period_metric != 0`
- `industry_pe_median` 会登记行业与估值输入组，并在样本偏小时附带 `industry_peer_sample_count < 5` 警告，而不是阻断计算
- `pb_mrq`、`interest_coverage`、`fcf` 这类字段，会在使用保守代理或回退路径时附带对应 `warning_conditions`
- 上述 warning 同时还会被归类到如 `proxy_used`、`fallback_used` 这类 `warning_categories`
- `beneish_m_score` 这类谨慎字段，会登记双期关键原始输入，并附带 `comparison_period available`、`sales_previous != 0`、`asset_quality_previous != 0` 等 hard gate 条件

这样做的直接收益是：

- schema 可以表达“最小可算门槛”
- runtime contract 可以表达同一语义并参与一致性校验
- 当字段返回 `null` 时，diagnostics 更容易把“缺字段”和“条件不满足”拆开说明
- 当字段虽然有值但使用了回退或保守代理时，warnings 可以把“可用但需谨慎解释”的语义带出去
- 常见可计算条件现在复用统一短语，减少了 schema、contract、文档三侧各写一套文本的漂移风险

## 6.2 当前 hard gate 与 soft warning 的边界

当前约定是：

- `minimum_input_groups` 与 `minimum_computable_conditions` 属于 hard gate；不满足时字段应返回 `null` 或不进入计算
- `warning_conditions` 与 `warning_categories` 属于 soft warning；命中时字段仍可返回值，但需要带出结构化提示

其中当前已经落地的典型 soft warning 包括：

- fallback 路径被触发，例如 `pe_ttm fallback_to pe`
- conservative proxy 被触发，例如 `fcf conservative_proxy_used`
- peer stat 样本偏小，例如 `industry_peer_sample_count < 5`

当前 snapshot 与 screening 都已经开始输出 `factor_warnings`。stocks 基础面与财务明细接口现在也会透出同一套结构化结果，前端详情页与单股分析页直接复用，不再各自维护第二套解释逻辑。例如当前茅台回归里，可以看到：

- `pb_mrq` 命中了 `pb_mrq estimated_from market_cap_and_total_equity`
- `interest_coverage` 命中了 `interest_coverage fallback_to raw_interest_expense`
- `fcf` 命中了 `fcf conservative_proxy_used`

并且每条 warning 现在都会附带结构化类别：

- `pb_mrq` -> `proxy_used`
- `interest_coverage` -> `fallback_used`
- `fcf` -> `proxy_used`

这一层与 `factor_diagnostics` 的区别是：

- `factor_diagnostics` 主要解释“为什么没算出来或为什么返回空值”
- `factor_warnings` 主要解释“虽然算出来了，但口径上需要谨慎解释”，并同时输出 `warning_conditions` 与 `warning_categories`

## 7. 当前建议的使用方式

后续如果你们还要扩展 P0 或增加 bundle，建议遵循下面顺序：

1. 先改 `core/skill_runtime/factor_schema.py`
2. 再改 bundle 实现
3. 再改 screening 字段注册或验证脚本
4. 最后再补文档说明

也就是说，`factor_schema.py` 应该成为 P0 字段定义的单一事实来源。

当前代码里，`app/models/screening.py` 的 P0 公共基本面字段已经改为从这份 schema 派生，`app/routers/screening.py` 的 financial 分类也复用了同一份字段集合。

另外，`net_working_capital`、`working_capital_change` 这类字段当前存在 runtime snapshot 与 screening 展示单位不一致的历史现实，因此 schema 允许用 `screening_unit` 显式声明 screening 链路单位，而不把这种差异继续埋在各处手写 metadata 里。

当前 snapshot 的 `factor_diagnostics` 也已经开始承载 `cautious` 字段的结构化诊断信息。例如：

- `piotroski_f_score` 会标记缺少对比期或双期输入字段
- `altman_z_score` 会标记缺少关键分量或 0 分母
- `beneish_m_score` 会标记缺少折旧摊销类原始字段或缺少对比期

这样在字段返回 `null` 时，调用方拿到的不再只是空值，还能知道是“缺期”、“缺字段”还是“分母非法”。

screening 链路当前也已补上一版精简诊断：

- 结果项只在 `cautious` 字段实际为 `null` 时返回 `factor_diagnostics`
- 对已命中的 soft warning，screening 结果项现在也会返回 `factor_warnings`
- screening 侧诊断默认不重复回传全部可用字段，只返回缺失字段的状态与原因
- 这样可以在不显著放大筛选结果体积的前提下，把 `null` 的语义带出去

stocks 详情链路当前也已接入同一套输出：

- `/api/stocks/{symbol}/fundamentals` 会返回 `factor_warnings` 与 `factor_diagnostics`
- `/api/stocks/{symbol}/financials` 会返回 `factor_snapshot`、`factor_warnings` 与 `factor_diagnostics`
- 股票详情页与单股分析页前端统一复用同一套业务化映射模块展示这些结构化提示
- 这样同一个字段在 screening、详情页、单股分析页上的“可用但需谨慎解释”语义可以保持一致，而不是每个页面再单独写一套说明

## 8. 下一步可以怎么继续

如果下一步继续完善，可以优先做下面两件事：

1. 继续细化 `minimum_computable_conditions` 的表达粒度，例如把更多分母保护、可比期存在性和样本门槛写成更稳定的声明
2. 再把这套公式级结构化定义向非 P0 因子包扩展
