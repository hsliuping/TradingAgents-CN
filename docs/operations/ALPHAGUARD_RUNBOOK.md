# AlphaGuard 运维手册

## 安全边界

AlphaGuard 仅支持研究与自动模拟交易。所有 FastAPI、队列 Worker 和分析 Worker 启动时
都必须满足：

```text
system_mode=SIM_AUTONOMOUS
live_trading_enabled=false
```

`RiskDecision PASS/REDUCE` 只是进入自动模拟执行链的资格，不是实盘订单。系统没有券商
适配器、实盘开关 API 或模拟转实盘路径。`/health/ready` 返回 `DEGRADED` 时管理页面仍可
使用；返回 HTTP 503 表示核心依赖故障或安全配置为 `UNSAFE`。

## 每日检查

```bash
make health
make readiness
docker compose ps
```

然后在 `AlphaGuard → 运维中心` 检查：

1. FastAPI、MongoDB、Redis、Scheduler、两套 Worker；
2. 交易日历、QFQ、原始行情、财务、新闻、公告、市场环境和行业历史；
3. Champion 指针、模型配置、评价样本和实验样本；
4. Outbox、撮合、结算、T+1、评价、实验与 Saga 恢复任务；
5. 负现金、负持仓、Dead Letter、卡住的 Settlement/Promotion Saga 和缺失索引。

不要把 `NOT_READY` 手工改成 READY。修复源数据或配置后，重新运行只读检查。

## 受控运维任务

管理员可以从运维中心登记以下 DB-backed 幂等任务：

- `HEALTH_CHECK`
- `DATA_READINESS_CHECK`
- `PAPER_RECONCILIATION`
- `EVALUATION_RECALCULATION`
- `EXPERIMENT_RECONCILIATION`
- `PROMOTION_SAGA_RECOVERY`
- `INTEGRITY_CHECK`

接口不接受脚本、函数名、配置覆盖或任意参数。任务先写
`ag_ops_job_requests`，调度器消费；重复 idempotency key 不会重复执行。

## 告警处置

同一 `category + code + source + source_object` 会聚合为一个告警并累计次数。管理员可以：

1. 确认告警；
2. 修复真实原因；
3. 填写至少 3 个字符的解决说明；
4. 重新运行健康或数据准备检查。

解决不会删除历史。相同问题再次出现时会重新打开，并追加 `ag_ops_events` 审计。
运维返回值和错误会递归脱敏，不展示 API Key、Token、密码、Cookie 或认证头。

## 常见故障

### `TRADING_CALENDAR_MISSING`

自动模拟、T+1、评价和 Champion 生效日期都不能用自然日猜测。补齐持久化 CN 交易日历后
重跑准备度检查。

### `QFQ_DATA_MISSING`

评价与历史重放要求带 `price_adjustment_mode=QFQ` 和 `price_data_version` 的日线数据。
不要用最新实时价或未版本化价格替代。

### Worker `DEGRADED / WORKER_STALE`

检查 `queue-worker` 与 `analysis-worker` 容器。心跳使用 Redis TTL；重启前先确认没有正在
处理的任务，避免误判为挂起。Worker 在不安全实盘配置下必须拒绝启动。

### `PROMOTION_SAGA_INCOMPLETE` 或 `settlement_saga_stuck`

不要直接改状态。通过受控 Saga recovery/reconciliation 任务恢复，并核对不可变事件、
账本和 Champion history。MongoDB 4.4 standalone 不支持当前工程所需的多文档事务，
所以这些链路使用可恢复 Saga。

### `FULL_CHALLENGER_PIPELINE_NOT_READY`

这是 PR-008 的明确 fail-closed 限制。可以查看确定性实验、重放和 Shadow，但不得伪造
PAPER_CHALLENGER 样本或跳过完整双模型/Consensus/HardRisk 隔离链。

## 发布前检查

```bash
make test-pr009
make type-check
make smoke
git diff --check
```

前端当前有 34 个上游 `DefaultRow TS2345` 存量错误；只有错误数量与类别均未增加时才可
视为 PR-009 未引入新类型回归。全量测试收集的 15 个既有错误也必须单独记录，不能宣称
全量通过。
