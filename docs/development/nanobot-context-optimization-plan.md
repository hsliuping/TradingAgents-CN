# Nanobot 上下文 Token 优化方案

## 现状分析

每次对话时 Nanobot 的上下文构成（典型值 ~34660 tokens）：

| 来源 | 估算 tokens | 占比 | 说明 |
|------|:---:|:---:|------|
| 工具定义 JSON Schema | ~15000 | 43% | 30+ 个工具的完整 JSON schema（name + description + parameters） |
| 系统提示词（身份声明） | ~1200 | 3% | `context.py` `_get_identity()` 产出，约 3k 中文字符 |
| SKILL 列表摘要 | ~800 | 2% | 所有已安装 skill 的 XML 目录（name + description + path） |
| SKILL.md 全文 | ~4000 | 12% | `nanobot-agent-design/SKILL.md` 47KB，通过 `build_system_prompt` 注入 |
| 额外系统指引块 | ~2000 | 6% | project_memory、agent_builder_lesson、callable_agent hint、governance |
| 历史对话 | ~4000 | 12% | 多轮累积的 user/assistant 消息 |
| 当前用户消息 | ~200 | 1% | 用户当前输入 |
| API 协议/格式开销 | ~3000 | 9% | JSON role 标记等 |
| 其他（bootstrap 文件等） | ~400 | 1% | AGENTS.md / USER.md / Memory 等 |

**核心问题：上下文窗口 65536 tokens，仅工具 schema 就占 43%，加上系统提示词和历史后，留给 LLM 回复的空间紧张。**

---

## 优化方案

### 方案 1：工具集按工作流阶段分片（预计节省 6000-8000 tokens）

**现状**：当前 `focused_factory_scope=True` 时，所有 24 个 `AGENT_BUILDER_TOOL_IDS` 一把全注入，无论当前处于哪个阶段。

**改进**：将工具集按 8 阶段拆分为 4 组，根据当前阶段（由线程上下文推断）只加载相关组：

| 工具组 | 包含阶段 | 工具 ID 列表 | 工具数 |
|--------|---------|-------------|:---:|
| **前期** | requirement-intake, confirmation | `prepare_agent_requirement_intake`, `prepare_agent_generation_confirmation`, `search_project_capabilities`, `inspect_agent_workshop_assets`, `inspect_runtime_agent_configs`, `inspect_prompt_templates` | 6 |
| **构建** | generation, governance | `create_or_update_agent_workshop_draft`, `analyze_agent_workshop_gaps`, `generate_agent_workshop_tooling_plan`, `build_agent_workshop_version`, `create_or_update_runtime_agent_config`, `create_or_update_universal_agent_prompt_template`, `bind_agent_tools_and_validate_candidate`, `generate_confirmed_candidate_agent` | 8 |
| **测试** | testing | `debug_agent_workshop_version`, `run_agent_workshop_real_data_test` | 2 |
| **后期** | evaluation, publish-ready, published | `evaluate_agent_workshop_version`, `iterate_agent_workshop_version`, `publish_agent_workshop_version` | 3 |

- 核心工具（read_file/write_file 等 7 个）常驻
- 用户可以通过提问在任何阶段"切组"（如测试阶段问"我要改一下 agent 配置"，系统检测到 builder 关键词后自动切回构建组）
- **预计节省**：24 → 最多 8 个 agent builder 工具，约减少 5000-8000 tokens

**实现方式**：在 `_build_scoped_tools` 中增加 `_infer_workshop_phase` 逻辑，读取 `thread_context.version_status` 来推断当前阶段。

---

### 方案 2：系统提示词按阶段精简（预计节省 2500-3500 tokens）

**现状**：`context.py` `_get_identity()` 包含全部 8 阶段工作流说明 + 修改 Agent 流程 + 行为准则，约 3000 中文字符。SKILL.md 全文 47KB 也通过 `build_system_prompt` 注入。

**改进**：对于明确处于 testing / evaluation 阶段的请求，注入精简版系统提示词：

| 版本 | 内容 | 估计 tokens | 适用阶段 |
|------|------|:---:|------|
| 完整版 | 全部 8 阶段 + SKILL.md 全文 | ~5500 | requirement → governance |
| 精简版（测试场景） | 只保留 testing + evaluation 阶段说明 + 测试工具使用约束 | ~1500 | testing, evaluation |
| 精简版（发布场景） | 只保留 publish + iterate 阶段说明 | ~800 | publish-ready, published |

**实现方式**：在 `ContextBuilder.build_system_prompt()` 中增加 `phase` 参数，由 runtime 传递。

---

### 方案 3：历史对话截断/压缩（预计节省 2000-4000 tokens）

**现状**：历史对话全量随每一轮追加，不做任何截断。

**改进**：
1. 当历史消息超过 15 条时，对最早的消息做摘要压缩（调用 LLM 生成 200 字以内的摘要替换原始内容）
2. 设置硬上限：消息列表最多保留最近 20 条完整消息

**实现方式**：在 `_build_capped_initial_messages` 中增加轮次计数。优先使用 token budget 截断（现有逻辑），超过阈值时触发压缩。

---

### 方案 4：工具 Schema 精简（预计节省 3000-5000 tokens）

**现状**：每个工具的 `description` 字段是从源码 `@register_tool` 的 `description` 参数直接取，部分工具描述很长（如 `prepare_agent_generation_confirmation` 的描述约 200 字符）。

**改进**：生成 OpenAI function calling schema 时对 `description` 做截断（超过 80 字符的部分用 "..." 省略）。LLM 主要依赖 `name` 和 `parameters` 来选择工具，超长描述作用有限。

**实现方式**：在 `to_schema()` 中加一行 `description = description[:80] + "..." if len(description) > 80 else description`。

---

### 方案 5：Extra Guidance 延迟加载（预计节省 1500-2000 tokens）

**现状**：每次请求都加载 4 块 guidance（project_memory、agent_builder_lesson、callable_agent hint、governance rule），不管当前阶段是否需要。

**改进**：
- `project_memory_guidance`：只在 generation/governance 阶段注入（构建时有必要遵守全局规则）
- `agent_builder_lesson_guidance`：只在 generation/governance 阶段注入
- `callable_agent hint`：只在用户明确请求分析时注入
- `governance rule`：只在 agent builder 相关请求时注入

---

## 预期效果汇总

| 优化项 | 预计节省 | 实施难度 | 风险 |
|--------|:---:|:---:|------|
| 方案1：工具分片 | 6000-8000 | 中 | 需要推断阶段逻辑正确 |
| 方案2：提示词精简 | 2500-3500 | 低 | 精简版不能漏掉关键行为约束 |
| 方案3：历史截断 | 2000-4000 | 中 | 压缩可能丢失重要上下文 |
| 方案4：Schema 精简 | 3000-5000 | 低 | description 截断不影响 function calling 准确性 |
| 方案5：Guidance 延迟 | 1500-2000 | 低 | 需确认各阶段对 guidance 的需求 |
| **合计** | **15000-22500** | — | 上下文从 34660 降至 ~15000-20000 |

---

## 建议实施顺序

1. **方案4**（Schema 精简）— 改动最小，一行代码，无副作用
2. **方案5**（Guidance 延迟）— 改动小，效果明显
3. **方案1**（工具分片）— 效果最大，需要正确推断阶段
4. **方案2**（提示词精简）— 辅助优化
5. **方案3**（历史截断）— 最后做，因为现有 token budget 截断逻辑已有部分效果
