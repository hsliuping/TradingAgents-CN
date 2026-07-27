# AlphaGuard MVP 部署

## 组件

主 Compose 声明：

- `backend`：FastAPI、Scheduler 和受控运维任务消费者；
- `frontend`：Vue 3 管理界面；
- `queue-worker`：旧 Redis 队列兼容消费者；
- `analysis-worker`：现行分析任务消费者；
- `mongodb`：MongoDB 4.4；
- `redis`：Redis 7。

两套 Worker 是独立进程，但共用既有任务系统、MongoDB 和 Redis。不存在第二套后端、
数据库访问层或模型框架。

## 首次启动

1. 创建 `.env`，配置 MongoDB、Redis 和模型提供商，不要把密钥提交到 Git。
2. 先执行 dry-run：

   ```bash
   make init-dry-run
   make indexes-dry-run
   make backup-dry-run
   ```

3. 显式创建缺失索引：

   ```bash
   make init
   ```

   初始化器只创建缺失索引并读取准备度；不会生成候选、样本、账户、订单、实验或虚假
   Champion。

4. 启动：

   ```bash
   docker compose up -d --build
   docker compose ps
   ```

5. 验证：

   ```bash
   curl --fail http://localhost:8000/health/live
   curl --fail http://localhost:8000/health/ready
   .venv/bin/python scripts/alphaguard_readiness_report.py
   ```

6. 登录前端，进入 `/alphaguard/overview`。旧 `/paper` 仍是人工即时模拟交易，
   `/alphaguard/paper` 才是隔离的自动模拟账户展示。

## 就绪语义

- `READY_FOR_PAPER`：自动模拟所需的持久化数据与服务满足当前版本要求；
- `DEGRADED_PAPER`：自动模拟可用但存在非核心降级；
- `NOT_READY`：缺少交易日历、行情、账户、政策等业务数据；管理面仍可访问；
- `UNSAFE`：安全配置违反 PR-001；服务必须 fail-closed。

`live_ready` 和 `live_execution_allowed` 永远为 `false`。

## 升级

升级前：

```bash
.venv/bin/python scripts/alphaguard_backup.py \
  --execute --output backups/alphaguard-YYYYMMDD-HHMMSS
git status --short
```

升级后只运行 create-only 索引脚本，不删除旧索引或历史版本。已创建的 EvidenceSnapshot、
决策、订单、Fill、Lot 和 Champion history 必须继续引用原版本。

## 停止与回退

```bash
docker compose down
```

代码使用 `git revert <pr009-commit>` 形成可审计反向提交，不使用
`git reset --hard`。PR-009 新集合可保留，旧代码不会读取；需要数据恢复时遵循
[备份与恢复](ALPHAGUARD_BACKUP_RESTORE.md)。
