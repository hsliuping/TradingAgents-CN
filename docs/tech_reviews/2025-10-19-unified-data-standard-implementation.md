# 统一数据标准与实施路径：行业分类、市场交易所、标识、单位时区、指标定义、冲突仲裁

日期：2025-10-19  
项目：TradingAgents-CN  
用途：数据一致性标准（PIT）与跨源融合的工程指南

## 1. 核心问题拆解
- 行业分类不统一：中文/英文/GICS/NAICS/自定义口径不一致，层级不同。
- 市场与交易所不统一：CN/HK/US 与 SSE/SZSE/HKEX/NASDAQ/NYSE 字段与符号不一。
- 标识不统一：`ts_code`、`symbol`、`full_symbol`、`yfinance` 规范不同，港股是否补零、A股是否带后缀不一致。
- 单位与时区不统一：币种（CNY/HKD/USD）、金额单位（元/百万/亿）、时间与时区格式不统一。
- 字段定义差异：财务指标口径（GAAP/IFRS/CAS），“行业/板块”语义层级不同。
- 值冲突：不同源给出名称/行业/财务数据不一致，需要仲裁与置信度规则。

## 2. 统一数据模型（Canonical Schema）
- 标识与命名（Identity）
  - 采用 `full_symbol = exchange_mic:symbol` 作为主键；`exchange_mic` 使用 ISO 10383（如 `XSHG`、`XSHE`、`XHKG`、`XNAS`、`XNYS`）。
  - `symbol` 规则：
    - A股：不带后缀的 6 位数字（如 `600519`）；`full_symbol` 形如 `XSHG:600519` 或 `XSHE:000001`。
    - 港股：不做左侧补零的纯数字字符串（如 `5`、`0005`、`2388`）；`full_symbol` 形如 `XHKG:0005`。保留 `vendor_symbols.hk_pad_left=4` 的适配能力（如 `yfinance: 0005.HK`）。
    - 美股：字母代码（如 `AAPL`）；`full_symbol` 形如 `XNAS:AAPL` 或 `XNYS:MSFT`。
  - 扩展标识：`isin`（推荐）、`country`（ISO 3166-1）、`currency`（ISO 4217）。
  - 保留供应商映射：`vendor_symbols = { tushare: 600519.SH, yfinance: 600519.SS, akshare: 600519 }`，便于反向解析与对账。
- 市场与交易所（Market/Exchange）
  - `market` 取值：`CN`、`HK`、`US`；`exchange_mic` 与 `exchange_name` 对齐；`timezone` 使用 IANA（如 `Asia/Shanghai`）。
  - 交易日历：统一由日历服务提供，含竞价/连续竞价/收盘阶段。
- 行业分类（Industry Taxonomy）
  - 采用 GICS 作为规范口径，四级：`sector`、`industry_group`、`industry`、`sub_industry`，含 `gics_code`。
  - 原始行业字段保留：`source_industry.name`、`source_industry.taxonomy`（如 CN-Industry/GICS/NAICS）、`source_industry.level`、`source_industry.code`、`map_confidence`。
  - 提供映射表：CN/自定义 → GICS；无法精确映射时标注 `approximate=true` 与置信区间。
- 单位与币种（Units/Currency）
  - 金额统一以数值 + 单位乘数表示：`value` + `unit_multiplier`（如 `1e6`/`1e8`）；保留原始单位 `unit_hint`（如 元/百万/亿）。
  - `currency` 统一为 ISO 4217；区别 `report_currency` 与 `trading_currency`；提供 `fx_rate_timestamp` 以便需要时折算。
- 时间与时区（Time/Timezone）
  - 所有事件与行情时间戳采用 `UTC`；保留 `timezone` 以描述来源时区；支持 `session_id` 与阶段枚举（`auction/open/regular/close`）。
  - 支持 PIT：`asof`、`effective_date`、`data_version`、`feature_version`，确保复现实验可重放。
- 指标定义（Metric Definitions）
  - `accounting_standard`：`GAAP`/`IFRS`/`CAS`（中国会计准则）；保留 `definition_notes` 与 `restatement=true/false`。
  - 规范字段示例：`revenue`、`net_income`、`eps_basic`、`eps_diluted`、`gross_margin`、`book_value_per_share`；必要时提供 `normalized_value` 与转换说明。
- 值冲突仲裁（Arbitration）
  - 加权聚合：综合 `source_priority`（可信度预设）、`freshness`（时间新鲜度）、`cross_validation`（与第二来源校验）、`variance`（来源间差异）。
  - 输出 `confidence_score`（0–1）与 `source_of_truth`（最终取值来源）；保留 `conflict_log` 以便审核。
  - 提供人工覆盖台帐：`manual_override`，含审计字段与过期策略。

## 3. 实施路径（Phased Plan）
- Phase 0：字典与规范
  - 产出 `exchange_mic`、`market`、`timezone` 枚举字典；确定 `full_symbol` 规则与港股补零适配选项。
  - 行业映射初稿：CN/自定义 → GICS；定义不可映射与近似映射标记。
  - 指标口径定义与度量单位规范；PIT 与版本字段约定。
- Phase 1：适配器与规范化函数
  - `normalize_symbol(source, code)`: 解析并生成 `full_symbol` 与 `vendor_symbols`。
  - `map_industry(source_field)`: 映射到 GICS 并产出 `map_confidence`。
  - `normalize_units(value, unit_hint, currency)`: 标准化数值与单位乘数；区分报告币与交易币。
  - `normalize_time(ts, timezone)`: 统一到 UTC 并保留来源时区。
- Phase 2：数据服务接口
  - `GET /meta/symbol/resolve`: 输入任意 `ts_code/symbol/yfinance`，输出规范化身份与映射。
  - `GET /data/candles`: 入参 `full_symbol/start/end/granularity/adjustment`；返回 `ts(open/high/low/close/volume/turnover/currency)`，`timezone=UTC`，含 `exchange_mic/market/unit_multiplier` 元数据。
  - `GET /data/industry`: 返回 GICS 规范字段与来源映射。
- Phase 3：校验与测试
  - 构建黄金样本集（CN/HK/US 各 50–100 标的）；覆盖多来源差异与典型边界。
  - 单元/集成测试：符号解析、行业映射、单位标准化、时间归一化与仲裁评分。
  - 观测与审计：生成冲突报告与人工覆盖审计台帐。
- Phase 4：交付与集成
  - 前后端联调：统一模型接入回测与模拟交易服务；SSE/WebSocket 推送采用规范字段。
  - 文档与版本：发布标准与字典文件；冻结 `data_version/feature_version` 与兼容策略。

## 4. 关键枚举与规则（摘要）
- `market`：`CN`、`HK`、`US`。
- `exchange_mic`：`XSHG`（SSE）、`XSHE`（SZSE）、`XHKG`（HKEX）、`XNAS`（NASDAQ）、`XNYS`（NYSE）。
- `full_symbol`：`exchange_mic:symbol`；A股不带后缀、港股不强制补零、美股字母代码。
- `timezone`：IANA 时区；所有时间戳以 `UTC` 存储。
- 行业：采用 GICS 四级，保留来源字段与映射置信度。

## 5. 快速示例
- 美股 AAPL：`symbol=AAPL`，`full_symbol=XNAS:AAPL`，`yfinance=AAPL`。
- A股 贵州茅台：`symbol=600519`，`full_symbol=XSHG:600519`，`tushare=600519.SH`，`yfinance=600519.SS`。
- 港股 长江和记：`symbol=0005`，`full_symbol=XHKG:0005`，`yfinance=0005.HK`（适配器支持左补零 4）。

## 6. 落地检查清单（Checklist）
- 明确 `full_symbol` 与 `exchange_mic` 作为唯一主键，完成字典发布。
- 完成 CN/HK/US 的符号解析与来源映射适配器。
- 发布 GICS 映射表与 `map_confidence` 规则；标注不可映射场景。
- 金额单位标准化与币种处理；记录 `unit_multiplier` 与 `fx_rate_timestamp`。
- 时间归一化至 `UTC`；保留 `timezone` 与 `session_id`。
- 启用仲裁与置信度评分；生成冲突与覆盖审计报告。
- 冻结 `data_version/feature_version`，确保 PIT 可复现。

注：本标准为工程实践指南，后续可在 `docs/config/` 发布字典与映射 JSON/YAML 文件，并在 `app/routers/data.py` 与适配器中逐步落地实现。