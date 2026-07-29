# AlphaGuard 前端使用手册

## 两个环境

AlphaGuard 提供两个用途不同的本地入口：

| 环境 | 前端 | API | 数据边界 |
| --- | --- | --- | --- |
| 真实本地环境 | `http://localhost:3000/alphaguard/overview` | `http://localhost:8000` | 读取真实本地 MongoDB；自动模拟链保持 fail-closed |
| 隔离引导演示 | `http://localhost:3001/alphaguard/overview` | `http://127.0.0.1:8010` | 只使用 `alphaguard_ui_demo` 的固定场景；不启动 Scheduler 或 Worker |

演示环境顶部始终显示 `DEMO ENVIRONMENT`。其中的 OrderIntent、Fill、收益和实验结果都
是产品交互样例，不是正式模拟账户或投资结果。

## 启动真实环境

推荐使用现有 Compose 配置启动完整服务：

```bash
docker compose up -d --build
docker compose ps
curl --fail http://localhost:8000/health/live
curl --fail http://localhost:8000/health/ready
```

随后打开 `http://localhost:3000/alphaguard/overview`。登录用户名为
`alphaguard_admin`；密码从本机已有的安全保存位置取得并在登录页手工输入。不要把密码
写进脚本、文档或截图。

停止真实环境：

```bash
docker compose down
```

## 启动隔离演示

在项目根目录启动只读演示 API：

```bash
.venv/bin/python scripts/run_alphaguard_ui_demo.py
.venv/bin/python scripts/run_alphaguard_ui_demo.py --execute
```

第一条命令只打印隔离设置，不写数据库。第二条命令显式启动 API，并在独立数据库
`alphaguard_ui_demo` 中创建或复用一个不可变场景。

另开一个终端启动演示前端：

```bash
cd frontend
VITE_ALPHAGUARD_DEMO=true \
VITE_DEV_PORT=3001 \
VITE_API_PROXY_TARGET=http://127.0.0.1:8010 \
npm run dev -- --host 0.0.0.0
```

打开 `http://localhost:3001/login`，点击“进入隔离演示”。演示环境不接受真实账号密码，
也没有生产配置、任务或交易写入口。停止时在两个终端分别按 `Ctrl-C`。

## 推荐浏览顺序

### 1. 总览

总览回答“系统现在能做什么”。先查看：

- `DEGRADED_PAPER`、`READY_FOR_PAPER` 或 `NOT_READY`；
- Data、Paper、Evaluation、Regime、Experiment、Challenger 和 Live 准备度；
- 当前交易日、候选、Snapshot、Proposal、模型/风控到达数；
- 三个自动模拟账户与开放告警。

`DEGRADED_PAPER` 不等于系统崩溃。它表示管理面和部分自动模拟能力可运行，但缺少的
数据或版本条件继续安全阻断对应链路。`LIVE` 始终关闭。

### 2. 候选池

真实环境中的操作顺序是：输入 CN 股票代码，添加 `USER_SELECTED` 来源，系统规范化代码
并等待数据扫描与 Snapshot。列表中的状态含义：

- DataQuality `PASS`：当前版本引用满足下游计算要求；
- DataQuality `FAIL`：显示缺失字段和阻断原因，不调用后续模型；
- Snapshot：一次不可变、可追溯的数据切片；
- Proposal：策略对该 Snapshot 的结构化结果；
- 冷却或持仓状态：决定何时可再次扫描，不会删除历史对象。

点击候选行可查看 `raw_refs`、数据版本、不可变 hash 和 DataQuality 原因。移除
`USER_SELECTED` 只移除该来源，不删除历史 Snapshot、决策或评价。

### 3. 决策链

时间线按以下顺序展示真实到达情况：

```text
EvidenceSnapshot -> Factor -> MarketContext -> MarketRegime -> QuantProposal
-> NormalTradePlan -> TopReviewDecision -> ConsensusDecision
-> HardRiskDecision -> OrderIntent
```

点击任一阶段可查看状态、原因、对象 ID、hash、组件版本、trace、创建时间和证据引用。
`NOT_REACHED`、`INSUFFICIENT_DATA`、`MODEL_FAILED` 与 `REJECT` 都是不同状态，页面不会把
它们补成 `HOLD` 或 `PASS`。

Normal 是第一轮结构化交易计划；Top 独立复核计划和证据。Consensus 只判断两者是否形成
可执行一致意见；HardRisk 再执行不可绕过的账户、仓位、价格和市场安全检查。前一步通过
不代表后一步通过。

PR-010模型运行时将“TradingAgents 研究”、Normal、Top、Consensus和HardRisk作为独立阶段
显示。模型节点还会显示运行模式、Profile/Prompt版本、结构化输出模式以及脱敏后的失败
原因。研究角色未启用、供应商未配置、预算阻断或结构化输出非法时，后续节点保持未到达；
页面不会以默认模型、默认HOLD或猜测的配置继续执行。

## 为什么没有订单

只有合法 Proposal、Normal、Top、Consensus、HardRisk 和执行安全门全部通过，系统才会
创建 OrderIntent。数据不足、模型失败、意见不一致或硬风控拒绝时，订单数为 0 是正确
结果。不要通过修改状态、手工插入 Outbox 或降低阈值来制造交易。

## 自动模拟账户

`AlphaGuard -> 自动模拟` 展示：

- `PAPER_QUANT`：量化基准账户；
- `PAPER_NORMAL`：普通模型账户；
- `PAPER_TOP_CONFIRMED`：双模型确认且通过硬风控的账户。

它们与旧 `/paper` 人工模拟页面相互独立。AlphaGuard 页面不提供修改现金、手工建单、
修改成交价、修改持仓或绕过 T+1 的入口。通过账户切换和页签可查看持仓、T+1 lot、订单、
Fill、费用和日快照。

## 评价中心

评价页将三种口径分开：历史研究回放、正式生产决策评价、实际模拟成交评价。历史回放
收益不是账户收益。依次查看期限成熟、Factor、Regime、Strategy、MFE/MAE、沪深300相对
表现和归因。`PENDING_VERSION_DISCONTINUITY` 表示锁定价格版本不连续，需保留待处理，
不是页面加载失败。

## 实验室

实验室用于查看 Champion、单变量实验、泄漏审计、稳健性、Shadow、Challenger、比较报告
和人工晋升记录。它不会自动推荐、晋升或回退版本。当真实样本、泄漏审计、风险审查或
完整 Challenger 链不满足时，晋升操作必须禁用。

## 运维中心

遇到页面加载失败、数据不足、Worker stale、评价未成熟或完整性告警时进入运维中心。
依次查看服务、数据准备、任务、告警、模型运行、完整性与版本。只允许登记白名单幂等
任务；页面不提供环境变量编辑、任意 Shell、任意 Mongo 查询或 live 开关。

“模型运行”显示三个受控角色及其固定Profile、Prompt版本、Credential状态、Provider
能力、预算状态和最近运行摘要。管理员可以显式触发受控能力探测，但不能提交任意模型名、
Prompt或凭证。能力探测可能访问供应商并产生费用，提交前必须确认；普通用户只能查看。
前端不会显示、修改或传输API Key。凭证只能通过本机安全环境、Keychain映射或容器Secret
提供，不能写入数据库配置、日志或截图。

## 常见问题

- 登录后仍返回登录页：确认使用正确环境的账号方式，并检查 API 是否可达。
- 页面显示后端服务连接失败：运行健康检查，恢复 API 后点击“重试连接”。
- `DEGRADED_PAPER`：查看阻断项；不要手工修改准备度。
- Proposal 存在但没有模型结果：查看 Proposal 是否 `TRIGGERED`，以及模型供应商健康状态。
- HardRisk `PASS` 但没有订单：继续检查执行安全门、幂等身份和下一交易日。
- 演示页无法写入：这是设计边界；切换真实环境也只能使用已有的受控管理员接口。

验收截图位于 [`docs/ux/screenshots`](../ux/screenshots/)。生产运维细节见
[`ALPHAGUARD_RUNBOOK.md`](../operations/ALPHAGUARD_RUNBOOK.md)。

## 已验收边界

`alphaguard-frontend-acceptance-v1` 已通过真实浏览器验收。登录、退出、路由保护、总览、
五个候选及详情、完整决策时间线、三个自动模拟账户、T+1 lot、Fill与费用、评价筛选、
实验泄漏失败、禁用晋升、运维告警、404和API异常提示均已实际操作验证。

演示数据库只包含一条确定性 fixture；生产 Candidate、Snapshot、Proposal、账户、订单、
Fill、持仓和评价数量在演示前后保持不变。Demo 顶部横幅不可关闭，演示 API 不启动
Scheduler/Worker，也不提供生产写入口。演示数据不得用于投资判断或正式评价结论。

当前生产状态为 `DEGRADED_PAPER`，`CHALLENGER_READY=false`、`LIVE_READY=false`。
FastAPI和两个Worker继续在live配置下fail-closed。前端类型安全检查点
`alphaguard-frontend-type-safe` 已清除原34个 `DefaultRow TS2345`，正式
`npm run type-check`、`npm run build` 和 `npx vite build` 均通过。

模型运行时当前为Level A准备态：Profile、Prompt、Credential引用、能力探测、预算、
审计、严格结构化输出和前端可见性已就绪；三个真实Profile的供应商访问探测均返回脱敏的
认证失败，因此未执行付费结构化生成，也没有真实Normal→Top结果。Demo的模型状态是
`STRUCTURAL_FIXTURE_ONLY`，不属于真实模型效果或生产数据。
