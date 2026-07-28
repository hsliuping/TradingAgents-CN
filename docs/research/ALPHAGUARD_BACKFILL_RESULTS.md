# AlphaGuard 第一轮历史回放结果

> 历史研究回放，不是实时生产成绩，不是实际账户收益，不是投资建议，未证明未来有效。

## 1. Canonical 运行

```text
backfill_run_id=9b921ffa-71a5-578b-85e8-252b2f9cfca9
report_id=54c36431-b5c6-5236-aaa2-73a4293d6efe
report_status=READY
report_hash=473902646fc07fb4fd0b9132776911347d410f772ef96a81962575c17310d302
code_commit=c6fd75f673e2fe5eafce22f61f06868cf38d0b53
code_tree_hash=a1350d105ba5bc7f11047ddd7f335c28a39008f73a0d92f6357400198c425beb
日期=2026-01-01 至 2026-06-30
抽样=WEEKLY_LAST_SESSION
持久化日历日期数=25
标的数=5
计划/完成/跳过/失败=125/125/0/0
模型回放=未请求
run_mode=RESEARCH_BACKFILL
research_only=true
automated_execution_allowed=false
```

同一 execute 命令立即复跑后，run/report ID、report hash、attempt_count 和全部 canonical
研究集合计数不变。Canonical run 每次运行前后均比较十个正式交易集合的 count 和内容
hash；比较通过，没有正式交易副作用。

实现期间保留了两个真实缺陷恢复 run：`6507b7ef-...` 和 `fe1e9721-...`。它们没有被删除
或伪装为 canonical 结果；二者同样只写研究/评价 lineage。Operations 的全库评价样本数会
包含这两个审计 run，本文件所有统计只使用上述 canonical run。

## 2. 历史 MarketContext

- Provider：BaoStock `00.9.30`；25/25 日期成功，Provider 失败 0。
- `ag_research_market_context_sources=25`、`ag_research_market_contexts=25`，全部 READY。
- 历史 A 股 universe 并集 5,216；每日 5,182～5,207。
- universe coverage=1；high/low coverage 约 0.99749～0.99981；sector coverage=1。
- 行业扩散使用 10/10 个历史行业指数；没有用五只候选代替全市场。
- 来源 BSON 文档约 1.38MB，低于 16MB 限制；重复 source/context ID 为 0。

这些数据只存在于 `ag_research_*`。生产 `ag_market_contexts` 仍为 0，Operations 因此继续
报告 `MARKET_CONTEXT_MISSING`；研究数据没有被复制成生产数据。

## 3. 数据质量

```text
HistoricalCoverageRecord=125
DataQuality PASS/WARN/FAIL=0/125/0
MarketContext READY/BLOCKED=125/0
warning 总数=248
HISTORICAL_INDUSTRY_MAPPING_UNAVAILABLE=125
NEWS_UNAVAILABLE_AS_OF_CUTOFF=123
```

WARN 没有被当成 FAIL，也没有用未来或当前值补齐。财务按真实披露日截断，新闻和公告按
历史发布时间截断；current-only 行业映射未回填历史，全部行业相对收益为 null。

## 4. 因子覆盖

Canonical run 生成 2,625 个 FactorResult，即 125 个 Snapshot × 21 个现有因子。

| 因子 | 有值/125 | 覆盖率 |
| --- | ---: | ---: |
| adjusted_net_profit_yoy_v1 | 0 | 0% |
| atr14_pct_v1 | 125 | 100% |
| average_amount20_v1 | 125 | 100% |
| close_vs_ma20_v1 | 125 | 100% |
| close_vs_ma60_v1 | 125 | 100% |
| dividend_yield_v1 | 0 | 0% |
| event_risk_v1 | 125 | 100% |
| ma20_slope_5d_v1 | 125 | 100% |
| ma20_vs_ma60_v1 | 125 | 100% |
| momentum_20d_v1 | 125 | 100% |
| momentum_60d_v1 | 125 | 100% |
| operating_cashflow_to_profit_v1 | 0 | 0% |
| pb_percentile_3y_v1 | 125 | 100% |
| pe_ttm_percentile_3y_v1 | 125 | 100% |
| relative_strength_hs300_20d_v1 | 125 | 100% |
| revenue_yoy_v1 | 112 | 89.6% |
| roe_v1 | 125 | 100% |
| short_term_excess_return5_v1 | 125 | 100% |
| turnover20_v1 | 125 | 100% |
| volatility20_annualized_v1 | 125 | 100% |
| volume_confirmation_20d_v1 | 125 | 100% |

每个因子的方向命中、归一化分桶和各期限收益均保存在 report 的 `factor_summary`。缺失的
财务因子保持 null，没有填 0 或改公式。

## 5. Regime 与 Strategy

Regime 计算率 125/125：

| Regime | 样本数 |
| --- | ---: |
| RANGE_STRONG | 45 |
| RANGE_WEAK | 65 |
| TREND_DOWN | 10 |
| TREND_UP | 5 |
| EXTREME_RISK | 0 |

两个现有 Strategy 对每个 Snapshot 各生成一个提案，共 250 个：

```text
REJECTED=200
WATCH=46
TRIGGERED=4
entry_zone 可评价=4
entry_zone 触及=2
```

没有修改门槛制造 `TRIGGERED`。模型回放未请求，Normal/Top/Consensus/HardRisk 运行数均
为 0，不能把本轮结果解释为完整双模型历史成绩。

## 6. 成熟评价

Canonical run 生成：

```text
EvaluationSubject=250
HorizonLabel=1016
  DECISION_CLOSE=1000
  PLANNED_ENTRY=16
CounterfactualEvaluation=500
AttributionRecord=250
selected_for_execution=false=250
research lineage=250/250
```

DECISION_CLOSE 成熟状态：

| 期限 | CALCULATED | PENDING | 平均收益 | 平均 MFE | 平均 MAE | 平均相对沪深300 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 1D | 250 | 0 | 0.0411% | 1.3969% | -1.4273% | -0.1473% |
| 5D | 250 | 0 | -0.1109% | 3.1446% | -2.8996% | -0.2863% |
| 10D | 250 | 0 | -0.2317% | 4.3343% | -4.4576% | -0.5376% |
| 20D | 240 | 10 | -0.2953% | 6.2112% | -6.4723% | -0.4933% |

250 是 proposal subject 数；两个 Strategy 共享同一批 125 个 Snapshot，因此不能把它当成
250 个独立市场机会。2026-06-30 的两个 Strategy × 五标的共 10 个 20D 标签，真实成熟日
为 2026-07-28；截至 2026-07-27 必须保持 PENDING。

归因：`CANDIDATE_SELECTION=242`、`STRATEGY_ENTRY=6`、`FACTOR_FAILURE=2`、
`UNKNOWN=0`。结果分类：`AVOIDED_LOSS=46`、`MISSED_OPPORTUNITY=34`、`LOSS=3`、
`NEUTRAL=167`。这些是现有 PR-007 口径下的研究标签，不代表实际账户盈亏。

## 7. 影子执行与正式账户隔离

```text
NOT_ELIGIBLE=246
INSUFFICIENT_DATA=4
FILLED/PARTIALLY_FILLED=0
研究 ExecutionMarketSnapshot=0
```

4 个 TRIGGERED 提案都因原始日线没有显式 `limit_up_price/limit_down_price` 而 fail-closed；
没有根据股票板块推算涨跌停，没有成交、费用或滑点统计。

回放结束后正式集合为：Outbox/Intent/Order/Fill/Position/Lot/Reservation/Ledger/
Settlement 均 0，自动账户仍为 3 个。三账户各 `initial_cash=cash_available=1000000.00`、
`cash_reserved=0`，三份 2026-07-27 DailyAccountSnapshot 的 `total_equity=1000000.00` 且
`valuation_complete=true`，资产守恒。

## 8. 缺陷恢复记录

真实执行发现并修复三个运行缺陷，均不改变交易参数：

1. 研究解析文档含 Decimal 时误用非 Decimal-safe 哈希，改为研究 canonical hash；
2. FAILED run 恢复后，旧失败汇总报告未刷新；报告改为同一 run 的 CAS 当前态，状态不得
   回退，并保留事件审计；
3. dirty-tree hash 原先把测试和文档变化当成运行代码变化，现只纳入 AlphaGuard 运行
   源码、配置和回放脚本。

失败样本使用相同 sample identity 恢复，最终 125/125 完成。任何同身份输入变化仍返回
`INTEGRITY_CONFLICT`，不会覆盖不可变 Snapshot、Factor、Proposal 或评价对象。

## 9. 验证结论与限制

```text
新增历史回放测试=11 passed
PR-001～PR-009 AlphaGuard 精确回归=455 passed, 89 warnings
研究索引重复执行=created 0 / unchanged 38 / failed 0
Champion=5/5 verified, conflicts 0
FastAPI /health/live=200
FastAPI /health/ready=200, DEGRADED_PAPER
MongoDB/Redis=healthy
queue heartbeat TTL>0（最终观测 12）
analysis heartbeat TTL>0（最终观测 46）
FastAPI/queue-worker/analysis-worker live=true=全部非零退出
修改 Python 编译=passed
git diff --check=passed
敏感信息扫描=20 files, 0 hits
```

根目录全量 `pytest --collect-only -q` 会在 collection 阶段执行存量实时网络和交互脚本；
本次在 395.17 秒后安全中止，当时为 197 collected / 12 errors，尚未完成，不能宣称复核了
既有 15 个完整收集错误。最近一次完整基线仍是 1142 collected / 15 errors。本阶段没有
新增 AlphaGuard 精确回归失败。

当前 Operations 为 `CODE_COMPLETE=true / RUNTIME_READY=true / PAPER_READY=true /
EVALUATION_READY=true / DATA_READY=false / LIVE_READY=false`。生产 MarketContext、历史行业
映射、实验样本和完整 Challenger 链仍是明确限制。未开始 PR-010，未调参，未运行双模型
全量回放，也未扩大日期、标的或抽样频率。
