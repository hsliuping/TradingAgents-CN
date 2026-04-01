# 技术因子治理说明

## 概述

本项目已将首批技术因子纳入与 P0 基本面因子同级的治理框架，覆盖以下四层：

- schema：字段显示名、数据类型、source priority、minimum input groups、minimum computable conditions
- catalog：因子分类、实现等级、输入字段、说明文案、风险/约束提示
- runtime semantic contract：运行时可用输入、来源优先级、历史窗口约束
- regression validation：物化集合、视图、数据库筛选、增强筛选数据库路径、schema/catalog/runtime 对齐校验

## 首批受治理技术因子

当前已经纳入同级治理的技术因子如下：

- `ma20`
- `rsi14`
- `kdj_k`
- `kdj_d`
- `kdj_j`
- `dif`
- `dea`
- `macd_hist`

这些字段当前已经同时满足：

- 已物化到 `stock_technical_indicators`
- 已投影到 `stock_screening_view`
- 已进入数据库筛选输出
- 已进入增强筛选数据库路径判定与执行
- 已纳入 `scripts/validate_technical_factors.py` 回归校验

## ma60 当前状态

`ma60` 目前已经完成以下治理层登记：

- 已登记在技术因子 schema
- 已登记在 factor catalog
- 已登记在 runtime semantic contract

但 `ma60` 当前**没有进入公开 screening 字段**，原因是：

- 首批技术因子治理先收口到已经完成端到端数据库链路验证的一组字段
- 当前 `stock_technical_indicators` 首批公开物化字段和 `stock_screening_view` 的公开筛选字段并未把 `ma60` 纳入回归链
- 如果先把 `ma60` 暴露给公开 screening，而没有同步进入公开物化字段、视图字段和统一回归校验，会出现“catalog 宣称可筛选，但数据库路径未完成同级验证”的语义漂移

换句话说，`ma60` 不是不能算，而是当前刻意不作为首批公开筛选字段发布。

## 数据路径

技术因子的数据库路径如下：

1. 从 `stock_daily_quotes` 提取历史行情
2. 通过 `scripts/materialize_technical_indicators.py` 计算并写入 `stock_technical_indicators`
3. 由 `stock_screening_view` 按 `code + source` 关联技术快照的最新记录
4. `DatabaseScreeningService` 从视图读取技术字段
5. `EnhancedScreeningService` 在数据库可处理条件下直接走数据库筛选路径

当前 A 股筛选路径仍遵循首选源语义，默认以优先级最高的数据源为准。

## 校验入口

推荐的统一校验入口：

```bash
python scripts/run_factor_validations.py
```

技术因子专项校验：

```bash
python scripts/validate_technical_factors.py
```

VS Code 任务：

- `Run Factor Validations`

注册表查询入口：

- `GET /api/screening/factor-registry`
- `GET /api/screening/factor-registry/{factor_id}`

技术因子专项校验当前覆盖：

- `BASIC_FIELDS_INFO` 与技术 schema 对齐
- technical schema / catalog / runtime semantic contract 对齐
- `stock_technical_indicators` 非空覆盖率
- `stock_screening_view` 与技术快照一致性
- 数据库筛选结果中技术字段非空可用
- 增强筛选在技术条件下是否实际走数据库路径

## 后续扩展原则

后续若要把新的技术因子加入公开 screening，至少需要同时完成以下动作：

1. 增加或更新物化字段
2. 视图投影该字段
3. 数据库筛选输出该字段
4. 增强筛选确认数据库可处理
5. schema / catalog / runtime semantic contract 三层登记
6. 将该字段纳入统一回归校验

未同时满足以上条件前，不应仅在 catalog 或 UI 层宣称该字段可用于公开筛选。
