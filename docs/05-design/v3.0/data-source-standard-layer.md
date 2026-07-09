# TradingAgents-CN Pro — 数据源接入标准层设计

**版本**: v3.0
**日期**: 2026-03-13
**状态**: 设计完成，待实施

---

## 1. 背景与结论

### 1.1 当前问题

当前系统已经具备多数据源接入能力，但不同数据域的标准化深度不一致：

1. 行情、K 线、基础信息已经有较明确的统一输出结构。
2. 财务数据虽然已接入 Tushare、AKShare、BaoStock、QMT 等来源，但标准化粒度不一致。
3. 不同接口存在“按优先级选源”和“按最新记录选源”并存的问题，容易导致页面展示混源。
4. 数据源实现当前大部分仍位于开源仓库，难以沉淀为商业版专有能力。

### 1.2 核心结论

这层**必须做**，但不应该做成“全量数据中台”。

正确方向是：

1. 建立**分域薄标准层**，而不是一个大而全的总标准层。
2. 优先标准化高价值、高复用、语义稳定的数据域。
3. 财务域当前阶段采用**单源优先策略**，默认以 Tushare 为主数据源。
4. 将“接口协议和加载机制”留在开源，将“数据源实现、字段映射、质量策略、优先级策略”逐步迁入闭源实现层。

### 1.3 为什么现在做

如果后续要接入：

1. QMT（实时行情、交易、财务、账户）
2. 米筐 / RiceQuant（研究数据、因子、历史数据、部分基础面）
3. 其它券商 / 商业数据源

没有标准层时，每接一个源，都要重复修改：

1. 数据源接入代码
2. 页面数据映射
3. 服务层聚合逻辑
4. 智能筛选 / 工具层输出
5. 数据源优先级选择逻辑

有了标准层后，新增源主要变成“实现一个 provider adapter + 对接标准域接口”的工作，边界清晰很多。

---

## 2. 设计目标

### 2.1 本阶段目标

1. 统一数据源接入的协议层。
2. 定义系统真正需要的业务标准域。
3. 明确哪些数据域做多源标准化，哪些域暂时单源。
4. 为闭源 provider 实现预留稳定的插件式加载入口。
5. 降低后续接入 QMT、米筐、券商接口的边际成本。

### 2.2 非目标

当前版本不做以下内容：

1. 不做全量财务字段的跨源统一语义模型。
2. 不做所有源字段级自动补齐和自动融合。
3. 不做完整的数据血缘平台或数据质量平台。
4. 不要求开源版保留所有商业数据源实现。

---

## 3. 总体原则

### 3.1 分域标准化，而不是全局统一

标准化应按数据域拆分，而不是把所有数据揉成一个总 schema。

建议分为以下标准域：

1. 行情域 QuoteDomain
2. K 线域 KlineDomain
3. 股票基础信息域 SecurityMasterDomain
4. 基础面快照域 FundamentalsSnapshotDomain
5. 财务明细域 FinancialStatementDomain
6. 交易执行域 TradingExecutionDomain
7. 研究/因子域 ResearchFactorDomain

### 3.2 优先稳定域，延后复杂域

优先做：

1. 实时行情
2. K 线
3. 基础信息
4. 基础面快照

暂缓重型多源统一：

1. 财务报表细项
2. 财务指标衍生项
3. 因子与研究数据

### 3.3 财务域采用单源优先

财务数据在当前阶段默认采用：

1. 主源：Tushare
2. 备用源：AKShare / BaoStock / QMT / 未来米筐
3. 页面默认不混源展示财务快照
4. 备用源仅在显式指定或后续补齐策略中使用

原因：

1. 财务指标同名不同义的问题远高于行情域
2. 单源更利于解释、审计和调试
3. 当前 Tushare 财务标准化成熟度最高

### 3.4 开源保协议，闭源保能力

开源应保留：

1. 标准域接口
2. adapter 抽象类
3. manager / registry / loader 机制
4. 业务层调用标准域的方式

闭源应承载：

1. 具体数据源适配实现
2. 字段映射规则
3. 优先级策略
4. 数据质量评分
5. 补齐与降级逻辑
6. 商业数据源接入（QMT、米筐等）

---

## 4. 分层架构

### 4.1 建议分层

```text
应用层（页面 / 工具 / 智能体 / API）
    ↓
业务标准域层（Quote / Kline / Fundamentals / Financials / Trading / Research）
    ↓
源适配聚合层（Source Selector / Fallback / Priority / Quality Policy）
    ↓
Provider Adapter 层（Tushare / AKShare / BaoStock / QMT / RiceQuant / Proprietary）
    ↓
原始数据源（远程 API、本地终端、文件、数据库）
```

### 4.2 各层职责

#### A. 应用层

只调用标准域接口，不直接理解具体数据源字段。

包括：

1. 股票详情页
2. 传统筛选
3. 智能筛选
4. 分析任务
5. MCP / 工具调用

#### B. 业务标准域层

负责定义“系统真正要消费的数据语义”。

例如：

1. QuoteDomain 返回 `close`, `pct_chg`, `amount`, `turnover_rate`
2. KlineDomain 返回 `time/open/high/low/close/volume/amount`
3. FundamentalsSnapshotDomain 返回 `pe`, `pb`, `ps`, `roe`, `debt_to_assets`, `dividend_yield`
4. FinancialStatementDomain 返回 `summary`, `raw_data`, `source_meta`

#### C. 源适配聚合层

负责：

1. 按配置选择数据源优先级
2. 决定是否允许 fallback
3. 控制是否允许跨源补齐
4. 记录命中源、缺失字段、质量标记

#### D. Provider Adapter 层

负责：

1. 和具体数据源打交道
2. 处理认证、限流、连接方式
3. 将原始响应转为“该源内部统一对象”
4. 交给上层做标准域映射

---

## 5. 标准域设计

### 5.1 QuoteDomain

**适用源**：Tushare、AKShare、BaoStock、QMT、米筐

**标准输出建议**：

```json
{
  "code": "000001",
  "trade_date": "20260313",
  "close": 12.34,
  "pct_chg": 1.25,
  "amount": 123456789.0,
  "turnover_rate": 3.21,
  "source": "qmt",
  "updated_at": "2026-03-13T15:00:00+08:00"
}
```

**结论**：这一域强烈建议做完整标准层。

### 5.2 KlineDomain

**适用源**：Tushare、AKShare、BaoStock、QMT、米筐

**标准输出建议**：

```json
{
  "code": "000001",
  "period": "day",
  "items": [
    {
      "time": "2026-03-13",
      "open": 12.1,
      "high": 12.5,
      "low": 11.9,
      "close": 12.34,
      "volume": 1234567,
      "amount": 123456789
    }
  ],
  "source": "tushare"
}
```

**结论**：这一域强烈建议做完整标准层。

### 5.3 SecurityMasterDomain

**适用源**：Tushare、AKShare、QMT、米筐、本地导入

**标准输出建议**：

1. `code`
2. `name`
3. `market`
4. `exchange`
5. `board`
6. `industry`
7. `list_date`

**结论**：这一域建议做完整标准层。

### 5.4 FundamentalsSnapshotDomain

**适用源**：Tushare、AKShare、QMT、米筐

**标准输出建议**：

1. `pe`
2. `pb`
3. `ps`
4. `roe`
5. `debt_to_assets`
6. `current_ratio`
7. `dividend_yield`
8. `report_period`
9. `source`

**结论**：做标准层，但以“轻指标集合”为限，不要扩展成全量财务中台。

### 5.5 FinancialStatementDomain

**适用源**：Tushare、AKShare、BaoStock、QMT、米筐

**当前阶段策略**：

1. 默认主源仅 Tushare
2. 其它源作为备用和对照
3. 标准输出仅提供：
   1. `summary`
   2. `raw_data`
   3. `source_meta`
4. 不做跨源字段级自动融合

**标准输出建议**：

```json
{
  "summary": {
    "report_period": "20250930",
    "report_type": "quarterly",
    "revenue": 1000000000,
    "net_profit": 200000000,
    "roe": 12.5,
    "debt_to_assets": 45.6,
    "current_ratio": 1.8,
    "dividend_yield": 3.1
  },
  "raw_data": {
    "income_statement": [],
    "balance_sheet": [],
    "cashflow_statement": [],
    "financial_indicators": [],
    "main_business": []
  },
  "source_meta": {
    "selected_source": "tushare",
    "selection_policy": "single_source_priority",
    "fallback_allowed": true
  }
}
```

**结论**：本阶段只做“单源标准层”，不做“多源财务融合层”。

### 5.6 TradingExecutionDomain

**适用源**：QMT、券商 API、未来专有交易网关

**说明**：

交易执行域和行情域不同，它更适合完全闭源实现。

建议标准化：

1. 下单请求
2. 订单状态
3. 持仓快照
4. 成交回报

### 5.7 ResearchFactorDomain

**适用源**：米筐、未来商业研究数据源

**说明**：

这一域先预留接口，不在当前阶段落地标准化实现。

原因：

1. 因子口径差异很大
2. 指标体系不稳定
3. 需要等商业数据源接入后再定义标准层边界

---

## 6. 财务域为什么不能一步做到全量多源统一

### 6.1 同名不等于同义

典型例子：

1. `roe`, `roe_waa`, `roe_dt`
2. `revenue`, `oper_rev`
3. `net_income`, `net_profit`, `n_income_attr_p`
4. `dividend_yield`, `dv_ratio`, `dv_ttm`

它们的口径、期间、是否 TTM、是否归母，不一定一致。

### 6.2 当前工程投入与收益不匹配

如果现在就做完整多源财务语义标准层，需要同时解决：

1. 字段映射 registry
2. 单位转换
3. 期间类型识别
4. 报表口径差异
5. 字段缺失补齐策略
6. 字段来源追踪
7. 质量分级

这会显著拉长落地周期。

### 6.3 当前更合理的方案

本阶段财务域采用：

1. `single_source_priority`
2. `selected_source = tushare`
3. 其它源仅作为备用和调试接口

这样不会阻碍未来扩展，因为接口契约已经为多源保留了位置。

---

## 7. 开源与闭源拆分设计

### 7.1 开源保留内容

建议保留在开源仓库：

1. `DataSourceAdapter` 抽象接口
2. `DataSourceManager` / `ProviderRegistry` / `SourceSelector` 机制
3. 各标准域的 schema 与调用接口
4. 通用 API 路由和服务调用边界
5. 调试型 mock / local provider

### 7.2 闭源迁移内容

建议迁移到闭源实现：

1. Tushare 商业实现与增强逻辑
2. QMT provider
3. 米筐 provider
4. 优先级策略与质量评分策略
5. 字段映射 registry
6. 财务补齐与降级规则
7. 限流、缓存、增量同步、反爬对抗策略

### 7.3 加载方式

建议采用可插拔加载：

```text
开源主程序
  ↓
Provider Loader
  ├── 加载开源 provider
  └── 尝试加载 proprietary provider package
        └── 如果不存在，不影响社区版运行
```

建议形式：

1. Python package 插件加载
2. entry point 或显式模块导入
3. 环境变量控制启用范围

---

## 8. 建议的数据源标准层模块划分

建议新增逻辑模块，而不是一次性大改现有代码。

### 8.1 开源层建议模块

```text
app/
  services/
    data_domains/
      quote_domain.py
      kline_domain.py
      fundamentals_domain.py
      financials_domain.py
      trading_domain.py
    data_sources/
      base.py
      manager.py
      selector.py
      loader.py
      schemas.py
```

### 8.2 闭源层建议模块

```text
tradingagents_proprietary/
  data_sources/
    tushare_provider.py
    qmt_provider.py
    ricequant_provider.py
    financial_mapping_registry.py
    quality_policy.py
    fallback_policy.py
```

---

## 9. 实施路线

### 阶段 1：整理标准域接口

目标：先把“系统按什么语义消费数据”定义清楚。

工作内容：

1. 定义 Quote/Kline/Fundamentals/Financials 的标准返回 schema
2. 梳理现有 API 哪些已经满足，哪些存在混源逻辑
3. 把现有路由中零散的数据源优先级逻辑收口

交付物：

1. 标准域 schema
2. 统一 SourceSelector
3. 基础接口统一选源策略

### 阶段 2：财务域单源标准化

目标：把财务域正式固定为单源优先，并保留扩展点。

工作内容：

1. 默认财务主源改为 Tushare
2. Financials API 增加 `source_meta`
3. 筛选/详情页/智能筛选统一读取财务标准输出
4. 其它财务源改为备用和显式指定调用

交付物：

1. 财务域单源稳定输出
2. 页面与工具链一致使用财务主源

### 阶段 3：闭源 Provider Loader

目标：开始把商业数据源实现抽离到闭源层。

工作内容：

1. 新增 provider loader
2. 定义 proprietary package 约定
3. 将 QMT / Tushare 增强逻辑迁出开源实现

交付物：

1. 开源协议 + 闭源实现的装配机制
2. 社区版无闭源包时仍可运行

### 阶段 4：新增源接入模板化

目标：未来接米筐、券商源时，工作量显著下降。

工作内容：

1. 输出接入模板
2. 定义标准域到 provider 的映射 checklist
3. 提供最小接入验收脚本

---

## 10. 实现时间评估

以下评估按“1 名熟悉当前代码库的主程”估算，含设计、编码、联调、回归，不含外部数据源申请和商业 API 采购时间。

### 10.1 最小可用版本（推荐）

范围：

1. 统一 SourceSelector
2. 落地 Quote/Kline/Fundamentals/Financials 4 个标准域
3. 财务域固定 Tushare 主源
4. 页面和智能筛选统一消费标准域输出
5. 预留闭源 provider loader 接口，但暂不做完整迁移

**预计时间：5 到 8 个工作日**

细分：

1. 架构收口与 schema 定义：1 天
2. 路由 / 服务改造：2 到 3 天
3. 前端与智能筛选联调：1 到 2 天
4. 回归测试与修正：1 到 2 天

### 10.2 增强版本

范围：

1. 上述最小版本
2. 增加 `source_meta`, `missing_fields`, `selection_policy`
3. 落地闭源 provider loader
4. 抽离 Tushare/QMT 增强实现到闭源包

**预计时间：2 到 3 周**

细分：

1. Loader + 注册机制：2 到 3 天
2. 闭源包拆分与回归：3 到 5 天
3. 配置、部署、兼容性处理：2 到 4 天
4. 测试与文档：2 到 3 天

### 10.3 重型多源财务标准层

范围：

1. 建财务字段映射 registry
2. 处理字段来源追踪、单位转换、期间口径、质量标记
3. 支持字段级跨源补齐和解释

**预计时间：4 到 8 周**

结论：当前不建议直接进入这一阶段。

---

## 11. 推荐决策

### 当前推荐执行方案

建议按以下顺序推进：

1. 先做“分域薄标准层”
2. 财务域先固定 Tushare 主源
3. 其它财务源退出默认业务链路
4. 同时把 provider 实现逐步迁入闭源
5. 待未来确有多源财务融合需求，再做重型财务标准层

### 不推荐方案

当前不建议：

1. 立刻做全量多源财务统一
2. 让详情页和筛选默认字段级混源
3. 把整个数据源框架全部搬进闭源

---

## 12. 下一步落地建议

### 立即可做

1. 抽出统一 `SourceSelector`
2. 收口股票详情 / 智能筛选 / 传统筛选的选源逻辑
3. 将财务域默认主源锁定为 Tushare
4. 为 Financials API 增加 `source_meta`

### 第二步可做

1. 新建 proprietary provider loader
2. 迁移 Tushare/QMT 具体实现到闭源包
3. 对外保留开源协议层

---

## 13. 最终判断

这一层值得做，但必须做轻、做薄、做分域。

对当前 v3.0 来说，最优解不是“全量统一所有数据源”，而是：

1. 行情、K 线、基础快照先标准化
2. 财务先单源稳定
3. provider 实现逐步闭源
4. 给 QMT、米筐等未来数据源预留稳定接入位

这样既能控制当前复杂度，又能显著降低未来接入新数据源的成本。
