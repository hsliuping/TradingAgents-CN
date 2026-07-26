# AlphaGuard Codex Execution Status

## 当前状态

- 更新时间：2026-07-26 12:42:36 CST（Asia/Shanghai）
- 当前阶段：PR-001 Baseline Guard
- 阶段状态：实现完成，验证完成
- 后续阶段：PR-002 及以后均未开始
- 固定安全模式：`system_mode=SIM_AUTONOMOUS`
- 实盘开关：`live_trading_enabled=false`
- 数据迁移：无
- 数据库 schema 变化：无
- 公开 API 变化：无

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

## 下一步闸门

PR-001 已完成。PR-002 未获本次任务授权，禁止继续实现；进入任何后续阶段前必须
重新确认范围、重新读取本状态文件，并重新建立阶段测试与回退计划。
