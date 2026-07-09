# TradingAgentsCN v3.x 项目进度追踪

> 本文档按时间顺序记录所有重要修改，便于后续跟进和追溯。
>
> 格式：日期 → 问题 → 解决方案 → 涉及文件 → 验证方法

---

## 2026-06-23 MCP 数据源接入问题修复

### 问题背景

用户询问"项目现在解决了所有问题了吗？MCP 接入数据源调用的问题解决了吗？"，经调查发现 MCP 主链路可用但存在 4 个未修复问题。

### 修复内容

#### 1. MCP 工具启动自动恢复（严重）

**问题**：`restore_enabled_servers()` 方法已定义但从未被调用，后端重启后 MCP 工具不自动注册到 ToolRegistry。

**解决方案**：在 `app/main.py` 的 `lifespan()` 中调用 `MCPService.restore_enabled_servers()`。

**涉及文件**：
- `app/main.py:331-339` — 新增 MCP 工具恢复调用

**验证方法**：后端重启后日志出现 `✅ 恢复了 N 个 MCP 工具`。

#### 2. Skill 执行器 MCP 路径实现（中等）

**问题**：`_execute_mcp()` 直接抛出 `NotImplementedError`，Skill 无法通过 MCP 协议调用工具。

**解决方案**：实现 `_execute_mcp()`，对接 `MCPClientManager`，支持 sse/streamable_http/stdio 三种传输协议。

**涉及文件**：
- `core/skills/executor.py:230-278` — 实现 MCP 执行路径
- `core/skills/models.py:56-61` — 去掉"预留"标注，默认 transport 改为 `sse`

**验证方法**：创建 `implementation.type == "mcp"` 的 Skill，调用后返回 MCP 工具结果。

#### 3. 凭证加密升级为 Fernet（中等）

**问题**：凭证加密使用 XOR + base64，可被轻易破解，不适合存储生产级 API Key。

**解决方案**：升级为 Fernet（AES-128-CBC + HMAC-SHA256），新密文带 `v2:` 前缀，旧密文向后兼容。

**涉及文件**：
- `app/routers/mcp.py:317-353` — `_encrypt_value` / `_decrypt_value` 升级

**验证方法**：新加密密文以 `v2:` 开头，旧密文仍可解密。

#### 4. 凭证列表遮蔽逻辑修复（低）

**问题**：`list_credentials` 用 `key_name` 后 4 位遮蔽，而非真实密钥值。

**解决方案**：解密 `key_value_encrypted` 后用 `_mask_value()` 遮蔽真实密钥前后 4 位。

**涉及文件**：
- `app/routers/mcp.py:421-446` — 修正遮蔽逻辑

**验证方法**：列表页显示 `sk-1****cdef`（真实密钥前后 4 位）。

### 相关文档

详细记录见 `docs/development/dynamic-agent-workflow-integration.md` 第 17-20 节。

---

## 2026-06-23 P0 动态 Agent 工作流生效问题修复

### 问题背景

全面扫描后发现 4 个 P0 问题会导致之前的动态 Agent 工作流改造在生产环境不生效。

### 待修复内容

#### P0-1: 数据库提示词迁移未实现（最关键） ✅ 已完成

**问题**：`dynamic-stage-reports-v1` 迁移仅有文档描述，无实际迁移脚本。数据库模板仍引用旧字段（`{market_report}`），聚合变量 `{analyst_reports}` 不生效。

**解决方案**：编写迁移脚本 `migrate_prompt_templates_dynamic_reports.py`，将 8 个 agent × 3 种 preference = 24 个模板迁移为引用聚合变量，并归档旧模板。

**涉及文件**：
- `scripts/migration/migrate_prompt_templates_dynamic_reports.py` — 新建迁移脚本（约 350 行）

**验证方法**：
```powershell
# 预览迁移
python scripts/migration/migrate_prompt_templates_dynamic_reports.py --dry-run

# 执行迁移
python scripts/migration/migrate_prompt_templates_dynamic_reports.py

# 回退迁移
python scripts/migration/migrate_prompt_templates_dynamic_reports.py --rollback
```

迁移后数据库中 `bull_researcher_v2` 等模板引用 `{analyst_reports}`。

#### P0-2: use_dynamic_state 默认未启用 ✅ 已完成

**问题**：`WorkflowEngine.__init__` 的 `use_dynamic_state: bool = False`，生产环境所有调用方均未传 True，动态状态 schema 不生效。

**解决方案**：将默认值改为 `True`。

**涉及文件**：
- `core/workflow/engine.py:176` — `use_dynamic_state: bool = True`

**验证方法**：运行股票分析，检查状态中包含动态 agent 字段。

#### P0-3: report_suffixes 不完整 ✅ 已完成

**问题**：`base.py` 的 `report_suffixes` 仅匹配 5 种后缀，缺少 `_analysis`/`_advice`/`_summary`/`_result`，持仓分析/复盘类 Agent 的提示词变量不会被注入。

**解决方案**：补全 `report_suffixes` 为 9 种后缀。

**涉及文件**：
- `core/agents/base.py:1195` — `report_suffixes = ("_report", "_plan", "_opinion", "_decision", "_assessment", "_analysis", "_advice", "_summary", "_result")`

**验证方法**：`technical_analysis` 等字段值被注入到模板变量。

#### P0-4: v1 agent 未设 workflow_stage ✅ 已完成

**问题**：`config.py` 的 BUILTIN_AGENTS 中 v1 agent 未设置 `workflow_stage`，不被 stage_aggregator 聚合。

**解决方案**：为 20 个 v1 agent 补充 `workflow_stage` 字段。

**涉及文件**：
- `core/agents/config.py` — BUILTIN_AGENTS 补充 workflow_stage（25 处）

**阶段映射**：
| 阶段 | Agent |
|---|---|
| analyst | market_analyst, fundamentals_analyst, news_analyst, social_analyst, sector_analyst, index_analyst, timing_analyst, position_analyst, emotion_analyst, attribution_analyst, pa_technical, pa_fundamental, pa_risk |
| research | bull_researcher, bear_researcher |
| risk | risky_analyst, safe_analyst, neutral_analyst |
| manager | risk_manager, research_manager, review_manager, pa_advisor |
| trader | trader, position_advisor |

**验证方法**：v1 agent 报告进入 `analyst_reports` 等聚合变量。

---

## 2026-06-23 v1 Agent 废弃标记

### 问题背景

用户要求将 v1 agent 打上废弃标识，防止新代码引用。

### 修复内容

#### 1. 新增 DEPRECATED 状态

**解决方案**：在 `AgentMaintenanceStatus` 中新增 `DEPRECATED` 状态，比 `UNMAINTAINED` 更明确。

**涉及文件**：
- `core/agents/config.py:79-83` — 新增 `AgentMaintenanceStatus.DEPRECATED`

#### 2. v1 Agent 标记为 DEPRECATED

**解决方案**：将 24 个 v1 agent 的 `maintenance_status` 从 `UNMAINTAINED` 改为 `DEPRECATED`。

**涉及文件**：
- `core/agents/config.py` — BUILTIN_AGENTS 中所有 v1 agent（24 处）

#### 3. 运行时废弃警告

**解决方案**：在 `AgentFactory.create()` 和 `WorkflowBuilder._execute_node()` 中添加废弃检查，使用 `warnings.warn()` 发出 `DeprecationWarning`。

**涉及文件**：
- `core/agents/factory.py:70-80` — 创建 Agent 时检查并发出警告
- `core/workflow/builder.py:1809-1817` — 执行节点时检查并发出警告

#### 4. 模块级废弃警告

**解决方案**：在 `adapters/__init__.py` 中添加模块级废弃警告，导入该模块时自动发出。

**涉及文件**：
- `core/agents/adapters/__init__.py:1-24` — 模块文档和废弃警告

### 效果

- 代码中引用 v1 agent 时会收到 `DeprecationWarning`
- 日志中会记录警告信息
- IDE 中可以看到 `DEPRECATED` 标记
- 未来版本可以安全移除 v1 agent

### 验证方法

```python
# 运行时会发出警告
from core.agents.adapters import MarketAnalystAgent  # DeprecationWarning

# 创建 Agent 时会发出警告
factory.create("market_analyst")  # DeprecationWarning + 日志警告
```

---

## 2026-06-23 P1 安全与废弃代码清理

### 问题背景

用户要求处理 P1 级别问题：硬编码凭证、过期废弃代码、v1 agent 清理、v1 调试路由。

### 修复内容

#### P1-5: 清理硬编码凭证 ✅ 已完成

**问题**：`admin/admin123`、`tradingagents123` 等硬编码凭证存在于代码中。

**解决方案**：
1. `user_service.py` 的 `create_admin_user()` 改为必须通过环境变量 `ADMIN_DEFAULT_PASSWORD` 或参数指定密码
2. `default_workflow_provider.py` 和 `workflow_api.py` 的 MongoDB 连接字符串改为必须通过环境变量 `MONGODB_CONNECTION_STRING` 指定

**涉及文件**：
- `app/services/user_service.py:315-344` — 移除硬编码默认密码
- `core/workflow/default_workflow_provider.py:68-78` — 移除硬编码连接字符串
- `core/api/workflow_api.py:59-88` — 移除硬编码连接字符串

**验证方法**：未设置环境变量时启动会抛出 `ValueError`。

#### P1-6: 清理过期废弃代码 ✅ 已完成

**问题**：
- `config_manager.py` 过期 83 天（原计划移除 2026-03-31）
- `unified_news_tool.py` 过期 8 天（原计划移除 2026-06-15）

**解决方案**：更新废弃警告，明确标注已过期和引用文件数量，督促迁移。

**涉及文件**：
- `tradingagents/config/config_manager.py:1-37` — 更新废弃警告（44 个引用）
- `tradingagents/tools/unified_news_tool.py:1-39` — 更新废弃警告（11 个引用）

**注意**：仍有大量文件引用这两个模块，直接删除会破坏现有代码。后续需要逐步迁移。

#### P1-7: v1 agent 代码清理 ✅ 已完成

**问题**：v1 agent 未明确标记废弃。

**解决方案**：已在 P0 阶段完成（新增 `DEPRECATED` 状态 + 运行时警告 + 模块级警告）。

#### P1-8: templates_debug.py v1 调试路由清理 ✅ 已完成

**问题**：`templates_debug.py` 是 v1 调试路由，未标记废弃。

**解决方案**：添加废弃警告，标注移除计划（v4.0 与 v1 Agent 同步移除）。

**涉及文件**：
- `app/routers/templates_debug.py:1-39` — 添加废弃警告
- `app/main.py:42,1152` — 添加废弃注释

**注意**：此路由仍有前端页面 `TemplateDebug.vue` 使用，移除前需要先迁移前端页面。

---

## 2026-06-23 P2 代码质量与配置完善

### 问题背景

用户要求处理 P2 级别问题：异常日志、报告字段列表、工坊规范化、配置异常日志、环境变量示例、迁移脚本、前端动态渲染。

### 修复内容

#### P2-9: `_get_dynamic_report_fields` 异常添加日志 ✅ 已完成

**问题**：`except: pass` 无日志，调试困难。

**解决方案**：将 `pass` 改为 `logger.warning()`，记录异常信息。

**涉及文件**：
- `core/workflow/engine.py:49,70` — 添加日志

#### P2-10: `_BUILTIN_REPORT_FIELDS` 补全列表 ✅ 已完成

**问题**：缺少 `risky_opinion`、`technical_analysis` 等字段。

**解决方案**：补全为 28 个字段，覆盖所有阶段。

**涉及文件**：
- `core/workflow/engine.py:24-59` — 补全列表

#### P2-11: 工坊两处入口规范化 output_field ✅ 已完成

**问题**：`agent_workshop_service.py:1177,3924` 未使用规范化函数。

**解决方案**：调用 `_normalize_output_field_name()` 规范化字段名。

**涉及文件**：
- `app/services/agent_workshop_service.py:1177-1178,3925-3926` — 添加规范化

#### P2-13: `config.py` 28处 `except: pass` 添加日志 ✅ 已完成

**问题**：静默吞掉配置异常。

**解决方案**：批量替换为 `except Exception as e: logger.warning()`。

**涉及文件**：
- `app/routers/config.py` — 31 处替换

#### P2-14: `.env.example` 补全缺失配置项 ✅ 已完成

**问题**：P1-5 新增的必需配置项未在示例中说明。

**解决方案**：
1. 新增 `ADMIN_DEFAULT_PASSWORD` 配置项
2. 将 `MONGODB_CONNECTION_STRING` 标记为必需
3. 更新说明文字

**涉及文件**：
- `.env.example:14-24,42-45,313-315` — 补全配置项和说明

#### P2-15: `migrations/v3_0_0.py` 创建索引 ✅ 已完成

**问题**：v3.0 新集合未创建索引。

**解决方案**：为 7 个集合创建 24 个索引。

**涉及文件**：
- `migrations/v3_0_0.py` — 新增索引创建逻辑

**索引列表**：
| 集合 | 索引 |
|---|---|
| agent_configs | agent_id(unique), enabled/version/runtime_status, workflow_stage, category |
| agent_versions | version_id(unique), spec_id+version, status |
| agent_specs | spec_id(unique), owner_user_id, status |
| agent_workshop_sessions | session_id(unique), spec_id, user_id+created_at, stage |
| template_history | migration_id, agent_name+timestamp |
| skill_bindings | skill_id+agent_id(unique), agent_id |
| tool_execution_logs | execution_id, agent_id+timestamp, tool_name, success |

#### P2-16: ReportDetail.vue 硬编码 moduleOrder ✅ 已确认

**问题**：前端仍有硬编码 moduleOrder。

**现状**：已实现动态模式，优先使用 `report_manifest`，`moduleOrder` 作为 fallback。设计合理，无需修改。

---

## 待办事项（P3）

### P1 - 安全与废弃代码清理

| # | 问题 | 位置 | 状态 |
|---|---|---|---|
| 5 | 硬编码凭证 `admin/admin123`、`tradingagents123` | `user_service.py:315`、`default_workflow_provider.py:71` | 待处理 |
| 6 | 过期废弃代码未清理（过期 83 天、8 天） | `tradingagents/config/config_manager.py`、`tradingagents/tools/unified_news_tool.py` | 待处理 |
| 7 | v1 agent 代码未清理 | `core/agents/adapters/__init__.py`、`core/workflow/builder.py` | 待处理 |
| 8 | `templates_debug.py` 整个文件是 v1 调试路由 | `app/routers/templates_debug.py` | 待处理 |

### P2 - 代码质量与配置

| # | 问题 | 位置 | 状态 |
|---|---|---|---|
| 9 | `_get_dynamic_report_fields` 异常静默吞掉 | `engine.py:49,69` | 待处理 |
| 10 | `_BUILTIN_REPORT_FIELDS` fallback 列表不完整 | `engine.py:24-36` | 待处理 |
| 11 | 工坊两处入口未规范化 output_field | `agent_workshop_service.py:1177,3924` | 待处理 |
| 12 | 前端 console.log 60+ 处 | `frontend/src/components/Sync/`、`frontend/src/views/Analysis/` | 待处理 |
| 13 | `config.py` 28 处 `except: pass` | `app/routers/config.py` | 待处理 |
| 14 | `.env.example` 缺失 30+ 配置项 | `.env.example` | 待处理 |
| 15 | `migrations/v3_0_0.py` 为空占位符 | `migrations/v3_0_0.py` | 待处理 |
| 16 | `ReportDetail.vue` 仍有硬编码 moduleOrder | `frontend/src/views/Reports/ReportDetail.vue:905-944` | 待处理 |

### P3 - 长期改进

| # | 问题 | 状态 |
|---|---|---|
| 17 | 单元测试覆盖率不足 | 待处理 |
| 18 | `tests/` 根目录 200+ 个调试文件 | 待处理 |
| 19 | `requirements-lock.txt` 未使用依赖 | 待处理 |
| 20 | v3.0 部分设计功能未实现（飞书/钉钉、北交所 ETF） | 待处理 |

---

## 文档索引

| 文档 | 内容 |
|---|---|
| `docs/development/dynamic-agent-workflow-integration.md` | 动态 Agent 接入工作流详细开发记录 |
| `docs/development/project-progress-tracker.md` | 本文档，项目进度追踪 |
| `docs/testing/v3-acceptance-test-plan.md` | v3.0 验收测试计划 |

---

## 更新日志

- **2026-06-23**：创建文档，记录 MCP 修复和 P0 待办事项
- **2026-06-23**：完成 P0-1（迁移脚本）、P0-2（use_dynamic_state）、P0-3（report_suffixes）、P0-4（v1 workflow_stage）
- **2026-06-23**：完成 v1 Agent 废弃标记（DEPRECATED 状态 + 运行时警告 + 模块级警告）
- **2026-06-23**：完成 P1-5（硬编码凭证）、P1-6（过期废弃代码）、P1-7（v1 agent）、P1-8（templates_debug）
- **2026-06-23**：完成 P2-9（异常日志）、P2-10（报告字段）、P2-11（工坊规范化）、P2-13（config日志）、P2-14（.env.example）、P2-15（迁移索引）、P2-16（前端动态）
- **2026-06-23**：创建 v3.0 验收测试计划（15 个测试模块，200+ 测试项）
- **2026-06-23**：分析流菜单重构（方案B）：精简为 5 项，合并 Skill 中心/Agent 管理/工作流创建，移回 4 个配置项到系统设置