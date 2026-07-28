# AlphaGuard 历史研究回放说明

## 1. 范围与安全边界

本阶段是 Historical Backfill & Accelerated Evaluation，不是 PR-010，也不是新的交易
功能。第一轮固定范围：

```text
市场：CN
日期：2026-01-01 至 2026-06-30
标的：600519、601318、000333、002594、300750
抽样：持久化交易日历中的每周最后一个开市日
模式：RESEARCH_BACKFILL
research_only=true
automated_execution_allowed=false
```

所有研究事实写入 `ag_research_*`，评价事实沿用 create-only 的 `ag_eval_*` 并通过
`lineage_ids.backfill_run_id/run_mode/research_only` 明确区分。以下正式集合在回放前后
执行数量和内容哈希核对，研究服务没有写权限：

```text
ag_execution_outbox
ag_order_intents
ag_paper_orders
ag_paper_fills
ag_paper_accounts
ag_paper_positions
ag_paper_position_lots
ag_paper_reservations
ag_paper_ledger_entries
ag_settlement_records
```

本阶段没有修改 Factor、Factor 权重、Regime、Strategy、Prompt、模型、Consensus、
HardRisk、Matching、Fee 或 Champion，也没有启用 PAPER_CHALLENGER。

## 2. 历史信息截断

每个 `symbol + trade_date` 独立冻结研究 Snapshot：

- RAW/QFQ 行情只接受 `trade_date <= snapshot_trade_date`，并锁定单一 QFQ 版本；
- 财务同时要求报告期不晚于交易日，且第一个有效披露字段
  `f_ann_date/ann_date/publish_date/published_at <= cutoff`；
- 新闻只接受 `publish_time/published_at/timestamp <= cutoff`；
- 公告只接受 `announcement_time/published_at/publish_time/timestamp <= cutoff`；
- MarketContext 必须是同一历史交易日、明确 Provider 和版本的唯一记录；
- 行业 current-only 映射不会用于历史，缺失时行业相对收益保持 null；
- 未来 1D/5D/10D/20D 行情只在 Snapshot、Factor、Regime、Proposal 已冻结后由评价服务读取。

同一历史身份出现多个 QFQ、沪深300或 MarketContext 版本时 fail-closed 为完整性冲突，
不选择“最新”记录。

## 3. 历史 MarketContext

现有 MarketRegimeEngine 的输入保持不变。历史市场环境使用 BaoStock 00.9.30：

1. 对每个抽样日调用 `query_all_stock(day=...)`，获得该日实际 A 股 universe；
2. 对所有日期的 universe 并集读取历史不复权日线，计算上涨、下跌、平盘、总成交额、
   前 20 个开市日成交额比和 20 日新高/新低；
3. 行业扩散使用十个可追溯的历史交易所行业指数 `sh.000032` 至 `sh.000041`；
4. 沪深300历史用于现有极端波动与市场宽度组合条件；
5. 不用五个候选代表全市场，不用当前行业成分回填历史，不把缺失字段填成 0。

每个日期保存原始归一化来源文档和计算后的 MarketContext。来源文档在写库前检查 BSON
大小，达到 15MB 即阻断，避免越过 MongoDB 16MB 单文档限制。同一日期、Provider、
Provider版本和规范化版本 create-only；相同身份不同内容抛出完整性冲突。

## 4. 确定性研究链

第一轮只运行确定性量化：

```text
HistoricalCoverageRecord
→ HistoricalResearchSnapshot
→ 现有纯函数 Factor
→ 现有 MarketRegimeEngine 计算函数
→ 现有 StrategyEngine
→ QuantTradeProposal
→ EvaluationSubject
→ HorizonLabel / Counterfactual / Attribution
```

模型回放未请求。没有健康、可审计的历史模型调用时不会生成默认 HOLD，样本记录为
`NOT_REQUESTED` 或 `NOT_CONFIGURED`。Consensus 和 HardRisk 不会被伪造为已运行。

## 5. 研究影子执行

仅 `TRIGGERED + BUY + entry_zone` 的 QuantProposal 进入研究影子可执行性评价：

- 使用持久化交易日历确定下一开市日和有效期；
- 用版本化 Paper Account Policy 计算规范化研究数量，保持 100 股整数手；
- 必须存在原始日线中的显式停牌、ST、涨停价和跌停价；
- 明确边界存在时复用 PR-006 `ExecutionMarketSnapshotService`、`MatchingEngine` 和
  `FeeEngine`，但通过研究数据库映射只写 `ag_research_execution_snapshots` 和
  `ag_research_backfill_events`；
- 缺涨跌停边界时返回 `INSUFFICIENT_DATA`，不根据板块推算；
- 研究收益同时扣除买入和假设退出卖出费用，不写账户、订单、Fill、持仓或 Ledger。

研究回放中，历史行情的采集时间晚于历史交易日是正常的。影子执行只忽略
`updated_at/as_of` 采集元数据的生产时点限制，仍锁定交易日、数据版本、来源引用和内容，
且只在决策冻结后读取 T+1 及之后的执行/评价行情。

## 6. 幂等、恢复和审计

- BackfillRun 身份由管理员、标的、日期、抽样日、锁定版本、代码 commit、AlphaGuard
  运行源码/配置的 dirty-tree hash 和配置 hash 决定；测试和文档变化不会伪造新运行版本；
- Sample 身份由 `backfill_run_id + symbol + trade_date` 决定；
- Snapshot、Factor、Regime、Proposal、ShadowExecution 和评价对象均 create-only；
- 同输入重复运行复用，身份相同但哈希不同返回 `INTEGRITY_CONFLICT`；
- `RUNNING/FAILED` 样本可由 `--resume` 继续，已完成和已明确跳过样本不重复写资产；
- Run、Sample 和 MarketContext 状态写入幂等 `ag_research_backfill_events`；
- 每次完整运行前后比较正式交易集合哈希，任何变化立即将 Run 标记 FAILED。
- BackfillReport 是同一 run 的 CAS 当前态：失败恢复可刷新汇总，但完成数和跳过数不能
  回退；不可变 Snapshot、Factor、Proposal、Label、Shadow 和 Attribution 仍为 create-only。

## 7. 操作命令

所有脚本默认 dry-run：

```bash
.venv/bin/python scripts/init_alphaguard_backfill_indexes.py
.venv/bin/python scripts/init_alphaguard_backfill_indexes.py --execute

.venv/bin/python scripts/sync_alphaguard_historical_market_context.py \
  --start 2026-01-01 --end 2026-06-30
.venv/bin/python scripts/sync_alphaguard_historical_market_context.py \
  --start 2026-01-01 --end 2026-06-30 --execute

.venv/bin/python scripts/run_alphaguard_historical_backfill.py \
  --username alphaguard_admin \
  --symbol 600519 --symbol 601318 --symbol 000333 \
  --symbol 002594 --symbol 300750 \
  --start 2026-01-01 --end 2026-06-30 \
  --as-of-trade-date 2026-07-27
```

只有显式 `--execute` 才写研究/评价集合。`--resume <run_id>` 恢复运行，
`--report-only <run_id>` 只重新查询报告。

## 8. 数据回退

回退前先保存精确 `backfill_run_id` 和研究集合计数。只允许按该 run 的明确 lineage 删除
或归档研究对象；MarketContext 来源可能被其他研究 Run 复用，不能按日期范围通配删除。
`ag_eval_*` 中的研究评价对象必须按 `lineage_ids.backfill_run_id` 精确识别。正式 Snapshot、
Factor、Proposal、账户、订单和账本不属于回退范围。

历史研究回放不是实时生产成绩，不是实际账户收益，不是投资建议，也未证明未来有效。

## 9. 第一轮完成身份

```text
canonical backfill_run_id=9b921ffa-71a5-578b-85e8-252b2f9cfca9
canonical report_id=54c36431-b5c6-5236-aaa2-73a4293d6efe
planned/completed/skipped/failed=125/125/0/0
report_status=READY
```

完整统计见 `docs/research/ALPHAGUARD_BACKFILL_RESULTS.md`。实现期间两个缺陷恢复 run 保留
审计 lineage，不计入 canonical 统计，也没有写入正式交易集合。
