# AlphaGuard Codex Execution Status

## 当前状态

- 更新时间：2026-07-27 20:50 CST（Asia/Shanghai）
- 当前阶段：AlphaGuard Real Data Activation（不是 PR-010）
- 阶段状态：真实数据激活完成；市场环境与成熟评价样本仍按真实状态保持 NOT_READY
- PR-001 检查点提交：`5c6ae8f`
- PR-001 检查点标签：`alphaguard-pr001-baseline`
- PR-002 检查点提交：`09567a1`
- PR-002 检查点标签：`alphaguard-pr002-structured-decision`
- PR-003 检查点提交：`21e9792`
- PR-003 检查点标签：`alphaguard-pr003-candidate-evidence`
- PR-004 检查点提交：`87026f5`
- PR-004 检查点标签：`alphaguard-pr004-quant-research`
- PR-005 检查点提交：`76f62e5`
- PR-005 检查点标签：`alphaguard-pr005-consensus-risk`
- PR-006 检查点标签：`alphaguard-pr006-automatic-paper`
- PR-009 检查点提交：`1d1608937a2c950040bd5346db138b3fddf0bd1c`
- PR-009 检查点标签：`alphaguard-pr009-mvp`
- MVP Runtime Bring-up 提交：`943560f`
- MVP Runtime Bring-up 标签：`alphaguard-bringup-runtime-ready`
- 后续阶段：PR-010 未开始
- 固定安全模式：`system_mode=SIM_AUTONOMOUS`
- 实盘开关：`live_trading_enabled=false`
- 数据迁移：未迁移人工模拟账户、现金、持仓、订单或成交数据
- 数据库迁移/新集合：新增 16 个 PR-006 自动模拟集合及 49 个 create-only 索引
- MongoDB 文档变化：PR-006 仅建索引；政策、账户和自动交易文档仍为 0
- 公开 API：新增 10 个认证只读端点和 1 个受控取消端点；无公共创建订单/成交/结算 API

## 基线来源

- 上游仓库：`https://github.com/hsliuping/TradingAgents-CN`
- 上游分支：`main`
- 基线提交：`74783e8817d6cf6de29867880631cc555153f36b`
- 基线提交时间：`2026-07-24T10:27:21+08:00`
- 基线提交说明：`docs: 添加 v1.1.0 发布说明文档`
- 主实施计划来源：`/Users/banana/Downloads/AlphaGuard_MASTER_IMPLEMENTATION_PLAN.md`
- 项目内主实施计划：`docs/refactor/MASTER_IMPLEMENTATION_PLAN.md`
- 主实施计划 SHA-256：`c87f1516a3eafd93424d0a3eb81a71a1129c0df895d5cb5128ec5a58e205b292`
- 两份主实施计划已通过逐字节比较，内容一致。

当前项目目录在任务开始时没有 TradingAgents-CN 源码。为执行源码级检查和
PR-001，已将上述官方提交作为当前项目的可追溯基线导入。

## 已阅读范围

### 总控、部署和配置

- `docs/refactor/MASTER_IMPLEMENTATION_PLAN.md`
- `README.md`
- `docker-compose.yml`
- `.env.example`
- `pyproject.toml`
- `tests/pytest.ini`
- `frontend/package.json`

### 后端、任务和配置入口

- `app/main.py`
- `app/core/config.py`
- `app/core/startup_validator.py`
- `app/worker.py`
- `app/worker/analysis_worker.py`
- `app/routers/system_config.py`
- `tests/test_config_system.py`

### TradingAgents 多智能体

- `tradingagents/graph/trading_graph.py`
- `tradingagents/graph/setup.py`
- `tradingagents/graph/signal_processing.py`
- `tradingagents/agents/trader/trader.py`
- `tradingagents/agents/managers/risk_manager.py`

### 模拟交易和自选股

- `app/routers/paper.py`
- `app/routers/favorites.py`
- `app/services/favorites_service.py`
- `frontend/src/api/paper.ts`
- `frontend/src/api/favorites.ts`
- `frontend/src/views/PaperTrading/index.vue`
- `frontend/src/views/Favorites/index.vue`

## PR-001 前运行基线

### 环境

- macOS，Apple Silicon
- Python：系统 Python 3.9.6；验证环境 Python 3.10.20
- Node.js：v26.0.0
- npm：11.12.1
- Docker：29.4.3
- Docker Compose：5.1.3
- pytest：8.4.2

锁定依赖不能在当前 macOS 上直接安装：

1. Python 3.12 被 `backports.asyncio.runner==1.2.0` 的 Python 版本约束阻断；
2. Python 3.10 被无条件 Windows 依赖 `pywin32==311` 阻断。

因此验证环境使用 Python 3.10，并按 `pyproject.toml` 的声明依赖安装。PR-001
没有修改依赖或锁文件。

### 服务启动

- MongoDB `mongo:4.4`：启动成功，健康检查通过，端口 27017。
- Redis `redis:7-alpine`：启动成功，健康检查通过，端口 6379。
- FastAPI：真实启动成功，`GET /api/health` 返回 HTTP 200。
- Vue/Vite：开发服务器启动成功，首页返回 HTTP 200。
- `npm exec vite build`：成功。
- `npm run type-check`：失败，存在多处上游 TypeScript 存量错误。

FastAPI 启动会自动访问外部行情源并执行股票基础信息同步；关闭 Uvicorn 后，
后台同步任务可能继续持有进程。这是上游现存启动/退出副作用。

### 测试基线

1. 标准命令 `.venv/bin/python -m pytest`
   - 根配置会收集 `scripts/` 和 `examples/` 中的联网、交互脚本；
   - 收集到 197 项，出现 12 个收集错误；
   - 持续访问行情接口，312.50 秒后人工中断；
   - 错误包括已删除模块、旧 `webapi` 导入、联网失败及从 stdin 读取。
2. 显式限定 `.venv/bin/python -m pytest -c tests/pytest.ini tests`
   - 收集到 698 项；
   - 15 个收集错误，2 个跳过；
   - 未进入执行阶段；
   - 主要原因是旧导入路径和已不存在的模块。

## PR-001 实际改动

- `.env.example`
  - 增加 AlphaGuard 两个显式安全默认值。
- `app/core/alphaguard_config.py`
  - 新增独立 Pydantic Settings 配置；
  - PR-001 仅接受 `SIM_AUTONOMOUS`；
  - `live_trading_enabled=true` 时 fail-closed；
  - 无缓存加载，API 和 Worker 启动时读取当前进程环境。
- `app/core/startup_validator.py`
  - 将 AlphaGuard 校验接入现有 FastAPI 启动验证；
  - 不安全配置进入现有 `invalid_configs` 并阻止 lifespan 启动。
- `app/worker.py`
  - 在导入数据库/队列实现前执行 AlphaGuard 安全校验。
- `app/worker/analysis_worker.py`
  - 在导入数据库/队列/分析服务前执行 AlphaGuard 安全校验。
- `tests/unit/test_alphaguard_baseline_guard.py`
  - 覆盖默认值、安全启动、未知模式、实盘开关和现有验证器集成。
- `docs/refactor/MASTER_IMPLEMENTATION_PLAN.md`
  - 保存总控实施计划的逐字节一致副本。
- `docs/refactor/CODEX_EXECUTION_STATUS.md`
  - 记录本基线、改动、测试和回退信息。

## PR-001 后验证

| 验证项 | 结果 |
| --- | --- |
| AlphaGuard 与现有配置相关测试 | `24 passed, 9 warnings`，0.25 秒 |
| Python `compileall`（改动文件） | 通过 |
| `git diff --check` | 通过 |
| 安全配置 API 启动 | 通过，`GET /api/health` HTTP 200 |
| `live_trading_enabled=true` API 启动 | 被拒绝，进程非零退出 |
| `live_trading_enabled=true` 两套 Worker 启动 | 均在任务资源初始化前被拒绝 |
| 限定 `tests/` 的全量收集 | 703 项，仍为同一组 15 个存量错误，2 个跳过 |
| MongoDB / Redis | 均保持 healthy |

收集总数增加 5，正好对应新增的 5 个 AlphaGuard 测试；收集错误数量和错误文件
与 PR-001 前一致。

## 明确未改范围

- 未修改 TradingAgents Graph、Trader、Risk Manager 或 SignalProcessor。
- 未修改自由文本决策、默认 HOLD、目标价推算等 PR-002 范围。
- 未新增因子、策略、候选池、自动订单或券商适配器。
- 未修改人工模拟交易和自选股的现有行为或公开接口。
- 未引入 PostgreSQL、Dify、Qlib、FinRL 或其他大型依赖。
- 未修复与 PR-001 无关的测试、TypeScript、依赖锁或启动同步问题。

## 已知存量风险

- FastAPI 和 `analysis_worker.py` 的部分上游导入在正式 lifespan/main 之前会连接
  MongoDB/Redis；AlphaGuard 已在任何任务或交易工作开始前阻断，但上游导入副作用
  仍值得后续单独治理。
- 两套 Worker 入口职责重叠。
- pytest 的默认收集范围会执行联网/交互脚本。
- 测试目录有 15 个旧模块/旧路径收集错误。
- 前端类型检查不通过，但开发服务器和 Vite 构建可运行。
- 启动时自动数据同步会产生网络与数据库副作用，并可能延迟进程退出。
- `SignalProcessor` 的默认 HOLD、猜测目标价等风险属于 PR-002，尚未处理。
- 人工模拟交易即时成交以及 favorites 字段契约风险均保持原状。
- README 对 `app/` 和 `frontend/` 描述了额外商用许可约束。

## 回退方案

本阶段没有数据库迁移、schema 变更、订单写入或公开 API 变更。独立回退步骤：

1. 恢复 `.env.example`、`app/core/startup_validator.py`、`app/worker.py`、
   `app/worker/analysis_worker.py` 到基线提交；
2. 删除 `app/core/alphaguard_config.py` 和
   `tests/unit/test_alphaguard_baseline_guard.py`；
3. 如需完整撤销文档阶段，再删除 `docs/refactor/`；否则建议保留总控计划和本记录；
4. 重新验证 MongoDB、Redis、FastAPI 健康检查及 Vite 启动；
5. 重新运行限定 `tests/` 的收集，预期恢复为 698 项、15 个存量收集错误、
   2 个跳过。

## PR-002 Structured Decision Foundation

### 阶段状态

- PR-002 实现完成，专项测试、PR-001 安全回归和运行态安全验证均已完成。
- PR-001 的安全不变量保持不变：
  - `system_mode=SIM_AUTONOMOUS`
  - `live_trading_enabled=false`
  - FastAPI 与两套 Worker 继续 fail-closed。
- 没有实施 PR-003 或任何后续模块。

### 新增文件

- `tradingagents/alphaguard/__init__.py`
- `tradingagents/alphaguard/decision_schemas.py`
- `tradingagents/alphaguard/structured_output.py`
- `tests/unit/alphaguard/test_decision_schemas.py`
- `tests/unit/alphaguard/test_structured_nodes.py`
- `tests/unit/alphaguard/test_signal_processor_structured.py`
- `tests/integration/test_alphaguard_structured_decision_graph.py`

### 修改文件

- `tradingagents/agents/trader/trader.py`
- `tradingagents/agents/managers/risk_manager.py`
- `tradingagents/agents/managers/research_manager.py`
- `tradingagents/agents/utils/agent_states.py`
- `tradingagents/graph/propagation.py`
- `tradingagents/graph/setup.py`
- `tradingagents/graph/trading_graph.py`
- `tradingagents/graph/signal_processing.py`
- `app/services/simple_analysis_service.py`
- `web/utils/analysis_runner.py`
- `docs/refactor/CODEX_EXECUTION_STATUS.md`

Research Manager 仅移除了“必须生成具体目标价”的直接上游约束；没有重写其投资
辩论逻辑。服务和 Web 工具仅扩展结构化结果持久化/只读展示兼容，没有视觉改造。

### 正式结构化调用链

```text
Research Manager legacy investment_plan（上下文/报告）
    ↓
Trader 单次模型调用
    ↓ 严格 JSON / provider-native structured output
Pydantic NormalTradePlan
    ↓ AgentState.normal_trade_plan
风险辩论（只保留人工可读讨论）
    ↓
Risk Judge 单次模型调用（显式读取 NormalTradePlan）
    ↓ 严格 JSON / provider-native structured output
Pydantic TopReviewDecision
    ↓ AgentState.top_review_decision
结构化状态日志 + MongoDB 分析记录
    ↓ 单向只读转换
LegacyDecisionAdapter（旧页面/API/报告展示，不可自动执行）
```

`final_trade_decision` 和 `trader_investment_plan` 仍存在，但现在是由已校验对象确定性
渲染的展示文本。它们不能反向覆盖结构化对象，也不再作为机器方向来源。

### NormalTradePlan

实现字段：

- 来源：`plan_id`、`snapshot_id`、`quant_proposal_id`
- 决策：`status`、`action`、`confidence`、`thesis`
- 证据：`bullish_evidence`、`bearish_evidence`
- 价格/仓位：`entry_zone`、`initial_position_pct`、`max_position_pct`、
  `target_price`、`valid_until`
- 条件：`add_conditions`、`stop_conditions`、`reduce_conditions`、
  `exit_conditions`、`invalidation_conditions`
- 风险：`main_risks`、`unresolved_questions`
- 审计：`model_meta`
- 显式缺省说明：`entry_zone_not_required_reason`、
  `valid_until_compatibility_reason`

语义校验包括数值范围、区间顺序、初始/最大仓位关系、status/action 对应、交易计划
完整性、BUY 入场区间的显式例外、有效期的显式兼容说明，以及失败状态不得携带
可执行价格/仓位字段。`target_price=None` 合法且不会改变 action。

PR-003 尚未建立 EvidenceSnapshot 和 QuantTradeProposal，因此：

- `snapshot_id=legacy-analysis:<analysis_id>`
- `quant_proposal_id=legacy-quant:none`

这是可见的兼容占位，不使用空字符串隐藏来源缺失；只能在 PR-003 建立真实快照后
替换。

### TopReviewDecision

实现字段：

- 来源：`review_id`、`snapshot_id`、`plan_id`
- 状态与评分：`status`、`completeness_score`、
  `logic_consistency_score`、`risk_control_score`
- 发现：`missing_evidence`、`logical_conflicts`、`risk_findings`
- 调整：`adjusted_plan`、`material_change_fields`
- 理由和审计：`review_reason`、`model_meta`

语义校验保证评分在 0 至 1；`RISK_ADJUST` 必须带调整计划；
`MATERIAL_REVISION` 必须带调整计划和重大变更字段；拒绝、暂停和失败状态不能产生
新可执行计划。终审与原计划还执行引用关系和方向约束：不能从非交易计划独立发起
交易，也不能把原 BUY 反转成 SELL/REDUCE，反之亦然。

本阶段没有实现 `ConsensusEngine` 或任何 Python 双模型一致性裁决。

### Prompt 和模型执行审计

- Trader Prompt：`normal_trade_plan@normal_trade_plan_v1`
- Risk Judge Prompt：`top_review_decision@top_review_decision_v1`
- `ModelExecutionMeta` 保存：
  - `provider`
  - `model_name`
  - `model_version`
  - `prompt_name`
  - `prompt_version`
  - `started_at`
  - `finished_at`
  - `latency_ms`
  - `execution_status`
  - `request_id` / `trace_id`
  - `error_type`
  - `error_message`
  - `raw_output_hash`

模型名称/版本来自实际节点配置或适配器属性；Prompt 使用固定常量版本，不使用
`latest`。运行时字段由 Python 注入，模型不能自行生成或覆盖。原始输出不写入节点
日志，只保存 SHA-256；错误文本会对 API Key、认证头、Bearer/Token 和常见
`sk-...` 值脱敏。

原生 `with_structured_output` 可用时优先使用；无法构造原生结构化 runnable 时退回
一次严格 JSON 调用。不会再调用第二个 LLM 解释第一轮文本，也不使用正则提取
JSON 或交易方向。

### 统一错误行为

- 模型超时：`MODEL_FAILED` + `MODEL_TIMEOUT`
- 供应商异常：`MODEL_FAILED` + `PROVIDER_ERROR`
- 空响应：`MODEL_FAILED` + `EMPTY_RESPONSE`
- 非法 JSON：`INVALID_OUTPUT` + `MALFORMED_JSON`
- Schema/语义错误：`INVALID_OUTPUT` + `SCHEMA_VALIDATION_ERROR`
- 缺失普通结构化计划：
  `INVALID_OUTPUT` + `MISSING_OR_INVALID_NORMAL_PLAN`
- 上游 Trader 失败：Risk Judge 不运行并生成 `SUSPEND`，原
  `decision_error` 保留贯穿 Graph

失败状态统一使用 `action=NONE` 或旧接口的“不可执行”，不会变成 HOLD、WAIT 或
NO_TRADE。

### SignalProcessor 与兼容层

已从正式决策路径移除：

- 空文本默认 HOLD；
- 无法识别时默认 HOLD；
- 正则猜测 BUY/SELL/HOLD；
- 第二次 LLM 调用解析终审文本；
- 正则抽取 JSON；
- 缺少目标价时从文本猜价；
- 按当前价、涨跌幅或固定系数生成目标价；
- 解析失败后补出可交易结果。

`SignalProcessor.process_signal()` 作为旧导入兼容入口保留，但任何文本输入都会得到
显式 `INVALID_OUTPUT/不可执行`，不会调用 LLM 或正则。正式 Graph 只调用
`process_structured()`。

`LegacyDecisionAdapter` 的用途仅限旧前端展示、旧 API 响应、人工报告和历史读取。
每个结果均包含：

- `compatibility_only=true`
- `not_for_automated_execution=true`
- `automated_execution_allowed=false`

目标价只从已校验计划直接投影；`None` 原样保留。兼容对象不得作为未来自动下单、
Consensus 或 HardRisk 输入。

### AgentState 与持久化

新增状态字段：

- `normal_trade_plan`
- `top_review_decision`
- `decision_error`
- `normal_model_meta`
- `top_model_meta`
- `analysis_id`

Propagation 显式初始化这些字段。Trader 和 Risk Judge 分别生产并验证两个对象；
Graph 缺失对象时只读适配器显式失败。状态日志保存全部结构化字段。

现有 MongoDB `analysis_reports` 与 `analysis_tasks.result` 使用可选字段扩展保存两个
决策对象、错误和两组模型元数据。没有新建集合、索引或迁移，也没有写入订单数据。

### PR-002 验证结果

| 验证项 | PR-002 结果 |
| --- | --- |
| PR-002 Schema/Trader/Risk/Signal/Graph 专项测试 | `40 passed` |
| 含现有 Risk Manager 回归 | `41 passed, 1 warning` |
| 现有 SignalProcessor/Risk 相关可运行测试 | `9 passed, 7 warnings` |
| PR-001 安全与配置测试 | `24 passed, 9 warnings` |
| Python `compileall` / `py_compile` | 通过 |
| `git diff --check` | 通过 |
| FastAPI 安全启动 | `GET /api/health` HTTP 200 |
| FastAPI 实盘开关拒绝 | 退出码 3，未完成应用启动 |
| `app/worker.py` 实盘开关拒绝 | 退出码 1，资源初始化前拒绝 |
| `app/worker/analysis_worker.py` 实盘开关拒绝 | 退出码 1，资源初始化前拒绝 |
| MongoDB / Redis | 均保持 healthy |
| 前端 `npm run type-check` | 失败，34 个存量 `TS2345 DefaultRow` 类型错误 |

限定测试目录收集：

- PR-001：703 项、15 个存量收集错误、2 个跳过；
- PR-002：743 项、相同 15 个存量收集错误；
- 增加的 40 项正好对应 PR-002 新增专项测试；
- 错误文件和错误类别与 PR-001 一致，仍是旧导入路径、不存在模块和上游依赖问题；
- 没有为改善数字而跳过新增测试，也没有修复无关存量错误。

前端没有代码改动。PR-001 只记录“多处上游 TypeScript 存量错误”，没有保存精确
数量；PR-002 复跑得到 34 个错误，全部仍属于已记录的 `TS2345 DefaultRow` 参数
类型不兼容类别。没有出现 PR-002 文件或新的错误类别，也没有为改善数字修复无关
前端技术债。

### 已知问题

- Provider 的原生结构化输出能力不同；不支持时依赖严格 JSON Prompt，任何额外文本
  都会 fail-closed 为 `INVALID_OUTPUT`。
- 当前 `model_version` 记录配置/适配器暴露的模型标识；若供应商只返回别名而不返回
  后端快照版本，无法在客户端推导隐藏版本。
- PR-002 的 `legacy-analysis:*` 和 `legacy-quant:none` 是有意保留的兼容来源。
  PR-003 已在新链路用真实 EvidenceSnapshot 替换前者；旧分析仍保留明确 legacy
  标记。`legacy-quant:none` 必须等 PR-004 的 QuantTradeProposal 才能替换。
- 风险辩手仍生成供终审参考的自然语言讨论，但正式 Risk Judge 明确读取
  `normal_trade_plan`，讨论文本不再能独立成为机器决策。
- 上游 FastAPI 启动仍会触发行情同步，关闭后后台线程可能延迟退出；这不是本阶段
  引入的问题。
- `web/utils/analysis_runner.py` 中已废弃的演示数据生成器仍包含随机演示价格，但它不
  在真实分析或结构化决策链上，也没有被改造成自动订单来源。

### PR-002 完成时明确未实施

- Candidate Pool
- EvidenceSnapshot
- DataQualityGate
- FactorRegistry / FactorEngine
- MarketRegimeEngine
- StrategyRegistry
- QuantTradeProposal 真实生产链
- ConsensusEngine
- HardRiskEngine
- OrderIntent / MatchingEngine
- 自动模拟交易或人工模拟交易改造
- Champion/Challenger
- 全市场推荐
- 真实券商连接
- Dify / Qlib / FinRL / RD-Agent

没有修改纸面交易路由、订单逻辑、实盘连接、PR-001 安全配置或前端视觉。

### PR-002 回退

当前安全回退边界是：

- 提交：`5c6ae8f`
- 标签：`alphaguard-pr001-baseline`

回退步骤：

1. 未提交 PR-002 时，先用 `git diff --binary > <安全目录>/pr002-tracked.patch`
   保存全部已跟踪文件修改；
2. 将三个新增范围 `tradingagents/alphaguard/`、`tests/unit/alphaguard/` 和
   `tests/integration/test_alphaguard_structured_decision_graph.py` 移到工作区外的带
   时间戳备份目录，避免直接删除；
3. 对第 1 步补丁执行 `git apply -R <安全目录>/pr002-tracked.patch`，只反向应用
   本阶段已跟踪文件修改；不要使用会覆盖用户工作的 `git reset --hard`；
4. PR-002 形成独立提交后，改用 `git revert <pr-002-commit>` 生成可审计回退提交；
5. 无数据库迁移或新集合需要撤销；已写入旧 MongoDB 文档的新增字段均为可选，
   旧代码会忽略，可保留；
6. 回退后重新运行：
   `.venv/bin/pytest -q tests/unit/test_alphaguard_baseline_guard.py
   tests/test_config_system.py`，预期 `24 passed`；
7. 重新验证安全 FastAPI HTTP 200，以及实盘开关下 API 和两套 Worker 均拒绝启动；
8. 重新检查 MongoDB、Redis healthy，且没有订单或券商调用。

### PR-002 完成时的下一阶段闸门

PR-002 到此结束。PR-003 及以后未获本次任务授权，不得开始 Candidate Pool、
EvidenceSnapshot、DataQualityGate、量化因子、Consensus、HardRisk 或订单系统。
进入下一阶段前必须重新确认授权、完整读取本状态文件并建立新的独立检查点。

---

## PR-003：Candidate Pool & EvidenceSnapshot

### 阶段结论与起点

PR-003 已完成实现和本阶段验证，工作严格停止在：

```text
Candidate Pool
→ DataQualityGate
→ immutable EvidenceSnapshot
→ snapshot_id structured-decision trace
→ analysis persistence
```

开始 PR-003 前工作区干净，PR-002 已形成独立提交 `09567a1`，且标签
`alphaguard-pr002-structured-decision` 指向该提交。PR-001 的安全默认值、FastAPI
和两套 Worker 的 fail-closed 入口均未修改。

本阶段没有创建因子、策略、QuantTradeProposal、ConsensusEngine、HardRiskEngine、
OrderIntent、自动模拟订单或真实券商调用。

### 实际修改文件

新增：

- `tradingagents/alphaguard/instruments.py`
- `tradingagents/alphaguard/candidate_schemas.py`
- `tradingagents/alphaguard/evidence_schemas.py`
- `tradingagents/alphaguard/mongo_indexes.py`
- `app/services/alphaguard/__init__.py`
- `app/services/alphaguard/candidate_pool_service.py`
- `app/services/alphaguard/data_quality_gate.py`
- `app/services/alphaguard/evidence_snapshot_service.py`
- `app/services/alphaguard/index_service.py`
- `app/routers/alphaguard.py`
- `scripts/init_alphaguard_indexes.py`
- `scripts/migrate_favorites_to_candidates.py`
- `tests/unit/alphaguard/_fakes.py`
- `tests/unit/alphaguard/test_candidate_pool_pr003.py`
- `tests/unit/alphaguard/test_evidence_snapshot_pr003.py`
- `tests/integration/alphaguard/test_candidate_sync_hooks_pr003.py`
- `tests/integration/alphaguard/test_snapshot_trace_chain_pr003.py`

修改：

- `app/core/database.py`
- `app/main.py`
- `app/models/analysis.py`
- `app/routers/analysis.py`
- `app/routers/paper.py`
- `app/services/favorites_service.py`
- `app/services/simple_analysis_service.py`
- `tradingagents/agents/managers/risk_manager.py`
- `tradingagents/agents/trader/trader.py`
- `tradingagents/agents/utils/agent_states.py`
- `tradingagents/alphaguard/__init__.py`
- `tradingagents/alphaguard/decision_schemas.py`
- `tradingagents/graph/propagation.py`
- `tradingagents/graph/trading_graph.py`
- `docs/refactor/CODEX_EXECUTION_STATUS.md`

`tradingagents/graph/setup.py` 经调用链检查后无需修改：Trader 和 Risk Judge 节点本身
没有换位，快照字段通过 Graph 初始状态和现有节点状态传播即可。没有为了目录形式改动
无关 Graph 接线。

### CandidateEntry、市场规范化与状态机

`CandidateEntry` 包含正式要求的 `candidate_id`、`user_id`、`symbol`、`market`、
`name`、`sources`、`status`、`priority`、时间字段、计划/订单/持仓依赖、
`removal_requested` 和固定 `schema_version=candidate-entry-v1`。

市场和代码统一规则：

- `A股/A_SHARE/CN/SH/SZ/SS/BJ` 归一为 `CN`；
- `港股/HK` 归一为 `HK`；
- `美股/US` 归一为 `US`；
- `600519`、`600519.SH`、`SH600519` 归一为同一 `CN/600519`；
- 港股补为 5 位代码，美股统一大写；
- 非法市场、非法代码和 `priority` 超出 `0..100` 均被 Schema 拒绝。

同一 `(user_id, market, symbol)` 只有一个候选，来源使用集合合并。状态迁移全部经过
`validate_candidate_transition()` 和集中映射；任意 API 字符串不能绕过状态机。
`REMOVED → WATCHING` 只有重新添加来源时允许。

删除采用逻辑删除：

1. 只移除 `USER_SELECTED`；
2. 重新查询正持仓、未完成订单、有效计划和分析中状态；
3. 仍需监控时保存 `removal_requested=true` 和明确保留原因；
4. 依赖全部清除后才进入 `REMOVED`；
5. 永不物理删除候选历史。

所有来源、状态、删除保护、重激活、对账和同步失败写入
`ag_candidate_events`，包括 `trace_id`。

### favorites 与 paper position 同步

`FavoritesService` 在原 favorite 写入成功后执行 best-effort 候选同步：

- 添加 favorite：合并 `USER_SELECTED`；
- 删除 favorite：只移除 `USER_SELECTED`；
- 候选同步失败：原 favorite 结果保持成功，写 `SYNC_FAILED` 审计；
- reconciliation 同时读取 `user_favorites.favorites` 和
  `users.favorite_stocks`，可补回失败同步并移除失效来源。

人工模拟交易仅在账户、持仓、订单和成交记录全部写入后调用同步钩子：

- `quantity > 0`：合并 `POSITION_REQUIRED`，维护 `POSITION_HELD`；
- `quantity == 0`：只移除 `POSITION_REQUIRED`；
- 同步失败不回滚合法成交，等待 reconciliation 修复；
- account reset 完成后执行一次 best-effort reconciliation。

成交价格、手续费、T+1、订单响应和人工操作方式均未修改。同步钩子不创建订单。

### DataQualityGate

第一版为纯 Python 确定性规则，不调用 LLM，覆盖：

- 市场和股票代码合法性；
- 引用能否解析到允许的现有 MongoDB 集合和真实记录；
- 目标交易日核心行情是否存在；
- OHLC 为有限正数；
- `high`/`low` 关系一致；
- `volume` 和 `amount` 有效且非负；
- 行情日期不晚于交易日和价格截止时间；
- 新闻/公告时间不晚于各自截止时间；
- 被声明为必要的数据源同步状态是否完成；
- 非核心财务、新闻/公告缺失进入 `WARN`。

核心行情缺失、OHLC/量价无效、未来数据、必要同步未完成或引用不可解析均为
`FAIL`。`FAIL` 报告保存到 `ag_data_quality_reports`，不创建快照；Graph 初始状态
也拒绝 `snapshot_id + FAIL`，因此 Trader 和 Risk Judge 不会被调用。不存在自动
重试为 `WARN` 或转换成 HOLD。

固定版本为 `data-quality-report-v1`。

### EvidenceSnapshot 与 immutable_hash

`EvidenceSnapshot` 实现总蓝图字段并使用 Pydantic frozen model。固定版本：

- `schema_version=evidence-snapshot-v1`
- `code_version=alphaguard-pr003-v1`

PR-004 占位严格限制为：

```text
factor_version_set={}
strategy_version=None
```

没有伪造任何因子、市场状态、量化提案或策略版本。Service 只提供 create、get、
list、verify/get-quality/analysis-preflight；没有 update/delete。API 也没有
PUT、PATCH 或 DELETE 快照路由。数据修复必须创建新 `snapshot_id`。

哈希流程：

1. 递归转换为规范值；
2. 排除 MongoDB `_id` 和 `immutable_hash`；
3. 字典键排序；
4. set 排序，日期/时间转 ISO 8601；
5. UTF-8、固定 JSON separators、禁止 NaN；
6. 计算 SHA-256。

相同规范内容得到相同哈希，引用或截止时间变化会改变哈希；读取分析前会重新校验，
篡改返回失败并阻断 AlphaGuard 分析。`raw_refs` 只保存固定引用，不复制无限原始
数据。

### snapshot_id 全链路

新链路：

```text
POST EvidenceSnapshot
→ DataQuality PASS/WARN
→ analysis request.snapshot_id
→ SimpleAnalysisService preflight
→ AgentState.snapshot_id/data_quality_status
→ Propagator/TradingGraph
→ Trader input
→ NormalTradePlan.snapshot_id
→ Risk Judge input
→ TopReviewDecision.snapshot_id
→ Graph final state/decision
→ analysis_tasks.result + analysis_reports
→ analysis API response/log
```

preflight 验证快照存在、属于当前用户、哈希正确、symbol/market/analysis_date 一致，
且数据质量不是 FAIL。任何一项失败都在模型节点之前阻断。

旧普通分析仍可省略 `snapshot_id`，但状态、结果、持久化和 API 均明确保存：

```text
legacy_analysis=true
automated_execution_allowed=false
```

旧路径继续使用明确的 `legacy-analysis:*` 标识；真实快照路径的两个结构化决策对象
使用真实 `snapshot_id`。`quant_proposal_id=legacy-quant:none` 仍保留，因为
QuantTradeProposal 属于 PR-004。

### MongoDB 集合和索引

新增独立集合：

- `ag_candidates`
- `ag_candidate_events`
- `ag_evidence_snapshots`
- `ag_data_quality_reports`

新增 15 个 create-only 索引：

- `ag_candidates`：唯一 `candidate_id`、唯一
  `(user_id,market,symbol)`、`(status,next_scan_at)`、`(user_id,status)`、
  `sources`；
- `ag_candidate_events`：唯一 `event_id`、`(candidate_id,created_at)`、
  `(user_id,created_at)`；
- `ag_evidence_snapshots`：唯一 `snapshot_id`、
  `(user_id,symbol,trade_date)`、`(symbol,market,trade_date)`、
  `immutable_hash`；
- `ag_data_quality_reports`：唯一 `quality_report_id`、
  `(symbol,market,trade_date)`、`(status,checked_at)`。

应用现有索引初始化会调用同一声明式计划。脚本支持 `--plan-only`，正确索引重复执行
均返回 `unchanged`，同名冲突会 fail-closed；不会 drop 集合/索引，也不会修改
paper、favorites 或 analysis 索引。

### API

新增并挂载：

```text
GET    /api/alphaguard/candidates
POST   /api/alphaguard/candidates
GET    /api/alphaguard/candidates/{candidate_id}
PATCH  /api/alphaguard/candidates/{candidate_id}
DELETE /api/alphaguard/candidates/{candidate_id}
POST   /api/alphaguard/candidates/reconcile

POST   /api/alphaguard/evidence/snapshots
GET    /api/alphaguard/evidence/snapshots/{snapshot_id}
GET    /api/alphaguard/evidence/snapshots/{snapshot_id}/quality
POST   /api/alphaguard/evidence/snapshots/{snapshot_id}/verify
```

继续使用现有认证、response wrapper、MongoDB 和 request trace middleware。
候选 GET 支持 market/status/source/symbol 过滤。DELETE 返回是否继续监控、保留原因
和 `physically_deleted=false`。DataQuality FAIL 返回 422 和完整阻断报告。

分析 API 只有向后兼容的可选 `snapshot_id` 输入和追踪字段输出；没有改变现有必填
参数。CORS 仅补充新增 PATCH 方法。

### favorites 数据迁移

`scripts/migrate_favorites_to_candidates.py`：

- 默认 dry-run，只有显式 `--execute` 才写候选；
- 同时读取两种历史 favorites 结构；
- 使用候选唯一身份和来源合并，重复运行不重复；
- 输出 added/updated/skipped/failed；
- 不修改或删除原 favorites。

本次真实数据库 dry-run 结果：

```text
added=0 updated=0 skipped=0 failed=0
```

当前数据库没有待迁移 favorite，因此没有执行 `--execute`。固定数据测试验证第一次
执行新增 1 条、第二次执行跳过且仍只有 1 条。

### PR-003 验证结果

| 验证项 | 结果 |
| --- | --- |
| Candidate Schema/状态机/服务 | `16 passed` |
| DataQuality/EvidenceSnapshot | `16 passed` |
| favorites/paper/迁移集成 | `5 passed` |
| snapshot_id/Graph/持久化集成 | `3 passed` |
| PR-003 专项合计 | `40 passed, 7 warnings` |
| PR-002 结构化决策回归 | `45 passed, 3 warnings` |
| PR-001 安全与配置回归 | `24 passed, 9 warnings` |
| 本阶段修改/新增 Python 文件 `py_compile` | 通过 |
| 全目录 `compileall` | 仅命中存量 `scripts/补充行业信息_akshare.py:81` 语法错误 |
| `git diff --check` | 通过 |
| 候选 API 冒烟 | POST/GET/DELETE 通过，未物理删除 |
| 快照 API 冒烟 | POST/GET/quality/verify 通过，无变更路由 |
| MongoDB 实际服务冒烟 | 候选合并、WARN 快照、哈希/preflight 通过，临时数据已清理 |
| 索引脚本 | 15 项计划；重复实际执行全部 `unchanged` |
| favorites 迁移脚本 | dry-run 通过，未写用户数据 |
| FastAPI 安全启动 | `GET /api/health` HTTP 200 |
| FastAPI 实盘开关拒绝 | 退出码 3 |
| `app/worker.py` 实盘开关拒绝 | 退出码 1，资源初始化前拒绝 |
| `app/worker/analysis_worker.py` 实盘开关拒绝 | 退出码 1，资源初始化前拒绝 |
| MongoDB / Redis | Docker healthy，实际 ping 均通过 |
| 前端 `npm run type-check` | 失败，仍是 34 个存量 `TS2345 DefaultRow` 错误 |

全量测试收集对比：

- PR-001：703 项，15 个存量收集错误；
- PR-002：743 项，相同 15 个存量收集错误；
- PR-003：783 项，相同 15 个存量收集错误；
- 新增 40 项全部被收集并独立通过；
- 没有新增错误文件或错误类别，没有跳过本阶段测试，也没有顺手修复上游技术债。

### 设计差异、限制和风险

总蓝图给出的是建议目录。实际保持现有模块化单体：

- 原建议拆分 `candidates.py` / `evidence.py`；实际合并为一个较小的
  `app/routers/alphaguard.py`，统一保证 `/api/alphaguard` 边界；
- 原建议在 `app/schemas`、`app/models` 再建一套类型；实际复用 PR-002 已建立的
  `tradingagents/alphaguard` 契约目录，避免两个 Pydantic 真相来源；
- 原建议可增加 reconciliation worker；本阶段实际提供服务方法、API 和 paper reset
  钩子，没有创建常驻扫描 Worker，以免提前形成自动候选扫描。

风险与限制：

- reconciliation 当前由显式 API、迁移或 paper reset 触发，尚未定时运行；这是避免
  提前实施自动扫描的有意边界；
- DataQualityGate 是第一版最小规则集，不含正式交易日历、财报披露周期分层或跨源
  价格共识；这些不能在本阶段伪装成量化因子；
- 数据版本字符串和 raw refs 由调用方提供，但 raw refs 会解析到真实记录并经过质量
  校验；本阶段没有建立独立数据版本注册中心；
- 快照不可变由 frozen Schema、无变更 Service/API 和哈希 preflight 共同保证；
  具备数据库管理员权限的离线篡改不能被物理禁止，但会被哈希发现并阻断分析；
- MongoDB standalone 环境没有跨集合事务，候选主记录与审计事件之间依赖
  reconciliation 处理极端部分失败；
- 上游 FastAPI 启动仍会触发行情/基础信息同步，退出后后台线程可能延迟结束；本次
  启动验证出现该已知行为，最终确认测试进程已终止；
- 前端没有新增页面，也未修改现有视觉或 34 个存量类型错误。

### 明确未实施

- FactorRegistry / FactorEngine
- MarketRegimeEngine
- StrategyRegistry
- QuantTradeProposal 真实生产链
- ConsensusEngine
- HardRiskEngine
- OrderIntent / MatchingEngine
- 自动模拟交易
- Champion/Challenger
- 自动推荐选股或全市场 LLM 扫描
- 真实券商连接
- PostgreSQL / Dify / Qlib / FinRL / RD-Agent

`CandidateStatus` 中为总蓝图预留的后续状态只建立校验规则，本阶段没有任何自动节点
触发它们。没有修改 PR-002 普通模型/顶尖模型职责和正式结构化输出语义。

### PR-003 回退

安全代码回退边界为 PR-002 标签：

```text
alphaguard-pr002-structured-decision
09567a1
```

当前 PR-003 尚未提交，建议回退步骤：

1. 先把 `git status --short` 保存到工作区外；
2. 用 `git diff --binary > <安全目录>/pr003-tracked.patch` 保存全部已跟踪修改；
3. 将本节“新增”列表中的未跟踪文件移动到工作区外的时间戳备份目录；
4. 对补丁执行 `git apply -R <安全目录>/pr003-tracked.patch`，只反向应用 PR-003
   已跟踪修改；不要使用 `git reset --hard`；
5. 若 PR-003 后续形成提交，改用 `git revert <pr-003-commit>`；
6. 旧 favorites、paper 和 analysis 数据无需回退；新增分析字段为可选，旧代码会忽略；
7. 四个 AlphaGuard 集合和索引可安全保留，不会被 PR-002 读取。若必须做物理数据库
   回退，先对四个精确集合执行 `mongodump`，核对备份后再单独 drop，禁止对数据库
   或通配集合执行递归删除；
8. 回退后重新运行 PR-002 45 项、PR-001 24 项，并验证 FastAPI HTTP 200、实盘开关
   下 FastAPI/两套 Worker 拒绝、MongoDB/Redis healthy；
9. 核对不存在 `/api/alphaguard` 路由、分析请求不再接受 `snapshot_id`，且没有候选
   同步钩子。

### 下一阶段闸门

PR-003 到此停止。进入 PR-004 前必须由人工另行授权、先提交或备份当前 PR-003
工作区，并再次完整读取主计划和本状态文件。当前不得开始因子、市场状态、策略、
QuantTradeProposal、一致性裁决、硬风控或任何订单链。

---

## PR-004：Factor, Regime & Strategy Engine

### 完成结论和安全边界

PR-004 已完成。正式确定性研究链为：

```text
EvidenceSnapshot
  -> immutable_hash / 版本锁校验
  -> SnapshotDataResolver
  -> FactorRegistry / FactorEngine
  -> FactorEvidenceBundle
  -> MarketRegimeEngine
  -> StrategyRegistry / StrategyEngine
  -> QuantTradeProposal
  -> append-only MongoDB 保存和认证查询
```

链路终止于不可自动执行的 `QuantTradeProposal`。全部提案强制
`automated_execution_allowed=false`。没有调用 LLM，没有进入 Trader、Risk Judge、
NormalTradePlan、TopReviewDecision，没有创建 OrderIntent、paper order、trade 或
持仓变更。PR-001 的 `SIM_AUTONOMOUS + live_trading_enabled=false` 不变量保持不变。

### 实际修改文件

新增：

```text
app/models/alphaguard/__init__.py
app/models/alphaguard/quant_collections.py
app/schemas/alphaguard/__init__.py
app/schemas/alphaguard/quant.py
app/routers/alphaguard_quant.py
app/services/alphaguard/factor_aggregation.py
app/services/alphaguard/factor_engine.py
app/services/alphaguard/factor_registry.py
app/services/alphaguard/market_regime_engine.py
app/services/alphaguard/quant_audit_service.py
app/services/alphaguard/quant_config.py
app/services/alphaguard/quant_research_pipeline.py
app/services/alphaguard/snapshot_data_resolver.py
app/services/alphaguard/strategy_engine.py
app/services/alphaguard/strategy_registry.py
config/alphaguard/factors/factor_set_v1.yaml
config/alphaguard/regimes/market_regime_v1.yaml
config/alphaguard/strategies/swing_trend_pullback_v1.yaml
config/alphaguard/strategies/position_exit_v1.yaml
scripts/seed_alphaguard_factor_definitions.py
scripts/seed_alphaguard_strategy_definitions.py
tests/unit/alphaguard/test_factor_engine_pr004.py
tests/unit/alphaguard/test_quant_pipeline_pr004.py
tests/unit/alphaguard/test_quant_schemas_pr004.py
tests/unit/alphaguard/test_regime_strategy_pr004.py
tests/unit/alphaguard/test_snapshot_resolver_pr004.py
```

最小修改：

```text
app/core/database.py
app/main.py
app/routers/alphaguard.py
app/services/alphaguard/data_quality_gate.py
app/services/alphaguard/evidence_snapshot_service.py
app/services/alphaguard/index_service.py
scripts/init_alphaguard_indexes.py
tradingagents/alphaguard/evidence_schemas.py
tradingagents/alphaguard/mongo_indexes.py
docs/refactor/CODEX_EXECUTION_STATUS.md
```

没有修改 Trader、Risk Manager、AgentState、SignalProcessor、paper 交易实现或前端。

### SnapshotDataResolver 与无未来数据保证

`SnapshotDataResolver`：

- 先读取并验证既有 `EvidenceSnapshot.immutable_hash`；
- 正式量化计算要求快照同时具备非空 `factor_version_set` 和
  `strategy_version`；
- 旧 PR-003 空版本快照默认拒绝，只有内部显式
  `allow_legacy_unversioned=true` 才能兼容研究；公开计算 API 不暴露该开关；
- 只逐条解析 `raw_refs`，不按 symbol 查询“最新”记录；
- 引用不唯一、找不到或哈希不一致时 fail-closed；
- 行情、指数和市场上下文限制在 `trade_date/price_cutoff_at`；
- 财务同时要求 `report_period <= trade_date` 以及
  `ann_date/f_ann_date/publish_date <= announcement_cutoff_at`，没有披露时间即排除；
- 新闻和公告分别服从 `news_cutoff_at`、`announcement_cutoff_at`；
- 持仓记录必须属于快照用户且不晚于价格截止；
- 未来交易日可以作为已提前公开的日历事实，但日历自身的
  `as_of/published_at` 必须不晚于快照截止；
- 不调用外部数据源，不用未来记录，不用更新后的非引用记录补缺。

DataQuality 引用前缀扩展到实际存在的 `stock_daily_quotes`、
`stock_financial_data`、`stock_news`、`paper_positions`，以及显式
`index_daily/market_context/trading_calendar` 引用。历史记录若用 symbol 和日期定位，
同日仍有多条候选时视为歧义并拒绝，推荐正式引用使用 ObjectId 或唯一 `ref_id`。

### 因子注册表、版本和定义

- 因子集合版本：`factor-set-v1`；
- 21 个因子版本均为 `1.0.0`；
- 公式实现版本：`factor-engine-v1`；
- `FactorDefinition` 保存 group、公式说明、依赖、窗口、缺失策略、归一化方法、
  参数、`code_hash`、`parameter_hash`、状态、创建时间和 Schema 版本；
- `(factor_id, factor_version)` 创建后不可覆盖；相同内容重复注册返回已有定义，
  同身份不同内容写审计并抛出完整性冲突；
- 公式或参数变化必须使用新版本。

正式因子如下：

| 因子 | 公式/数据依赖 |
| --- | --- |
| `close_vs_ma20_v1` | `close / MA20 - 1`；20 个快照行情 close |
| `close_vs_ma60_v1` | `close / MA60 - 1`；60 个 close |
| `ma20_vs_ma60_v1` | `MA20 / MA60 - 1`；60 个 close |
| `ma20_slope_5d_v1` | `MA20(t) / MA20(t-5) - 1`；25 个 close |
| `momentum_20d_v1` | `close(t) / close(t-20) - 1`；21 个 close |
| `momentum_60d_v1` | `close(t) / close(t-60) - 1`；61 个 close |
| `relative_strength_hs300_20d_v1` | 股票 20 日收益减沪深300同期收益；对齐日期 |
| `volume_confirmation_20d_v1` | 当日 volume / 前20日 volume 中位数 |
| `revenue_yoy_v1` | 最新已披露 revenue / 上年同报告期 - 1 |
| `adjusted_net_profit_yoy_v1` | 明确扣非利润字段 / 上年同报告期 - 1；不拿普通净利润代替 |
| `roe_v1` | 最新已披露标准 ROE |
| `operating_cashflow_to_profit_v1` | `n_cashflow_act / net_income`；近零分母拒绝 |
| `pe_ttm_percentile_3y_v1` | 自身正 PE 最多 756 期历史分位；至少60个有效样本 |
| `pb_percentile_3y_v1` | 自身正 PB 最多 756 期历史分位；至少60个有效样本 |
| `dividend_yield_v1` | 快照行情中的 `dv_ttm/dv_ratio/dividend_yield` |
| `atr14_pct_v1` | 14 期 True Range 均值 / close；需要15期 OHLC |
| `volatility20_annualized_v1` | 20 日日收益样本标准差 × `sqrt(250)` |
| `average_amount20_v1` | 20 日 amount 算术平均 |
| `turnover20_v1` | 20 日 turnover_rate 算术平均 |
| `short_term_excess_return5_v1` | 股票 5 日收益减沪深300同期收益；风险归一化取绝对幅度 |
| `event_risk_v1` | 结构化 severity/risk_level 优先，后接 `event-risk-rules-v1` 固定关键词 |

行业强度组保留为正式分组，但当前没有可靠快照行业强度时序输入，因此不伪造可选
增强因子，覆盖率为 0、得分为 null。

### FactorResult、缺失值、归一化与聚合

`FactorResult` 保存唯一 result_id、因子/代码/参数版本、证券身份、交易日、snapshot、
raw/score/direction/confidence/missing_reason、精确引用、输入哈希及计算时间。
`normalized_score` 只能是 0～100 或 null，confidence 只能是 0～1。

缺失数据统一为：

```text
raw_value = null
normalized_score = null
direction = UNKNOWN
confidence = 0
missing_reason = 明确依赖说明
```

缺失财务不解释为 0，未抓到新闻不解释为无风险，市场数据不足不解释为震荡。归一化
只使用版本 YAML 的固定上下界、单调线性、对数线性、自身历史分位或绝对风险映射，
不使用候选池排名、未来全样本、动态权重或 LLM。

`FactorEvidenceBundle` 保存各组有效/总因子数、coverage、等权权重、缺失因子和得分。
默认覆盖率阈值为 0.60；低于阈值时组分为 null。趋势/动量/质量/估值/流动性越高越
强或越有吸引力；波动风险和事件风险越高风险越大。

### MarketContext 与 MarketRegimeEngine

市场状态只接受快照显式引用的宽基指数历史和 `ag_market_contexts` 公共市场记录。
输入指标包括指数相对 MA20/MA60、MA20 五日斜率、20 日年化波动率、上涨/下跌家数
计算的宽度、行业扩散度、成交额比、新高/新低比和结构化极端风险标志。没有用单只
股票代替市场。

版本 `market-regime-v1` 只产生五种状态：

- `EXTREME_RISK`：阻断标志，或高波动与宽度崩溃同时成立；
- `TREND_UP`：指数在 MA20/MA60 上方、斜率正、宽度和行业扩散度达到阈值；
- `TREND_DOWN`：指数在 MA60 下方、斜率负且宽度弱；
- `RANGE_STRONG`：中期结构未破坏且宽度非负，但不满足完整上升趋势；
- `RANGE_WEAK`：其余偏弱但未达到下降/极端风险。

缺少必需指标返回 `INSUFFICIENT_DATA + regime=null`；非法负家数或越界行业扩散度
返回 `INVALID_INPUT + regime=null`。两者都禁止新持仓、不允许开仓策略，但保留
`POSITION_EXIT_V1`。各状态的允许策略和最大总敞口来自 YAML，不在 Prompt 中。

当前实际 MongoDB 没有指数、市场宽度或交易日历业务记录，因此真实快照在补齐明确
raw refs 前会按设计得到数据不足，而不是一个虚构市场状态。

### 策略注册表和两套 Champion

策略集合版本为 `strategy-set-v1`，公式实现为 `strategy-engine-v1`；两套策略版本均
为 `1.0.0`，状态均为 `CHAMPION`。`StrategyDefinition` 保存适用市场/状态、因子依赖、
必需分组、参数、代码和参数哈希、父版本及晋升时间。同版本不可覆盖；PR-004 没有
Challenger 或自动晋升工作流。

`SWING_TREND_PULLBACK_V1`：

- 仅 CN，且只在 `TREND_UP/RANGE_STRONG` 和 `allow_new_positions=true` 时运行；
- 检查趋势、动量、沪深300相对强弱、流动性、波动风险、事件风险；
- 回调必须位于固定的 20 日高点回撤区间且接近 MA20，中期趋势仍在 MA60 上方；
- 输出 TRIGGERED/BUY、WATCH/WAIT、REJECTED/HOLD 或
  INSUFFICIENT_DATA/WAIT；
- 触发时提供确定性 entry zone、5% 初始/10% 最大建议仓位、加减仓/退出/失效条件；
- 有效期只取快照引用交易日历中的后 3 个开市日；日历不足则不触发；
- 不包含、推算或强制生成 target_price。

`POSITION_EXIT_V1`：

- 只读取快照引用、属于当前用户且 quantity > 0 的 paper position；
- 无正持仓固定返回 `REJECTED/HOLD + NO_POSITION`；
- 检查跌破 MA20/MA60、MA20 斜率、20 日动量、波动/事件风险和市场
  TREND_DOWN/EXTREME_RISK；
- 重大风险给出 SELL，多个降险条件给出 REDUCE，否则 WATCH/HOLD；
- `quantity/available_qty` 和 T+1 可卖信息进入 EvidenceRef/risk flag；
- 即使建议 SELL，仍只生成研究提案，不调用人工模拟交易 API。

### QuantTradeProposal、幂等和完整性

`QuantTradeProposal` 保存 candidate/snapshot、策略和市场状态版本、因子集合版本、
状态、候选动作、可选 entry zone、建议仓位、规则条件、交易日历有效期、预计持有
周期、因子摘要和结果 ID、证据、风险、原因、解释、input_hash 和创建时间。Schema
使用 `Literal[False]` 强制不可自动执行；没有目标价字段。

不可变身份：

```text
FactorResult       (snapshot_id, factor_id, factor_version)
MarketRegimeResult (snapshot_id, regime_version)
QuantTradeProposal (snapshot_id, strategy_id, strategy_version)
```

重复输入和实现/参数哈希一致时返回已有对象；同一身份但输入、代码或参数哈希变化时
写 `QUANT_INTEGRITY_CONFLICT` 并拒绝覆盖。proposal/result ID 由输入哈希确定性生成。
任一策略 TRIGGERED 时，只有 `WATCHING` 候选允许转为 `SIGNAL_DETECTED`；不会推进
AI、风控或订单状态。

审计事件保存在额外 append-only `ag_quant_audit_events`，覆盖定义注册、因子计算、
市场状态成功/失败、策略评估成功/失败、提案创建和完整性冲突。

### 新快照版本关联

新正式量化快照必须在创建之前：

1. 因子和策略定义已经通过种子脚本登记；
2. `factor_version_set` 与已登记 `factor-set-v1` 的 21 个精确版本完全一致；
3. `strategy_version=strategy-set-v1`；
4. 两者与 raw refs、cutoff 和数据版本一起参与 `immutable_hash`。

旧快照不回填、不更新、不重算哈希。EvidenceSnapshot Schema 同时接受完整的旧
空版本形态和完整的新版本形态，不接受只提供其中一项的半版本形态。

### MongoDB 集合、索引和数据变化

新增所需集合：

```text
ag_factor_definitions
ag_factor_results
ag_regime_results
ag_strategy_definitions
ag_quant_proposals
```

为公共市场输入和审计另增加：

```text
ag_market_contexts
ag_quant_audit_events
```

索引包含指令要求的定义唯一身份、result/snapshot/factor 唯一身份、input_hash、
symbol/market/date、snapshot/group、regime/version/status/date、strategy/version/
status/markets、proposal_id、snapshot/strategy/version、candidate/status/created_at
及审计 snapshot/type/time。继续使用同一 create-only 索引器：不 drop、不替换同名
冲突，冲突明确失败。

真实开发数据库执行结果：

- 索引脚本第一次补建 PR-004 索引，第二次全部 `unchanged`；
- 因子种子第一次写入 21 条，第二次 `seeded_or_verified=21`；
- 策略种子第一次写入 2 条，第二次 `seeded_or_verified=2`；
- 写入 23 条定义注册审计；
- `ag_factor_results/ag_regime_results/ag_quant_proposals` 均为 0；
- `paper_orders/paper_trades` 均为 0；
- 没有迁移、更新或删除 PR-003 快照、候选、favorites、paper 或 analysis 数据。

### API

均复用现有 `get_current_user` 认证、response wrapper、request trace 和 MongoDB：

```text
GET  /api/alphaguard/factors/definitions
GET  /api/alphaguard/factors/results?snapshot_id=...
GET  /api/alphaguard/factors/results/{snapshot_id}
POST /api/alphaguard/quant/evaluate/{snapshot_id}
GET  /api/alphaguard/regimes/{snapshot_id}
GET  /api/alphaguard/strategies/definitions
GET  /api/alphaguard/quant-proposals
```

客户端不能上传 FactorResult、MarketRegimeResult 或 QuantTradeProposal；没有更新、
删除或订单端点。计算 API 只选择快照中锁定的版本，不接受客户端临时结果或权重。

### PR-004 测试和全阶段回归

| 验证项 | 结果 |
| --- | --- |
| PR-004 Schema/因子/状态/策略/解析器/管线/API/索引 | `41 passed, 4 warnings` |
| PR-003 专项回归 | `40 passed` |
| PR-002 结构化决策专项 | `40 passed` |
| PR-001 安全与配置回归 | `24 passed`（最终复跑含 `tests/test_config_system.py`） |
| PR-001～PR-004 合并选择集 | `145 passed, 14 warnings` |
| Python 新增/修改文件 `py_compile/compileall` | 通过 |
| 全目录 `compileall` | 仅存量 `scripts/补充行业信息_akshare.py:81` 语法错误 |
| `git diff --check` | 通过 |
| 全量测试收集 | `824 collected, 15 errors`，错误文件/类别与 PR-003 相同 |
| 前端 `npm run type-check` | 失败，仍为 34 个存量 `TS2345 DefaultRow` |
| FastAPI 安全启动 | `GET /api/health` HTTP 200 |
| FastAPI 实盘开关拒绝 | 退出码 3 |
| `app/worker.py` 实盘开关拒绝 | 退出码 1，任务资源初始化前 |
| `app/worker/analysis_worker.py` 实盘开关拒绝 | 退出码 1，任务资源初始化前 |
| MongoDB / Redis | Docker healthy，实际 ping 为 `1.0 / True` |
| 索引脚本 | 第二次执行全部 `unchanged`，无删除 |
| 因子/策略脚本 dry-run | 通过，明确提示需 `--execute` |
| 因子/策略脚本 execute 幂等 | `21 / 2` 两次一致 |
| Quant API 冒烟 | 认证依赖和 definitions/proposals 查询 HTTP 200 |
| 重复计算 | 复用 21 个结果、1 个状态、2 个提案，无重复 |
| 无未来数据 | 行情、财务、新闻未来记录均排除；篡改哈希阻断 |
| 自动交易副作用 | 订单、成交、持仓变化均为 0 |

PR-003 为 783 collected；PR-004 新增 41 项后为 824 collected，增量完全对应本阶段
测试。15 个收集错误、34 个前端错误和中文脚本语法错误均是已记录存量问题，没有
新增错误类别，也没有跳过或顺手修复。

### 设计差异、限制和安全影响

1. 原设计建议将全部 Schema 放在多个 `app/schemas/alphaguard/*.py`；实际以单一
   `quant.py` 保存一个严格真相来源，避免当前规模下跨文件循环。安全语义不变。
2. 原设计列出独立 `market_context_service.py`；实际公共市场记录只能通过
   `SnapshotDataResolver` 的明确快照引用读取，没有开放写 API。原因是当前项目没有
   可靠市场宽度/指数入库链，贸然新增实时抓取会破坏无未来数据边界。后续只能由
   独立数据工程阶段补齐，不得由策略引擎外部查询。
3. 原设计可将 FactorEvidenceBundle 持久化；实际 bundle 在同一管线内确定性生成，
   底层 FactorResult、Regime 和 Proposal 已持久化且都有哈希。未增加非必要集合。
4. 额外增加 `ag_quant_audit_events`，用于满足定义/计算/冲突审计要求；它只追加，
   不参与交易执行。
5. 当前历史行情可承载全部价格因子，但实际开发数据库对应数据为 0；指数、市场宽度、
   行业强度和交易日历也无业务数据。生产计算会明确数据不足，不会实时补齐或猜测。
6. `event_risk_v1` 是固定关键词和结构化字段规则，不是语义模型；规则改变必须升版。
7. 仓位百分比只是策略研究建议，尚未经过 PR-005 HardRiskEngine。

### 兼容性和明确未实施

- PR-003 旧快照保持字节/哈希不变；旧请求仍可创建空版本兼容快照；
- PR-002 的结构化模型链和旧展示字段没有修改；
- PR-001 安全配置和两套 Worker 入口没有修改；
- 现有 favorites、人工模拟交易、手续费、滑点和 T+1 实现没有修改；
- MongoDB 字段扩展和新集合不会改变旧文档解析；
- 公开变化仅为新增认证 API 与 EvidenceSnapshot 创建请求允许完整版本锁。

明确未实施 PR-005 及以后：

```text
ContextBuilder LLM 注入
ConsensusEngine
MaterialRevision 人工确认流
HardRiskEngine / RiskDecision
OrderIntent / MatchingEngine
自动模拟交易或实盘
Champion/Challenger 晋升
全市场自动推荐
Dify / Qlib / FinRL / RD-Agent
```

### PR-004 回退

安全代码边界为：

```text
21e9792
alphaguard-pr003-candidate-evidence
```

1. 当前 PR-004 尚未形成提交。先将 `git status --short` 和
   `git diff --binary` 保存到工作区外，并把本节“新增”文件复制到带时间戳备份目录；
2. 仅反向应用保存的 PR-004 tracked patch，并移动本节新增文件；不要使用
   `git reset --hard` 或覆盖其他用户改动；
3. PR-004 后续形成独立提交后，优先使用 `git revert <pr004-commit>`；
4. PR-003 四个集合和历史快照绝不回填或删除，PR-001 安全配置绝不回退；
5. 新增定义、结果和索引对 PR-003 代码不可见，可安全保留。若确需物理回退，先对
   上述 7 个精确集合执行 `mongodump` 并验证备份，再逐个处理；禁止通配 drop；
6. 当前真实库只有 21 个因子定义、2 个策略定义、23 个注册审计和索引，没有结果、
   regime、proposal 或订单数据；
7. 回退后复跑 PR-001 24 项、PR-002 40 项、PR-003 40 项，并重新验证 FastAPI
   HTTP 200、API/两 Worker 实盘拒绝及 MongoDB/Redis healthy。

### 当前 Git 状态和下一阶段闸门

PR-003 已提交并标记；PR-004 当前为未提交的已跟踪修改和新增文件，未混入 PR-003
提交。完成最后复跑后应以实际 `git status --short` 为准。PR-004 到此停止；
不得开始 PR-005，进入 PR-005 必须由人工重新授权并先建立 PR-004 独立检查点。

---

## PR-005：Dual Model Consensus & Hard Risk

### 完成结论与阶段边界

PR-005 已完成。开始阶段前已将 PR-004 建立为独立提交和标签：

```text
87026f5 feat(pr-004): establish deterministic quant research
alphaguard-pr004-quant-research
```

同时确认 `alphaguard-pr001-baseline`、`alphaguard-pr002-structured-decision`、
`alphaguard-pr003-candidate-evidence` 均存在，且
`git diff alphaguard-pr004-quant-research..HEAD --check` 通过。

本阶段正式链路为：

```text
TRIGGERED QuantTradeProposal
  -> immutable DecisionContext
  -> NormalTradePlan
  -> TopReviewDecision
  -> optional single RevisionRequest / revised plan / final review
  -> pure-Python ConsensusEngine
  -> ConsensusDecision
  -> pure-Python HardRiskEngine
  -> RiskDecision
```

链路严格终止于 `RiskDecision`。`PASS/REDUCE` 只表示具备进入后续阶段的资格；
`RiskDecision.order_intent_created` 和 `DecisionPipelineResult.order_intent_created`
均由 `Literal[False]` 强制为 false。本阶段没有 OrderIntent、PaperOrder、成交、
现金/持仓修改、冻结、自动撮合、自动模拟交易或实盘连接。PR-001 的
`SIM_AUTONOMOUS + live_trading_enabled=false` 和三个启动入口 fail-closed 保持不变。

### 实际修改与新增文件

修改：

```text
app/main.py
app/services/alphaguard/data_quality_gate.py
app/services/alphaguard/snapshot_data_resolver.py
tradingagents/agents/managers/risk_manager.py
tradingagents/agents/trader/trader.py
tradingagents/agents/utils/agent_states.py
tradingagents/alphaguard/decision_schemas.py
tradingagents/alphaguard/mongo_indexes.py
tradingagents/alphaguard/structured_output.py
docs/refactor/CODEX_EXECUTION_STATUS.md
```

新增：

```text
tradingagents/alphaguard/decision_control_schemas.py
app/schemas/alphaguard/decision.py
app/models/alphaguard/decision_collections.py
app/routers/alphaguard_decisions.py
app/services/alphaguard/decision_context_builder.py
app/services/alphaguard/decision_validation.py
app/services/alphaguard/decision_model_runner.py
app/services/alphaguard/revision_service.py
app/services/alphaguard/consensus_engine.py
app/services/alphaguard/risk_policy_registry.py
app/services/alphaguard/risk_context_resolver.py
app/services/alphaguard/hard_risk_engine.py
app/services/alphaguard/decision_audit_service.py
app/services/alphaguard/decision_pipeline.py
config/alphaguard/risk/risk_policy_v1.yaml
scripts/init_alphaguard_decision_indexes.py
scripts/seed_alphaguard_risk_policies.py
tests/unit/alphaguard/pr005_helpers.py
tests/unit/alphaguard/test_decision_control_schemas_pr005.py
tests/unit/alphaguard/test_consensus_engine_pr005.py
tests/unit/alphaguard/test_hard_risk_engine_pr005.py
tests/unit/alphaguard/test_decision_pipeline_pr005.py
tests/unit/alphaguard/test_quant_model_permissions_pr005.py
tests/unit/alphaguard/test_decision_persistence_api_pr005.py
```

没有修改 paper 路由/服务、订单、账户、持仓、费用、撮合、结算、前端视觉或真实券商
代码。

### DecisionContext 与 ContextBuilder

`DecisionContext` 为 frozen Pydantic 对象，Schema 版本
`decision-context-v1`，包含：

- analysis/user/candidate/symbol/market/trade_date；
- snapshot/proposal/strategy/factor-set/regime 的全部版本身份；
- 完整 `QuantTradeProposal`、`MarketRegimeResult`、factor summary/result IDs；
- price/financial/news/announcement/account/portfolio 六组 EvidenceRef；
- data quality、risk flags、missing evidence；
-普通/顶尖 Prompt 版本、创建时间和 `context_hash`。

`context_hash` 对排除 ID/hash/创建时间后的规范 JSON 使用 UTF-8、确定性排序、
固定 separators、禁止 NaN 和 SHA-256。同一输入得到相同哈希；对象创建后不可更新，
同一 analysis 内容冲突会失败。

ContextBuilder 只读取：

1. 已保存且哈希有效的 EvidenceSnapshot；
2. `SnapshotDataResolver` 逐项解析的 raw refs；
3. 已保存、身份和 input hash 均一致的 FactorResult；
4. 已保存 MarketRegimeResult、QuantTradeProposal、策略定义和候选身份；
5. 快照显式引用的账户、持仓、订单完整性摘要、标的交易状态和交易日历。

不按 symbol 查询最新行情/新闻/财报/持仓，不调用外部数据接口，不读取快照截止后的
证据，不允许 Prompt 自行搜索或补全。证据按类别、时间、引用 ID 确定性排序，不复制
无限原文。FactorResult 作为派生证据时，Builder 会继续验证其所有底层输入都存在于
快照 raw refs。

在模型调用之前 fail-closed 检查：

- DataQuality 不能为 FAIL；
- 必须有行情、账户、交易日历和标的交易状态证据；
- 停牌、涨跌停和 ST 状态字段不能缺失；
- BUY 必须有可验证组合快照，除非快照明确证明空组合；
- SELL/REDUCE 必须有目标持仓及 available quantity；
- 任一 user/symbol/market/trade_date/snapshot/proposal/strategy/version 身份不一致
  立即写 `DECISION_CONTEXT_INVALID`，不调用任何模型。

### 模型输入证据边界、Prompt 和执行元数据

PR-002 的 legacy Prompt 未覆盖。PR-005 新版本：

```text
normal_trade_plan_quant_v1
normal_trade_plan_revision_v1
top_review_decision_quant_v1
```

Trader 的量化路径只从规范化 DecisionContext、原 QuantTradeProposal 和可选
RevisionRequest 生成输入；Risk Judge 同时读取 DecisionContext、QuantProposal、
NormalTradePlan、MarketRegime、快照账户/组合证据、风险政策摘要和风险事件，不只读
普通模型结论。旧报告和 memory 文本不进入 PR-005 机器输入。

`ModelExecutionMeta` 向后兼容扩展并在 PR-005 正式路径强制保存：

```text
provider/model_name/model_version
prompt_name/prompt_version/template_hash
context_hash/input_hash/raw_output_hash
request_id/trace_id/attempt_number
started_at/finished_at/latency_ms/execution_status
error_type/error_message
```

成功结果必须有输出哈希；失败同样保留调用元数据。日志不保存密钥、完整认证头或原始
敏感输出。

### NormalTradePlan 与 QuantTradeProposal 约束

现有 NormalTradePlan 采用向后兼容可选字段增加：

```text
analysis_id
decision_context_id
symbol
market
trade_date
strategy_id
strategy_version
revision_round
supersedes_plan_id
revision_request_id
```

旧分析可以缺失，PR-005 正式路径全部强制匹配。只有：

```text
status=TRIGGERED
action_candidate in BUY/SELL/REDUCE
automated_execution_allowed=false
```

的 QuantTradeProposal 才进入模型。WATCH、REJECTED、INSUFFICIENT_DATA 和
INVALID_INPUT 直接形成明确终止，不调用普通或顶尖模型。

普通模型提出交易时必须：

- action 与 QuantProposal 完全同向；
- snapshot/proposal/context/strategy/symbol/market/trade_date 全部一致；
- max position 不超过 QuantProposal；
- EvidenceRef 必须存在于 DecisionContext；
- 保留完整退出/失效条件和有效期；
- `target_price=null` 合法且不会补价。

反向交易、越权仓位、快照外证据、缺失执行元数据均转为明确 INVALID_OUTPUT；
MODEL_FAILED/INVALID_OUTPUT/INSUFFICIENT_DATA 不会转换成 HOLD。

### TopReviewDecision 权限与降险白名单

顶尖模型是风险终审，不是第二个 Trader。`CONFIRM` 只能确认完整同向
PROPOSE_TRADE。`RISK_ADJUST` 第一版只接受可被 Python 证明的纯降险：

- 降低 initial/max position 和 confidence；
- entry zone 只能缩为原区间子集；
- valid_until 只能缩短；
- stop/reduce/exit/invalidation/main risks 只能保留原项并追加；
- 不改变 action、strategy、snapshot、proposal、context、symbol、market、
  trade_date、核心 thesis、证据和其他计划身份；
- 不把 null target_price 变成价格。

提高仓位、扩大区间、延长有效期、删除原条件、修改 action/strategy/证据、增加目标价
均为非法调整。顶尖模型如认为方向错误必须 REJECT，不能发起或反转交易。

MATERIAL_REVISION 也不能借重大修订暗含提高仓位/置信度、扩大入场、延长有效期、
删除既有风险条件、改变 add conditions、补目标价或更改身份/方向；这类输出直接
INVALID_OUTPUT。

### MATERIAL_REVISION 一轮返回和 RevisionRequest

`RevisionRequest` 为 frozen `revision-request-v1`，保存 request/analysis/snapshot、
original plan、review、固定 `revision_round=1`、requested changes、material fields、
risk findings、constraints 和创建时间。

流程严格为：

```text
round 0 MATERIAL_REVISION
  -> 保存 RevisionRequest
  -> 普通模型生成 revision_round=1 且带 supersedes_plan_id/revision_request_id 的计划
  -> 顶尖模型第二次且最后一次审核
```

修订模型可以 WAIT/NO_TRADE/INSUFFICIENT_DATA，但不能换方向、换快照或引入外部证据。
第二轮再次 MATERIAL_REVISION 固定触发 `REVISION_LIMIT_REACHED` 和
CONSENSUS_REJECT；不存在递归或第三次模型调用。

### ConsensusDecision 与 ConsensusEngine

`ConsensusDecision` 版本 `consensus-decision-v1`，保存 consensus/analysis/snapshot/
proposal/plan/review ID、状态、最终计划及 SHA-256、revision round、是否需普通模型
再确认、原因、校验错误、`consensus-policy-v1` 和时间。

ConsensusEngine 为纯 Python，不导入或调用 LLM，必检：

- context/proposal/plan/review 的全部身份、方向、版本和 revision round；
- proposal 必须 TRIGGERED，plan 必须 PROPOSE_TRADE；
- Prompt/模型执行元数据和 context/input/output hash；
- EvidenceRef 必须存在于 DecisionContext；
- proposal/plan 有效期；
- review 必须指向当前 plan；
- adjusted plan 必须为严格白名单纯降险；
- 最终计划 Pydantic Schema 和 final plan hash；
- 重大修改最多一轮。

状态映射：

```text
PROPOSE_TRADE + CONFIRM                 -> CONSENSUS_PASS
PROPOSE_TRADE + 合法 RISK_ADJUST       -> CONSENSUS_PASS（使用 adjusted plan）
round 0 MATERIAL_REVISION              -> CONSENSUS_REVISE
round 1 CONFIRM/合法 RISK_ADJUST       -> CONSENSUS_PASS
round 1 MATERIAL_REVISION              -> CONSENSUS_REJECT
NO_TRADE/WAIT/REJECT                   -> CONSENSUS_REJECT
MODEL_FAILED/INVALID_OUTPUT/身份或哈希错误 -> CONSENSUS_INVALID
```

只有 `CONSENSUS_PASS + final_plan != null` 才调用 HardRiskEngine。

### RiskPolicy

版本化 YAML 为 `risk-policy-v1@1.0.0`：

```text
max_single_position_pct=0.10
max_total_exposure_pct=0.60
max_industry_exposure_pct=0.25
max_new_positions_per_day=3
min_cash_reserve_pct=0.20
max_order_participation_rate=0.05
st_buy_enabled=false
allow_buy_when_suspended=false
allow_sell_when_suspended=false
cn_buy_lot_size=100
allow_cn_sell_odd_lot=true
decision_validity_required=true
snapshot_integrity_required=true
data_quality_fail_blocked=true
live_trading_enabled=false
```

当前没有可靠业务阈值的 minimum average amount、maximum volatility risk score 和
maximum event risk score 保持 null，对应规则返回 NOT_APPLICABLE；没有伪造阈值。
但数量参与率仍要求可靠 average_amount_20d，缺失时 SUSPEND。

注册表使用 `config_hash`；相同版本同内容幂等，同版本不同内容拒绝覆盖。种子脚本
默认 dry-run，必须显式 `--execute`；不提供公开 RiskPolicy 写 API。

### RiskRuleResult 与 HardRiskEngine

`RiskRuleResult` 版本 `risk-rule-result-v1`，每条规则保存 rule ID/version、状态、
observed/threshold、原/调整仓位和数量、证据、原因及时间，并在 Schema 层禁止增加
仓位或数量。

HardRiskEngine 是纯 Python、只读取已解析快照，不调用 LLM、实时数据、账户写服务或
订单服务。规则版本均为 1.0.0：

```text
AG-RISK-INTEGRITY
AG-RISK-VALIDITY
AG-RISK-TRADING-STATUS
AG-RISK-ACCOUNT
AG-RISK-PRICING
AG-RISK-POSITION-LIMITS
AG-RISK-NEW-POSITIONS
AG-RISK-DUPLICATE-ORDER
AG-RISK-LIQUIDITY
AG-RISK-VOLATILITY
AG-RISK-EVENT
AG-RISK-TRADING-CALENDAR
AG-RISK-QUANTITY
```

校验覆盖：

- snapshot/context/consensus/final-plan/hash/身份/DataQuality/active policy；
- proposal 和 plan 有效期；
- 停牌、ST、涨停买入、跌停卖出、政策禁买名单；
- 账户存在、ACTIVE/ENABLED、user/market/currency、现金/equity；
- 当前/交易后单股、总仓位、行业仓位、现金保留和市场状态总敞口；
- 当日新开仓、同向有效订单及订单快照完整性；
- 流动性、波动和事件政策；
- 快照交易日历、持仓数量、available_qty/T+1 和参与率。

固定禁止条件/完整性错误优先 REJECT；关键证据、系统、账户或日历缺失为 SUSPEND；
有可安全降低额度为 REDUCE；其余适用规则通过才 PASS。所有规则结果均保存，不能因
一条通过覆盖更严格结果。HardRisk 输出 action 始终与 final plan 相同。

### 仓位与数量计算

BUY 批准仓位不大于：

```text
min(
  final_plan.max_position_pct,
  policy single-position cap,
  min(policy, regime) total-exposure remaining,
  industry-exposure remaining,
  cash-after-reserve remaining
)
```

只会降低，不会提高。保守定价使用 entry zone 上界；没有 entry zone/可靠快照价格时
SUSPEND。批准数量再受现金/仓位及 5% average amount participation 上限约束；CN 买入
向下取整到 100 股，取整后为 0 时 REJECT。

SELL/REDUCE 只取 `min(held quantity, available_qty)`，不超过 T+1 可卖数量；退出允许
奇数股，REDUCE 需要取整时只会向下。批准数量只是风险上限，不冻结资金且不是订单量。

### T+1 与交易日历

`earliest_eligible_execute_at` 只来自快照明确引用的、trade_date 之后第一个开市
session；绝不使用自然日 `+1`。缺少可靠日历时规则 SUSPEND 且执行时间为 null。
所有结果固定 `requires_execution_recheck=true`，因为 PR-006 在真正创建执行意图前
仍必须重新检查动态交易状态。

### RiskDecision

`RiskDecision` 版本 `risk-decision-v1`，保存 risk/analysis/consensus/snapshot/
proposal/account 身份、PASS/REDUCE/REJECT/SUSPEND、固定方向、原/批准仓位和数量、
定价引用、最早执行时间、全部规则、原因、policy 版本、input hash 和创建时间。

`input_hash` 包含 snapshot hash、resolved snapshot input hash、context hash、
consensus hash、policy hash 和 account ID。Schema 和所有构造路径都强制
`order_intent_created=false`。

### DecisionPipeline、Candidate 状态和幂等

公开编排入口：

```python
evaluate_quant_proposal(
    quant_proposal_id: str,
    account_id: str | None = None,
)
```

流程按 Context -> normal -> top -> optional single revision -> consensus -> hard risk
顺序保存对象和审计。候选状态只会走：

```text
SIGNAL_DETECTED -> AI_ANALYZING
PROPOSE_TRADE   -> PLAN_PROPOSED -> TOP_REVIEWING
PASS/REDUCE     -> APPROVED
NO_TRADE/REJECT -> REJECTED
WAIT/数据不足/模型失败 -> COOLDOWN
系统/风控暂停或非法 -> RISK_ALERT/COOLDOWN
```

不会进入 ORDER_PENDING 或 POSITION_HELD。

`decision_run_key = SHA-256(user_id, snapshot_id, quant_proposal_id, account_id,
decision-pipeline-v1)`。相同 terminal run 默认返回已保存结果，不重复调用模型或写
plan/review/consensus/risk；同身份 proposal input hash 改变时写完整性冲突并拒绝。
只有内部显式 `retry_failed=true` 才能重试失败，公开 API 不暴露 force/retry；
每次重试增加 attempt_number，历史失败计划、review、事件和 run 不覆盖。

### MongoDB 集合、索引与数据变化

新增：

```text
ag_decision_contexts
ag_consensus_decisions
ag_risk_policies
ag_risk_decisions
ag_decision_events
ag_revision_requests
ag_decision_runs
```

NormalTradePlan 和 TopReviewDecision 继续在 `analysis_reports` 中保存当前对象与历史
数组，旧文档字段均可选。

索引包含指令要求的 context/consensus/risk/policy/event/revision 唯一身份与查询索引，
另加 `(decision_run_key, attempt_number)` 唯一索引和 terminal 查询索引。脚本只
create，不 drop；同名规格冲突失败。实际重复执行全部显示 `unchanged`。

真实开发库数据变化：

- 已登记 1 条 `risk-policy-v1@1.0.0`，ACTIVE 且 live trading false；
- PR-005 决策、context、consensus、risk、revision、event、run 均为 0；
- `analysis_reports/paper_accounts/paper_positions/paper_orders/paper_trades` 均为 0；
- 没有更新或删除 PR-003/PR-004 历史数据。

### API

复用现有 `get_current_user`、response wrapper、request trace 和 MongoDB：

```text
POST /api/alphaguard/decisions/evaluate/{quant_proposal_id}
GET  /api/alphaguard/analyses/{analysis_id}
GET  /api/alphaguard/decisions/{plan_id}
GET  /api/alphaguard/reviews/{review_id}
GET  /api/alphaguard/consensus/{consensus_id}
GET  /api/alphaguard/risk-decisions/{risk_decision_id}
GET  /api/alphaguard/decision-events
```

evaluate body 只允许可选 account_id。客户端不能上传计划、review、consensus、risk、
Prompt、政策或模型桩；读取按当前 user 的 DecisionContext 归属授权。没有 update/
delete、OrderIntent、自动订单或 `/paper/order` 调用。

### 审计事件

append-only `ag_decision_events` 保存 event/analysis/user/candidate/snapshot/proposal/
plan/review/consensus/risk ID、round、attempt、trace、reason、时间和 Schema 版本。

已覆盖：

```text
DECISION_CONTEXT_CREATED / DECISION_CONTEXT_INVALID
NORMAL_MODEL_STARTED / NORMAL_MODEL_COMPLETED / NORMAL_MODEL_FAILED
NORMAL_PLAN_REJECTED
TOP_REVIEW_STARTED / TOP_REVIEW_COMPLETED / TOP_REVIEW_FAILED
MATERIAL_REVISION_REQUESTED / NORMAL_REVISION_COMPLETED / REVISION_LIMIT_REACHED
CONSENSUS_PASS / CONSENSUS_REVISE / CONSENSUS_REJECT / CONSENSUS_INVALID
HARD_RISK_STARTED / HARD_RISK_PASS / HARD_RISK_REDUCE
HARD_RISK_REJECT / HARD_RISK_SUSPEND
DECISION_RUN_REUSED / DECISION_INTEGRITY_CONFLICT
```

### 测试和回归结果

| 验证项 | 结果 |
| --- | --- |
| PR-005 Context/Schema/模型权限/修订/Consensus/HardRisk/Pipeline/API/索引 | `88 passed, 4 warnings` |
| PR-001～PR-004 合并回归 | `145 passed, 14 warnings` |
| 其中 PR-001 安全与配置 | `24 passed` |
| 其中 PR-002 结构化决策 | `40 passed` |
| 其中 PR-003 候选与快照 | `40 passed` |
| 其中 PR-004 量化研究 | `41 passed` |
| 全量测试收集 | `912 collected, 15 errors` |
| 前端 `npm run type-check` | 失败，仍为 34 个存量 `TS2345 DefaultRow` |
| 新增/修改 Python 文件 `py_compile` | 通过 |
| 全目录 `compileall` | 仅存量 `scripts/补充行业信息_akshare.py:81` 语法错误 |
| `git diff --check` | 通过 |
| FastAPI 安全启动 | `GET /api/health` HTTP 200 |
| FastAPI 实盘开关拒绝 | 退出码 3 |
| `app/worker.py` 实盘开关拒绝 | 退出码 1，资源初始化前 |
| `app/worker/analysis_worker.py` 实盘开关拒绝 | 退出码 1，资源初始化前 |
| MongoDB / Redis | Docker healthy，实际 ping `1.0 / True` |
| 决策索引脚本 | 重复执行全部 `unchanged` |
| 风险政策脚本 dry-run | 通过，无写入 |
| 风险政策 execute 幂等 | 两次均 `seeded_or_verified=risk-policy-v1@1.0.0` |
| Decision API 冒烟 | 认证、路由和只读/服务依赖替换通过 |
| 禁止订单依赖检查 | pipeline/consensus/hard-risk/router 无 OrderService、OrderIntent、PaperOrder、MatchingEngine 或 `/paper/order` 引用 |
| 交易副作用检查 | 订单、成交、现金、持仓变化均为 0 |

PR-004 收集为 824 项；PR-005 新增 88 项后为 912 项，增量完全对应本阶段专项测试。
15 个全量收集错误、34 个前端 TS2345 和中文脚本语法错误的文件及类别与 PR-004
完全一致，没有新增错误类别，也没有跳过测试或顺手修复无关存量技术债。

### 兼容性、设计差异与已知限制

1. 原设计建议将 context/consensus/risk 拆为三个 Schema 文件；实际用
   `tradingagents/alphaguard/decision_control_schemas.py` 作为单一严格真相来源，
   `app/schemas/alphaguard/decision.py` 只做后端重导出，避免跨层循环。安全语义不变。
2. 原蓝图可理解为直接改写 PR-002 legacy LangGraph；实际保留旧 Graph 用于旧分析和
   展示兼容，新认证 Decision API 通过独立 `DecisionPipeline` 编排正式 PR-005 链。
   两者共用同一 Trader/Risk Judge 结构化节点和 Schema；旧文本不能进入正式
   Consensus/HardRisk。
3. 当前真实库没有可靠账户/组合/标的交易状态/交易日历公共数据。没有凭空适配或用
   最新数据库数据代替快照；真实提案在补齐显式 raw refs 前会于 ContextBuilder 或
   HardRisk SUSPEND/fail-closed。
4. minimum liquidity、maximum volatility/event risk 阈值没有已确认业务依据，按
   蓝图保持 null；后续只能通过新 RiskPolicy 版本调整，不能覆盖 v1。
5. PR-005 RiskDecision 不是执行时行情担保，PR-006 必须再次验证交易状态、价格、
   账户、T+1、现金和可卖数量。
6. MongoDB 只新增集合/索引和可选分析字段，旧文档读取兼容；公开变化只有新增认证
   API，无旧 API 破坏性变化。

### 明确未实施 PR-006 及以后

```text
OrderIntent
PaperOrder 自动创建
MatchingEngine / FeeEngine
资金冻结、账户/现金/持仓写入
自动成交、结算和自动模拟交易
人工模拟交易规则修改
真实券商连接
执行时动态风控担保
Champion/Challenger
策略自动晋升
全市场自动推荐
Dify / Qlib / FinRL / RD-Agent
```

### 数据和代码回退

安全代码边界为：

```text
87026f5
alphaguard-pr004-quant-research
```

PR-005 当前尚未提交，回退时必须保留可恢复性：

1. 先把 `git status --short` 保存到工作区外；
2. 使用
   `git diff --binary alphaguard-pr004-quant-research > <安全目录>/pr005.patch`
   保存 tracked patch，并将本节新增文件复制到带时间戳的工作区外备份；
3. 仅反向应用该 PR-005 patch 并移走本节新增文件，不使用 `git reset --hard`、
   `git checkout --` 或其他会覆盖用户工作的命令；
4. PR-005 后续形成独立提交时，优先用 `git revert <pr005-commit>` 生成可审计回退；
5. PR-001 安全配置以及 PR-003/PR-004 集合和历史数据绝不回退；
6. 新索引和空 PR-005 集合可安全保留。若必须物理回退，先对上述 7 个精确集合执行
   `mongodump` 并验证备份，再只删除精确 PR-005 索引/集合，禁止通配 drop；
7. 唯一实际业务数据为 `risk-policy-v1@1.0.0`。物理删除前必须先备份该精确记录；
   更安全的逻辑回退是将新版本政策标为 INACTIVE，而不是覆盖 v1 内容；
8. 移除新增 router 后复跑 PR-001～PR-004 的 145 项，并重新验证 FastAPI HTTP 200、
   API/两 Worker 实盘拒绝、MongoDB/Redis healthy、paper 数据无变化。

### 当前 Git 状态与下一阶段闸门

PR-001～PR-004 均为独立提交和标签。PR-005 当前是相对于
`alphaguard-pr004-quant-research` 的未提交修改与新增文件，没有混入 PR-004。
最终 `git diff --check` 通过。

PR-005 到此停止。不得开始 PR-006；进入 PR-006 必须由人工另行授权，并先为当前
PR-005 建立独立提交或可恢复检查点。

---

## PR-006：Automatic Paper Trading

### 完成结论和安全边界

PR-006 已完成。开始本阶段前已确认工作区干净、PR-001～PR-005 标签完整，并将
PR-005 固定为：

```text
76f62e5 feat(pr-005): establish consensus and hard risk
alphaguard-pr005-consensus-risk
```

本阶段建立了独立于人工即时成交接口的自动模拟交易链：

```text
RiskDecision / benchmark source
  -> DB-backed ExecutionOutbox
  -> OrderIntentFactory / BenchmarkExecutionSafetyGate
  -> immutable OrderIntent
  -> centralized PaperOrder state machine
  -> cash or FIFO lot reservation
  -> immutable ExecutionMarketSnapshot
  -> deterministic MatchingEngine
  -> immutable PaperFill + Decimal FeeEngine
  -> recoverable Settlement Saga
  -> PositionLot / Position / Account / Ledger
  -> DailyAccountSnapshot
```

所有 PR-006 Schema 继承固定约束：

```text
execution_environment = PAPER
live_execution_allowed = false
```

PR-001 的 `system_mode=SIM_AUTONOMOUS` 和 `live_trading_enabled=false` 未修改；
安全配置下 FastAPI 可启动，不安全配置下 FastAPI 和两套 Worker 仍在资源初始化前
拒绝启动。代码没有 Broker SDK、BrokerAdapter、实盘订单对象或券商网络调用。

### 实际修改和新增文件

核心 Schema、集合及配置：

- `tradingagents/alphaguard/paper_schemas.py`
- `app/schemas/alphaguard/paper.py`
- `app/models/alphaguard/paper_collections.py`
- `app/models/alphaguard/__init__.py`
- `tradingagents/alphaguard/mongo_indexes.py`
- `tradingagents/alphaguard/candidate_schemas.py`
- `config/alphaguard/paper/account_policy_v1.yaml`
- `config/alphaguard/paper/execution_policy_v1.yaml`
- `config/alphaguard/paper/fee_policy_v1.yaml`

服务和编排：

- `app/services/alphaguard/paper_storage.py`
- `app/services/alphaguard/paper_policy_registry.py`
- `app/services/alphaguard/paper_audit_service.py`
- `app/services/alphaguard/paper_calendar_service.py`
- `app/services/alphaguard/paper_account_service.py`
- `app/services/alphaguard/benchmark_execution_safety_gate.py`
- `app/services/alphaguard/execution_outbox_service.py`
- `app/services/alphaguard/order_intent_factory.py`
- `app/services/alphaguard/paper_order_service.py`
- `app/services/alphaguard/execution_market_snapshot_service.py`
- `app/services/alphaguard/matching_engine.py`
- `app/services/alphaguard/fee_engine.py`
- `app/services/alphaguard/paper_execution_service.py`
- `app/services/alphaguard/settlement_service.py`
- `app/services/alphaguard/paper_candidate_sync_service.py`
- `app/services/alphaguard/paper_task_service.py`
- `app/services/alphaguard/paper_jobs.py`
- `app/services/alphaguard/decision_pipeline.py`
- `app/services/alphaguard/candidate_pool_service.py`
- `app/services/alphaguard/index_service.py`

API、调度、脚本和前端：

- `app/routers/alphaguard_paper.py`
- `app/main.py`
- `scripts/init_alphaguard_paper_indexes.py`
- `scripts/seed_alphaguard_paper_policies.py`
- `scripts/create_alphaguard_paper_accounts.py`
- `frontend/src/api/alphaguardPaper.ts`
- `frontend/src/components/paper/AlphaGuardAutoPaperPanel.vue`
- `frontend/src/views/PaperTrading/index.vue`

专项测试：

- `tests/unit/alphaguard/pr006_helpers.py`
- `tests/unit/alphaguard/test_paper_schemas_pr006.py`
- `tests/unit/alphaguard/test_fee_matching_snapshot_pr006.py`
- `tests/unit/alphaguard/test_paper_accounts_orders_settlement_pr006.py`
- `tests/unit/alphaguard/test_outbox_intent_safety_pr006.py`
- `tests/unit/alphaguard/test_paper_security_jobs_api_pr006.py`
- `tests/integration/alphaguard/test_automatic_paper_trading_pr006.py`

原有 `app/routers/paper.py`、`frontend/src/api/paper.ts` 和人工集合未修改。

### 自动账户和人工账户隔离

自动账户只使用 `ag_paper_*` / `ag_*` 专用集合，人工账户继续使用：

```text
paper_accounts
paper_positions
paper_orders
paper_trades
```

自动账户类型为：

| 账户类型 | 决策来源 | 审核语义 | 是否影响主 Candidate |
| --- | --- | --- | --- |
| `PAPER_QUANT` | `QuantTradeProposal(TRIGGERED)` | benchmark only，不伪造 Consensus/HardRisk | 否 |
| `PAPER_NORMAL` | `revision_round=0` 的 `NormalTradePlan(PROPOSE_TRADE)` | benchmark only，不使用顶尖模型调整计划 | 否 |
| `PAPER_TOP_CONFIRMED` | `RiskDecision(PASS/REDUCE)` | 必须已有 `ConsensusDecision=PASS` 和 HardRisk 批准 | 是 |
| `PAPER_CHALLENGER` | PR-006 无自动来源 | 只建账户和执行能力，保持空账户 | 否 |

账户唯一身份为 `user_id + account_type + market`。初始化为 create-only 幂等逻辑：
已有账户和余额只复用，不覆盖、不重置。自动市场只接受 `CN/CNY`，金额和结算全部
使用 `Decimal` / MongoDB `Decimal128`。

初始资金来自 `paper-account-policy-v1@1.0.0`，默认值与现有人工账户默认资金一致，
但不共享账户文档或余额。政策不散落在业务代码中。

### BenchmarkExecutionSafetyGate

`BenchmarkExecutionSafetyGate` 是纯 Python 机械准入门，只为 Quant/Normal 基准账户
检查账户 ACTIVE、CN/CNY、现金、持仓、T+1 可卖 lot、仓位上限、总敞口、重复有效
订单、A 股 100 股整数手、执行日期和交易状态。输出独立
`BenchmarkExecutionDecision`，明确：

```text
benchmark_only = true
consensus_approved = false
hard_risk_approved = false
```

它不执行模型终审，也不命名为 HardRiskDecision。关键账户、价格、日历或交易状态
缺失时为 `SUSPEND`，不会假设资金充足、持仓为零或标的可交易。

### OrderIntent 和 OrderIntentFactory

`OrderIntent` create-only、哈希校验且不可变，保存 source、analysis/candidate、
snapshot/quant/plan/consensus/risk 标识、原始 action、side、数量、价格、执行窗口、
政策版本、账户状态快照和稳定幂等键。

映射规则：

- `BUY -> side=BUY + LIMIT`，限价只能来自最终计划 `entry_zone.upper`；
- `SELL/REDUCE -> side=SELL + MARKET_ON_OPEN`，保留 `original_action=REDUCE`；
- 无可靠 BUY 入场上界、持久化交易日历、合法数量或身份链时不创建 Intent；
- 不读取“最新价格”猜限价，不生成虚构卖价；
- 执行窗口只由 `trading_calendar` 中明确 `is_open/open/is_trading_day=true`
  的 CN session 生成，不使用自然日加减；
- 幂等身份为账户、source type、source object、side 和 execution policy；
- 同幂等键同内容复用，不同内容报完整性冲突。

`PAPER_TOP_CONFIRMED` 重新检查 Risk/Consensus、approved quantity、account/symbol/
market/snapshot、有效期和执行日期。历史 `RiskDecision.order_intent_created=false`
永远不改写；创建事实记录在 Outbox、Intent 和事件中。

### ExecutionOutbox

DecisionPipeline 只持久化以下事件，不直接创建订单或改资产：

```text
CREATE_QUANT_BENCHMARK_INTENT
CREATE_NORMAL_BENCHMARK_INTENT
CREATE_TOP_CONFIRMED_INTENT
```

Outbox 状态为 `PENDING/PROCESSING/COMPLETED/FAILED/DEAD_LETTER`，保存 attempt、
next attempt、经脱敏错误、幂等键和错误历史。重复消费不会重复创建 Intent、Order
或预留；超过重试上限进入 DEAD_LETTER 并写审计，不静默丢失。

### PaperOrder 状态机与预留

集中状态机为：

```text
CREATED -> RESERVED -> SUBMITTED -> PENDING
PENDING -> PARTIALLY_FILLED -> SETTLEMENT_PENDING -> PENDING/FILLED
SETTLEMENT_PENDING -> SETTLEMENT_FAILED -> SETTLEMENT_PENDING
CREATED/RESERVED/SUBMITTED/PENDING/PARTIALLY_FILLED
  -> CANCELLED/REJECTED/EXPIRED
```

比总蓝图增加 `SETTLEMENT_PENDING` 和 `SETTLEMENT_FAILED`，原因是当前 MongoDB 不
支持事务，订单必须在 Saga `COMMITTED` 后才可以变为 `PARTIALLY_FILLED/FILLED`。
所有迁移通过服务校验并增加 `order_version`，禁止任意字符串覆盖。

BUY 预留以限价、最大成交金额和保守最大费用计算，将
`cash_available -> cash_reserved`；重复预留不重复扣款，实际消费后释放差额。
可用现金永不为负，预留不足时拒绝剩余成交。

SELL/REDUCE 按 FIFO 从 `available_from_date <= trade_date` 的 lot 分配，将可卖数量
转为 lot `reserved_quantity`。T+1 未解锁 lot 不可预留，同一 lot 不会重复冻结。
取消、拒绝、过期释放未成交余额；部分成交只消费实际成交部分。

### ExecutionMarketSnapshot

执行快照以 `symbol + CN + trade_date + data_version` 唯一，保存 Decimal OHLC/
prev_close、volume/amount、suspended/ST、明确 limit up/down、source refs、cutoff、
日线粒度和 immutable hash。

- 只读取指定交易日的现有日线记录；
- 当前日只允许收盘后构建，不读未来数据；
- 缺 OHLC、交易状态、涨跌停价格或哈希不一致时阻断；
- `tradestatus=1` 解释为可交易，`0` 解释为停牌；
- 未发现可靠涨跌停字段时不使用 10% 硬编码猜测；
- 同身份同内容复用，不同内容完整性冲突；
- `simulation_granularity=DAILY_OHLCV`、
  `matched_after_market_close=true`，不声称重建逐笔成交。

执行行情和每日账户快照调度也只在持久化明确开市日运行；日历缺失或闭市直接跳过。

### MatchingEngine、滑点和成交量

`matching-engine-v1` 为纯 Python、确定性、无 LLM、无网络、无账户写入：

- MARKET_ON_OPEN：BUY 为 open 加买入滑点，SELL 为 open 减卖出滑点；
- BUY LIMIT：开盘不高于限价取 open，否则日内 low 触及才取 limit；
- SELL LIMIT：开盘不低于限价取 open，否则日内 high 触及才取 limit；
- 成交价经过 `0.01` tick、限价边界和明确涨跌停边界；
- 停牌不成交；一字涨停不买、一字跌停不卖；
- 缺可靠停牌/涨跌停状态为 BLOCKED，不假设可交易；
- 容量为 `floor(volume * max_participation_rate)`，BUY 再向下取 100 股整数手；
- 最终数量不超过订单剩余、容量和有效预留；
- 同一订单同一交易日最多一个 Fill，由唯一索引保证；
- 未到 earliest、已过期或当日已有 Fill 均不撮合。

`paper-execution-policy-v1@1.0.0` 保存双边 5 bps 滑点、5% 成交量参与率、价格 tick、
BUY LIMIT、退出 MOO、5 个有效 session 和日线模拟粒度；业务代码不散落这些常量。

### FeeEngine、PaperFill、PositionLot 和 T+1

FeeEngine 使用 `Decimal`，由 `paper-fee-policy-v1@1.0.0` 提供佣金率、最低佣金、
卖出印花税、过户费和其他费用，输出不可变 `FeeBreakdown`，作用域为
`ORDER_TRADE_DATE`。规则缺失或版本不存在时阻断结算，不默认费用为 0。

现有 `paper_market_rules` 实际为空且无可依赖业务记录，因此没有假装复用；v1 参数
与现有人工模拟默认规则对齐并独立版本化，后续费率变化必须新增版本。

`PaperFill` 保存订单/Intent/账户、执行快照、交易日、数量、Decimal 成交价和名义
金额、费用明细、净现金影响、匹配/费用版本、幂等键和不可变哈希。唯一身份为
`order_id + trade_date`，重复匹配不会重复插入。

BUY 成交创建 PositionLot，成本包含分摊买入费用；`available_from_date` 只能来自
持久化交易日历的下一开市日。SELL/REDUCE 按 FIFO 消耗 lot，并支持部分卖出、
全部退出和剩余零股退出。Position 是 lot 汇总缓存；不一致时 reconciliation 写
完整性错误并阻断继续下单，fill/lot/ledger 是核对依据。

### SettlementService、Saga、账本和资产守恒

运行态确认 MongoDB `4.4.30` 为 standalone，`setName=null`；只读事务探针返回
MongoDB code 20，因此采用可恢复 Saga，不假装多集合事务原子性：

```text
PREPARED
  -> ACCOUNT_APPLIED
  -> POSITION_APPLIED
  -> LEDGER_APPLIED
  -> COMMITTED
FAILED / COMPENSATION_REQUIRED
```

每一步保存稳定幂等键和恢复状态。重复 fill 结算直接复用；进程中断后从已完成阶段
继续，不重复扣款、加仓、减仓或记账。未 `COMMITTED` 的订单保持
`SETTLEMENT_PENDING/FAILED`，绝不标为 FILLED。

不可变账本记录 `CASH_CHANGE/POSITION_COST_CHANGE/FEE_EXPENSE/REALIZED_PNL/
RESERVATION_RELEASE`，保存 before/after、fill、settlement 和幂等键。测试逐项验证：

- 无费用成交瞬间权益守恒；
- 有费用时权益变化只等于费用；
- 部分成交后已消费与剩余预留一致；
- 取消/过期只释放预留，不改变净资产；
- 重复任务不会产生第二次资产变化；
- 结算后现金、持仓和 lot 数量不为负。

### 取消、过期、Worker 和每日任务

唯一写操作 API 为订单取消。允许取消 CREATED/RESERVED/SUBMITTED/PENDING/
PARTIALLY_FILLED，已成交部分保留，仅释放剩余现金或 lot 预留；重复取消幂等，不
删除订单或 Fill。

现有 APScheduler 中注册的 DB-backed 幂等任务包括：

```text
process_execution_outbox
settle_pending_fills
expire_orders
release_stale_reservations
roll_position_lot_availability
build_execution_market_snapshots
match_orders_for_trade_date
create_daily_account_snapshots
reconcile_paper_accounts
```

同时保留 `create_order_intents` 和 `submit_paper_orders` 显式任务入口。实际调度将
factory、order creation 和 reservation 合并在同一 Outbox 消费工作流，减少
Outbox COMPLETED 但订单未创建的间隙；各内部步骤仍独立幂等。这是相对蓝图的实现
差异，不改变安全边界。

每次任务运行保存 job type、trade date、幂等键、状态、attempt、起止时间和脱敏
错误。同一 job key 重跑不重复创建 Intent/Order/Fill/Settlement/解锁/快照。

### DailyAccountSnapshot 和 Candidate

每日账户快照使用目标开市日收盘价，保存 Decimal 现金、冻结资金、持仓市值、权益、
已实现/未实现盈亏、费用、gross exposure、持仓数、价格引用和输入哈希。价格缺失
时 `valuation_complete=false` 并列出缺失标的，不按 0 静默宣称估值正常。

只有 `PAPER_TOP_CONFIRMED` 同步主 Candidate：

```text
Intent / PENDING / PARTIALLY_FILLED -> ORDER_PENDING
BUY FILLED -> POSITION_HELD
SELL/REDUCE 后仍有仓位 -> POSITION_HELD
清仓 -> WATCHING
终止且无仓位 -> APPROVED/WATCHING/COOLDOWN（按原因）
```

Quant、Normal、Challenger 永不改变主 Candidate。同步失败只写事件并交由
reconciliation 修复，不回滚已合法提交的结算。

### MongoDB 集合和索引

PR-006 使用 16 个专用集合：

```text
ag_paper_accounts
ag_paper_account_snapshots
ag_benchmark_execution_decisions
ag_order_intents
ag_paper_orders
ag_paper_fills
ag_paper_positions
ag_paper_position_lots
ag_paper_reservations
ag_paper_ledger_entries
ag_settlement_records
ag_execution_market_snapshots
ag_execution_outbox
ag_paper_job_runs
ag_paper_events
ag_paper_policies
```

建立 49 个 create-only 索引，覆盖蓝图要求的账户、Intent、Order、Fill、Position、
Lot、Reservation、Snapshot、Settlement、Outbox、AccountSnapshot、Job 和 Event
唯一/查询键。脚本两次 execute 均显示 `created=0 unchanged=49 failed=0`，因为应用
启动索引初始化已先创建相同索引；没有删除或覆盖任何旧索引，也未触碰人工集合。

三项脚本默认 dry-run，只有 `--execute` 才写入：

- 政策 dry-run 输出 3 个稳定配置哈希，无写入；
- 账户 dry-run 输出 4 个账户类型和初始资金，无写入；
- 索引 dry-run 输出 16 个集合、49 个索引，无写入；
- 同版本政策不同内容拒绝覆盖，账户初始化不覆盖余额。

当前真实库 PR-006 accounts/intents/orders/fills/lots/settlements 均为 0；人工
paper_accounts/positions/orders/trades 也保持 0。PR-006 没有迁移或修改业务数据。

### API、前端和审计

认证 API 前缀为 `/api/alphaguard/paper`，新增 10 个 GET 查询端点和唯一 POST：

```text
POST /orders/{order_id}/cancel
```

客户端不能创建 OrderIntent、PaperOrder、PaperFill、Settlement、账户余额或持仓，
不能上传成交价、政策或模型结果，也没有公共结算触发接口。未认证访问返回 401。

PaperTrading 页面增加“人工模拟 / AlphaGuard 自动模拟”模式开关。自动视图支持
账户类型切换、现金/冻结资金/总资产、持仓/可卖数量/lot、订单/部分成交、Fill、
费用、source/Risk/Candidate/Analysis 关联和受控取消；没有下单、改价、改
RiskDecision 或实盘开关。原人工页面和 API 保持原样。

`ag_paper_events` 记录账户、Outbox、Intent、Order、Reservation、Snapshot、
Matching、Settlement、Lot、AccountSnapshot 和完整性事件，包含 user/account/
intent/order/fill/settlement/source/risk/trace/reason/time/schema 等关联标识；
异常不只留普通日志。

### 测试和运行验证

| 验证项 | 结果 |
| --- | --- |
| PR-006 Schema/账户/来源/安全门/预留/状态机 | 通过 |
| Snapshot/Matching/Fee/Fill/Lot/T+1 | 通过 |
| Saga/恢复/账本/资产守恒 | 通过 |
| Outbox/任务/取消/过期/幂等 | 通过 |
| Candidate/人工隔离/禁止实盘/E2E | 通过 |
| PR-006 专项合计 | `64 passed, 67 warnings` |
| PR-001～PR-005 可运行选择集 | `233 passed, 13 warnings` |
| 其中 PR-001 安全测试 | 保持通过 |
| 前端 `npm run type-check` | 仍为 34 个存量 `DefaultRow TS2345`，无新增类别 |
| 修改 Python 文件 `py_compile` | 通过 |
| 全项目 compileall | 仅存量 `scripts/补充行业信息_akshare.py:81` 中文脚本语法错误 |
| `git diff --check` | 通过 |
| 全量测试收集 | 完成结果 `974 collected, 15 errors`；随后新增 2 个已独立通过测试，当前规模可确定为 976；最终复跑因旧模块收集期外部连接超过 10 分钟无输出而终止 |
| FastAPI 安全启动 | `127.0.0.1:18006`，`/api/health` HTTP 200 |
| 自动 Paper API 冒烟 | 未认证 accounts 返回 401，认证边界生效 |
| FastAPI 不安全配置 | `live_trading_enabled=true` 时 exit 3、启动前阻断 |
| `app/worker.py` 不安全配置 | exit 1、启动前阻断 |
| `app/worker/analysis_worker.py` 不安全配置 | exit 1、启动前阻断 |
| MongoDB / Redis | Mongo ping=1；Redis PONG；Docker 健康 |
| MongoDB 事务能力 | standalone，事务探针 code 20，使用 Saga |
| 索引脚本 | 两次 execute 均 49 unchanged；dry-run 通过 |
| 政策/账户脚本 | dry-run 通过，无写入 |

专项测试使用固定内存 Mongo、固定交易日历、固定 OHLCV 和模型/决策桩，不访问真实
模型、行情、券商或外部网络。静态与运行测试证明：

- PR-006 服务不导入人工 `app.routers.paper`；
- 不调用旧 `/paper/order`；
- 无 BrokerAdapter、券商 SDK 或真实订单网络请求；
- 自动操作不写 `paper_accounts/paper_positions/paper_orders/paper_trades`；
- 人工路由不写 `ag_paper_*`；
- Challenger 无自动 Intent；
- 所有自动对象为 PAPER 且 live_execution_allowed=false；
- 重复整条任务链不产生第二次资产变化。

### 设计差异、兼容性和已知限制

1. 原蓝图优先 MongoDB transaction；实际 MongoDB 4.4 standalone 不支持，因此实现
   可恢复 Saga，并增加 `SETTLEMENT_PENDING/SETTLEMENT_FAILED`。安全性更明确：
   未提交结算不会被当作 FILLED。
2. 原蓝图列出独立 create/submit 定时步骤；实际保留任务入口但生产调度由 Outbox
   consumer 串联工厂、订单和预留，各步骤仍幂等，避免可靠事件与订单之间的窗口。
3. 当前真实 `trading_calendar` 没有可用 session；真实自动订单会 fail-closed，
   不会用周末、节假日或自然日 +1。上线数据准备必须先加载版本化交易日历。
4. 当前真实日线只有 OHLCV/pre_close 和部分 `tradestatus/isST`，没有可靠板块涨跌
   停价格。缺 limit_up/down 时执行快照阻断，不硬编码 10%。
5. 当前 `paper_market_rules` 无记录，因此 fees 使用独立不可变 v1 政策；没有把缺失
   规则解释为零费用。
6. 第一版只支持 CN/CNY 日线盘后近似，不支持 HK/US、期货期权、融资融券、做空、
   分钟/逐笔撮合。原人工 HK/US 兼容未删除。
7. 当前政策和四类账户仅完成 dry-run，生产数据库没有自动创建；需人工明确执行
   seed/account 脚本并补齐日历/交易状态数据后，真实自动链才会运行。
8. 前端 34 个 DefaultRow TS2345、15 个旧收集错误和中文脚本语法错误均为既有上游
   限制；第一次全量收集实际完成为 974/15，之后新增的 2 项已在 64 项专项中通过。
   最终全量复跑在旧测试收集期建立外部连接并超过 10 分钟无输出后终止；976 是
   `974 + 2` 的确定性规模推算，不宣称该次命令成功完成。没有为了数字跳过 PR-006
   新测试，也没有顺手修复无关技术债。
9. PR-006 只保存 DailyAccountSnapshot，不实现绩效评价、归因、Champion/Challenger
   实验或策略晋升。

### 明确未实施 PR-007 及以后

```text
绩效评价与归因
Alpha Score / 风险调整收益评价
Champion/Challenger 自动实验和晋升
策略自动淘汰
全市场自动推荐
真实券商连接和实盘订单
HK/US/衍生品自动撮合
分钟级或逐笔仿真
Dify / Qlib / FinRL / RD-Agent
```

没有修改 QuantTradeProposal、NormalTradePlan、TopReviewDecision、
ConsensusDecision、RiskDecision 或 EvidenceSnapshot 的历史内容；DecisionPipeline
只追加可靠 Outbox 事件。

### 数据变化和完整回退

PR-006 真实数据库只新增 create-only 索引，未 seed 政策、未创建账户、未产生 Intent、
Order、Fill、Reservation、Settlement、Position、Lot、Ledger 或 AccountSnapshot。
人工模拟数据未变化。

完成检查点后的首选回退方法：

1. 记录当前 `git status --short` 和 `git tag --list "alphaguard-pr00*"`；
2. 用 `git revert <pr006-commit>` 创建可审计反向提交，不使用 `reset --hard` 或
   `checkout --` 覆盖用户工作；
3. 移除新增 router 和调度后复跑 PR-001～PR-005 的 233 项及三项启动保护；
4. 49 个空索引/空集合可安全保留，不影响 PR-001～PR-005；
5. 如必须物理移除，先对 16 个精确集合执行并验证 `mongodump`，确认均无业务文档，
   再逐个删除精确 PR-006 索引/集合，禁止通配 drop；
6. 若未来已执行 seed 或发生自动模拟交易，禁止直接 drop：先停调度、备份 policies/
   accounts/intents/orders/fills/lots/ledger/settlements/outbox/events，完成账本与账户
   reconciliation，再只做逻辑停用；
7. 永远不删除或重置人工 `paper_*` 集合，不回退 PR-001 安全默认值；
8. 回退后再次验证 FastAPI HTTP 200、不安全 FastAPI/两 Worker 阻断、Mongo/Redis
   healthy、旧 `/paper/*` 冒烟和自动集合无残留副作用。

### 当前 Git 状态与阶段闸门

PR-001～PR-005 均为独立提交和标签。PR-006 的代码、测试和文档将形成单独提交并标记：

```text
alphaguard-pr006-automatic-paper
```

检查点完成后工作区应为 clean，`git diff alphaguard-pr005-consensus-risk..HEAD --check`
应通过。PR-006 到此停止；PR-007 没有开始，必须由人工另行授权。

---

## PR-007：Evaluation & Attribution

### 1. 完成结论

PR-007 已完成。系统在 PR-001～PR-006 的不可变决策、风控和自动模拟交易事实之上，
增加了一条只读生产事实、只写 `ag_eval_*` 集合的评价链：

```text
QuantTradeProposal / NormalTradePlan / TopReviewDecision
ConsensusDecision / RiskDecision / BenchmarkExecutionDecision
ExecutionOutbox / OrderIntent / PaperOrder / PaperFill / PositionExit
        ↓
EvaluationSubject
        ↓
1D / 5D / 10D / 20D HorizonLabel
        ↓
CounterfactualEvaluation / AccountPerformanceMetric
PairedDecisionComparison / ModuleEvaluationMetric
        ↓
AttributionRecord + append-only AttributionOverride
```

评价模块允许在期限成熟后读取事后行情，但其任何对象都不能成为候选、证据、因子、
市场状态、策略、模型决策、Consensus、HardRisk 或自动模拟执行的输入。评价失败不会
阻断或回滚合法交易事实，也不会修改账户、现金、持仓、订单、成交和结算。

### 2. 实际修改和新增文件

核心 Schema 与集合：

```text
tradingagents/alphaguard/evaluation_schemas.py
app/schemas/alphaguard/evaluation.py
app/models/alphaguard/evaluation_collections.py
tradingagents/alphaguard/__init__.py
app/schemas/alphaguard/__init__.py
```

评价服务：

```text
app/services/alphaguard/evaluation_policy_registry.py
app/services/alphaguard/evaluation_repository.py
app/services/alphaguard/evaluation_audit_service.py
app/services/alphaguard/trading_horizon_resolver.py
app/services/alphaguard/adjusted_price_resolver.py
app/services/alphaguard/horizon_label_service.py
app/services/alphaguard/evaluation_subject_builder.py
app/services/alphaguard/counterfactual_evaluation_engine.py
app/services/alphaguard/account_metric_service.py
app/services/alphaguard/paired_comparison_service.py
app/services/alphaguard/module_metric_service.py
app/services/alphaguard/attribution_rule_registry.py
app/services/alphaguard/attribution_engine.py
app/services/alphaguard/evaluation_pipeline.py
app/services/alphaguard/evaluation_jobs.py
```

配置、索引、API、调度和候选保护：

```text
config/alphaguard/evaluation/evaluation_policy_v1.yaml
config/alphaguard/evaluation/attribution_rules_v1.yaml
scripts/init_alphaguard_evaluation_indexes.py
tradingagents/alphaguard/mongo_indexes.py
app/routers/alphaguard_evaluations.py
app/main.py
app/services/alphaguard/candidate_pool_service.py
```

前端：

```text
frontend/src/api/alphaguardEvaluations.ts
frontend/src/components/paper/AlphaGuardEvaluationCenter.vue
frontend/src/views/PaperTrading/index.vue
```

测试：

```text
tests/unit/alphaguard/pr007_helpers.py
tests/unit/alphaguard/test_evaluation_schemas_horizons_pr007.py
tests/unit/alphaguard/test_evaluation_subjects_candidate_pr007.py
tests/unit/alphaguard/test_metrics_pairing_attribution_pr007.py
tests/unit/alphaguard/test_counterfactual_pipeline_security_pr007.py
```

### 3. EvaluationSubject

`EvaluationSubject` 是 create-only 的评价样本，保存：

- `subject_id / subject_type / source_object_id / source_object_version`；
- `user_id / analysis_id / candidate_id / snapshot_id / quant_proposal_id`；
- `symbol / market / decision_trade_date / decision_stage / decision_status`；
- 原始动作、仓位、入场区间、有效期和可追溯证据；
- 是否被选择执行、是否存在实际成交、完整 lineage IDs；
- `discovered_at / evaluation_version / immutable_hash / schema_version`。

发现器从既有对象原样发现量化提案、普通计划、顶尖终审、Consensus、HardRisk、
BenchmarkSafety、Outbox、Intent、Order、Fill 和平仓事实，不调用模型，也不重新解释
自然语言。实际成交通过 lineage 反向标记上游样本的 `actual_execution_exists`。

为避免错误语义复用，实际实现增加两个安全扩展：

- `BENCHMARK_DECISION`：只表示 BenchmarkExecutionSafetyGate，绝不伪装 HardRisk；
- `EXECUTION_OUTBOX`：表示待处理、失败或死信的执行来源，绝不伪装订单或成交。

### 4. HorizonLabel

每个 subject 按 anchor 生成不可变标签：

- `DECISION_CLOSE`：所有决策样本的标准比较锚点；
- `PLANNED_ENTRY`：BUY 计划入场区间上界的路径标签，不声明真实成交；
- `ACTUAL_FILL`：真实 Fill 的执行锚点；
- `COUNTERFACTUAL_FILL`：反事实执行结果内部使用。

标签明确保存状态、价格口径、数据版本、输入哈希、数据引用、收益、相对收益、
MFE/MAE 和触发信息。未成熟为 `PENDING`，行情不足为 `INSUFFICIENT_DATA`，来源不合法
为 `INVALID_SOURCE`；这些状态不会被填成零收益或正常样本。

### 5. 交易日期限定义

版本化政策 `evaluation-policy-v1 / 1.0.0` 定义：

```text
1D  = 决策日后的第 1 个开放交易日
5D  = 决策日后的第 5 个开放交易日
10D = 决策日后的第 10 个开放交易日
20D = 决策日后的第 20 个开放交易日
```

期限只使用 `trading_calendar` 中显式 `market=CN, is_open=true` 的 session。自然日 `+N`
不是后备方案；周末、节假日和缺失交易日历不会被猜测。历史回放发现器还增加
`decision_trade_date <= as_of_trade_date` 的硬过滤，禁止未来决策对象进入过去评价批次。

### 6. 复权价格口径

标签要求行情记录显式包含：

```text
adjustment_mode = QFQ
data_version
trade_date
open / high / low / close
```

解析器不会从未复权 OHLC 推算复权价格，不会调用实时接口补数据，也不会把缺失版本
解释为某个默认版本。同一交易日重复记录内容不一致会报完整性冲突。

`ACTUAL_FILL` 的收益标签使用同一 QFQ 序列的复权 anchor close 与未来复权 close；
PR-006 的原始成交价单独保存在 `execution_anchor_price`。继续持有反事实则只用原始
成交价和到期日不可变 `ExecutionMarketSnapshot` 的原始 close，避免原始成交价和
复权未来价混算。

### 7. MFE / MAE 口径

在 anchor 之后、期限结束日之前（含结束日）的复权日线区间内：

```text
MFE = max(adjusted_high) / adjusted_anchor_price - 1
MAE = min(adjusted_low)  / adjusted_anchor_price - 1
```

`action_aligned_return` 对 BUY 保持收益方向，对 SELL/REDUCE 取反；原始市场路径的
`raw_forward_return` 始终保留。空路径不会生成伪造的 0 MFE/MAE。

### 8. 相对指数和行业收益

指数基准第一版固定为政策中的沪深 300 `000300`，必须与标的使用相同：

- anchor 日与期限结束日；
- QFQ 口径；
- 显式 `data_version`。

`relative_benchmark_return = raw_forward_return - benchmark_return`。

现有真实库没有可靠的“快照时行业映射 + 同版本行业指数复权序列”，因此行业字段保留，
但返回 `industry_unavailable_reason`，不会使用当前最新行业分类回填，也不会伪造中性
行业收益。这是 fail-closed 的数据能力限制。

### 9. CounterfactualEvaluation

反事实引擎是纯 Python，仅产生评价对象：

- `SIGNAL_ONLY`：未交易信号的市场表现，不宣称可执行；
- `EXECUTABLE_SHADOW`：以固定标准资金、同一版本 MatchingEngine/FeeEngine、历史不可变
  ExecutionMarketSnapshot 做影子撮合，支持多日和部分成交；
- `CONTINUE_HOLDING`：对实际退出样本估算继续持有至主期限的事后结果。

它只导入 PR-006 的纯函数 MatchingEngine 和 FeeEngine，不导入 OrderService、
ReservationService、SettlementService 或 Worker，不创建正式 Intent/Order/Fill，
不修改账户。缺日历、执行快照、交易状态、费用政策或原始 Fill 时返回明确不足状态。

### 10. 实际执行评价

执行样本覆盖 Outbox、Intent、Order、Fill 和 PositionExit，可观察：

- 从决策到执行各阶段状态；
- 提交、拒绝、过期、部分成交和完整成交比例；
- 是否真正执行以及规则版本；
- 计划与执行的配对差异；
- Fill 费用和继续持有反事实；
- 账户日快照的费用拖累、换手、敞口和估值完整性。

由于当前只有日线盘后模拟，不声称获得逐笔滑点、盘中路径或真实可成交队列位置。

### 11. 四账户指标

`AccountPerformanceMetric` 对四种自动模拟账户使用完全相同的 Decimal 口径：

```text
PAPER_QUANT
PAPER_NORMAL
PAPER_TOP_CONFIRMED
PAPER_CHALLENGER
```

保存期初/期末权益、总收益、最大回撤、已实现/未实现盈亏、费用、费用拖累、平均敞口、
换手、Fill/订单数量、胜率、Profit Factor 和估值完整/不完整天数。

指标只读取指定期间内的 DailyAccountSnapshot、Fill、Order 和已提交 Settlement。
Order/Settlement 缺少可靠业务日期时不进入该期间，避免待成交对象导致异常或跨期污染。
少于两期快照为 `INSUFFICIENT_HISTORY`；任一日估值不完整为
`INCOMPLETE_VALUATION`，不会把缺价按零估值后宣称完整。

### 12. 配对比较方法

配对只在同一真实机会身份下成立，至少要求：

- `snapshot_id / symbol / market / decision_trade_date` 完全一致；
- 1D、5D、10D、20D 四个期限均成熟；
- 两边复权模式、价格版本、基准版本和期限结束日一致；
- 执行比较还必须具备规则版本。

实现比较：

```text
QUANT_VS_NORMAL
NORMAL_VS_TOP
TOP_VS_HARD_RISK
ORIGINAL_VS_RISK_REDUCED
PLAN_VS_EXECUTION
```

不满足可比条件时保存 `NOT_COMPARABLE` 和具体原因，不把非配对样本强行计算为模型价值。

### 13. Quant、Normal、Top、Consensus 和 HardRisk 评价

阶段指标统一保存覆盖率、1/5/10/20D 原始和方向对齐平均收益、MFE、MAE、执行选择率、
实际成交率、拒绝率、调整率、模型错误率、避免亏损数和错失机会数。

- Quant：评价 TRIGGERED/WATCH/REJECTED 等原始量化结果；
- Normal：与 Quant 同机会配对，测量普通模型增量；
- Top：区分 CONFIRM、RISK_ADJUST、MATERIAL_REVISION、REJECT、SUSPEND 和模型错误；
- Consensus：区分 PASS、REVISE、REJECT、INVALID 的拦截结果；
- HardRisk：区分 PASS、REDUCE、REJECT、SUSPEND，并保留仓位变化。

所有“价值”都是同机会、同期限的事后诊断，不是因果结论。

### 14. BenchmarkSafety 独立评价

BenchmarkExecutionSafetyGate 输出使用独立 `BENCHMARK_DECISION` subject 和
`decision_stage=BENCHMARK_SAFETY`。Schema 双向强制这种映射，防止基准机械安全门被
保存或展示成通过了 Consensus/HardRisk。

### 15. 因子、Regime 和 Strategy 评价

因子指标按 `factor_id:factor_version` 聚合真实 `normalized_score / raw_value /
direction`，保存：

- 数据覆盖率和缺失率；
- 1/5/10/20D 平均收益；
- 方向命中率；
- 10D 分数分桶收益；
- 平均 MFE/MAE；
- `future_normalization_used=false`。

样本不足时 Rank IC 明确为未计算，不做伪统计。Regime 评价保存对应样本的基准收益和
MFE/MAE，但因缺少可靠市场宽度数据，标记 `market_breadth_status=UNAVAILABLE`，
不宣称“市场状态判定正确”。Strategy 按 strategy/version/status 聚合相同标签合同。

### 16. AttributionRuleRegistry 与失败归因

版本化规则 `attribution-rules-v1 / 1.0.0`，主归因期限为 10D，覆盖：

```text
DATA_QUALITY
CANDIDATE_SELECTION
FACTOR_FAILURE
REGIME_MISCLASSIFICATION
STRATEGY_ENTRY
NORMAL_MODEL
TOP_MODEL
CONSENSUS
HARD_RISK
EXECUTION
MARKET_SHOCK
UNKNOWN
```

规则阈值来自 YAML，不散落在代码中。归因区分盈利、亏损、避免亏损、错失机会、
中性和数据不足；输出规则 ID、主/次类别、证据、置信度和机器说明，并始终显示
“规则化诊断，不代表严格因果”。期限未成熟时归因为 `PENDING_HORIZON`，数据不足
优先归 `DATA_QUALITY`，不会硬猜模块责任。

### 17. 人工覆盖机制

人工只能追加 `AttributionOverride`：

- 保存原 Attribution ID、覆盖类别、原因、用户和时间；
- 不 update/delete 原机器归因；
- 同一内容幂等复用，同一身份不同内容报冲突；
- API 返回机器归因及完整 overrides 历史。

人工覆盖不进入自动学习、决策、风控或执行。

### 18. MongoDB 集合和索引

新增 13 个只用于评价的集合：

```text
ag_eval_subjects
ag_eval_horizon_labels
ag_eval_counterfactuals
ag_eval_account_metrics
ag_eval_paired_comparisons
ag_eval_attributions
ag_eval_attribution_overrides
ag_eval_runs
ag_eval_events
ag_eval_factor_metrics
ag_eval_regime_metrics
ag_eval_strategy_metrics
ag_eval_execution_metrics
```

共 42 个 create-only 索引，覆盖不可变身份、版本、用户/日期、stage/status、成熟期、
账户、比较、归因、任务和事件查询。索引脚本可重复运行，第二次结果为
`created=0, unchanged=42`；冲突明确失败，不删除已有索引。

实际数据库只创建了这 42 个索引及空集合，13 个集合文档数均为 0；没有 seed 评价
结果，也没有修改 PR-001～PR-006 或人工模拟集合。

### 19. API

认证后提供：

```text
GET  /api/alphaguard/evaluations/overview
GET  /api/alphaguard/evaluations/subjects
GET  /api/alphaguard/evaluations/subjects/{subject_id}
GET  /api/alphaguard/evaluations/decisions/{source_object_id}
GET  /api/alphaguard/evaluations/accounts
GET  /api/alphaguard/evaluations/accounts/compare
GET  /api/alphaguard/evaluations/model-value
GET  /api/alphaguard/evaluations/factors
GET  /api/alphaguard/evaluations/regimes
GET  /api/alphaguard/evaluations/strategies
GET  /api/alphaguard/evaluations/execution
GET  /api/alphaguard/evaluations/counterfactuals
GET  /api/alphaguard/attributions
POST /api/alphaguard/evaluations/run
POST /api/alphaguard/attributions/{attribution_id}/overrides
```

所有查询按当前用户授权；全用户回放仅管理员可登记。`run` 只登记幂等后台任务，不在
请求线程执行大批计算。客户端不能上传收益标签、价格、Counterfactual、Metric 或机器
归因，也没有评价对象 update/delete API。

API 冒烟：overview=200、run=200、非管理员 all-users=403，重复登记只产生一个 run。

### 20. 前端页面

PaperTrading 增加“评价与归因”只读标签，包含：

- 全样本概览；
- 四账户对比（包括 Challenger `NOT_ACTIVE` 占位）；
- 模型价值和阶段指标；
- 反事实与未成交诊断；
- 机器归因和人工覆盖历史。

页面显示样本量、数据不足和“非严格因果”提示，不提供自动交易、价格修改、风险修改、
归因机器事实修改、策略晋升或 Challenger 启动控件。

### 21. Worker 和调度

在既有 FastAPI APScheduler 中：

```text
16:20  PR-006 DailyAccountSnapshot
16:35  PR-007 schedule_daily_evaluation
每15分钟 run_pending_evaluations
17:00  PR-006 account reconciliation
```

评价 Worker 从 `ag_eval_runs` 读取 PENDING/FAILED 任务；统一流水线严格按 subject、
label、counterfactual、account metric、paired comparison、module metric、attribution
执行。蓝图中的各任务名保留为统一入口别名，实际使用一个有序、幂等流水线，减少中间
阶段错序。评价异常只记录 `ag_eval_runs/ag_eval_events`，不会中断 PR-006 调度。

### 22. 幂等和完整性

- run key = as-of trade date + user scope + evaluation version；
- 相同 terminal run 直接复用，不重复计算；
- immutable repository 对同身份同内容复用、同身份不同内容报完整性冲突；
- Subject、Label、Counterfactual、Comparison、Attribution 和 Metric 均有稳定 ID/hash；
- 失败重试增加 attempt，并保留 `error_history`；
- 单 subject 评价不发现无关样本，也不错误计算全账户/全样本统计；
- 候选物理删除前检查未完成评价引用；存在引用时 fail-closed；
- 重复 Worker 冒烟结果：第一次 completed=1，第二次 completed=0，attempt 保持 1。

### 23. 无未来数据回流和无账户副作用

静态依赖和运行测试确认：

- EvaluationPipeline 写集合白名单只有 13 个 `ag_eval_*`；
- 评价服务不导入 OrderService、ReservationService、SettlementService 或 Broker；
- 不更新 EvidenceSnapshot、FactorResult、QuantProposal、模型计划、Review、Consensus、
  RiskDecision、OrderIntent、PaperOrder、PaperFill、账户、现金、持仓或 PositionLot；
- Factor/Regime/Strategy/Context/Decision/HardRisk 不导入 evaluation 模块；
- 未来行情只在期限成熟后的评价模块读取；
- 评价结果不会被注入 Prompt、ContextBuilder 或任何执行政策；
- `live_trading_enabled=false` 和两套 Worker fail-closed 保护保持不变。

### 24. 测试和验证结果

PR-007 专项：

```text
49 passed
```

覆盖 Schema、期限成熟、交易日历、QFQ/版本、篡改与冲突、MFE/MAE、基准收益、样本
发现、Benchmark 独立语义、历史回放截止日、候选删除保护、反事实影子多日/部分成交、
继续持有原始价格口径、账户指标、严格配对、模块统计、规则归因、人工覆盖、API 权限、
任务幂等、单样本评价、无未来数据回流和无生产副作用。

PR-001～PR-007 精确回归集：

```text
346 passed
```

其中 PR-001～PR-006 原基线 297 项继续通过；PR-007 新增 49 项。

其他验证：

```text
tests/ collect-only: 1023 collected, 15 known errors
frontend type-check: 34 errors, all TS2345
Python compile (app/tradingagents/tests/PR-007 script): passed
scripts full compile: only known 补充行业信息_akshare.py:81 syntax error
git diff --check: passed
FastAPI safe start /api/health: HTTP 200
FastAPI live=true: exit 3, startup rejected
app/worker.py live=true: exit 1, startup rejected
app/worker/analysis_worker.py live=true: exit 1, startup rejected
MongoDB ping: healthy
Redis ping: healthy
evaluation index repeated run: created=0, unchanged=42
API smoke: 200 / 200 / admin guard 403
evaluation worker idempotency smoke: reused terminal result
```

15 个收集错误与 PR-006 的类别完全一致；前端仍只有既有 34 个 `DefaultRow TS2345`。
没有跳过 PR-007 新测试，也没有为了数字修复无关上游技术债。

根目录 collect-only 会收集并执行旧 `scripts/test_*.py`，触发外部 AkShare/网络和交互式
输入，已安全中断；不把该次中断命令宣称为完整收集。上述 `tests/` 范围的 1023/15 是
实际完成的全测试目录收集结果。

### 25. 兼容性、设计差异和已知限制

1. 现有公共行情没有已验证的持久化 QFQ OHLC 与版本合同；真实标签会 fail-closed 为
   `INSUFFICIENT_DATA/INVALID_SOURCE`，不会用未复权数据冒充。
2. 现有真实交易日历和真实市场评价样本为空，当前 13 个评价集合也为 0 文档；本阶段
   验证使用固定离线数据，没有伪造生产评价结果。
3. 行业映射/行业指数缺少快照时版本，行业相对收益明确为空；后续只能通过版本化数据
   准备补齐，不能读取当前行业覆盖历史。
4. `RuleCondition` 仍是结构化容器中的自然语言条件，没有可安全机器比较的价格阈值，
   因此 stop/exit touch 字段保留但不自动猜测触发。
5. 日线模拟只支持每订单每日一个 Fill；执行评价不能重建真实逐笔成交或队列优先级。
6. 小样本统计明确 `INSUFFICIENT_SAMPLE`；Rank IC、市场宽度和严格因果归因不伪造。
7. 账户指标依赖至少两期完整 DailyAccountSnapshot；Challenger 在 PR-008 前正常显示
   `NOT_ACTIVE/INSUFFICIENT_HISTORY`。
8. 调度使用一个统一评价 run 承载蓝图中的多个作业名。其安全影响是阶段顺序更清晰，
   失败隔离不变；若未来数据规模需要分片，可在后续阶段拆成相同幂等合同的独立 Worker。
9. 安全扩展的 `BENCHMARK_DECISION` 和 `EXECUTION_OUTBOX` 比把它们伪装成 HardRisk/
   Order 更保守；不改变任何 PR-006 Schema 或历史对象。
10. FastAPI 关闭时仍可观察到既有股票同步后台线程延迟退出；HTTP 启动和安全保护均已
    验证，此存量问题未在 PR-007 扩大处理。

### 26. 明确未实施 PR-008 及以后

```text
Champion/Challenger 自动实验
策略自动晋升、降级或淘汰
模型自动选择或权重调整
将评价标签反馈到 Prompt、Factor、Regime、Strategy、Consensus 或 HardRisk
自动改变执行/费用/风险政策
全市场自动推荐
真实券商、实盘订单或 live 开关
Dify / Qlib / FinRL / RD-Agent
```

PAPER_CHALLENGER 只读取并显示 PR-006 创建的空账户状态，不创建 Intent 或交易。

### 27. 数据变化和完整回退

本阶段真实数据库变化仅为 13 个空评价集合上的 42 个 create-only 索引；评价文档为 0，
PR-001～PR-006、人工 paper 和自动 `ag_paper_*` 数据均未修改。

完成检查点后的回退：

1. 停用 `alphaguard_evaluation_schedule` 和 `alphaguard_evaluation_worker`；
2. 记录 `git status --short`、目标 commit 和 tag；
3. 使用 `git revert <pr007-commit>` 创建可审计反向提交，不使用 `reset --hard`；
4. 移除评价 router/前端入口/调度后，复跑 PR-001～PR-006 的 297 项精确回归；
5. 42 个空索引和空集合可保留，不影响交易链；
6. 如必须物理移除，先确认 13 个精确集合文档数均为 0 并做 `mongodump`，再逐个 drop
   精确评价集合；禁止通配删除；
7. 若未来已产生评价文档，先完整备份全部 `ag_eval_*`，评价数据仍可离线保留，因为它
   不参与生产交易；
8. 回退后验证 FastAPI HTTP 200、三项 live=true 阻断、Mongo/Redis healthy、
   PR-006 自动模拟链和人工 `/paper/*` 均无变化；
9. 永远不回退 PR-001 的 `SIM_AUTONOMOUS / live_trading_enabled=false` 安全不变量。

### 28. 当前 Git 状态与阶段闸门

PR-001～PR-006 均保留独立提交和标签。PR-007 的代码、测试和本文档形成单独提交：

```text
feat(alphaguard): complete PR-007 evaluation and attribution
```

并标记：

```text
alphaguard-pr007-evaluation-attribution
```

检查点完成后工作区为 clean，标签到 HEAD 的 diff check 通过。PR-007 到此停止；
PR-008 没有开始，必须由人工另行授权。

---

## PR-008：Experiment Lab & Champion/Challenger

### 1. 完成结论与安全边界

PR-008 已完成源码、测试、运行基线和独立检查点准备。本阶段建立的是受控、可审计且
可回退的实验闭环：

```text
不可变实验定义
→ 固定 DatasetManifest
→ 时间序列样本外/历史重放
→ 泄漏审计与稳健性测试
→ 同快照 Shadow
→ 独占 PAPER_CHALLENGER Assignment
→ 配对 ChampionComparisonReport
→ 顶尖模型实验风险审查
→ 管理员 PromotionRequest + PromotionApproval
→ 可恢复 PromotionSaga
→ 按交易日生效的 ChampionResolver
```

没有自动晋升或自动回退，没有修改 `live_trading_enabled=false`，没有真实交易，也没有
开始 PR-009。真实评价样本仍为 0，因此生产比较只能得到 `INSUFFICIENT_DATA`，且无法
创建 PromotionRequest；所有测试 fixture 只存在于 FakeDB，不写真实业务集合。

### 2. 实际修改文件

新增 Schema、集合和配置：

- `tradingagents/alphaguard/experiment_schemas.py`
- `app/schemas/alphaguard/experiment.py`
- `app/models/alphaguard/experiment_collections.py`
- `config/alphaguard/experiments/promotion_policy_v1.yaml`
- `config/alphaguard/experiments/replay_policy_v1.yaml`
- `config/alphaguard/experiments/robustness_suite_v1.yaml`

新增实验服务：

- `experiment_config.py`
- `experiment_repository.py`
- `experiment_audit_service.py`
- `experiment_state_machine.py`
- `experiment_component_adapters.py`
- `experiment_registry.py`
- `experiment_dataset_service.py`
- `historical_replay_engine.py`
- `walk_forward_validation.py`
- `leakage_audit_service.py`
- `robustness_test_service.py`
- `shadow_experiment_service.py`
- `challenger_assignment_service.py`
- `challenger_order_intent_service.py`
- `champion_comparison_service.py`
- `experiment_risk_review_service.py`
- `promotion_policy_service.py`
- `champion_resolver.py`
- `champion_promotion_service.py`
- `champion_rollback_service.py`
- `experiment_reconciliation.py`
- `experiment_task_service.py`

新增 Router、Worker、脚本、前端和测试：

- `app/routers/alphaguard_experiments.py`
- `app/worker/alphaguard/__init__.py`
- `app/worker/alphaguard/experiment_tasks.py`
- `scripts/init_alphaguard_experiment_indexes.py`
- `scripts/import_current_champions.py`
- `scripts/verify_champion_assignments.py`
- `frontend/src/api/alphaguardExperiments.ts`
- `frontend/src/components/paper/AlphaGuardExperimentLab.vue`
- `tests/unit/alphaguard/pr008_helpers.py`
- 四个 `test_experiment_*_pr008.py`

最小修改现有接线：

- `app/main.py`
- `app/services/alphaguard/evidence_snapshot_service.py`
- `app/services/alphaguard/factor_engine.py`
- `app/services/alphaguard/factor_aggregation.py`
- `app/services/alphaguard/market_regime_engine.py`
- `app/services/alphaguard/quant_research_pipeline.py`
- `app/services/alphaguard/paper_order_service.py`
- `app/services/alphaguard/paper_execution_service.py`
- `app/services/alphaguard/paper_task_service.py`
- `app/routers/alphaguard_paper.py`
- `tradingagents/alphaguard/evidence_schemas.py`
- `tradingagents/alphaguard/paper_schemas.py`
- `tradingagents/alphaguard/mongo_indexes.py`
- 两个 AlphaGuard Schema `__init__.py`
- `frontend/src/views/PaperTrading/index.vue`

### 3. ExperimentRegistry 和组件支持范围

`ExperimentRegistry` 只提供 create/get/list/validate/transition/suspend/retire 语义；没有
任意字段 update。核心定义、基线、挑战版本、假设和主变量受 frozen Schema 与
`immutable_definition_hash` 双重保护，内容变化必须创建新 Experiment。

完整确定性执行适配器支持：

```text
FACTOR_WEIGHT
FACTOR_SET
REGIME_CONFIG
STRATEGY_CONFIG
```

以下类型可登记，但当前工程没有足够安全的版本隔离接口，因此
`execution_supported=false`、`promotion_eligible=false`，原因固定为
`UNSUPPORTED_COMPONENT_ADAPTER`：

```text
FACTOR_FORMULA
NORMAL_PROMPT
TOP_PROMPT
MODEL_CONFIG
AGENT_CONFIG
DEBATE_CONFIG
HARD_RISK_CONFIG
MATCHING_CONFIG
```

没有建立第二套生产配置体系。PR-004 的 Factor/Regime/Strategy 定义仍是基础事实；
PR-008 仅创建不可变组件版本记录和唯一 Champion 指针。

### 4. 单变量隔离

标准实验必须且只能有一个 `is_primary=true` 的 `ExperimentVariableChange`。
Registry 验证：

1. baseline/challenger 都存在且属于同一 component slot；
2. payload hash 不同，不能用同内容伪版本；
3. `primary_variable_path` 确实变化；
4. 除主变量外的规范化 payload 完全一致；
5. 组件适配器支持相应执行；
6. 版本 hash 有效；
7. 实验不会修改生产配置。

出现额外变化时自动定性为 `MULTIVARIATE`，允许研究但永远不可走标准晋升。

### 5. 版本状态机

实现 DRAFT、EXPERIMENT、BACKTESTED、SHADOW、CHALLENGER、CHAMPION、DEGRADED、
SUSPENDED、RETIRED 的显式迁移表。禁止 DRAFT/BACKTESTED/SHADOW 直接进入 CHAMPION；
只有携带有效人工批准上下文的 CHALLENGER 才能进入 CHAMPION；RETIRED 不可恢复。
状态变更使用服务端规则并记录 `EXPERIMENT_STATE_CHANGED`，客户端不能提交任意状态。

### 6. DatasetManifest

`ExperimentDatasetManifest` 是 create-only：

- Snapshot ID 与 symbols 排序去重；
- 固定起止日期、cutoff、筛选规则和源集合 hash；
- 同内容产生稳定 SHA-256；
- 缺失、未来、market 不一致或 immutable hash 被篡改的 Snapshot 会阻断；
- Manifest 创建后不会随着新数据自动追加；新样本必须新建 Manifest。

### 7. 时间序列分割

支持 `ANCHORED_HOLDOUT`、`ROLLING_WALK_FORWARD`、`EXPANDING_WALK_FORWARD`。
不使用随机打乱。Train/Validation/Test 顺序严格，Test 只能更晚；embargo 至少覆盖
当前最大评价期限 20 个交易观察点，并清除跨边界收益期限样本。样本不足返回
`INSUFFICIENT_DATA`，不缩短测试期，也不只挑选最佳 fold。

### 8. 历史重放和样本外验证

`HistoricalReplayEngine` 按 Manifest 中 Snapshot 的 `(trade_date, snapshot_id)` 顺序
执行。Champion 与 Challenger 使用同一 Snapshot、代码 commit、tree hash、配置 hash
和除唯一变量外相同的版本。决策输出先产生，之后才读取已成熟 PR-007 HorizonLabel，
避免标签进入决策输入。

结果只写 `ag_exp_*`，不写 Candidate、生产 FactorResult、QuantProposal、模型决策、
Outbox、Order、Fill 或账户。相同输入复用同一 run/result，确定性组件的 result hash
稳定。OUT_OF_SAMPLE 每个 fold 单独保存并汇总，不在 Test 期重新调参。

### 9. 泄漏审计

`LeakageAuditReport` 独立检查未来价格、未来财务、未来新闻、评价标签、分割重叠和
当前配置泄漏。任一布尔项为 true 即 `FAIL`，PromotionPolicy gate 不允许人工绕过。
EvidenceSnapshot 的 cutoff 与 raw refs 仍是数据边界，重放不会读取“当前最新”配置或
Manifest 之外的新 Snapshot。

### 10. 稳健性测试

影子稳健性套件版本为 `robustness-suite-v1@1.0.0`，包含：

```text
BASELINE
FEE_1_5X / FEE_2X
SLIPPAGE_1_5X / SLIPPAGE_2X
ENTRY_DELAY_1D
LIQUIDITY_REDUCTION
MISSING_NONCORE_DATA
WITHOUT_BEST_TRADE
WITHOUT_TOP_5_TRADES
REGIME_SEGMENTED
```

压力参数只作用于实验计算，不修改正式 FeeEngine/MatchingEngine，也不写正式账户。
失败和不完整场景会保留；五类 Regime 缺失时报告明确 `INCOMPLETE`。

### 11. Shadow

新 EvidenceSnapshot 保存成功后只登记幂等、低优先级 `SHADOW_SNAPSHOT` 任务。Shadow
读取生产 Champion 已完成使用的同一 Snapshot，固定除主变量外的全部版本，产出成对
实验输出和差异，不修改 Candidate、生产研究/决策、Outbox、订单、成交或账户。
Snapshot 保存主流程不会因 Shadow 登记失败而失败；异常写实验审计并留给 reconciliation。

达到 PromotionPolicy 的 20 个观察交易日前不能进入 CHALLENGER。

### 12. PAPER_CHALLENGER 与独占规则

`ChallengerAssignmentService` 要求：

- 实验已到 SHADOW 且满足观察期；
- 同一 `user_id + market` 不存在其他 ACTIVE/CLOSING Assignment；
- 目标账户必须是 `PAPER_CHALLENGER`；
- 账户无未完成订单、预留或非零持仓；
- 创建新的 baseline account snapshot，绝不自动清仓或重置余额；
- 停止时如仍有订单/持仓只进入 CLOSING，待自然归零后 COMPLETED。

Challenger OrderIntent 增加 `experiment_id/assignment_id` lineage，只能从实验专用输出中
已经完整通过 NormalPlan、TopReview、Consensus、HardRisk 的链创建，且固定
`execution_environment=PAPER`、`live_execution_allowed=false`。PAPER_CHALLENGER 的
订单、成交和取消不会更新主 Candidate；PAPER_TOP_CONFIRMED 不受影响。

实际适配差异：确定性组件目前能完整运行重放和 Shadow，但现有生产 DecisionPipeline
没有“实验专用 Mongo 命名空间”的双模型执行接口。为避免 Challenger 污染生产决策集合，
本阶段没有复用生产 Pipeline 或正式 Outbox 伪造该输出；内部 Intent 服务对缺少完整
隔离链的输出 fail-closed。因此已实现 Assignment、lineage、账户隔离和受控执行入口，
真实 PAPER_CHALLENGER 下单要等安全的隔离双模型适配器提供完整链后才会发生。安全影响
是少执行而非越权执行；不得用测试对象填补该缺口。

### 13. Champion/Challenger 公平比较

`ChampionComparisonService` 综合历史重放、样本外、稳健性、Shadow、
PAPER_CHALLENGER 和 PR-007 配对评价。比较 gate 包括样本量、配对覆盖、泄漏、稳健性、
Shadow/Challenger 观察日、完整性错误、Regime 覆盖、最大回撤和极端交易依赖。

报告同时保存 Champion、Challenger、同机会 paired 指标；改善、恶化、不可比和数据不足
均保留。总收益更高不会自动变为 READY。

### 14. PromotionPolicy

锁定 `promotion-policy-v1@1.0.0`：

- 历史样本 30、样本外 20、配对 20、配对覆盖 0.80；
- Shadow 和 Challenger 各 20 个交易日；
- 泄漏、稳健性、Shadow、PAPER_CHALLENGER、顶尖模型审查和人工批准均必需；
- integrity error 必须为 0；
- 未隐藏默认盈利门槛；净收益/收益回撤/费用/换手阈值为 null 时只展示、不猜阈值；
- 回撤、极端交易依赖与 Regime 覆盖门槛显式版本化。

Experiment 创建时锁定 policy version，不能看完结果再换策略。

### 15. 顶尖模型实验风险审查

结构化 Prompt 固定为 `experiment_risk_review_v1`，继续复用 PR-002
`ModelExecutionMeta`，记录 provider/model/prompt/input/output hash、耗时、request/trace
和错误。模型读取正面、负面、数据不足、泄漏、稳健性、Shadow、Challenger 与回退信息。

只有 `READY_FOR_HUMAN_REVIEW` 可以进入 PromotionRequest；MORE_VALIDATION_REQUIRED、
REJECT、SUSPEND、MODEL_FAILED、INVALID_OUTPUT 均 fail-closed。模型没有修改结果、
Policy、审批或 Champion 的权限。

### 16. 人工晋升

晋升分为 PromotionRequest 和独立 PromotionApproval。所有写 API 需要现有管理员权限。
批准必须验证：

```text
PROMOTE <experiment_id> TO <version_ref>
当前 Champion hash
Challenger hash
锁定 Policy
泄漏 PASS
有效 READY 风险审查
ComparisonReport 有效期
有效交易日
无完整性冲突
存在 previous version
```

非管理员、错误确认文本、hash 并发变化、数据不足、泄漏失败或重复冲突均不能晋升。

### 17. ChampionResolver、生效日期与生产接线

`ChampionResolver` 是新任务唯一 PR-008 版本指针解析入口，只读取已 COMMITTED 的
ChampionAssignment 和满足 `effective_from_trade_date` 的历史记录；解析失败不按最高
版本或最新记录回退。

新创建 EvidenceSnapshot 会由服务端解析并锁定完整 `champion_version_refs`。新的
QuantResearchPipeline 在 Snapshot 携带锁定版本时，按这些版本解析 FactorSet/
FactorWeight、Regime 与 Strategy；旧 Snapshot 不回填，继续走 PR-004 兼容路径。
已有 Snapshot、FactorResult、QuantProposal、模型决策、RiskDecision、Intent、Order
和 PositionLot 永远保持创建时版本。

### 18. PromotionSaga 与并发锁

MongoDB 4.4.30 当前为 standalone，`setName=None`，不支持多文档事务。因此没有伪装
事务，而是实现：

```text
PREPARED
→ LOCK_ACQUIRED
→ CURRENT_CHAMPION_VERIFIED
→ ASSIGNMENT_WRITTEN
→ RESOLVER_VERIFIED
→ COMMITTED
```

以及 ROLLBACK_REQUIRED/ROLLED_BACK/FAILED。锁有明确 slot identity 和过期时间；
assignment 使用 CAS/version，旧指针写 ChampionHistory。只有 Saga COMMITTED 后
Resolver 才会对生效日解析新版本。恢复 Worker 可验证并完成中断 Saga，或把仍匹配本
Saga 的指针回滚；重复恢复幂等，不会形成两个 Active Champion。

### 19. 回退机制

回退是管理员明确操作，要求确认文本、原因、有效交易日和 current hash。它只将未来
解析切回 `previous_version_ref`，使用相同锁、CAS、历史和 Saga 验证；不会删除失败版本、
实验、比较报告、订单或持仓，也不会回写旧对象。自动监控只能产生告警，不能自动回退。

### 20. MongoDB 集合和索引

新增 24 个专用集合：

```text
ag_exp_component_versions
ag_exp_definitions
ag_exp_variable_changes
ag_exp_dataset_manifests
ag_exp_time_splits
ag_exp_runs
ag_exp_run_results
ag_exp_leakage_audits
ag_exp_robustness_reports
ag_exp_shadow_runs
ag_exp_shadow_outputs
ag_exp_challenger_assignments
ag_exp_comparison_reports
ag_exp_risk_reviews
ag_exp_promotion_policies
ag_exp_promotion_requests
ag_exp_promotion_approvals
ag_exp_promotion_sagas
ag_exp_champion_assignments
ag_exp_champion_history
ag_exp_rollbacks
ag_exp_locks
ag_exp_task_runs
ag_exp_events
```

共 69 个 create-only 索引。脚本重复执行两次均为
`created=0 unchanged=69 failed=0`；不删除或修改 PR-001～PR-007 索引。
ACTIVE Challenger 采用部分唯一索引与 Service 锁双重约束。

### 21. 配置、导入和真实数据变化

`import_current_champions.py` 默认 dry-run，不按最高版本猜 Champion。显式执行只导入
PR-004 当前已确认的 5 个确定性 slot。真实库当前变化：

```text
ag_exp_component_versions=5
ag_exp_promotion_policies=1
ag_exp_champion_assignments=5
ag_exp_definitions=0
ag_exp_runs=0
```

初次显式导入为 `created=5 reused=5 conflicts=0 failed=0`，随后重复执行为
`created=0 reused=10 conflicts=0 failed=0`；
`verify_champion_assignments.py` 为 `assignments=5 verified=5 conflicts=0`。
5 个 bootstrap 指针使用显式生效日 `2026-07-27`；脚本执行时现在
强制要求 `--effective-date`，同 slot 的生效日或其他 assignment 内容变化按 hash 冲突
阻断，不会静默复用。真实交易日历集合当前为空，因此 bootstrap 脚本不宣称自行验证
了该日期；后续 Promotion/Rollback 服务仍必须由持久化交易日历验证生效日。
PR-008 首次真实 BSON 验证发现 Python `date` 不能直接编码，导入在写 Champion 前安全
失败；已统一通过 `experiment_document` 将 date 转成 BSON datetime，并新增真实 BSON
编码测试。失败时没有产生半成品 Champion 指针。

### 22. API

新增认证 API：

- Experiment list/create/get/validate/run/runs/comparison；
- Shadow start/pause/complete；
- Challenger activate/deactivate；
- experiment risk review；
- promotion request create/approve/reject；
- Champion list/get/rollback。

普通用户只读自身授权数据；所有写操作显式 `_require_admin`。没有 delete、客户端结果
上传、ChampionAssignment 修改、公开 OrderIntent/Order/Fill 创建或任意生产配置 API。
大型任务只登记 DB-backed worker。安全启动 API 冒烟：health 200；未认证 experiments
401；单元 API 权限测试验证管理员闸门和非管理员 403。

### 23. 前端最小实验室

PaperTrading 增加最小“AlphaGuard 实验室”：

- Champion 总览、当前/前一版本、生效日和来源实验；
- 实验列表和详情、唯一变量、Manifest、各阶段、负面结果和审计；
- 管理员晋升对话框显示 current/challenger hash、泄漏/风险/失败 gate、回退版本和明确
  确认文本；
- 管理员回退对话框显示当前/目标版本、原因和生效日期。

没有自动推荐、默认批准、结果修改、历史删除或真实交易入口。

### 24. Worker 和调度

实现 DB-backed、低优先级且幂等的：

```text
experiment_run_consumer
historical_replay_worker
walk_forward_validation_worker
leakage_audit_worker
robustness_test_worker
shadow_experiment_worker
challenger_monitor_worker
comparison_report_worker
experiment_risk_review_worker
promotion_saga_recovery_worker
experiment_reconciliation_worker
```

主调度只挂统一实验 consumer、Shadow、Challenger monitor、Saga recovery 和 reconciliation；
细分 worker 可单独部署。任务运行晚于生产撮合、结算和 PR-007 评价；失败只写
`ag_exp_task_runs/ag_exp_events`，不暂停 Champion 生产链。

### 25. 审计、幂等和完整性

Experiment、Manifest、Run、Leakage、Robustness、Shadow、Challenger、Comparison、
RiskReview、Promotion、Saga、Champion 和 Rollback 全部有结构化 `ag_exp_events`。
事件携带可用的 trace/experiment/run/manifest/split/shadow/assignment/promotion/saga/
slot/version/hash/user/market lineage。

稳定 identity/hash 覆盖 Experiment、Manifest、Split、Run、Output、Report、Task、
Promotion 和 Assignment。同身份同内容复用；同身份不同内容报
`ExperimentIntegrityConflict`。失败 task 保留错误，重跑不覆盖 terminal 结果。

### 26. 生产链隔离

静态依赖和运行测试确认：

- Replay/Shadow 只写 `ag_exp_*`；
- 不导入 BrokerAdapter，不调用真实订单网络；
- Shadow 不写 Candidate、FactorResult、QuantProposal、决策、Outbox、Order、Fill、
  Account、Position、Lot 或 Ledger；
- Challenger 只允许 `PAPER_CHALLENGER`，不写 PAPER_TOP_CONFIRMED；
- Challenger PaperOrder/Fill lineage 延续 experiment/assignment；
- Challenger 订单状态不会改变主 Candidate；
- PR-007 label 只在决策输出之后用于评价；
- `live_trading_enabled=false` 和三入口 fail-closed 保护保持不变。

### 27. 测试和验证结果

PR-008 专项（Schema、Registry、全部状态迁移、Manifest、三种时间分割、泄漏、确定性
重放、单变量隔离、稳健性、Shadow 无副作用、Challenger 隔离、比较、风险审查、人工
晋升、Saga 恢复、Resolver 生效日、回退、BSON、API、Worker、真实样本不足）：

```text
84 passed
```

PR-001～PR-007 精确回归：

```text
346 passed
```

PR-001～PR-008 合并精确集：

```text
430 passed
```

其他验证：

```text
tests/ collect-only: 1109 collected, 15 known errors
frontend type-check: 34 errors, all existing DefaultRow TS2345
modified Python compile: passed
scripts full compile: only known 补充行业信息_akshare.py:81 syntax error
git diff --check: passed
FastAPI safe start /api/health: HTTP 200
experiment API without auth: HTTP 401
FastAPI live=true: exit 3, startup rejected
app/worker.py live=true: exit 1, startup rejected
app/worker/analysis_worker.py live=true: exit 1, startup rejected
MongoDB 4.4.30 ping: healthy, standalone, transactions unavailable
Redis ping: healthy
experiment indexes repeated: created=0, unchanged=69, failed=0
Champion import initial/repeated: created=5/0, reused=5/10, conflicts=0
Champion verify: assignments=5, verified=5, conflicts=0
historical replay / worker / Shadow / Saga / rollback idempotency: passed in suite
```

15 个全量收集错误的文件和 ImportError 类别与 PR-007 一致；仅因新增测试，成功收集数
从 1023 增至 1109。前端仍只有既有 34 个 TS2345，没有新增错误类别。

### 28. 真实样本不足与已知限制

真实库验证：

```text
ag_evidence_snapshots=0
ag_quant_proposals=0
ag_consensus_decisions=0
ag_risk_decisions=0
ag_paper_fills=0
ag_eval_subjects=0
ag_eval_paired_comparisons=0
ag_exp_definitions=0
ag_exp_runs=0
```

因此生产 ComparisonReport 必须 `INSUFFICIENT_DATA`，PromotionRequest 被拒绝，不存在
虚假 Challenger 或虚假 Champion。其他存量限制保持：

1. 真实 QFQ、交易日历、历史行业映射和评价样本不足；
2. 模型/Prompt/HardRisk/Matching 组件无安全隔离适配器，仅允许登记；
3. 确定性实验使用 PR-007 成熟标签评价，不能在标签成熟前给出收益结论；
4. MongoDB standalone 必须依赖可恢复 Saga，不能宣称多文档 ACID；
5. Challenger 完整双模型实验执行入口按第 12 节 fail-closed；
6. FastAPI 关闭时既有股票同步线程可能延迟退出，未在本阶段扩大处理；
7. 前端完整产品整合、可视化和运维能力属于 PR-009。

### 29. 明确未实施 PR-009 及以后

没有实现完整前端重构、自动晋升、自动回退、自动改因子/策略/Prompt/模型/HardRisk/
Matching、自动实盘、券商连接、全市场自动推荐、Dify、Qlib、FinRL 或 RD-Agent。
实验失败不会暂停 Champion 生产链。

### 30. 完整回退

代码回退：

1. 暂停 5 个 `alphaguard_experiment_* / alphaguard_shadow_* /
   alphaguard_challenger_*` 调度任务；
2. 记录当前提交、标签、`git status --short`，并先导出数据库备份；
3. 使用 `git revert <pr008-commit>` 创建可审计反向提交，禁止 `reset --hard`；
4. 回退后复跑 PR-001～PR-007 精确集，预期 346 passed；
5. 验证 FastAPI 200、live=true 三入口阻断、Mongo/Redis 健康。

数据回退：

1. 5 个 ChampionAssignment 目前只锁定既有 PR-004 版本；可保留，旧代码不会读取；
2. 若必须移除，先 `mongodump` 全部精确 `ag_exp_*` 集合；
3. 确认 `ag_exp_definitions/ag_exp_runs` 仍为 0 后，按精确 collection 名逐个处理，
   禁止通配删除；
4. 不删除 PR-004 Factor/Strategy、PR-005 Risk、PR-006 Paper、PR-007 Evaluation 数据；
5. 不删除历史组件版本、失败实验或旧 Champion；生产已有对象不回写；
6. 永远不回退 PR-001 的 SIM_AUTONOMOUS / live=false 安全不变量。

### 31. 设计差异汇总

原设计：所有组件均可登记；实际：只有四类确定性组件可执行，其余 fail-closed。
原因是现有 Prompt/Model/Risk/Matching 缺少安全版本隔离接口。可比性影响是这些组件
当前不能产生可晋升结果；生产安全影响为不运行，不会偷用 current/latest。

原设计：PAPER_CHALLENGER 走完整隔离双模型链；实际：Assignment 和执行消费闸门已完成，
但没有把生产 DecisionPipeline 复用到实验集合。原因是复用会污染正式决策、Outbox 和
Candidate。可比性影响是当前真实 Challenger 交易样本仍为 0；生产安全影响为 fail-closed。
安全隔离执行适配器只能在后续明确授权阶段补齐，不能用 fixture 冒充。

原设计：MongoDB transaction 或 Saga；实际：standalone MongoDB 使用 Saga。可比性无
影响；生产安全通过 CAS、锁、Resolver 验证、history 和恢复任务保证。

### 32. 当前 Git 状态与阶段闸门

本节随指定独立检查点提交：

```text
feat(alphaguard): complete PR-008 experiment lab
tag: alphaguard-pr008-experiment-lab
```

提交和标签后 `git status --short` 必须为空，标签必须指向 HEAD。PR-008 到此停止；
PR-009 及以后必须重新获得人工授权。

---

## PR-009：Front-end Integration & Operations（2026-07-27）

### 1. 完成结论

PR-009 已按最小 MVP 范围完成代码、统一前端、Operations Center、分层健康检查、数据
准备度、持久化告警、受控运维任务、Compose、初始化/备份/恢复脚本和运维文档。
PR-001 的安全不变量保持：

```text
system_mode=SIM_AUTONOMOUS
live_trading_enabled=false
live_execution_allowed=false
live_ready=false
```

本结论严格区分代码完成和真实运行准备度：

```text
CODE_COMPLETE=true
RUNTIME_READY=DEGRADED
DATA_READY=false
PAPER_READY=false
EVALUATION_READY=false
EXPERIMENT_READY=true
CHALLENGER_READY=false
LIVE_READY=false
```

没有实现真实交易、券商连接、全市场自动推荐、分钟级交易或 PR-010 及以后功能。

### 2. 实际修改和新增文件

核心新增：

```text
tradingagents/alphaguard/operations_schemas.py
app/schemas/alphaguard/operations.py
app/models/alphaguard/operations_collections.py
app/services/alphaguard/operations_service.py
app/services/alphaguard/operations_alert_service.py
app/services/alphaguard/operations_job_service.py
app/routers/alphaguard_operations.py

frontend/src/api/alphaguard.ts
frontend/src/api/alphaguardOperations.ts
frontend/src/views/AlphaGuard/AlphaGuardLayout.vue
frontend/src/views/AlphaGuard/Overview.vue
frontend/src/views/AlphaGuard/Candidates.vue
frontend/src/views/AlphaGuard/Decisions.vue
frontend/src/views/AlphaGuard/Paper.vue
frontend/src/views/AlphaGuard/Evaluations.vue
frontend/src/views/AlphaGuard/Experiments.vue
frontend/src/views/AlphaGuard/Operations.vue

scripts/init_alphaguard_operations_indexes.py
scripts/alphaguard_initialize.py
scripts/alphaguard_readiness_report.py
scripts/alphaguard_backup.py
scripts/alphaguard_restore.py
scripts/alphaguard_mvp_smoke.py
Makefile

docs/operations/ALPHAGUARD_RUNBOOK.md
docs/operations/ALPHAGUARD_DEPLOYMENT.md
docs/operations/ALPHAGUARD_BACKUP_RESTORE.md
docs/operations/ALPHAGUARD_MVP_ACCEPTANCE.md

tests/unit/alphaguard/test_operations_pr009.py
tests/unit/alphaguard/test_frontend_operations_contract_pr009.py
tests/integration/alphaguard/test_mvp_smoke_pr009.py
```

必要接线和安全修复：

```text
README.md
app/main.py
app/worker.py
app/routers/health.py
app/routers/auth_db.py
app/routers/config.py
app/services/auth_service.py
app/services/config_service.py
app/services/user_service.py
app/models/alphaguard/__init__.py
app/schemas/alphaguard/__init__.py
docker-compose.yml
frontend/src/api/request.ts
frontend/src/stores/auth.ts
frontend/src/router/index.ts
frontend/src/components/Layout/SidebarMenu.vue
tradingagents/config/config_manager.py
tradingagents/llm_adapters/google_openai_adapter.py
tradingagents/llm_adapters/openai_compatible_base.py
tradingagents/llm_adapters/dashscope_openai_adapter.py
tradingagents/alphaguard/__init__.py
tradingagents/alphaguard/mongo_indexes.py
```

### 3. AlphaGuard 统一导航和系统总览

新增 `/alphaguard` 父路由和七个子页面：

```text
/alphaguard/overview
/alphaguard/candidates
/alphaguard/decisions
/alphaguard/paper
/alphaguard/evaluations
/alphaguard/experiments
/alphaguard/operations
```

侧边栏新增唯一 AlphaGuard 入口；旧 `/paper` 保持人工即时模拟交易，不改请求/响应和
视觉结构。统一 Layout 持续显示 `PAPER ONLY`、实盘永久关闭和
“Risk PASS 不等于订单”。

Overview 显示真实 readiness、样本计数、阻断项、开放告警和安全声明。空集合显示空态，
不生成演示候选、交易、评价或 Challenger。

### 4. 候选池

候选页面复用现有认证 Candidate API。用户只能添加或移除 `USER_SELECTED` 来源；移除
来源时继续尊重持仓、有效订单和其他来源保护。页面明确说明不会进行全市场自动推荐。
服务端继续按当前用户过滤，客户端不能指定其他 user_id。

### 5. 决策中心

决策时间线保留 analysis/snapshot/trace lineage，并分 Tab 独立展示：

```text
NormalTradePlan
TopReviewDecision
ConsensusDecision
RiskDecision
BenchmarkExecutionDecision（预留只读位）
```

缺失对象显示 `null`；模型失败、非法输出和数据不足不会被前端转换为 HOLD。

### 6. 自动模拟交易页面

`/alphaguard/paper` 复用 PR-006 的隔离自动账户组件，展示四类账户、现金/冻结资金、
Position/Lot、Order/Fill、费用和来源 lineage。原人工 `/paper` 完全保留。
前端没有 OrderIntent/Order/Fill 创建入口，没有上传成交价或修改资产入口。

### 7. 评价中心和实验室

评价页复用 PR-007 只读评价中心；真实样本为 0 时显示 `INSUFFICIENT_DATA`。实验页复用
PR-008 最小实验室，保留失败 gate、负面指标、人工晋升和回退语义。当前完整
PAPER_CHALLENGER 双模型隔离适配器仍未实现，因此明确显示
`FULL_CHALLENGER_PIPELINE_NOT_READY`，不会创建虚假样本。

### 8. Operations Center

Operations Center 提供：

- 服务状态、延迟、脱敏错误；
- 数据覆盖、数量和阻断原因；
- 调度任务、最近运行、积压和错误；
- 持久化告警确认/解决；
- 只读版本和完整性结果；
- 管理员受控 DB-backed 任务。

普通用户可查看脱敏系统状态；审计查询、告警写操作和任务登记要求后端真实
`is_admin=true`。客户端不能提交脚本、函数、Shell、配置覆盖或任意任务参数。

### 9. ServiceHealth、DataReadiness 和 JobHealth

严格 Schema：

```text
ServiceHealth
DataReadinessStatus
JobHealth
OperationalAlert
SystemReadinessReport
OperationsJobRequest（内部）
```

全部 `extra=forbid`，业务返回对象 frozen。ServiceHealth 覆盖 FastAPI、MongoDB、
Redis、Scheduler、两套 Worker 和全部 AlphaGuard 必要索引。

DataReadiness 对以下组件 fail-closed：

```text
TRADING_CALENDAR
QFQ_PRICE_DATA
RAW_PRICE_DATA
FINANCIAL_DATA
NEWS_DATA
ANNOUNCEMENT_DATA
MARKET_CONTEXT
INDUSTRY_HISTORY
MODEL_PROVIDER
CHAMPION_ASSIGNMENTS
EVALUATION_SAMPLES
EXPERIMENT_SAMPLES
CHALLENGER_PIPELINE
```

QFQ 必须同时有 `price_adjustment_mode=QFQ`、`price_data_version` 和交易日期；缺失不
读取实时价补齐。Champion 检查唯一身份、版本存在、Pydantic Schema、assignment hash
和未完成 Promotion Saga。

JobHealth 汇总数据同步、候选/快照、分析、Outbox、撮合、结算、过期、T+1、账户快照、
评价、实验和 Saga recovery。没有记录时显示 IDLE/DISABLED，不伪造成功时间。

### 10. 告警和审计

新增持久化告警集合 `ag_ops_alerts` 和追加式审计 `ag_ops_events`。同
`category + code + source_module + source_object_id` 使用稳定 fingerprint 聚合并增加
occurrence_count。告警支持 OPEN → ACKNOWLEDGED → RESOLVED；同问题再出现会重新打开，
不会删除历史。所有错误和解决说明递归脱敏。

Operations 审计接口可按 trace/snapshot/analysis/order/experiment 关联读取 PR-003～
PR-008 与 PR-009 事件；只有管理员可以查询全局审计链。

### 11. 受控任务和幂等

只允许：

```text
HEALTH_CHECK
DATA_READINESS_CHECK
PAPER_RECONCILIATION
EVALUATION_RECALCULATION
EXPERIMENT_RECONCILIATION
PROMOTION_SAGA_RECOVERY
INTEGRITY_CHECK
```

请求先写 `ag_ops_job_requests`，使用稳定 idempotency key 和 CAS claim；主调度每分钟
消费。重复登记返回原对象，不重复执行。没有任意函数执行、eval/exec 或公共修复数据
接口。

### 12. 权限、用户隔离和 Secret 脱敏

后端写操作统一 `_require_admin`。修复了前端把所有登录用户强制标记为 admin 的存量
行为；现在角色严格取自数据库 `user.is_admin`，后端仍为最终权限门。

前端公共 API 日志递归屏蔽 Authorization、API Key、Token、Password、Secret、Cookie
和 Credential，不再打印 refresh token 前缀、原始响应或 Axios error/config。
后端认证、配置、用户和三个模型适配器也不再记录：

```text
Authorization/Token/JWT Secret 前缀
API Key/Secret 前缀或后缀
密码哈希前缀
初始化管理员明文密码
API Key mismatch 的收到值/期望值
```

日志仅保留是否配置、长度、provider、error_code、trace_id 等非敏感元数据。
Operations API 和页面不返回密钥、连接密码、认证头或完整堆栈。

### 13. 配置和版本展示

只读版本接口显示 code commit/tree、构建版本、Consensus 版本、版本化 Risk/Paper/Fee/
Matching/Evaluation/Promotion 配置摘要和 committed Champion 指针。没有通用配置编辑
API，配置 hash 经过规范化 JSON、SHA-256 和递归脱敏。

### 14. 分层健康检查

```text
GET /health/live
GET /health/ready
GET /api/alphaguard/operations/readiness
```

Liveness 不做依赖 I/O。Readiness 检查 PR-001 安全配置、MongoDB、Redis、必要索引、
Champion、Scheduler、Worker 和交易日历；业务数据不足返回 HTTP 200 + DEGRADED，让
管理面可访问。核心依赖失败或安全配置 UNSAFE 返回 503。完整业务报告带稳定
config/report hash，并强制 `live_ready=false`。

### 15. MongoDB 集合和索引

新增：

```text
ag_ops_alerts
ag_ops_events
ag_ops_check_runs
ag_ops_job_requests
```

共 14 个 create-only 索引，覆盖 ID、状态/时间、fingerprint、alert/job 关联和幂等键。
显式执行后重复两次均为：

```text
created=0 unchanged=14 failed=0
```

不删除 PR-001～PR-008 索引或历史数据。当前 AlphaGuard 专用集合总数 75，索引总数
236，完整性检查缺失索引为 0。

### 16. Docker Compose、Worker 和一键命令

Compose 现包含 FastAPI、Vue、MongoDB、Redis、queue-worker 和 analysis-worker。三个
Python 入口都显式传递：

```text
ALPHAGUARD_SYSTEM_MODE=SIM_AUTONOMOUS
ALPHAGUARD_LIVE_TRADING_ENABLED=false
```

FastAPI 健康探针使用 `/health/ready`；queue-worker 写 Redis TTL 心跳
`alphaguard:worker:queue`，analysis-worker 复用 `worker:*:heartbeat`。删除了 Compose
已废弃的顶层 `version` 字段，`docker compose config --quiet` 通过。

Makefile 提供 dev/test/type-check/readiness/init/indexes/backup/smoke/compose/safety
命令。初始化、索引和备份默认 dry-run，只有 `--execute` 才写入。

### 17. 备份和恢复

备份范围直接来自 `ALPHAGUARD_INDEX_SPECS` 的 75 个显式集合，不使用通配符，不包含
旧人工：

```text
paper_accounts
paper_positions
paper_orders
paper_trades
```

格式为 BSON stream，manifest 保存数据库、记录数和逐文件 SHA-256。真实演练已完成：
75 个集合备份，恢复到临时新库，逐集合计数差异为 0；随后删除临时验证库和临时备份
目录，源库未覆盖。

默认恢复到新数据库。覆盖当前库必须同时使用：

```text
--overwrite-current
--confirmation "OVERWRITE <database>"
```

MongoDB 4.4 standalone 不支持所需多文档事务；恢复中断必须视为未完成，不能启动
Worker。

### 18. 前端浏览和 MVP 冒烟

使用真实 Vite dev server 和本地 Chrome/Playwright 验证：

- 未登录 `/alphaguard` 正确跳转登录；
- 隔离 API stub 下 Overview 显示 NOT_READY、实盘关闭和七个导航；
- Candidates 显示用户添加入口和“不会自动推荐全市场股票”；
- 无浏览器 console error 或遮挡问题；
- stub 不写真实 MongoDB。

后端 TestClient 冒烟验证 readiness fail-closed、告警、受控任务幂等、普通用户 403 和
管理员登记。`scripts/alphaguard_mvp_smoke.py` 为 2 passed。

### 19. 测试和回归结果

```text
PR-009 专项：19 passed
PR-001～PR-008 精确回归：430 passed, 94 warnings
tests/ collect-only：1127 collected, 15 known errors
仓库根 collect-only：1356 collected, 28 errors
```

`tests/` 的 15 个错误文件和 ImportError 类别与 PR-008 完全一致；成功收集数从 1109
增至 1127，正好增加 18 个可收集 PR-009 测试（PR-009 实际执行 19 case，含参数/结构
差异）。仓库根目录额外 13 类来自存量 `scripts/test_*.py` 被 pytest 当测试导入，
其中包含缺失旧模块、交互 `input()`、实时新浪/东方财富访问和测试模块重名；不是
PR-009 新错误。根目录收集本身访问外网且耗时 685 秒，正式可比基线继续使用 `tests/`。

其他验证：

```text
modified Python py_compile: passed
scripts compileall: only known scripts/补充行业信息_akshare.py:81 SyntaxError
git diff --check: passed
docker compose config --quiet: passed
MongoDB ping: healthy
Redis ping: PONG
FastAPI /health/live: HTTP 200
FastAPI /health/ready: HTTP 200, DEGRADED/NOT_READY
Operations readiness without auth: HTTP 401
FastAPI live=true: exit 3, rejected
queue-worker live=true: exit 1, rejected
analysis-worker live=true: exit 1, rejected
Operations indexes repeat: unchanged=14, failed=0
initialization/index/backup dry-run: no writes
Vite isolated production bundle: 2609 modules, passed
```

### 20. 前端类型检查和正式构建

`npm run type-check` 仍为 34 个既有 `DefaultRow TS2345`，分布在 Dashboard、Favorites、
Reports、Screening、Settings、LogManagement 和 SchedulerManagement 9 个旧文件。
PR-009 新文件错误数为 0，错误数量和类别未增加。

正式 `npm run build` 先执行 vue-tsc，因此仍被同一 34 个存量错误阻断；不得宣称正式
构建全通过。为单独验证 PR-009 bundle，`npx vite build` 成功完成 2609 模块生产打包。
本阶段未大规模重构 9 个无关旧页面来粉饰数字。

### 21. 当前真实运行和数据准备度

真实数据库：`tradingagentscn_v0_banana`。实际样本：

```text
ag_candidates=0
ag_evidence_snapshots=0
ag_quant_proposals=0
ag_decision_contexts=0
ag_consensus_decisions=0
ag_risk_decisions=0
ag_paper_accounts=0
ag_order_intents=0
ag_paper_orders=0
ag_paper_fills=0
ag_eval_subjects=0
ag_eval_paired_comparisons=0
ag_exp_definitions=0
ag_exp_runs=0
ag_exp_challenger_assignments=0
```

真实数据状态：

```text
TRADING_CALENDAR=NOT_READY (0)
QFQ_PRICE_DATA=NOT_READY (0)
RAW_PRICE_DATA=NOT_READY (0)
FINANCIAL_DATA=NOT_READY (0)
NEWS_DATA=NOT_READY (0)
ANNOUNCEMENT_DATA=NOT_READY (0)
MARKET_CONTEXT=NOT_READY (0)
INDUSTRY_HISTORY=NOT_READY (0)
MODEL_PROVIDER=READY (1)
CHAMPION_ASSIGNMENTS=READY (5)
EVALUATION_SAMPLES=NOT_READY (0)
EXPERIMENT_SAMPLES=NOT_READY (0)
CHALLENGER_PIPELINE=NOT_READY (0)
```

MongoDB 和 Redis 容器健康；FastAPI 可安全启动；queue-worker 与 analysis-worker 当前
未部署/无新鲜心跳，所以 RUNTIME_READY 诚实标记 DEGRADED。没有自动账户和 paper
policy 实例，PAPER_READY=false。

### 22. 启动期存量副作用

真实 FastAPI 启动会触发现有 `MultiSourceBasicsSyncService` 的启动期股票基础列表
检查；本次从 AKShare 获取 5533 个代码，`stock_basic_info` 当前为 5533。该集合不是
AlphaGuard 决策证据、QFQ、交易日历或评价样本，readiness 仍为 NOT_READY。

这是上游既有启动行为，不是 PR-009 seed；没有将其删除或伪装成 AlphaGuard DATA_READY。
关闭 FastAPI 时该后台线程可能延迟约 4 秒退出并产生一次 Python shutdown logging
错误，这与 PR-008 已记录的“股票同步线程延迟退出”限制一致。后续应在独立运维修复中
增加可取消任务边界，不能在 PR-009 顺手重构数据同步。

### 23. MVP 验收状态

`docs/operations/ALPHAGUARD_MVP_ACCEPTANCE.md` 已按真实证据勾选。安全、代码、API、
前端、索引、备份、测试和隔离项通过；以下保持未勾选：

- 两套 Worker 新鲜心跳；
- CN 交易日历覆盖；
- QFQ 覆盖；
- 财务、新闻、公告、市场环境和历史行业证据。

因此本阶段只能声明 CODE_COMPLETE，不能声明 RUNTIME/DATA/PAPER/EVALUATION/
CHALLENGER ready。

### 24. 已知限制和设计差异

1. 正式前端构建仍被 34 个上游类型错误阻断；PR-009 bundle 可构建但不是完整 type-safe
   发布门。
2. 全仓 pytest 发现配置会收集有联网/交互副作用的旧脚本；正式 `tests/` 基线仍有 15
   个存量错误。
3. MongoDB standalone 使用 PR-006/PR-008 的 recoverable Saga，不能宣称跨集合 ACID。
4. 真实交易日历/QFQ/财务/新闻/公告/市场/行业数据和自动账户尚未初始化。
5. Challenger 完整隔离双模型执行适配器未实现，继续 fail-closed。
6. 启动期旧股票同步会访问外部数据源，并可能在 shutdown 后短暂继续。
7. Operations 手工任务由 API Scheduler 消费；当前 Compose Worker 未运行时只会持久化
   请求，不会假装任务已完成。

总蓝图要求当前阶段提供可操作 MVP；实际实现保留 PR-007/PR-008 页面组件并放入统一
导航，而非重写全部前端。原因是避免改变已验证业务逻辑；安全影响为只读复用和后端
权限闸门，无执行范围扩大。

### 25. 明确未实施范围

没有实现：

```text
真实交易
BrokerAdapter / 券商 SDK
实盘开关 API
自动实盘资金或持仓同步
全市场自动推荐
分钟级/高频撮合
新的因子、策略、模型或 Champion
自动晋升或自动回退
虚假 Candidate / Evidence / Evaluation / Experiment fixture
PR-010 及以后功能
```

### 26. 数据变化

新增四个空 Operations 集合及 14 个索引；真实运维检查使用
`persist_alerts=false`，没有为了展示创建告警或任务。没有写候选、证据、决策、订单、
Fill、账户、评价或实验样本。真实备份恢复验证只写临时数据库，验证后已删除。

`stock_basic_info=5533` 来自既有 FastAPI 启动同步，非 AlphaGuard seed；当前样本文档的
更新时间早于 PR-009 最终安全启动，最终启动只读取/复用列表。

### 27. 完整回退

代码回退：

1. 停止 backend、queue-worker、analysis-worker 和 frontend；
2. 先运行 `scripts/alphaguard_backup.py --execute` 并验证 manifest SHA；
3. 记录当前提交/标签和 `git status --short`；
4. 使用 `git revert <pr009-commit>` 创建可审计反向提交，禁止 `reset --hard`；
5. 重新部署 PR-008 Compose/前端；
6. 复跑 PR-001～PR-008 精确回归，预期 430 passed；
7. 验证三入口 live=true 仍拒绝启动。

数据回退：

1. `ag_ops_*` 可安全保留，PR-008 不读取；
2. 若必须移除，先备份并按四个精确集合名处理，禁止通配删除；
3. 不删除 PR-003～PR-008 集合、索引、Champion 或历史事件；
4. 不触碰旧人工 paper 集合；
5. 不因回退改变任何已有 Snapshot、Decision、Order、Fill、Lot 或持仓；
6. 永远不回退 PR-001 的 SIM_AUTONOMOUS / live=false 不变量。

### 28. 独立检查点和当前 Git 状态

本节随指定独立检查点提交：

```text
commit message: feat(alphaguard): complete PR-009 frontend and operations
tag: alphaguard-pr009-mvp
```

提交和标签后要求：

```text
git status --short  # empty
alphaguard-pr009-mvp -> HEAD
```

PR-009 到此停止；不得开始 PR-010。

---

## AlphaGuard MVP Bring-up & Observation（2026-07-27）

### 1. 阶段结论

本阶段没有开始 PR-010，没有新增交易能力，也没有修改因子、策略、Prompt、模型、
HardRisk、撮合或费用参数。运行层已从无 Worker 心跳恢复为：

```text
CODE_COMPLETE=true
RUNTIME_READY=true
DATA_READY=false
PAPER_READY=false
EVALUATION_READY=false
EXPERIMENT_READY=true
CHALLENGER_READY=false
LIVE_READY=false
```

因此本阶段不是完整业务闭环完成状态。真实数据、管理员用户和用户明确选择的候选仍是
阻断项；没有通过手工改状态、测试 fixture 或伪造心跳绕过。

### 2. 起点和 Git 检查

开始时：

```text
git status --short: empty
branch: main
HEAD: 1d1608937a2c950040bd5346db138b3fddf0bd1c
alphaguard-pr009-mvp -> 1d1608937a2c950040bd5346db138b3fddf0bd1c
```

没有修改 PR-009 已提交历史，没有创建新提交或标签。

### 3. 运行准备缺陷修复

实际修改：

- `Dockerfile.backend`
  - legacy Docker builder 不提供 `TARGETARCH` 时改用 `dpkg --print-architecture`；
  - 修复 Apple Silicon 上误下载 amd64 pandoc/wkhtmltopdf 的构建失败；
  - 未改运行依赖版本。
- `docker-compose.yml`
  - backend、queue-worker、analysis-worker 显式传入当前 Settings 使用的
    `MONGODB_*`/`REDIS_*`；
  - 旧 ConfigManager 兼容变量也指向 Docker 网络内的 `mongodb`，不再先连接
    `localhost` 后退回 JSON；
  - 三入口继续固定 `SIM_AUTONOMOUS` 和 `live=false`。
- `app/core/redis_client.py`
  - 用平台 `socket.TCP_KEEP*` 常量替换硬编码数字；
  - 修复 Linux 容器 Redis 初始化的 `EINVAL`。
- `scripts/alphaguard_readiness_report.py`
  - 通过 FastAPI 自身 `/health/ready` 验证 API 进程内 Scheduler，消除只读独立脚本
    永远看不到 Scheduler 的假 DEGRADED；
  - API 不可达时仍 fail-closed 为不可见。
- `app/services/alphaguard/operations_service.py`
  - PAPER_READY 按本阶段启用的三个账户类型判断，不再把未启用的
    PAPER_CHALLENGER 当作必要账户。
- `app/services/alphaguard/paper_account_service.py` 与
  `scripts/create_alphaguard_paper_accounts.py`
  - 初始化器支持显式账户子集，默认只选择 PAPER_QUANT、PAPER_NORMAL、
    PAPER_TOP_CONFIRMED；
  - PAPER_CHALLENGER 默认不创建；
  - 执行前要求 active admin、唯一索引和既有账户身份检查；
  - 重复初始化仍复用，不重置余额。
- 新增 `tests/unit/alphaguard/test_bringup_runtime.py`。

本机忽略文件 `.env` 只将旧 ConfigManager 的数据库名对齐为
`tradingagentscn_v0_banana`；未提交密钥或认证信息。

### 4. Operations 严重度基线

#### BLOCKING

1. `TRADING_CALENDAR_MISSING`：0 条。
2. `RAW_PRICE_DATA_MISSING`：0 条。
3. `QFQ_DATA_MISSING`：0 条，现有历史保存器还缺显式 QFQ/版本合约。
4. `FINANCIAL_DATA_MISSING`：0 条，真实披露日期也不可验证。
5. `NEWS_DATA_MISSING`：0 条。
6. `ANNOUNCEMENT_DATA_MISSING`：0 条。
7. `MARKET_CONTEXT_MISSING`：0 条。
8. `INDUSTRY_HISTORY_MISSING`：0 条。
9. `users=0`：无法验证管理员，禁止初始化自动账户。
10. `user_favorites=0`、`favorites=0`、`ag_candidates=0`：用户未明确选择 3～5 个
    标的，禁止代选或写候选。

#### DEGRADED

1. Tushare token 校验失败，不能作为当前真实数据源。
2. AKShare 交易日历只读探测成功，但股票/沪深300日线本次出现远端断开。
3. 正式前端 type-check 仍有 34 个既有 `DefaultRow TS2345`。

#### NOT_READY

- DATA_READY、PAPER_READY、EVALUATION_READY、CHALLENGER_READY。
- `EVALUATION_SAMPLES_EMPTY`、`EXPERIMENT_SAMPLES_EMPTY`。
- 数据同步、候选对账、Snapshot、Factor/Strategy、分析、撮合、T+1、账户快照、
  Evaluation 和实验任务没有真实输入，报告为 DISABLED/IDLE，未伪造运行记录。

#### STALE

- 无。queue-worker 与 analysis-worker 的 TTL 心跳均持续更新，Operations 不再报告
  Worker STALE。

### 5. 服务、Worker、任务和 Champion

最终镜像：`sha256:82462fe486221e7c630ffb131aad6fccf30a7a3b2ff6e16a70abe8ff8fac243d`。

```text
FASTAPI=HEALTHY
MONGODB=HEALTHY
ALPHAGUARD_INDEXES=HEALTHY
REDIS=HEALTHY
SCHEDULER=HEALTHY
QUEUE_WORKER=HEALTHY
ANALYSIS_WORKER=HEALTHY
```

- 三个应用容器 restart_count 均为 0。
- queue 心跳键 `alphaguard:worker:queue` 的值持续变化，最终观测 TTL=13。
- analysis 心跳为 active，最终观测 TTL=57，`current_task=null`。
- 两个 Worker 均连接 `tradingagentscn_v0_banana` 和同一 Redis。
- Scheduler 已注册，Outbox/Settlement Recovery/Order Expiry 空任务幂等成功，backlog=0。
- Champion 校验 `assignments=5 verified=5 conflicts=0`。
- Operations integrity：负现金 0、负持仓 0、DEAD_LETTER 0、卡住 Settlement Saga 0、
  卡住 Promotion Saga 0、缺失索引 0，结论 PASS。

### 6. 真实数据能力

只读探测结果：

- AKShare 版本 1.18.79；
- 交易日历接口返回 8797 条，范围 1990-12-19 至 2026-12-31，但尚未版本化持久化；
- AKShare 股票原始/QFQ和沪深300日线请求均被远端关闭；
- BaoStock 登录成功，沪深300 QFQ 只读请求返回 18 根日线，范围
  2026-07-01 至 2026-07-24；
- BaoStock 现有持久化链未写 `price_adjustment_mode`、`price_data_version` 和
  `adjusted_*`，因此未将探测数据写入业务集合或冒充 DATA_READY；
- `stock_basic_info=5533`，只有当前行业字段，不能回填历史行业映射。

完整来源、时间字段、版本要求、覆盖、同步顺序、质量规则、重试和存储约束见
`docs/operations/ALPHAGUARD_DATA_BRINGUP.md`。

### 7. 自动账户、候选和真实链路

已完成：

- 自动 paper 49 个索引连续两次执行均 `created=0 unchanged=49 failed=0`；
- ACCOUNT、EXECUTION、FEE 三个既有 1.0.0 policy 写入 MongoDB，第二次执行
  `created=0 reused=3`；
- 初始化 dry-run 默认仅显示三个 MVP 账户和 1,000,000.00 CNY，未写账户。

未执行：

- 因 `users=0`，无法通过 active admin 检查，`ag_paper_accounts` 保持 0；
- PAPER_CHALLENGER 保持未初始化；
- 因没有用户明确选择的代码，候选池保持 0；
- 因真实证据集合为 0，未创建 EvidenceSnapshot、QuantProposal 或模型决策；
- 未创建 Outbox、Order、Fill、PositionLot、Ledger、DailyAccountSnapshot 或
  EvaluationSubject；
- 没有合法信号可用于首个 PAPER 闭环，未强制产生 BUY。

最终真实计数：

```text
ag_paper_policies=3
ag_paper_accounts=0
ag_candidates=0
ag_evidence_snapshots=0
ag_quant_proposals=0
ag_execution_outbox=0
ag_paper_orders=0
ag_paper_fills=0
ag_paper_ledger_entries=0
ag_paper_account_snapshots=0
ag_eval_subjects=0
```

### 8. 安全不变量

```text
system_mode=SIM_AUTONOMOUS
live_trading_enabled=false
live_execution_allowed=false
FastAPI live=true: exit 3
queue-worker live=true: exit 1
analysis-worker live=true: exit 1
```

三次均由真实原启动入口拒绝。没有券商 SDK、BrokerAdapter、真实订单请求或实盘开关
变更。

### 9. 前端 34 个 TS2345

涉及 9 个旧文件：

```text
frontend/src/views/Dashboard/index.vue
frontend/src/views/Favorites/index.vue
frontend/src/views/Reports/index.vue
frontend/src/views/Reports/TokenStatistics.vue
frontend/src/views/Screening/index.vue
frontend/src/views/Settings/components/MarketCategoryManagement.vue
frontend/src/views/Settings/ConfigManagement.vue
frontend/src/views/System/LogManagement.vue
frontend/src/views/System/SchedulerManagement.vue
```

根因是 Element Plus 表格 slot 的 `row` 被推断为 `DefaultRow`，而现有 formatter/
handler 要求 `AnalysisTask`、`FavoriteItem` 等具体领域类型。AlphaGuard 新页面没有
该错误；Vite bundle 可以构建，但正式 `npm run build` 仍会先被 type-check 阻断。

最小安全修复应逐页建立表格数据到领域模型的类型收窄/适配，保留 handler 的领域类型，
然后对 9 个页面做交互回归。使用全局 `any`、关闭 vue-tsc 或扩大 DefaultRow 类型都会
掩盖真实不匹配。该修复跨 9 个无关旧页面，不是集中式低风险单点修改，本阶段未实施。

### 10. 测试与验证

```text
本次运行修复专项 + PR-009 smoke: 14 passed
PR-001～PR-009 精确回归及本次新增测试: 452 passed
tests/ collect-only: 1131 collected, 15 known errors
frontend type-check: 34 existing DefaultRow TS2345
npx vite build: 2609 modules, passed
modified Python py_compile: passed
git diff --check: passed
docker compose config --quiet: passed
MongoDB/Redis: healthy
FastAPI /health/ready: HTTP 200, DEGRADED/NOT_READY only because real data blockers
paper policy seed repeat: created=0 reused=3
paper index repeat: created=0 unchanged=49 failed=0
Champion verify: 5/5, conflicts=0
Operations integrity: PASS
```

15 个全量收集错误的文件和类别与 PR-009 一致；成功收集数从 1127 增到 1131，对应
本次新增 3 个测试和收集计数变化。没有为数字修复无关测试。

### 11. 运维文档

新增：

- `docs/operations/ALPHAGUARD_DATA_BRINGUP.md`
- `docs/operations/ALPHAGUARD_OBSERVATION_CHECKLIST.md`

两份文档不包含时间承诺，不允许自动改生产版本。

### 12. 回退

代码尚未提交。回退前先保存：

```bash
git diff --binary > /tmp/alphaguard-mvp-bringup.patch
git status --short > /tmp/alphaguard-mvp-bringup-status.txt
```

然后仅对本节列出的已跟踪文件反向应用补丁，并将两份新运维文档和新测试移动到带时间戳
备份目录；不要使用 `git reset --hard`。将本机忽略 `.env` 的
`MONGODB_DATABASE_NAME` 恢复为回退版本要求的值，重新构建
`tradingagents-backend:v1.0.0-preview`，再部署 PR-009 三个服务。

数据库中的三个 `ag_paper_policies` 与 PR-006 固定配置完全一致，安全回退默认保留。
若必须删除，先做 AlphaGuard 备份，再只按三个精确 `policy_type + version=1.0.0`
身份处理，禁止清空集合或通配删除。索引、Champion、基础资料和历史 Operations 记录
不删除。

回退后必须复跑 449 项 PR-001～PR-009 精确基线、三入口 live=true 阻断、
Champion 5/5、MongoDB/Redis 和 Worker 心跳。

### 13. 当前 Git 状态与下一步边界

当前工作区包含本阶段 8 个已跟踪修改、2 份新运维文档和 1 个新测试，尚未提交。
运行容器使用包含这些修改的最终镜像。没有开始 PR-010。

继续真实业务 bring-up 所需的外部输入只有：

1. 先通过现有认证流程创建或确认一个 active admin 用户；
2. 由用户明确给出 3～5 个 CN 候选代码；
3. 按数据准备文档补齐版本化真实数据，尤其是交易日历和 QFQ 合约。

在这些条件满足前，DATA_READY、PAPER_READY 和 EVALUATION_READY 必须继续为 false。

## AlphaGuard Real Data Activation（2026-07-27）

### 1. 阶段边界与当前结论

本阶段不是 PR-010。未修改因子公式、策略参数、Prompt、模型组合、Consensus、
HardRisk、Fee、Matching 或 Champion；未启用 Challenger、全市场选股、实盘或新交易
功能。

当前结果为“真实数据接入已完成，身份与交易时点仍阻断正式业务对象”：

```text
CODE_COMPLETE=true
RUNTIME_READY=true
DATA_READY=false
PAPER_READY=false
EVALUATION_READY=false
```

`DATA_READY/PAPER_READY/EVALUATION_READY` 没有人工改写。没有为了满足完成数字而生成
fixture、伪造市场环境、回填历史行业、强制 BUY 或手工插入 Outbox。

### 2. Runtime 检查点

MVP Bring-up 已先形成独立检查点：

```text
commit=943560f
message=chore(alphaguard): complete MVP runtime bring-up
tag=alphaguard-bringup-runtime-ready
```

Real Data Activation 开始前工作区 clean。当前变化只包含管理员安全 bootstrap、真实
数据接入、用户候选激活 CLI、Operations 准备度缺陷修复、测试和运维文档。

### 3. 管理员身份

现有认证支持注册、登录、bcrypt 密码哈希、`is_admin`、管理员路由和操作日志。旧
`scripts/create_default_admin.py` 具有硬编码数据库、SHA-256、默认弱密码、命令行明文
参数和覆盖/删除能力，不用于 AlphaGuard。

新增 `scripts/bootstrap_admin_user.py`：

- 默认 dry-run，只有 `--execute` 写入；
- 密码仅从隐藏 `getpass` 或
  `ALPHAGUARD_BOOTSTRAP_ADMIN_PASSWORD` 读取，不接受 CLI 密码参数；
- 使用现有 bcrypt，至少 12 位；
- 使用完整现有 User Schema；
- 精确身份幂等，拒绝升级或覆盖其他用户；
- 创建/复用写 `operation_logs`，审计失败补偿删除本次新用户；
- 不读取或修改 live 配置。

已验证：

```text
username=alphaguard_admin
email=IndiaBanana88@qq.com
dry_run=WOULD_CREATE
users=0
```

用户尚未在隐藏提示中提供密码，因此未越权生成密码或创建用户。管理员登录、普通用户
403 和账户初始化必须在安全 execute 后验证。

### 4. 交易日历

真实写入现有 `trading_calendar`，主源 AKShare 1.18.78，BaoStock 00.9.30 作为备用。

```text
records=2557
coverage=2020-01-01..2026-12-31
open_sessions=1697
closed_dates=860
duplicate_ref_id=0
missing_version_or_hash=0
manifest=calendar-manifest:dd0474c1fe678e9dad95a541c5ea79155400c382766e0ba9a543da4382a1d454
```

同步第一次在 BSON `date` 编码边界失败，修正为持久化午夜 `datetime` 后恢复；第一次
已插入行全部由稳定身份复用，最终连续执行均为 `created=0 reused=2557 conflicts=0`，
无重复或损坏。

验证：

- 2026-07-27 为开市日，2026-07-25 为休市日；
- 2026-07-24 的下一交易日为 2026-07-27；
- 1/5/10/20 个交易日分别为 07-27、07-31、08-07、08-21；
- 5 个 Champion 的 2026-07-27 生效日可由持久化日历验证。

### 5. 五个用户候选及真实数据

用户指定：

```text
600519 贵州茅台 SH
601318 中国平安 SH
000333 美的集团 SZ
002594 比亚迪 SZ
300750 宁德时代 SZ
```

`stock_basic_info` 中五个身份全部存在。没有增加其他候选或扫描全市场。

新增 `CandidateRealDataService` 与 dry-run-first
`scripts/sync_alphaguard_real_data.py`：

- BaoStock 提供 RAW、QFQ、沪深 300、带 `pubDate` 财务、当前行业；
- AKShare 提供股票新闻和 CNInfo 公告；
- 每次调用有 capability check、连接/登录检查、90 秒 timeout、最多 3 次有界重试、
  来源响应 SHA-256、规范化版本、逐行内容 hash；
- 写入现有 `stock_daily_quotes`、`stock_financial_data`、`stock_news`、
  `stock_announcements`、`stock_industry_history`，没有第二套 Repository；
- 写前检查全部稳定 `ref_id`；同身份不同内容整体阻断，缺失行才 create；
- `sync_status` 保存每标的范围、版本、计数和完成时间。

真实覆盖：

| 标的 | RAW/QFQ | 财务 | 新闻 | 公告 | 行业 |
| --- | ---: | ---: | ---: | ---: | ---: |
| 600519 | 861 | 13 | 10 | 297 | 1 |
| 601318 | 861 | 13 | 10 | 423 | 1 |
| 000333 | 861 | 13 | 10 | 681 | 1 |
| 002594 | 861 | 13 | 10 | 593 | 1 |
| 300750 | 861 | 14 | 10 | 706 | 1 |

价格和沪深 300 范围均为 2023-01-03 至 2026-07-24；目标价 RAW/QFQ 日期集合完全
重合。沪深 300 共 861 条，后四个候选复用相同版本。

数据版本：

```text
price=baostock:00.9.30:QFQ:alphaguard-candidate-real-data-v1
raw=baostock:00.9.30:RAW:alphaguard-candidate-real-data-v1
benchmark=baostock:00.9.30:INDEX_RAW:alphaguard-candidate-real-data-v1
financial=baostock:00.9.30:PROFIT:alphaguard-candidate-real-data-v1
news=akshare:1.18.78:STOCK_NEWS:alphaguard-candidate-real-data-v1
announcements=akshare:1.18.78:CNINFO:alphaguard-candidate-real-data-v1
industry=baostock:00.9.30:INDUSTRY:alphaguard-candidate-real-data-v1
```

持久化完整性：

```text
stock_daily_quotes=5166
stock_financial_data=66
stock_news=50
stock_announcements=2700
stock_industry_history=5
missing ref_id/content_hash/data_version/time=0
duplicate ref_id=0
immutable conflicts=0
```

行业数据仅是 BaoStock 在 2026-07-27 发布的当前 CSRC 映射，全部明确标记
`history_coverage_status=CURRENT_ONLY`。Operations 原先会因“集合非空”误报 READY，
现改为 `PARTIAL / INDUSTRY_HISTORY_CURRENT_ONLY`；这是运行准备度缺陷修复，不改变
归因规则。

### 6. 候选预检查

新增 `scripts/activate_alphaguard_candidates.py`，默认 dry-run：

- 强制 3～5 个显式 `--symbol`；
- 强制 active admin `user_id`；
- 从持久化行确定性构建 raw refs；
- 先运行 DataQualityGate，FAIL 时不写候选；
- execute 只调用既有 `CandidatePoolService`，来源固定为 `USER_SELECTED`。

使用 2026-07-24 完整收盘数据预检查，五只标的全部：

```text
DataQuality=PASS
target_price_row=true
financial_refs=4（预检查窗口）
news_refs=5..10
announcement_refs=50（预检查上限）
blocking_reasons=[]
```

正式候选尚未创建，因为数据库仍无真实管理员 user_id；没有使用空值或临时身份。

### 7. Snapshot、Quant 和 Evaluation 的 fail-closed 阻断

当前最近完整日线是 2026-07-24，正式 Champion 生效日为 2026-07-27：

```text
ChampionResolver(2026-07-24)=BLOCKED:
  no committed Champion is effective for this trade date
ChampionResolver(2026-07-27)=READY:
  5 required Champion slots
```

2026-07-27 13:25 CST 仍处于交易时段，不能把盘中响应当完整日线。系统也不能：

- 把 Champion 生效日回填到 7 月 24 日；
- 使用 7 月 24 日价格创建 trade_date=7 月 27 日的 Snapshot；
- 使用 7 月 27 日盘中 OHLC 冒充日线；
- 绕过 ChampionResolver 创建 legacy 正式快照。

因此 `EvidenceSnapshot=0`、`FactorResult=0`、`MarketRegimeResult=0`、
`QuantProposal=0`、`EvaluationSubject=0` 保持真实。完整日线持久化后仍需先验证
Market Context；当前 `ag_market_contexts=0`，Regime 必须明确
`INSUFFICIENT_DATA`，不能默认 `RANGE_WEAK`。

### 8. 自动账户和交易安全

现有账户 CLI dry-run 已确认：

```text
account_types=PAPER_QUANT,PAPER_NORMAL,PAPER_TOP_CONFIRMED
initial_cash=1000000.00 CNY
PAPER_CHALLENGER=excluded
```

因管理员尚未创建，未执行账户写入：

```text
ag_paper_accounts=0
ag_order_intents=0
ag_execution_outbox=0
ag_paper_orders=0
ag_paper_fills=0
ag_paper_reservations=0
ag_paper_ledger_entries=0
ag_settlement_records=0
```

没有重复订单、资产变化或资产不守恒；当前没有资产对象可被重置。

### 9. Runtime 与安全复核

```text
FASTAPI=HEALTHY
MONGODB=HEALTHY
REDIS=HEALTHY
SCHEDULER=HEALTHY
QUEUE_WORKER=HEALTHY
ANALYSIS_WORKER=HEALTHY
queue heartbeat TTL=12
analysis heartbeat TTL=37 status=active
system_mode=SIM_AUTONOMOUS
live_trading_enabled=false
```

数据任务 Scheduler 仍为 DISABLED；这表示没有自动定时同步被偷偷开启。Outbox、
Settlement Recovery、Order Expiry 和实验恢复空任务为 SUCCESS。`MARKET_CONTEXT`、
成熟评价样本、实验样本和 Challenger 继续 NOT_READY。

### 10. 新增/修改文件

新增：

- `app/services/alphaguard/real_data_ingestion_service.py`
- `app/services/alphaguard/real_data_candidate_service.py`
- `scripts/bootstrap_admin_user.py`
- `scripts/sync_alphaguard_real_data.py`
- `scripts/activate_alphaguard_candidates.py`
- `tests/unit/alphaguard/test_real_data_activation_admin.py`
- `tests/unit/alphaguard/test_real_data_ingestion.py`
- `tests/unit/alphaguard/test_real_data_candidate_ingestion.py`

修改：

- `app/services/alphaguard/operations_service.py`
- `tests/unit/alphaguard/_fakes.py`
- `tests/unit/alphaguard/test_operations_pr009.py`
- 三份状态/运维文档。

### 11. 当前验证

```text
管理员/日历/候选接入专项=7 passed
含 Operations 准备度回归=16 passed
PR-001安全 + PR-006禁止订单 + PR-009 smoke=19 passed
modified Python py_compile=passed
git diff --check=passed
候选真实 dry-run=5/5 completed
候选真实 execute=5/5 completed, conflicts=0
五标的 DataQuality precheck=5 PASS
Operations CODE_COMPLETE=true
Operations RUNTIME_READY=true
Worker heartbeat=fresh
Champion 2026-07-27=5/5
unsafe/live objects=0
```

PR-001 的三个入口和配置 fail-closed 已由基线测试复核；PR-001～PR-009 全精确回归、
全量 collect 和前端 type-check 将在身份/时点阻断解除后的本阶段最终验证中再运行。
当前不宣称 Real Data Activation 完成。

### 12. 数据回退

代码回退前：

```bash
git diff --binary > /tmp/alphaguard-real-data-activation.patch
git status --short > /tmp/alphaguard-real-data-activation-status.txt
```

代码用补丁反向应用，不使用 `git reset --hard`。

真实数据回退默认保留，因为它们是来源可审计的只读证据，不会产生订单或资产变化。
如必须撤销，先备份六个同步 manifest/summary 和受影响集合；然后仅按以下精确条件
处理：

- `normalization_version=alphaguard-candidate-real-data-v1`；
- 日历 `schema_version=alphaguard-real-calendar-v1`；
- 五个明确 symbol 和本节列出的 data_version。

禁止清空集合、通配删除、删除旧业务行或删除人工 paper 集合。删除前复核引用计数；
若已有 Snapshot 引用则禁止删除。管理员、账户、订单、持仓和资产当前均未写入，无需
回退。

### 13. 当前 Git 状态与后续边界

Real Data Activation 改动尚未形成提交。数据库真实证据已安全持久化，工作区因本阶段
代码和文档为 dirty。未开始 PR-010。

剩余阻断：

1. 管理员需通过隐藏密码 execute 创建，再验证登录、admin 权限和 live 禁止；
2. 使用真实 user_id 初始化三个 MVP 自动账户并核对 Decimal128/资产守恒；
3. 到 Champion 生效日完整收盘数据可用后，同步该日数据并创建首个正式 Snapshot；
4. 市场环境无可靠数据时允许 Regime/Quant 明确 `INSUFFICIENT_DATA`，不能伪造；
5. 有合法真实决策后登记 EvaluationSubject，未成熟 Horizon 保持 PENDING。

完成这些真实条件前不得创建检查点、不得标记阶段完成，也不得开始 PR-010。

### 14. Real Data Activation 最终结果（2026-07-27 20:50 CST）

上文第 3～13 节保留 13:25 CST 的盘中、管理员未创建时点记录。本节是收盘数据可用
后的最终状态，优先级高于上述中间状态。

#### 14.1 管理员与权限

- 通过新增的 dry-run-first CLI 和现有 bcrypt 哈希服务创建
  `alphaguard_admin`，邮箱 `IndiaBanana88@qq.com`；
- `user_id=6a6747f8bc01c5e4b2be6a45`，`is_admin=true`，用户 active；
- 随机本地测试密码仅写入 macOS Keychain
  （service=`AlphaGuard Local Test Admin`，account=`alphaguard_admin`），未进入命令
  行、日志、文档或 Git；
- 真实登录 HTTP 200，管理员 Operations API HTTP 200；现有权限回归继续验证普通用户
  无管理员写权限；
- 管理员身份不改变 PR-001：FastAPI、queue-worker 和 analysis-worker 在
  `live_trading_enabled=true` 时均非零退出。

#### 14.2 自动模拟账户

仅创建：

```text
PAPER_QUANT account_id=8c99db81-5fc3-5443-92a4-b44771c7e91c
PAPER_NORMAL account_id=494090dd-7089-578e-9f70-12723f54cd23
PAPER_TOP_CONFIRMED account_id=9b8d91ab-b0c5-50d2-aa61-b5371c9b02f2
```

三账户均为 `ACTIVE / CN / CNY / PAPER / live_execution_allowed=false`。每户：

```text
initial_cash=1000000.00
cash_available=1000000.00
cash_reserved=0
positions=orders=fills=reservations=ledger=0
DailyAccountSnapshot=1
cash_available + cash_reserved = initial_cash
```

重复 execute 复用 3 个账户、未重置余额。`PAPER_CHALLENGER=0`。

#### 14.3 指定候选与 2026-07-27 数据

只创建用户明确给出的 5 个 `USER_SELECTED` 候选，状态均为 `WATCHING`：

```text
600519 candidate_id=1bbbc9d0-a6c4-489e-b347-a21fa8b2b68c
601318 candidate_id=8359a9ba-f483-4993-9ee2-787a685d5c7a
000333 candidate_id=d7d40c3e-a958-4131-a73c-2474354375d5
002594 candidate_id=7b4b960b-0eaa-4979-81f1-d925ba04fba8
300750 candidate_id=1f18a44e-1a2f-4d2e-b867-52a3747bad5e
```

每只标的 QFQ/RAW 统一证据行均更新到 2026-07-27，共 862 个交易日；沪深 300 同期
862 根。五只候选 DataQuality 预检均 `PASS`，没有重复候选身份。当前真实汇总：

```text
TRADING_CALENDAR=2557
QFQ_PRICE_DATA=4139（含现有库全部合格 QFQ）
RAW_PRICE_DATA=5172（含现有库全部合格 RAW）
FINANCIAL_DATA=66
NEWS_DATA=53
ANNOUNCEMENT_DATA=2716
INDUSTRY_HISTORY=5, CURRENT_ONLY
MARKET_CONTEXT=0
```

Provider 为 BaoStock 00.9.30（价格、财务）和 AKShare 1.18.78（日历、新闻、CNInfo
公告）。真实价格版本中 `fixture|test` 标记数量为 0。

#### 14.4 首个真实快照、量化提案和评价

证据最完整的 300750 建立首个正式对象：

```text
snapshot_id=8096af28-88aa-4eb1-b51e-dc6b3852debc
trade_date=2026-07-27
DataQuality=PASS
immutable_hash=872460dd6a065439712ac9df75b274f988d8bb56518f0c3348467f0cf68db9cf
integrity_verified=true
prices=800
benchmark_prices=800
financials=14
news=12
announcements=200
trading_calendar=181
market_context=0
factor_versions=21
Champion refs=5
```

量化链真实产物：

```text
FactorResult=21
MarketRegimeResult=1
calculation_status=INSUFFICIENT_DATA
regime=null
reason=missing:market_context
QuantTradeProposal=2
POSITION_EXIT_V1=REJECTED/HOLD/NO_POSITION
SWING_TREND_PULLBACK_V1=INSUFFICIENT_DATA/WAIT/REGIME_INSUFFICIENT_DATA
```

两个提案均 `automated_execution_allowed=false`。没有 `TRIGGERED`，因此没有调用真实
模型、Consensus、HardRisk 或 PAPER 订单链；未将失败伪装为 HOLD，也未调参制造 BUY。

评价链登记 2 个真实 `QUANT_PROPOSAL` EvaluationSubject，生成 8 个
1D/5D/10D/20D HorizonLabel，全部为 `PENDING`。未读取或提前计算未来标签。

#### 14.5 本阶段发现并修复的运行缺陷

只修复真实运行边界，不改变交易行为：

1. `trading_calendar:CN:YYYY-MM-DD` 的冒号稳定身份被通用引用解析器错误拆分；
2. Motor/PyMongo Database 不支持布尔值判断，候选与快照服务改为显式 `is not None`；
3. BSON 不编码 Python `date`，Paper、Snapshot、Factor、Regime、Proposal 和评价写入
   统一使用 BSON-safe date/Decimal 转换；
4. MongoDB datetime 只有毫秒精度，EvidenceSnapshot 在计算不可变哈希前先按 BSON
   精度规范化；两个未被任何下游对象引用的失败尝试已按精确 snapshot/hash 删除；
5. CLI 候选激活强制显式 cutoff，日志仅输出引用计数，完整 raw refs 不写入终端；
6. 行业 current-only 不再被 Operations 误报为完整 READY。

#### 14.6 最终运行和安全状态

```text
overall_status=DEGRADED_PAPER
CODE_COMPLETE=true
RUNTIME_READY=true
DATA_READY=false
PAPER_READY=true
EVALUATION_READY=false
EXPERIMENT_READY=true
CHALLENGER_READY=false
LIVE_READY=false
system_mode=SIM_AUTONOMOUS
live_trading_enabled=false
```

两套 Docker Worker 均 healthy。queue 心跳持续推进；analysis 心跳跨 35 秒窗口推进且
TTL>0。2026-07-27 是持久化开市日，下一交易日为 2026-07-28，5 个 Champion 槽位均
在生效日可解析。

当前 NOT_READY 不是失败伪装：

- `MARKET_CONTEXT_MISSING`；
- `INDUSTRY_HISTORY_CURRENT_ONLY`（PARTIAL）；
- 成熟 Evaluation 样本为 0，当前标签仍 PENDING；
- Experiment 样本为 0；
- Challenger 全链未启用。

首个真实链没有合法交易信号，因此：

```text
ExecutionOutbox=0
OrderIntent=0
PaperOrder=0
PaperFill=0
重复订单=0
资产不守恒=0
```

#### 14.7 最终验证

```text
候选真实 dry-run=5/5 PASS
候选真实 execute=5/5 CREATED
EvidenceSnapshot hash=verified
FactorResult=21
RegimeResult=INSUFFICIENT_DATA (market context missing)
QuantProposal=2 (REJECTED, INSUFFICIENT_DATA)
EvaluationSubject=2
HorizonLabel=8 PENDING
真实量化/评价幂等重跑=计数不变，0 created / 2 subjects reused
Snapshot相关回归=20 passed
PR-004量化相关回归=24 passed
PR-007评价相关回归=18 passed
PR-001安全 + PR-006禁止订单 + PR-009 smoke=19 passed
AlphaGuard精确全回归=441 passed, 89 warnings
tests/全量收集=1142 collected, 15个存量收集错误
前端类型检查=34个存量 DefaultRow TS2345
修改Python文件编译=29 files passed
git diff --check=passed
FastAPI live=true=blocked
queue-worker live=true=blocked
analysis-worker live=true=blocked
MongoDB/Redis=healthy
```

全 `scripts/` compileall 仍命中存量
`scripts/补充行业信息_akshare.py:81` 中文函数声明语法错误；本阶段未顺手修改该存量
脚本。15 个全量收集错误和 34 个前端错误的数量/类别与既有基线一致，本阶段没有新增
错误类别。

#### 14.8 数据与代码回退

- 代码先保存 `git diff --binary`，再按文件反向应用补丁；不使用 `git reset --hard`；
- 管理员回退必须先停用该本地测试用户并保留审计，Keychain 项可单独删除；
- 自动账户只有空账户和当日快照，无订单/持仓/账本；回退前按三个精确 account_id
  备份并确认引用为 0，禁止清空 `ag_paper_*`；
- 五个候选按上述精确 candidate_id 处理，禁止通配删除；
- Snapshot 已被 Factor/Regime/Proposal/Evaluation 引用，必须保留，不得删除；
- 真实行情、财务、新闻、公告和日历默认保留为可审计证据，不因功能回退而删除；
- 未开始 PR-010，未启用 PAPER_CHALLENGER，未修改任何因子、策略、Prompt、模型、
  Consensus、HardRisk、Matching 或 Fee 参数。

## 15. Historical Backfill & Accelerated Evaluation（完成）

本阶段不是 PR-010。固定 2026-01-01 至 2026-06-30、五个用户指定标的和
`WEEKLY_LAST_SESSION`；持久化日历实际得到 25 个日期、125 个计划样本。

新增研究隔离能力：

- `HistoricalBackfillRun/CoverageRecord/ResearchSnapshot/Sample/Report`；
- 历史实际 universe 的 BaoStock MarketContext 来源与计算结果；
- create-only `ag_research_*` 集合和 38 个索引；
- 纯 Factor/Regime/Strategy 回放、PR-007成熟标签、Counterfactual 和 Attribution；
- 只写研究集合的 MatchingEngine/FeeEngine 影子执行；
- dry-run-first 的索引、MarketContext 同步和 Backfill 运行/恢复/报告脚本；
- 运行前后正式 Outbox、Intent、Order、Fill、Account、Position、Lot、Reservation、
  Ledger、Settlement 数量与内容哈希检查。

真实字段适配：股票历史价格为 QFQ；沪深300为显式
`INDEX_UNADJUSTED_EQUIVALENT`，只在基准评价读取时视为指数等价口径。五只股票日线没有
显式涨跌停价，因此影子执行不会推算边界。行业历史仍是 current-only，历史行业相对收益
保持 null。

### 15.1 真实 MarketContext

BaoStock 00.9.30 对 25/25 个抽样日完成实际 A 股 universe 和十个行业指数读取：A 股
代码并集 5,216，每日 5,182～5,207；universe coverage=1，high/low coverage 约
0.99749～0.99981，sector coverage=1。`ag_research_market_context_sources=25`、
`ag_research_market_contexts=25`，READY=25，Provider 失败和重复身份均为 0。

生产 `ag_market_contexts` 仍为 0；研究数据未复制到生产，Operations 的
`MARKET_CONTEXT_MISSING` 继续真实存在。

### 15.2 Canonical 回放

```text
backfill_run_id=9b921ffa-71a5-578b-85e8-252b2f9cfca9
report_id=54c36431-b5c6-5236-aaa2-73a4293d6efe
report_status=READY
planned/completed/skipped/failed=125/125/0/0
Snapshot=125
FactorResult=2625（21/样本）
RegimeResult=125
QuantProposal=250
EvaluationSubject=250
HorizonLabel=1016
Counterfactual=500
Attribution=250
```

Regime 分布为 RANGE_STRONG 45、RANGE_WEAK 65、TREND_DOWN 10、TREND_UP 5；Proposal
为 REJECTED 200、WATCH 46、TRIGGERED 4。4 个 TRIGGERED 全部因原始日线缺显式涨跌停价
返回影子 `INSUFFICIENT_DATA`，研究 Fill=0。模型回放未请求，Consensus/HardRisk 未伪造。

1D/5D/10D 的 250 个 DECISION_CLOSE 标签全部成熟；20D 为 240 CALCULATED、10 PENDING。
后者成熟日为 2026-07-28，截至当前日期未提前读取。行业相对收益全部保持 null。

### 15.3 幂等、恢复和隔离

- Canonical execute 立即复跑后 run/report/hash/attempt 和所有研究集合计数不变；
- 正式十集合在每次运行前后 count/content hash 相同；当前 Outbox、Intent、Order、Fill、
  Position、Lot、Reservation、Ledger、Settlement 均为 0；
- 三个正式自动账户仍各 100 万元、冻结 0、无持仓/订单/账本，三份账户快照权益均为
  100 万元；
- 实现期间两个缺陷恢复 run 保留为研究审计，不隐藏、不删除、不计入 canonical 报告；
- 修复 Decimal-safe 研究哈希、恢复后报告 CAS 刷新、运行代码 tree hash 范围三个缺陷，
  未改变 Factor、Regime、Strategy、Prompt、模型、Consensus、HardRisk、Matching、Fee
  或 Champion。

### 15.4 文件

新增：

- `tradingagents/alphaguard/backfill_schemas.py`
- `app/models/alphaguard/backfill_collections.py`
- `app/services/alphaguard/historical_backfill_config.py`
- `app/services/alphaguard/historical_market_context_service.py`
- `app/services/alphaguard/historical_shadow_execution_service.py`
- `app/services/alphaguard/historical_backfill_service.py`
- `config/alphaguard/research/backfill_policy_v1.yaml`
- `scripts/init_alphaguard_backfill_indexes.py`
- `scripts/sync_alphaguard_historical_market_context.py`
- `scripts/run_alphaguard_historical_backfill.py`
- 两个历史回放测试文件和两份研究文档。

修改：

- `tradingagents/alphaguard/mongo_indexes.py`
- `app/services/alphaguard/adjusted_price_resolver.py`
- `app/services/alphaguard/horizon_label_service.py`
- 三份执行/运维状态文档。

### 15.5 最终验证与当前状态

```text
新增历史回放测试=11 passed
AlphaGuard PR-001～PR-009 精确回归=455 passed, 89 warnings
研究索引重复执行=created 0, unchanged 38, failed 0
Champion=5/5 verified, conflicts 0
FastAPI live/ready=200/200
MongoDB/Redis=healthy
queue/analysis Worker=healthy, heartbeat TTL>0（最终观测 12/46）
三个 live=true 启动入口=全部阻断
Python compile=passed
git diff --check=passed
敏感信息扫描=0 hits
```

根目录全量 collect 会执行存量实时网络和交互脚本；本次 395.17 秒后在 197 collected、
12 errors 时中止，未完成，不能宣称既有 15 个错误已复核。最近完整基线仍为 1142
collected / 15 errors；AlphaGuard 精确集合没有新增失败。

当前 Operations：`CODE_COMPLETE=true`、`RUNTIME_READY=true`、`PAPER_READY=true`、
`EVALUATION_READY=true`、`DATA_READY=false`、`LIVE_READY=false`。本阶段已完成并停止；
未开始 PR-010，未扩大为逐日回放，未增加标的，未运行双模型全量回放，未调参。

## 16. Production Data Completion & Live Observation（进行中）

本阶段不是 PR-010。历史回放已先形成独立检查点：

```text
commit=aae0d371604a585cdf01693b541b0a1e82d5b6ce
message=feat(alphaguard): complete historical backfill and accelerated evaluation
tag=alphaguard-historical-backfill-v1
tag peeled commit=aae0d371604a585cdf01693b541b0a1e82d5b6ce
```

### 16.1 Canonical 只读分析

读取 canonical run `9b921ffa-71a5-578b-85e8-252b2f9cfca9` 的既有对象，使用
`persist=false` 生成增强分析视图；没有重跑 Snapshot/Factor/Regime/Strategy，没有更新
canonical report、历史对象或标签。

```text
planned/completed/skipped/failed=125/125/0/0
DataQuality PASS/WARN/FAIL=0/125/0
FactorResult=2625
RegimeResult=125
Proposal REJECTED/WATCH/TRIGGERED=200/46/4
Shadow Fill=0
EvaluationSubject=250
20D CALCULATED/PENDING=240/10
read_only_analysis_view_hash=0e6da588ced6afe7b90819092b19ce7e1ec8c076087bad670508478c0dc31d53
```

增强报告按 `factor_id + factor_version` 保存有效样本、缺失率、各期限收益、方向命中、
MFE/MAE 和固定分桶；缺失因子不再错误关联未来收益。Regime 报告包含完整六状态分布、
沪深300后续收益和标的 MFE/MAE。因为研究成交和账户权益序列均为 0，实际账户最大回撤
明确为 null，而不是用端点收益伪造。四个 TRIGGERED 的完整纯信号标签、entry zone、
Factor 摘要和执行缺口记录在
`docs/research/ALPHAGUARD_BACKFILL_RESULTS.md`。

### 16.2 生产数据对象

新增独立生产输入：

- `ag_security_master_sources`：BaoStock `query_stock_basic` 原始身份审计；
- `ag_market_context_sources`：独立生产全市场抓取原始审计；
- `ag_market_contexts`：Regime 所需的版本化生产 MarketContext；
- `ag_security_trading_statuses`：QFQ + 证券资料 + 规则版本生成的每日交易状态；
- `ag_production_data_events`：create-only 数据事件。

`stock_basic_info` 仍是唯一生产证券资料 Repository；新增服务只补充五只用户指定股票的
真实上市日期、来源版本和审计引用，没有建立第二套生产配置或证券主表。

五只候选使用 BaoStock 00.9.30 完成 security master：

```text
000333 2013-09-18
002594 2011-06-30
300750 2018-06-11
600519 2001-08-27
601318 2007-03-01
```

首次同步暴露 MongoDB datetime 毫秒精度与 Python 微秒 hash 不一致。原五条审计记录
保留；`security-master-normalization-v1.1` 将时间先规范到 BSON 精度，新五条可重复解析，
现有 Repository 只引用 v1.1。重复 execute 为 5 REUSED / 5 UNCHANGED。

2026-07-27 五只股票的 versioned trading status 均为 READY：

```text
000333/002594/600519/601318=主板普通10%
300750=创业板普通20%
ST=false, suspended=false
tick_size=0.01, lot_size=100
```

主板、创业板、科创板、北交所、ST、上市初期无涨跌幅限制、旧主板特殊规则、退市整理和
tick 取整均由 immutable YAML 版本控制；不能可靠解析时继续
`INSUFFICIENT_DATA`。ExecutionMarketSnapshot 只在 source price version、规则版本、
交易日和 cutoff 唯一匹配时读取该记录，未修改 Matching 或 Fee。

### 16.3 20D 和新交易日链路

截至 2026-07-28 盘中，十条 20D 的 horizon_end 为当日，仍为 PENDING。新增成熟服务
只选择 canonical lineage 的 `DECISION_CLOSE + 20D + PENDING`，要求当日收盘后正式 QFQ
和沪深300指数等价数据已经持久化；价格引用同时要求 `available_at` 和 `collected_at`
不晚于评价截止时间。修改前后比较全部旧成熟 label hash，重复运行成熟 0。

2026-07-28 12:00 左右实际执行了一次默认 dry-run。服务在读取或修改标签前返回
`current trading day has not completed; labels remain PENDING`，没有数据库写入。随后只读
复核仍为：

```text
1D/5D/10D CALCULATED=250/250/250
20D CALCULATED/PENDING=240/10
```

生产观察脚本要求同日 15:00 后 cutoff、exact-date READY MarketContext、五个 READY
TradingStatus 和现有 USER_SELECTED candidates。它依次调用现有 DataQuality、
EvidenceSnapshot、Factor/Regime/Strategy；只有真实 TRIGGERED 才进入现有 DecisionPipeline。
无 TRIGGERED 时对正式 Outbox、Intent、Order、Fill、Account、Position、Lot、
Reservation、Ledger、Settlement、DailyAccountSnapshot 的 count + content hash 做前后
比较。

### 16.4 测试隔离

根 `pytest.ini` 和 `conftest.py` 增加显式 suite：

```text
offline（默认）
unit
integration
network
interactive
manual
legacy_collection_error
all
```

默认 offline 通过 collection-time 精确文件清单隔离实时网络/交互/人工脚本，仍保留安全
测试和确定性 integration，并在进程级阻断 INET socket 与 `input()`。默认入口现在只包含
已审计的 AlphaGuard unit/integration；未经逐文件审计的旧顶层 debug、Provider 和本机
服务脚本保留在显式 `manual/network/interactive` 边界。当前默认离线入口为
`465 passed, 89 warnings`。显式 `legacy_collection_error` 入口准确复现 14 个当前存量
导入错误，没有删除、吞错或全局 skip；该旧入口自身可能执行旧模块的本机 Mongo 初始化，
所以不属于默认离线 CI。

生产数据与测试边界专项为 `10 passed`；PR-001～PR-009 加本阶段新增测试的完整
AlphaGuard 精确回归即上述 `465 passed`。本阶段没有修改 Factor、Regime、
Strategy、Prompt、模型、Consensus、HardRisk、Matching、Fee 或 Champion；未新增股票、
未激活 PAPER_CHALLENGER、未创建真实订单、未开始 PR-010。

### 16.5 运行态、安全与资产核验

2026-07-28 12:07～12:11 的只读核验：

```text
Docker backend / queue-worker / analysis-worker / MongoDB / Redis=healthy
AlphaGuard required indexes missing=0（production data indexes=18）
queue-worker heartbeat TTL=13s
analysis-worker heartbeat TTL=42s
FastAPI live=true=exit 3
queue-worker live=true=exit 1
analysis-worker live=true=exit 1
三个正式自动账户=ACTIVE，initial/available=1000000.00，reserved=0
Position/Order/Fill/Reservation/Ledger/Settlement=0
每账户 DailyAccountSnapshot=1
Snapshot/Proposal/Outbox/Intent/Order/Fill duplicate identity=0
正式 ag_quant_proposals=2；Outbox/Intent/Order/Fill=0
```

Operations 实际为 `DEGRADED_PAPER`：

```text
CODE_COMPLETE=true
RUNTIME_READY=true
DATA_READY=false
PAPER_READY=true
EVALUATION_READY=true
LIVE_READY=false
blocking=MARKET_CONTEXT_CURRENT_VERSION_MISSING
```

另外两个既有非本阶段阻断仍为 `EXPERIMENT_SAMPLES_EMPTY` 和
`FULL_CHALLENGER_PIPELINE_NOT_READY`；本阶段按要求不补 Challenger。最近日志中的
Tushare token 错误是已知 Provider 不可用，没有被当成空数据或成功同步。

### 16.6 幂等缺陷修复

- Production MarketContext 重复运行现在复用首次保存的 `available_at/collected_at`；
  同一版本、同一内容即使执行时钟变化仍返回 `REUSED`，内容变化仍
  `INTEGRITY_CONFLICT`。
- security master 目标为 `UNCHANGED` 时不再刷新 `updated_at`，完全跳过目标 upsert；
  历史审计源和现有生产记录均未删除或重写。
- ExecutionMarketSnapshot 与剩余标签成熟都同时检查 `available_at` 和
  `collected_at`，不能用声明时间早于真实采集时间的记录绕过 cutoff。

### 16.7 当前未完成条件

- 2026-07-27 原独立同步进程已完成 5201/5201 全市场记录，但 v1
  `collected_at=2026-07-28 11:44` 晚于声明的 `available_at=2026-07-27 15:00`；
  该行保留为审计、消费者拒绝，未重复同步；
- 后续 policy/normalization/calculation 已升级为 v1.1，要求
  `available_at=max(close, collected_at)`；当前 v1.1 生产记录为 0；
- 2026-07-28 尚未收盘，正式 QFQ 不能入库，十条 20D 不能提前成熟；
- 同理，2026-07-28 五标的新 Snapshot/Regime/Proposal 尚不能运行；
- 因这些真实时间/数据条件，当前 `DATA_READY` 和 `LIVE_READY` 不能人工改为 true。

### 16.8 当前 Git 状态

```text
HEAD=aae0d371604a585cdf01693b541b0a1e82d5b6ce
tag=alphaguard-historical-backfill-v1
historical checkpoint=clean and independently committed
Production Data Completion changes=working tree, not committed
```

当前阶段尚未形成完成检查点：2026-07-28 正式收盘数据和 current v1.1
MarketContext 均未满足，不能把“代码可运行”冒充为“生产数据完成”。工作区差异只包含本
阶段生产数据接入、时序/幂等缺陷修复、测试边界与四份要求文档；没有回滚或重做历史
检查点。

## 17. Production Data Completion & Live Observation（完成）

本节取代 16.7/16.8 的盘中状态。本阶段仍不是 PR-010；没有修改 Factor、Regime、
Strategy、Prompt、模型、Consensus、HardRisk、Matching、Fee 或 Champion。

### 17.1 AKShare 日线回退与正式增量

新增统一 `DailyPriceProviderRegistry / DailyPriceProviderResolver`，Provider 声明能力、
底层来源、版本、RAW/QFQ/index、volume/amount、更新时间和网络属性。实现：

- BaoStock `query_history_k_data_plus`；
- AKShare/Eastmoney `stock_zh_a_hist`、`index_zh_a_hist`；
- AKShare/Tencent `stock_zh_a_hist_tx`。

Provider 网络对象不能进入 Snapshot；只有规范化、交叉验证、持久化及本地 gate 后才可
使用。成交量统一为股，成交额统一为 CNY；原始 source identity、response hash、
validation refs、Provider update time 和 content hash 全部保留。

2026-07-24 能力验证：BaoStock 与本地控制记录一致；Tencent 的股票 RAW/QFQ 经单位和
Decimal 量化后在 v1 容差内，沪深300有 0.0013～0.0035 点精度差；Eastmoney 当次远端
断连。2026-07-28 精确探测中 BaoStock 与 Tencent 对六个标的都返回完整正式日线，
Eastmoney ERROR。最终选择 BaoStock，`fallback_reason=null`；Tencent 只作为
validation ref。Provider 自身更新时间均不可得，按事实保存 null。

只新增 2026-07-28 六条 `stock_daily_quotes`。五股各有明确 RAW 和 QFQ version；沪深300
为 `INDEX_UNADJUSTED_EQUIVALENT`。首次写入后同步复跑全部 REUSED，同身份不同 hash 仍
抛 `INTEGRITY_CONFLICT`，禁止 upsert 覆盖。

### 17.2 交易状态与 Production MarketContext

五个 `ag_security_trading_statuses` 全部 READY：000333/002594 为深主板10%，
300750 为创业板20%，600519/601318 为沪主板10%；全部非ST、非停牌、tick 0.01、lot
100。上市初期、ST、科创板、北交所、退市整理和无价格限制分支均由版本化规则处理，不可
判断时仍 INSUFFICIENT_DATA。

2026-07-28 Production MarketContext v1.1：

```text
context_id=10b1f30f-60d8-5798-bc9c-0c9f11685cd1
provider=AKShare/Tencent 1.18.78
universe provider=BaoStock 00.9.30
source/expected=5193/5201
coverage universe/high-low/sector=0.998462/0.999230/1
advance/decline/unchanged=2365/2681/147
new_high/new_low=268/458
industry_diffusion=0.3
benchmark close/MA20/MA60=4569.5235/4743.523775/4838.2949667
volatility20=0.2950825816
status=READY
```

使用当日实际 A股 universe、120日 Tencent 日线、十个行业指数和持久化沪深300序列；
没有读写 `ag_research_*`，没有用五只候选或0填充缺失。跨执行时刻复跑为 source/context
REUSED。

### 17.3 20D、生产观察与资产

Canonical run 的 20D DECISION_CLOSE 仍为 240 CALCULATED / 10 PENDING。十条到期记录
需要跨 `candidate-real-data-v1` 与 `daily-price-normalization-v1` 两个 QFQ version；
AdjustedPriceResolver 按既有规则拒绝混合。一次不完整计算的十条记录由严格 lineage、
状态、空 refs 和 input-hash CAS 恢复为 PENDING；240条 CALCULATED 未修改。最终 dry-run
成熟0、blocker全部为 `VERSION_LOCKED_QFQ_SERIES_UNAVAILABLE`。

五个 2026-07-28 Candidate：

```text
DataQuality PASS=5
EvidenceSnapshot=5（integrity=5）
FactorResult=105
RegimeResult=5（INSUFFICIENT_DATA=5）
QuantProposal=10（REJECTED=5, INSUFFICIENT_DATA=5）
EvaluationSubject=10
TRIGGERED=0
```

不可变 Snapshot 只锁定新增 version 的当日 benchmark ref，现有 RegimeEngine 需要61条
close，因此正确返回 `missing:benchmark_prices.close[61]`，没有默认 RANGE_WEAK。无
TRIGGERED，所以 Normal/Top/Consensus/HardRisk 没有被调用，也没有 Intent/Outbox。

正式 Outbox、Intent、Order、Fill、Position、Lot、Reservation、Ledger、Settlement 全部
为0；三账户各 cash_available=1000000.00、cash_reserved=0、无费用和PnL变化。前后
content hash 相同；Snapshot/Factor/Regime/Proposal/EvaluationSubject 重复身份为0。

### 17.4 测试、运行态和 Readiness

```text
默认离线 CI=490 passed, 89 warnings
Production data + provider 专项=33 passed
修改 Python 编译=passed
git diff --check=passed
Operations integrity=PASS
MongoDB/Redis/Scheduler=HEALTHY
backend/queue-worker/analysis-worker=HEALTHY
queue/analysis heartbeat TTL=13/41
FastAPI/queue-worker/analysis-worker live=true=全部非零退出
required indexes missing=0
```

Readiness：

```text
CODE_COMPLETE=true
RUNTIME_READY=true
DATA_READY=true
PAPER_READY=true
EVALUATION_READY=true
EXPERIMENT_READY=true
CHALLENGER_READY=false
LIVE_READY=false
overall=DEGRADED_PAPER
```

Operations 过去使用 UTC-naive `now` 比较 CN-market-naive available_at，误把收盘后记录
判为未来；现统一使用 `Asia/Shanghai` wall clock，不降低时序门禁。QFQ/RAW coverage
不再被任意5000行读取上限截断。`INDUSTRY_HISTORY` 仍为 PARTIAL/CURRENT_ONLY，只用于
归因且缺失时保持 null；CLI 不再把这个非生产链硬依赖混入 DATA_READY。

### 17.5 实际文件范围与回退

新增 production data schemas/collections、daily Provider/Resolver、增量价格、Security
Master、交易状态、MarketContext、标签成熟与观察服务；新增对应 dry-run-first 脚本、
版本化 YAML、create-only 索引、离线/网络测试边界和专项测试。修改仅涉及现有数据解析、
执行快照时序门禁、Operations readiness、Decimal canonical 化、历史报告只读统计和本节
四份文档。

回退代码使用本阶段独立提交的父提交；数据库对象不通配删除。若需回退，按
trade_date=2026-07-28、精确 ref/context/status/snapshot ID 先做引用审计；EvidenceSnapshot、
Factor、Regime、Proposal 和 EvaluationSubject 已形成 lineage，应默认保留。正式交易
集合和账户无需资产回滚，因为本阶段没有资产变化。

已知限制：十条20D仍因版本连续性保持PENDING；五个当日 Regime 因不可变 Snapshot 的
benchmark version seam 保持 INSUFFICIENT_DATA；历史行业映射 current-only；Eastmoney
接口当次断连；Provider 自身更新时间不可得；Challenger 与 live 继续关闭。未开始
PR-010。

## 18. Production History Continuity & Observation Phase 2（完成）

本阶段不是 PR-010，没有修改 Factor、Regime、Strategy、Prompt、模型、Consensus、
HardRisk、Matching、Fee、Champion 或交易参数。

### 18.1 Production MarketContext 历史

使用持久化 CN 交易日历选定 2026-07-28 之前 120 个开市日
（2026-01-26～2026-07-27），由正式 BaoStock 历史 Universe、
AKShare/Tencent 日线、十个行业指数和持久化沪深300重新构建：

```text
history normalization=alphaguard-production-market-context-history-v1.1
calculation=production-market-context-calculation-v1.1
READY=120/120
首次 CREATED source/context=120/120
跨执行时刻复跑 REUSED source/context=120/120
duplicate identity=0
provider failure=0
```

历史 Universe 单日覆盖率为 0.9903846154～0.9994230769，新高/新低最低覆盖率
0.9974942174，行业覆盖率 1。没有读取或复制 `ag_research_*`，没有覆盖 2026-07-28
current v1.1 Context。历史记录的 `available_at/collected_at` 保存真实补采时刻。

### 18.2 Regime 与不可变对象

MarketRegime 实际最长强制窗口为 61 根沪深300 close；MarketContext 同时强制当日市场
宽度和行业扩散度。历史 Context 已完整，因此
`MARKET_CONTEXT_HISTORY_READY=true`。

五个既有 2026-07-28 Snapshot 不能回填新引用。按 Snapshot 锁定 Champion 配置执行纯
内存复核，5/5 的 result ID 与 input hash 不变，仍因只有一根锁定基准价格而
`INSUFFICIENT_DATA`，故 `REGIME_READY=false`。没有覆盖 RegimeResult、重跑 Proposal 或
调用模型链。

一次早期复核误用了默认 Regime 配置并创建 5 条无引用的
`INSUFFICIENT_DATA` 结果。精确引用审计确认下游引用为 0 后，只删除该 5 个 ID并恢复原始
5 条结果；随后新增 Snapshot 锁定版本的无持久化复核入口和防回归测试。资产与正式交易
对象未受影响。

### 18.3 20D 连续性

Canonical run 的 10 条 PENDING 20D 标签在 2026-07-28 出现 QFQ version seam。窗口没有
缺少交易日，但现有 Repository 不支持同一 symbol/date 并列第二版本而不产生查询歧义。
采用安全方案B：

```text
20D DECISION_CLOSE CALCULATED=240（未修改）
20D DECISION_CLOSE PENDING=10
blocker=VERSION_LOCKED_QFQ_SERIES_UNAVAILABLE
跨版本拼接=0
```

### 18.4 完整性、测试和 Readiness

正式 Intent/Outbox/Order/Fill/Position/Lot/Reservation/Ledger/Settlement 均为0；
三个账户各 cash_available=1,000,000 CNY、cash_reserved=0。候选、Snapshot、Factor、
Regime、Proposal、EvaluationSubject、HorizonLabel 的真实身份重复组均为0；生产对象
引用研究 lineage 为0；无负资产、死信、卡住 Settlement/Promotion Saga。

```text
新增连续性+生产数据测试=22 passed, 84 warnings
默认离线CI=497 passed, 89 warnings
Python编译/git diff --check/敏感信息扫描=passed
MongoDB/Redis/Scheduler/FastAPI/两套Worker=HEALTHY
三个入口 live=true=全部拒绝启动
```

Readiness 仍由现有报告计算：

```text
CODE_COMPLETE=true
RUNTIME_READY=true
DATA_READY=true
PAPER_READY=true
EVALUATION_READY=true
EXPERIMENT_READY=true
CHALLENGER_READY=false
LIVE_READY=false
overall=DEGRADED_PAPER
```

下一持久化开市日为 2026-07-29；完成时尚无该日完整收盘数据，因此未运行下一日观察链。
回退代码使用本阶段提交的父提交；数据库历史证据默认保留，若需移除必须先做引用审计，
并仅按历史 normalization 和精确日期范围处理。未开始 PR-010。

## 19. Frontend Product Acceptance & Guided Demo（完成）

本阶段只完成前端产品验收、只读演示环境和用户文档，没有修改 Factor、Regime、Strategy、
Prompt、模型、Consensus、HardRisk、Matching、Fee、Champion 或任何交易参数。完成检查点为
本节所在提交，标签 `alphaguard-frontend-acceptance-v1`，父检查点为
`alphaguard-production-history-v1`（`6bea71e`）。

### 19.1 真实环境与隔离演示

真实前端/API 继续使用 `http://localhost:3000` 和 `http://localhost:8000`。新增独立演示
API `http://127.0.0.1:8010` 与前端 `http://localhost:3001`；演示 API 只允许数据库
`alphaguard_ui_demo`、显式 database scope 和 `ALPHAGUARD_UI_DEMO=true`，并同时关闭旧
ConfigManager Mongo storage、Scheduler、Worker、backfill 和 live execution。

演示数据库只有集合 `ag_ui_demo_scenarios` 和一条确定性不可变 fixture；页面永久显示
`DEMO ENVIRONMENT`，写操作、晋升和回退入口均禁用。演示覆盖 DataQuality FAIL、WATCH、
Top 拒绝、HardRisk 拒绝、完整 OrderIntent、T+1 Fill/PositionLot/费用、成熟评价、泄漏
失败和晋升样本不足十个场景。演示 OrderIntent、Fill、收益及实验结果不属于正式生产数据。

### 19.2 页面和浏览器验收

实际浏览器逐页验证总览、候选池、决策链、自动模拟、评价中心、实验室和运维中心；同时
验证登录/退出、未认证路由重定向、候选详情、阶段详情、三个账户切换、T+1 lot、费用、
评价筛选、实验泄漏失败、禁用写操作、告警、404 和 API 不可用提示。决策时间线明确区分
`NOT_REACHED`、`INSUFFICIENT_DATA`、`MODEL_FAILED`、拒绝和通过，不再把未到达状态补成
HOLD/PASS。总览将 `DEGRADED_PAPER` 解释为部分能力安全关闭，而不是系统崩溃。

12 张实际浏览器截图保存在 `docs/ux/screenshots/`，均为真实 PNG，不含密码、Token、
Cookie、Authorization 或管理员邮箱。真实生产登录密码未被读取、重置、记录或自动化输入。
用户已完成实际产品体验并接受当前页面和业务流程。

### 19.3 测试、隔离和资产

```text
默认离线CI=505 passed, 89 warnings
AlphaGuard前端/API/安全专项=55 passed, 85 warnings
Demo隔离测试=8 passed, 85 warnings
Python编译=passed
独立Vite生产bundle=passed（2610 modules，50.82s）
git diff --check=passed
敏感信息扫描=passed
```

`npm run type-check` 和正式 `npm run build` 仍准确报告 34 个存量 `DefaultRow TS2345` 并
以 exit 2 结束；错误只位于未触达的 Dashboard、Favorites、Reports、Screening、Settings
和 System 页面。本阶段 AlphaGuard、认证、API 与 Demo 新增/修改文件类型错误为0。没有
关闭 TypeScript 检查，也没有使用全局 `any` 消除基线。

演示运行前后生产数据保持：Candidate=5、EvidenceSnapshot=6、QuantProposal=12、
EvaluationSubject=762，OrderIntent/Outbox/Order/Fill/Position/Lot/Reservation/Ledger 全部为0。
三个自动模拟账户各 initial/cash_available=1,000,000.00 CNY、cash_reserved=0，资产守恒。
Demo 数据库只有一条 fixture，未写入任何生产集合。

FastAPI、MongoDB、Redis、Scheduler、queue-worker 和 analysis-worker 均健康，两个 Worker
heartbeat TTL 为13/31秒。将 `ALPHAGUARD_LIVE_TRADING_ENABLED=true` 后，FastAPI、
queue-worker、analysis-worker 分别以 exit 3/1/1 拒绝启动。

### 19.4 Readiness 与已知限制

```text
CODE_COMPLETE=true
RUNTIME_READY=true
DATA_READY=true
PAPER_READY=true
EVALUATION_READY=true
EXPERIMENT_READY=true
CHALLENGER_READY=false
LIVE_READY=false
overall=DEGRADED_PAPER
blocking=EXPERIMENT_SAMPLES_EMPTY,FULL_CHALLENGER_PIPELINE_NOT_READY
```

已知限制仅按事实保留：正式 `npm run build` 仍被34个存量类型错误阻断；真实环境没有完整
Normal→Top→Consensus→HardRisk→Order→Fill案例，因此完整流程只在明确隔离的 Demo 展示；
Challenger 与 live 继续关闭。本阶段未开始 PR-010。

## 20. Frontend Type Safety Cleanup（完成）

本阶段从 `alphaguard-frontend-acceptance-v1`（`a0d7434`）开始，只清理旧前端表格的
`DefaultRow TS2345`。没有新增业务功能，没有修改路由、API 地址、认证、权限、数据来源、
排序、筛选、分页、交易逻辑、后端 Schema、交易参数或 Champion。

### 20.1 精确基线和根因

开始时 `npm run type-check` 与正式 `npm run build` 均以 exit 2 返回下列34个错误；
独立 `npx vite build` 当时可以通过，但不作为正式构建成功：

| 文件 | 基线行号 | 数量 | 表格 data 的实际类型 | 处理函数期望类型 | 根因 |
| --- | --- | ---: | --- | --- | --- |
| `Dashboard/index.vue` | 125, 132 | 2 | `AnalysisTask[]` | `AnalysisTask` | Element Plus slot 推断为 `DefaultRow` |
| `Favorites/index.vue` | 191 | 1 | `FavoriteItem[]` | `FavoriteItem` | 同上 |
| `Reports/index.vue` | 79, 130, 136, 161 | 4 | `ReportListItem[]` | `ReportListItem` | 同上 |
| `Reports/TokenStatistics.vue` | 217 | 1 | `TokenRecord[]` | `TokenRecord` | 同上 |
| `Screening/index.vue` | 250, 322, 325 | 3 | `StockInfo[]` | `StockInfo` | 同上 |
| `Settings/components/MarketCategoryManagement.vue` | 50, 57, 64 | 3 | `MarketCategory[]` | `MarketCategory` | 同上 |
| `Settings/ConfigManagement.vue` | 165, 173, 181, 188 | 4 | `LLMProvider[]` | `LLMProvider` | 同上 |
| `Settings/ConfigManagement.vue` | 348, 354, 361, 368 | 4 | `LLMConfig[]` | `LLMConfig` | 同上 |
| `Settings/ConfigManagement.vue` | 493, 494 | 2 | `DatabaseConfig[]` | `DatabaseConfig` | 同上 |
| `System/LogManagement.vue` | 76, 79, 84 | 3 | `LogFileInfo[]` | `LogFileInfo` | 同上 |
| `System/SchedulerManagement.vue` | 148, 157, 167, 176, 184 | 5 | `Job[]` | `Job` | 同上 |
| `System/SchedulerManagement.vue` | 337, 470 | 2 | executions 响应 / `JobExecution[]` | `JobExecution` | slot 为 `DefaultRow`；手动历史另被错误标成 `JobHistory[]` |

Element Plus 2.4.4 的 table slot 声明将 `scope.row` 暴露为
`DefaultRow = Record<PropertyKey, any>`，不会从强类型 `data` 反推页面 DTO。因此即使页面的
`ref` / `computed` 已经是明确数组类型，直接把 slot row 传给强类型函数仍会产生 TS2345。
这不是后端字段变化。

### 20.2 修复方式和文件

新增 `frontend/src/utils/tableRows.ts`。`invokeTableRowAction` 只有在 slot row 与当前表格
强类型 data 数组中的对象满足引用身份相等时才调用处理函数；该检查构成运行时类型证明，
不使用 `any`、`as any`、`unknown as T`、`ts-ignore` 或类型配置降级。合法 Element Plus
行仍按原事件、原参数和原顺序执行，外来行安全不调用。

九个旧页面只将34个受影响的事件入口接到该守卫。Scheduler 的手动历史实际读取
`getJobExecutions` / `getSingleJobExecutions`，返回和展示的字段均为 `JobExecution`；
页面局部列表改为 `JobExecution[]` 并删除原先扩展对象后强制伪装成 `JobHistory` 的断言。
没有修改 `frontend/src/api/scheduler.ts` 或后端 Scheduler Schema。

实际代码修改范围：

```text
frontend/src/utils/tableRows.ts
frontend/src/views/Dashboard/index.vue
frontend/src/views/Favorites/index.vue
frontend/src/views/Reports/index.vue
frontend/src/views/Reports/TokenStatistics.vue
frontend/src/views/Screening/index.vue
frontend/src/views/Settings/components/MarketCategoryManagement.vue
frontend/src/views/Settings/ConfigManagement.vue
frontend/src/views/System/LogManagement.vue
frontend/src/views/System/SchedulerManagement.vue
```

### 20.3 构建、回归和浏览器结果

```text
npm run type-check=PASS（DefaultRow TS2345 34→0，其他错误0）
npm run build=PASS（vue-tsc + Vite）
npx vite build=PASS
AlphaGuard前端/API/安全专项=55 passed, 85 warnings
Demo隔离测试=8 passed, 85 warnings
默认离线CI=505 passed, 89 warnings
```

浏览器实际检查正式登录页及未认证路由重定向；隔离 Demo 中受影响的旧 Dashboard 正常
打开，表格、空状态和操作按钮可见，无无限 loading、字面 `undefined` 或行处理
`TypeError`。该旧页请求 Demo 未实现的 legacy API 时仍按既定边界返回404，不属于新增
错误。AlphaGuard Overview、Candidates、Decisions、Paper、Evaluations、Experiments、
Operations 均完成加载，短暂 loading 正常消失，控制台新增错误为0，Demo Overview 永久
显示 `DEMO ENVIRONMENT`。未自动读取或输入正式环境密码。

### 20.4 隔离、安全和 Readiness

只读核验保持：

```text
生产 Candidate=5
生产 EvidenceSnapshot=6
生产 QuantProposal=12
生产 EvaluationSubject=762
生产 OrderIntent/Outbox/Order/Fill/Position/Lot/Reservation/Ledger=0
三个正式自动账户 initial/cash_available=1000000.00，cash_reserved=0
Demo 数据库集合=ag_ui_demo_scenarios，记录=1
Docker FastAPI/MongoDB/Redis/queue-worker/analysis-worker=healthy
FastAPI live=true=exit 3
queue-worker live=true=exit 1
analysis-worker live=true=exit 1
```

最终 Readiness 仍由现有服务计算：

```text
CODE_COMPLETE=true
RUNTIME_READY=true
DATA_READY=true
PAPER_READY=true
EVALUATION_READY=true
EXPERIMENT_READY=true
CHALLENGER_READY=false
LIVE_READY=false
overall=DEGRADED_PAPER
blocking=EXPERIMENT_SAMPLES_EMPTY,FULL_CHALLENGER_PIPELINE_NOT_READY
```

业务显示和操作行为未改变。本阶段没有运行2026-07-29生产观察链，也没有开始 PR-010。

## 21. First Complete Production Decision Cycle（完成）

本阶段从 `alphaguard-frontend-type-safe`（`959104f`）开始，只执行2026-07-29正式收盘
数据门禁、增量生产数据、不可变 MarketContext 窗口、正式观察链和完整性验证。没有重新
初始化账户、Champion 或索引，没有重跑历史回放，也没有修改 Factor、Strategy、模型、
Prompt、Consensus、HardRisk、Matching、Fee、交易参数或 Champion。

### 21.1 收盘门禁、行情和交易状态

持久化交易日历确认 `CN / 2026-07-29 / is_open=true`。只读 Provider 探测在收盘后通过：
600519、601318、000333、002594、300750 和000300均由 BaoStock 00.9.30 的正式历史日线
接口返回精确2026-07-29数据；AKShare/Eastmoney 与 AKShare/Tencent只作交叉验证。所有
主记录均具备合法 OHLC、非缺失 volume/amount、明确 RAW/QFQ 版本、来源身份、采集时间和
稳定 content hash，不是盘中快照、分钟线聚合、前一交易日替代或测试数据。

增量同步只新增6条 `stock_daily_quotes`，没有覆盖旧记录。五只股票保存独立 RAW 与 QFQ
版本；000300按既有指数无复权等价模式保存。重复身份执行遵循相同内容 `REUSED`、不同内容
`INTEGRITY_CONFLICT`。五只股票新增5条版本化交易状态：

```text
000333 previous_close=85.37 upper/lower=93.91/76.83 SZSE_MAIN NORMAL_10
002594 previous_close=93.35 upper/lower=102.69/84.02 SZSE_MAIN NORMAL_10
300750 previous_close=390.86 upper/lower=469.03/312.69 CHINEXT NORMAL_20
600519 previous_close=1320.00 upper/lower=1452.00/1188.00 SSE_MAIN NORMAL_10
601318 previous_close=54.20 upper/lower=59.62/48.78 SSE_MAIN NORMAL_10
```

五只股票均为非ST、非停牌、非无涨跌幅限制特殊日，tick size=0.01、lot size=100。主板
10%与创业板20%按既有版本化规则分别计算，没有统一套用10%。

### 21.2 Production MarketContext 和不可变历史窗口

Production MarketContext v1.1基于5,201只正式全市场日线及10个行业指数生成，未使用五只
候选代表市场，也未复制研究对象或以0填充缺失值：

```text
context_id=141788c5-6496-5d1e-a99d-8ebc64337efe
trade_date=2026-07-29
benchmark_close=4600.2624
benchmark_ma20=4725.588030
benchmark_ma60=4834.844225
benchmark_ma20_slope=-0.0156666
benchmark_volatility_20d=0.2975646
market_amount=2295838601573.85
advance/decline/unchanged=3967/1173/61
market_breadth=0.5435798
new_high/new_low=604/479
industry_diffusion=0.8
extreme_risk=false
universe_coverage=1
missing_fields=[]
quality_status=READY
content_hash=891a9d1df22db2966800b49eb35795d3023712478778c8f5b8f15c7f24590e3a
```

新增 create-only `MarketContextWindowManifest` 和服务，锁定121个连续开市日的生产
MarketContext（120个历史输入加当日）：

```text
manifest_id=965c1bc0-b78e-5f2a-a946-06e130d50561
window=2026-01-27..2026-07-29
required_count=121
actual_count=121
context_version=production-market-context-calculation-v1.1
manifest_hash=d286c5165100c4c4936a02f05f644221084ea285e1ecaacd2210fc416c4d2c36
```

Manifest只引用生产集合，按日期、context id和content hash有序锁定；未来日期、日期断点、
歧义身份、版本不兼容或数量不足均返回 `REGIME_INPUT_NOT_READY`。dry-run不写库，首次
execute为 `CREATED`，相同输入复跑为 `REUSED`；不在运行时用“最新120根”替代Manifest。
Production MarketContext本身也完成跨执行时刻的正式Provider复跑：全市场5,201/5,201、
行业指数10/10、失败0，source和context两层均返回 `REUSED`。一次额外只读会话曾阻塞在
BaoStock socket并被安全终止，未进入写路径；新会话完整复跑后通过，不影响正式对象。

### 21.3 Snapshot、Factor、Regime 和 Proposal

五只候选DataQuality均为PASS，各创建1个2026-07-29正式EvidenceSnapshot；Snapshot锁定
RAW/QFQ、财务披露、新闻、公告、交易状态、涨跌停、当日MarketContext、窗口Manifest、
Champion集合、数据版本、cutoff和immutable hash。幂等复跑复用同一Snapshot身份，没有
覆盖2026-07-28或研究对象。

每只Snapshot生成21个FactorResult，共105个，其中15个有效、90个因已锁定输入不足保持
缺失/UNKNOWN。五个RegimeResult均安全返回 `INSUFFICIENT_DATA`：当前Snapshot只锁定2个
基准价格引用，而既有MarketRegimeEngine要求61个
`benchmark_prices.close`。窗口Manifest本身完整且版本兼容，但不能替代Engine明确要求的
基准价格序列，因此：

```text
REGIME_READY=false
missing=benchmark_prices.close[61]
actual locked benchmark refs=2
```

没有修改Regime规则或为完成演示追加第二Snapshot身份。既有Strategy仍为每只候选生成
2个QuantProposal，共10个：

```text
POSITION_EXIT_V1 REJECTED=5
SWING_TREND_PULLBACK_V1 INSUFFICIENT_DATA=5
TRIGGERED=0
```

由于没有自然产生TRIGGERED，NormalTradePlan、TopReview、Consensus和HardRisk均未调用；
OrderIntent、ExecutionOutbox、Order和Fill保持0。这是合法安全结果，不需要下一交易日
撮合验证。

### 21.4 Evaluation、幂等和生产完整性

新增10个QUANT_PROPOSAL EvaluationSubject，并按既有服务为1D/5D/10D/20D各创建10个
`PENDING` HorizonLabel，共40个；没有读取未来行情。历史canonical run的10个
`PENDING_VERSION_DISCONTINUITY` 20D标签保持不变，未跨QFQ版本拼接。

dry-run前后19个相关集合计数完全一致。正式复跑复用五个Snapshot、相同Proposal和Subject
身份，HorizonLabel不增长；Quote、交易状态、MarketContext和Manifest均使用create-only
身份与内容哈希，未发生静默覆盖。重复身份聚合为0，生产Snapshot引用研究集合为0，没有
未来数据泄漏、死信、卡住Saga、负现金、负持仓、异常冻结或账本失衡。

三个自动模拟账户保持：

```text
PAPER_QUANT initial/cash_available=1000000.00 cash_reserved=0
PAPER_NORMAL initial/cash_available=1000000.00 cash_reserved=0
PAPER_TOP_CONFIRMED initial/cash_available=1000000.00 cash_reserved=0
```

### 21.5 测试、健康和 Readiness

```text
本阶段新增测试=4 passed
默认离线CI=509 passed, 89 warnings
PR-001～PR-009及AlphaGuard精确回归=506 passed, 89 warnings
Production Data/History/MarketContext Window专项=25 passed
Regime/Evaluation/Paper专项=54 passed, 85 warnings
frontend type-check=PASS
正式 npm run build=PASS
npx vite build=PASS
Python编译=PASS
MongoDB/Redis/Scheduler/FastAPI/queue-worker/analysis-worker=HEALTHY
FastAPI live=true=exit 3
queue-worker live=true=exit 1
analysis-worker live=true=exit 1
```

最终Readiness继续由现有服务计算：

```text
CODE_COMPLETE=true
RUNTIME_READY=true
DATA_READY=true
PAPER_READY=true
EVALUATION_READY=true
EXPERIMENT_READY=true
CHALLENGER_READY=false
LIVE_READY=false
overall=DEGRADED_PAPER
blocking=EXPERIMENT_SAMPLES_EMPTY,FULL_CHALLENGER_PIPELINE_NOT_READY
```

已知限制：本阶段得到明确、安全、可审计的Regime输入不足结果，尚无真实
Normal→Top→Consensus→HardRisk生产案例，也没有订单需要下一交易日撮合。完整生产决策
周期验证完成到合法安全终点；未开始PR-010。
