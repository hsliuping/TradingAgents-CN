# AlphaGuard 快速开始

## 1. 启动

真实本地环境：

```bash
docker compose up -d --build
docker compose ps
```

隔离演示需要两个终端：

```bash
.venv/bin/python scripts/run_alphaguard_ui_demo.py --execute
```

```bash
cd frontend
VITE_ALPHAGUARD_DEMO=true VITE_DEV_PORT=3001 \
VITE_API_PROXY_TARGET=http://127.0.0.1:8010 npm run dev -- --host 0.0.0.0
```

## 2. 登录

- 真实环境：打开 `http://localhost:3000/login`，用户名 `alphaguard_admin`，手工输入本机
  安全保存的密码。
- 演示环境：打开 `http://localhost:3001/login`，点击“进入隔离演示”，不输入真实密码。

## 3. 查看总览

进入 `AlphaGuard -> 总览`。先看整体准备度、当前交易日、候选和 Snapshot 数量，以及
`LIVE = NOT READY`。`DEGRADED_PAPER` 表示部分能力安全关闭，不代表整个系统故障。

## 4. 打开候选

进入“候选池”，点击任一股票行。查看 DataQuality、Snapshot ID、数据版本、hash 和缺失
字段。演示中的 `600519` 展示 DataQuality fail-closed。

## 5. 查看决策

进入“决策链”。选择 `300750` 可查看演示的完整
Quant -> Normal -> Top -> Consensus -> HardRisk -> OrderIntent 路径；其他标的展示 WATCH、
Top 拒绝或 HardRisk 拒绝。时间线中的“TradingAgents 研究”与 Normal/Top 分开显示；
`NOT_REACHED`、`MODEL_FAILED` 和 `INVALID_OUTPUT` 不会被页面补成 HOLD。

## 6. 查看模拟账户

进入“自动模拟”，切换量化基准、普通模型和双模型确认账户。再查看持仓、T+1 lot、订单
与成交费用。演示结果不是正式账户收益。

## 7. 查看评价

进入“评价中心”，切换期限成熟、Factor、Regime、Strategy 和归因页签。历史研究回放与
实际模拟成交始终分开展示。

## 8. 查看系统健康与配置模型凭证

进入“运维中心”，依次查看服务、数据准备、任务、告警、Models & API、完整性与版本。
“Models & API”展示服务商、API凭证、模型目录、模型Profile、Prompt版本、价格、预算、
能力检查和调用记录。普通用户只能查看状态；管理员可以登记OpenAI-Compatible Endpoint，
再把对应API Key直接提交给本机后端并写入macOS Keychain。页面不会显示已保存Key，输入
在提交开始时立即清空，浏览器不保存Key或直接访问任何模型Provider。

Compose后端运行在容器内，不能访问宿主Keychain，因此凭证表单会安全禁用。配置凭证时在
项目根目录启动本机API：

```bash
.venv/bin/python scripts/run_alphaguard_credential_host.py --execute
```

另开一个终端启动对应前端：

```bash
cd frontend
VITE_DEV_PORT=3002 \
VITE_API_PROXY_TARGET=http://127.0.0.1:8011 \
VITE_ALPHAGUARD_CREDENTIAL_HOST=true \
npm run dev -- --host 127.0.0.1
```

打开 `http://localhost:3002/login`，手工登录后进入
`AlphaGuard -> 运维中心 -> Models & API`。第三方服务按以下顺序登记：

1. 在“1. 服务商”选择已有Endpoint继续配置，或新增OpenAI-Compatible DRAFT；
2. 明确确认第三方数据发送并通过URL安全验证；
3. 在“2. API凭证”选择已验证Endpoint，填写新Key并保存到Keychain；
4. 在“3. 模型目录”受控探测`/models`或手工登记模型及实际能力；
5. 在“4. 价格”登记该Endpoint独立的Decimal价格版本；
6. 在“5. 模型Profile”分别分配Normal与Top；使用同一模型时必须显式确认；
7. 在“6. 能力检查”查看Normal/Top结构化输出、usage、费用和预算状态。

配置变更使用“创建新版本”，旧Endpoint版本不会被覆盖；DRAFT未通过URL验证前不能进入
凭证配置。凭证先通过Endpoint认证但尚未登记模型或价格时显示`DEGRADED`属于预期状态；
继续完成模型目录、价格和Profile后再执行完整能力检查。

选择Endpoint版本后先看页面顶部“配置完整性”。兼容Credential默认名称包含Endpoint版本；
不要把v2名称复用于v4。任何步骤失败都会显示脱敏的HTTP状态、错误代码和摘要，并且刷新后
仍以数据库真实状态为准。`URL_VALIDATED`、`UNVERIFIED`或`DEGRADED`都是可继续配置的安全
中间状态，不等于READY，也不会触发付费模型调用。

不要把Key发到聊天、终端参数、文档或截图中；已经暴露过的Key不可恢复或复用。真实环境
健康检查仍可运行：

```bash
curl --fail http://localhost:8000/health/live
curl --fail http://localhost:8000/health/ready
```

停止真实环境使用 `docker compose down`；停止演示环境时在两个演示终端分别按 `Ctrl-C`。

## 9. 每日运行、错误与备份

盘后统一任务在 18:40 按 20 个显式依赖阶段运行。普通用户在“运维中心”查看中文状态；管理员
需要手工预览或恢复时使用默认 dry-run 的统一入口：

```bash
.venv/bin/python scripts/alphaguard_daily_run.py --trade-date 2026-08-03
.venv/bin/python scripts/alphaguard_daily_run.py --trade-date 2026-08-03 --status
```

不要使用 live 参数，也不要为了验收强制产生模型调用、买入或成交。详细步骤见：

- [每日运行手册](ALPHAGUARD_DAILY_OPERATIONS.md)
- [备份与恢复](ALPHAGUARD_BACKUP_RESTORE.md)
- [故障排查](ALPHAGUARD_TROUBLESHOOTING.md)

## 当前验收状态

- 前端验收检查点：`alphaguard-frontend-acceptance-v1`；
- MVP 运行封板提供统一日常编排、恢复、备份、隔离恢复和中文验收矩阵；
- `ACTIVE_CHALLENGER=false`、`AUTO_CANDIDATE_ACCEPT=false`、`LIVE_READY=false`，页面没有实盘入口；
- 演示数据库与生产数据库完全隔离，演示中的订单、成交和收益不是生产数据；
- 前端类型安全检查点 `alphaguard-frontend-type-safe` 已清除原34个
  `DefaultRow TS2345`；`npm run type-check`、正式 `npm run build` 和
  `npx vite build` 均可通过；
- PR-010 已保存真实双模型 Level B 证据；日常任务仍只在 Proposal 自然触发且全部配置门禁通过时
  调用模型，不会为验收制造新调用；
- API Key只能在本机安全后端对应的“API凭证”表单中手工输入，不要发送到聊天、终端参数、
  文档或截图中。

验收截图位于 [`docs/ux/screenshots`](../ux/screenshots/)，完整说明见
[`ALPHAGUARD_FRONTEND_GUIDE.md`](ALPHAGUARD_FRONTEND_GUIDE.md)。
