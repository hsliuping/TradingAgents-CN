# AlphaGuard 每日运行手册

本手册面向日常操作者。AlphaGuard 当前只运行自动模拟交易：`system_mode=SIM_AUTONOMOUS`、
`live_trading_enabled=false`。任何 `--live`、`--live=true` 或 `live=true` 都会被拒绝。

## 每日检查顺序

盘后统一任务 `alphaguard_daily_run` 默认在 Asia/Shanghai 18:40 运行。它按固定依赖执行：

| 阶段 | 内容 | 前置条件 |
| --- | --- | --- |
| 1 | 交易日历确认 | 无 |
| 2 | 证券基础数据同步 | 交易日历完成 |
| 3 | RAW/QFQ 行情同步 | 证券同步完成 |
| 4 | 基准和行业数据同步 | 行情同步完成 |
| 5 | 交易状态同步 | 基准与行业完成 |
| 6 | DataQuality | 交易状态完成 |
| 7 | 推荐数据覆盖 | DataQuality 通过 |
| 8 | 全市场推荐 | 覆盖门禁通过 |
| 9 | 候选池 Snapshot | 推荐完成；只处理用户已确认候选 |
| 10 | Factor 与 Regime | Snapshot 完成 |
| 11 | QuantProposal | Factor 与 Regime 完成 |
| 12 | TradingAgents 与双模型链 | Proposal 自然满足触发条件 |
| 13 | OrderIntent 安全门 | 模型链到达并通过既有门禁 |
| 14 | 次交易日订单处理 | OrderIntent 阶段完成 |
| 15 | 撮合与结算 | T+1 处理完成 |
| 16 | Evaluation | 撮合与结算完成 |
| 17 | Attribution | Evaluation 完成 |
| 18 | Challenger | Attribution 完成 |
| 19 | Operations 汇总与一致性 | Challenger 完成 |
| 20 | 通知 | 核心链完成；通知失败只降级通知 |

非交易日从第 1 阶段开始安全跳过，不会同步、调用模型或创建订单。任何依赖失败都会阻断后续阶段。

## 一键预览与执行

默认命令是 dry-run，不连接执行器、不写业务对象：

```bash
.venv/bin/python scripts/alphaguard_daily_run.py --trade-date 2026-08-03
```

查看同一交易日和输入版本的持久化状态：

```bash
.venv/bin/python scripts/alphaguard_daily_run.py \
  --trade-date 2026-08-03 --status
```

只有确认数据库、Redis、数据源和模型配置属于目标环境后，才显式执行：

```bash
.venv/bin/python scripts/alphaguard_daily_run.py \
  --trade-date 2026-08-03 --execute
```

执行会访问现有数据源并写入既有 AlphaGuard 模拟运行集合。不要在正式环境用它制造推荐、候选、
模型结果或交易；正式验收只读。

## 安全恢复

检测到 `RUNNING`、`FAILED` 或 `BLOCKED` 阶段时，普通执行会要求恢复。使用：

```bash
.venv/bin/python scripts/alphaguard_daily_run.py \
  --trade-date 2026-08-03 --execute --resume
```

相同交易日、相同输入版本和相同阶段的身份固定。已经完成的阶段显示 `REUSED`，不会重复同步、
调用模型、下单或成交。只检查某一安全区间时使用阶段英文名：

```bash
.venv/bin/python scripts/alphaguard_daily_run.py \
  --trade-date 2026-08-03 --execute --resume \
  --from-stage EVALUATION --to-stage NOTIFICATION
```

区间的第一个阶段仍会核对区间外的直接依赖；依赖未完成时不会继续。

## 查看结果

命令行按“数据同步、推荐、候选池、决策、模型、风控、订单、评价、异常”输出中文摘要。
前端进入 `AlphaGuard -> 运维中心`，重点查看：

- “MVP 验收状态”：每个模块的可用、降级、未就绪或阻断状态；
- “今日运行”：最近任务、失败阶段和恢复提示；
- “一致性状态”：只报告，不自动修复正式数据；
- “通知状态”：连接、最后成功时间、重试次数和降级状态；
- “高级信息”：需要排障时再查看 ID、版本、Hash 和错误码。

没有模型调用、订单或成交不一定是错误。Proposal 未触发、模型拒绝、Consensus 不一致、HardRisk
拒绝或执行安全门阻断时，零订单是正确结果。

## 暂停、恢复和安全关闭

管理员可进入 `系统设置 -> 定时任务`，找到 `alphaguard_daily_run` 后暂停或恢复。暂停统一任务不会
改变账户、持仓、Champion 或 Challenger。不要通过删除任务记录来“恢复”。

安全关闭完整环境：

```bash
docker compose down
```

关闭前先确认没有阶段处于 `RUNNING`；若进程被迫中断，重启后使用 `--status` 和 `--resume`。

## 每日操作清单

1. 查看 `/health/live` 与 `/health/ready`；
2. 确认 `LIVE_READY=false`、`ACTIVE_CHALLENGER=false`；
3. 查看 18:40 统一任务状态；
4. 只在需要时执行 `--resume`；
5. 查看 DataQuality、推荐、候选、模型、订单、评价和一致性；
6. 确认通知降级没有被误报为核心交易故障；
7. 按备份手册创建并校验本机备份；
8. 安全关闭前确认任务没有运行中状态。

备份见 [AlphaGuard 备份与恢复](ALPHAGUARD_BACKUP_RESTORE.md)，异常处理见
[AlphaGuard 故障排查](ALPHAGUARD_TROUBLESHOOTING.md)。
