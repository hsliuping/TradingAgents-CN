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

## 14. Production Data Completion（2026-07-28）

本阶段没有从 `ag_research_*` 复制生产对象，也没有修改 Factor、Regime、Strategy、
Prompt、模型、Consensus、HardRisk、Matching、Fee 或 Champion。新增生产数据身份如下：

| 数据域 | 生产集合 | 真实来源 | 时间/版本身份 |
| --- | --- | --- | --- |
| 证券资料原始审计 | `ag_security_master_sources` | BaoStock `query_stock_basic` 00.9.30 | `available_at/collected_at` + provider raw hash + normalization version |
| 证券资料解析目标 | 现有 `stock_basic_info` | 同上 | `security_master_source_ref/security_master_data_version/content_hash` |
| 全市场环境原始审计 | `ag_market_context_sources` | BaoStock 全 A 股历史截面、十个行业指数 + 正式沪深300 | trade_date/provider/normalization/content hash |
| 全市场环境 | `ag_market_contexts` | 独立生产抓取计算 | trade_date/data_version/calculation_version/content hash |
| 每日证券交易状态 | `ag_security_trading_statuses` | 正式 QFQ 日线 + 证券资料 + 版本化规则 | symbol/trade_date/price version/security-master version/rule version |

### 14.1 MarketContext 字段映射

| Regime 输入 | 来源/计算 |
| --- | --- |
| 指数收盘、MA20、MA60 | 同一 `price_data_version` 的正式 `stock_daily_quotes:000300` |
| MA20 斜率 | 当前 MA20 相对五个交易日前 MA20，`production-market-context-calculation-v1.1` |
| 20日波动率 | 正式沪深300连续收盘收益标准差年化 |
| 市场成交额/变化 | BaoStock 全 A 股当日成交额与前20个交易日均值 |
| 上涨/下跌/市场宽度 | 当日实际 A 股 universe；不使用五只候选或沪深300替代 |
| 新高/新低 | 每只实际 universe 股票相对前20个交易日 |
| 行业扩散度 | 十个交易所行业指数上涨比例 |
| 极端风险标志 | 只调用现有 Regime 阈值计算，不新增或修改阈值 |

缺失值不填 0，不足数据返回 `INSUFFICIENT_DATA`，不会默认 `RANGE_WEAK`。同一
`trade_date + data_version` 内容相同复用，内容不同返回 `INTEGRITY_CONFLICT`。

### 14.2 涨跌停与交易状态

版本化 `cn-price-limit-rules-v1@1.0.0` 覆盖：

- 沪深主板普通 10%、ST/*ST 5%；
- 创业板、科创板 20%，创业板 2020-08-24 前按旧规则；
- 北交所 30%；
- 2023-04-10 后注册制主板及创业板/科创板/北交所上市初期五个交易日无涨跌幅限制；
- 老主板上市初期、退市整理、身份冲突、未知板块或无涨跌幅限制日均 fail-closed；
- 0.01 元 tick 使用 `ROUND_HALF_UP`，lot size=100；
- 停牌和 ST 使用正式日线显式字段，不根据名称单独猜测。

五只候选的 BaoStock 上市资料已经 dry-run、写入并重复复用：

```text
000333 2013-09-18 美的集团
002594 2011-06-30 比亚迪
300750 2018-06-11 宁德时代
600519 2001-08-27 贵州茅台
601318 2007-03-01 中国平安
```

首次实现发现 MongoDB datetime 只保留毫秒，早期五条审计源使用微秒参与 hash，重复校验
因而被安全阻断。旧五条没有删除；新增
`security-master-normalization-v1.1` 后生成五条可复现版本，现有
`stock_basic_info` 只引用 v1.1。重复 execute 为 `source=REUSED / target=UNCHANGED`。

2026-07-27 五只候选交易状态均为 READY，并已重复复用：

```text
000333 SZSE_MAIN upper/lower=92.95/76.05
002594 SZSE_MAIN upper/lower=101.08/82.70
300750 CHINEXT    upper/lower=459.61/306.41
600519 SSE_MAIN  upper/lower=1427.15/1167.67
601318 SSE_MAIN  upper/lower=59.42/48.62
```

这些记录在 2026-07-28 才完成采集，`available_at` 不会被伪装成 2026-07-27 当时已知；
不会回写历史回放，也不会让四个历史 TRIGGERED 伪装成实际可成交。

### 14.2.1 首条生产 MarketContext 的时序审计

被中断的原同步进程继续在后台完成，没有重新启动。只读结果：

```text
trade_date=2026-07-27
provider=baostock 00.9.30
source_record_count/expected=5201/5201
amount_window=20
sector_records=10
benchmark_records=61
universe/high-low/sector coverage=1/0.9992309171/1
advance/decline/unchanged=4884/268/49
calculation_status=READY
missing_fields=[]
source count=1
context count=1
duplicate identity=0
```

但是该 v1 记录的 `available_at=2026-07-27 15:00`，真实
`collected_at=2026-07-28 11:44`。内容虽然完整，时点不可用于 2026-07-27 决策。记录不
覆盖、不删除；消费者现在同时要求：

```text
calculation_version=current policy version
available_at <= cutoff_at
collected_at <= cutoff_at
```

后续生成版本升级为 policy `1.0.1`、normalization/calculation `v1.1`，其
`available_at=max(trade close, first collected_at)`，source 也保存 `available_at`，时间先
规范到 MongoDB 毫秒精度。遵照“不重复同步”的要求，本阶段没有再次抓取或写入
2026-07-27 v1.1；因此当前版本生产 MarketContext 数量为 0，`DATA_READY` 继续
NOT_READY，而不是因一条时序不合格记录变成 true。

### 14.3 剩余 20D 标签

Canonical run 仍为 `20D CALCULATED=240 / PENDING=10`。十条 PENDING 的真实期限日为
2026-07-28。只有在当日 15:00 后、五标的及沪深300的完整正式 QFQ/指数等价日线持久化
且具有稳定 ref/version/hash 后，才允许运行：

```bash
.venv/bin/python scripts/mature_alphaguard_backfill_labels.py \
  --backfill-run-id 9b921ffa-71a5-578b-85e8-252b2f9cfca9 \
  --as-of-trade-date 2026-07-28
```

dry-run 全部 READY 后才可显式加 `--execute`。服务只选择 canonical lineage 的
`DECISION_CLOSE + 20D + PENDING`，执行前后比较全部既有成熟标签 hash；重复执行必须成熟
0 条。价格行的 `available_at` 和 `collected_at` 都必须不晚于评价截止时间。盘中、缺正式
QFQ、未来日期或任一 source 不完整时明确阻断。

2026-07-28 12:00 左右已运行一次默认 dry-run，结果为
`current trading day has not completed; labels remain PENDING`。该检查发生在标签查询和
替换前，没有数据库写入。随后只读复核仍为 `20D CALCULATED=240 / PENDING=10`。

### 14.4 测试边界

根目录 `pytest.ini` 和 collection-time 分类只隔离精确清单，不删除或全局 skip 测试：

```bash
# 默认离线确定性 CI：不访问实时网络，不等待 input
.venv/bin/python -m pytest

# 显式实时网络边界
.venv/bin/python -m pytest --alphaguard-suite=network

# 显式交互/人工边界
.venv/bin/python -m pytest --alphaguard-suite=interactive
.venv/bin/python -m pytest --alphaguard-suite=manual

# 显式复现存量导入错误
.venv/bin/python -m pytest --alphaguard-suite=legacy_collection_error --collect-only
```

默认离线入口只包含已经审计的 AlphaGuard unit/integration，并在进程级禁止 INET socket
和 `input()`；未经逐文件审计的旧顶层 debug、Provider 和本机服务测试保留在显式
`manual/network/interactive` 边界。实际结果为：

```text
默认离线确定性 CI=465 passed, 89 warnings
生产数据 + 测试边界专项=10 passed
显式 legacy_collection_error=14 个既有 ImportError，exit 2
```

14 个错误没有被吞掉或改成业务通过。显式 legacy 入口会执行旧模块现有的本机 Mongo
初始化日志，默认离线入口不会放行网络或交互。

### 14.5 当前运行状态

```text
MongoDB/Redis/Scheduler/queue-worker/analysis-worker=HEALTHY
queue-worker heartbeat TTL=13s
analysis-worker heartbeat TTL=42s
FastAPI/queue-worker/analysis-worker live=true=exit 3/1/1
三个自动账户 initial_cash/cash_available=1000000.00/1000000.00
cash_reserved=0
Position/Order/Fill/Reservation/Ledger/Settlement=0
正式 Snapshot/Proposal/Outbox/Intent/Order/Fill duplicate identity=0
```

当前 Operations 保持 `DATA_READY=false`，直接阻断为
`MARKET_CONTEXT_CURRENT_VERSION_MISSING`。v1.1 生成器已修复跨执行时刻幂等：重复运行
复用第一次 `available_at/collected_at`；security master 的 `UNCHANGED` 目标不再刷新
`updated_at`。这些修复没有触发新的 Provider 同步或数据库写入。

## Production Data Completion 最终记录（2026-07-28 收盘后）

本节取代上方“盘中 / 尚无 v1.1”的即时状态。没有重新运行历史回放、全量行情、账户、
Champion 或索引初始化。

### 日线 Provider 与持久化

- 已知完整日 `2026-07-24`：BaoStock 与既有本地记录逐字段一致；AKShare/Tencent 在统一
  Decimal 量化和单位换算后，股票 RAW/QFQ 价格在版本化容差内，volume/amount 的尾差被
  明确记录；沪深300存在 0.0013～0.0035 点的 Provider 精度差异，仍在容差内。
- AKShare/Eastmoney 的 `stock_zh_a_hist` / `index_zh_a_hist` 能力存在，但当次连接被远端
  关闭；没有将空响应写入数据库。
- `2026-07-28`：BaoStock RAW/QFQ（指数为
  `INDEX_UNADJUSTED_EQUIVALENT`）六个标的均 VALID；AKShare/Tencent 六个标的均 VALID；
  Eastmoney 均 ERROR。Resolver 选择 BaoStock，`fallback_reason=null`，Tencent 只写入
  `validation_refs`。
- 股票 RAW 容差为价格 `max(0.01, 0.001%)`、volume `max(100股, 0.001%)`、amount
  `max(100元, 0.001%)`；QFQ 价格容差为 `max(0.05, 0.1%)`。成交量统一为股、成交额统一为
  CNY，价格量化到 0.0001、金额量化到 0.01。
- 本地 exact-date 六条记录全部为 `bar_granularity=PROVIDER_DAILY`、
  `bar_completion_status=COMPLETED`，collected_at 为 17:52:49～17:53:01 CST，晚于收盘；
  RAW/QFQ/index 版本、来源身份和 content hash 完整。重复同步全部 REUSED，原始
  collected_at/hash 不变。

### 交易状态和 MarketContext

五只股票的 2026-07-28 `ag_security_trading_statuses` 全部 READY 且重复 REUSED：

```text
000333  SZSE_MAIN  previous=84.13   upper/lower=92.54/75.72
002594  SZSE_MAIN  previous=92.40   upper/lower=101.64/83.16
300750  CHINEXT    previous=400.00  upper/lower=480.00/320.00
600519  SSE_MAIN   previous=1289.50 upper/lower=1418.45/1160.55
601318  SSE_MAIN   previous=53.41   upper/lower=58.75/48.07
```

全部 `is_st=false / is_suspended=false / tick_size=0.01 / lot_size=100`。规则分别使用主板
10%和创业板20%，没有统一按10%计算。

生产 MarketContext v1.1 使用独立的当日 BaoStock A股 universe 与
AKShare/Tencent 120日历史日线构建，没有读取或复制 `ag_research_*`：

```text
context_id=10b1f30f-60d8-5798-bc9c-0c9f11685cd1
status=READY
provider=akshare-tencent 1.18.78
universe provider=baostock 00.9.30
source/expected=5193/5201
universe/high-low/sector coverage=0.998462/0.999230/1
advance/decline/unchanged=2365/2681/147
new_high/new_low=268/458
industry_diffusion=0.3
benchmark_close/MA20/MA60=4569.5235/4743.523775/4838.2949667
benchmark_volatility20=0.2950825816
calculation_version=production-market-context-calculation-v1.1
```

首次写入后跨执行时刻完整复跑为 `source_action=REUSED /
context_action=REUSED`；content hash 稳定，研究与生产对象隔离。

### 评价、观察和 Readiness

十条剩余 20D 标签因历史 QFQ 与新增日线的版本 seam 不能组成单一锁定序列，保持
`240 CALCULATED / 10 PENDING`。这是 fail-closed，不是用缺失数据完成成熟。

五个候选均 `DataQuality=PASS`，新增对象为 Snapshot 5、Factor 105、Regime 5、Proposal
10、EvaluationSubject 10；唯一身份重复均为 0。Regime 因不可变 Snapshot 中只锁定了
新增版本的一条沪深300记录而返回 `INSUFFICIENT_DATA`，Proposal 为 5 REJECTED +
5 INSUFFICIENT_DATA，无 TRIGGERED。模型、Consensus、HardRisk 和订单链没有被伪造。

Operations 当前：

```text
CODE_COMPLETE=true
RUNTIME_READY=true
DATA_READY=true
PAPER_READY=true
EVALUATION_READY=true
EXPERIMENT_READY=true
CHALLENGER_READY=false
LIVE_READY=false
```

`INDUSTRY_HISTORY` 仍明确为 `PARTIAL / CURRENT_ONLY`，只影响历史行业归因，不被伪装成
READY。`DATA_READY` 的生产数据域已完成，但不表示每个不可变 Snapshot 都有连续单版本
历史。完整 Challenger 按既有边界保持关闭，live 永久 fail-closed。

## Production History Continuity Phase 2

生产 MarketContext v1.1 历史已按持久化交易日历补齐：

```text
范围=2026-01-26..2026-07-27
开市日=120
READY=120
source/context 首次创建=120/120
第二次完整执行复用=120/120
历史 normalization=alphaguard-production-market-context-history-v1.1
calculation=production-market-context-calculation-v1.1
```

数据来自历史日实际 BaoStock A股 Universe、AKShare/Tencent 个股日线、十个行业指数及
持久化沪深300，不来自研究 Context。A股单日覆盖率最低 0.9903846154，新高/新低最低
覆盖率 0.9974942174，行业覆盖率为 1；120 日均无 Provider 失败或
`INSUFFICIENT_DATA`。2026-07-28 current v1.1 保持原 ID/hash/时间。

这使生产 MarketContext 历史输入本身 READY，但不会回填既有 Snapshot。2026-07-28 的
五个不可变 Snapshot 仍只锁定一根新版本沪深300，故锁定 Regime 结果 5/5 保持
`INSUFFICIENT_DATA`。下一开市日 2026-07-29 尚未收盘和持久化，没有运行新观察链。

Canonical 10 条 20D 标签继续使用安全方案B：240 条已成熟标签不动，10 条因 7月28日
QFQ 版本断点保持 PENDING；不跨版本拼接。生产与研究 lineage 交叉引用为 0，正式交易和
账户资产没有变化。

```text
MARKET_CONTEXT_HISTORY_READY=true
REGIME_READY=false
DATA_READY=true
LIVE_READY=false
overall=DEGRADED_PAPER
```
