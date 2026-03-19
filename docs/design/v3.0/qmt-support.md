# QMT（迅投 MiniQMT）数据源支持

## 📋 文档信息

| 项目 | 内容 |
|------|------|
| 版本 | v1.1 |
| 状态 | 已实现并持续扩展 |
| 日期 | 2026-03-19 |
| 目标 | 支持迅投 QMT/MiniQMT 量化终端作为数据源，获取股票列表、行情、K 线、财务数据与 ETF 数据 |

---

## 1. 概述

QMT（迅投 MiniQMT）是券商量化终端，通过 `xtquant.xtdata` 连接本地 MiniQMT 客户端获取行情数据。作为多数据源之一，可与 Tushare、AKShare、BaoStock 等按优先级协同工作。

**前置条件**：
- MiniQMT 客户端需已启动（仅 Windows 支持）
- 获取行情数据不需要登录券商账户
- 新闻不支持，统一使用 AKShare 数据源

---

## 2. 2026-03 最新落地

本轮已补齐 QMT 在系统中的一等数据源能力，重点包括：

1. QMT 已接入统一配置、配置桥接、数据源测试、系统配置校验与前端数据源配置弹窗。
2. QMT 已新增 5 类调度任务：基础信息、实时行情、历史数据、财务数据、状态检查。
3. QMT 历史数据已接入 `stock_daily_quotes` 入库链路，财务数据已接入 `stock_financial_data` 入库链路。
4. QMT 适配器已支持 `xtdatacenter` 可选初始化、板块数据预下载、历史数据自动补齐、财务数据自动下载。
5. QMT 已接入 ETF 同步链路，可获取 ETF 列表并参与 ETF 基础信息与 ETF 日线同步。
6. 已新增 QMT 原生分析模式：当 Tushare 不可用或显式指定 QMT 时，大盘分析师与板块分析师会自动切换到 QMT 工具与 QMT 口径提示词。

---

## 3. 已实现能力

| 模块 | 实现位置 | 说明 |
|------|----------|------|
| **数据源适配器** | `app/services/data_sources/qmt_adapter.py` | QMTAdapter，实现 DataSourceAdapter 接口 |
| **同步服务** | `app/worker/qmt_sync_service.py` | QMTSyncService，支持股票基础信息、实时行情、历史数据、财务数据、状态检查 |
| **ETF 同步** | `app/worker/etf_sync_service.py` | QMT 已加入 ETF 基础信息与 ETF 日线同步映射 |
| **定时任务** | `app/main.py` | 已注册 QMT 基础信息、行情、历史、财务、状态检查 5 个 CRON 任务 |
| **配置** | `app/core/config.py` | 新增统一开关、CRON、批量大小、数据目录、端口、自动下载等完整运行时配置 |
| **配置桥接** | `app/core/config_bridge.py`、`app/core/unified_config.py` | 支持 QMT token 与 config_params 桥接到运行时环境 |
| **数据源注册** | `app/services/data_sources/manager.py` | 与 Tushare、AKShare 等并列注册 |
| **多数据源同步** | `app/routers/stock_sync.py`、`app/services/config_service.py` | 支持 data_source=qmt 的同步与连通性测试 |
| **前端配置** | `frontend/src/views/Settings/components/DataSourceConfigDialog.vue` | 设置页已可直接配置 QMT 数据源 |

---

## 4. 数据能力

| 能力 | 说明 |
|------|------|
| 股票列表 | 通过沪深 A 股板块获取，支持北交所（8/4/92 开头 → .BJ） |
| ETF 列表 | 通过 ETF/场内基金板块 + 代码前缀过滤获取，支持沪深 ETF |
| 日线行情 | `get_market_data_ex`，并可在读取前自动触发历史数据下载 |
| 实时行情 | get_full_tick |
| 财务数据 | `download_financial_data`、`get_financial_data`，并支持同步入库 |
| 历史数据入库 | 通过 `HistoricalDataService` 写入 `stock_daily_quotes` |
| 财务数据入库 | 通过 `FinancialDataService` 写入 `stock_financial_data` |
| 新闻 | 不支持，由 DataSourceManager 回退到 AKShare |

---

## 5. QMT 分析模式

QMT 当前不仅可用于同步，也可作为大盘/板块分析的运行时数据源。

### 5.1 已接入的分析师

| 分析师 | QMT 工具 | 分析口径 |
|------|----------|----------|
| `index_analyst_v2` | `get_market_overview_qmt` | 指数趋势、市场扩散、成交活跃度、风格切换、盘面结构 |
| `sector_analyst_v2` | `get_sector_analysis_qmt` | 行业内强弱、龙头带动、扩散度、活跃度、本地行业映射 |

### 5.2 模式选择逻辑

系统会优先读取运行态状态中的以下字段决定期望数据源：

- `analysis_data_source`
- `preferred_data_source`
- `market_data_source`
- `data_source`

若显式要求 `qmt`，且 QMT 可用，则走 QMT 模式；若要求 `tushare` 且 Tushare 可用，则走 Tushare 模式；若未指定，则优先 Tushare，不可用时回退到 QMT。

### 5.3 QMT 模式特征

1. 会切换到专门的 QMT 工具，而不是复用 Tushare 风格工具。
2. 会给分析师追加 QMT 模式提示词约束，避免继续索取北向资金、两融、涨跌停官方统计、同花顺板块资金流等口径。
3. 板块分析会明确区分“QMT 行情”和“本地 `stock_basic_info` 行业映射”两个数据来源。
4. QMT 模式强调盘面结构分析，不尝试伪造官方统计指标。

---

## 6. 关键配置项

常用配置项如下：

- `QMT_UNIFIED_ENABLED`
- `QMT_BASIC_INFO_SYNC_ENABLED` / `QMT_BASIC_INFO_SYNC_CRON`
- `QMT_QUOTES_SYNC_ENABLED` / `QMT_QUOTES_SYNC_CRON`
- `QMT_HISTORICAL_SYNC_ENABLED` / `QMT_HISTORICAL_SYNC_CRON`
- `QMT_FINANCIAL_SYNC_ENABLED` / `QMT_FINANCIAL_SYNC_CRON`
- `QMT_STATUS_CHECK_ENABLED` / `QMT_STATUS_CHECK_CRON`
- `QMT_TOKEN`
- `QMT_DATA_DIR`
- `QMT_LISTEN_PORT` / `QMT_LISTEN_PORT_RANGE`
- `QMT_INIT_MARKETS`
- `QMT_ALLOW_OPTIMIZE_ADDRESSES`
- `QMT_KLINE_MIRROR_MARKETS` / `QMT_KLINE_MIRROR_ENABLED`
- `QMT_AUTO_DOWNLOAD_HISTORY`
- `QMT_AUTO_DOWNLOAD_FINANCIAL`
- `QMT_AUTO_DOWNLOAD_SECTOR`
- `QMT_HISTORY_START_TIME`
- `QMT_HISTORICAL_SYNC_DAYS`
- `QMT_HISTORICAL_BATCH_SIZE`
- `QMT_FINANCIAL_BATCH_SIZE`

---

## 7. 代码格式转换

- 6 位代码 ↔ xtdata 格式：`000001.SZ`、`600000.SH`、`920985.BJ`
- 北交所：43/83/87/89/92 开头 → `.BJ`
- ETF：50/51/52/56/58 开头 → `.SH`，15/16/18 开头 → `.SZ`

---

## 8. 启用方式

1. 安装 xtquant（随 MiniQMT 安装）
2. 启动 MiniQMT 客户端
3. 在 `.env` 或系统配置中设置 `QMT_UNIFIED_ENABLED=true`
4. 按需配置 `QMT_DATA_DIR`、`QMT_TOKEN`、`QMT_LISTEN_PORT_RANGE`、`QMT_INIT_MARKETS`
5. 如需自动补历史或财务下载，配置 `QMT_AUTO_DOWNLOAD_HISTORY=true`、`QMT_AUTO_DOWNLOAD_FINANCIAL=true`
6. 定时任务将按 CRON 执行；也可通过多数据源配置页进行测试，或通过调度任务手动触发

---

## 9. 当前边界

1. QMT ETF 数据同步已落地；ETF 分析工作流已存在，但 ETF 能力成熟度仍弱于普通股票主流程。
2. QMT 分析模式目前仅覆盖大盘分析与板块分析，尚未覆盖更完整的市场统计替代口径。
3. 文档所述能力目前已完成代码接入，但尚未在所有部署环境完成 MiniQMT 实盘级回归验证。
4. 新闻与公告仍不走 QMT，继续由 AKShare 等源补位。
