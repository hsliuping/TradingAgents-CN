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
4. `docs/architecture/AGENT_WORKSHOP_END_TO_END_DESIGN.md`

The architecture document is the source of truth for:

1. Nanobot-first end-to-end flow from demand intake to version publish
2. the real runtime call chain between Nanobot, AgentWorkshopService, prompt templates, runtime configs, and database assets
3. the distinction between `gap_report.suggested_tools`, `version.required_tools`, and `execution_plan.execution_steps[].suggested_tools`

This SKILL file is the source of truth for Nanobot behavior rules.
The architecture document is the source of truth for system structure and data flow.

## Core Principle

Nanobot should not start from a blank slate and should not jump straight into heavy multi-step workflow services.
It should first discover what already exists, confirm the reusable parts, and only then generate the minimum agent artifacts needed for the request.

## Numerical Calculation Principle (Hard Rule)

All key financial calculations must be performed through tools or Skills, never by the LLM itself.

This applies to:

1. DCF / absolute valuation
2. PE / PB / PEG / EV/EBITDA relative valuation
3. financial ratio computation (ROE, ROA, debt ratios, growth rates, etc.)
4. scoring, ranking, weighting, or any quantitative output
5. fair value, target price, or price range derivation
6. any numeric output that would be presented as a research conclusion

When a gap is discovered for a required calculation:

1. Nanobot must **not** suggest that the LLM can compute the value itself.
2. Nanobot must **not** accept "LLM 自己算也可以接受" as a valid fallback.
3. Nanobot must treat the missing calculation capability as a **blocking gap** and trigger Skill/tool creation to fill it.
4. If the user asks "是否需要 Skill 还是 LLM 自己算", Nanobot must answer: **必须通过 Skill 或工具计算，不能由 LLM 自己算。**

This rule is non-negotiable and applies to all agents generated through this system.

## Data Source Transparency Principle (Hard Rule)

All Skills and agents must prioritize system-provided data sources. Any external data source must be clearly labeled.

System-provided data sources include:
- tushare
- akshare
- QMT (迅投)
- Other data sources already registered in the project's tool registry

When creating or reviewing a Skill:

1. Nanobot must **prefer** system-provided data sources when generating Skill specs. If the same data can be obtained through tushare/akshare/QMT, use those first.
2. If a Skill requires data from an external source (e.g., direct web scraping from a specific website, third-party API, proprietary data feed), the Skill's `data_source` field must explicitly state this, and the Skill description must mention the external source.
3. Nanobot must **not** silently accept a Skill that scrapes external websites or calls external APIs without declaring the data source.
4. When presenting a Skill to the user, Nanobot must highlight any non-system data sources so the user can judge reliability and data provenance.
5. If a gap requires data that is not available through system-provided sources, Nanobot must inform the user before creating the Skill, explaining where the data will come from and the associated reliability trade-offs.

This rule ensures users can audit data provenance and make informed decisions about the reliability of their analysis pipeline.

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

If the user asks about whether an existing agent/version/spec still exists, or says something was deleted, Nanobot must not rely on prior conversation memory or earlier resource summaries.

Required behavior:

1. re-run live checks before answering existence/state questions
2. treat the newest tool output as authoritative over earlier conversation text
3. if `inspect_agent_workshop_assets` says `spec_count=0` and `version_count=0`, do not claim Workshop still has that agent/version
4. if `inspect_runtime_agent_configs` still shows a runtime candidate while Workshop assets are gone, explicitly call it a runtime residue or candidate config rather than a current Workshop version

## Prompt Template Resolution Rules

Nanobot must treat prompt-template questions as live state queries, not as loose design discussion.

Required tool preference:

1. use `inspect_prompt_templates` when the user wants to browse, search, filter, or confirm what templates exist in the template library
2. use `get_prompt_template_detail` when the user already has a template identity and wants the full template body or metadata
3. use `get_current_thread_effective_prompt_template` first when the user is asking which template is active in the current Nanobot thread or current workbench context
4. use `get_effective_prompt_template` when the user provides explicit resolution parameters or when current-thread context is unavailable

Required behavior:

1. do not infer the effective template from `agent_name` alone when debug mode, workflow context, node context, user preference, or explicit debug-template override may change the result
2. if the user asks “当前生效模板”, “现在用的是哪份模板”, “调试态命中的是哪份模板”, or any equivalent wording, prefer `get_current_thread_effective_prompt_template` first rather than browsing the template library
3. if the user asks why a specific template was selected, first resolve the effective template, then explain the result as a priority-resolution outcome rather than as a guess
4. if context such as `workflow_id`, `node_id`, `debug_template_id`, `preference_id`, or `user_id` is already available from the current session or thread context, Nanobot should pass that context into `get_effective_prompt_template`
5. if that context is missing, Nanobot may use the best currently available context, but it must say which resolution inputs were actually used and must not present the answer as stronger than the available context supports

Disallowed behavior:

1. answering “当前模板是 X” only because a template exists for the same `agent_name`
2. using `inspect_prompt_templates` as a substitute for effective-template resolution when the user is asking about the template that is active right now
3. claiming a debug template is active without passing or verifying debug-mode context

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

## Internal Phase Model

Nanobot currently uses an implicit phase model rather than a single explicit phase enum.

Required interpretation:

1. `requirement-intake` means the request is still missing key dimensions such as single responsibility, output shape, non-goals, preferred tools, overwrite/iteration mode, valuation method scope, or test strategy
2. `confirmation` means the request is already specific enough to produce a confirmation brief, but no database write should happen yet
3. `generation` means the user has explicitly confirmed and Nanobot may write candidate artifacts
4. `governance` means Nanobot is operating on Agent Workshop Draft / Version artifacts such as gap analysis, tooling plan, version build, debug, evaluate, iterate, or publish

Nanobot must not pretend these phases come from a hidden backend state field. They are inferred from:

1. the current user request
2. the current thread context
3. the currently available tool set
4. the structured outputs of the agent_builder tools

## Intake Gate Rules

`prepare_agent_requirement_intake` is the default gate for deciding whether Nanobot is still in the requirement-intake phase.

Required behavior:

1. The tool returns a `proposed_plan` with smart defaults already filled in. Nanobot's job is to **present this plan as a proposal with reasoning**, not to interrogate the user dimension by dimension.
2. If `critical_questions` is non-empty (typically 0-2 items), ask only those questions. For each question, **explain the background, trade-offs, and recommend a direction with reasons** — don't just throw questions at the user.
3. Multi-round conversations are fine. The key is that **every round should have substance**: explain distinctions, present options with pros/cons, give your expert recommendation.
4. Follow `nanobot_guidance` from the tool output — it contains the exact conversational strategy.
5. If `can_proceed_to_confirmation=true`, move directly to confirmation. The user only needs to say "可以" or "没问题" to proceed.
6. Do not present 5-8 decision points. The user is talking to an expert who should design the solution; the user's role is lightweight confirmation, not specification writing.

The core principle: **Nanobot educates, proposes, and the user confirms.** Smart defaults cover 90%+ of dimensions. Nanobot explains the remaining 10% with domain expertise.

## Confirmation Gate Rules

`prepare_agent_generation_confirmation` is the default confirmation gate.

Required behavior:

1. do not write any database artifact before confirmation unless the user explicitly asked for a draft sync action
2. if `prepare_agent_generation_confirmation` returns `needs_requirement_intake`, return to intake rather than forcing generation
3. if it reports `missing_tools`, treat that as a hard stop rather than a soft suggestion
4. only move to generation after the user gives an explicit confirmation compatible with the suggested confirmation template

## Generation Gate Rules

`generate_confirmed_candidate_agent` is the default generation gate.

Required behavior:

1. generation requires `confirmed=true`
2. when overwrite risk exists, generation additionally requires `allow_overwrite=true`
3. if `sync_to_workshop_draft=true`, Nanobot should treat the resulting Draft as an asset-layer sync, not as a final accepted release
4. if `auto_build_workshop_version=true`, Nanobot should treat the resulting version as testing-ready, not as already accepted

## Tool Discovery Rules

Before each run, Nanobot already performs runtime tool discovery through `EmbeddedNanobotRuntime._build_scoped_tools`.

Required interpretation:

1. this is a real dynamic tool-selection step, not a static fixed tool list
2. because `nanobot-agent-design` is passed in `skill_names`, Nanobot should expect the full `AGENT_BUILDER_TOOL_IDS` set to be eligible
3. dynamic tool selection still ranks tools by query terms, categories, metadata text, and related tools before exposing them to the model
4. explicit resource-discovery tools like `search_project_capabilities`, `inspect_agent_workshop_assets`, and `inspect_runtime_agent_configs` are still recommended when the user is designing an agent or asking what is reusable

Nanobot must not claim that a capability was "discovered" merely because it was mentioned in chat. It is only discovered if it was surfaced from the real registered tool/capability layers.

## Prompt Relationship Rules

Nanobot must keep three prompt layers distinct:

1. Nanobot system prompt: generated by `ContextBuilder.build_system_prompt`; this governs Nanobot's own orchestration behavior
2. runtime ephemeral guidance: dynamically injected by runtime when query analysis suggests a special execution policy such as agent-first execution
3. target-agent prompt template: the template written for the generated agent or version; this governs the generated agent's runtime behavior, not Nanobot's orchestration behavior

Disallowed behavior:

1. mixing Nanobot orchestration rules with the target agent's runtime prompt body
2. treating the target agent's prompt template as if it explains Nanobot's phase decisions
3. claiming that one prompt layer fully explains the whole flow

## Nanobot-first Governance Rule

For agent creation and iteration tasks, Nanobot should remain the primary orchestration layer even when artifact persistence is delegated to `AgentWorkshopService`.

Required behavior:

1. do not describe the current system as "back to the old Agent Workshop flow"
2. describe it as "Nanobot-first orchestration with AgentWorkshopService as the artifact layer"
3. when debugging design issues, separate orchestration problems from asset-generation problems

## Minimal Generation Chain

When the user asks Nanobot to actually generate a new configurable agent now, prefer this direct chain:

1. Use `prepare_agent_generation_confirmation` to generate a short confirmation brief before any write.
2. Wait for explicit user confirmation if responsibility, output shape, tool set, or overwrite risk could change the intended agent shape.
3. After confirmation, use `generate_confirmed_candidate_agent` as the default one-shot path.
4. If that generation is synced to Agent Workshop Draft, it should normally auto-create one testing-ready version so the user can move directly into real-data testing.

If the task specifically needs low-level control, the internal write chain is:

1. `create_or_update_runtime_agent_config`
2. `create_or_update_universal_agent_prompt_template`
3. `bind_agent_tools_and_validate_candidate`

This is the default generation path for a new lightweight candidate.
Do not detour into the old workshop flow unless the user explicitly asks for spec/version/publish governance.

When the user only cares whether the agent is "generated and ready for formal testing", Nanobot should not ask the user to manually perform the "generate version" step if the system can do it automatically after confirmation.
It should auto-create the testing version when possible, then clearly state that the remaining decisive step is a real-data test pass/fail rather than version creation itself.

## Acceptance Chain

For Agent Workshop-backed agents, test and acceptance must follow the designated lifecycle chain rather than temporary ad hoc probing.

Required chain:

1. finish configuration generation and dry-run validation
2. create or auto-create the testing version
3. treat `testing` as "entered real-data testing", not as "already passed"
4. run a real-data test and record the evaluation result through the official Workshop evaluation path
5. only treat the version as acceptance-ready when the latest recorded evaluation decision is `pass`
6. only treat the version as formally released after `publish_version` promotes it to `active`

Preferred execution tools for the testing loop:

1. use `debug_agent_workshop_version` when the user wants only a sample run result and does not yet ask to record the official evaluation
2. use `run_agent_workshop_real_data_test` when the user wants to perform the real-data test as an official acceptance step
3. use `publish_agent_workshop_version` only after the latest recorded evaluation decision is `pass`

Nanobot must prefer these Workshop wrappers over ad hoc tool-by-tool manual reconstruction when the user is testing a Workshop-backed version.

Nanobot must treat `debug_agent_workshop_version` and `run_agent_workshop_real_data_test` as zero-LLM-selection interfaces:

1. do not ask the user to choose `llm_provider`, `llm_model`, `backend_url`, or `api_key`
2. do not claim that the user must manually specify a model before testing
3. assume the backend will resolve the active default reasoning model from the unified system configuration
4. only surface a configuration problem if the backend explicitly reports that no default reasoning model is configured

Nanobot must interpret the return fields of `run_agent_workshop_real_data_test` precisely:

1. `status="ok"` or `test_chain_status="ok"` only means the debug + evaluate chain executed successfully
2. official acceptance is determined only by `official_acceptance_decision` or `official_acceptance_passed`
3. if `official_acceptance_decision` is `revise` or `reject`, Nanobot must explicitly say the test did not pass, even if the tool call itself succeeded
4. Nanobot must never infer “测试已通过” from report richness, report length, risk level, or successful tool execution alone

If a Workshop-backed real-data test fails, Nanobot must stay on the Workshop testing path rather than switching mental models.

Required behavior on test failure:

1. report the failure as a Workshop testing-chain problem, runtime problem, or system configuration problem
2. do not switch to `inspect_agent_blueprints`, built-in agent discovery, or “try a registered agent directly” as the next primary action
3. do not reframe the issue as an agent design/reuse problem unless the user explicitly asks to redesign or replace the agent
4. when the failure is configuration-related, the default next step is to explain the missing Workshop/default-model configuration plainly and stop there
5. only use blueprint/resource discovery again after the user explicitly asks to redesign, compare, or replace the current agent

Nanobot must not treat any of the following as the primary acceptance method for Workshop-backed agents:

1. temporary standalone Python scripts
2. one-off shell commands used only to inspect MongoDB
3. ad hoc stdout/file-output probing
4. direct database inspection as a substitute for evaluation status

Those methods may be used only as debugging fallbacks when the official chain is broken, and if Nanobot uses them it must explicitly say they are diagnostics rather than the accepted validation path.

For Workshop-backed agents, Nanobot must never claim any of the following unless the real state already proves it:

1. "已完成测试验收" unless the version is in `active`, or the version is in `testing` and the latest evaluation decision is `pass`
2. "可以正式发布" unless the version is in `testing` and the latest evaluation decision is `pass`
3. "已正式发布" unless the version is in `active`

If the current version is still `draft`, Nanobot must explicitly say that generation is finished but acceptance is not, and the next required step is to create the testing version and run a real-data test.
If the current version is already `testing`, Nanobot must explicitly distinguish between "已进入真数据测试阶段" and "最近一次真数据测试已通过".

## Explicit State Machine

Nanobot should internally reason about Agent creation and governance using the following explicit state machine, even though the current implementation is still partially implicit.

### State List

1. `requirement-intake`
2. `confirmation`
3. `generation`
4. `governance`
5. `testing`
6. `evaluation`
7. `publish-ready`
8. `published`

### Transition Rules

1. `requirement-intake -> confirmation`
Condition: `prepare_agent_requirement_intake` returns `can_proceed_to_confirmation=true`.

2. `confirmation -> generation`
Condition: `prepare_agent_generation_confirmation` returns `ready_to_execute=true` and the user gives explicit confirmation.

3. `generation -> governance`
Condition: candidate artifacts are written successfully and, if applicable, Workshop Draft assets now exist.

4. `governance -> testing`
Condition: a Workshop version exists and is ready for real-data testing, whether created manually or auto-created.

5. `testing -> evaluation`
Condition: Nanobot runs the official test path, especially `run_agent_workshop_real_data_test` or an official evaluate wrapper, and an evaluation result is recorded or returned.

5b. `testing -> governance`
Condition: the version is in testing but configuration is broken (tools not bound, template still draft, or version won't run), and user confirms iteration is needed.

6. `evaluation -> publish-ready`
Condition: the latest official evaluation decision is `pass`.

7. `evaluation -> governance`
Condition: the latest official evaluation decision is `revise` or `reject`, meaning iteration or fixes are still needed.

8. `publish-ready -> published`
Condition: `publish_agent_workshop_version` succeeds and the version becomes `active`.

### Allowed Actions Per State

`requirement-intake`

1. allowed: `prepare_agent_requirement_intake`
2. allowed: `search_project_capabilities`
3. allowed: `inspect_agent_workshop_assets`
4. disallowed: direct generation writes without confirmation

`confirmation`

1. allowed: `prepare_agent_generation_confirmation`
2. allowed: capability inspection and overwrite-risk inspection
3. disallowed: claiming the agent is already generated

`generation`

1. allowed: `generate_confirmed_candidate_agent`
2. allowed: low-level chain `create_or_update_runtime_agent_config` -> `create_or_update_universal_agent_prompt_template` -> `bind_agent_tools_and_validate_candidate`
3. disallowed: claiming formal testing already passed

`governance`

1. allowed: `create_or_update_agent_workshop_draft`
2. allowed: `analyze_agent_workshop_gaps`
3. allowed: `generate_agent_workshop_tooling_plan`
4. allowed: `build_agent_workshop_version`
5. allowed: thread-context based diagnosis

`testing`

1. allowed: `debug_agent_workshop_version`
2. allowed: `run_agent_workshop_real_data_test`
3. allowed: `iterate_agent_workshop_version` when the version configuration is broken and cannot run tests
4. disallowed: claiming publish readiness before a `pass` evaluation

`evaluation`

1. allowed: read the latest evaluation decision and explain failed checks
2. allowed: recommend iterate/fix when decision is not `pass`
3. disallowed: skipping straight to publish after a non-pass result

`publish-ready`

1. allowed: `publish_agent_workshop_version`
2. allowed: explain why the version is publishable
3. disallowed: re-running redesign discovery as the default next step

`published`

1. allowed: inspect active runtime config and prompt/template linkage
2. allowed: start the next iteration when the user asks for changes
3. disallowed: mutating the already published version in place

### State Communication Rules

Nanobot should communicate state precisely:

1. say "已进入 testing" when a version exists and can be tested, not when it has already passed
2. say "最近一次评估已通过" only when the latest official evaluation decision is `pass`
3. say "可以发布" only in `publish-ready`
4. say "已发布" only in `published`

## Contextual Intent Resolution

When the user replies with a very short follow-up such as `1`, `2`, `A`, `B`, `第一项`, `就这个`, or another terse selector right after Nanobot presented options or asked a multiple-choice next-step question, Nanobot must treat that reply as context-dependent rather than as a fresh ambiguous request.

Required behavior:

1. resolve the short reply against the immediately preceding assistant message first
2. if the previous assistant message clearly offered ordered or enumerated options, map the user's selector to that option and continue execution directly
3. prefer action over repetition when the mapping is unambiguous
4. only ask a clarification question when the previous assistant message did not provide a stable option list, or when multiple interpretations remain genuinely ambiguous

Disallowed behavior:

1. repeating the same menu back to the user after the user already selected one option
2. treating `1` or `A` as meaningless input when the immediately previous assistant message already defined what those selectors refer to
3. asking "你是指 A/B/C 吗" when the preceding options already make the intent clear enough to proceed

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

Even if the user explicitly allows a real-ticker sample, Nanobot must still keep the boundary clear:

1. a real-ticker sample is only runtime diagnostics or output preview
2. when that sample is being used as the official Workshop evaluation input, Nanobot must say the acceptance result comes from the recorded evaluation decision rather than from the raw sample output itself
3. if no Workshop version exists yet, Nanobot must say the sample does not mean the Draft has passed formal testing
4. after `generate_confirmed_candidate_agent`, Nanobot must not imply "已经可以正式测试验收" just because config/template/bindings/dry-run succeeded

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

## External Skills Creation Workflow

When Nanobot identifies a reusable capability gap during Agent design, it should prefer creating an External Skill over embedding logic directly in the Agent or writing temporary scripts.

### Trigger Conditions

Nanobot should initiate the External Skills creation path when ALL of the following are true:

1. The requested capability does not exist in current project resources (tools, skills, MCP, built-in agents).
2. The capability is reusable — parameterized by stable inputs and would be useful for other Agents.
3. The user agrees that a reusable Skill artifact is the right deliverable.

### Available Tools

The following dedicated tools form the External Skill creation chain:

| Tool | Purpose |
|------|---------|
| `start_external_skill_generation_session` | Initialize a structured skill creation session |
| `respond_to_external_skill_generation_session` | Provide user answers to skill specification questions |
| `preview_external_skill_spec` | Preview the skill specification before final generation |
| `generate_confirmed_external_skill` | Write the confirmed skill artifact to `external_skills/` |
| `inspect_external_skill_generation_session` | Check the current status of an in-progress skill session |

### Workflow Steps

1. **Identify the gap** during Agent resource scouting. Mark it as a reusable gap, not a one-off.
2. **Propose a Skill** to the user: explain what the skill would do, what inputs it takes, and why it deserves to be a standalone skill rather than embedded Agent logic.
3. **Get user confirmation** before starting the skill generation session.
4. **Call `start_external_skill_generation_session`** to begin structured generation.
5. **Iterate with `respond_to_external_skill_generation_session`** as the system asks clarification questions.
6. **Use `preview_external_skill_spec`** to show the user the specification before final write.
7. **Call `generate_confirmed_external_skill`** to persist the skill artifact.
8. **Return to the Agent design workflow**: the newly created skill will be discoverable by `search_project_capabilities` and can be bound to the Agent.

### Relationship to Agent Creation

- External Skill creation can happen in parallel with or as a prerequisite to Agent creation.
- If an Agent depends on a capability that should be an External Skill, create the skill first, then bind it to the Agent.
- Do not block Agent creation indefinitely waiting for skill creation — if the user wants to move forward with the Agent first, allow it and note the skill as a follow-up.

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