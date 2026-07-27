# AlphaGuard 真实数据准备方案

## 1. 目的与边界

本文用于把 AlphaGuard 已完成的代码链路接到可追溯的真实数据。数据准备必须
create-only 或幂等，必须保留来源、截止时间和版本，不能用测试 fixture、未来数据、
当前值回填历史，也不能因为数据缺失而降低 DataQualityGate 标准。

本阶段不改变因子、策略、Prompt、模型、HardRisk、撮合、费用或 Champion，不做
全市场自动推荐，不启用 PAPER_CHALLENGER，不连接真实券商。

## 2. 2026-07-27 真实基线

数据库为 `tradingagentscn_v0_banana`。当前 `stock_basic_info=5533`，它只证明股票
基础列表存在，不是决策证据。以下 AlphaGuard 数据集合均为 0：

| 数据项 | 当前来源能力 | 目标存储 | 时间字段 | 版本要求 | 当前覆盖 | 快照可稳定引用 |
| --- | --- | --- | --- | --- | --- | --- |
| 交易日历 | AKShare `tool_trade_date_hist_sina` 只读探测成功 | `trading_calendar` | `session_date` / `trade_date` | `calendar_version`、来源哈希、`published_at` | 持久化 0；探测范围 1990-12-19 至 2026-12-31 | 否 |
| 原始日线 | AKShare/现有历史同步器；本次远端连接被关闭 | `stock_daily_quotes` | `trade_date` | 原始模式、来源版本、批次哈希 | 0 标的、0 记录 | 否 |
| QFQ 日线 | BaoStock 只读 `adjustflag=2` 探测成功；现有保存器未写显式 QFQ 合约 | `stock_daily_quotes` | `trade_date` | `price_adjustment_mode=QFQ`、`price_data_version`、调整后 OHLC、稳定 `data_ref` | 0 标的、0 记录 | 否 |
| 沪深 300 | BaoStock 只读探测成功；AKShare 本次连接失败 | `stock_daily_quotes` | `trade_date` | 与标的一致的原始/QFQ版本 | 持久化 0；只读探测得到 2026-07-01 至 2026-07-24 共 18 根日线 | 否 |
| 市场环境 | 当前无真实生产器 | `ag_market_contexts` | `trade_date`、`as_of` | 市场环境规则版本、输入哈希 | 0 | 否 |
| 财务数据 | 现有 Tushare/AKShare/BaoStock 同步入口 | `stock_financial_data` | `report_period`、真实披露日 | 数据源版本、披露版本、输入哈希 | 0 标的、0 记录 | 否 |
| 财务披露日期 | Tushare适配字段较完整；当前 token 校验失败 | 随财务文档 | `f_ann_date` / `ann_date` / `publish_date` | 不允许用报告期或抓取时间代替 | 0 | 否 |
| 新闻 | 现有 AKShare/Tushare 入口；无自选标的可同步 | `stock_news` | `publish_time` | 来源、抓取批次、内容哈希 | 0 | 否 |
| 公告 | 当前无已验证的独立生产链 | `stock_announcements` | `announcement_time` | 公告 ID、来源、内容哈希 | 0 | 否 |
| 行业历史映射 | `stock_basic_info.industry` 只有当前值，不能代表历史 | `stock_industry_history` | `effective_from` / `effective_to` | 分类体系和映射版本 | 0 | 否 |

额外状态：

- Tushare 当前 token 无效，不能作为可用源。
- AKShare 交易日历接口可达；股票和指数日线接口本次返回远端断开，必须按失败处理。
- BaoStock 可登录且可读取 QFQ 日线，但现有 `HistoricalDataService` 只保存普通
  OHLC/`adjustflag`，未满足 `AdjustedPriceResolver` 的显式版本合约。禁止直接把这些
  行宣称为 AlphaGuard QFQ。
- `ag_evidence_snapshots`、`ag_quant_proposals`、`ag_eval_subjects` 均为 0。

## 3. 最低数据范围

1. 交易日历：至少覆盖全部价格历史、当前交易日以及订单/评价需要的未来已公布交易日。
2. 标的和沪深 300 日线：每个用户明确选择的候选至少 756 个连续交易时段；这是现有
   三年估值分位因子的最大固定回看窗口。缺口不能用自然日或插值补齐。
3. 原始与 QFQ 日线必须来自同一可审计批次，日期集合、停牌语义和成交量单位需可核对。
4. 财务：至少包含最新已披露报告及同比所需的上一年同报告期；每条必须有真实披露日。
5. 新闻和公告：覆盖快照配置的截止窗口；只允许 `publish_time <= cutoff_at`。
6. 市场环境：每个决策交易日必须有沪深 300、涨跌家数、行业扩散等现有 Regime
   输入；缺字段不能描述成中性市场。
7. 行业历史：覆盖候选和评价期间，并能按交易日解析当时有效行业。

## 4. 同步顺序

1. 验证 MongoDB/Redis、AlphaGuard 索引、Champion 和安全不变量。
2. 建立版本化交易日历并验证下一交易日计算。
3. 复核股票代码、市场、上市日期和当前基础信息。
4. 同步用户明确选择的 3～5 个标的和沪深 300 原始日线。
5. 从声明了复权口径的数据源同步 QFQ 日线，生成不可变 `price_data_version`。
6. 同步财务报表和真实披露日期。
7. 同步新闻与公告，分别保存，不能把普通新闻冒充公告。
8. 生成版本化市场环境和历史行业映射。
9. 对每个集合执行质量审计；只有全部关键项通过才创建 EvidenceSnapshot。
10. Snapshot 成功后依次运行 Factor、Regime、Strategy 和 QuantProposal；任何缺失
    继续返回 NOT_READY/INSUFFICIENT_DATA。

## 5. 版本生成和存储约束

- 版本内容至少包含：数据源、接口/规则版本、复权模式、批次截止时间、字段模式版本和
  规范化内容 SHA-256。
- 同一业务身份同一内容允许复用；同一身份不同内容必须产生新版本或完整性冲突，不能
  静默覆盖。
- 原始行保留来源 ID；EvidenceSnapshot 的 `raw_refs` 只引用已持久化的稳定 ID。
- 财务按披露版本保存，修订报表不能覆盖旧披露版本。
- 新闻和公告使用来源 ID 或规范化内容哈希去重，保存真实发布时间。
- 交易日历保存其发布/抓取截止时间；不能用自然日 `+1` 计算 T+1。
- 当前历史日线唯一索引未包含复权模式和数据版本；在该存储契约补齐并测试前，QFQ
  同步保持 NOT_READY。

## 6. 数据质量规则

- OHLC 均为有限正数，`low <= open/close <= high`，成交量与成交额非负且单位明确。
- 目标交易日价格必须精确存在；不得用“最近一条”代替。
- QFQ 必须同时具有调整后 OHLC、`price_adjustment_mode=QFQ`、
  `price_data_version` 和稳定 `data_ref`。
- 标的与沪深 300 的交易日必须可对齐；混合版本或重复冲突日期直接阻断。
- 财务必须同时有报告期和披露日，披露日晚于快照截止时间的记录必须排除。
- 新闻、公告、行业和市场环境均不得晚于对应快照 cutoff。
- 停牌、ST、涨跌停与市场规则缺失时，执行链必须 SUSPEND，不得推断可交易。
- 每次同步记录总数、插入、复用、冲突、失败、开始/结束时间和批次哈希。

## 7. 失败重试

- 同步任务使用持久化 job/run 记录，不以内存队列作为唯一依据。
- 网络和限流错误允许有上限的退避重试；认证失败、Schema错误和同身份内容冲突不自动
  重试覆盖。
- 部分批次失败保留成功和失败明细，但该批次不能标记完整。
- 重试必须复用相同输入身份并生成新的 attempt，不能覆盖原错误。
- 达到失败上限后进入明确 FAILED/DEAD_LETTER 并告警；不得继续创建 Snapshot。

## 8. Snapshot 引用方式

1. 先按 `user_id + symbol + market + trade_date` 固定全部来源集合和截止时间。
2. 将价格、沪深 300、财务、新闻、公告、市场环境、交易日历、账户证据转换为
   `collection:stable_id[:date]` 引用。
3. 运行 DataQualityGate，保存独立报告。
4. 只在报告非 FAIL 时创建不可变 EvidenceSnapshot 和 SHA-256。
5. SnapshotDataResolver 只能解析这些引用，不查询最新行情或外部接口。

## 9. 验证命令

```bash
.venv/bin/python scripts/alphaguard_readiness_report.py --json
.venv/bin/python scripts/verify_champion_assignments.py
.venv/bin/python scripts/init_alphaguard_paper_indexes.py
curl -fsS http://127.0.0.1:8000/health/ready
docker compose ps
docker compose logs --since=10m backend queue-worker analysis-worker
npm --prefix frontend run type-check -- --pretty false
git diff --check
```

每次受控同步后还应按目标集合核对：总记录数、distinct symbol、最早/最晚交易日、
字段缺失率、版本数、同身份冲突数、最后成功同步时间和可解析 raw_refs 数。计数为 0
或版本字段缺失时保持 NOT_READY。

## 10. 当前不支持或尚未就绪

- 版本化交易日历持久化任务尚未注册。
- 显式版本化 QFQ 写入契约尚未接入现有 HistoricalDataService。
- 沪深 300、市场环境和历史行业映射尚无通过完整性验证的生产同步器。
- 公告尚无独立且稳定的持久化生产链。
- Tushare 认证不可用；AKShare 日线端点本次不可用。
- 没有管理员用户，也没有用户明确选择的 3～5 个候选代码。

因此当前 `DATA_READY=false`。上述事实不得通过手工改状态、测试 fixture 或伪造引用
变为 true。
