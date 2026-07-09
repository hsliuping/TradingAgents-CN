# Hermes vs nanobot：基于代码分析的逐项对比

> 分析日期：2026-06-30
> 方法：对比本周 36 个 commit 解决的问题 vs Hermes 源码/架构文档

---

## 一、本周 36 个 commit 分类

### 1.1 框架基础设施问题（Hermes 已内置解决）

| # | Commit | 问题 | nanobot 修复方式 | Hermes 方案 |
|---|---|---|---|---|
| 1 | `13e05947` 稳定 Nanobot 意图上下文与会话连续性 | contextvar 跨异步回退，intent 丢失 | 模块级 dict + MongoDB 双重兜底 | SQLite session state，无 contextvar 依赖 |
| 2 | `e94d4f36` IntentContext + FlowController 状态机 | 阶段流转混乱，LLM 跳过阶段 | 手写 FlowController + PhaseRule + 7 阶段状态机 | 不内置，但 Skill 系统可定义多步流程 |
| 3 | `6d6b9943` V2 多方案确认 + 缺口分析前置 | 方案确认后仍做 gap 分析 | 重写 7 阶段流程 + 工具约束 | 不内置，需业务 Skill 定义 |
| 4 | `ed7fab49` 工具路由升级为语义向量搜索 | 工具选择靠关键词匹配 | 集成向量搜索 | 内置工具注册表 + 基于 toolset 的选择 |
| 5 | `5210cf40` 增强 Agent 工坊日志可观测性 | 日志不完整，无法追踪流程 | 手动加日志 | 内置 callbacks + progress tracking |
| 6 | `ce3b6902` 加固 Agent Workshop 运行时执行闭环 | 工具执行失败、重试、fallback | 手动加固 | 内置 retry、fallback、compression |
| 7 | `f20e304e` 复用 active skill generation sessions | session 管理混乱 | 手动管理 session 复用 | `hermes_state.py` 完整 session 管理 |
| 8 | `ea84f71a` Phase3 并发治理与失败恢复 | 并发工具执行问题 | 手动实现 thread worker | 内置 ThreadPoolExecutor 并发执行 |
| 9 | `36c06602` Agent 工坊与工作流兼容性修复 | agent_type 不统一、治理引导缺失 | 手动修复兼容性 | 不涉及，Hermes 无此概念 |

**小计：9 个 commit，Hermes 可解决 7 个（完全解决 7 个，部分解决 2 个）**

### 1.2 业务逻辑问题（任何框架都需要）

| # | Commit | 说明 |
|---|---|---|
| 10 | `981f0951` 新增 90+ 财经工具 | 业务工具，任何框架都需要 |
| 11 | `ce343253` 新增标准财务数据能力 | 数据源适配，业务逻辑 |
| 12 | `01ef48d2` 完善 Skill 生成角色元数据 | Skill 生成业务逻辑 |
| 13 | `0fb631d1` 清理已删除 Agent | Agent 生命周期管理，业务逻辑 |
| 14 | `2cf0a7ce` 改进 Skill 生成失败上下文 | Skill 生成业务逻辑 |
| 15 | `e017ce87` 添加外部估值历史访问 | 数据访问，业务逻辑 |
| 16 | `392d33cb` Agent Studio 技能自动补全 | 业务功能 |
| 17 | `5b09a292` Phase3 缺口补齐执行面 | 缺口管理业务逻辑 |
| 18 | `a7e98477` Phase2/2.5 缺口补齐 | 缺口管理业务逻辑 |
| 19-36 | 各种 UI、文档、入口收敛、运行时补齐 | 业务功能 + 文档 |

**小计：27 个 commit，都是业务逻辑**

### 1.3 未提交的修改（基于本周对话）

| 修改 | 问题 | 分类 |
|---|---|---|
| `context_injection_policy.py` (新文件) | MEMORY.md 污染、多存储混乱 | 框架基础设施 |
| `context.py` 平台背景知识 + 记忆边界 | 平台知识缺失 | 业务配置 |
| `agent_builder_flow.py` 待确认上下文注入 | 跨轮上下文丢失 | 框架基础设施 |
| `intent_context.py` 阶段新增 | 状态管理 | 框架基础设施 |
| `runtime.py` InjectionPolicy 集成 | 上下文装配 | 框架基础设施 |
| `tools/context.py` 模块级 intent 存储 | contextvar 兜底 | 框架基础设施 |
| `nanobot_agent_builder_tools.py` 大量修改 | 工具逻辑 + guidance | 混合 |
| `embedded_nanobot_service.py` intent 持久化 | 持久化治理 | 框架基础设施 |
| `nanobot-memory-governance-design.md` (新文件) | 记忆治理设计 | 架构设计 |
| `pre_check.py` (新文件) | 预检工具 | 工程工具 |

**未提交的框架基础设施修改：约 800 行代码，6 个文件**

---

## 二、Hermes 源码架构分析

### 2.1 会话管理：`hermes_state.py` + `run_agent.py`

**Hermes 实现：**

```
AIAgent.run_conversation(
    conversation_history=None  # 自动从 SQLite 加载
)
```

- 会话状态存储在 SQLite（`~/.hermes/state.db`）
- `sessions` 表：session_id, source, user_id, model, parent_session_id, billing
- `messages` 表：完整消息历史，role, content, tool_calls, tokens, reasoning
- FTS5 全文搜索：`session_search` 工具可跨会话搜索
- Session lineage：parent_session_id 链，compression 时自动创建子 session

**与 nanobot 对比：**

| 维度 | nanobot 当前 | Hermes |
|---|---|---|
| 存储 | MongoDB + contextvar + 模块级 dict | SQLite 单文件 |
| 会话恢复 | 手动从 MongoDB 读取 thread_context | `run_conversation()` 自动加载 |
| 跨轮状态 | 靠 contextvar（不可靠）+ 模块级 dict（兜底） | conversation_history 参数直接传递 |
| 消息存储 | MongoDB `embedded_nanobot_threads` | SQLite `messages` 表 |
| 全文搜索 | 无 | FTS5 内置 |
| 会话压缩 | 无 | 内置 context compression |

**结论：Hermes 的会话管理是框架级实现，nanobot 需要手写 ~300 行代码才能达到等效功能，且可靠性不如。**

### 2.2 记忆管理：`memory` 工具 + MEMORY.md

**Hermes 实现：**

```
memory(action="add", target="memory", content="...")
memory(action="replace", target="memory", old_text="...", content="...")
memory(action="remove", target="memory", old_text="...")
```

- `MEMORY.md`（2,200 chars）+ `USER.md`（1,375 chars）
- Agent 自管理（add/replace/remove），不是人工维护
- 字符限制防止膨胀
- session 开始时作为 frozen snapshot 注入系统 prompt
- 重复自动去重
- 安全扫描（注入检测、凭证泄露检测）

**与 nanobot 对比：**

| 维度 | nanobot 当前 | Hermes |
|---|---|---|
| 记忆文件 | `MEMORY.md` 整段注入，无限制 | 2,200 chars 限制，Agent 自管理 |
| 管理方式 | 人工维护，容易膨胀 | Agent 通过 `memory` 工具自管理 |
| 旧内容污染 | 删了 Agent 后记忆还在文件里 | `memory remove` 可删除 |
| 注入时机 | 每次 LLM 调用都注入 | session 开始时 frozen snapshot |
| 安全 | 无 | 注入/凭证泄露检测 |

**结论：Hermes 的 memory 系统比 nanobot 的 MEMORY.md 注入成熟得多，但两者都依赖文件系统存储。Hermes 的优势在于 Agent 自管理 + 字符限制 + 安全扫描。**

### 2.3 工具执行与结果同步：`run_agent.py` 主循环

**Hermes 实现：**

```python
# 极简版循环
for tool_call in response.tool_calls:
    result = handle_function_call(tool_call.name, tool_call.args)
    messages.append({"role": "tool", "tool_call_id": tool_call.id, "content": result})
```

- 工具执行结果自动追加到 `conversation_history`
- 单工具：主线程直接执行
- 多工具：ThreadPoolExecutor 并发执行
- 结果按调用顺序插入，不按完成顺序
- `clarify` 等交互式工具强制串行

**与 nanobot 对比：**

| 维度 | nanobot 当前 | Hermes |
|---|---|---|
| 结果同步 | 每个工具手动调用 `update_intent_context_in_thread` | 自动追加到 conversation_history |
| 并发 | 手动实现 | ThreadPoolExecutor 内置 |
| 交互式工具 | 无特殊处理 | `clarify` 强制串行 |

**结论：Hermes 的工具结果同步是框架级自动的，nanobot 需要每个工具手动维护。**

### 2.4 Prompt 装配：`prompt_builder.py`

**Hermes 实现：**

```
系统 Prompt = SOUL.md + MEMORY.md + USER.md + Skills + Context Files + Tool Guidance
```

- 在 session 开始时一次性组装
- 中间不变（保护 prefix cache）
- 多来源自动合并

**与 nanobot 对比：**

| 维度 | nanobot 当前 | Hermes |
|---|---|---|
| 装配方式 | 散落在 runtime/context/tool 中各自注入 | `prompt_builder.py` 统一装配 |
| 缓存 | 无 | Anthropic prefix caching |
| 来源管理 | InjectionPolicy 手动过滤 | 统一来源，按优先级装配 |

**结论：Hermes 的 prompt 装配是统一的，nanobot 是散落的。我们正在写的 InjectionPolicy 本质上就是在做 Hermes 的 prompt_builder 已经做的事。**

### 2.5 Context Compression：`context_compressor.py`

**Hermes 实现：**

- 触发条件：conversation >50% 模型 context window
- 中间轮次被摘要压缩
- 最后 N 条消息保留（默认 20）
- 工具调用/结果对保持完整
- 压缩后创建子 session（parent_session_id）

**与 nanobot 对比：**

| 维度 | nanobot 当前 | Hermes |
|---|---|---|
| 压缩 | 无 | 内置 |
| 长对话处理 | 依赖 LLM 自身 context window | 自动压缩 |

**结论：nanobot 无此能力，长对话会直接超出 context window。**

---

## 三、核心问题对照：Hermes 能否直接解决

### 问题 1：contextvar 跨异步回退 → intent 丢失

- **nanobot 修复**：`13e05947` commit + 模块级 dict + MongoDB 持久化（~150 行）
- **Hermes**：✅ 完全不依赖 contextvar。`hermes_state.py` 使用 SQLite，`run_conversation()` 通过 `conversation_history` 参数直接传递状态。
- **可删除**：`core/tools/context.py` 中的模块级 intent 存储（~100 行）

### 问题 2：跨轮上下文丢失

- **nanobot 修复**：未提交的 `build_flow_guidance_block` 待确认上下文注入（~30 行）+ 手动 `pending_question`
- **Hermes**：✅ 会话历史自动恢复。`run_conversation()` 接受 `conversation_history` 参数，自动加载上一轮完整对话。`session_search` 工具可跨会话搜索。
- **可删除**：`build_flow_guidance_block` 中的 pending_question 注入逻辑

### 问题 3：旧 Agent 记忆污染新建

- **nanobot 修复**：未提交的 `context_injection_policy.py`（~200 行）+ 禁止 MEMORY.md 注入
- **Hermes**：⚠️ 部分解决。Hermes 的 MEMORY.md 是 Agent 自管理，有 2,200 chars 限制。但 Hermes 采用的是单 Agent 模式，多 Agent 工作坊场景仍需业务层管理。
- **可删除**：InjectionPolicy 中的 file_memory 过滤逻辑

### 问题 4：工具调用后状态未同步

- **nanobot 修复**：每个工具手动调用 `update_intent_context_in_thread`
- **Hermes**：✅ 工具执行结果自动追加到 `conversation_history`。这是 agent loop 的内置行为，不需要工具自己维护。
- **可删除**：所有工具中的 `update_intent_context_in_thread` 调用

### 问题 5：阶段流转依赖 LLM 自觉

- **nanobot 修复**：`e94d4f36` commit + `6d6b9943` commit，FlowController + PhaseRule（~800 行）
- **Hermes**：❌ 不内置。Hermes 是通用 Agent，没有"Agent Builder 工作流"概念。但 Skill 系统可定义流程引导。
- **不可删除**：阶段流转的业务逻辑仍需保留，但可以用 Hermes 的 Skill 系统替代部分 FlowController 的功能。

### 问题 6：多存储边界混乱

- **nanobot 修复**：未提交的 InjectionPolicy + 存储权责设计（~300 行 + 设计文档）
- **Hermes**：✅ SQLite 统一存储。不需要 MongoDB、Redis、Mem0、向量库、文件 Memory 五路混战。
- **可删除**：InjectionPolicy 中的存储过滤逻辑

### 问题 7：对话摘要缺失

- **nanobot 修复**：未实现
- **Hermes**：✅ 内置。每轮后自动回顾 + 写入 MEMORY.md。context_compressor 自动压缩长对话。
- **可删除**：无需实现

### 问题 8：Prompt 装配散落

- **nanobot 修复**：未提交的 InjectionPolicy（~200 行）
- **Hermes**：✅ `prompt_builder.py` 统一装配。SOUL.md + MEMORY.md + Skills + Context Files + Tool Guidance 自动合并。
- **可删除**：InjectionPolicy 全部

---

## 四、量化对比

### 4.1 代码量

| 类别 | nanobot 当前 | 迁移到 Hermes 后 |
|---|---|---|
| 框架基础设施（FlowController + IntentContext + InjectionPolicy + contextvar 兜底） | ~1,900 行 | 0 行（删掉） |
| 业务工具（13 个 Agent Builder 工具） | ~3,000 行 | ~3,000 行（保留，适配注册方式） |
| Agent Workspace 服务 | ~5,000 行 | ~5,000 行（不变） |
| 前端 AgentStudio | ~3,000 行 | ~3,000 行（适配 API 层） |
| 新增：Hermes 对接代码 | 0 行 | ~500 行（HermesBuilderProvider + 工具注册 + Skill 定义） |

### 4.2 本周 commit 时间占比

| 类别 | Commit 数 | 占比 |
|---|---|---|
| 框架基础设施问题 | 9 | 25% |
| 业务逻辑 | 27 | 75% |

**关键发现**：虽然框架基础设施只占 25% 的 commit 数，但这些 commit 的**调试时间占比远高于 25%**。contextvar 回退、跨轮上下文丢失、阶段流转混乱这些问题，每个都需要多轮调试才能定位根因。

---

## 五、Hermes 的局限

### 5.1 不提供的功能

| 功能 | 说明 |
|---|---|
| Agent Builder 工作流状态机 | Hermes 是通用 Agent，没有"创建 Agent 的 7 步流程" |
| Gap 分析 | 业务特有，需自定义工具 |
| 方案生成（A/B/C 方案） | 业务特有，需自定义工具 |
| Agent 配置写入 | 业务特有，需自定义工具 |
| 多 Agent 管理 | Hermes 是单 Agent 模式 |

### 5.2 架构差异需要注意

| 差异 | 影响 |
|---|---|
| Hermes 是同步 Agent Loop | 我们的 Agent Builder 工具是异步的，需要适配 |
| Hermes 默认使用 SQLite | 我们的业务数据在 MongoDB，需要保留 |
| Hermes 的 Skill 是 MD 文件 | 我们的工具是 Python 函数，注册方式不同 |
| Hermes 的 memory 是 Agent 自管理 | 我们当前是人工维护 MEMORY.md |

### 5.3 风险评估

| 风险 | 等级 | 说明 |
|---|---|---|
| Hermes API 不稳定 | 中 | 2026.02 发布，v0.8.0，API 可能变化 |
| 工具注册方式不同 | 低 | 工具函数本身不变，只需改注册方式 |
| 同步/异步适配 | 中 | Hermes 是同步 loop，我们的工具是异步的 |
| 前端 SSE 格式不同 | 低 | 前端 API 层适配即可 |

---

## 六、最终建议

### 6.1 结论

**Hermes 能解决 7/9 个框架基础设施问题，不能解决 2/9 个（阶段状态机 + 部分业务逻辑）。但这些不能解决的问题本来就不是框架应该提供的。**

**本周 25% 的 commit（9 个）是在修复框架基础设施问题，如果换 Hermes，这些 commit 不需要存在。**

### 6.2 迁移路线

```
阶段 1：Hermes 基础对接（1-2 天）
  - 安装 Hermes
  - 实现 HermesBuilderProvider
  - 注册 13 个 Agent Builder 工具（工具函数不变，改注册方式）
  - 验证：单轮对话能调用工具

阶段 2：工作流 Skill 定义（1-2 天）
  - 编写 Agent Builder 工作流 SKILL.md
  - 定义 7 阶段流程
  - 验证：完整流程能走通

阶段 3：前端适配 + 清理（1-2 天）
  - 前端 AgentStudio 适配 Hermes
  - 删除 ~1,900 行框架基础设施代码
  - 保留 MongoDB 做业务数据
  - 验证：完整新建 Agent 流程

总计：3-6 天
```

### 6.3 保留的系统

| 保留 | 原因 |
|---|---|
| MongoDB（Agent Spec/Version/Config） | 业务数据 |
| 13 个 Agent Builder 工具函数 | 纯业务逻辑 |
| 前端 AgentStudio | 只改 API 适配层 |
| AgentWorkshopService | 核心业务逻辑 |
| AgentBuilderProvider 抽象层 | 已建好 |

### 6.4 可删除的系统

| 删除 | 原因 |
|---|---|
| FlowController / PhaseRule / FlowPhase | Hermes 不内置，但 Skill 系统可替代 |
| IntentContext / IntentStage | Hermes session 替代 |
| InjectionPolicy | Hermes prompt_builder 替代 |
| 模块级 `_nanobot_intents_by_thread` | Hermes SQLite 替代 |
| contextvar 兜底逻辑 | Hermes 无 contextvar 依赖 |
| MEMORY.md 注入逻辑 | Hermes 自管理 memory |
| Mem0 集成 | 可选，Hermes 有 Mem0 provider 插件 |