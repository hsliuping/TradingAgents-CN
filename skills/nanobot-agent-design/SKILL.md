---
name: nanobot-agent-design
description: Use when the user asks Nanobot to design, create, generate, adapt, or scaffold a new agent from existing project resources, tools, skills, prompts, or agent blueprints.
metadata: '{"nanobot":{"always":true}}'
---

# Nanobot Agent Design

Use this skill when the user wants Nanobot to create or redesign an agent based on the resources already present in this repository.

Do not directly hand off the task to the old Agent Workshop flow unless the user explicitly asks to use that workflow.
The default path for Nanobot is a lighter workflow built around resource scouting, confirmation, and targeted generation.

This repository also supports v3.0 style configurable agents stored in MongoDB.
Nanobot should treat database-backed agent assets as first-class resources, not just the built-in Python agent registry.

Relevant design references:

1. `docs/design/v3.0/ai-workflow-generation.md`
2. `docs/design/v3.0/agent-workshop-interface-sequence.md`
3. `docs/design/v3.0/implementation-status-report.md`

## Core Principle

Nanobot should not start from a blank slate and should not jump straight into heavy multi-step workflow services.
It should first discover what already exists, confirm the reusable parts, and only then generate the minimum agent artifacts needed for the request.

## Resource Discovery Order

When the user asks for a new agent, inspect resources in this order:

1. Use `search_project_capabilities` to find relevant tools, skills, MCP capabilities, and external skills.
2. Use `inspect_agent_blueprints` to find similar built-in agents.
3. Use `inspect_runtime_agent_configs` to find database-backed runtime agents and UniversalAgent candidates.
4. Use `inspect_agent_workshop_assets` to find reusable `agent_specs`, `agent_versions`, and prompt-template lineage.
5. Use `get_agent_blueprint_details` on the closest built-in candidate.
6. Only then read focused source files such as:
   - `core/agents/config.py`
   - `core/agents/universal.py`
   - `core/agents/factory.py`
   - the nearest adapter under `core/agents/adapters/`
   - `core/tools/config.py` or the specific tool implementation file
   - `skills/*/SKILL.md` if the task depends on a specialized workflow

Do not start by reading large service files or old workshop orchestration code unless the task specifically needs it.

## Resource Confirmation Rules

Before claiming a resource is usable, confirm at least one of these:

1. It appears in `search_project_capabilities` as bindable.
2. It appears in a registered agent blueprint.
3. It appears in `inspect_runtime_agent_configs` as an existing runtime agent definition.
4. It appears in `inspect_agent_workshop_assets` as an existing spec or built version.
5. Its implementation file and tool metadata both exist.

If a capability is only mentioned in old docs or old configs but is not bindable or not implemented, treat it as a gap, not an available dependency.

Nanobot must never collapse different resource layers into a single undifferentiated “existing agents” list.

It must keep these layers distinct in both reasoning and final user-facing output:

1. built-in blueprints from the Python agent registry
2. runtime-configured agents from `agent_configs` and `tool_agent_bindings`
3. workshop assets from `agent_specs` and `agent_versions`

If the user asks why something is not visible in Agent Workshop, Nanobot must explicitly state that the Agent Workshop UI reflects workshop assets, not every runtime-configured agent and not built-in blueprints.

## Default Design Workflow

For a new agent request, Nanobot should follow this sequence:

1. If the user's request is still high-level, call `prepare_agent_requirement_intake` first.
2. Restate the target job of the agent in one sentence.
3. Identify the minimum capabilities the agent truly needs.
4. Search project capabilities for those needs.
5. Check whether an existing runtime-configured agent or published version already covers the need.
6. Find the nearest existing built-in agent blueprint.
7. Decide the build path:
   - reuse an existing agent with light adaptation
   - publish or refine an existing configurable agent asset
   - create a new prompt/template-driven agent
   - create a new database-configured UniversalAgent-backed agent
   - create a new tool-bound agent
   - create a new workflow node only if a standalone agent is not enough
8. Generate only the minimal artifacts needed.

Prefer a narrow and composable agent over a large all-in-one design.

## Minimal Generation Chain

When the user asks Nanobot to actually generate a new configurable agent now, prefer this direct chain:

1. Use `prepare_agent_generation_confirmation` to generate a short confirmation brief before any write.
2. Wait for explicit user confirmation if responsibility, output shape, tool set, or overwrite risk could change the intended agent shape.
3. After confirmation, use `generate_confirmed_candidate_agent` as the default one-shot path.

If the task specifically needs low-level control, the internal write chain is:

1. `create_or_update_runtime_agent_config`
2. `create_or_update_universal_agent_prompt_template`
3. `bind_agent_tools_and_validate_candidate`

This is the default generation path for a new lightweight candidate.
Do not detour into the old workshop flow unless the user explicitly asks for spec/version/publish governance.

## Confirmation Gate

Before the confirmation gate, Nanobot should check whether a requirement-intake gate is needed.

Use `prepare_agent_requirement_intake` when the user only gives a high-level idea such as “帮我做一个估值 agent” and the actual intended shape is still unclear.

The minimum intake dimensions are:

1. single responsibility
2. expected output shape
3. non-goals
4. required or preferred tools
5. new creation vs overwrite/iteration

If the user asks a follow-up such as “报告会是什么样子”, “给我看报告样式”, “输出结构是什么”, or any similar style/format question before generation, Nanobot must treat that as output-shape clarification rather than as a request for a filled report.

For that case, the intake must also clarify:

1. whether the user wants only a section skeleton / field template, or a placeholder-only mock layout
2. which sections are in scope, and which sections must not be added implicitly

For stock-analysis or valuation agents, Nanobot must treat the following as hard rules and explicit intake dimensions:

1. trading advice, position sizing, entry ranges, stop-loss lines, target prices, and other action-oriented content are globally forbidden for all agents and cannot be enabled
2. which valuation methods are in scope and which are out of scope
3. whether generation should stop at configuration validation or also run a real-stock sample report
4. if the user is asking about report style, whether the preview is structure-only and which report sections are allowed

If those dimensions are missing, Nanobot must keep asking clarification questions and must not jump to confirmation just because a candidate tool set already exists.

Before writing any database artifacts, Nanobot should decide whether a confirmation gate is required.

It is required when at least one of these is true:

1. The single responsibility could be interpreted in multiple ways.
2. The expected output shape is still ambiguous.
3. The bound tool set could materially change the agent's behavior.
4. The target `agent_id` already has config, template, or tool bindings.
5. The user did not explicitly say to proceed with creation after seeing the proposed shape.

In those cases:

1. Generate a short confirmation brief.
2. Ask for a clear yes/no style user confirmation.
3. Only then call the write path.

If `prepare_agent_generation_confirmation` returns `confirmation_brief.user_confirmation_template`, Nanobot should use that template as the primary user-facing confirmation message instead of rewriting the confirmation in its own words.

Allowed behavior:

1. Paste or closely preserve `user_confirmation_template` first.
2. Add at most one short sentence before or after it if needed for transition.
3. Preserve the suggested confirmation reply format.

Disallowed behavior:

1. Re-expand the confirmation into a looser freeform explanation.
2. Drop the report contract details when they already exist in the template.
3. Replace the template with a shorter but vaguer summary.

For stock-analysis or valuation agents, Nanobot must not auto-run a real ticker example unless the user explicitly agreed to that test strategy during intake or confirmation.

Nanobot must never ask the user whether trading advice is allowed, because that policy is already fixed: it is not allowed.

When the user is only asking about report style, Nanobot must not fabricate a full stock report with real-looking numbers, confidence scores, price ranges, or detailed scenario content. It must answer with a structure skeleton using placeholders or field names unless the user explicitly asked for a placeholder mock layout.

For valuation agents specifically, Nanobot must not silently widen the report into a full-stack analysis package. If the current confirmed responsibility is valuation analysis, a style preview must stay inside valuation-related sections unless the user explicitly asked to include additional modules. It must not add technical analysis, trading plans, multi-role debate synthesis, or bull/bear comparison by default.

When answering a style-preview question, Nanobot must anchor to the immediately preceding confirmed context in the conversation, including the proposed output_field and target responsibility, instead of switching to a generic “financial full report” template.

## Style Preview Examples

Use the following examples as behavioral templates when the user is asking what a generated report would look like.

### Example 1: Correct Structure-Only Preview

Context:

1. The proposed agent responsibility is valuation analysis only.
2. The proposed output_field is `valuation_report`.
3. The user asks: “这个 agent 生成的报告会是什么样子？”

Good answer shape:

```text
可以先把 valuation_report 设计成下面这种结构骨架：

- 标的基本信息
- 估值方法说明
- 核心估值指标摘要
- 同行业可比结果
- 估值结论摘要
- 主要风险提示

说明：这里只展示报告结构，不填充真实内容，也不扩展到技术分析、交易计划或多空辩论。
```

Why this is correct:

1. It stays inside valuation scope.
2. It answers the style question with a skeleton only.
3. It does not fabricate realistic-looking report content.

### Example 2: Correct Placeholder Mock Preview

Context:

1. The proposed agent responsibility is valuation analysis only.
2. The user explicitly asks for a placeholder-style mock layout.

Good answer shape:

```text
可以，下面给你看一个占位符版本的样式预览：

- 标的：某A股公司
- 估值方法：PE / PB / PEG 相对估值
- 当前估值判断：[占位符]
- 同行业对比摘要：[占位符]
- 估值偏高/偏低的依据：[占位符]
- 风险提示：[占位符]

说明：这是样式预览，不代表真实研究结果，不包含交易建议或操作性结论。
```

Why this is correct:

1. The user explicitly allowed a placeholder mock.
2. The answer still stays inside valuation scope.
3. The answer uses placeholders rather than fabricated real analysis.

### Example 3: Forbidden Overreach

If the current conversation is only about a valuation-agent style preview, Nanobot must not answer with content like this:

```text
- 投资观点：建议买入
- 目标价区间：...
- 技术面结论：...
- 交易计划：...
- Bull / Bear 情景推演：...
- 置信度：...
```

Why this is wrong:

1. It turns a style-preview question into a full report.
2. It introduces globally forbidden trading advice and action-oriented content.
3. It silently widens the scope beyond valuation analysis.
4. It fabricates details that were never requested.

Default rule:

1. If the user asks only what the report looks like, prefer a section skeleton.
2. Only show placeholder mock content if the user explicitly asked for it.
3. Keep the preview inside the already confirmed responsibility and output_field context.

## Report Contract Confirmation Flow

If the intended output is a report-like artifact, Nanobot should not ask for final creation confirmation with only a vague phrase such as “结构化报告” or “输出报告”.

Before asking the user for the final yes/no confirmation, the confirmation payload should include a compact report contract with both content scope and style scope.

That report contract should contain at least:

1. report content scope
   - which sections are included
   - which sections are explicitly excluded
   - whether the scope is limited to the current single responsibility
2. report style mode
   - structure skeleton only
   - or placeholder-only mock layout
3. output_field binding
   - which output_field the report maps to
4. hard constraints
   - no trading advice
   - no action-oriented instructions
   - no unconfirmed module expansion

For valuation agents, the default report contract should be conservative:

1. content scope defaults to valuation-related sections only
2. style mode defaults to structure skeleton only
3. technical analysis, trading plans, multi-role debate synthesis, and other non-valuation modules are excluded unless the user explicitly adds them

Nanobot should present this report contract during confirmation so the user can verify both “报告写什么” and “报告长什么样” before any database artifacts are written.

## Thin Decision Protocol

Nanobot must treat agent creation as a thin decision workflow, not a heavy workshop pipeline.

The immediate goal is not version governance.
The immediate goal is:

1. Can a runnable agent be generated now?
2. Will that generated agent match the user's intended job closely enough?

The protocol has only five stages:

1. Target Clarification
   - Restate the agent's single responsibility in one sentence.
   - Reject multi-role bundling unless the user explicitly wants a multi-role workflow.
2. Resource Scouting
   - Search project capabilities.
   - Inspect runtime-configured agents.
   - Inspect workshop assets.
   - Inspect the nearest built-in blueprint if still needed.
3. Coverage Confirmation
   - Separate confirmed resources from merely similar ones.
   - Mark every missing dependency as a real gap.
4. Build Path Decision
   - Choose exactly one primary path.
   - Do not mix multiple creation paths unless there is a hard dependency.
5. Minimal Artifact Plan
   - List only the smallest set of artifacts that must change.
   - If no artifact needs to be created yet, say so explicitly.

This protocol must not expand into the old workshop stages such as extended requirement chat, long gap-analysis loops, evaluation pipelines, or publish governance, unless the user explicitly asks for those flows.

Versioning, evaluation, and publish governance are secondary.
They should not block the first question: can Nanobot generate the right agent shape now?

## Primary Build Path Rule

Nanobot must choose one and only one primary build path first:

1. Reuse existing built-in blueprint.
2. Reuse or refine existing runtime-configured agent.
3. Reuse or publish an existing workshop version.
4. Create a new UniversalAgent-backed config.
5. Create a new Python agent adapter.

Use the first path that fully satisfies the requirement.
Only escalate to a lower path when the higher path is insufficient.

## Reusable Capability Promotion Rule

When Nanobot discovers that the requested capability does not already exist, it must decide whether the gap is one-off or reusable before writing code.

Treat the gap as a reusable capability when most of these are true:

1. The logic is parameterized by stable inputs such as `symbol`, `start_date`, `end_date`, `report_period`, or similar business parameters.
2. The same analysis or calculation would reasonably be reused for other stocks, other dates, or other agents.
3. The implementation is deterministic or mostly deterministic once inputs are fixed.
4. The result is a named business capability rather than a one-time debugging probe.

If the gap is reusable, Nanobot must not stop at a local `temp/*.py` script as the final artifact.
The default target should be a reusable skill artifact, preferably an executable external skill that can be loaded from `external_skills` and reused by later runs.

For reusable gaps, Nanobot should explicitly report:

1. why this is a reusable capability rather than a one-off script
2. the minimal reusable artifact to create
3. whether a temporary probe script is only being used for short validation before the reusable skill is created

`temp/*.py` is acceptable only for short-lived inspection, schema probing, or data validation.
It is not an acceptable final delivery for a reusable stock-analysis capability.

## Required Output Contract

When Nanobot proposes or creates an agent, its answer must contain these sections in this order.
Do not skip them.

1. Target Responsibility
   - One sentence only.
2. Can Generate Now
   - Answer yes or no.
   - State the narrowest reason.
3. Desired Shape Match
   - Explain whether the generated agent would match the user's intended job.
   - Call out obvious mismatch risk early.
4. Confirmed Reusable Resources
   - Only resources that were actually confirmed.
   - Include the resource type for each item: capability, blueprint, runtime agent, workshop asset, prompt asset.
   - Group results by source layer instead of mixing blueprint, runtime agent, and workshop asset entries into one flat “existing agent” table.
5. Unconfirmed or Similar Resources
   - Items that look relevant but were not confirmed.
6. Real Gaps
   - Missing tools, missing prompts, missing bindings, missing runtime config, missing code.
7. Chosen Build Path
   - Exactly one primary path from the list above.
   - Explain why it is the lightest viable path.
8. Minimal Artifact Plan
   - List the exact records or files that need to be created or updated.
   - Prefer database/config artifacts over new code when appropriate.

For the default lightweight path, the expected artifacts are usually:

1. `agent_configs`
2. `prompt_templates`
3. `tool_agent_bindings`

If Nanobot is asked to proceed immediately, it should keep the same structure and then append:

9. Execution Result
   - What was actually created, updated, or left unchanged.

## Output Template

Use this exact shape when responding to agent-creation requests:

```text
Target Responsibility
- ...

Can Generate Now
- yes/no: ...

Desired Shape Match
- match_level: high/medium/low
- reason: ...

Confirmed Reusable Resources
- [type] name: why it is usable

Unconfirmed or Similar Resources
- [type] name: why it is only suspected

Real Gaps
- ...

Chosen Build Path
- primary_path: ...
- reason: ...

Minimal Artifact Plan
- ...
```

If execution has already happened, append:

```text
Execution Result
- created: ...
- updated: ...
- unchanged: ...
```

## Visibility Contract

If the runtime can surface progress to the user, Nanobot should expose visible stage updates using short plain-language messages.

Preferred visible stages:

1. 正在确认目标职责
2. 正在判断是否可直接生成
3. 正在检索可复用能力
4. 正在检查现有配置式 Agent
5. 正在判断生成结果是否贴合目标
6. 正在整理最终方案

These are not a heavy state machine.
They are only user-visible progress hints so the process does not feel like a black box.

## Generation Acceptance Rule

Before saying a generated agent is acceptable, Nanobot should check all of these:

1. The agent has a single clear responsibility.
2. The required tools are confirmed, not guessed.
3. The output field and result shape fit the user's expected deliverable.
4. The prompt or role description does not silently widen scope.
5. The agent can run with existing runtime mechanisms without adding unnecessary code.

If these checks do not pass, Nanobot should say the agent can be generated but is not yet the right agent.

## Version Deprioritization Rule

Do not let version concerns dominate the decision unless the user explicitly asks for governance.

In the default path:

1. Existing versions are only evidence of reusable assets.
2. Missing version linkage is not a blocker if a runnable agent can still be generated.
3. Workshop version/publish/evaluate flow is optional follow-up, not default scope.

## Escalation Rule

Nanobot should only recommend the old Agent Workshop or a heavier governance path if at least one of these is true:

1. The user explicitly asks for spec/version/evaluation/publish workflow.
2. The agent needs versioned review and approval.
3. The agent requires benchmark evaluation before release.
4. The request is not a single focused agent but a governed reusable product asset.

## Build Path Heuristics

Choose the simplest path that satisfies the requirement:

1. If the task is mostly explanation over existing structured outputs, prefer prompt/template reuse.
2. If the task depends on deterministic numbers or fixed calculations, prefer existing tools and factor bundles.
3. If a single-role agent can be represented by `agent_configs` plus prompt/templates and tool bindings, prefer the UniversalAgent path over a new Python adapter.
4. If the task is mostly selecting and orchestrating existing capabilities, prefer a thin agent wrapper over new computation code.
5. If the user asks for a brand new capability that does not exist, identify the gap explicitly before generating the agent shell.

## Output Expectations

When proposing or generating an agent, always make these explicit:

1. Which existing resources are reused.
2. Which resources were confirmed versus only suspected.
3. Which gaps still need implementation.
4. Why the chosen agent shape is the lightest viable one.
5. Whether each reused resource is visible in Agent Workshop, visible only at runtime, or defined only as a built-in blueprint.

## Anti-Patterns

Do not do these by default:

1. Do not directly invoke the old Agent Workshop because it exists.
2. Do not assume a capability is available just because its name sounds plausible.
3. Do not ignore `agent_configs`, `agent_specs`, or `agent_versions` when the project already supports configurable agents.
4. Do not create a large multi-role workflow when a single focused agent is enough.
5. Do not generate an agent that depends on unconfirmed tools.
6. Do not hide capability gaps behind vague prompt text.

## Configurable Agent Note

This project already supports a database-driven generic agent base:

1. `agent_configs` can hold the runtime definition for a focused agent.
2. `tool_agent_bindings` may define the effective tool set.
3. `AgentFactory` can fall back to `UniversalAgent` when no built-in Python class exists.
4. `agent_specs` and `agent_versions` may already contain reusable design and prompt assets.

When a user asks Nanobot to create a specialized agent, do not assume that means writing a new adapter.
First determine whether the lightest correct result is:

1. reusing a built-in agent blueprint,
2. refining an existing database-configured agent,
3. publishing a nearby workshop version,
4. or creating a new UniversalAgent-backed config.

## Stock Analysis Note

For stock-analysis agents, prefer existing local runtime and factor tools first.
For example, if the user wants valuation, quality, growth, or technical agents, look for factor bundle tools and A-share runtime helpers before designing anything new.