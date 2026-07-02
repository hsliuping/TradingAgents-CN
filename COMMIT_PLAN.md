# Git 分批提交计划

> 未提交修改统计：72 个文件，+4026 / -11819 行
> 生成时间：2026-07-02

---

## 批次1：refactor: Nanobot 移除迁移 - 删除死代码

**说明：** 移除 Nanobot 运行时遗留的全部死代码，包括 agent/bus/command/cron/providers/security/session/utils 等目录，以及 runtime.py、agent_builder_flow.py 等核心文件。约 7500+ 行代码删除。

**删除的文件/目录：**
```
core/embedded_nanobot/agent/                    (整个目录，12个文件)
core/embedded_nanobot/bus/                      (整个目录)
core/embedded_nanobot/command/                  (整个目录)
core/embedded_nanobot/cron/                     (整个目录)
core/embedded_nanobot/providers/                (整个目录)
core/embedded_nanobot/security/                 (整个目录)
core/embedded_nanobot/session/                  (整个目录)
core/embedded_nanobot/utils/                    (整个目录)
core/embedded_nanobot/runtime.py                (-2353行)
core/embedded_nanobot/agent_builder_flow.py     (-994行)
app/services/agent_builders/                    (整个目录，5个文件)
tests/core/embedded_nanobot/test_runtime_hygiene.py    (-2014行)
scripts/validate_agent_builder_project_memory_loop.py
scripts/validate_agent_workshop_governance_l4_l6_loop.py
tests/scripts/test_validate_agent_builder_project_memory_loop.py
tests/scripts/test_validate_agent_workshop_governance_l4_l6_loop.py
```

**修改的文件：**
```
core/embedded_nanobot/__init__.py               (清理导入)
```

**Commit message:**
```
refactor: 移除 Nanobot 运行时死代码

删除 agent/bus/command/cron/providers/security/session/utils 等
遗留目录，以及 runtime.py(~2700行)、agent_builder_flow.py(~400行)、
test_runtime_hygiene.py(~2000行) 等文件。
共计删除约 7500+ 行无效代码。
```

---

## 批次2：refactor: Agent Builder 工作流核心重构

**说明：** Agent Builder 工作流从 Nanobot `_run_react_loop` 迁移到 UnifiedLLMClient.achat()，实现 tool-first 和标准 Function Calling 模式；修复意图识别、方案路由、日志路径等问题。

**文件列表：**
```
core/embedded_nanobot/workflows/agent_builder_nodes.py         (+1808/-... 行，核心重构)
core/embedded_nanobot/workflows/agent_builder_conditions.py
core/embedded_nanobot/workflows/agent_builder_graph.py
core/embedded_nanobot/workflows/agent_builder_state.py
core/embedded_nanobot/workflows/agent_builder_store.py
app/services/embedded_nanobot_service.py                       (api channel 切换到 UnifiedLLMClient)
app/main.py
```

**主要修改内容：**
- 用 `UnifiedLLMClient.achat()` 替换 Nanobot 的 `_run_react_loop`
- 实现 tool-first 和标准 Function Calling 两种模式
- 移除 XML 解析相关函数
- 修复意图识别日志路径（parents[4] → parents[3]）
- 修复 `last_hint` 截断问题，完整提取建议的股票代码
- 新增 `_extract_suggested_stock_from_state` 回退提取函数
- 修复方案选择路由问题（"重测"等操作正确触发）
- 修复 `node_requirement_intake` 保存 spec_id（英文 slug）
- 所有兜底逻辑从 md5 哈希改为有意义的 slug 生成

**Commit message:**
```
refactor: Agent Builder 工作流核心重构

- 用 UnifiedLLMClient.achat() 替换 Nanobot _run_react_loop
- 实现 tool-first 和标准 Function Calling 两种模式
- 移除 XML 解析相关函数
- 修复意图识别日志路径和 last_hint 截断问题
- 修复方案选择路由和 spec_id 生成逻辑
- embedded_nanobot_service api channel 切换到 UnifiedLLMClient
```

---

## 批次3：feat: Agent 工坊服务增强

**说明：** 多方案生成、缺口分析优化、模板名称修复、能力索引增强、删除前流程引用检测。

**文件列表：**
```
app/services/agent_workshop_service.py     (+1718/-... 行)
app/services/capability_index_service.py
core/memory/service.py
```

**主要修改内容：**
- 多方案生成：无阻塞缺口时默认生成3套方案（推荐完整交付、保守可追溯版、扩展增强版）
- 模板名称修复：发布时将模板名从"xxx 草案"改为"xxx v版本号"
- 新增 `_check_workflow_references()` 函数，检查 Agent 被哪些工作流引用
- `delete_spec` 和 `delete_version` 增加 `force` 参数和引用检查
- 能力索引增强：覆盖词词汇扩展（新增资产质量/偿债能力/流动性等21个类别）
- 项目记忆服务优化

**Commit message:**
```
feat: Agent 工坊服务增强

- 多方案生成：默认生成2-4套可比较方案
- 模板名称修复：发布时更新为正式名称
- 删除前流程引用检测：新增 _check_workflow_references
- 能力索引覆盖词扩展：新增21个金融分析类别
```

---

## 批次4：feat: Agent ID 命名优化 + 冗余模板清理

**说明：** Agent ID 从随机哈希改为 LLM 生成有意义的英文 slug；消除 Agent 工坊生成两套提示词模板的冗余问题。

**文件列表：**
```
core/tools/implementations/agent_builder/nanobot_agent_builder_tools.py    (+331/-... 行)
tests/core/tools/implementations/test_nanobot_agent_builder_tools.py
```

**主要修改内容：**
- `_generate_short_agent_name_llm`：返回值从 str 改为 dict（含 name + slug），LLM 同时生成中文名和英文 ID
- 新增 `_fallback_slug_from_name()`：通过中英文关键词映射生成有意义的英文 slug
- `_generate_short_agent_name_fallback`：返回值改为 dict
- `prepare_agent_requirement_intake`：返回结果新增 `proposed_agent_slug`
- `generate_confirmed_candidate_agent`：当 `sync_to_workshop_draft=True` 时跳过 `create_or_update_universal_agent_prompt_template` 调用，避免生成冗余模板

**命名效果示例：**
| 中文名 | 旧英文名（随机哈希） | 新英文名（有意义） |
|--------|---------------------|-------------------|
| 风险评估助手 | agent_candidate_1bd94b55 | risk_assessment |
| 财报排雷助手 | agent_candidate_xxxxxxx | financial_risk_screener |
| 多维度估值分析助手 | agent_candidate_xxxxxxx | valuation_analyst |

**Commit message:**
```
feat: Agent ID 命名优化 + 冗余模板清理

- Agent ID 从随机哈希改为 LLM 生成有意义的英文 slug
- 新增 _fallback_slug_from_name 关键词映射兜底函数
- sync_to_workshop_draft=True 时跳过冗余模板创建
- 消除 Agent 工坊生成两套提示词模板的问题
```

---

## 批次5：fix: 提示词模板查询修复 + 删除引用检测 API

**说明：** 修复流程编辑器中提示词模板返回空列表的问题；新增删除引用检测的 API 路由。

**文件列表：**
```
app/routers/prompt_templates.py     (+39/-... 行)
app/routers/agent_workshop.py       (+26/-... 行)
```

**主要修改内容：**
- `get_agent_templates` 接口增加 fallback 逻辑：指定类型查不到时自动去 universal 类型查找
- `delete_spec` 和 `delete_version` API 路由增加 `force` 查询参数
- 被工作流引用阻止删除时返回 409 状态码和引用列表

**Commit message:**
```
fix: 提示词模板查询修复 + 删除引用检测 API

- prompt_templates 查询增加 universal 类型 fallback
- agent_workshop 删除路由增加 force 参数
- 被工作流引用时返回 409 状态码和引用列表
```

---

## 批次6：feat: 前端优化（模板管理 + 流程编辑器 + 工坊管理页面）

**说明：** 修复流程编辑器中 Agent ID 显示不友好和模板为空的问题；优化工坊管理页面删除确认弹窗。

**文件列表：**
```
frontend/src/api/agentWorkshop.ts                          (+28/-... 行)
frontend/src/constants/agentLabels.ts                      (+2 行)
frontend/src/views/Settings/TemplateManagement.vue         (+48/-... 行)
frontend/src/views/Workflow/AgentStudio.vue                (+81/-... 行)
frontend/src/views/Workflow/AgentWorkshopManager.vue       (+72/-... 行)
frontend/src/views/Workflow/Editor.vue                     (+66/-... 行)
```

**主要修改内容：**
- `Editor.vue`：`loadAgentTemplates` 先试 universal 类型再 fallback 到 analysts；新增 `getAgentDisplayName` 显示中文名
- `TemplateManagement.vue`：添加"Agent工坊 → 自定义Agent（universal）"分组选项
- `agentLabels.ts`：新增 `universal: '自定义Agent'` 映射
- `agentWorkshop.ts`：新增 `WorkflowReference` 和 `DeleteWithReferencesResult` 类型；`deleteSpec`/`deleteVersion` 增加 `force` 参数
- `AgentWorkshopManager.vue`：删除确认弹窗优化——被工作流引用时显示引用列表，支持二次确认强制删除
- `AgentStudio.vue`：UI 优化

**Commit message:**
```
feat: 前端优化（模板管理 + 流程编辑器 + 工坊管理页面）

- 流程编辑器：Agent ID 显示中文名，模板查询修复
- 模板管理：新增 universal 类型分组
- 工坊管理页面：删除前显示工作流引用列表，支持强制删除
- API 层：新增 WorkflowReference 类型，deleteSpec/deleteVersion 增加 force 参数
```

---

## 批次7：refactor: 工具输出字段中文化

**说明：** 金融分析工具输出字段统一中文化，提升用户可读性。

**文件列表：**
```
core/skill_runtime/standard_financial_apis.py                    (+63/-... 行)
core/tools/implementations/fundamentals/factor_bundle_tools.py   (+17 行)
core/tools/implementations/fundamentals/financial_tools.py       (+335 行)
core/tools/implementations/fundamentals/standard_financial_tools.py (+68 行)
core/tools/implementations/market/sector_market_tools.py         (+9 行)
core/tools/implementations/market/technical_factor_bundle_tool.py (+2 行)
core/tools/implementations/risk/earnings_quality.py              (+9 行)
core/tools/implementations/risk/extended_risk_models.py          (+9 行)
core/tools/implementations/risk/fraud_signals.py                 (+6 行)
core/tools/implementations/social/stock_sentiment.py             (+9 行)
core/tools/implementations/technical/chart_patterns.py           (+9 行)
core/tools/implementations/technical/crossover_signals.py        (+2 行)
```

**Commit message:**
```
refactor: 工具输出字段中文化

统一金融分析工具（基本面/市场/风险/技术面/社交）的输出字段为中文，
提升用户可读性。
```

---

## 批次8：chore: 测试脚本更新 + 其他

**说明：** 测试脚本适配工作流重构，其他小修改。

**文件列表：**
```
scripts/test_agent_builder_graph.py                              (+270/-... 行)
tradingagents/dataflows/providers/china/tushare.py               (+2 行)
```

**Commit message:**
```
chore: 测试脚本更新 + 其他

- test_agent_builder_graph.py 适配工作流重构
- tushare.py 小修复
```

---

## 提交顺序建议

按以下顺序提交，确保依赖关系正确：

1. **批次1**（死代码清理）→ 无依赖，先提交
2. **批次2**（工作流重构）→ 依赖批次1的清理
3. **批次3**（工坊服务增强）→ 依赖批次2的工作流
4. **批次4**（ID命名优化）→ 依赖批次2和3
5. **批次5**（API修复）→ 依赖批次3和4
6. **批次6**（前端优化）→ 依赖批次5的API
7. **批次7**（工具中文化）→ 独立，可随时提交
8. **批次8**（测试脚本）→ 依赖批次2

## 提交命令示例

```bash
# 批次1
git add core/embedded_nanobot/agent/ core/embedded_nanobot/bus/ core/embedded_nanobot/command/ core/embedded_nanobot/cron/ core/embedded_nanobot/providers/ core/embedded_nanobot/security/ core/embedded_nanobot/session/ core/embedded_nanobot/utils/ core/embedded_nanobot/runtime.py core/embedded_nanobot/agent_builder_flow.py core/embedded_nanobot/__init__.py app/services/agent_builders/ tests/core/embedded_nanobot/test_runtime_hygiene.py scripts/validate_agent_builder_project_memory_loop.py scripts/validate_agent_workshop_governance_l4_l6_loop.py tests/scripts/test_validate_agent_builder_project_memory_loop.py tests/scripts/test_validate_agent_workshop_governance_l4_l6_loop.py
git commit -m "refactor: 移除 Nanobot 运行时死代码"

# 批次2
git add core/embedded_nanobot/workflows/agent_builder_nodes.py core/embedded_nanobot/workflows/agent_builder_conditions.py core/embedded_nanobot/workflows/agent_builder_graph.py core/embedded_nanobot/workflows/agent_builder_state.py core/embedded_nanobot/workflows/agent_builder_store.py app/services/embedded_nanobot_service.py app/main.py
git commit -m "refactor: Agent Builder 工作流核心重构"

# 批次3
git add app/services/agent_workshop_service.py app/services/capability_index_service.py core/memory/service.py
git commit -m "feat: Agent 工坊服务增强"

# 批次4
git add core/tools/implementations/agent_builder/nanobot_agent_builder_tools.py tests/core/tools/implementations/test_nanobot_agent_builder_tools.py
git commit -m "feat: Agent ID 命名优化 + 冗余模板清理"

# 批次5
git add app/routers/prompt_templates.py app/routers/agent_workshop.py
git commit -m "fix: 提示词模板查询修复 + 删除引用检测 API"

# 批次6
git add frontend/src/api/agentWorkshop.ts frontend/src/constants/agentLabels.ts frontend/src/views/Settings/TemplateManagement.vue frontend/src/views/Workflow/AgentStudio.vue frontend/src/views/Workflow/AgentWorkshopManager.vue frontend/src/views/Workflow/Editor.vue
git commit -m "feat: 前端优化（模板管理 + 流程编辑器 + 工坊管理页面）"

# 批次7
git add core/skill_runtime/standard_financial_apis.py core/tools/implementations/fundamentals/ core/tools/implementations/market/ core/tools/implementations/risk/ core/tools/implementations/social/ core/tools/implementations/technical/
git commit -m "refactor: 工具输出字段中文化"

# 批次8
git add scripts/test_agent_builder_graph.py tradingagents/dataflows/providers/china/tushare.py
git commit -m "chore: 测试脚本更新 + 其他"
```
