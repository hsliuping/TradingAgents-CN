# AlphaGuard 自动模拟运行观察清单

## 使用原则

- 每个交易日按本清单记录真实状态，不自动修改 Champion、因子、策略、Prompt、模型、
  HardRisk、撮合或费用配置。
- `PASS` 必须来自可验证的运行证据；无数据记 `NOT_READY`，过期记 `STALE`，故障记
  `BLOCKING` 或 `DEGRADED`。
- 不因没有交易信号而调参或强制 BUY；WATCH、NO_TRADE、REJECT 和 SUSPEND 都是合法
  业务结果。
- 任何真实交易入口、BrokerAdapter 或 `live_trading_enabled=true` 都是立即阻断项。

## 每日检查

### 1. 服务和 Worker

- [ ] FastAPI `/health/live` 为 200。
- [ ] MongoDB、Redis 和 AlphaGuard 索引健康。
- [ ] API Scheduler 为 HEALTHY，关键任务已注册。
- [ ] queue-worker 进程健康、重启次数无异常。
- [ ] `alphaguard:worker:queue` 心跳值持续变化且 TTL 大于 0。
- [ ] analysis-worker 进程健康、重启次数无异常。
- [ ] `worker:*:heartbeat` 为 active、时间持续变化且 TTL 大于 0。
- [ ] 两套 Worker 连接到同一目标数据库和 Redis DB。
- [ ] 最近日志无重复 Traceback、连接循环失败或未处理任务错误。

### 2. 安全不变量

- [ ] `system_mode=SIM_AUTONOMOUS`。
- [ ] `live_trading_enabled=false`。
- [ ] `live_execution_allowed=false`。
- [ ] FastAPI、queue-worker、analysis-worker 在 `live=true` 时仍拒绝启动。
- [ ] 无券商 SDK、BrokerAdapter、真实订单网络请求或实盘开关 API。

### 3. 数据同步与 DataQuality

- [ ] 交易日历版本、范围、最后同步和下一交易日可解析。
- [ ] 候选与沪深 300 原始/QFQ 日线覆盖完整、版本一致。
- [ ] 财务报告期和真实披露日期完整。
- [ ] 新闻、公告发布时间不晚于快照 cutoff。
- [ ] 市场环境和行业历史映射可按交易日解析。
- [ ] 同步任务无 FAILED/DEAD_LETTER，重试没有覆盖原错误。
- [ ] DataQuality FAIL、缺失率、异常 OHLC 和未来数据数量已记录。
- [ ] EvidenceSnapshot raw_refs 均能唯一解析，哈希验证通过。

### 4. 决策链

- [ ] Candidate 仅来自用户明确选择，不存在全市场自动推荐。
- [ ] QuantProposal 的 WATCH/REJECTED/INSUFFICIENT_DATA 数量和原因正常。
- [ ] Normal 模型 MODEL_FAILED、INVALID_OUTPUT、INSUFFICIENT_DATA 分开统计。
- [ ] TopReview 模型失败和非法输出未回退为 HOLD。
- [ ] Consensus PASS/REVISE/REJECT/INVALID 数量及 lineage 可追踪。
- [ ] HardRisk PASS/REDUCE/REJECT/SUSPEND 的触发规则完整。
- [ ] 所有对象的 user/symbol/market/trade_date/snapshot/version 身份一致。

### 5. Outbox、订单和撮合

- [ ] 仅 RiskDecision PASS/REDUCE 或受控基准链产生对应 outbox。
- [ ] outbox backlog、retry、DEAD_LETTER 数量正常。
- [ ] 无重复 idempotency key、Intent、Order 或 Fill。
- [ ] 未到执行日、停牌、涨跌停和缺行情订单未被错误成交。
- [ ] 部分成交、剩余数量、预留和订单状态一致。
- [ ] PAPER_CHALLENGER 无活动账户、订单或持仓。
- [ ] 人工 paper 集合未被自动链修改。

### 6. 结算、账本和资产守恒

- [ ] Settlement Saga 无长期 PREPARED/中间态/COMPENSATION_REQUIRED。
- [ ] Fill 只结算一次，未 COMMITTED 的订单未标记 FILLED。
- [ ] 现金可用、冻结现金、持仓、lot 和预留均不为负。
- [ ] BUY lot 的 T+1 可用日期来自交易日历。
- [ ] FIFO 消耗、手续费和已实现盈亏与不可变 Fill 一致。
- [ ] 账本借贷变化可解释账户差额。
- [ ] 取消/过期只释放剩余预留，不改变净资产。
- [ ] 账户 reconciliation 通过；冲突已告警而非静默修正。

### 7. 账户估值和评价

- [ ] DailyAccountSnapshot 每个启用账户每个交易日唯一。
- [ ] 缺收盘价时 `valuation_complete=false`，未按 0 静默估值。
- [ ] 总权益、敞口、费用和持仓数量可由账户/持仓/快照复算。
- [ ] 合法决策/执行已登记真实 EvaluationSubject。
- [ ] HorizonLabel 只在真实交易日和 QFQ 数据成熟后计算。
- [ ] 评价样本不足保持 NOT_READY/INSUFFICIENT_DATA。
- [ ] 未来收益或归因没有进入任何决策输入。

### 8. 告警和日报结论

- [ ] 所有 OPEN/ACKNOWLEDGED 告警已按严重度检查。
- [ ] BLOCKING、DEGRADED、NOT_READY、STALE 项目已列出责任域和证据。
- [ ] 当日新增错误与存量错误分开。
- [ ] 记录 worker 心跳、任务积压、数据版本、Snapshot/Proposal/Decision/Order/Fill
  增量和资产核对结果。
- [ ] 未执行任何自动晋升、自动回退或生产参数修改。

## 建议日报格式

```text
trade_date:
code_complete:
runtime_ready:
data_ready:
paper_ready:
evaluation_ready:

blocking:
degraded:
not_ready:
stale:

queue_worker_heartbeat:
analysis_worker_heartbeat:
job_backlog:
data_sync:
data_quality:
model_failures:
invalid_outputs:
consensus:
hard_risk:
outbox:
orders:
settlement:
asset_conservation:
valuation:
evaluation_maturity:
alerts:

changes_performed:
changes_explicitly_not_performed:
evidence_links_or_ids:
```

## 当前首次观察结论（2026-07-27）

- `CODE_COMPLETE=true`、`RUNTIME_READY=true`、`EXPERIMENT_READY=true`。
- FastAPI、MongoDB、Redis、Scheduler、queue-worker、analysis-worker 均 HEALTHY。
- 两个 Worker 心跳真实存在并持续更新；没有写入虚假心跳。
- Champion 5/5 验证通过；Operations integrity 为 PASS。
- `DATA_READY=false`、`PAPER_READY=false`、`EVALUATION_READY=false`。
- 数据、账户、候选、Snapshot、QuantProposal、Order、Fill 和 EvaluationSubject 当前均
  未伪造或强制创建。
- 当前阻断项详见 `ALPHAGUARD_DATA_BRINGUP.md` 和执行状态文档。
