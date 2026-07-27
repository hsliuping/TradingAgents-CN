# AlphaGuard MVP 验收清单（PR-009）

验收以真实运行状态为准，代码完成不等于数据或模拟交易已经就绪。

## 安全

- [x] `system_mode=SIM_AUTONOMOUS`
- [x] `live_trading_enabled=false`
- [x] FastAPI 在不安全配置下拒绝启动
- [x] 两套 Worker 在不安全配置下拒绝启动
- [x] 无 BrokerAdapter、券商 SDK、实盘开关和真实订单网络请求
- [x] `live_ready=false`、`live_execution_allowed=false`

## 运行

- [x] MongoDB 与 Redis 健康
- [x] FastAPI `/health/live` 为 200
- [x] `/health/ready` 能区分 READY、DEGRADED、NOT_READY、UNSAFE
- [ ] queue-worker 和 analysis-worker 均有新鲜 Redis 心跳
- [x] Scheduler 和 DB-backed 运维任务可见

## 数据准备

- [ ] CN 交易日历有明确覆盖范围
- [ ] QFQ 日线带版本和日期
- [ ] 原始行情、财务、新闻、公告、市场环境和历史行业数据可追溯
- [x] 模型提供商已配置但密钥不出现在 API、日志或页面
- [x] ChampionAssignment 唯一、哈希有效、版本存在
- [x] 缺失数据明确显示 NOT_READY，不自动补成中性或可交易

## 产品链路

- [x] `/alphaguard` 统一入口可访问
- [x] 候选池只允许用户添加/移除 `USER_SELECTED` 来源
- [x] Normal、Top、Consensus、Risk 四个结构化对象独立展示
- [x] 自动模拟四账户与旧人工 `/paper` 清晰隔离
- [x] 评价数据不足显示 `INSUFFICIENT_DATA`
- [x] 实验负面指标和失败 gate 可见
- [x] FULL_CHALLENGER_PIPELINE_NOT_READY 时不能伪造 Challenger
- [x] 管理员写操作有 403 权限闸门和审计

## 资产与完整性

- [x] 无负现金、负持仓
- [x] 无重复 Intent、Order、Fill 或 Settlement
- [x] Outbox Dead Letter 可见
- [x] Settlement/Promotion Saga 可恢复
- [x] 人工模拟集合未被自动链路修改
- [x] 取消/过期只释放预留，不改变净资产

## 脚本与回退

- [x] 初始化、索引、备份、恢复默认 dry-run
- [x] 索引脚本重复执行为 unchanged
- [x] 备份 manifest 和 SHA-256 验证通过
- [x] 默认恢复到新数据库
- [x] 当前库覆盖要求明确确认文本
- [x] 回退使用 `git revert`，不删除历史版本或业务记录

## 测试记录

- [x] PR-009 专测
- [x] PR-001～PR-008 精确回归
- [x] 全量 collect-only 与 15 个存量错误对比
- [x] 前端类型检查与 34 个存量 TS2345 对比
- [x] Python 编译
- [x] `git diff --check`
- [x] FastAPI/Worker 安全启动与阻断
- [x] Operations API 与 MVP smoke

只有证据齐全时才能勾选。当前真实数据为 0 的环节必须保持未勾选或
`INSUFFICIENT_DATA`，不能使用测试 fixture 填充生产集合。

2026-07-27 实测结论：`CODE_COMPLETE=true`，但 Worker 当前未部署且交易日历、QFQ、
财务、新闻、公告、市场环境和历史行业数据均为空，因此
`RUNTIME_READY=DEGRADED`、`DATA_READY=false`、`PAPER_READY=false`。以上未勾选项是
真实运行阻断，不是测试遗漏。
