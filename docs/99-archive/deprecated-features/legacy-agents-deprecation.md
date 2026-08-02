# 旧版 Agent 引擎停用通知

> **状态**：已封堵（v3.0）  
> **计划删除**：v4.0  
> **生效日期**：2026-07-28

## 1. 背景与决策

### 1.1 双引擎并存问题

系统此前处于双引擎并存状态：

| 引擎 | 类 | 对应 Agent | 状态 |
|------|----|-----------|------|
| 新引擎 | `WorkflowEngine` | v2 agent（`risk_manager_v2`、`research_manager_v2`、`trader_v2`、`*_analyst_v2`） | ✅ 主推 |
| 旧引擎 | `TradingAgentsGraph` / `StockAnalysisEngine` | 旧版 agent（`risk_manager`、`research_manager`、`trader`、`market_analyst` 等） | ⚠️ 已封堵 |

**问题**：
- 开发时容易误改到旧版 agent（P0/P1/P2 改造只针对 v2）
- 前端不传 `engine` 参数时默认走 legacy 引擎
- 队列 Worker 的 else 分支会走到旧版

### 1.2 决策

**不删除旧版代码文件**（避免 import 错误），但把所有通往旧版 agent 的**执行入口**堵上（抛 `RuntimeError` 或 `HTTPException(400)`），让代码无法走到旧版。保留服务的管理功能（查询任务列表、状态等）。为 v4.0 彻底删除做准备。

**保留 `unified` 引擎**：`unified` 实际走 `UnifiedAnalysisService.analyze_stock` → `WorkflowEngine`，属于新引擎路径，不堵。

## 2. 废弃范围

### 2.1 废弃的引擎/类

- `tradingagents.graph.trading_graph.TradingAgentsGraph`
- `tradingagents.core.engine.stock_analysis_engine.StockAnalysisEngine`
- `core.workflow.builder._try_create_legacy_agent` 的 `factory_map`（13 个旧版 agent 工厂）

### 2.2 废弃的服务方法

| 文件 | 方法 | 改法 |
|------|------|------|
| `app/services/unified_analysis_engine.py` | `_select_engine` | 拒绝返回 `"legacy"`，抛 `RuntimeError` |
| `app/services/unified_analysis_engine.py` | `_execute_via_legacy` | 方法开头抛 `RuntimeError` |
| `app/services/simple_analysis_service.py` | `_get_trading_graph` | 方法开头抛 `RuntimeError` |
| `app/services/simple_analysis_service.py` | `execute_analysis_background` | 方法开头抛 `RuntimeError` |
| `app/services/simple_analysis_service.py` | `_execute_analysis_sync` | 方法开头抛 `RuntimeError` |
| `app/services/simple_analysis_service.py` | `_run_analysis_sync` | 方法开头抛 `RuntimeError` |
| `app/services/analysis_service.py` | `_get_trading_graph` | 方法开头抛 `RuntimeError` |
| `app/services/analysis_service.py` | `execute_analysis_task` | 方法开头抛 `RuntimeError` |
| `app/services/analysis_service.py` | `_execute_analysis_sync` | 方法开头抛 `RuntimeError` |
| `app/services/analysis_service.py` | `_execute_analysis_sync_with_progress` | 方法开头抛 `RuntimeError` |
| `app/services/thread_worker.py` | else 分支（engine 非 v2/unified） | 抛 `RuntimeError` |
| `app/services/portfolio_service.py` | `_get_stock_analysis_via_engine` | 方法开头抛 `RuntimeError`（死代码） |
| `app/services/portfolio_service.py` | `_get_stock_analysis_via_legacy` | 方法开头抛 `RuntimeError`（死代码） |
| `app/routers/analysis.py` | 单股/批量分析 legacy 分支 | 抛 `HTTPException(400)` |
| `app/routers/templates_debug.py` | v1 调试路径 | 抛 `HTTPException(400)` |
| `core/workflow/builder.py` | `_try_create_legacy_agent` | 返回 `None` + 警告日志 |

## 3. 保留的能力

以下功能**不受影响**，仍可正常使用：

### 3.1 服务管理功能
- `SimpleAnalysisService.create_analysis_task`（创建任务入队，不执行旧引擎）
- `SimpleAnalysisService.create_and_execute_analysis_v2`（已用 `UnifiedAnalysisEngine`）
- `SimpleAnalysisService.get_task_status`、`list_all_tasks`、`list_user_tasks`、`cancel_task`、`cleanup_zombie_tasks`
- `AnalysisService.submit_single_analysis`、`submit_batch_analysis`（仅创建任务）
- `AnalysisService.get_task_status`、`cancel_task`

### 3.2 新引擎路径
- `unified` 引擎（`UnifiedAnalysisService.analyze_stock` → `WorkflowEngine`）
- `v2` 引擎（`task_analysis_service` → `UnifiedAnalysisEngine` → `WorkflowEngine` + v2 agent）
- 交易复盘（`trade_review_service` → `WorkflowEngine`）
- 持仓分析 v2（`PortfolioService.analyze_position_by_code_v2` → `task_analysis_service`）

### 3.3 AnalysisEngine 枚举
- `AnalysisEngine.LEGACY` 枚举值**保留**（兼容旧客户端请求），但在路由层拦截返回 400 + 指引

## 4. 替代方案指引

| 场景 | 旧路径（已停用） | 新路径（请使用） |
|------|------------------|------------------|
| 单股分析 | `engine=legacy` → `TradingAgentsGraph` | `engine=v2`（默认）→ `task_analysis_service` → `WorkflowEngine` |
| 批量分析 | `engine=legacy` → `TradingAgentsGraph` | `engine=v2`（默认）→ `task_analysis_service` |
| 持仓分析 | `analyze_position_by_code` → `StockAnalysisEngine` | `analyze_position_by_code_v2` → `task_analysis_service` |
| 交易复盘 | — | `trade_review_service`（已用 `WorkflowEngine`） |
| Agent 调试 | `agent_version=v1` → `TradingAgentsGraph` | `agent_version=v2` → `WorkflowEngine` |

## 5. 回滚方案

每个堵点都在方法开头加了一行 `raise RuntimeError(...)` 或 `return None`，下方原代码保留（加 `# pragma: no cover`）。回滚时只需删除 raise 语句即可恢复，不影响原逻辑。

## 6. 时间线

| 阶段 | 版本 | 动作 |
|------|------|------|
| 封堵 | v3.0 | 所有入口抛错，旧版 agent 不再被调用 |
| 删除 | v4.0 | 整体删除 `TradingAgentsGraph`、`StockAnalysisEngine`、`_try_create_legacy_agent` 的 `factory_map`、旧版 agent 文件等 |

## 7. 验证方案

### 7.1 静态验证
```powershell
# 确认 AnalysisEngine.LEGACY 不再作为默认值
rg "AnalysisEngine\.LEGACY" app/routers/analysis.py
# 期望：仅在 raise/拒绝逻辑中出现

# 确认 _try_create_legacy_agent 返回 None
rg "_try_create_legacy_agent" core/workflow/builder.py
```

### 7.2 运行时验证
1. `.\start_dev.ps1 backend 3.0` 重启后端
2. 前端提交单股分析（不带 engine 参数）→ 应走 V2 引擎，日志无 `TradingAgentsGraph`
3. `curl` 调用 `POST /api/analysis/single` 传 `engine=legacy` → 返回 400
4. 持仓分析 → 走 `analyze_position_by_code_v2` → 成功
5. 交易复盘 → 成功（未受影响）
6. 后端日志搜索 `[已停用]`，确认无误触发
