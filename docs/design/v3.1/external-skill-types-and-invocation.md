# 外部 Skill 类型与调用机制设计文档

> 本文档记录 TradingAgentsCN 项目中外部 Skill 的类型定义、调用链路、存在问题、解决方案和实施计划。
> 便于后续开发人员理解 Skill 系统的全貌，并按计划分步实施改进。

## 0. 一句话总结

项目支持 4 种 Skill 类型（knowledge/python/http/mcp），通过统一的 ToolRegistry 注册机制让 Agent 和智能助手调用。当前存在"导入后不立即生效""绑定 UI 缺失""knowledge 类型处理不当"等问题，需要分步实施改进。

---

## 1. Skill 类型定义

### 1.1 支持的类型

| 类型 | 标识 | 执行方式 | 数据来源 | 适用场景 |
|---|---|---|---|---|
| **knowledge** | `implementation=None` | 不执行，作为上下文注入提示词 | SKILL.md（YAML+Markdown） | 知识库、使用指南、领域知识 |
| **python** | `implementation.type=python` | 沙箱子进程执行 Python 代码 | SKILL.md / AI 生成 | 数据计算、业务逻辑、工具调用 |
| **http** | `implementation.type=http` | aiohttp 调用外部 API | SKILL.md / 自定义工具 | 第三方 API 集成、数据查询 |
| **mcp** | `implementation.type=mcp` | MCPClientManager 调用 MCP Server | SKILL.md / MCP 管理 | MCP 协议工具调用 |

### 1.2 数据模型

**文件**: `core/skills/models.py`

```python
class ImplementationType(str, Enum):
    PYTHON = "python"
    HTTP = "http"
    MCP = "mcp"

class PythonImplementation:
    module: str          # 模块路径
    function: str        # 函数名
    code: str           # 源代码（沙箱执行）
    is_async: bool      # 是否异步

class HttpImplementation:
    url: str            # 请求 URL（支持 {param} 占位符）
    method: str         # GET/POST/PUT/PATCH/DELETE
    headers: dict       # 请求头（支持 {{param}} 变量替换）
    body_template: str  # 请求体模板
    auth: dict          # 认证配置
    response_mapping: dict  # 响应字段映射
    timeout: int        # 超时秒数

class McpImplementation:
    server_url: str     # MCP Server URL
    tool_name: str      # MCP 工具名
    transport: str      # stdio/sse/streamable_http
```

### 1.3 SKILL.md 格式

```yaml
---
name: stock-price-query
description: 查询股票实时价格
version: 1.0.0
author: TradingAgentsCN
category: finance
tags: [stock, price, realtime]
icon: 📈
color: "#1890ff"

# Function Calling 元数据
when_to_use: "当用户需要查询股票实时价格时使用"
when_not_to_use: "查询历史 K 线数据时不要使用"
parameters:
  - name: symbol
    type: string
    description: 股票代码，如 000001.SZ
    required: true
  - name: market
    type: string
    description: 市场类型，如 A股/H股
    required: false
    default: "A股"
returns:
  type: object
  description: 包含 price, change, change_percent 的对象
examples:
  - input: {symbol: "000001.SZ"}
    output: {price: 12.34, change: 0.56, change_percent: 4.75}

# 执行实现（可选，缺失则为 knowledge 类型）
implementation:
  type: python
  code: |
    import json
    # ... Python 代码 ...
    print(json.dumps(result))

# implementation:
#   type: http
#   url: "https://api.example.com/price?symbol={symbol}"
#   method: GET
#   headers:
#     Authorization: "Bearer {{token}}"
#   response_mapping:
#     price: "$.data.price"
#     change: "$.data.change"

# implementation:
#   type: mcp
#   server_url: "http://localhost:8001/sse"
#   tool_name: "get_stock_price"
#   transport: sse

# 知识型 Skill 的 Markdown 指令
instructions: |
  ## 使用指南
  当需要查询股票价格时，请按以下步骤操作...
---

# Stock Price Query Skill

This skill provides real-time stock price query functionality...
```

---

## 2. 当前调用链路

### 2.1 应用启动时的初始化

**文件**: `app/main.py` (lifespan)

```
应用启动
├── 1. 加载 custom_tools 集合
│   └── register_custom_tool → ToolRegistry
├── 2. 加载 skills 集合 (enabled=True)
│   └── _register_skill_to_registry → ToolRegistry
│       ├── 有 code → register_single_external_skill (沙箱包装器)
│       └── 无 code → SkillExecutor.create_sync_wrapper + register_function
├── 3. 加载 external_skills 集合 (status=active)
│   └── load_external_skills_to_registry → ToolRegistry
└── 4. 恢复 MCP 服务器
    └── MCPService.restore_enabled_servers → _register_mcp_tool → ToolRegistry
```

### 2.2 Agent 调用 Skill

```
用户请求 → WorkflowEngine
├── AgentFactory.create_with_dynamic_tools(agent_id, llm)
│   ├── BindingManager.get_tools_for_agent(agent_id) → tool_ids
│   └── BaseAgent._load_tools_v2(tool_ids)
│       └── registry.get_langchain_tool(tool_id) → LangChain Tool
├── BaseAgent.invoke_with_tools(messages)
│   ├── self._llm.bind_tools(self._langchain_tools)
│   ├── LLM 返回 tool_calls
│   ├── _execute_tool_calls(tool_calls)
│   │   └── tool.invoke(tool_args)
│   │       ├── Python Skill → SkillExecutor._execute_python
│   │       │   ├── 沙箱执行 code
│   │       │   ├── 从 ToolRegistry 查找函数
│   │       │   └── 动态导入 module.function
│   │       ├── HTTP Skill → SkillExecutor._execute_http
│   │       │   └── aiohttp 发送 HTTP 请求
│   │       └── MCP Skill → SkillExecutor._execute_mcp
│   │           └── MCPClientManager.call_tool → MCP Server
│   └── 生成最终报告
```

### 2.3 智能助手调用 Skill

```
用户消息 → /api/assistant/chat
├── IntelligentAssistantService._ensure_client()
│   ├── 从 ToolRegistry 获取所有工具
│   ├── tool_metadata_list_to_openai → OpenAI 工具定义
│   └── inject_tools(tool_functions) → LLM 客户端
├── service.chat(user_message)
│   ├── 构建 system prompt + history + user message
│   └── self._llm_client.achat(messages, tools, auto_execute_tools=True)
│       └── LLM 自主选择工具调用（ReAct 模式）
│           └── 工具函数执行（同 Agent 调用链路）
└── 返回 {reply, tools_used, data_refs}
```

### 2.4 关键组件

| 组件 | 文件 | 职责 |
|---|---|---|
| ToolRegistry | `core/tools/registry.py` | 统一工具注册表，存储元数据和函数 |
| SkillExecutor | `core/skills/executor.py` | Skill 执行器，支持 python/http/mcp |
| BindingManager | `core/config/binding_manager.py` | Skill-Agent 绑定关系管理 |
| MCPClientManager | `core/tools/mcp/client_manager.py` | MCP 客户端，后台事件循环 |
| ExternalSkillLoader | `core/tools/external_skill_loader.py` | 外部 Skill 沙箱加载器 |
| IntelligentAssistantService | `app/services/intelligent_assistant_service.py` | 智能助手服务 |

---

## 3. 存在的问题

### 3.1 导入后不立即生效（严重）

**问题**: 用户导入 Skill 后，只写入 MongoDB，不主动注册到 ToolRegistry。必须重启后端才能被 Agent 调用。

**影响**: 用户体验差，导入后无法立即测试和使用。

**位置**: `app/routers/skills.py` 的所有导入端点（6 个）。

### 3.2 Skill-Agent 绑定 UI 缺失（严重）

**问题**: 后端已有 `bind-batch` API，但前端 Skill 中心没有提供绑定入口。用户不知道如何把 Skill 绑定到 Agent。

**影响**: 用户导入 Skill 后无法让 Agent 使用，Skill 系统形同虚设。

**位置**: `frontend/src/views/Workflow/SkillCenter.vue`。

### 3.3 knowledge 类型处理不当（中等）

**问题**: knowledge 类型 Skill 没有可执行代码，但当前逻辑会尝试注册到 ToolRegistry。LLM 看到工具会尝试调用，导致失败。

**影响**: knowledge 类型 Skill 应该作为提示词上下文注入，而不是作为可调用工具。

**位置**: `app/routers/skills.py` 的 `_register_skill_to_registry`、`core/agents/base.py`。

### 3.4 MCP Skill 管理割裂（中等）

**问题**: MCP Skill 有两个入口：
- SKILL.md 中定义 `implementation.type=mcp`（Skill 中心导入）
- MCP 管理页面添加 MCP Server（自动发现工具）

两者注册到 ToolRegistry 的 `tool_id` 格式不同，容易混淆。

**影响**: 用户难以理解两条路径的区别，维护成本高。

### 3.5 导入反馈不完整（中等）

**问题**: 导入成功后只显示"导入成功"，不提示下一步操作（测试、绑定）。

**影响**: 用户不知道导入后还需要绑定才能生效。

### 3.6 测试逻辑不区分类型（已修复）

**问题**: 已在上一轮修复，测试逻辑现在区分 knowledge 和 executable 类型。

---

## 4. 解决方案

### 4.1 方案 1：导入后立即生效（P0）

**目标**: 导入 Skill 后立即注册到 ToolRegistry，无需重启。

**实现**:

```python
# app/routers/skills.py - 所有导入端点
async def import_skill(...):
    # ... 现有逻辑：解析、存储 ...
    
    # 新增：立即注册到 ToolRegistry
    await _register_skill_to_registry(skill_doc)
    
    return {
        "success": True, 
        "message": "导入成功并已生效",
        "skill_id": skill_doc["name"],
        "skill_type": skill_doc.get("implementation", {}).get("type", "knowledge") if skill_doc.get("implementation") else "knowledge"
    }
```

**涉及端点**:
- `POST /api/skills/import`
- `POST /api/skills/import-url`
- `POST /api/skills/import-file`
- `POST /api/skills/import-skillhub`
- `POST /api/skills/import-github`
- `POST /api/skills/import-agenthub`

**验证**: 导入后立即在 ToolRegistry 中查询，应能找到该工具。

### 4.2 方案 2：完善 Skill-Agent 绑定 UI（P0）

**目标**: 在 Skill 中心提供"绑定 Agent"操作，引导用户完成绑定。

**实现**:

前端新增：
- Skill 列表每项增加"绑定"按钮
- 绑定弹窗：多选 Agent + 优先级设置
- 绑定状态展示：显示已绑定的 Agent 数量

后端复用：
- `POST /api/skill-center/skills/{skill_id}/bind-batch`（已存在）
- `GET /api/skill-center/skills/{skill_id}/bindings`（已存在）

**涉及文件**:
- `frontend/src/views/Workflow/SkillCenter.vue` — 增加"绑定"按钮和弹窗
- `frontend/src/api/skillCenter.ts` — 调用绑定 API（已有，补充类型）
- `app/routers/skill_center.py` — 已有端点，无需修改

**验证**: 绑定后，Agent 执行时能加载到该 Skill。

### 4.3 方案 3：knowledge 类型正确处理（P1）

**目标**: knowledge 类型 Skill 不注册为可调用工具，而是作为提示词上下文注入。

**实现**:

```python
# app/routers/skills.py - _register_skill_to_registry
async def _register_skill_to_registry(doc: Dict[str, Any]):
    impl = doc.get("implementation")
    
    # 新增：knowledge 类型不注册为工具
    if not impl:
        logger.info(f"Skill '{doc.get('name')}' 是知识型，不注册为可调用工具")
        return
    
    # ... 原有注册逻辑 ...
```

```python
# core/agents/base.py - _get_prompt_from_template
def _get_prompt_from_template(self, ...):
    prompt = super()._get_prompt_from_template(...)
    
    # 新增：注入已绑定的 knowledge Skill
    knowledge_skills = self._load_bound_knowledge_skills()
    if knowledge_skills:
        prompt += "\n\n## 可用知识库\n"
        for skill in knowledge_skills:
            prompt += f"\n### {skill['name']}\n{skill.get('instructions', '')}\n"
    
    return prompt

def _load_bound_knowledge_skills(self) -> List[Dict]:
    """加载绑定到当前 Agent 的 knowledge 类型 Skill"""
    # 从 BindingManager 获取绑定的 tool_ids
    # 从 skills 集合查询 implementation=None 的 Skill
    # 返回 [{name, instructions, description}]
    ...
```

**涉及文件**:
- `app/routers/skills.py` — `_register_skill_to_registry` 跳过 knowledge 类型
- `core/agents/base.py` — `_get_prompt_from_template` 注入 knowledge Skill
- `frontend/src/views/Workflow/SkillCenter.vue` — UI 标注类型和生效方式

**验证**: knowledge 类型 Skill 不出现在 ToolRegistry，但 Agent 提示词中包含其内容。

### 4.4 方案 4：统一 MCP Skill 管理（P1）

**目标**: 保留两条路径，但统一命名规范和 UI 展示。

**实现**:

命名规范：
- SKILL.md 的 MCP Skill：`skill_{name}`（与其他 Skill 一致）
- MCP 管理的 MCP 工具：`mcp_{server_id}_{tool_name}`（保持不变）

UI 展示：
- Skill 中心：显示 SKILL.md 导入的 MCP Skill，来源标注"SKILL.md"
- MCP 管理页面：显示 MCP Server 自动发现的工具，来源标注"MCP Server"
- 两者都标注"协议: MCP"

**涉及文件**:
- `frontend/src/views/Workflow/SkillCenter.vue` — 增加来源标注
- `frontend/src/views/Workflow/McpServers.vue` — 增加来源标注

**验证**: 两个入口的 MCP 工具都能被 Agent 调用，UI 清晰区分来源。

### 4.5 方案 5：导入流程引导（P1）

**目标**: 导入成功后，弹出引导提示，指引用户完成后续操作。

**实现**:

```vue
<!-- SkillCenter.vue -->
<el-dialog v-model="importSuccessVisible" title="导入成功">
  <div class="import-success">
    <el-result icon="success" title="Skill 导入成功">
      <template #sub-title>
        Skill 已立即生效，接下来请完成绑定以让 Agent 使用
      </template>
    </el-result>
    
    <div class="next-steps">
      <h4>下一步</h4>
      <ol>
        <li>[可选] 测试 Skill 是否正常工作</li>
        <li>[必需] 绑定到 Agent — 让 Agent 能调用此 Skill</li>
        <li>[可选] 绑定到智能助手 — 让智能助手能调用此 Skill</li>
      </ol>
    </div>
  </div>
  <template #footer>
    <el-button @click="importSuccessVisible = false">稍后</el-button>
    <el-button type="primary" @click="goToBind">立即绑定</el-button>
  </template>
</el-dialog>
```

**涉及文件**:
- `frontend/src/views/Workflow/SkillCenter.vue` — 导入成功回调

**验证**: 导入后弹出引导，点击"立即绑定"跳转到绑定弹窗。

---

## 5. 实施计划

### 5.1 阶段 1（P0，必须完成）

| 任务 | 方案 | 涉及文件 | 验证 |
|---|---|---|---|
| 导入后立即生效 | 方案 1 | `app/routers/skills.py` | 导入后 ToolRegistry 立即有该工具 |
| Skill-Agent 绑定 UI | 方案 2 | `frontend/src/views/Workflow/SkillCenter.vue` | 绑定后 Agent 能加载 Skill |

### 5.2 阶段 2（P1，建议完成）

| 任务 | 方案 | 涉及文件 | 验证 |
|---|---|---|---|
| knowledge 类型处理 | 方案 3 | `app/routers/skills.py`、`core/agents/base.py` | knowledge Skill 注入提示词 |
| 导入流程引导 | 方案 5 | `frontend/src/views/Workflow/SkillCenter.vue` | 导入后弹出引导 |

### 5.3 阶段 3（P1，可选）

| 任务 | 方案 | 涉及文件 | 验证 |
|---|---|---|---|
| 统一 MCP Skill 管理 | 方案 4 | `frontend/src/views/Workflow/SkillCenter.vue`、`McpServers.vue` | UI 清晰区分来源 |

---

## 6. 关键文件索引

| 文件 | 职责 |
|---|---|
| `core/skills/models.py` | Skill 数据模型 |
| `core/skills/parser.py` | SKILL.md 解析器 |
| `core/skills/executor.py` | Skill 执行器（python/http/mcp） |
| `app/routers/skills.py` | Skill 管理 API（导入、测试、注册） |
| `app/routers/skill_center.py` | Skill 中心 API（绑定、日志） |
| `core/tools/registry.py` | 工具注册表 |
| `core/tools/external_skill_loader.py` | 外部 Skill 沙箱加载器 |
| `core/tools/custom_tool.py` | 自定义 HTTP 工具 |
| `core/tools/fc_converter.py` | 工具元数据转 OpenAI 格式 |
| `core/tools/mcp/client_manager.py` | MCP 客户端管理器 |
| `app/services/mcp_service.py` | MCP 服务 |
| `core/agents/base.py` | Agent 基类（工具加载、执行） |
| `core/config/binding_manager.py` | Skill-Agent 绑定管理 |
| `app/services/intelligent_assistant_service.py` | 智能助手服务 |
| `app/main.py` | 应用启动（Skill 初始化） |
| `frontend/src/views/Workflow/SkillCenter.vue` | Skill 中心前端 |
| `frontend/src/api/skillCenter.ts` | Skill 中心前端 API |
| `frontend/src/api/skills.ts` | Skill 前端 API |

---

## 7. 注意事项

1. **向后兼容**: 所有修改不能破坏现有 Skill 的可用性。
2. **性能**: 导入后立即注册不应阻塞 API 响应，注册失败不应导致导入失败。
3. **错误处理**: 注册失败时记录日志，但不影响导入成功状态。
4. **测试**: 每个阶段完成后，需要验证现有功能不受影响。
5. **文档**: 实施过程中更新本文档的"实施记录"章节。

---

## 8. 实施记录

> 本章节在实施过程中逐步更新，记录每个阶段的完成情况。

### 阶段 1：导入后立即生效 + 绑定 UI

**状态**: ✅ 已完成

**实施内容**:
- [x] 方案 1：导入后立即生效
  - 修复 `_register_skill_to_registry` 的 bug：原先 `if not impl or not params: return` 会跳过无参数的可执行 Skill
  - knowledge 类型（无 implementation）不再注册为可调用工具，改为通过提示词注入
  - 所有 6 个导入端点已调用 `_register_skill_to_registry`（原有代码已实现）
- [x] 方案 2：Skill-Agent 绑定 UI
  - 前端已有完整的绑定弹窗（`bindDialogVisible`、`handleBindAgent`、`confirmBatchBind`）
  - 支持多选 Agent、设置优先级、查看已绑定 Agent、解绑
  - 导入成功后自动弹出绑定对话框（`handleSkillImported`）

**额外完成**:
- [x] 方案 3：knowledge 类型正确处理
  - `_register_skill_to_registry` 跳过 knowledge 类型
  - `core/agents/base.py` 新增 `_load_bound_knowledge_skills` 方法
  - `_get_prompt_from_template` 自动注入已绑定的 knowledge Skill 内容
- [x] 方案 5：导入流程引导
  - `handleSkillImported` 已实现导入后自动弹出绑定对话框

**验证结果**:
- [x] 导入后 ToolRegistry 立即有该工具（可执行类型）
- [x] 绑定后 Agent 能加载 Skill
- [x] knowledge 类型 Skill 不注册为工具，但通过提示词注入
- [x] 导入后自动弹出绑定对话框

**涉及文件**:
- `app/routers/skills.py` — 修复 `_register_skill_to_registry` 逻辑
- `core/agents/base.py` — 新增 `_load_bound_knowledge_skills` 方法，提示词注入 knowledge Skill

### 阶段 2：knowledge 类型处理 + 导入引导

**状态**: ✅ 已在阶段 1 完成

**实施内容**:
- [x] 方案 3：knowledge 类型正确处理（见阶段 1）
- [x] 方案 5：导入流程引导（见阶段 1）

### 阶段 3：统一 MCP Skill 管理

**状态**: 待实施

**实施内容**:
- [ ] 方案 4：统一 MCP Skill 管理

**验证结果**:
- [ ] UI 清晰区分来源
