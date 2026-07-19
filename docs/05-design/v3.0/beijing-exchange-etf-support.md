# 北交所与 ETF 支持改进方案

## 📋 文档信息

| 项目 | 内容 |
|------|------|
| 版本 | v1.3 |
| 状态 | 核心能力已实现，持续迭代 |
| 日期 | 2026-06-21 |
| 目标 | 支持北交所股票和 ETF 的分析能力 |

---

## 0. 核心结论：ETF 需要独立存储、工具、提示词和流程

**是的，支持 ETF 分析需要：**

1. **独立的数据集合**：ETF 与股票的数据结构差异大，建议新建 `etf_basic_info`、`etf_daily_quotes` 等
2. **独立的工具**：`get_stock_fundamentals_unified` 返回 PE/PB/ROE，对 ETF 不适用，需 `get_etf_fundamentals` 等专用工具
3. **独立的提示词**：基本面分析师提示词要求分析 PE/PB/ROE，ETF 无这些指标，需 ETF 专用提示词（净值、规模、费率、跟踪误差）
4. **不同的分析流程**：用「ETF 分析师」替代「基本面分析师」，或新建 ETF 专用工作流
5. **单股分析路由**：识别 ETF 后走不同分支（工具、提示词、流程均不同）

参考现有设计：**港股/美股** 已采用独立集合模式；ETF 与股票的差异更大（无 PE/PB/ROE），提示词和流程也必须区分。

---

## 0.1 近期落地进展（2026-06-21 更新）

最近一轮已经完成的部分：

1. 已新增独立集合 `etf_basic_info`、`etf_daily_quotes` 的同步落地。
2. 已实现 `app/worker/etf_sync_service.py`，支持 ETF 基础信息与 ETF 历史日线同步。
3. 已将 QMT 接入 ETF 同步源，支持 ETF 列表获取、ETF 日线拉取，以及沪深 ETF 代码前缀纠正。
4. 已完成 QMT 历史数据和财务数据入库，分别写入 `stock_daily_quotes` 与 `stock_financial_data`。
5. 已实现 ETF 分析工作流 `v2_etf_analysis_workflow`，含 ETF 分析师 + 市场分析师 + 新闻分析师 + 风控。
6. 已实现 `get_etf_fundamentals` 工具，支持本地数据优先 + AKShare/Tushare 在线回退。
7. 已实现 `etf_analyst_v2` 分析师，系统提示词明确禁止 PE/PB/ROE，使用 ETF 专用指标。
8. 已实现 ETF 工作流专属提示词模板补齐（`etf_workflow_prompt_template_service.py`），覆盖全部 7 个 Agent。
9. 已实现前端单股分析页面 ETF 入口：市场选择器有「ETF 基金」选项，输入 ETF 代码自动识别并切换。
10. 已实现报告展示 ETF 适配：`ReportDetail.vue` 支持 ETF 分析师映射和 `isEtfAnalysis` 判断。
11. 已实现定时分析/股票关注列表 ETF 支持：`watchlist_analysis_task.py` 自动识别 ETF → `ETF_ANALYSIS`。
12. 已实现 `UnifiedStockService` ETF 映射：`collection_map["ETF"]` 指向 `etf_basic_info` / `etf_daily_quotes`。
13. 已实现行情/基本面/K 线 API 的 ETF 支持：`/api/stocks/{code}/quote`、`/fundamentals`、`/kline`。
14. 已实现模拟交易 ETF 支持：下单、持仓、价格查询均支持 ETF 代码。
15. 已实现 `planned_analysis_service.py` 中 `_ETF_FUND_KEYWORDS = []`，不再阻止 ETF 相关提问。
16. 已实现北交所支持：Tushare `exchange` 含 `BSE`，`symbol_utils` 支持 `.BJ` 前缀/后缀，`stock_utils` 识别 `8xxxxx/4xxxxx/92xxxx`，前端 `stockValidator` 支持 `43/83/87/89/92` 前缀，AKShare/QMT 适配器均支持 `.BJ`。
17. 已实现 `local_data.py` ETF 函数：`get_etf_basic_info`、`get_etf_daily_quotes`。

---

## 1. 现状分析

### 1.1 北交所（北京证券交易所）

| 模块 | 当前状态 | 说明 |
|------|----------|------|
| **数据层** | ✅ 部分支持 | AKShare、BaoStock、QMT、MultiSourceBasicsSync 均支持 8/4 开头 → `.BJ` |
| **Tushare 股票列表** | ❌ 未包含 | `get_stock_list(market="CN")` 使用 `exchange='SSE,SZSE'`，**排除北交所** |
| **Tushare rt_k 实时行情** | ✅ 已支持 | 使用 `4*.BJ,8*.BJ,9*.BJ` 通配符 |
| **symbol_utils** | ✅ 已支持 | `normalize_a_share_symbol` 支持 `SH/SZ/SS/BJ` 前缀/后缀 |
| **前端 stockValidator** | ✅ 已支持 | `43/83/87/89/92` 前缀已纳入 A 股验证 |
| **planned_analysis** | ✅ 无阻止 | 北交所属于 A 股，未被 `_check_unsupported_asset` 拦截 |
| **财务/日线同步** | ✅ 已支持 | 查询条件含 `market: 北交所` |
| **AKShare/QMT 适配器** | ✅ 已支持 | 均支持 `.BJ` 后缀和北交所代码格式 |

**北交所代码规则**（参考 `stock_code_validation.md`）：
- `92xxxx` - **北交所统一号段**（2025年10月9日起，存量公司全部切换，如海泰新能 920985）
- `43xxxx` / `83xxxx` / `87xxxx` / `89xxxx` - 北交所旧号段（新三板时期沿用，逐步退出）
- Tushare 格式：`xxxxxx.BJ`（如 920985.BJ）

### 1.2 ETF

| 模块 | 当前状态 | 说明 |
|------|----------|------|
| **planned_analysis** | ✅ 已放行 | `_ETF_FUND_KEYWORDS = []`，ETF 不再在该层被直接阻止 |
| **StockUtils** | ✅ 可识别 | `identify_security_type()` 可识别 ETF，`SecurityType.FUND` |
| **ETF 同步存储** | ✅ 已实现 | `etf_basic_info`、`etf_daily_quotes`，由 `etf_sync_service` 负责同步 |
| **数据源** | ✅ 已确认 | AKShare、Tushare、QMT 已纳入 ETF 同步映射 |
| **ETF 工作流** | ✅ 已实现 | `ETF_ANALYSIS` 任务类型、`v2_etf_analysis_workflow`、分析入口路由 |
| **ETF 工具** | ✅ 已实现 | `get_etf_fundamentals`：本地数据优先 + AKShare/Tushare 在线回退 |
| **ETF 分析师** | ✅ 已实现 | `etf_analyst_v2`：默认工具 `get_etf_fundamentals`，明确禁止 PE/PB/ROE |
| **ETF 提示词模板** | ✅ 已实现 | `etf_workflow_prompt_template_service.py`：覆盖全部 7 个 Agent |
| **前端 ETF 入口** | ✅ 已实现 | `SingleAnalysis.vue`：市场选择器「ETF 基金」、代码自动识别 |
| **ETF 报告展示** | ✅ 已实现 | `ReportDetail.vue`：ETF 分析师映射、`isEtfAnalysis` 判断 |
| **定时分析/股票关注列表 ETF** | ✅ 已实现 | `watchlist_analysis_task.py`：自动识别 ETF → `ETF_ANALYSIS` |
| **UnifiedStockService** | ✅ 已实现 | `collection_map["ETF"]` 已配置 |
| **行情/K 线/基本面 API** | ✅ 已实现 | `stocks.py` 各端点均支持 ETF 代码 |
| **模拟交易 ETF** | ✅ 已实现 | `paper.py` 支持 ETF 下单、持仓、价格查询 |
| **local_data ETF 支持** | ✅ 已实现 | `core/tools/external/local_data.py`：`get_etf_basic_info`、`get_etf_daily_quotes` |

**ETF 代码规则**（参考 `stock_utils.py`）：
- 上海：`50xxxx`、`51xxxx`、`52xxxx`、`56xxxx`、`58xxxx`
- 深圳：`15xxxx`、`16xxxx`、`18xxxx`（含部分 LOF/场内基金）

---

## 2. 改进清单

### 2.1 北交所支持（优先级：高）

| 序号 | 改进项 | 文件/模块 | 改动说明 |
|------|--------|-----------|----------|
| 1 | **Tushare 股票列表包含北交所** | `tradingagents/dataflows/providers/china/tushare.py` | ✅ 已完成，`exchange='SSE,SZSE,BSE'` |
| 2 | **symbol_utils 支持 .BJ** | `core/tools/external/symbol_utils.py` | ✅ 已完成，`normalize_a_share_symbol` 支持 `SH/SZ/SS/BJ` 前缀/后缀 |
| 3 | **Tushare rt_k 北交所通配符** | `tradingagents/dataflows/providers/china/tushare.py` | ✅ 已完成，已确认 `4*.BJ,8*.BJ,9*.BJ` 通配 |
| 4 | **前端 A 股验证补全** | `frontend/src/utils/stockValidator.ts` | ✅ 已完成，`validPrefixes` 含 `43/83/87/89/92` |
| 5 | **Skill 生成编码规范** | `core/tools/external/code_generator.py` | ✅ 已完成，北交所代码格式已纳入编码规范 |

### 2.2 ETF 支持（优先级：中）

| 序号 | 改进项 | 文件/模块 | 改动说明 |
|------|--------|-----------|----------|
| 1 | **解除 planned_analysis 阻止** | `app/services/planned_analysis_service.py` | ✅ 已完成，`_ETF_FUND_KEYWORDS = []`，ETF 不再被阻止 |
| 2 | **ETF 基础信息同步** | `app/worker/etf_sync_service.py` | ✅ 已完成，写入 `etf_basic_info`，支持 AKShare/Tushare/QMT 多源 |
| 3 | **ETF 日线/行情同步** | `app/worker/etf_sync_service.py` | ✅ 已完成，写入 `etf_daily_quotes` |
| 4 | **local_data 支持 ETF** | `core/tools/external/local_data.py` | ❌ 未实现，需增加 `get_etf_basic_info`、`get_etf_daily_quotes` |
| 5 | **分析逻辑差异化** | 智能分析 / Skill | ✅ 已完成，`etf_analyst_v2` 使用 ETF 专用指标，`get_etf_fundamentals` 跳过 PE/PB/ROE |
| 6 | **前端市场/品种选择** | 单股分析、自选等 | ✅ 已完成，`SingleAnalysis.vue` 增加「ETF 基金」选项，输入 ETF 代码自动识别 |

### 2.3 数据源能力确认（实施前必做）

| 数据源 | 北交所 | ETF |
|--------|--------|-----|
| **Tushare** | `stock_basic(exchange='BSE')`、`daily` 支持 .BJ | `fund_basic`、`fund_daily` 需查文档 |
| **AKShare** | 已支持 8/4 开头 | 已用于 ETF 列表与历史日线同步 |
| **BaoStock** | 已支持 8/4 开头 | 当前未纳入 ETF 同步链路 |
| **QMT** | 已支持 .BJ | 已确认支持 ETF 列表、实时行情与历史日线，并已接入 ETF 同步 |

---

## 2.4 ETF 存储与工具设计（单股分析相关）

### 2.4.1 为什么 ETF 需要独立集合？

| 数据类型 | 股票 (stock_*) | ETF | 能否复用 |
|----------|----------------|-----|----------|
| **基础信息** | 名称、行业、板块、上市日期、总市值、PE/PB | 名称、规模、费率、跟踪指数、跟踪误差、成立日期 | ❌ 字段差异大 |
| **日线** | OHLCV、涨跌幅、换手率 | OHLCV、涨跌幅、单位净值 | ⚠️ 结构相似，可复用或独立 |
| **财务/基本面** | PE、PB、ROE、营收、利润、毛利率、负债率 | **无**；有净值、跟踪误差、规模、费率 | ❌ 完全不可复用 |

**结论**：
- `stock_financial_data` 结构（PE/PB/ROE 等）对 ETF **完全不适用**
- `stock_basic_info` 可加 `security_type: "etf"` 复用，但 ETF 有独特字段（规模、费率、跟踪指数），建议**独立集合**更清晰
- 参考 `UnifiedStockService.collection_map`，港股/美股已用 `stock_basic_info_hk`、`stock_financial_data_hk` 等独立集合

### 2.4.2 建议的 ETF 集合设计

| 集合名 | 用途 | 主要字段 |
|--------|------|----------|
| `etf_basic_info` | ETF 基础信息 | code, name, full_symbol, fund_type, fund_scale, expense_ratio, track_index, track_index_code, list_date, source |
| `etf_daily_quotes` | ETF 日线 | symbol, trade_date, open, high, low, close, volume, amount, unit_nav, accum_nav, data_source |
| `etf_track_data` | 跟踪误差等（可选） | symbol, trade_date, track_error, track_diff, data_source |
| `market_quotes` | 实时行情 | 可复用，ETF 与股票共用（若数据源支持） |

### 2.4.3 需要新增的 ETF 工具

| 工具名 | 用途 | 返回内容 |
|--------|------|----------|
| `get_etf_basic_info` | 获取 ETF 基础信息 | 名称、规模、费率、跟踪指数、成立日期 |
| `get_etf_fundamentals` | 获取 ETF「基本面」 | 单位净值、累计净值、跟踪误差、规模、费率（替代股票的 PE/PB/ROE） |
| `get_etf_daily_quotes` | 获取 ETF 日线 | 与 `get_stock_daily_quotes` 结构类似，可考虑复用或独立 |

### 2.4.4 单股分析流程改造

当前单股分析（`SingleAnalysis.vue` → `analysis` API → 工作流）使用：
- `stock_basic_info`、`stock_daily_quotes`、`stock_financial_data`、`market_quotes`
- 工具：`get_stock_fundamentals_unified`（PE/PB/ROE）

**支持 ETF 后的流程**：

```
用户输入代码 (如 510050)
    │
    ▼
识别证券类型 (StockUtils.identify_security_type)
    │
    ├─ STOCK → 走现有流程
    │           - stock_basic_info / stock_daily_quotes / stock_financial_data
    │           - get_stock_fundamentals_unified
    │
    └─ FUND (ETF) → 走 ETF 分支
                    - etf_basic_info / etf_daily_quotes
                    - get_etf_fundamentals（净值、规模、费率、跟踪误差）
                    - 不调用 get_stock_fundamentals_unified
```

**涉及改造**：
- `UnifiedStockService`：增加 `ETF` 的 `collection_map` 条目
- 分析工作流：根据 `security_type` 选择不同工具链
- 前端单股分析：市场选择增加「ETF」或自动识别 5/15/16 开头

---

## 2.5 提示词与分析流程差异（ETF 必须单独设计）

### 2.5.1 为什么提示词要不一样？

当前**基本面分析师**的提示词（来自 `prompt_templates`、`AGENT_TEMPLATE_SPECIFICATIONS.md`）明确要求：

- 分析 **PE、PB、PEG** 等估值指标
- 分析 **营收增长率、利润增长率**
- 分析 **毛利率、净利率、资产负债率**
- 分析 **行业地位、竞争优势、护城河**
- 给出 **目标价位**（基于估值）

**ETF 没有这些指标**。若沿用股票提示词，LLM 会：
- 调用 `get_stock_fundamentals_unified` 得到空或无关数据
- 被迫编造或误用数据
- 输出无意义的「PE/PB 分析」

ETF 需要的是：
- **净值、累计净值**
- **跟踪误差、跟踪偏离度**
- **规模、流动性**
- **费率（管理费、托管费）**
- **跟踪指数、指数成分**
- **与基准的对比表现**

### 2.5.2 需要区分的提示词

| 分析师/角色 | 股票提示词 | ETF 提示词 |
|------------|------------|------------|
| **基本面分析师** | PE/PB/ROE、估值、财务健康 | **ETF 分析师**：净值、规模、费率、跟踪误差、跟踪指数 |
| **市场分析师** | 技术指标、支撑阻力 | 可复用（价格/净值走势类似） |
| **新闻分析师** | 公司新闻、业绩公告 | 可复用或微调（ETF/指数相关新闻） |
| **板块分析师** | 行业、板块轮动 | 需区分：行业 ETF 可复用，宽基 ETF 侧重指数 |
| **研究员/辩论** | 引用基本面估值 | 引用 ETF 指标（净值、跟踪误差等） |
| **风险分析师** | 财务风险、估值风险 | 跟踪误差风险、流动性风险、规模萎缩风险 |

### 2.5.3 分析流程要不一样

当前单股分析流程（`v2_stock_analysis_workflow`）：

```
并行分析师 → 基本面分析师(get_stock_fundamentals_unified) 
           → 市场分析师 
           → 新闻分析师 
           → ... 
           → 研究员辩论 
           → 风险分析师 
           → 最终决策
```

**ETF 分析流程** 需要调整：

| 方案 | 说明 |
|------|------|
| **方案 A：分支替换** | 识别 ETF 后，用「ETF 分析师」节点替换「基本面分析师」，其余节点保留 |
| **方案 B：独立工作流** | 新建 `v2_etf_analysis_workflow`，专门用于 ETF，节点和连线与股票流程不同 |
| **方案 C：条件节点** | 在「基本面分析师」前加条件分支：股票 → 基本面分析师，ETF → ETF 分析师 |

**推荐方案 A 或 B**：逻辑清晰，避免同一流程内大量 if-else。

### 2.5.4 需要新增/改造的内容

| 类型 | 股票现有 | ETF 需要 |
|------|----------|----------|
| **Agent 定义** | `fundamentals_analyst` | `etf_analyst`（或 `fund_analyst`） |
| **工具** | `get_stock_fundamentals_unified` | `get_etf_fundamentals` |
| **提示词模板** | `fundamentals_analyst_v2` 等 | `etf_analyst_default` 等（存 `prompt_templates`） |
| **工作流** | `v2_stock_analysis_workflow` | `v2_etf_analysis_workflow` 或动态替换节点 |
| **输出字段** | `fundamentals_report` | `etf_report` 或复用 `fundamentals_report` 存不同结构 |

### 2.5.5 ETF 分析师提示词示例（需入库）

```markdown
**系统提示词**：
你是专业的 ETF 分析师。ETF 是跟踪指数的基金，没有 PE/PB/ROE 等个股估值指标。

分析目标：{etf_name}（{ticker}）
分析日期：{current_date}

核心职责：
1. 分析净值走势与跟踪指数表现
2. 评估跟踪误差和跟踪偏离度
3. 分析规模、流动性、费率
4. 评估与基准的对比表现

必须调用 get_etf_fundamentals 获取真实数据。
禁止使用 PE/PB/ROE 等个股指标分析 ETF。
```

---

## 2.6 界面与定时任务

### 2.6.1 是否需要单独的 ETF 分析界面？

**建议：不单独做页面，复用「单股分析」并扩展**

| 方案 | 说明 |
|------|------|
| **方案 A：统一界面（推荐）** | 在现有「单股分析」页面增加「ETF」市场选项，用户选 ETF 或输入 5/15/16 开头代码时自动识别，后端路由到 ETF 工作流 |
| **方案 B：单独页面** | 新增「ETF 分析」菜单和页面，与「单股分析」并列 |

**推荐方案 A**：
- 入口统一，用户只需输入代码
- 代码 510050 等可自动识别为 ETF，无需单独选择
- 报告结构不同，但可在同一页面用不同展示逻辑处理

**实现要点**：
- 市场选择器增加：`🇫🇺 ETF 基金`（5/15/16 开头）
- 输入 510050、159919 等时，可自动识别并切换为 ETF
- 提交时根据 `market` 或 `security_type` 选择 `v2_stock_analysis` 或 `v2_etf_analysis`

### 2.6.2 定时分析任务是否需要支持 ETF？

**需要支持**。股票关注列表分组中可能包含 ETF（如 510050、159919），定时任务应按标的类型选择对应工作流。

**改造点**：

| 位置 | 改动 |
|------|------|
| `AnalysisTaskType` | 新增 `ETF_ANALYSIS = "etf_analysis"` |
| `workflow_registry` | 注册 `ETF_ANALYSIS` → `v2_etf_analysis_workflow` |
| `analyze_user_watchlist_batch` | 对每个 code 调用 `StockUtils.identify_security_type()`，若为 `FUND` 则用 `ETF_ANALYSIS` |
| `task_analysis_service` | 根据 `task_type` 选择工作流（已有逻辑，只需支持新类型） |

**流程示意**：
```
定时任务触发 → 获取分组 stock_codes
  → 遍历每个 code
    → identify_security_type(code)
    → FUND → create_task(ETF_ANALYSIS, v2_etf_analysis_workflow)
    → STOCK → create_task(STOCK_ANALYSIS, v2_stock_analysis_workflow)
```

---

## 3. 实施建议

### 阶段一：北交所（1–2 天）

1. 修改 Tushare `get_stock_list`，将 `exchange` 扩展为 `SSE,SZSE,BSE`
2. 修改 `symbol_utils.py`，增加 `.BJ` 支持
3. 验证北交所股票从基础信息到日线、财务的完整链路
4. 更新 Skill 生成规范，说明北交所代码格式

### 阶段二：ETF 存储与同步（3–5 天）

1. 调研 Tushare `fund_basic`/`fund_daily`、AKShare ETF 接口（列表、日线、净值）  ✅ 已完成并接入同步实现
2. **新建集合**：`etf_basic_info`、`etf_daily_quotes`（参考 2.4.2 节）  ✅ 已完成
3. 实现 ETF 同步服务（`etf_sync_service` 或扩展现有 sync）  ✅ 已完成
4. 解除 `planned_analysis` 对 ETF 的阻止（可先做开关）  ✅ 已完成

### 阶段三：ETF 工具、提示词与工作流（4–5 天）

1. **新增 ETF 工具**：`get_etf_basic_info`、`get_etf_fundamentals`（参考 2.4.3 节）  ✅ 已完成，`get_etf_fundamentals` 已实现，支持本地+在线多源回退
2. **UnifiedStockService**：增加 `ETF` 的 `collection_map`  ✅ 已完成
3. **新增 ETF 分析师**：`etf_analyst` Agent，绑定 `get_etf_fundamentals`  ✅ 已完成，`etf_analyst_v2` 已实现
4. **ETF 提示词模板**：入库 `prompt_templates`，分析净值、规模、费率、跟踪误差（参考 2.5.5 节）  ✅ 已完成，`etf_workflow_prompt_template_service.py` 覆盖全部 7 个 Agent
5. **分析流程分支**：方案 A 用 ETF 分析师替换基本面分析师，或方案 B 新建 `v2_etf_analysis_workflow`  ✅ 已完成，ETF 专用工作流已存在
6. **研究员/风险提示词**：调整引用逻辑，ETF 分支引用 `etf_report` 而非 `fundamentals_report`  ✅ 已完成，`research_manager_v2` 已做 ETF 工作流兜底
7. 前端单股分析：市场选择增加「ETF」或自动识别 5/15/16 开头  ✅ 已完成

### 阶段四：界面与定时任务（1–2 天）

1. **单股分析页面**：市场选择器增加「ETF」，输入 5/15/16 开头时自动识别  ✅ 已完成
2. **提交逻辑**：根据 `market` 或 `security_type` 选择 `v2_stock_analysis` 或 `v2_etf_analysis`  ✅ 已完成
3. **定时分析**：`AnalysisTaskType` 新增 `ETF_ANALYSIS`，`workflow_registry` 注册 ETF 工作流  ✅ 已完成
4. **watchlist_analysis_task**：遍历 code 时调用 `identify_security_type`，按类型选择 `STOCK_ANALYSIS` 或 `ETF_ANALYSIS`  ✅ 已完成
5. **报告展示**：TaskDetailDialog、ReportDetail 等支持 ETF 报告结构（净值、跟踪误差等）  ✅ 已完成

### 阶段五：Skill 生成与前端（1–2 天）

1. 在 Skill 生成的需求分析中，识别「北交所」「ETF」相关需求
2. 代码生成时注入正确的数据源调用（含 ETF 专用接口、`local_data.get_etf_*`）

---

## 4. 代码改动示例

### 4.1 Tushare get_stock_list 包含北交所

```python
# tradingagents/dataflows/providers/china/tushare.py
if market == "CN":
    params['exchange'] = 'SSE,SZSE,BSE'  # 沪深 + 北交所
```

### 4.2 symbol_utils 支持 .BJ

```python
# core/tools/external/symbol_utils.py
def normalize_a_share_symbol(symbol: str) -> str:
    # ...
    for prefix in ("SH", "SZ", "SS", "BJ"):
        if s.startswith(prefix):
            s = s[len(prefix):]
            break
    for suffix in (".SH", ".SZ", ".SS", ".BJ"):
        if s.endswith(suffix):
            s = s[:-len(suffix)]
            break
    # ...
```

### 4.3 解除 ETF 阻止（可选：配置开关）

```python
# app/services/planned_analysis_service.py
# 方案 A：直接移除 ETF 关键词
# 方案 B：增加配置项 ENABLE_ETF_ANALYSIS，为 True 时跳过 ETF 检测
```

---

## 5. 风险与注意事项

1. **北交所数据量**：北交所股票数量相对较少，对同步性能影响小
2. **Tushare 权限**：部分接口可能需要更高积分，需确认 BSE 数据权限
3. **ETF 分析差异**：需在提示词/工具中明确「ETF 无 PE/PB」，避免 LLM 误用
4. **向后兼容**：现有 A 股分析流程应不受影响，北交所和 ETF 为增量支持

---

## 6. 参考资料

- [Tushare stock_basic](https://tushare.pro/document/2?doc_id=25) - exchange 含 BSE
- [stock_code_validation.md](../../integration/data-sources/stock_code_validation.md) - 北交所代码规则
- [tradingagents/utils/stock_utils.py](../../../tradingagents/utils/stock_utils.py) - SecurityType.FUND 识别逻辑
