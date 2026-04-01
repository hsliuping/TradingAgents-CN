# 财务 Period 规范化层说明

这份文档用于说明当前仓库里已经落地的财务数据定义层雏形：它解决了什么问题、现在长什么样、哪些部分已经可用、哪些部分还没有完成。

## 1. 为什么要做这一层

历史上，`stock_financial_data` 同时承担了几种职责：

- 最新快照存储
- 多来源混合落库
- 原始子表归档
- 下游因子读取入口

这会带来几个明显问题：

- 同一只股票往往只保留少量顶层字段，跨期因子无法稳定计算
- 历史多期数据实际藏在 `raw_data` 子表里，但消费方往往读不到
- 不同来源的字段命名和层级不一致，导致每个下游都要自己处理一遍口径
- 筛选、runtime、报告很容易各算各的，出现轻微偏差甚至结构性缺失

当前引入的 `stock_financial_periods`，就是为了解决这个问题。

## 2. 当前已经落地的能力

当前已经存在一个可运行的 canonical period 层，主要由下面几部分组成：

- 展开逻辑：`core/skill_runtime/data_access.py` 中的 `expand_financial_document_to_periods(...)`
- 规范化访问：`core/skill_runtime/data_access.py` 中的 `get_stock_financial_periods(...)`
- 物化脚本：`scripts/materialize_financial_periods.py`
- 目标集合：`stock_financial_periods`

当前消费这个层的下游包括：

- 基本面 runtime bundle
- 基本面 snapshot
- 数据库筛选服务的财务富化
- `stock_screening_view`

也就是说，这层现在已经不是“设计中的概念”，而是实际运行路径的一部分。

## 3. 当前 canonical record 的结构

一条 canonical period record 的核心原则是：

- 以 `symbol + source + report_period + ann_date` 作为 period 粒度识别
- 把高频消费字段平铺到顶层
- 把来源明细保留在 `raw_data` 下

当前记录通常包含以下几类字段。

### 3.1 标识字段

- `symbol`
- `code`
- `name`
- `source`
- `data_source`
- `report_period`
- `report_date`
- `report_type`
- `ann_date`
- `updated_at`

### 3.2 平铺后的收入与利润字段

- `revenue`
- `oper_rev`
- `net_income`
- `net_profit`
- `oper_profit`
- `operating_profit`
- `ebit`
- `total_profit`
- `oper_cost`
- `oper_exp`
- `admin_exp`
- `fin_exp`
- `rd_exp`

### 3.3 平铺后的资产负债字段

- `total_assets`
- `total_liab`
- `total_equity`
- `total_cur_assets`
- `total_cur_liab`
- `total_nca`
- `total_ncl`
- `money_cap`
- `accounts_receiv`
- `inventories`
- `fix_assets`

### 3.4 平铺后的现金流字段

- `n_cashflow_act`
- `n_cashflow_inv_act`
- `n_cashflow_fin_act`
- `c_cash_equ_end_period`
- `c_cash_equ_beg_period`

### 3.5 平铺后的常用指标字段

- `roe`
- `roa`
- `gross_margin`
- `netprofit_margin`
- `debt_to_assets`
- `assets_to_eqt`
- `current_ratio`
- `quick_ratio`
- `cash_ratio`

### 3.6 原始来源保留区

- `raw_data.income_statement`
- `raw_data.balance_sheet`
- `raw_data.cashflow_statement`
- `raw_data.financial_indicators`

这意味着：

- 下游常见因子优先读顶层平铺字段
- 只有在顶层字段不足时，才回退到 `raw_data.*`

## 4. 当前这层的定位

当前这层更准确的定位是：

- 它已经是 canonical storage/access layer
- 但还不是完全独立的 declarative schema layer

换句话说，当前已经具备：

- 统一 period 粒度
- 统一字段名
- 统一常用回退链
- 统一下游消费入口

但还没有完全具备：

- 独立 schema 定义文件
- 字段级单位声明
- 字段级缺失策略声明
- source 优先级和冲突策略的声明式定义
- 数据质量等级或 unavailable reason 的统一输出

## 5. 现在应该怎样使用它

当前推荐的使用原则如下。

### 5.1 新的基本面实现

默认直接使用：

- `get_stock_financial_periods(...)`

不建议新的跨期逻辑再默认直接读取：

- `get_stock_financial_data(...)`

### 5.2 读取顺序

建议统一遵循：

1. 先读平铺字段
2. 平铺字段没有，再读 `raw_data.*`
3. 仍然没有时，再决定是否允许保守估算

### 5.3 对旧集合的定位

当前建议把：

- `stock_financial_data`

理解为：

- 历史兼容层
- 原始归档层
- 最新快照来源之一

而不要再把它当作新的业务语义主入口。

## 6. 已经验证通过的结果

当前 period 层迁移之后，以下能力已经在实际验证中恢复或稳定：

- `peg`
- `roic`
- `piotroski_f_score`
- `altman_z_score`
- `revenue_yoy`
- `net_profit_yoy`
- `oper_profit_yoy`
- `revenue_cagr_3y`
- `profit_cagr_3y`
- `working_capital_change`
- `pb_mrq`
- `interest_coverage`

并且 screening、runtime、snapshot 三条链路的口径已经基本对齐。

## 7. 仍然没有完成的部分

当前还没有完全完成的工作主要有三类。

### 7.1 正式 schema 化

需要把当前隐含在代码里的字段定义，抽成正式 schema，例如：

- 字段名
- 单位
- 数据类型
- 允许缺失策略
- 估算回退策略
- `cautious` 等级

### 7.2 source-to-canonical mapping 独立化

当前很多字段映射仍然写在展开和平铺代码里。

后续更合理的做法是把不同来源到 canonical 字段的映射单独抽成声明式配置。

### 7.3 数据质量元信息

像 `beneish_m_score` 这种字段，现在只能返回 `null`。

后续更理想的是统一补上：

- `unavailable_reason`
- `data_quality_state`
- `derived_from`

这样下游才能区分：

- 是真实没有数据
- 还是当前口径不允许保守估算
- 还是字段存在但质量不足

## 8. 推荐的下一步

如果下一阶段要把这层真正做成“正式数据定义层”，建议按下面顺序推进：

1. 抽出 canonical financial period schema 文档和代码定义
2. 抽出 source 映射表，而不是继续把映射逻辑散在实现里
3. 为 `cautious` 因子统一加入 unavailable reason / quality state
4. 再把更多下游逻辑改为直接消费 schema，而不是只消费 helper

## 9. 一句话结论

当前仓库已经有了一层可运行、可消费、已经接入 runtime 与 screening 的财务 period 规范化层；但它还属于“正式数据定义层的第一阶段实现”，不是最终形态。
