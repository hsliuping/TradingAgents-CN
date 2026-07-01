# Git 分批提交方案（2026-07-01 全部改动）

## 前置说明

工作区共 **43 个修改文件** + **若干新增文件**（`workflows/` 目录、设计文档等），全部纳入以下 7 批 commit。

---

## Batch 1: Agent Builder LangGraph 工作流核心

**提交信息**：
```
feat: Agent Builder LangGraph 工作流核心实现

- 新增 workflows/ 目录：状态机图、节点、条件路由、状态定义、会话存储
- route_start 白名单覆盖所有 wait 节点 + evaluate_or_publish + error_recovery
- _is_confirm 增加"重跑""重测""再测"关键词
- 新增 wait_evaluation 节点：测试完成后等待用户决策发布/重测/修改/取消
- real_data_test → wait_evaluation（不再自动进发布），发不发布由人决定
- evaluate_or_publish 发布成功 → current_node = "wait_evaluation"
- 删除 6 个死函数：route_wait_* 系列、route_evaluate_or_publish、route_after_error
- agent_builder_flow.py: FlowPhase 新增值、工具映射、方案选择辅助函数
- intent_context.py: 意图上下文字段扩展
- agent/context.py: Agent 上下文构建增强
- agent/context_injection_policy.py: 新增上下文注入策略模块
- agent/tools/registry.py: 工具注册增强
- runtime.py: Agent Builder LangGraph feature flag、embedding 诊断日志
- nanobot_agent_builder_tools.py: 补充缺失的 import re
```

**文件**：

| 文件 | 状态 | 改动量 |
|---|---|---|
| `core/embedded_nanobot/workflows/agent_builder_graph.py` | 新增 | 图定义 + 边 + 条件边 |
| `core/embedded_nanobot/workflows/agent_builder_nodes.py` | 新增 | 15 个节点函数 |
| `core/embedded_nanobot/workflows/agent_builder_conditions.py` | 新增 | 路由条件 + fallback |
| `core/embedded_nanobot/workflows/agent_builder_state.py` | 新增 | TypedDict 状态 |
| `core/embedded_nanobot/workflows/agent_builder_store.py` | 新增 | 会话存储 |
| `core/embedded_nanobot/agent_builder_flow.py` | M | +349 |
| `core/embedded_nanobot/intent_context.py` | M | +35 |
| `core/embedded_nanobot/agent/context.py` | M | +165 |
| `core/embedded_nanobot/agent/context_injection_policy.py` | 新增 | 上下文注入策略 |
| `core/embedded_nanobot/agent/tools/registry.py` | M | +7 |
| `core/embedded_nanobot/runtime.py` | M | +586 |
| `core/tools/implementations/agent_builder/nanobot_agent_builder_tools.py` | M | +1002 |

---

## Batch 2: Agent Builder 服务层

**提交信息**：
```
feat: Agent Builder 服务层增强

- agent_workshop_service: gap_report 从 builder_contracts 恢复、acknowledged_gaps 支持、方案选择联动
- embedded_nanobot_service: thread_context 持久化日志、MongoDB fallback 恢复 intent
- capability_index_service: embedding 模型检查、初始化诊断
- routers/embedded_nanobot.py: API 路由增强
- schemas/embedded_nanobot.py: Schema 字段扩展
- memory/service.py: 记忆服务增强
- tools/context.py + loader.py + registry.py: 工具上下文/加载/注册增强
- frontend/src/api/embeddedNanobot.ts: API 类型扩展
```

**文件**：

| 文件 | 改动量 |
|---|---|
| `app/services/agent_workshop_service.py` | +244 |
| `app/services/embedded_nanobot_service.py` | +182 |
| `app/services/capability_index_service.py` | +46 |
| `app/routers/embedded_nanobot.py` | +32 |
| `app/schemas/embedded_nanobot.py` | +1 |
| `core/memory/service.py` | +27 |
| `core/tools/context.py` | +48 |
| `core/tools/loader.py` | +21 |
| `core/tools/registry.py` | +6 |
| `frontend/src/api/embeddedNanobot.ts` | +4 |

---

## Batch 3: 后端工具输出中文化

**提交信息**：
```
refactor: 工具输出字段中文化（用户可见部分）

- dividend_enhancement: valuation_signal (undervalued→低估, overvalued→高估, neutral→中性)
- dividend_enhancement: data_quality (sufficient→数据充足, limited→数据有限, insufficient→数据不足)
- cashflow_enhancement: surprise_category / overall_sentiment / data_quality 全部中文化
- dcf_valuation: method 中文化
- extended_valuation: method 中文化
```

**文件**：

| 文件 | 改动内容 |
|---|---|
| `core/tools/implementations/fundamentals/dividend_enhancement.py` | valuation_signal、data_quality 英→中 |
| `core/tools/implementations/fundamentals/cashflow_enhancement.py` | surprise_category、overall_sentiment、data_quality 英→中 |
| `core/tools/implementations/fundamentals/valuation/dcf_valuation.py` | method 英→中 |
| `core/tools/implementations/fundamentals/valuation/extended_valuation.py` | method 英→中 |

---

## Batch 4: 前端界面中文化

**提交信息**：
```
refactor: 前端用户可见文本中文化

- AgentWorkshop: Worker→执行器, tool-driven→工具驱动, not-run→未运行
- AgentStudio: Prompt Agent→提示词代理, Draft→草稿, Spec→规格, unknown→未知, universal→通用, System Prompt→系统提示词, User Prompt→用户提示词
- AgentWorkshopLanding: Agent Workshop→Agent 工坊, Assistant Mode→助手模式, Standard Flow→标准流程, Management→管理
- AgentDetail / Agents: license_tier 映射 (free→免费版, basic→基础版, pro→专业版, enterprise→企业版)
- SkillGeneration: unknown→未知
```

**文件**：

| 文件 | 改动内容 |
|---|---|
| `frontend/src/views/Workflow/AgentWorkshop.vue` | 标签/状态中文化 |
| `frontend/src/views/Workflow/AgentStudio.vue` | 标签/状态中文化 |
| `frontend/src/views/Workflow/AgentWorkshopLanding.vue` | 标题中文化 |
| `frontend/src/views/Workflow/AgentDetail.vue` | getLicenseLabel |
| `frontend/src/views/Workflow/Agents.vue` | getLicenseLabel |
| `frontend/src/views/Workflow/SkillGeneration.vue` | unknown→未知 |

---

## Batch 5: Baostock → Tushare 历史估值数据源

**提交信息**：
```
refactor: 历史估值分位数据源从 Baostock 迁移到 Tushare

- Baostock 连接不稳定（登录失败: WinError 10057）
- external_sources.get_external_valuation_data 改用 Tushare daily_basic
- tushare.py: 新增 get_daily_basic_batch_range，支持日期范围批量获取 PE_TTM/PB/PS_TTM/PCF_TTM
- get_historical_valuation_percentile_tool 不再返回 no_data
```

**文件**：

| 文件 | 改动内容 |
|---|---|
| `core/skill_runtime/external_sources.py` | get_external_valuation_data 切换到 Tushare |
| `tradingagents/dataflows/providers/china/tushare.py` | 新增 get_daily_basic_batch_range |
| `core/skill_runtime/fundamental_factors.py` | 联动调整 |
| `core/skill_runtime/standard_financial_apis.py` | 联动调整 |

---

## Batch 6: MiniQMT → QMT 重命名

**提交信息**：
```
docs: MiniQMT → QMT 统一重命名

- 文件头、注释、日志中 "MiniQMT" 统一改为 "QMT 交易终端"
- 配置描述、错误消息、诊断建议同步更新
- 数据源常量描述更新
- 前端数据源配置对话框文字更新
- 功能逻辑无变化（xtquant API 一致）
```

**文件**：

| 文件 | 改动内容 |
|---|---|
| `app/services/data_sources/qmt_adapter.py` | 文件头、注释、日志 MiniQMT → QMT |
| `app/core/config.py` | 配置描述 |
| `app/core/unified_config.py` | 配置描述 |
| `app/main.py` | 注释 |
| `app/routers/config.py` | 错误消息 |
| `app/routers/embedded_nanobot.py` | 描述文字 |
| `app/routers/stock_sync.py` | 注释 |
| `app/schemas/embedded_nanobot.py` | 描述文字 |
| `app/services/config_service.py` | QMT 连通性测试消息 |
| `app/services/data_sources/manager.py` | 注释 |
| `app/services/portfolio_service.py` | 注释/错误消息 |
| `app/worker/qmt_sync_service.py` | 注释/错误消息 |
| `tradingagents/constants/data_sources.py` | 数据源常量描述 |
| `frontend/src/views/Settings/components/DataSourceConfigDialog.vue` | 前端显示文字 |

---

## Batch 7: 设计文档

**提交信息**：
```
docs: Agent Builder 设计文档更新

- agent-workshop-full-lifecycle-flow-v2.md: 完整生命周期流程更新
- agent-builder-intent-classification-v2.md: 意图分类 v2 方案设计
- agent-builder-langgraph-workflow-design.md: LangGraph 工作流设计
```

**文件**：

| 文件 | 状态 |
|---|---|
| `docs/design/v3.0/agent-workshop-full-lifecycle-flow-v2.md` | M |
| `docs/design/v3.0/agent-builder-intent-classification-v2.md` | 新增 |
| `docs/design/v3.0/agent-builder-langgraph-workflow-design.md` | 新增 |

---

## 建议提交顺序

```
1. Batch 1 (Agent Builder LangGraph 核心)
2. Batch 2 (Agent Builder 服务层)
3. Batch 3 (后端工具中文化)
4. Batch 4 (前端中文化)
5. Batch 5 (Baostock → Tushare)
6. Batch 6 (MiniQMT → QMT)
7. Batch 7 (设计文档)
```

### 文件归属总表

```
Batch 1 (13 files):
  core/embedded_nanobot/workflows/agent_builder_graph.py     NEW
  core/embedded_nanobot/workflows/agent_builder_nodes.py     NEW
  core/embedded_nanobot/workflows/agent_builder_conditions.py NEW
  core/embedded_nanobot/workflows/agent_builder_state.py     NEW
  core/embedded_nanobot/workflows/agent_builder_store.py     NEW
  core/embedded_nanobot/agent_builder_flow.py                M
  core/embedded_nanobot/intent_context.py                    M
  core/embedded_nanobot/agent/context.py                     M
  core/embedded_nanobot/agent/context_injection_policy.py    NEW
  core/embedded_nanobot/agent/tools/registry.py              M
  core/embedded_nanobot/runtime.py                           M
  core/tools/implementations/agent_builder/nanobot_agent_builder_tools.py  M

Batch 2 (10 files):
  app/services/agent_workshop_service.py                     M
  app/services/embedded_nanobot_service.py                   M
  app/services/capability_index_service.py                   M
  app/routers/embedded_nanobot.py                            M
  app/schemas/embedded_nanobot.py                            M
  core/memory/service.py                                     M
  core/tools/context.py                                      M
  core/tools/loader.py                                       M
  core/tools/registry.py                                     M
  frontend/src/api/embeddedNanobot.ts                        M

Batch 3 (4 files):
  core/tools/implementations/fundamentals/dividend_enhancement.py        M
  core/tools/implementations/fundamentals/cashflow_enhancement.py        M
  core/tools/implementations/fundamentals/valuation/dcf_valuation.py     M
  core/tools/implementations/fundamentals/valuation/extended_valuation.py M

Batch 4 (6 files):
  frontend/src/views/Workflow/AgentWorkshop.vue              M
  frontend/src/views/Workflow/AgentStudio.vue                M
  frontend/src/views/Workflow/AgentWorkshopLanding.vue       M
  frontend/src/views/Workflow/AgentDetail.vue                M
  frontend/src/views/Workflow/Agents.vue                     M
  frontend/src/views/Workflow/SkillGeneration.vue            M

Batch 5 (4 files):
  core/skill_runtime/external_sources.py                     M
  tradingagents/dataflows/providers/china/tushare.py         M
  core/skill_runtime/fundamental_factors.py                  M
  core/skill_runtime/standard_financial_apis.py              M

Batch 6 (14 files):
  app/services/data_sources/qmt_adapter.py                   M
  app/core/config.py                                         M
  app/core/unified_config.py                                 M
  app/main.py                                                M
  app/routers/config.py                                      M
  app/routers/embedded_nanobot.py                            M
  app/routers/stock_sync.py                                  M
  app/schemas/embedded_nanobot.py                            M
  app/services/config_service.py                             M
  app/services/data_sources/manager.py                       M
  app/services/portfolio_service.py                          M
  app/worker/qmt_sync_service.py                             M
  tradingagents/constants/data_sources.py                    M
  frontend/src/views/Settings/components/DataSourceConfigDialog.vue  M

Batch 7 (3 files):
  docs/design/v3.0/agent-workshop-full-lifecycle-flow-v2.md  M
  docs/design/v3.0/agent-builder-intent-classification-v2.md NEW
  docs/design/v3.0/agent-builder-langgraph-workflow-design.md NEW
```

> **注意**：`app/routers/embedded_nanobot.py` 和 `app/schemas/embedded_nanobot.py` 同时出现在 Batch 2 和 Batch 6 中。Batch 6 提交时可能已无法干净提交这些文件的 QMT 重命名部分（因为 Batch 2 已改过）。建议在 Batch 2 中一并将这两个文件的 QMT 文字也改掉，或者在 Batch 2 提交时不包含 QMT 相关改动，全留给 Batch 6。
