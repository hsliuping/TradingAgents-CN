# AlphaGuard Codex Execution Status

## 当前状态

- 更新时间：2026-07-26 21:00 CST（Asia/Shanghai）
- 当前阶段：PR-006 Automatic Paper Trading
- 阶段状态：实现完成，验证完成
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
- 后续阶段：PR-007 及以后均未开始
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
