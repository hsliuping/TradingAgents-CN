# AlphaGuard 生产历史连续性

## 1. 范围与安全边界

本阶段只补齐 Production MarketContext 的生产历史输入，并审计 canonical
Historical Backfill 剩余 10 个 20D 标签的 QFQ 版本连续性。这不是 PR-010，没有修改
Factor、Regime、Strategy、Prompt、模型、Consensus、HardRisk、Matching、Fee 或
Champion；没有增加股票、启用 Challenger、创建订单或连接券商。

生产与研究继续严格隔离：

- 生产历史只写 `ag_market_context_sources`、`ag_market_contexts` 和
  `ag_production_data_events`；
- 不读取或复制 `ag_research_market_context_sources`、
  `ag_research_market_contexts` 或 `ag_exp_*`；
- 研究对象不进入 Snapshot、OrderIntent、Outbox 或 Paper 账户；
- 所有历史标签和既有生产决策对象均保持 create-only。

## 2. MarketRegime 实际窗口

当前 `MarketRegimeEngine` 的强制输入为：

| 输入 | 实际最小窗口 | 来源 |
| --- | ---: | --- |
| 沪深300 close/MA20 | 20个交易时段 | Snapshot `benchmark_prices` |
| 沪深300 close/MA60 | 60个交易时段 | Snapshot `benchmark_prices` |
| MA20 5日斜率 | 25个交易时段 | 当前MA20相对前移5日MA20 |
| 20日年化波动率 | 21个收盘/20个收益 | Snapshot `benchmark_prices` |
| 市场宽度 | 当日 | `advance_count/decline_count` |
| 行业扩散度 | 当日10个行业指数，最低覆盖80% | Production MarketContext |
| 成交额变化 | 当前及前20个交易时段 | Production MarketContext，辅助 |
| 新高/新低 | 当前及前20个交易时段 | Production MarketContext，辅助 |

统一沪深300门槛是61根有效收盘。没有缩短该门槛，也没有把缺失字段填0或默认成
`RANGE_WEAK`。

## 3. 目标日期与数据源

日期严格来自持久化 `trading_calendar`：

```text
through trade date = 2026-07-28
prior open sessions = 120
target range = 2026-01-26..2026-07-27
existing current context = 2026-07-28
combined intended coverage = 121 open sessions
```

历史源沿用正式生产 Provider：

- 当日 A股 Universe：BaoStock 00.9.30 `query_all_stock(day=...)`；
- 个股日线、全市场成交额、20日新高/新低：AKShare 1.18.78
  `stock_zh_a_hist_tx`，底层 Tencent；
- 十个行业指数：同一 AKShare/Tencent 历史日线接口；
- 沪深300趋势和波动：已持久化 `stock_daily_quotes`，每根保留自己的真实
  `price_data_version/ref_id/content_hash`。

Universe 使用各历史交易日真实返回的股票集合和 `tradeStatus`，不使用当前5193只全集、
五只候选、研究集合或静态 fixture。无法恢复的数据按覆盖率和缺失字段明确标记，不填0。

## 4. 版本、可用性与幂等

当前日记录继续使用：

```text
normalization = alphaguard-production-market-context-v1.1
calculation = production-market-context-calculation-v1.1
```

批量历史记录使用独立且版本化的逐日响应 hash 口径：

```text
normalization = alphaguard-production-market-context-history-v1.1
calculation = production-market-context-calculation-v1.1
```

区分历史 normalization 的原因不是改变计算规则，而是保证单日业务内容 hash 不依赖一次
批量请求的起止范围，同时不改变2026-07-28已持久化 v1.1 的既有 hash 语义。

历史数据是收盘后补采证据，`available_at/collected_at` 保存真实首次采集时间，不伪装成
历史当日已采集。所有输入业务日期均不晚于对应 Context `trade_date`，没有未来市场宽度或
未来行业值参与计算。

create-only 身份：

```text
source = market + trade_date + provider + provider_version + normalization
context = market + trade_date + data_version
```

相同身份、相同内容返回 `REUSED`；相同身份、不同内容抛
`INTEGRITY_CONFLICT`。既有 `created_at/collected_at/content_hash/source_hash` 不刷新。

## 5. QFQ 版本连续性

Canonical run：

```text
backfill_run_id=9b921ffa-71a5-578b-85e8-252b2f9cfca9
decision_trade_date=2026-06-30
target_trade_date=2026-07-28
pending 20D labels=10
```

五只股票的21个评价交易日没有缺行，但全部在终点出现同一版本断点：

```text
2026-06-30..2026-07-27
  baostock:00.9.30:QFQ:alphaguard-candidate-real-data-v1

2026-07-28
  baostock:00.9.30:baostock:QFQ:
  alphaguard-daily-price-normalization-v1
```

沪深300也在2026-07-28从旧 `INDEX_RAW` 版本切换至新的
`INDEX_UNADJUSTED_EQUIVALENT` 规范化版本。问题是版本/规范化批次变化，不是缺少中间
交易日。

本阶段选择安全方案B：继续 `PENDING_VERSION_DISCONTINUITY`。现有
`stock_daily_quotes.ref_id` 是每标的每日唯一身份；直接再写一套同日 QFQ 会造成生产
Repository 查询歧义。系统不建立旁路价格库、不改仓储身份契约、不跨版本容差拼接，也不
修改240条已成熟20D标签。

## 6. 不可变 Snapshot 与 Regime

五个2026-07-28生产 Snapshot 各自只锁定一根新版本沪深300引用；既有五个
MarketRegimeResult 因 `benchmark_prices.close[61]` 不足而
`INSUFFICIENT_DATA`。补齐 Production MarketContext 历史不会更改 Snapshot
`raw_refs/immutable_hash`。

由于 `ag_regime_results` 对 `snapshot_id + regime_version` create-only 唯一，不能用新
数据原地覆盖旧结果。历史补齐后只按现有引擎复核：输入 hash 不变则复用原
`INSUFFICIENT_DATA`；不会伪造新的 Regime 或覆盖现有 Proposal。完整历史供后续新交易日
Snapshot 按当时锁定版本使用。

## 7. 实际执行结果

受控同步严格选择持久化日历中 2026-07-28 之前的 120 个开市日。实际结果：

```text
日期范围=2026-01-26..2026-07-27
Production MarketContext history=120
READY=120
INSUFFICIENT_DATA=0
首次 source/context CREATED=120/120
第二次 source/context REUSED=120/120
duplicate date/identity/content hash=0/0/0
研究集合引用=0
```

历史 A 股 Universe 是 BaoStock 对每个业务日返回的实际集合。120 日代码并集为 5219；
单日 source/expected 覆盖率为 0.9903846154～0.9994230769，新高/新低最低覆盖率为
0.9974942174，十个行业指数覆盖率始终为 1。Provider 批次失败为 0。单条 source BSON
约 1.48 MB，低于 MongoDB 16 MB 限制。

2026-07-28 既有 current v1.1 Context 未覆盖或刷新。数据库当前另保留一条
2026-07-27 的旧 v1 时序审计记录，因此 `ag_market_contexts` 总数是 122：

```text
history v1.1=120
current v1.1=1
legacy v1 audit row=1
```

### 7.1 Regime 只读复核

五个 2026-07-28 Snapshot 的 Champion 版本、raw refs 和 immutable hash 均保持不变。
使用 Snapshot 锁定的 `regime:market-regime-v1` 在内存中复核：

```text
snapshot=5
VERIFIED_UNCHANGED=5
INTEGRITY_CONFLICT=0
MISSING_RESULT=0
原/新 input_hash=逐项相同
原/新状态=INSUFFICIENT_DATA
Proposal change=0
模型链调用=0
```

既有 Snapshot 只锁定一根新版本沪深300数据，仍缺
`benchmark_prices.close[61]`。因此：

```text
MARKET_CONTEXT_HISTORY_READY=true
REGIME_READY=false
```

历史 Context 已可供后续新业务日使用，但不能改变已经创建的 Snapshot。持久化日历的
下一开市日是 2026-07-29；本阶段完成时该日尚未收盘和入库，所以没有运行新的生产观察
链。

实现期间有一次只读复核误调用了默认 Regime 配置入口，创建了 5 条未被任何 Proposal、
Decision、Evaluation 或交易对象引用的 `INSUFFICIENT_DATA` 结果。发现后立即完成全引用
审计，并只删除这 5 条精确 ID；原 5 条锁定结果仍在，数量、ID 和 input hash 均已复原。
随后将复核固化为不持久化的 `verify_locked_regimes`，且新增测试确保始终解析 Snapshot
锁定版本。该事件没有下游对象或资产影响。

### 7.2 QFQ 标签与资产

Canonical 20D 审计结果：

```text
DECISION_CLOSE CALCULATED=240
DECISION_CLOSE PENDING=10
PLANNED_ENTRY CALCULATED=4
10条 blocker=VERSION_LOCKED_QFQ_SERIES_UNAVAILABLE
成熟/改写=0/0
```

240 条已成熟标签未重算。10 条标签的 21 个交易日没有缺行，但 2026-07-28 发生 QFQ
版本断点，继续采用方案B并保持 `PENDING_VERSION_DISCONTINUITY`。

正式 Outbox、Intent、Order、Fill、Position、Lot、Reservation、Ledger、Settlement
仍为 0。三个自动账户各有可用现金 1,000,000 CNY、冻结现金 0、仓位 0；无负现金、负
持仓、死信或卡住 Saga，资产未变化。

### 7.3 验证和 Readiness

```text
本阶段连续性/生产数据专项=22 passed, 84 warnings
默认离线CI（PR-001～PR-009及现有精确回归）=497 passed, 89 warnings
Python编译=passed
git diff --check=passed
敏感信息扫描=0 hits
MongoDB/Redis/Scheduler/FastAPI=HEALTHY
queue-worker/analysis-worker=HEALTHY
FastAPI/queue-worker/analysis-worker live=true=全部拒绝启动
```

最终 Readiness：

```text
CODE_COMPLETE=true
RUNTIME_READY=true
DATA_READY=true
PAPER_READY=true
EVALUATION_READY=true
EXPERIMENT_READY=true
CHALLENGER_READY=false
LIVE_READY=false
overall=DEGRADED_PAPER
```

这次补全是生产输入连续性建设，不是新的历史回放、生产收益或策略效果证明。

## 8. 回退

代码通过本阶段独立提交的父提交回退，不使用 `git reset --hard`。

数据库证据默认保留。若业务明确要求撤销：

1. 先备份本阶段 Context、source、event 精确身份并执行引用审计；
2. 只处理 `2026-01-26..2026-07-27` 且 normalization 为
   `alphaguard-production-market-context-history-v1.1` 的对象；
3. 禁止删除2026-07-28既有 Context；
4. 禁止通配清空集合；
5. 禁止触碰 `ag_research_*`、HorizonLabel、账户或交易集合；
6. 若任何 EvidenceSnapshot 已引用目标 Context，则停止删除并保留证据。
