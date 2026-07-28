# AlphaGuard 真实数据准备方案

## 1. 目的与边界

本文用于把 AlphaGuard 已完成的代码链路接到可追溯的真实数据。数据准备必须
create-only 或幂等，必须保留来源、截止时间和版本，不能用测试 fixture、未来数据、
当前值回填历史，也不能因为数据缺失而降低 DataQualityGate 标准。

本阶段不改变因子、策略、Prompt、模型、HardRisk、撮合、费用或 Champion，不做
全市场自动推荐，不启用 PAPER_CHALLENGER，不连接真实券商。

## 2. 2026-07-27 真实基线

数据库为 `tradingagentscn_v0_banana`。`stock_basic_info=5533`，用户明确选择：
`600519`、`601318`、`000333`、`002594`、`300750`。2026-07-27 已使用
BaoStock 00.9.30 和 AKShare 1.18.78 完成受控版本化同步：

| 数据项 | 当前来源能力 | 目标存储 | 时间字段 | 版本要求 | 当前覆盖 | 快照可稳定引用 |
| --- | --- | --- | --- | --- | --- | --- |
| 交易日历 | AKShare，BaoStock 作为合法备用 | `trading_calendar` | `session_date`、`as_of` | manifest SHA-256、逐行内容 hash | 2557 条，2020-01-01 至 2026-12-31 | 是 |
| 原始日线 | BaoStock `adjustflag=3` | `stock_daily_quotes` | `trade_date`、`timestamp` | RAW 版本、来源响应 hash | 5 标的各 862 根，2023-01-03 至 2026-07-27 | 是 |
| QFQ 日线 | BaoStock `adjustflag=2` | `stock_daily_quotes` | `trade_date`、`timestamp` | `price_adjustment_mode=QFQ`、调整后 OHLC、稳定 `data_ref` | 5 标的各 862 根，与 RAW 日期完全重合 | 是 |
| 沪深 300 | BaoStock `sh.000300` | `stock_daily_quotes` | `trade_date`、`timestamp` | `INDEX_UNADJUSTED_EQUIVALENT`、稳定版本 | 862 根，2023-01-03 至 2026-07-27 | 是 |
| 市场环境 | 当前无真实生产器 | `ag_market_contexts` | `trade_date`、`as_of` | 市场环境规则版本、输入哈希 | 0 | 否 |
| 财务数据 | BaoStock profit data | `stock_financial_data` | `report_period`、`published_at` | 来源版本、披露身份、内容 hash | 每标的 13–14 期，共 66 条 | 是 |
| 财务披露日期 | BaoStock `pubDate` | 随财务文档 | `f_ann_date` / `ann_date` / `published_at` | 不用报告期或抓取时间代替 | 66/66 有实际披露日 | 是 |
| 新闻 | AKShare `stock_news_em` | `stock_news` | `publish_time`、`collected_at` | 来源 ID、内容 hash | 每标的 10–12 条，共 53 条 | 是 |
| 公告 | AKShare CNInfo disclosure | `stock_announcements` | `announcement_time`、`collected_at` | CNInfo ID/内容 hash | 每标的 297–722 条，共 2716 条 | 是 |
| 行业历史映射 | BaoStock 当前 CSRC 分类 | `stock_industry_history` | `effective_from` / `effective_to` | 分类体系和映射版本 | 5 条，均为 2026-07-27 `CURRENT_ONLY` | 仅当日后可引用 |

额外状态：

- Tushare 当前 token 无效，未使用。
- AKShare 某些行情接口仍会被远端断开，因此价格只使用已验证 BaoStock 接口；
  AKShare 只负责已验证的日历、新闻和 CNInfo 公告能力。
- `scripts/sync_alphaguard_real_data.py` 默认 dry-run，候选域必须逐个传入用户指定
  `--symbol`，不会抓取或写入全市场候选。
- 所有 7150 条候选业务记录（不含复用的沪深 300）和 2557 条日历记录均具有
  `ref_id`、`data_version`、`content_hash` 和确定时间字段；重复 `ref_id=0`。
- 已创建 1 个真实 EvidenceSnapshot、21 个 FactorResult、1 个 RegimeResult、
  2 个 QuantProposal、2 个 EvaluationSubject 和 8 个 PENDING HorizonLabel。

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
- 真实激活行使用 sparse 唯一 `ref_id`；旧历史行不被覆盖。AdjustedPriceResolver
  只接受显式 QFQ 版本，混合版本继续 fail-closed。

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
.venv/bin/python scripts/sync_alphaguard_real_data.py --domain TRADING_CALENDAR --start 2020-01-01 --end 2026-12-31
.venv/bin/python scripts/sync_alphaguard_real_data.py --domain CANDIDATE_REAL_DATA --start 2023-01-01 --end 2026-07-24 --symbol 600519 --symbol 601318 --symbol 000333 --symbol 002594 --symbol 300750
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

- 市场环境仍为 0，Regime 必须返回 `INSUFFICIENT_DATA`，不得默认
  `RANGE_WEAK`。
- 行业只有 2026-07-27 当前映射；Operations 将其报告为 `PARTIAL /
  INDUSTRY_HISTORY_CURRENT_ONLY`，不得用于之前日期。
- 本地管理员和三个 MVP 自动账户已按现有认证/账户规则初始化；PAPER_CHALLENGER
  保持 0。
- 最近完整价格日为 2026-07-27；Champion 生效日已由持久化日历确认，首个正式快照
  已创建并通过不可变哈希回读验证。
- Tushare 认证不可用；AKShare 行情端点不作为当前价格源。

因此当前 `DATA_READY=false`、`PAPER_READY=true`、`EVALUATION_READY=false`。
这三个值只能随真实对象和真实运行证据变化，不能手工修改。

## 11. 首次真实激活对象

```text
admin user_id=6a6747f8bc01c5e4b2be6a45
candidate count=5
snapshot_id=8096af28-88aa-4eb1-b51e-dc6b3852debc
snapshot hash verified=true
FactorResult=21
Regime=INSUFFICIENT_DATA / missing:market_context
QuantProposal=2 / REJECTED + INSUFFICIENT_DATA
EvaluationSubject=2
HorizonLabel=8 PENDING
Outbox=Intent=Order=Fill=0
```

这次真实链验证了缺少市场环境时 fail-closed；后续数据准备应补齐版本化
`ag_market_contexts` 和历史行业映射，而不是修改 Regime 或策略阈值。

## 12. Historical Backfill 数据接入（2026-07-27）

历史研究回放没有复用生产 `ag_market_contexts` 身份，而是新增 create-only 的
`ag_research_market_context_sources/ag_research_market_contexts`：

- 持久化日历在 2026-01-01 至 2026-06-30 实际选出 25 个每周最后开市日；
- 第一轮固定为 5 个用户指定标的，共 125 个计划样本；
- 五只标的 QFQ/RAW 和沪深300均覆盖 2023-01-03 至 2026-07-27，各 862 根；
- 股票使用 `QFQ`，沪深300使用明确的 `INDEX_UNADJUSTED_EQUIVALENT`，评价解析器只对
  指数基准接受该等价口径；
- BaoStock 每个抽样日的实际沪深 A 股 universe 用于上涨/下跌、成交额和高低点，不用
  五只候选替代全市场；
- 十个历史交易所行业指数用于行业扩散，current-only 的五条股票行业映射不参与历史；
- 股票日线没有显式 `limit_up_price/limit_down_price`，因此研究影子执行明确返回
  `INSUFFICIENT_DATA`，不推算板块涨跌停边界。

历史 MarketContext 同步脚本默认 dry-run，真实 execute 使用 20 秒 socket 超时、三次重试、
逐阶段进度、源响应哈希、归一化记录和 BSON 15MB 上限检查。中断前不会写半成品；同一
日期/Provider/版本重复执行复用，内容变化则完整性冲突。

## 13. Historical Backfill 完成状态（2026-07-27）

- 研究 MarketContext：25/25 READY，实际 A 股 universe 并集 5,216，Provider 失败 0；
- canonical run `9b921ffa-71a5-578b-85e8-252b2f9cfca9`：125/125 完成；
- 125 个研究 Snapshot、2,625 个 FactorResult、125 个 RegimeResult、250 个 Proposal；
- 250 个研究 EvaluationSubject，1D/5D/10D 全成熟，20D 为 240 成熟和 10 PENDING；
- 缺失历史新闻和 current-only 行业映射仅产生 WARN/null，没有用未来数据回填；
- 研究数据没有写入 `ag_market_contexts`，所以生产 `DATA_READY=false` 继续正确；
- 生产数据补齐顺序不变：正式 MarketContext 与 point-in-time 行业历史仍需合法 Provider
  和版本化同步，不能从研究集合复制或人工改 readiness。

三个 0% 覆盖财务因子和 `revenue_yoy_v1` 的 10.4% 缺失已记录为数据限制，不通过修改
因子公式处理。详细结果见 `docs/research/ALPHAGUARD_BACKFILL_RESULTS.md`。
