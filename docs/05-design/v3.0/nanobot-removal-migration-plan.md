# Nanobot 移除迁移方案

> 生成时间：2026-07-01
> 状态：可行性分析完成，待审核
> 上次更新：2026-07-01 — 补充可行性分析、接口差异、风险分级

## 一、背景

### 1.1 问题

Agent Builder（Agent 生成工坊）反复出现 LLM 输出的工具调用 XML 泄露给用户的问题。尽管多次修复（`_parse_text_tool_calls` 4 种格式解析、`_strip_tool_call_xml` 4 种正则清洗、强制兜底调用），问题仍然存在。

根因：Nanobot 的 ReAct 循环不使用标准 Function Calling 协议，而是把工具定义写成文字塞进 system prompt，让 LLM 用 `<invoke>` / `<｜｜DSML｜｜>` 等标签"模拟"工具调用，再用正则解析文本。这 fundamentally 不可靠。

### 1.2 对比

智能助手（`IntelligentAssistantService`）使用 `UnifiedLLMClient.achat(auto_execute_tools=True)` 走标准 OpenAI Function Calling 协议，从没有 XML 泄露问题。

### 1.3 结论

Nanobot 在本项目中的所有能力都有更好的替代方案，可以完全移除。

---

## 二、Nanobot 能力逐项审计

### 2.1 Nanobot 目录结构

```
core/embedded_nanobot/
├── __init__.py                          # 导出 InboundMessage/OutboundMessage/MessageBus/TradingAgentsLLMProvider
├── runtime.py                           # EmbeddedNanobotRuntime（~2700 行）
├── intent_context.py                    # IntentContext/IntentStage/IntentAction
├── agent_builder_flow.py                # FlowPhase 状态机（已被 LangGraph 替代）
├── agent/
│   ├── context.py                       # ContextBuilder（AGENTS.md/SOUL.md）
│   ├── context_injection_policy.py      # InjectionPolicy
│   ├── hook.py                          # AgentHook
│   ├── memory.py                        # MemoryStore/MemoryConsolidator
│   ├── runner.py                        # AgentRunner.run（经典 ReAct）
│   ├── skills.py                        # SkillsLoader
│   └── tools/
│       ├── base.py                      # Tool 抽象基类
│       ├── filesystem.py                # ReadFile/WriteFile/EditFile/ListDir
│       ├── shell.py                     # ExecTool
│       ├── web.py                       # WebSearch/WebFetch
│       ├── tradingagents_bridge.py      # TradingAgentsRegistryTool
│       └── registry.py                  # ToolRegistry
├── bus/
│   ├── events.py                        # InboundMessage/OutboundMessage
│   └── queue.py                         # MessageBus
├── command/
│   ├── router.py                        # CommandRouter
│   └── builtin.py                       # /stop /status /new /help
├── cron/
│   ├── types.py                         # CronJob/CronSchedule
│   └── service.py                       # CronService
├── providers/
│   ├── base.py                          # LLMProvider 抽象
│   └── unified.py                       # TradingAgentsLLMProvider
├── security/network.py                  # URL 校验
├── session/manager.py                   # Session/SessionManager（JSONL）
├── utils/helpers.py                     # 工具函数
└── workflows/                           # ← 我们自己写的 LangGraph 工作流
    ├── agent_builder_state.py
    ├── agent_builder_store.py
    ├── agent_builder_graph.py
    ├── agent_builder_nodes.py
    └── agent_builder_conditions.py
```

### 2.2 Agent Builder 路径依赖的 Nanobot 能力

| Nanobot 能力 | 是否用到 | 能否替代 | 替代方案 |
|---|---|---|---|
| `_run_react_loop`（文本 XML 工具调用） | ✅ 核心依赖 | ✅ | `UnifiedLLMClient.achat(auto_execute_tools=True)` |
| `_parse_text_tool_calls`（4 种格式解析） | ✅ 被上面调用 | ✅ | 标准 Function Calling 不需要文本解析 |
| `_strip_tool_call_xml`（XML 清洗） | ✅ 被上面调用 | ✅ | 标准 FC 不产生 XML |
| `_build_force_call_params`（强制兜底） | ✅ 被上面调用 | ⚠️ 需迁移 | 逻辑保留，改为代码直接调工具 |
| `TradingAgentsLLMProvider`（LLM 桥接） | ✅ 所有节点用 | ✅ | 直接用 `UnifiedLLMClient` |
| Nanobot `ToolRegistry`（工具注册表） | ✅ 节点用 | ✅ | `core.tools.registry`（已存在） |
| `EmbeddedNanobotRuntime.handle_message` | ✅ 路由层调 | ✅ | 直接调 `execute_graph()` |

### 2.3 关键接口差异（实际代码验证）

#### 2.3.1 `TradingAgentsLLMProvider` 不是薄包装

```python
class TradingAgentsLLMProvider(LLMProvider):
    def __init__(self, client: UnifiedLLMClient, model: str):
        self.client = client  # ← 内部已经持有 UnifiedLLMClient
        self._default_model = model

    async def chat(self, messages, tools, model, ...):
        # _convert_messages: dict → Message (Pydantic)
        response = await self.client.achat(
            self._convert_messages(messages),  # ← 消息格式转换
            tools=tools,
            auto_execute_tools=False,          # ← 不自动执行工具
            ...
        )
```

**关键发现**：`TradingAgentsLLMProvider` 内部已经用 `UnifiedLLMClient`。去掉它意味着直接调用 `UnifiedLLMClient.achat()`，只需要做两件事：
- 消息格式转换：`dict` → `Message` Pydantic 对象（`_convert_messages` 逻辑）
- 流式输出的 `on_content_delta` 回调

#### 2.3.2 `UnifiedLLMClient.achat()` vs `astream()` — 流式+工具无法同时使用

| 方法 | 返回值 | auto_execute_tools | 流式输出 |
|---|---|---|---|
| `achat()` | `LLMResponse` (完整) | ✅ 支持 | ❌ 不支持（返回完整结果） |
| `astream()` | `AsyncIterator[str]` | ❌ 不支持 | ✅ 支持（逐 token yield） |

**这是最大的技术差距**。当前 `_run_react_loop` 做的是：
1. Step 1：非流式调 LLM（返回 `tool_calls`）→ 流式推送 thought 文本 → 执行工具
2. Step 2：流式调 LLM → 逐 token 推送最终回复

`UnifiedLLMClient.achat(auto_execute_tools=True)` 能完成 Step 1 + 工具执行，但工具执行期间的 token 不会流式输出。Step 2 需要用 `astream()` 单独实现。

#### 2.3.3 `tool_choice="required"` 是配置级，非调用级

```python
# LLMConfig 中的字段，不是 achat() 的参数
config = LLMConfig.from_env(LLMProvider.DEEPSEEK)
config.tool_choice = "required"  # ← 必须在建 client 时设置
client = UnifiedLLMClient.from_config(config)
```

每个节点需要不同的 required tool，这意味着要么每个节点建新 client，要么不用 `tool_choice` 而是手动检查。

#### 2.3.4 工具 Schema 格式不同

| | Nanobot Tool | UnifiedLLMClient 期望 |
|---|---|---|
| 格式 | `{"name": "...", "description": "...", "parameters": {...}}` | `{"type": "function", "function": {"name": "...", "description": "...", "parameters": {...}}}` |
| 获取方式 | `tool.to_schema()` | `ToolCallNormalizer.normalize_tool_definition(fn)` |

需要格式转换层。

#### 2.3.5 SSE 事件格式表（完整对比）

当前路由层的 SSE 事件机制（`c:\TradingAgentsCN\app\routers\embedded_nanobot.py`）：

```
路由层创建 asyncio.Queue → 4 个回调 → service.chat() → runtime.handle_message() → _run_agent_builder_graph()
                                                                                          ↓
                                                                              graph 节点通过 state["_event_callback"] / state["_on_stream"]
                                                                              调用 emit() → queue.put() → _sse_event() → yield to SSE stream
```

事件类型映射：

| SSE 事件 | 来源 | 数据结构 |
|---|---|---|
| `started` | 路由层 `emit("started", ...)` | `{"message": "助手已开始处理请求", "session_key": ...}` |
| `progress` | runtime `event_callback("progress", ...)` | `{"message": "正在分析需求...", "session_key": ...}` |
| `token` | runtime `on_stream(delta)` → `emit("token", ...)` | `{"content": delta, "session_key": ...}` |
| `tool_event` | runtime `event_callback("tool", ...)` / `("tool_done", ...)` | `{"name": ..., "status": "running"/"completed"/"error", "label": ...}` |
| `step_event` | runtime `event_callback("step", ...)` | `{"step": ..., "status": "completed", "title": ..., "detail": ...}` |
| `done` | 路由层 `emit("done", ...)` | `{"content": ..., "tools_used": [...], "stop_reason": "completed"}` |
| `error` | 路由层 `emit("error", ...)` | `{"message": str(exc), "session_key": ...}` |

`UnifiedLLMClient` 的 `progress_callback` 事件类型完全不同：

| UnifiedLLMClient 事件 | 说明 |
|---|---|
| `llm_initial_response` | 首次 LLM 响应 |
| `tool_round_started` | 工具轮次开始 |
| `tool_started` | 单个工具开始执行 |
| `tool_completed` | 单个工具执行完毕 |
| `tool_round_completed` | 工具轮次完成 |
| `llm_tool_response` | 工具后的 LLM 响应 |
| `tool_limit_reached` | 达到最大轮次限制 |
| `tool_limit_summary_completed` | 强制总结完成 |
| `llm_final_response` | 最终 LLM 响应 |

**需要事件适配层**将 UnifiedLLMClient 事件翻译为前端期望的 SSE 格式。

### 2.4 Agent Builder 路径不用的 Nanobot 能力

| Nanobot 能力 | 状态 | 说明 |
|---|---|---|
| `AgentRunner.run`（经典 ReAct） | ❌ 不用 | Agent Builder 走 LangGraph |
| `Session/SessionManager`（JSONL 会话） | ❌ 不用 | Agent Builder 用 MongoDB checkpoint |
| `ContextBuilder`（AGENTS.md/SOUL.md） | ❌ 不用 | Agent Builder 有自己的节点提示词 |
| `MemoryStore/MemoryConsolidator` | ❌ 不用 | InjectionPolicy 已对 Agent Builder 禁用 |
| `CommandRouter`（/stop /status /new） | ❌ 不用 | Agent Builder 不支持命令 |
| `CronService` | ❌ 不用 | 无关 |
| 文件/Shell/Web 工具 | ❌ 不用 | `include_inspect_tools=False` 已全部关闭 |
| `SkillsLoader` | ❌ 不用 | Agent Builder 不加载 SKILL.md |
| `IntentContext`（跨轮意图上下文） | ⚠️ 工具层引用 | Agent Builder 有自己的 `message_history` + 意图分类 |
| `FlowPhase`（流程状态机） | ⚠️ 旧逻辑 | LangGraph 状态机已替代 |
| `InjectionPolicy`（上下文注入策略） | ⚠️ 旧逻辑 | Agent Builder 节点提示词自己控制 |

---

## 三、Channel 使用情况

### 3.1 活跃 Channel

| channel 值 | 调用方 | 走哪条路径 | 是否需要 Nanobot |
|---|---|---|---|
| `agent_workshop` | AgentStudio.vue + AgentWorkshop.vue 前端 | LangGraph（我们的代码） | ❌ 不需要 |
| `api` | Debug/EmbeddedNanobot.vue 调试页 | 经典 ReAct（AgentRunner） | ⚠️ 调试用 |
| `agent_workshop_evaluation` | 后端 agent_workshop_service.py 评估 worker | 经典 ReAct（AgentRunner） | ⚠️ 后端用 |
| `embedded` | EmbeddedNanobotBuilderProvider | 经典 ReAct（AgentRunner） | ⚠️ 半活跃 |

### 3.2 死代码 Channel

| channel 值 | 说明 |
|---|---|
| `agent_workshop_worker` | 仅在 `_is_internal_worker_channel` 过滤集合中出现，无任何发送方 |
| `general` / `preview` / `skill_creation` | 代码库中不存在 |

### 3.3 调用路径（代码级展开）

**路径 A：Agent 工坊主对话（最活跃路径）**
```
前端 AgentStudio.vue / AgentWorkshop.vue
  → embeddedNanobotApi.chatStream({ channel: 'agent_workshop', ... })
  → POST /api/embedded-nanobot/chat/stream

  ←── SSE 事件循环 ──→
  路由层 embedded_nanobot_chat_stream():
    创建 asyncio.Queue
    定义 emit(event, payload) → queue.put() → _sse_event() → yield SSE
    定义 on_progress / on_stream / on_tool_event / on_step_event 回调
    ↓
    service.chat(channel="agent_workshop", 
                 on_progress=on_progress, on_stream=on_stream,
                 on_tool_event=on_tool_event, on_step_event=on_step_event)
      ↓
      runtime.handle_message(channel="agent_workshop")
        → _run_agent_builder_graph()
          → execute_graph(state, tool_registry=self.tools, provider=self.provider, model=self.model)
            → state["_tool_registry"] = tool_registry
            → state["_provider"] = provider          # ← Nanobot 依赖
            → state["_model"] = model                 # ← Nanobot 依赖
            → graph.ainvoke(state)
              → node 读 state["_provider"] 调 LLM   # ← 节点用 provider
              → node 读 state["_tool_registry"] 执行工具
```

**路径 B：调试页对话**
```
前端 Debug/EmbeddedNanobot.vue
  → embeddedNanobotApi.chatStream({ channel: 'api', ... })
  → POST /api/embedded-nanobot/chat/stream
  → runtime.handle_message(channel="api")
  → AgentRunner.run()  ← Nanobot 经典 ReAct
```

**路径 C：评估 Worker（后端内部）**
```
AgentWorkshopService._run_nanobot_evidence_worker_task
  → EmbeddedNanobotService.chat(channel="agent_workshop_evaluation")
  → runtime.handle_message(channel="agent_workshop_evaluation")
  → AgentRunner.run()  ← Nanobot 经典 ReAct
```

**路径 D：EmbeddedNanobotBuilderProvider**
```
EmbeddedNanobotBuilderProvider.clarify_requirements / analyze_gaps / plan_tooling / build_draft
  → runtime.handle_message(channel="embedded" 默认)
  → AgentRunner.run()  ← Nanobot 经典 ReAct
```

---

## 四、可行性分析 — 接口差异与适配方案

### 4.1 差距 1：非流式 `achat()` 替代双阶段 ReAct 循环（风险等级：中）

**问题**：`_run_react_loop` 分 Step 1（非流式 → 执行工具）和 Step 2（流式 → 推送给用户）。`UnifiedLLMClient.achat(auto_execute_tools=True)` 一次性完成"LLM 思考 → 调工具 → LLM 总结"，但不流式推送任何 token。

**当前用户体验**：
```
[正在分析需求...]           ← progress 事件
[思考文本流式出现...]        ← token 事件 (Step 1 thought)
[执行：xxx_tool]            ← tool_event
[完成：xxx_tool]            ← tool_event
[正在分析结果...]           ← progress 事件
[最终回复流式出现...]        ← token 事件 (Step 2 final)
```

**替换后用户体验**：
```
[执行：xxx_tool]            ← progress_callback → tool_started
[完成：xxx_tool]            ← progress_callback → tool_completed
[最终回复完整出现]           ← 非流式，一次性
```

**适配方案**：工具执行后，对最终 `LLMResponse.content` 做分块流式推送（模拟流式效果，类似智能助手的 40 字符分块）。

**风险**：用户等待时间略长（工具执行期间无文字输出），但 XML 泄露彻底消除。

### 4.2 差距 2：`_build_force_call_params` 必须保留（风险等级：高）

当前代码中 7 个工具都有专门的参数提取逻辑：

| 工具 | 从 state 提取的参数 | 代码行 |
|---|---|---|
| `prepare_agent_requirement_intake` | `user_request` | ~4 行 |
| `prepare_agent_generation_confirmation` | `agent_id`, `agent_name`, `target_responsibility`, `tool_ids` | ~25 行 |
| `analyze_agent_workshop_gaps` | `agent_id`, `agent_name`, `target_responsibility` | ~8 行 |
| `propose_agent_build_plans` | `gap_report_json`, `agent_responsibility` | ~8 行 |
| `generate_confirmed_candidate_agent` | `responsibility`, `selected_plan_id`, `tool_ids` (from gap_report existing_tools/suggested_tools) | ~50 行 |
| `build_agent_workshop_version` | （在 `_build_force_call_params` 第 672+ 行继续） | — |
| `run_agent_workshop_real_data_test` | `version_id`, `test_symbol` | — |

**适配方案**：保留 `_build_force_call_params` 函数。新流程改为：

```python
# 方案：代码先调工具 → LLM 总结结果
tool_params = _build_force_call_params(required_tool_name, state)
result = await tool_registry.execute(required_tool_name, tool_params)
# 将结果写入 state
state["tool_result"] = result
# 用 LLM 总结（非流式 → 分块推送）
messages = [{"role": "system", "content": summary_prompt + f"\n工具结果: {result}"}]
response = await llm_client.achat(messages)
stream_chunked(response.content, on_stream)
```

**重要**：不再需要 LLM 决策调哪个工具。每个节点就知道自己该调什么。这从根本上消除了 XML 泄露的根因。

### 4.3 差距 3：`node_classify_user_intent` 用 `provider.chat_with_retry`（风险等级：低）

`node_classify_user_intent` 是最简单的 LLM 调用场景：输入 system prompt + 当前消息，输出 JSON。

**适配方案**：直接替换为 `UnifiedLLMClient.achat()`。

```python
# 当前
response = await provider.chat_with_retry(messages=messages, model=model, temperature=0.0)

# 替换
messages = [Message(role=MessageRole.USER, content=classify_prompt)]
response = await llm_client.achat(messages, temperature=0.0)
raw = response.content or ""
```

### 4.4 差距 4：工具 Schema 格式转换（风险等级：低）

```python
# Nanobot 格式
schema = tool.to_schema()  # {"name": "xxx", "description": "...", "parameters": {...}}

# OpenAI Function Calling 格式
openai_schema = {
    "type": "function",
    "function": {
        "name": schema["name"],
        "description": schema["description"],
        "parameters": schema["parameters"],
    }
}
```

**适配方案**：添加 `_to_openai_tool_schema(tool)` 辅助函数。

### 4.5 差距 5：`execute_graph()` 签名变更（风险等级：中）

```python
# 当前签名
async def execute_graph(
    graph, state, tool_registry, provider, model,  # ← provider + model
    event_callback=None, on_stream=None, max_steps=10,
)

# 新签名
async def execute_graph(
    graph, state, tool_registry, llm_client,  # ← UnifiedLLMClient
    event_callback=None, on_stream=None, max_steps=10,
)
```

**适配方案**：
- `state["_llm_client"]` 替代 `state["_provider"]` + `state["_model"]`
- 节点内部从 `state.get("_llm_client")` 获取客户端
- `_make_node_wrapper` 的 `param_names` 匹配自动适应（注入 `llm_client` 而非 `provider` + `model`）

### 4.6 差距 6：SSE 事件适配（风险等级：低）

不需要改前端。只需在 graph 层面维持现有 SSE 事件格式。

**适配方案**：
- `progress_callback` → 映射为 `tool_started`/`tool_completed` → `emit("tool_event", ...)`
- 工具执行前的"正在分析需求..." → `emit("progress", ...)`
- 最终文本分块推送 → `emit("token", ...)`

---

## 五、迁移计划（更新后）

### 阶段 1：替换 agent_workshop 路径（解决 XML 泄露）

**目标**：`agent_workshop` channel 不再经过 Nanobot Runtime，直接用 `UnifiedLLMClient` + 代码控制工具执行。

**核心策略**：工具先跑 → 结果写入 state → LLM 总结 → 分块流式推送。不再让 LLM 决策调哪个工具。

**改动范围**：

| 文件 | 改动 |
|---|---|
| `core/embedded_nanobot/workflows/agent_builder_nodes.py` | 新增 `_run_node_tool_first()` 替代 `_run_node_llm()` + `_run_react_loop()`；保留 `_build_force_call_params`；删除 `_parse_text_tool_calls`、`_strip_tool_call_xml`、ReAct 相关代码；新增 `_to_openai_tool_schema()`；`node_classify_user_intent` 改用 `UnifiedLLMClient` |
| `core/embedded_nanobot/workflows/agent_builder_state.py` | `_provider` / `_model` → `_llm_client: Optional[UnifiedLLMClient]` |
| `core/embedded_nanobot/workflows/agent_builder_graph.py` | `execute_graph` 签名变更：`provider, model` → `llm_client`；`_make_node_wrapper` 注入 `llm_client` |
| `core/embedded_nanobot/workflows/agent_builder_conditions.py` | 无改动 |
| `core/embedded_nanobot/workflows/agent_builder_store.py` | 无改动 |
| `app/services/embedded_nanobot_service.py` | `agent_workshop` channel 跳过 `runtime.handle_message`，直接调 `execute_graph` |
| `app/routers/embedded_nanobot.py` | 无改动 |

**新增函数**：

```python
async def _run_node_tool_first(
    state, system_prompt, tool_registry, llm_client,
    required_tool_name, include_inspect_tools=False,
    event_callback=None, on_stream=None,
) -> Tuple[str, List[Dict], Dict]:
    """工具先行模式：代码调工具 → LLM 总结 → 分块流式推送
    不再让 LLM 决策调哪个工具，从根本上消除 XML 泄露。
    """
    # 1. 构建工具参数
    tool_params = _build_force_call_params(required_tool_name, state)
    
    # 2. 执行工具
    await _emit_event(event_callback, "tool", f"执行：{required_tool_name}")
    result = await tool_registry.execute(required_tool_name, tool_params)
    await _emit_event(event_callback, "tool_done", f"完成：{required_tool_name}")
    
    tool_events = [{"name": required_tool_name, "params": tool_params, "status": "ok"}]
    
    # 3. LLM 总结（非流式）
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"工具 {required_tool_name} 已执行，结果:\n{str(result)[:4000]}"},
    ]
    
    await _emit_event(event_callback, "progress", "正在分析结果...")
    response = await llm_client.achat(
        [_convert_message(msg) for msg in messages],
        temperature=0.3,
    )
    
    # 4. 分块流式推送（模拟流式效果）
    final_text = response.content or ""
    chunk_size = 40
    for i in range(0, len(final_text), chunk_size):
        chunk = final_text[i:i+chunk_size]
        if on_stream:
            asyncio.ensure_future(_invoke_stream(on_stream, chunk))
        await asyncio.sleep(0.01)  # 给前端渲染时间
    
    return final_text, tool_events, {required_tool_name: str(result)}
```

**删除清单**：
- `_run_react_loop`（~250 行，含 Step1/Step2/force-call/兜底重试）
- `_parse_text_tool_calls`（~100 行，4 种格式正则解析）
- `_strip_tool_call_xml`（~30 行，4 种正则清洗）
- 正则常量：`_DSML_PATTERN` / `_INVOKE_PATTERN` / `_TOOL_CALL_PATTERN` / `_JSON_TOOL_PATTERN` / `_TOOL_CALL_STRIP_PATTERNS`
- `_run_node_llm` 中 tool_defs 的 Nanobot 格式构建逻辑

**保留清单**：
- `_build_force_call_params`（~120 行，7 个工具的参数提取，逻辑完全保留）
- `_emit_event` / `_invoke_stream`
- `node_classify_user_intent`（签名改 `llm_client` 替代 `provider` + `model`）
- `_extract_json_from_result`
- 所有 `_build_*_prompt` 函数

**验证**：
- 165 个现有测试通过（需适配 runtime 注入变更）
- 前端 AgentStudio 创建 Agent 全流程，不再出现 XML 泄露
- 8 个节点的工具调用成功率 100%
- 分块流式推送的 token 事件正常（前端可见打字效果）
- `logs/intent_classify_prompts.log` 正常记录

---

### 阶段 2：替换 api 调试页路径

**目标**：`api` channel 不再经过 Nanobot Runtime，直接用 `UnifiedLLMClient`。

**改动范围**：

| 文件 | 改动 |
|------|------|
| `app/services/embedded_nanobot_service.py` | `api` channel 时，走 `UnifiedLLMClient.achat(auto_execute_tools=True)` + 全量工具注入 |
| `app/routers/embedded_nanobot.py` | 无改动 |
| `frontend/src/views/Debug/EmbeddedNanobot.vue` | 无改动（channel 值透传） |

**新增**：
- `_run_simple_chat(user_message, history, llm_client, tool_registry)` — 类似智能助手的 `_do_chat()`，注入全量工具 + `auto_execute_tools=True`
- `progress_callback` → SSE 事件适配

**保留**：
- 文件/Shell/Web 工具注册到 `core.tools.registry`（如果调试页需要）

---

### 阶段 3：替换评估 Worker 路径

**目标**：`agent_workshop_evaluation` channel 不再经过 Nanobot Runtime。

**改动范围**：

| 文件 | 改动 |
|------|------|
| `app/services/agent_workshop_service.py` | `_run_nanobot_evidence_worker_task` 改为直接调 `UnifiedLLMClient.achat()` |
| `app/services/embedded_nanobot_service.py` | `agent_workshop_evaluation` channel 路由到新路径 |

**注意事项**：
- Worker 需要全量工具注入（包括文件/Shell/Web 工具 + agent workshop 工具）
- ContextBuilder 逻辑需要内联为 system prompt
- 结果持久化逻辑不变（MongoDB 消息存储）

---

### 阶段 4：替换 EmbeddedNanobotBuilderProvider 路径

**目标**：`embedded` channel 不再经过 Nanobot Runtime。

**改动范围**：

| 文件 | 改动 |
|------|------|
| `app/services/agent_builders/embedded_nanobot_builder.py` | `_call_nanobot` 改为直接调 `UnifiedLLMClient.achat()` |

**注意事项**：
- BuilderProvider 的 4 个方法（`clarify_requirements` / `analyze_gaps` / `plan_tooling` / `build_draft`）需要重构
- 每个方法传入不同的 system prompt + 工具列表
- 验证 BuilderProvider 是否还在生产路径被调用（可能已是死代码）

---

### 阶段 5：清理 Nanobot 代码

**目标**：删除 `core/embedded_nanobot/` 下不再使用的代码。

**删除清单**（约 7500+ 行）：

| 路径 | 行数（估算） | 说明 |
|------|------------|------|
| `runtime.py` | ~2700 | EmbeddedNanobotRuntime |
| `intent_context.py` | ~300 | IntentContext |
| `agent_builder_flow.py` | ~400 | FlowPhase |
| `agent/runner.py` | ~300 | AgentRunner |
| `agent/hook.py` | ~100 | AgentHook |
| `agent/context.py` | ~300 | ContextBuilder |
| `agent/context_injection_policy.py` | ~200 | InjectionPolicy |
| `agent/memory.py` | ~400 | MemoryStore/MemoryConsolidator |
| `agent/skills.py` | ~200 | SkillsLoader |
| `agent/tools/base.py` | ~150 | Tool 抽象基类 |
| `agent/tools/filesystem.py` | ~300 | 文件工具 |
| `agent/tools/shell.py` | ~200 | Shell 工具 |
| `agent/tools/web.py` | ~400 | Web 工具 |
| `agent/tools/tradingagents_bridge.py` | ~150 | 桥接工具 |
| `agent/tools/registry.py` | ~150 | Nanobot ToolRegistry |
| `bus/` | ~100 | MessageBus |
| `command/` | ~200 | CommandRouter |
| `cron/` | ~300 | CronService |
| `providers/` | ~200 | LLMProvider/TradingAgentsLLMProvider |
| `security/` | ~100 | 网络安全 |
| `session/` | ~300 | Session/SessionManager |
| `utils/` | ~100 | 工具函数 |

**保留清单**：

| 路径 | 说明 |
|------|------|
| `workflows/agent_builder_state.py` | LangGraph 状态定义 |
| `workflows/agent_builder_store.py` | MongoDB checkpoint |
| `workflows/agent_builder_graph.py` | LangGraph 图定义 |
| `workflows/agent_builder_nodes.py` | 节点实现（改造后） |
| `workflows/agent_builder_conditions.py` | 条件路由 |

---

## 六、风险与注意事项

### 6.1 兼容性

- **前端无改动**：路由端点 `/api/embedded-nanobot/chat/stream` 不变，SSE 事件格式不变
- **MongoDB 集合不变**：`embedded_nanobot_threads` / `embedded_nanobot_thread_messages` / `agent_builder_graph_sessions` 不变
- **工具不变**：10 个 Agent Builder 工具和所有基本面工具不变

### 6.2 风险评估矩阵

| 风险 | 等级 | 概率 | 影响 | 缓解措施 |
|---|---|---|---|---|
| `achat()` 无流式导致用户体验下降 | 中 | 高 | 用户等待时无视觉反馈 | 分块推送模拟流式；保留 progress 事件 |
| `_build_force_call_params` 迁移遗漏 | 高 | 中 | 工具因参数不全失败 | 保留原函数不变，只改调用方式 |
| 工具 Schema 格式转换错误 | 低 | 低 | LLM 返回格式错误 | 添加 `_to_openai_tool_schema()` 单元测试 |
| graph 注入变更导致节点无法获取 llm_client | 中 | 中 | 运行时崩溃 | `_make_node_wrapper` 动态参数注入自动适应 |
| SSE 事件适配遗漏 | 低 | 低 | 前端无响应 | 事件格式不变，只在 graph 层保持原 emit 调用 |
| 意图分类 `provider` → `llm_client` 遗漏 | 低 | 低 | 意图分类失败 | 独立函数，搜 `provider.chat_with_retry` 直接替换 |
| 阶段 2-4 其他 channel 破坏 | 低 | 低 | 调试页/worker/BuilderProvider 不可用 | 分阶段迁移，每个阶段独立测试 |

### 6.3 注意事项（更新后）

1. **意图分类**：`node_classify_user_intent` 调用 `provider.chat_with_retry(messages, model, temperature=0.0)` → 替换为 `llm_client.achat(converted_messages, temperature=0.0)`
2. **Checkpoint 不受影响**：`AgentBuilderGraphStore` 是我们自己的代码，与 Nanobot 无关
3. **`_build_force_call_params` 逻辑完全保留**：不删除、不重构，只改调用方（从"LLM 没调时兜底"变为"代码直接调工具前构建参数"）
4. **`TradingAgentsLLMProvider` 的重试**：`chat_with_retry` 3 次重试。`UnifiedLLMClient._aretry_chat` 也有指数退避重试，参数一致
5. **`agent_workshop_evaluation` worker**：当前走 Nanobot 的 ContextBuilder + InjectionPolicy，迁移后需自行构建 system prompt。这可能最复杂
6. **`EmbeddedNanobotBuilderProvider`**：确认是否还在生产路径被调用。如果是死代码，阶段 4 可跳过，直接删除
7. **`_convert_messages` 逻辑**：`TradingAgentsLLMProvider._convert_messages` 做 `dict → Message` 转换。迁移后需提取为独立工具函数
8. **节点 8 个，迁移量**：全部 8 个节点都调 `_run_node_llm`，改一个函数即可覆盖所有节点

### 6.4 回滚方案

如果阶段 1 出现问题，回滚步骤：
1. Git revert 阶段 1 的 commit
2. `_AGENT_BUILDER_GRAPH_ENABLED = False` → 退回 Nanobot Runtime 的经典 ReAct 路径
3. 前端不受影响（路由端点不变）

---

## 七、时间评估

> 基于实际代码结构和依赖范围估算。未包含联调/真数据 LLM 测试等待时间。

| 阶段 | 工作量 | 预估时间 | 依赖 | 说明 |
|---|---|---|---|---|
| **阶段 0：准备** | 小 | 2-4 h | 无 | 确认所有 channel 调用入口；备份 `_build_force_call_params`；准备 `UnifiedLLMClient` 工具函数 |
| **阶段 1：替换 agent_workshop 路径** | 中 | 8-12 h | 阶段 0 | 核心改动在 `agent_builder_nodes.py`，8 个节点共享 `_run_node_llm`，改一个函数即可覆盖；测试适配量较大 |
| **阶段 1 验证** | 中 | 6-10 h | 阶段 1 | 165 个单元测试适配；前端全流程至少跑 3 轮；检查 XML 泄露是否消失 |
| **阶段 2：替换 api 调试页** | 小 | 2-3 h | 阶段 1 | 调试页接口简单，主要复用阶段 1 的 `_run_node_tool_first` 思路 |
| **阶段 3：替换评估 Worker** | 中 | 4-6 h | 阶段 1 | 需要迁移 ContextBuilder 上下文构建；测试需要触发后端 worker |
| **阶段 4：替换 BuilderProvider** | 中-大 | 4-8 h | 阶段 1 | 需要先确认 BuilderProvider 是否在生产路径使用；如果是死代码可跳过 |
| **阶段 5：清理 Nanobot 代码** | 小 | 2-3 h | 阶段 1-4 | 删除约 7500+ 行；主要工作是处理残余 import 和 `__init__.py` 导出 |
| **整体回归测试** | 中 | 6-10 h | 阶段 5 | 所有 channel 跑通；前端完整创建 Agent 全流程；无 XML 泄露 |

### 汇总

| 范围 | 总人时 | 建议排期 |
|---|---|---|
| 只做阶段 1（解决 XML 泄露，不移除 Nanobot） | **16-26 h** | 2-3 个工作日 |
| 阶段 1-3（主路径 + 调试页 + 评估 Worker） | **28-46 h** | 4-6 个工作日 |
| 全部 5 阶段（完全移除 Nanobot） | **34-56 h** | 5-8 个工作日 |

### 建议

- **最小可行**：只做阶段 1。这是性价比最高的方案——用 2-3 天彻底解决 XML 泄露，Nanobot Runtime 其余路径暂时保留。
- **最干净**：做完全部 5 阶段。但阶段 4 需要先确认 `EmbeddedNanobotBuilderProvider` 是否还活着，如果是死代码，可节省 4-8 h。

---

# 八、验收标准

### 阶段 1 验收

- [ ] 前端 AgentStudio 创建 Agent 全流程，不再出现 XML 泄露
- [ ] 165 个现有测试通过（含适配后的测试）
- [ ] 8 个节点的工具调用成功率 100%
- [ ] 分块流式推送：前端可见 typing 效果
- [ ] `logs/intent_classify_prompts.log` 正常记录
- [ ] progress 事件（"正在分析需求..."）正常
- [ ] tool_event（"执行：xxx"/"完成：xxx"）正常
- [ ] done 事件格式不变

### 全部完成验收

- [ ] `core/embedded_nanobot/` 下只剩 `workflows/` 目录
- [ ] `grep -r "from core.embedded_nanobot" --exclude-dir=workflows` 无结果（或仅有类型导入）
- [ ] `grep -r "EmbeddedNanobotRuntime"` 无结果
- [ ] 所有 4 个 channel 路径正常工作
- [ ] 无 XML 泄露报告
- [ ] 前端 Agent 创建全流程：发现需求 → 缺口分析 → 方案选择 → 生成 → 测试 → 发布
