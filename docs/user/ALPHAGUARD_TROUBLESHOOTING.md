# AlphaGuard 故障排查

先判断异常是否影响核心安全链。通知、行业映射等可选能力降级时，页面仍可使用；DataQuality、模型
配置、HardRisk、账户一致性或执行幂等失败时必须停止相关任务，不得降低阈值绕过。

## 快速定位

1. 打开 `AlphaGuard -> 运维中心`；
2. 查看中文异常说明中的“发生了什么、是否影响核心功能、建议怎么处理”；
3. 再展开“高级信息”查看错误码、版本和 Hash；
4. 使用每日命令 `--status` 确认失败阶段；
5. 修复外部条件后用 `--resume`，不要删除状态记录或手工改成成功。

## 常见问题

| 现象 | 核心影响 | 处理 |
| --- | --- | --- |
| 通知显示降级或实时连接断开 | 否 | 页面可继续使用；最多重试 6 次。恢复服务后手动刷新或重新登录。 |
| 未读数显示 0 且 `DEGRADED` | 否 | 这是安全占位，不代表真实没有未读通知；不要据此清理消息。 |
| `UNAUTHENTICATED` | 通知停止 | 重新登录；Token 不应出现在 URL、日志或截图。 |
| `FORBIDDEN` | 通知停止 | 确认用户仍存在且处于启用状态；不要改用管理员硬编码身份。 |
| 非交易日全部 `SKIPPED` | 否 | 正常行为，不要强制执行后续阶段。 |
| `DATA_QUALITY_NOT_READY` | 是 | 修复 RAW/QFQ、交易状态、基准覆盖或版本连续性后恢复；不得绕过。 |
| 没有模型调用 | 通常否 | 检查 Proposal 是否自然 `TRIGGERED`；未触发时不调用模型是正确结果。 |
| `MODEL_FAILED` 或非法结构化输出 | 是 | 检查 Profile、Prompt、Credential、价格、预算和 Provider；不得降级成 HOLD。 |
| HardRisk 通过但没有订单 | 可能否 | 继续查看执行安全门、幂等键、T+1 和验证模式；HardRisk PASS 不等于订单。 |
| `RESUME_REQUIRED` | 暂停流程 | 用同一交易日和输入版本执行 `--resume`。 |
| `DEPENDENCY_NOT_COMPLETED` | 是 | 先恢复直接依赖；不要使用 `--from-stage` 跳过未完成依赖。 |
| 一致性 `WARNING` | 视检查项 | 查看卡住 Saga 或 Outbox 死信，运行既有幂等恢复任务后重查。 |
| 一致性 `FAIL` | 是 | 暂停订单/结算；生成报告并人工处理，系统不会自动修改正式数据。 |
| 备份 Secret 扫描失败 | 备份不可用 | 删除配置或文档中的 Secret，改用 Keychain `credential_ref`，重新创建新目录。 |
| Manifest Hash 不一致 | 备份不可用 | 不要恢复；从可信源重新创建备份。 |
| 隔离恢复目标非空 | 否 | 使用新的隔离数据库名；不要加正式覆盖参数。 |

## 任务中断或服务重启

重启 FastAPI、Scheduler 或 Worker 后：

```bash
.venv/bin/python scripts/alphaguard_daily_run.py \
  --trade-date 2026-08-03 --status
```

若存在未完成阶段：

```bash
.venv/bin/python scripts/alphaguard_daily_run.py \
  --trade-date 2026-08-03 --execute --resume
```

已完成阶段会 `REUSED`。如果账户、订单、Fill 或 Champion 在重启前后发生非预期变化，立即停止恢复，
保存只读快照并检查一致性；不要手工回写金额或删除 Fill。

## 通知排查

通知 WebSocket URL 固定为 `/api/ws/notifications`，JWT 通过 `Sec-WebSocket-Protocol` 传递。
浏览器最多执行 6 次指数退避，之后显示中文降级提示。REST 列表和未读数会返回
`service_status=READY/DEGRADED`；HTTP 200 不代表底层通知一定可用。

通知失败不会改变 Proposal、模型、HardRisk、OrderIntent、订单、成交或结算状态。

## 一致性排查

统一检查覆盖现金、冻结资金、持仓、订单/Fill 数量、Ledger 重建、Snapshot 和模型引用、决策链、
推荐接受、Challenger 隔离、Champion、索引、Reservation、重复 Fill、孤立 Position、Saga 和 Outbox。

报告只给证据和建议，`auto_repair_performed=false`。正式数据库失败不能由脚本自动修复。

## 获取帮助时可提供的信息

可以提供：错误码、阶段名、交易日期、脱敏后的版本、Hash、对象数量和 Operations 中文摘要。

不要提供：API Key、Cookie、JWT、`.env`、Keychain 内容、完整请求 Header、完整 WebSocket URL或模型
消息正文。

日常流程见 [AlphaGuard 每日运行手册](ALPHAGUARD_DAILY_OPERATIONS.md)，备份见
[AlphaGuard 备份与恢复](ALPHAGUARD_BACKUP_RESTORE.md)。
