# 动态 Agent 接入工作流开发记录

> 本文按“原问题是什么 → 解决了什么问题 → 解决方案是什么 → 涉及文件 → 如何验证”的方式记录，便于后续开发人员排查和扩展。

## 0. 一句话总结

原系统的股票分析流程主要依赖固定 v2 Agent 和硬编码报告字段。新 Agent，尤其是 Agent 工坊 / nanobot 生成的动态 Agent，即使能创建出来，也不能稳定参与分析师汇总、多空辩论、风险评估、最终决策和最终报告。

本次改造打通了：

```text
Agent 工坊 / nanobot 生成 Agent
  → 测试通过
  → 发布 active
  → 加入工作流
  → 执行输出
  → 阶段报告聚合
  → 下游辩论和风险评估引用
  → 最终报告动态包含
```

## 1. 原问题：新增 Agent 的输出无法自动进入下游辩论和风险评估

### 原问题是什么

原股票分析流程是：

```text
各分析师独立分析
  → 多空研究员辩论
  → 研究经理形成投资计划
  → 风险三方评估
  → 风险经理形成风险结论
  → 交易员形成最终操作计划
  → 整合成最终报告
```

但下游 Agent 的提示词和状态读取依赖固定字段，例如：

- `market_report`
- `fundamentals_report`
- `news_report`
- `sentiment_report`
- `bull_report`
- `bear_report`

如果新增一个 Agent，例如：

- `chip_distribution_analyst_v2`
- `industry_comparison_report`
- `financial_health_report`

它的输出不会自动进入：

- 多空研究员提示词
- 风险评估提示词
- 交易员提示词
- 最终报告字段列表

### 解决了什么问题

新增 Agent 的输出现在可以按所属阶段自动聚合，并通过统一变量给下游 Agent 使用。

### 解决方案是什么

新增 `workflow_stage` 阶段元数据，并提供阶段报告聚合器。

每个 Agent 通过 `workflow_stage` 声明自己属于哪个阶段：

| 阶段 | 说明 |
|---|---|
| `analyst` | 分析师阶段 |
| `research` | 多空研究阶段 |
| `risk` | 风险三方阶段 |
| `manager` | 研究经理 / 风险经理 |
| `trader` | 交易决策阶段 |

阶段聚合器自动生成：

| 聚合变量 | 内容 |
|---|---|
| `analyst_reports` | 所有分析师输出 |
| `research_reports` | 多空研究输出 |
| `risk_reports` | 风险三方输出 |

下游提示词只要引用 `{analyst_reports}`、`{research_reports}`、`{risk_reports}`，即可自动获得新增 Agent 的输出。

### 涉及文件

| 文件 | 调整 |
|---|---|
| `core/agents/config.py` | `AgentMetadata` 新增 `workflow_stage` |
| `core/workflow/stage_aggregator.py` | 新增阶段报告聚合器 |
| `core/agents/base.py` | 提示词变量自动注入阶段聚合报告 |
| `core/agents/adapters/*_v2.py` | v2 Agent 补齐 `workflow_stage` |

### 如何验证

模拟状态中包含新增 Agent 输出：

```python
state = {
    "chip_report": "筹码分布分析内容"
}
```

验证：

```text
analyst_reports includes chip_report = True
```

## 2. 原问题：最终报告字段是硬编码的，新增 Agent 输出不会进入报告

### 原问题是什么

原系统存在多套硬编码报告字段列表，例如：

- `_BUILTIN_REPORT_FIELDS`
- `REPORT_FIELDS`
- `STANDARD_REPORT_FIELDS`
- 前端 `moduleOrder`

这些字段列表只知道固定 Agent 的输出。新增 Agent 的输出字段不会自动进入最终 `structured_reports`。

### 解决了什么问题

最终报告字段现在可以从 Agent 元数据和运行时配置中动态推导。

### 解决方案是什么

新增动态字段收集逻辑：

```python
_get_dynamic_report_fields(agent_ids)
```

字段来源：

1. 代码内置 Agent：从 `AgentRegistry` 读取 `output_field`。
2. 工坊 Agent：从 MongoDB `agent_configs` 读取 `output_field`。

同时修复委派 Agent 的遗漏问题：

`_extract_agent_ids()` 现在会提取：

- 节点 `agent_id`
- 辩论 `participants`
- 委派 `delegated_agent_ids`

因此 `chip_distribution_analyst_v2` 这类委派 Agent 也能进入最终报告字段。

### 涉及文件

| 文件 | 调整 |
|---|---|
| `core/workflow/engine.py` | 动态推导报告字段；提取 delegated Agent |

### 如何验证

```text
contains chip_distribution_analyst_v2 = True
contains chip_report = True
```

## 3. 原问题：动态 Schema 没有 reducer，并行节点可能覆盖状态

### 原问题是什么

动态生成的 TypedDict 字段原来只是普通类型：

```python
market_report: str
```

在 LangGraph 并行执行时，多个节点写状态可能互相覆盖。

### 解决了什么问题

动态 Schema 字段现在带 reducer 注解，能正确合并状态。

### 解决方案是什么

抽离共享 reducer，并让动态 Schema 生成时使用：

```python
Annotated[str, keep_non_empty]
Annotated[dict, merge_dict]
Annotated[list, keep_latest_list]
```

### 涉及文件

| 文件 | 调整 |
|---|---|
| `core/state/reducers.py` | 新增共享 reducer |
| `core/state/builder.py` | 动态 TypedDict 字段加 reducer |
| `core/workflow/builder.py` | 改为导入共享 reducer |

### 如何验证

动态生成 Schema 后，字段包含 reducer 注解，例如：

```text
market_report → keep_non_empty
tool_call_summaries → merge_dict
messages → add_messages
```

## 4. 原问题：工具调用结果只在当前 Agent 内部可见，下游 Agent 无法参考

### 原问题是什么

Agent 调用工具后，工具结果只进入当前 Agent 的消息历史，最终被总结成报告。下游 Agent 只能看到报告，无法知道：

- 调用了哪些工具
- 参数是什么
- 成功还是失败
- 返回结果摘要是什么

### 解决了什么问题

工具调用摘要现在可以进入工作流状态，并被下游 Agent 引用。

### 解决方案是什么

在 `_execute_tool_calls()` 中收集工具调用摘要，并写入：

```python
tool_call_summaries[agent_id] = markdown_summary
```

下游模板可通过：

```text
{tool_call_summaries}
```

引用前序工具调用摘要。

### 涉及文件

| 文件 | 调整 |
|---|---|
| `core/agents/base.py` | 收集和注入工具调用摘要 |
| `core/agents/analyst.py` | 返回 `tool_call_summaries` |
| `core/agents/adapters/*_analyst_v2.py` | v2 分析师返回工具摘要 |
| `core/workflow/builder.py` | WorkflowState 新增 `tool_call_summaries` |

### 如何验证

工具调用后状态中出现：

```text
tool_call_summaries = {
  "market_analyst_v2": "### market_analyst_v2 工具调用记录..."
}
```

## 5. 原问题：数据库提示词仍引用旧字段，动态聚合变量不会被使用

### 原问题是什么

系统提示词默认从数据库读取。即使代码已经注入 `{analyst_reports}`，如果数据库模板没有引用该变量，下游 Agent 仍然只会使用旧字段。

### 解决了什么问题

数据库模板已版本化迁移到动态聚合变量。

### 解决方案是什么

执行数据库提示词迁移：

```text
migration_id = dynamic-stage-reports-v1
```

处理范围：

- `bull_researcher_v2`
- `bear_researcher_v2`
- `research_manager_v2`
- `risky_analyst_v2`
- `safe_analyst_v2`
- `neutral_analyst_v2`
- `risk_manager_v2`
- `trader_v2`

每个 Agent 覆盖：

- aggressive
- neutral
- conservative

迁移结果：

```text
24 个旧 active 模板 → archived
24 个新 active 模板 → 动态流程版
48 条 template_history 记录
```

### 新增变量映射

| Agent | 新增变量 |
|---|---|
| bull / bear researcher | `{analyst_reports}` |
| research_manager | `{analyst_reports}`、`{research_reports}` |
| risk 三方 | `{analyst_reports}`、`{research_reports}` |
| risk_manager | `{research_reports}`、`{risk_reports}` |
| trader | `{analyst_reports}`、`{research_reports}`、`{risk_reports}` |

### 回退方案

新模板记录：

```text
base_template_id
base_version
migration_id = dynamic-stage-reports-v1
```

旧模板记录：

```text
status = archived
archived_by_migration = dynamic-stage-reports-v1
```

回退时：

1. 归档 `migration_id=dynamic-stage-reports-v1` 的新模板。
2. 恢复 `archived_by_migration=dynamic-stage-reports-v1` 的旧模板。

## 6. 原问题：Agent 工坊生成的 Agent 没被纳入动态流程

### 原问题是什么

Agent 工坊 / nanobot 生成的 Agent 存储在 MongoDB `agent_configs`，不是代码注册的 `AgentRegistry`。

原先动态聚合只看 `AgentRegistry`，因此会漏掉工坊 Agent。

### 解决了什么问题

工坊 Agent 现在可以参与：

- 工作流构建
- UniversalAgent 执行
- 阶段报告聚合
- 动态最终报告字段

### 解决方案是什么

将 `agent_configs` 纳入以下运行时入口：

- Agent 列表接口
- WorkflowBuilder Agent 检查
- AgentFactory UniversalAgent 创建
- 阶段报告聚合器
- 最终报告字段推导

### 涉及文件

| 文件 | 调整 |
|---|---|
| `app/routers/agents.py` | Agent 列表包含已发布工坊 Agent |
| `core/workflow/builder.py` | 未注册 Agent 可从 `agent_configs` 创建，但必须满足运行条件 |
| `core/agents/factory.py` | 从 `agent_configs` 创建 UniversalAgent |
| `core/workflow/stage_aggregator.py` | 聚合工坊 Agent 输出 |
| `core/workflow/engine.py` | 工坊 Agent 输出进入最终报告字段 |

### 如何验证

```text
analyst_reports_exists = True
contains_workshop_report = True
dynamic_fields = ['financial_health_report', 'final_trade_decision']
```

## 7. 原问题：未测试或未发布的工坊 Agent 也可能被加入流程

### 原问题是什么

工坊 Agent 生成后会写入 `agent_configs`。如果只按 `agent_id` 判断，draft/testing/archived 版本也可能被流程识别。

### 解决了什么问题

只有测试通过并正式发布为 active 的工坊 Agent 才能进入流程。

### 解决方案是什么

工坊 Agent 必须满足：

```text
metadata.source = agent_workshop
enabled = true
version_status = active
runtime_status = active
```

状态流转：

```text
DRAFT
  ↓ evaluate pass
TESTING
  ↓ publish
ACTIVE
  ↓ 新版本发布 / 回滚
ARCHIVED
```

发布规则：

- 只有 `TESTING` 版本可以发布为 `ACTIVE`。
- 发布新版本时，旧版本运行时配置会禁用。
- 回滚时，只启用回滚后的 active 版本。

### 涉及文件

| 文件 | 调整 |
|---|---|
| `app/services/agent_workshop_service.py` | 发布、回滚、运行时状态写入 |
| `app/routers/agents.py` | 只返回 active 工坊 Agent |
| `core/workflow/builder.py` | 只识别 active 工坊 Agent |
| `core/agents/factory.py` | 只创建 active 工坊 Agent |
| `core/workflow/stage_aggregator.py` | 只聚合 active 工坊 Agent |
| `core/workflow/engine.py` | 只收集 active 工坊 Agent 字段 |

### 数据迁移结果

已有工坊配置迁移：

```text
workshop agent_configs = 9
```

规则：

```text
agent_versions.status == active → enabled=True, runtime_status=active
testing / archived / missing_version → enabled=False, runtime_status=archived
```

验证：

```text
testing_agent_aggregated = False
testing_dynamic_fields = ['final_trade_decision']

active_agent_aggregated = True
active_dynamic_fields = ['industry_comparison_report', 'final_trade_decision']
```

## 8. 原问题：工坊生成的 output_field 可能是中文长句，无法稳定参与动态 Schema 和报告

### 原问题是什么

旧工坊 Agent 可能生成类似字段：

```text
PE 估值结果：估值区间、当前值位置、关键假设、适用性判断、失效条件
```

这类字段不适合：

- 动态 Schema
- 提示词变量
- 最终报告字段
- 前端展示
- 测试评估匹配

### 解决了什么问题

新生成的 Agent 输出字段会规范化为稳定字段名。

### 解决方案是什么

新增输出字段规范化：

```text
只允许小写字母、数字、下划线
建议后缀：_report / _result / _summary / _assessment / _decision / _plan / _opinion
```

示例：

| 输入 | 输出字段 |
|---|---|
| `financial_health_report` | `financial_health_report` |
| `valuation` | `valuation_report` |
| `PE 估值结果：估值区间、当前值位置、关键假设` | `pe_report` |
| `估值区间` | `analysis_xxxxxxxx_report` |

规范字段用于：

- `AgentSpec.outputs`
- `AgentVersion.output_schema.required`
- `AgentVersion.output_schema.properties`
- `AgentMetadata.outputs`
- `AgentMetadata.output_field`
- `agent_configs.output_field`
- benchmark `expected_outputs`
- production-review 输出覆盖评分
- runtime prompt 输出字段说明

### 涉及文件

| 文件 | 调整 |
|---|---|
| `app/services/agent_workshop_service.py` | 输出字段规范化、schema、metadata、评估链路统一字段 |

### 如何验证

```text
output_fields = ['valuation_report', 'pe_report']
schema_required = ['valuation_report', 'pe_report']
NANOBOT_AGENT_OUTPUT_FIELD_PROMPT_CHAIN_OK
```

## 9. 原问题：nanobot / 工坊生成提示词没有明确要求稳定输出字段

### 原问题是什么

新 Agent 是通过 nanobot / Agent 工坊生成的。如果只在后端兜底规范字段，而不改生成提示词，LLM 仍可能生成中文长句字段。

### 解决了什么问题

nanobot / 工坊提示词现在明确要求输出字段使用结构化对象和英文蛇形字段名。

### 解决方案是什么

需求整理提示词新增要求：

```text
outputs 必须使用结构化对象数组
name 必须是稳定英文蛇形字段名
中文说明写 description
```

示例：

```json
{
  "outputs": [
    {
      "name": "valuation_report",
      "type": "string",
      "description": "估值分析报告，包含估值区间、关键假设和失效条件"
    }
  ]
}
```

工具规划提示词新增要求：

```text
draft_tools.inputs/outputs 使用结构化对象数组
name 使用稳定英文蛇形字段名
中文说明写 description
```

运行时提示词中也会展示稳定字段：

```text
- valuation_report: 估值分析报告
- pe_report: PE 估值结果...
```

### 涉及文件

| 文件 | 调整 |
|---|---|
| `app/services/agent_workshop_service.py` | requirement_clarification、tooling_plan、runtime prompt 均补齐字段规范 |

## 10. 原问题：Agent 工坊接口 404

### 原问题是什么

访问：

```text
GET /api/agent-workshop/sessions?page=1&page_size=30
```

返回 404。

原因：

- `app/routers/agent_workshop.py` 中路由存在。
- `app/main.py` 中没有注册该 router。

### 解决了什么问题

Agent 工坊 API 路由已挂载。

### 解决方案是什么

在 `app/main.py` 注册：

```python
from app.routers import agent_workshop as agent_workshop_router
register_router_with_log(app, agent_workshop_router.router, "Agent 工坊路由 (agent-workshop)", tags=["agent-workshop"])
```

### 涉及文件

| 文件 | 调整 |
|---|---|
| `app/main.py` | 注册 Agent 工坊路由 |

## 11. 原问题：Skill 绑定和工具执行结果缺少反馈闭环

### 原问题是什么

Skill 可以导入，但绑定到 Agent 的能力不够完善；工具执行结果也没有持久化反馈。

### 解决了什么问题

Skill 可以批量绑定到 Agent，并可以查看工具执行日志。

### 解决方案是什么

新增：

- Skill-Agent 批量绑定
- 绑定查询
- 解绑
- 绑定优先级
- 工具执行日志持久化
- Skill 中心执行日志页签

### 涉及文件

| 文件 | 调整 |
|---|---|
| `app/routers/skill_center.py` | 批量绑定、查询绑定、执行日志 API |
| `frontend/src/api/skillCenter.ts` | 前端 API |
| `frontend/src/views/Workflow/SkillCenter.vue` | 绑定弹窗和执行日志 UI |
| `core/tools/execution_logger.py` | 工具执行日志记录器 |
| `core/agents/base.py` | 工具执行成功/失败日志接入 |
| `app/main.py` | 初始化执行日志器 |

### 新增 API

```text
POST /api/skill-center/skills/{skill_id}/bind-batch
GET  /api/skill-center/skills/{skill_id}/bindings
GET  /api/skill-center/tool-logs
GET  /api/skill-center/tool-logs/stats
```

## 12. 原问题：腾讯 SkillHub 未接入 Skill 发现页

### 原问题是什么

用户要求接入：

```text
https://skillhub.cloud.tencent.com/
```

并放在 Skill 发现页第一位。

### 解决了什么问题

SkillHub 已接入发现/导入页，并支持搜索与导入。

### 解决方案是什么

新增 SkillHub 精选 Skill 列表和导入接口。

### 涉及文件

| 文件 | 调整 |
|---|---|
| `app/routers/skills.py` | SkillHub 列表、搜索、导入接口 |
| `frontend/src/api/skills.ts` | SkillHub API 类型和函数 |
| `frontend/src/views/Workflow/SkillCenter/SkillDiscover.vue` | SkillHub 作为第一 Tab |

### 新增 API

```text
GET  /api/skills/skillhub/skills
POST /api/skills/import-skillhub
```

## 13. 最终效果

现在主链路已打通：

```text
代码内置 v2 Agent
或 Agent 工坊 / nanobot 生成 Agent
  ↓
声明 output_field + workflow_stage
  ↓
正式发布 active
  ↓
进入工作流执行
  ↓
按阶段聚合为 analyst_reports / research_reports / risk_reports
  ↓
下游 Agent 提示词引用聚合报告
  ↓
辩论、风险评估、交易决策参考新增 Agent 输出
  ↓
最终 structured_reports 动态包含新增字段
```

## 14. 关键修改文件索引

| 文件 | 主要作用 |
|---|---|
| `core/state/reducers.py` | 共享 reducer |
| `core/state/builder.py` | 动态 Schema 字段 reducer |
| `core/agents/config.py` | AgentMetadata 新增 `workflow_stage` |
| `core/workflow/stage_aggregator.py` | 阶段报告聚合 |
| `core/agents/base.py` | 阶段变量、工具摘要、工具日志接入 |
| `core/workflow/engine.py` | 动态报告字段、delegated Agent 识别 |
| `core/workflow/builder.py` | 工坊 Agent 运行资格过滤 |
| `core/agents/factory.py` | active 工坊 Agent 创建 UniversalAgent |
| `app/services/agent_workshop_service.py` | 工坊生成、测试、发布、输出字段、提示词全链路 |
| `app/routers/agents.py` | Agent 列表只返回 active 工坊 Agent |
| `app/main.py` | 注册工坊路由、初始化工具日志器 |
| `app/routers/skill_center.py` | Skill 绑定和工具日志 API |
| `app/routers/skills.py` | SkillHub 接入 |
| `frontend/src/views/Workflow/SkillCenter.vue` | Skill 绑定和执行日志 UI |
| `frontend/src/views/Workflow/SkillCenter/SkillDiscover.vue` | SkillHub 发现页 |

## 15. 注意事项

1. 已发布旧 Agent 不建议直接修改 `output_field`，应通过新版本发布来修正。
2. 只有 active 工坊 Agent 会进入工作流；draft/testing/archived 不参与聚合和报告。
3. 数据库提示词已版本化迁移，旧版本可回退。
4. 后端需通过项目脚本启动：

```powershell
.\start_dev.ps1 backend 3.0
```

## 16. 建议验收流程

1. 在 Agent 工坊生成一个股票分析类 analyst Agent。
2. 确认输出字段为稳定英文字段，例如 `valuation_report`。
3. Debug / production-review 评估通过，进入 testing。
4. 发布为 active。
5. 加入测试工作流。
6. 运行股票分析。
7. 检查：
   - 新 Agent 是否执行。
   - 输出是否进入 `analyst_reports`。
   - bull / bear / risk / trader 是否引用聚合报告。
   - 最终 `structured_reports` 是否包含新 Agent 输出字段。

## 17. 原问题：MCP 工具在后端重启后不自动恢复

### 原问题是什么

`MCPService.restore_enabled_servers()` 方法已定义，但从未被调用。后端每次重启后，所有已启用的 MCP 服务器配置虽然还在数据库中（`is_enabled=True`），但工具不会自动注册到 `ToolRegistry`。

结果：

- Agent 调用 MCP 工具会失败（工具不存在）。
- 必须人工去管理页面手动重新启用每个 MCP 服务器。
- 违背了"接入数据源即可用"的核心诉求。

### 解决了什么问题

后端启动时自动恢复所有已启用 MCP 服务器的工具到 `ToolRegistry`，Agent 重启后可直接调用。

### 解决方案是什么

在 `app/main.py` 的 `lifespan()` 中，Skill 初始化之后、配置桥接之前，调用 `MCPService.restore_enabled_servers()`：

```python
from app.services.mcp_service import MCPService
mcp_service = MCPService(db)
await mcp_service.restore_enabled_servers()
```

`restore_enabled_servers()` 会：

1. 查询 `mcp_server_configs` 中所有 `is_enabled=True` 的文档。
2. 遍历每个服务器的 `discovered_tools`。
3. 调用 `_register_mcp_tool()` 注册到 `ToolRegistry`。
4. 失败的工具会记录警告日志，不阻塞其他工具恢复。

### 涉及文件

| 文件 | 调整 |
|---|---|
| `app/main.py` | `lifespan()` 中新增 MCP 工具恢复调用 |

### 如何验证

后端重启后：

```text
日志出现: ✅ 恢复了 N 个 MCP 工具
日志出现: ✅ MCP 服务器工具恢复完成
```

Agent 调用 MCP 工具不再报"工具不存在"。

## 18. 原问题：Skill 执行器 MCP 路径未实现

### 原问题是什么

`core/skills/executor.py` 的 `_execute_mcp()` 直接抛出 `NotImplementedError`：

```python
async def _execute_mcp(impl: McpImplementation, **kwargs) -> Any:
    raise NotImplementedError("MCP Server 执行协议尚未实现...")
```

如果 Skill 的 `implementation.type == "mcp"`，调用必然失败。

### 解决了什么问题

Skill 现在可以通过 MCP 协议调用外部 MCP Server 的工具。

### 解决方案是什么

实现 `_execute_mcp()`，对接 `MCPClientManager`：

```python
from core.tools.mcp.client_manager import get_mcp_client_manager

# 根据 transport 构造 config
config = {
    "transport_type": transport,
    "connection": {"url": impl.server_url}  # 或 stdio 的 command
}

# 用 asyncio.to_thread 包装同步调用，避免阻塞事件循环
result = await asyncio.to_thread(
    manager.call_tool, config, impl.tool_name, kwargs, 60
)
```

支持三种传输协议：

| transport | server_url 含义 | connection |
|---|---|---|
| `sse` | HTTP URL | `{"url": ...}` |
| `streamable_http` | HTTP URL | `{"url": ...}` |
| `stdio` | 命令路径 | `{"command": ..., "args": []}` |

返回值处理：

- MCP 工具返回字符串，尝试解析为 JSON，便于下游处理。
- 解析失败则返回原始字符串。

### 涉及文件

| 文件 | 调整 |
|---|---|
| `core/skills/executor.py` | 实现 `_execute_mcp()`，对接 `MCPClientManager` |
| `core/skills/models.py` | `McpImplementation` 去掉"预留"标注，默认 transport 改为 `sse` |

### 如何验证

创建一个 `implementation.type == "mcp"` 的 Skill，调用后不再抛 `NotImplementedError`，能正确返回 MCP 工具结果。

## 19. 原问题：MCP 凭证加密强度不足

### 原问题是什么

`app/routers/mcp.py` 的凭证加密使用 XOR + base64：

```python
encrypted = bytes(b ^ key[i % len(key)] for i, b in enumerate(data))
return base64.b64encode(encrypted).decode("ascii")
```

XOR 加密可被轻易破解，不适合存储生产级 API Key。

### 解决了什么问题

凭证加密升级为 Fernet（AES-128-CBC + HMAC-SHA256），达到生产级安全强度。

### 解决方案是什么

用 `cryptography.fernet.Fernet` 替代 XOR + base64：

```python
from cryptography.fernet import Fernet

def _encrypt_value(plain: str) -> str:
    f = _get_fernet()
    token = f.encrypt(plain.encode("utf-8")).decode("ascii")
    return f"v2:{token}"  # 加 v2: 前缀区分新旧格式

def _decrypt_value(cipher: str) -> str:
    if cipher.startswith("v2:"):
        # 新格式：Fernet 解密
        f = _get_fernet()
        return f.decrypt(cipher[3:].encode("ascii")).decode("utf-8")
    else:
        # 旧格式：XOR + base64 解密（向后兼容）
        ...
```

Fernet 密钥从 `JWT_SECRET` 的 SHA256 派生：

```python
key = base64.urlsafe_b64encode(hashlib.sha256(secret.encode()).digest())
```

向后兼容：

- 新凭证加密后带 `v2:` 前缀。
- 旧凭证（无前缀）解密时自动走 XOR + base64 路径。
- 旧凭证在被读取时不会自动升级，但新写入的凭证都是 Fernet 加密。

### 涉及文件

| 文件 | 调整 |
|---|---|
| `app/routers/mcp.py` | `_encrypt_value` / `_decrypt_value` 升级为 Fernet，保留旧格式兼容 |

### 如何验证

```python
# 新加密
cipher = _encrypt_value("my-api-key")
assert cipher.startswith("v2:")

# 新解密
assert _decrypt_value(cipher) == "my-api-key"

# 旧格式兼容
old_cipher = base64.b64encode(...).decode("ascii")  # 旧格式
assert _decrypt_value(old_cipher) == "原始值"
```

## 20. 原问题：MCP 凭证列表遮蔽逻辑错误

### 原问题是什么

`list_credentials` 接口返回的 `key_value_masked` 用 `key_name` 的后 4 位遮蔽，而非真实密钥值：

```python
key_value_masked="****" + doc.get("key_name", "")[-4:] if doc.get("key_name") else "****"
```

例如：

- `key_name = "TUSHARE_TOKEN"`
- `key_value = "abc123xyz789"`
- 显示：`****OKEN`（错误，暴露了变量名而非密钥）

用户在列表页看到的遮蔽值与真实密钥无关，无法核对密钥是否正确。

### 解决了什么问题

凭证列表现在显示真实密钥的前后 4 位遮蔽值。

### 解决方案是什么

解密 `key_value_encrypted` 后用 `_mask_value()` 遮蔽：

```python
key_value = _decrypt_value(doc.get("key_value_encrypted", ""))
masked = _mask_value(key_value)  # 前4位 + **** + 后4位
```

例如：

- `key_value = "abc123xyz789"`
- 显示：`abc1****z789`（正确，用户可核对密钥）

解密失败时回退为 `****`，不阻塞列表返回。

### 涉及文件

| 文件 | 调整 |
|---|---|
| `app/routers/mcp.py` | `list_credentials` 解密后遮蔽，而非用 `key_name` 遮蔽 |

### 如何验证

```text
key_value = "sk-1234567890abcdef"
key_value_masked = "sk-1****cdef"  # 正确遮蔽真实密钥
```
