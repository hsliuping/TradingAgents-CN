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

## 8. 查看系统健康

进入“运维中心”，依次查看服务、数据准备、任务、告警、模型运行、完整性与版本。
“模型运行”只展示已登记的 Profile、Prompt、能力状态、预算和脱敏错误，不展示或接收
API Key。真实环境也可运行：

```bash
curl --fail http://localhost:8000/health/live
curl --fail http://localhost:8000/health/ready
```

停止真实环境使用 `docker compose down`；停止演示环境时在两个演示终端分别按 `Ctrl-C`。

## 当前验收状态

- 前端验收检查点：`alphaguard-frontend-acceptance-v1`；
- 真实系统状态：`DEGRADED_PAPER`，表示部分能力安全关闭，不是系统故障；
- `CHALLENGER_READY=false`、`LIVE_READY=false`，页面没有实盘入口；
- 演示数据库与生产数据库完全隔离，演示中的订单、成交和收益不是生产数据；
- 前端类型安全检查点 `alphaguard-frontend-type-safe` 已清除原34个
  `DefaultRow TS2345`；`npm run type-check`、正式 `npm run build` 和
  `npx vite build` 均可通过；
- 模型运行时目前只达到 Level A：三个登记Profile的真实供应商访问探测均因认证失败而
  fail-closed，未产生模型结果、订单或账户变动。不要在页面、文档或命令行参数中输入
  API Key。

验收截图位于 [`docs/ux/screenshots`](../ux/screenshots/)，完整说明见
[`ALPHAGUARD_FRONTEND_GUIDE.md`](ALPHAGUARD_FRONTEND_GUIDE.md)。
