# Skill 生成引擎 Agent 化改造设计

> 版本：v3.0 设计文档
> 更新时间：2026-06-28
> 实现进度：Phase E0/E1/E2a/E2b 已完成第一版最小闭环；Phase E3a 已完成第一版；Phase E3b 待真实数据验证后决定。
> 关联文档：[agent-studio-skill-auto-completion.md](./agent-studio-skill-auto-completion.md)
> 目标：把 Skill 生成的内核从「固定 DAG 管线」升级为「工具增强的 Agent 循环」，让生成器在生成过程中能感知环境、能自递归、能复用 Nanobot 的上下文与经验，同时完整保留既有质控与治理闸门。
> 外部参考：借鉴 [Hermes Agent](https://github.com/NousResearch/hermes-agent) 的循环形状与工具模式，但不替换底座。本文 §3.4 记录了具体借鉴项与适用边界。

---

## 1. 背景

当前 Skill 自动补齐链路（见关联文档）在「产品流程 / 任务编排 / 异步 job」层面已经基本闭环。但在更底层的「Skill 生成内核引擎」上，暴露出一组累积性痛点。本文档专门处理引擎层，不重复关联文档已覆盖的编排与 job 治理内容。

引擎相关代码位于：

```text
core/tools/external/iteration_controller.py        # 迭代控制器（生成主循环）
core/tools/external/reconnaissance_controller.py   # 前置侦察层
core/tools/external/recon_tools.py                 # 侦察工具集（只读探测）
app/services/skill_generation_service.py           # 生成服务（入库/注册/合规）
```

---

## 2. 痛点（按提出顺序累积）

### 2.1 不会自递归，复杂需求修不动

简单需求能一次生成成功；稍复杂的需求一旦失败，生成器不会自己「查原因」，因为它不是自递归（self-recursive）的循环——当前反思步骤的产物只回灌给代码再生成，从不回头重新侦察。

代码现状：

- [iteration_controller.py](../../../core/tools/external/iteration_controller.py) 的 `run()` 在失败后会调用 `_reflect_on_failure`，产出 root_cause / fix_plan / confidence / should_retry。
- 但反思结果**只回灌给代码再生成**（`CodeGenerator.generate(..., feedback=...)`），从不回头重新侦察。
- 反思能改「代码怎么写」，但改不了「对环境的事实认知」——如果根因是数据/接口层面的误判，反复改代码也修不好。
- 即使 `should_retry=false` 能提前终止，但它只能「放弃」而不能「回头查真值后再试」。

### 2.2 Nanobot 与 Skill 生成是两套体系，上下文/经验不共享

当前是「Nanobot + Skill 管线」两套不同体系的拼接：

- Nanobot 侧已经获得的对话上下文、系统感知、积累的经验，没有传递给 Skill 生成内核。
- Skill 生成时是「冷启动」，看不到 Nanobot 已经摸清的现状。
- 这种拼接是结构性硬伤，不是参数没传全的问题。

代码现状：

- `SkillGenerationService.start_session()` 已支持 `handoff_context`，但当前透传字段很薄（source / source_spec_id / source_name / target_capability / handoff_intent）。
- 没有共享的经验/记忆存储被生成内核消费。

### 2.3 生成器无法感知系统环境，流程太死板太长

生成器没办法在生成过程中感知系统环境：不能去数据库查真实数据，不能验证某个接口是否可用。流程固定、链路太长。Nanobot 和 Hermes 这类 ReAct agent 在这方面「很直接」。

代码现状（已逐项核对）：

- [recon_tools.py](../../../core/tools/external/recon_tools.py) 的 `RECON_TOOLS` 是 8 个**只读结构探测工具**：
  - `list_available_collections` / `inspect_collection_schema`：只返回结构摘要，注释明写「只返回结构摘要，不返回完整样本文档」。
  - `check_field_coverage`：只返回字段非空覆盖率。
  - `inspect_symbol_sample`：只返回样本概览，不返回完整原文。
  - `describe_runtime_helper` / `list_runtime_functions`：只返回函数签名/文档，不能调用。
  - `list_external_data_sources` / `list_mcp_tools`：只列目录。
- 因此：**没有任何工具能跑一条真实查询返回真值，也没有任何工具能真的调一次接口验证其可用性。**
- 更关键：[reconnaissance_controller.py](../../../core/tools/external/reconnaissance_controller.py) 的侦察（`MAX_RECON_TOOL_ROUNDS = 10`）只在生成**前**跑一次，产出的 `ImplementationFactReport` 之后被**冻结**；在 [iteration_controller.py](../../../core/tools/external/iteration_controller.py) 的修复循环里（`MAX_ITERATIONS = 8`），生成器**一个侦察/查询工具都调不了**，只能拿沙箱 stdout/stderr 干瞪眼。

### 2.4 三个痛点的统一根因

三条痛点本质是同一个病根：

> Skill 生成内核是一条**固定 DAG 管线（pipeline）**，不是一个 **Agent 循环**。
> 它把「调查」前置并冻结，把「执行/修复」关进无工具的沙箱，各阶段不能交织、不能回头。

Nanobot / Hermes 之所以「直接」，正是因为它们是 ReAct 循环：调查与执行在同一个循环里，随时能调工具去查真值、探接口、再改。

---

## 3. 方案原则

### 3.1 目标方向：内核 Agent 化，而不是更换底座

- **不替换底座为 Hermes。** Hermes 是一个完整产品（独立 CLI/gateway/installer，自带 SKILL.md 程序性记忆格式），其「技能」是给它自己用的程序性记忆，与本项目受治理的 Python `external_skills` 工具是不同物种，直接替换会引入物种错配税与重集成成本。
- **不把 Skill 生成直接塞进 Nanobot 主对话循环。** 当前阶段采用 **SkillGeneration 专用 Agent Loop**：复用 Nanobot 已验证的 provider、tool schema、message 协议与上下文摘要，但运行时与用户对话循环隔离，避免长上下文和新工具影响常规对话。
- **Nanobot 继续作为用户交互与任务发起入口。** Agent Studio / Nanobot 负责理解用户意图、提交 `SkillBuildTask`、传递 `handoff_context`；专用 Agent Loop 负责 Skill 生成智能；平台治理负责最终入库、注册和索引。
- **Hermes 退化为可选项**：作为 ReAct 模式参考；未来若 Hermes 能作为内部执行引擎接入，也必须输出本项目的 `external_skills` 产物，并经过同一套合规、质控、注册与能力索引治理。

### 3.2 治理不丢

代码生成、静态校验、沙箱、Judge 评分、`_save_skill()` 合规入库与热注册，**全部保留为「循环里可调用的工具/终点闸门」**。循环变敏捷，闸门照样守在终点：

- 涉及交易建议/买卖信号/仓位建议的判定与拦截，**复用项目既有的全局非投顾合规校验**，不在引擎里新写一套规则（口径不漂移）。
- 正式 Skill 必须经由 `SkillGenerationService` 入库（`external_skills`，`source=generated`）、热注册（`register_single_external_skill`）、能力索引同步（`CapabilityIndexService.ensure_index`）。

### 3.3 中间路线：暴露「少量高价值工具」，不拆 20 个微步骤

关联文档 §3.4 否决「把所有管线组件拆成 Nanobot 工具（方案 C）」的顾虑（token 膨胀、LLM 级联、治理难统一）成立。本方案走中间路线：

- **不**把每个微步骤都拆成工具。
- **只**暴露一小撮高价值工具：现有侦察工具 + 新增「实时只读查询」+ 新增「接口探针」+ 一个把「生成 → 校验 → 沙箱 → 评分」打包成一步的「管线工具」。
- 循环负责决策与交织；管线工具内部仍是既有质控闭环。

**警告：管线工具化不是可选增强。** 如果不把生成/校验/沙箱/评分打包，循环每轮至少要调 4 次工具，就退化成关联文档否决的方案 C 的简化版，token 膨胀风险复活。因此管线工具是本方案成立的支柱。

### 3.4 借鉴 Hermes Agent 的具体模式

[Hermes Agent](https://github.com/NousResearch/hermes-agent) 是目前最成熟的 ReAct agent 实现之一。其架构对我们有三个高价值借鉴项和一个不可借鉴项，以下逐一分析。

#### 3.4.1 借鉴项 A：一个 while 循环就是全部编排

Hermes 的核心循环（`run_agent.py` 的 `AIAgent._run_agent_loop()`）极其简单：

```
while iterations < max_turns:
    response = LLM(messages, tools)
    if tool_calls: dispatch each → append tool_results → continue
    else: return response
```

没有「前置侦察阶段」、没有「冻结事实报告」、没有「独立反思步骤」、没有「管线 DAG」。一个 while 循环就是全部——调查、生成、修复都在同一循环、同一消息历史里交织。

**对我们的启示**：不需要建显式的「根因分类 → 触发再侦察」机制。只要循环每步都能调用正确的工具（包括查询/探针），LLM 自己就会在失败后查看结果并决定是改代码还是查数据。显式根因分类是过度工程化。

#### 3.4.2 借鉴项 B：execute_code — 沙箱内的代码也能调工具

Hermes 的 `execute_code` 工具（[code_execution_tool.py](https://github.com/NousResearch/hermes-agent/blob/main/tools/code_execution_tool.py)）允许 LLM 把 Python 脚本丢进子进程执行，脚本内部可以通过 RPC 回调主进程的 7 个白名单工具（`web_search`、`read_file`、`write_file`、`search_files`、`patch`、`terminal`、`web_extract`）。

这意味着「验证数据源是否可用」和「写代码」可以在**同一次 execute_code 调用内**完成：脚本第 3 行先 `web_search` 验证 API 返回结构，第 10 行根据真实结构写解析逻辑。不需要「先侦察 → 冻结事实 → 再生成」。

**对我们的启示**：把既有 `SandboxRunner` 改造成允许受控工具调用（白名单 + RPC 或等价机制），这比「让循环在反思后再回头调侦察工具」更直接、更短路径。

#### 3.4.3 借鉴项 C：经验积累是异步批量审查，不是每次生成都沉淀

Hermes 的经验积累机制：

> 每 10 个用户 prompt → 一个分叉的 review agent 看对话，决定有没有值得存进 memory/skill 的东西。

这意味着经验沉淀是**异步的、批量的、有质量筛选的**，不是每次任务结束都写。

**对我们的启示**：我们前面的 Phase E3 之所以难设计，就是因为试图在每次生成结束时都沉淀经验。借鉴 Hermes：改成 (1) 同一次 gap resolution 内不重复犯错（低成本，E3a），(2) 跨 session 经验只在「这次失败学到了新东西」时才沉淀，或走周期性批量审查（待验证，E3b）。

#### 3.4.4 不可借鉴项：Hermes 的 Skill 产物与本项目物种不同

Hermes 的「Skill」是 SKILL.md 程序性记忆文档（给 Hermes 自己读的），本项目的「Skill」是受治理的 Python `external_skills` 工具（给 trading agent 调用的）。前者不需要沙箱校验、不需要 Judge 评分、不需要合规审查、不需要热注册到 ToolRegistry。

因此 Hermes 的 `/learn` 命令（`agent/learn_prompt.py`）和 `skill_manage` 工具**不能直接移植**——我们必须保留自己的质控闸门与 Skill 产物形态。借鉴只限于循环形状和工具暴露方式，不涉及产物。

| 维度 | Hermes | 本项目 | 借鉴？ |
|------|--------|--------|--------|
| 循环形状 | 单 while 循环，无阶段分离 | 固定 DAG 管线 | ✅ 借鉴 |
| 沙箱工具访问 | execute_code 内 RPC 调 7 个白名单工具 | SandboxRunner 无工具 | ✅ 借鉴 |
| 失败处理 | LLM 自然看结果再决定，无显式反思步骤 | 专门 _reflect_on_failure + 结构化输出 | ✅ 简化 |
| 经验积累 | 周期性异步批量审查 | 计划每次沉淀 | ✅ 借鉴分层 |
| Skill 产物形态 | SKILL.md 程序性记忆 | Python external_skills 工具 | ❌ 不能抄 |
| 质量控制 | 无（LLM 自判） | StaticValidator + Judge + 沙箱 | ❌ 必须保留 |
| 合规审查 | 无 | 全局非投顾合规校验 | ❌ 必须保留 |
| 产物治理 | 无（写文件即完成） | _save_skill → external_skills → ToolRegistry → CapabilityIndex | ❌ 必须保留 |

---

## 4. 目标架构

```text
Agent Studio / Nanobot（用户交互、任务发起、上下文交接）
  │
  └─ SkillGeneration 专用 Agent Loop（复用 Nanobot 技术栈，但不运行在主对话循环内）
      │
      │  所有工具在各阶段均可调用（无阶段隔离）
      │
      ├─ 常驻工具
      │    run_readonly_query   ← 新增：白名单 + 限行数，查真实数据返回真值
      │    probe_interface      ← 新增：真调一次数据源/接口，回报可用性与返回形状
      │    recon 只读工具（已有）← 保留，作为结构的快速入口
      │    pipeline_tool        ← 单轮「生成→校验→沙箱→评分」，不在内部做多轮智能重试
      │
      ├─ 沙箱内工具（借鉴 Hermes execute_code 模式）
      │    SandboxRunner 改造为允许白名单只读工具调用（RPC 或等价机制）
      │    仅供构建/诊断/测试脚本使用，最终 Skill 代码不得依赖这些 RPC stub
      │
      └─ 终点闸门（保留，不放松）
           合规校验（复用全局非投顾） → _save_skill 入库 → 热注册 → 能力索引同步
```

核心变化：
- **取消「侦察阶段」**：不再有前置冻结的侦察。查询/探针/结构探测工具是循环内**常驻工具**，任何时候都能调用。
- **取消显式「根因分类 + 再侦察触发」机制**：借鉴 Hermes ReAct 模式，失败后 LLM 自己看结果决定下一步——需要查数据就调 `run_readonly_query`，需要改代码就调 `pipeline_tool`。不需要专门建一个「触发再侦察」的分支逻辑。
- **沙箱有工具**：SandboxRunner 内的代码能调只读白名单工具，把「验证数据源」和「写代码」合并成一步。
- **反思留痕但不硬编码驱动流程**：失败信息仍结构化记录（供审计与 Skill 工坊展示），同时压缩成 `failure_summary` 进入下一轮 Agent 上下文；不再用显式根因分类分支决定流程。

与现状的关键差异：

| 维度 | 当前（固定管线） | 目标（Agent 循环） |
|------|------------------|---------------------|
| 侦察时机 | 仅生成前一次，事实冻结 | 取消「侦察」概念——工具常驻，按需调用 |
| 环境感知 | 只读结构摘要 | 真值查询 + 接口探针 + 沙箱内也可调 |
| 失败修复 | 显式反思 → 分类 → 回灌代码 | ReAct 原生：LLM 看结果和 `failure_summary`，自己决定下一步调哪个工具 |
| 上下文 | 冷启动 | 复用 Nanobot 对话上下文与经验 |
| 治理 | 管线末端 | 不变，仍在循环终点 |

---

## 5. 技术方案

### 5.0 循环承载方式评估（已验证，2026-06-28）

#### 5.0.1 代码事实（已逐文件核对）

**Nanobot 的 AgentRunner 确实支持自主子循环。**

`core/embedded_nanobot/agent/runner.py` 的 `AgentRunner.run()`（L86-175）：

```python
for iteration in range(spec.max_iterations):   # 默认 100
    response = await self.provider.chat_with_retry(
        messages=messages, tools=spec.tools.get_definitions(), model=spec.model
    )
    if response.has_tool_calls:
        # 执行工具 → 结果追加到 messages → continue（回到循环头，不需要用户介入）
        results, new_events, fatal_error = await self._execute_tools(spec, response.tool_calls)
        for tool_call, result in zip(response.tool_calls, results):
            messages.append({"role": "tool", "tool_call_id": tool_call.id,
                             "name": tool_call.name, "content": sanitize_tool_result_content(result)})
        continue
    # 没有 tool_calls → 终止循环
    break
```

在一次 `handle_message` 里，LLM 可以连续调 0–100 次工具，**每次之间不需要用户说话**。这正是 ReAct agent 循环的形状。

**但当前 Skill 生成根本没走 Nanobot 的 AgentRunner。**

`app/services/skill_generation_service.py` 的 `_launch_pipeline_task()`（L435-583）：

```python
async def _run_pipeline():
    result = await asyncio.get_event_loop().run_in_executor(
        None,
        lambda: self._controller.run(spec, ...)  # ← IterationController，同步 for 循环
    )
```

`IterationController.run()`（`core/tools/external/iteration_controller.py`）是一个**同步 `for` 循环**，不是 agent 循环。LLM 只在每个管线阶段内部被调用（生成/反思/评分），循环逻辑是硬编码的 DAG。

**结论：Nanobot 与 Skill 生成是两个隔离的循环，当前毫无交集。** Skill 生成作为 `asyncio.create_task()` 启动的后台任务，在 Nanobot 的 AgentRunner 之外独立运行。

#### 5.0.2 两种承载方式的能力边界

| 维度 | X：Nanobot 托管子循环 | Y：独立 agent loop |
|------|----------------------|---------------------|
| **技术可行性** | ✅ 已验证，AgentRunner 设计即为此 | ✅ 已验证，当前独立循环可改造 |
| **LLM 可见性** | 全上下文（每轮所有工件进 LLM） | 可控（管线工具内部不暴露中间态） |
| **Token 消耗** | 极高（全上下文每轮都喂给 LLM） | 可控（管线工具打包，对外只暴露结果） |
| **改造量** | 大——每个管线阶段拆成 Nanobot 工具 + 治理适配 | 中等——IterationController 改造 + 工具集统一 |
| **质量闸门** | 需重建——StaticValidator/Judge/沙箱要变成工具链，LLM 可能跳过 | 保留——管线工具内部闭环不变 |
| **代码审计** | 复杂——LLM 有跳步骤的自由 | 简单——管线工具是黑盒，内部不受 LLM 影响 |
| **对现有 Nanobot 的影响** | 可能——新工具和长上下文影响常规对话 | 无——独立循环，隔离 |

#### 5.0.3 决策：走 Y

**不走 X 的决定性理由**：

X 意味着把 StaticValidator、SandboxRunner、OutputEvaluator、BusinessVerifier 全部拆成独立工具暴露给 LLM。这不仅是改造量大——它从根本上改变了质控模型：从「硬编码管线必过每一关」变成「LLM 决定过不过关」。当前质控闸门之所以可靠，正是因为它们是代码逻辑而非 LLM 自判。把闸门变成 LLM 可跳过的工具选项，是本末倒置。

**Y 的边界**：

- `IterationController` 从同步 `for` 循环改造成 ReAct agent loop（异步、工具驱动）
- 循环可以调 4 类工具：`run_readonly_query` / `probe_interface` / 结构探测 / `pipeline_tool`
- `pipeline_tool` 内部保留完整硬编码质控闭环（生成 → 校验 → 沙箱 → 评分），LLM 不能跳过
- 循环逻辑：LLM 看结果 → 决定调哪个工具 → 看新结果 → 再决定，直到通过或熔断

**未来是否合并回 X**：等 Y 跑通后，如果工具接口已统一且治理可控，可以把同一个循环塞回 Nanobot 的 AgentRunner 驱动——但这需要 Nanobot 能理解 `pipeline_tool` 的语义，是远期工作。

### 5.1 循环内常驻工具（替代「侦察层」）

当前 [recon_tools.py](../../../core/tools/external/recon_tools.py) 的 `RECON_TOOLS` 只在生成前跑一次。改造目标：**这些工具（加上新增的两个）变成循环内每一步都可以调用的常驻工具**，不再有「侦察阶段」的隔离。

新增两个真实查询/探针工具，仍受治理（只读、白名单、限额）：

1. `run_readonly_query(collection, filter, projection, limit)`
   - 在白名单集合上跑只读查询，返回**真实文档**（不是结构摘要）。
   - 强约束：只读（拒绝任何写操作语义）、`limit` 上限（如 ≤ 20）、字段投影建议、超时上限。
   - 价值：让生成器能用真实数据验证假设，而不是只看 schema 猜。

2. `probe_interface(source_or_helper, sample_args)`
   - 用样例参数真的调用一次数据源 helper / 外部接口，回报：是否成功、返回结构/形状、耗时、错误信息。
   - 强约束：只对登记在册的数据源/helper 生效、超时上限、对外部接口做频控保护。
   - 价值：让生成器在「把某接口写进代码前」先确认它当前真的可用、真的返回数据。

### 5.2 沙箱内工具访问（借鉴 Hermes execute_code 模式）

当前 [SandboxRunner](core/tools/external/sandbox_runner.py) 执行的脚本不能调用任何项目工具——只能 import Python 标准库和安装的第三方包。

借鉴 Hermes 的 `execute_code`：
- 脚本通过 RPC（或等价机制）回调主进程，调用**白名单只读工具**（与 §5.1 的常驻工具有重叠但不要求完全一致）。
- 白名单建议：`run_readonly_query`、`probe_interface`、`inspect_collection_schema`、`describe_runtime_helper`。
- 调用次数、超时、返回体积均有限额。

**边界约束（必须硬性执行）：沙箱 RPC 只允许用于构建期诊断，不允许进入最终 Skill 产物。**

| 场景 | 是否允许调用沙箱 RPC 工具 | 说明 |
|------|--------------------------|------|
| Agent 诊断脚本 | 允许 | 用于确认真实字段、接口返回形状、数据覆盖率 |
| 测试 harness / 探针脚本 | 允许 | 用于辅助验证候选代码是否满足契约 |
| 最终生成的 Skill 代码 | 不允许 | 不能 import `hermes_tools` 或任何构建期 RPC stub |
| 注册到 `external_skills` 的代码 | 不允许 | 只能依赖平台正式运行时 API，如 `core.skill_runtime.data_access` / `project_access` |

因此，静态校验需新增一条规则：候选 Skill 代码中出现 `hermes_tools`、构建期 RPC stub 或未登记的沙箱工具依赖时，直接判定失败，防止出现「构建时能跑、线上不能跑」的 Skill。

改造后的效果：
```python
# 诊断脚本内（在构建沙箱中运行，不是最终 Skill 代码）
from hermes_tools import run_readonly_query, probe_interface  # RPC stub

# 先查真实数据确认字段名
result = run_readonly_query("stock_basic_info", {"ts_code": "600519.SH"}, None, 1)
actual_fields = list(result[0].keys())  # 看到真实字段名

# 再把确认后的字段事实写入 Agent 上下文，供下一次 pipeline_tool 生成正式 Skill 代码
# 最终 Skill 代码仍只能使用 core.skill_runtime.* 正式 API
```

### 5.3 ReAct 反思替代显式根因分类

当前 `_reflect_on_failure` 有专用 prompt 模板，产出结构化 root_cause / fix_plan / confidence / should_retry。Hermes 证明这些**不是必需品**——在 ReAct 循环里，LLM 看到失败的 tool_result 后自然就会决定下一步。

改造方案：

1. **取消显式的「根因分类」分支逻辑**。不再需要代码判断 `code-level vs data-level` 来决定走不同路径。
2. **保留 should_retry 但简化语义**：改造成单一的循环控制信号，不需要三态分类。LLM 自己通过调用的工具选择来表达「需要查数据」还是「需要改代码」——它调 `run_readonly_query` 就是在查数据，调 `pipeline_tool` 就是在改代码。
3. **保留失败的结构化记录**（root_cause / stage / error / 轮次），但定位从「硬编码驱动下一步」改为「审计留痕 + Skill 工坊展示 + Agent 工作记忆」。记录写入 `IterationRound.reflection` 不变，但不再作为旧式 `_build_rich_feedback` 指令直接塞给代码生成器。
4. **新增 `failure_summary`**：每轮失败后生成一段短摘要，进入下一轮 Agent 上下文，避免长 stdout/stderr 和工具结果淹没关键事实。
5. **保留熔断**：`MAX_ITERATIONS = 8`、`_STALE_FAILURE_THRESHOLD = 5`（连续相同失败仍判不可恢复）、工具调用总数上限。

`failure_summary` 示例：

```json
{
  "failure_summary": "当前候选代码把 get_external_historical_data 返回的 close 当成 pe_ttm 使用，导致历史估值分位数错误。已确认该 helper 只返回 OHLCV；下一轮应探测或使用 get_external_valuation_data 获取 pe_ttm/pb_mrq 时间序列。",
  "failed_contracts": ["historical_pe_series", "historical_pb_series"],
  "verified_facts": [
    "get_external_historical_data returns OHLCV only",
    "get_external_valuation_data returns pe_ttm/pb_mrq"
  ]
}
```

这不是恢复旧的「反思指令驱动流程」，而是给 Agent Loop 一块稳定的工作记忆：流程仍由 LLM 下一步工具选择决定。

### 5.4 管线工具化（支柱，非可选）

把「生成 → 静态校验 → 沙箱 → 评分」封装成一个对循环可见的单一工具 `pipeline_tool`。循环一次调用即获得一轮完整质控结果。

这是「中间路线」（§3.3）之所以成立的支柱：没有它，循环每轮要调 4 次工具（CodeGenerator → StaticValidator → SandboxRunner → OutputEvaluator），每个工具调用都增加一轮 LLM 推理，token 指数增长。打包成一步后，LLM 级联和 token 膨胀问题同时解决。

`pipeline_tool` 内部仍是既有质控闭环，不放松任何一步。

**关键边界：`pipeline_tool` 是“单轮候选生成与质控工具”，不是旧 `IterationController.run()` 的多轮重试黑盒。**

原因：如果 `pipeline_tool` 内部继续自己跑 8 轮生成/反思/重试，外层 Agent Loop 只能在全部失败后才介入，仍然会重复旧管线「错误方向上消耗多轮」的问题。正确边界是：

```text
Agent Loop
  → 可先调 run_readonly_query / probe_interface 查真值
  → 调 pipeline_tool 生成并评估一版候选 Skill
  → 看失败摘要 / 评分 / 契约缺口
  → 必要时再调查询/探针
  → 再调 pipeline_tool
```

`pipeline_tool` 对外返回应包含：
- `status`：pass / fail / blocked
- `code_path` / `snapshot_path`：候选代码与本轮快照
- `static_validation`：静态校验结果
- `sandbox_result`：沙箱 stdout/stderr、异常、样例输出
- `evaluation`：Judge 评分、失败契约、业务验收结果
- `failure_summary`：供下一轮 Agent 使用的压缩失败摘要
- `verified_facts`：本轮确认过的环境事实，如「某 helper 只返回 OHLCV」

多轮策略、是否再查数据、是否继续生成，由外层 Agent Loop 决定；`MAX_ITERATIONS` / `_STALE_FAILURE_THRESHOLD` 迁移为外层循环熔断条件。

### 5.5 上下文与经验共享（分两层）

基于 Hermes「周期性异步批量审查」的启发，将经验共享拆为两层：

#### 第一层（低成本，确定性高）：同一次 gap resolution 内不重复犯错

1. **加厚 handoff_context**：`SkillGenerationService.start_session()` 接收 Nanobot 已掌握的现状摘要（已搜过的能力、已确认的数据源、用户澄清结论、相关 gap 上下文）。
2. **循环内事实累积**：每一步的工具调用结果自然累积在消息历史中，不需要额外存储。
3. **失败原因回写 job 文档**：失败的结构化记录写入 `agent_workshop_gap_resolution_jobs` 对应 gap 条目，同一次 job 内的其他 gap 或同一 gap 的重试可以读取。

### 5.6 异步任务 in-flight 幂等锁（硬约束）

Skill 创建是异步任务，因此系统存在「已提交但尚未注册为可用 Skill」的中间态。这个中间态如果不纳入去重，会出现同一 gap 被两个入口同时生成的情况：

```text
入口 A 提交 Skill 生成
  → skill_creation_sessions: generating
  → capability index: 暂时还没有

入口 B 稍后检查
  → capability index 查不到
  → 误以为没有
  → 又提交一个 Skill 生成
```

因此，Agent Loop 启动前必须执行 in-flight 去重检查，且该检查是硬约束，不是体验优化。

创建前按顺序检查三层：

1. **已注册 Skill**：CapabilityIndex / ToolRegistry 中已有可复用能力。
2. **正在生成中的 Skill session**：`skill_creation_sessions.status in ["gathering", "confirmed", "generating"]`，且匹配同一 `agent_spec_id` / `workshop_session_id` / `gap_id` 或同一 `target_capability`。
3. **正在运行中的 GapJob**：`agent_workshop_gap_resolution_jobs` 中同一 session + gap 集合的 active job。

命中第 2 或第 3 层时，不新建任务，直接复用已有 `skill_session_id` / `job_id`，并把状态返回给前端。换句话说：

> in-flight 状态也是能力占用状态。

这条约束必须覆盖所有入口：

- Agent Studio 手动触发 Skill 补齐
- Nanobot 自动调用 gap resolution
- 后台 GapJob worker 重试
- 用户重复点击或刷新后再次触发

验收标准：同一 `agent_spec_id + gap_id/target_capability` 在任意时刻最多只有一个 active Skill 生成会话。

---

## 6. 实施计划与进度

> 推进原则：先以**最小侵入**验证「Agent 化是否真能解决复杂需求」，再决定是否扩大改造面。每一步都不动 Nanobot 底座、不引入 Hermes 替换底座。
> 
> Phase 顺序按依赖关系排列，不是按重要性。E2a 和 E2b 必须并行推进（互不依赖，但 E2b 是整个中间路线的支柱）。

### Phase E0：专用循环边界 + handoff_context 加厚 + in-flight 幂等

状态：**部分完成（2026-06-28）**。

已完成：

1. [iteration_controller.py](../../../core/tools/external/iteration_controller.py) 新增 `run_agentic()`，Skill 生成默认进入 **SkillGeneration 专用 Agent Loop**，不运行在 Nanobot 主对话循环内。
2. [skill_generation_service.py](../../../app/services/skill_generation_service.py) 默认调用 `run_agentic()`；保留 `SKILL_GENERATION_AGENTIC_ENABLED=false` 回退旧 `run()` 管线。
3. 上游 Agent 工坊入口已补充 active `skill_creation_sessions` 复用逻辑，避免同一 gap 被同步入口和异步 GapJob 重复生成。

待完成：

1. `handoff_context` 仍需进一步加厚为完整现状摘要，并在 Agentic prompt 中更系统地消费。
2. in-flight 幂等需要补充更完整的集成测试，覆盖所有入口。

内容：

1. 明确 Skill 生成采用 **SkillGeneration 专用 Agent Loop**：复用 Nanobot provider / tool schema / message 协议，但不运行在 Nanobot 主对话循环内。
2. 将 `handoff_context` 从当前 5 个薄字段加厚为完整的现状摘要（已搜过的能力、已确认的数据源、用户澄清结论、相关 gap 上下文）。
3. 在所有 Skill 生成入口前增加 in-flight 幂等锁：先查已注册 Skill、再查 active `skill_creation_sessions`、再查 active GapJob，命中则复用而不是新建。

前置依赖：无。

验收：

1. 明确当前循环承载方式和后续演进路径。
2. 由 Agent Studio 发起的生成，不再重复侦察 Nanobot 已确认的事实。
3. 同一 `agent_spec_id + gap_id/target_capability` 在任意时刻最多只有一个 active Skill 生成会话。

### Phase E1：循环内常驻查询/探针工具

状态：**已完成第一版（2026-06-28）**。

已完成：

1. [recon_tools.py](../../../core/tools/external/recon_tools.py) 新增 `run_readonly_query()`：
   - 只允许查询 `skill_runtime.catalog.SUPPORTED_COLLECTIONS` 白名单集合。
   - 仅支持简单等值过滤，拒绝 Mongo `$` 操作符。
   - `limit` 上限为 20，并限制返回体积。
2. [recon_tools.py](../../../core/tools/external/recon_tools.py) 新增 `probe_interface()`：
   - 允许真实调用 `core.skill_runtime.data_access`、`project_access`、`external_sources` 中公开 helper。
   - 返回 success、耗时、返回形状、结果预览。
3. 两个工具已加入 `RECON_TOOLS`，并注册进 `run_agentic()` 的常驻工具集。
4. 已新增测试覆盖操作符拒绝和 helper 返回形状探测。

待增强：

1. 增加更细粒度的频控/超时指标统计。
2. 在真实复杂 Skill 生成中验证是否能纠正 schema 误判。

内容：

1. 新增 `run_readonly_query`、`probe_interface`，落实只读/白名单/限额/超时/频控约束。
2. 注册进循环的工具集（不再绑定「侦察阶段」——工具在任何阶段均可调用）。

前置依赖：无（可在 E0 并行）。

验收：

1. 生成过程中 LLM 能用真值查询纠正一次「凭 schema 误判」的场景。
2. 接口探针能正确识别一个不可用/返回为空的数据源。
3. 两个工具均无法触发写操作，且受 limit/超时/频控保护。

### Phase E2a：ReAct 反思替代显式根因分类

状态：**已完成第一版（2026-06-28）**。

已完成：

1. [iteration_controller.py](../../../core/tools/external/iteration_controller.py) 新增 Agentic 外层循环，由 LLM 在每一步自主选择查询/探针/诊断脚本/`pipeline_tool`。
2. `pipeline_tool` 失败后返回 `failure_summary`、`should_retry`、`evaluation`、`sandbox_result`，由外层 Agent Loop 决定下一步，而不是旧管线内部固定重试。
3. `verified_facts` 会从 `run_readonly_query`、`probe_interface`、`run_diagnostic_script` 的工具结果中自动累积。
4. `agentic_trace` 与 `verified_facts` 已写入 `PipelineResult.final_metadata`，成功/失败均可审计。

保留项：

- `_reflect_on_failure()` 暂未删除，仍作为 `pipeline_tool` 单轮内部的失败审计和 `should_retry` 判断来源；外层流程不再依赖显式「根因分类 → 再侦察」分支。

待增强：

1. 将 `failure_summary` 更明确地追加进下一轮 LLM 消息，而不是只作为状态变量供下一次 `pipeline_tool` 使用。
2. 真实复杂用例验证后，再决定是否进一步弱化 `_reflect_on_failure()`。

前置依赖：Phase E1（循环已有真实查询/探针工具可用）。

内容：

1. 移除显式的「根因分类 → 分支走不同路径」逻辑。
2. 简化 `_reflect_on_failure` 为审计留痕（root_cause / stage / error / 轮次），不再回灌给代码生成器作为「指令」。
3. 让 LLM 通过工具选择自然表达「需要查数据」还是「需要改代码」。
4. 保留 `should_retry` / `MAX_ITERATIONS` / `_STALE_FAILURE_THRESHOLD` 等熔断。

验收：

1. 对一个「数据层误判导致的失败」需求，循环能自行调用 `run_readonly_query` 查真值后修复。
2. 连续相同失败仍能在阈值内收敛为 FAIL，不会无限循环。
3. 每轮失败仍有结构化留痕，可审计（不受简化影响）。

### Phase E2b：管线工具化 + 沙箱工具访问

状态：**已完成第一版（2026-06-28）**。

已完成：

1. [iteration_controller.py](../../../core/tools/external/iteration_controller.py) 新增 `_run_pipeline_tool_once()`，将「代码生成 → 静态校验 → 沙箱执行 → Judge 评分 → 业务验收 → 边缘测试」封装为单轮 `pipeline_tool`。
2. `pipeline_tool` 对外返回 `status`、`code_path`、`snapshot_path`、`static_validation`、`sandbox_result`、`evaluation`、`failure_summary`、`verified_facts`、`should_retry`。
3. [sandbox_runner.py](../../../core/tools/external/sandbox_runner.py) 新增 `run_diagnostic_script()`：
   - 构建期诊断脚本可临时 `import hermes_tools`。
   - `hermes_tools` stub 只映射白名单只读工具。
   - 单次最多 12 次工具调用。
4. [static_validator.py](../../../core/tools/external/static_validator.py) 已拦截最终 Skill 代码导入 `hermes_tools`、`sandbox_tools`、`skill_build_tools`，避免构建期 stub 泄漏到线上运行时。
5. 新增 [test_skill_generation_agentic_engine.py](../../../tests/core/tools/test_skill_generation_agentic_engine.py)，覆盖诊断沙箱、构建期 stub、最终 Skill 拦截、查询/探针工具。

待增强：

1. 诊断沙箱目前是等价 stub，不是完整 RPC server；后续如需要更强隔离，可替换为真正主进程 RPC dispatch。
2. `pipeline_tool` 的 stale failure 熔断目前主要依赖外层轮次和内部 `should_retry`，后续可补充显式相同失败签名计数。

前置依赖：无（技术层面独立，可与 E2a 并行；但从验证节奏看，建议 E2a/E2b 同批推进）。

内容：

1. 把「生成 → 静态校验 → 沙箱 → 评分」封装为单一 `pipeline_tool`。内部质控闭环不变，对外暴露为一个函数调用。
2. 改造 `SandboxRunner`，允许沙箱内脚本通过 RPC（或等价机制）调用白名单只读工具。白名单初始定为 `run_readonly_query`、`probe_interface`、`inspect_collection_schema`、`describe_runtime_helper`。
3. 沙箱工具调用受次数/超时/返回体积限额保护。

验收：

1. 循环单次调用 `pipeline_tool` 即可获得一轮完整质控结果（生成+校验+沙箱+评分），LLM 推理轮数不因步骤数膨胀。
2. 沙箱内代码能在一次执行中先查真值再写解析逻辑（不再需要「先侦察再生成」的两阶段分离）。
3. 沙箱工具调用无法绕过白名单，且受限额保护。

### Phase E3a：同 job 内经验不重复犯错（低成本）

状态：**已完成第一版（2026-06-28）**。

已完成：

1. [nanobot_agent_builder_tools.py](../../../core/tools/implementations/agent_builder/nanobot_agent_builder_tools.py) 新增同 job 经验聚合：`_collect_gap_job_known_context()` 会从同一 GapJob 的其他 gap 中收集 `agentic_failure_summary` 与 `agentic_verified_facts`。
2. GapJob worker 在启动后续 Skill session 时，会将已知失败摘要和已验证事实写入 `handoff_context.known_failure_summaries` / `known_verified_facts`。
3. GapJob 轮询到 Skill session `completed` / `failed` 时，会从 `skill_creation_sessions.pipeline_result.final_metadata` 抽取并回写：
   - `agentic_failure_summary`
   - `agentic_verified_facts`
   - `agentic_trace`
   - `generation_engine`
4. [requirement_analyzer.py](../../../core/tools/external/requirement_analyzer.py) 的上游交接上下文会展示同 job 已知失败和已验证事实，要求后续 Skill 不要重复采用已被证伪的数据源/字段假设。
5. [skill_generation_service.py](../../../app/services/skill_generation_service.py) 会将 handoff_context 中的已知经验写入 `SkillSpec.metadata`。
6. [iteration_controller.py](../../../core/tools/external/iteration_controller.py) 的 Agentic 初始 prompt 会消费 `SkillSpec.metadata.known_failure_summaries` / `known_verified_facts`。

待增强：

1. 增加同 job 多 gap 经验复用的集成测试。
2. 在真实 gap resolution 任务中观察是否明显减少重复踩坑。

前置依赖：Phase E2a+E2b（循环已有完整工具集与审计留痕）。

内容：

1. 失败原因回写 job 文档（已有 `agent_workshop_gap_resolution_jobs` gap 条目）。
2. 同一次 job 内的其他 gap 或同一 gap 的重试，在启动时从 job 文档读取已知失败原因，注入 handoff_context。
3. 循环内工具调用结果自然累积在消息历史中（不需要额外机制）。

验收：

1. 同一次 gap resolution 中，第一个 gap 踩过的坑不会在第二个 gap 重复。
2. 同一 gap 重试时，不再从零开始侦察已确认不可用的数据源。

### Phase E3b：跨 session 经验积累与检索（待验证）

前置依赖：Phase E3a 完成 + Phase E1/E2 在真实复杂需求上跑过数据。

内容：

1. 观察：做完 E1–E3a 之后，剩余失败中有多少是「如果它能记得上次跨 session 踩的坑就能修好」的。
2. 如果比例显著（>20% 的跨 session 同类失败），再设计具体沉淀与检索机制（优先复用 `CapabilityIndexService`）。
3. 如果比例低（<20%），标记为「不值得工程化」，关闭此 Phase。

**本 Phase 不做前置设计。** 在数据出来之前设计经验存储的 schema、检索策略、prompt 注入方式，是过早优化。

---

## 7. 关键风险与控制

| 风险 | 控制 |
|------|------|
| Nanobot 无法承载自主子循环 | 走 Phase E0 先行评估 + 独立子 agent 循环 Y 方案兜底 |
| 新增查询/探针被滥用为写操作或越权访问 | 只读语义校验 + 集合/数据源白名单 + limit/超时 + 拒绝写 |
| 接口探针对外部数据源造成压力 | 频控、超时、仅对登记数据源生效 |
| 工具过多导致 token 膨胀或 LLM 级联 | 管线工具化（E2b 支柱）把 4 步打包为 1 步；否则不准上线 |
| 循环无限重试 | 复用 `MAX_ITERATIONS` / `_STALE_FAILURE_THRESHOLD` 熔断 + 工具调用总数上限 |
| 沙箱工具访问被突破白名单 | 白名单硬编码在服务端 RPC dispatch 层，不在脚本侧可篡改位置 |
| 合规口径漂移 | 终点强制复用全局非投顾合规校验，不在引擎内另写规则 |
| 治理被绕过 | 正式 Skill 必须经 `_save_skill` 入库 + 热注册 + 能力索引同步 |
| 跨 session 经验过度设计 | Phase E3b 设硬门槛（先看数据再决定），不提前设计 |

---

## 8. 结论

三条痛点（不会自递归、上下文不共享、无法感知环境）是同一个根因：Skill 生成内核是固定管线而非 Agent 循环。正确的方向是**把内核 Agent 化**，而不是更换底座为 Hermes。

Hermes 提供了三个高价值可借鉴模式（单循环编排、沙箱工具访问、异步批量经验积累），但它的 Skill 产物形态、质量控制策略与我们物种不同，不能移植。

最稳、最省的落地路径：

```text
Phase E0 专用循环边界 + 加厚 handoff_context + in-flight 幂等
  → Phase E1 常驻查询/探针工具（循环任一步都可调）
  → Phase E2a ReAct 反思替代显式根因分类 + failure_summary 工作记忆
  → Phase E2b 单轮 pipeline_tool + 沙箱工具访问边界
  → Phase E3a 同 job 内不重复犯错（已完成第一版）
  → Phase E3b 跨 session 经验（看数据再决定做不做）
```

关键约束：
- 管线工具化（E2b）是本方案成立的支柱，不做则中间路线失效，token 膨胀风险复活。
- 跨 session 经验（E3b）不在当前阶段设计——先做完 E1+E2 并在真实复杂需求上跑数据后，再决定范围。
- 治理、合规、质控闸门一毫米不松。

先做 Phase E1–E2 拿到「能查数据、能验接口、能自递归」的最小闭环；截至 2026-06-28，E1–E3a 已完成第一版实现，并通过新增 Agentic Engine 单测。下一步应在真实复杂需求上验证效果，再决定 E3b 是否需要跨 session 经验。
