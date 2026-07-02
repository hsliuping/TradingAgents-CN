# Debug Session: gap-vector-recall

Status: [OPEN]

## Symptom
用户重启后在 Agent 工坊中执行“重新做现有工具的能力分析”，风险评估助手仍判断缺少现金流恶化分析能力，尽管代码中已有现金流质量/现金流分析/财务造假信号等工具，并且已补强工具元数据、移除 gap 服务层关键词纠偏。

## Expected
重新做功能能力评估时，能力索引/向量召回应能召回现金流相关工具，LLM gap 分析不应把“现金流恶化分析”判断为完全缺口。

## Hypotheses
1. Capability index 没有刷新，运行时仍使用旧工具元数据，所以向量库看不到新补强说明。
2. Capability index 刷新了，但 cashflow 相关工具没有被注册进能力索引，或 `auto_register/category` 等元数据导致缺失。
3. 向量检索召回了 cashflow 工具，但 gap prompt 中 `known_tools/key_tool_detail_lines` 未包含它们，可能被 topK/去重/快照构造裁掉。
4. 用户触发的“重新做现有工具能力分析”没有走新的 `rerun_gap/gap_analysis` 路由，而是复用了旧 session/version metadata 里的旧 gap_report 或旧 candidate_plans。
5. LLM prompt 中仍有其它旧约束或旧缓存上下文，使其忽略已召回的现金流工具并生成缺口。

## Evidence Plan
- 检查后端日志中 gap analysis / capability index / search_capabilities / retrieved tools 相关记录。
- 检查当前代码是否已经记录足够的召回证据；如不足，再只加 instrumentation 日志，不改业务逻辑。
- 对比运行时能力索引中的现金流工具文档是否包含新元数据。
- 验证当前意图路由是否真的进入 rerun_gap/gap_analysis。

## Timeline
- Created debug record.
- Read runtime logs under `logs/embedded_nanobot_events`, `logs/tradingagents.log`, `logs/webapi.log`.

## Evidence Collected

### E1. The user action did call `analyze_agent_workshop_gaps`
`logs/embedded_nanobot_events/embedded_agent-studio_1782963182682_20260702.ndjson` shows at 13:58:39:
- step: 缺口分析
- tool_event: 执行：analyze_agent_workshop_gaps
- tool_event: 完成：analyze_agent_workshop_gaps

So the rerun action did enter the gap analysis tool at least once.

### E2. Earlier gap analysis prompt did not contain the actual risk-agent requirement
`logs/tradingagents.log` around lines 7799-7835 shows:
- prompt_metrics: known_tools=6, selected_tool_details=6, capability_requirements=0
- spec summary goal was `候选 Agent`
- legal tools were unrelated:
  - execute_callable_agent
  - get_position_analysis
  - list_callable_agents
  - start_external_skill_generation_session
  - trigger_position_analysis
  - propose_agent_build_plans

The prompt did not contain `商誉减值 / 应收账款异常 / 现金流恶化` as structured capability requirements. This means vector search was executed against a low-information/generic spec, not the actual desired risk assistant.

### E3. Capability index itself did rebuild/sync and tools were registered
`logs/tradingagents.log` shows:
- `get_cashflow_analysis` registered
- `get_growth_cashflow_factor_bundle_tool` registered
- `get_cashflow_quality_trend_tool` registered
- `get_cashflow_quality_deep` registered
- Capability index: `270/270 已索引`, backend qdrant

So “cashflow tools not registered at all” is unlikely.

### E4. At 13:57 and 14:00, plan generation reused the old bad gap report
`embedded_agent-studio_1782963182682_20260702.ndjson` lines 193-194 show `propose_agent_build_plans` received a `gap_report_json` that still contains:
- existing_tools: goodwill/receivables/risk factors/balance sheet only
- suggested_tools: `cash_flow_risk_analyzer`
- blocking_gaps: `缺少现金流恶化分析能力...`

So after rerun, the visible response is partly generated from an old/stale gap_report_json, not necessarily the freshly recalculated capability snapshot.

## Current Diagnosis
Two issues are likely stacked:

1. **Spec quality issue**: the gap analyzer sometimes receives a generic `AgentSpec` (`候选 Agent`, no explicit capability requirements), so vector retrieval cannot hit the right financial-risk tools. This explains why the legal tool list can be unrelated.
2. **State/cache issue**: after the rerun, `propose_agent_build_plans` still uses an older bad `gap_report_json`, so the final user-facing response keeps repeating the old cashflow gap even if a rerun happened.

## Hypothesis Status
1. Index not refreshed: partly rejected. Logs show index sync and qdrant ready.
2. Cashflow tools not registered/indexed: mostly rejected by registration/index logs, but direct retrieval still needs a targeted query check.
3. Retrieved but not passed to prompt: supported for the 13:58 rerun. The latest prompt legal tool list did not include cashflow tools, so the LLM could only mark cashflow as a missing capability.
4. Rerun reused stale gap/plan state: partly supported for 13:57 regenerate-plan; for 13:58 rerun it did run gap_analysis again, then plan_generation used the new but still bad gap_report.
5. Prompt/cache made LLM ignore tools: secondary. The stronger evidence is that the legal tool list lacked cashflow tools.

### E5. 13:58 rerun did not route to `候选 Agent`; it used the risk assistant spec
`logs/tradingagents.log` for trace `87206023-979a-4656-88be-2e1cb9d0aeee` shows:
- `GraphStore][Load] thread=embedded:agent-studio:1782963182682: node=wait_plan_selection, stage=plan_selection_pending`
- `ClassifyIntent ... msg=重新做一下现有工具的能力分析吧 → intent=rerun_gap`
- `Node][Enter] node_gap_analysis ... spec=agent_candidate_1bd94b55`
- `[AgentWorkshop] 开始缺口分析: session_id=51b84202-bf63-47ae-89d3-56076d49c02d spec_id=agent_candidate_1bd94b55 spec_name=风险评估助手`

So the current user-facing rerun is bound to `风险评估助手`, not `候选 Agent`.

### E6. `候选 Agent` is a fallback name from empty graph state, seen in old/other flows
`core/embedded_nanobot/workflows/agent_builder_nodes.py` uses `state.get("spec_name", "") or "候选 Agent"` in forced tool parameters. Earlier logs around 06:35 were for `test-e2e-1733399906` / `agent_candidate_06789a92`, where `spec_name` was empty and fell back to `候选 Agent`. That was not the 13:58 `embedded:agent-studio:1782963182682` rerun.

### E7. The actual 13:58 mismatch is capability retrieval/selection, not Agent identity
At 13:58, the legal tool list in the prompt for `风险评估助手` contained goodwill/receivables/risk event/fraud/balance-sheet tools, but did not contain:
- `get_cashflow_quality_trend_tool`
- `get_cashflow_analysis`
- `get_growth_cashflow_factor_bundle_tool`
- `get_cashflow_quality_deep`

Because the prompt explicitly constrains `existing_tools` to the legal list, the LLM had no allowed cashflow tool to select and therefore generated `cashflow_deterioration_analyzer` as a suggested missing tool.

### E8. Thread context persistence is incomplete for this thread
For `embedded:agent-studio:1782963182682`, repeated logs show:
- `[EmbeddedNanobot][Normalize] input_keys=['preference_id'] output_keys=['preference_id']`
- `[EmbeddedNanobot][MongoWrite] ... thread_context_keys=['preference_id']`

This means Mongo thread metadata is not carrying `spec_id/spec_name/workshop_session_id/version_id`. The graph checkpoint still carries the correct `spec_id`, but frontend thread matching/recovery is fragile because persisted thread context lacks the Agent identity.

## Current Conclusion
The “候选 Agent” line is from a fallback/old flow and should not be used to explain the 13:58 failure. The 13:58 flow did know the current Agent was `风险评估助手`; the failure point is later: capability index retrieval/selected legal tool list did not include cashflow tools, so the gap prompt forced the LLM to treat cashflow as missing. Separately, thread_context persistence is incomplete and should be fixed because it can cause future thread/spec matching problems, but it was not the direct cause of the 13:58 cashflow gap output.

### E9. 14:45 rerun confirms the direct failure point is the legal tool list
`logs/tradingagents.log` trace `557dd028-49fd-43d7-b1f0-5bc75538501c` shows:
- Capability index is ready and fingerprint matched: `312 个工具 / 312 个已索引 / backend=qdrant`.
- Gap snapshot has `builtin_tools=29` and `source=self_collected`, so the vector path did return many candidates.
- Prompt metrics: `known_tools=8`, `selected_tool_details=6`.
- The compact prompt legal tool list contains only goodwill, receivables, risk-event, report-query tools, and `analyze_agent_workshop_gaps`; it does not include cashflow tools.

Code inspection shows why:
- Gap retrieval used the global capability index without source/category scoping, so business tools and operational tools shared the same vector search space.
- `_select_gap_analysis_tool_details()` selected the first recalled details without filtering report/agent-builder operational tools.
- The compact prompt then passed `known_tools[:8]`, which hard-truncated the legal list to 8 tools.

Therefore the LLM was correctly following the prompt constraint but was given an incomplete legal list.

### E10. Operational/report tools were recalled because the retrieval domain was too broad
The capability index writes all auto-registered tools into one collection, including `assistant_ops` report-query and Agent Builder control tools. Gap analysis previously called `search_capabilities(..., bindable_only=False)` without `source_types` or category constraints, while the query/spec contains words like `报告`, `分析报告`, `Agent 工坊`, and `缺口分析`. In a global semantic space those operational tools are plausible matches, even though they are not valid business capabilities for a financial-risk Agent.

Fix direction: do not rely on post-filtering only. Gap analysis should search within a scoped business-capability domain from the start.

### E11. Direct recall probe: vector search is reasonable for specific cashflow queries, weak for generic risk queries
A direct probe compared `RAW_GLOBAL`, `BINDABLE_GLOBAL`, and `BUSINESS_SCOPED` top-20 results for several queries.

Findings:
- `现金流恶化`: raw global top results are cashflow/fundamental tools. Top hits include `get_cashflow_analysis`, `get_cashflow_quality_trend_tool`, `get_financial_cashflow_quality_trend`, `get_growth_cashflow_factor_bundle_tool`, `get_cash_flow_statement`. No report/assistant_ops tools appeared in top-20.
- `经营现金流 自由现金流 利润含金量`: raw global top results are also cashflow/fundamental tools. No report/assistant_ops tools appeared in top-20.
- `财报风险 商誉减值 应收账款异常 现金流恶化`: raw global top results are fundamentals/news tools. Cashflow appears by rank 12 (`get_cashflow_analysis`) and no report/assistant_ops tools appeared in top-20.
- `风险`: raw global includes `assistant_ops` hits such as `get_portfolio_risk_profile_tool`, `create_assistant_subtopic`, `trigger_position_analysis`, `get_analysis_status` because they genuinely contain generic risk/analysis semantics in their retrieval text.
- `财报风险信号`: raw global is mostly fundamentals/news; one assistant_ops tool (`get_portfolio_risk_profile_tool`) appears around rank 17.
- `BUSINESS_SCOPED` removes assistant_ops/report hits for the generic risk queries.

Interpretation:
- The embedding/vector index is not fundamentally broken for specific capability queries; it retrieves cashflow tools correctly.
- The weak point is broad/generic query text (`风险`, `报告`, `分析报告`, `Agent 工坊`, `缺口分析`) combined with a global mixed-purpose tool index. Generic terms make operational tools semantically close enough to enter lower ranks.
- For Agent gap analysis, query construction must emphasize extracted business capability atoms and avoid global constraints/output/report wording; retrieval must also be scoped to business capability categories.

## Fix Applied
1. `app/main.py`: backend startup now calls `CapabilityIndexService.ensure_index()` after custom tools, skills, MCP tools, and config bridge are loaded. This makes restart actively sync the capability vector index instead of waiting for the first gap/search call.
2. `app/services/capability_index_service.py`: index fingerprint now includes `when_not_to_use` and `retrieval_text`. Tool metadata/disambiguation text changes will change the fingerprint/document hash and trigger incremental vector upsert.
3. `app/services/agent_workshop_service.py`: gap capability retrieval now builds multiple semantic queries from the spec goal, responsibilities, outputs, success criteria, preferred methods, and structured capability requirements.
4. `app/services/agent_workshop_service.py`: multi-query retrieval now pins each query's top results before global sorting, so specific dimensions such as “现金流恶化” are less likely to be squeezed out by broader financial-risk results.
5. `app/services/embedded_nanobot_service.py`: graph responses now persist merged thread_context from graph state, preserving `spec_id/spec_name/workshop_session_id/version_id/node_id/intent` instead of writing only the request's `preference_id`.
6. `app/services/agent_workshop_service.py`: legal tool list generation now filters builtin `assistant_ops/utility/knowledge/mcp` operational tools from gap-analysis candidates, so report-query and Agent Builder internal tools no longer occupy business capability slots.
7. `app/services/agent_workshop_service.py`: compact prompt no longer truncates `known_tools` to the first 8 entries. The legal list now uses the selected capability candidates consistently, and logs `[GapAnalysis][LegalTools]` with selected/skipped labels.
8. `app/services/capability_index_service.py`: `search_capabilities()` now supports category scoping. Gap analysis uses this to restrict retrieval to business capability categories (`market/fundamentals/news/social/china/technical/screening/trade_review`) and `bindable_only=True`, so operational report/query/Agent Builder tools are outside the search domain rather than merely filtered after recall.
9. `app/services/agent_workshop_service.py`: gap retrieval query construction now excludes `constraints`, `outputs`, and `preferred_methods` from capability search text. This prevents synthetic output names such as `candidate_..._report`, global policy text, and `workflow_stage:analyst` from becoming standalone vector queries that pin report/operational tools into the merged top results.
10. `app/services/agent_workshop_service.py`: removed the remaining compact-prompt hard cap `known_tools[:8]` and matching metric cap `min(len(known_tools), 8)`. `gap_analysis_request_compact_first` now receives and logs the full selected legal tool list.
11. `app/services/agent_workshop_service.py`: gap capability retrieval now applies an explicit minimum retrieval score (`0.42`) before a candidate can be accepted or pinned. Multi-query merging keeps up to 4 accepted tools per query dimension, but only if they pass the score threshold. The final legal tool list limit is raised to 24 to cover multi-dimensional specs. Logs now include `[CapabilitySnapshot][Multi][Scores]` and `[GapAnalysis][LegalTools]` with scores/ranks.

## Verification
- `python -m py_compile app/services/capability_index_service.py app/services/agent_workshop_service.py app/services/embedded_nanobot_service.py app/main.py` passed.
- `python -m py_compile app/services/agent_workshop_service.py` passed after legal-tool-list fix.
- `python -m py_compile app/services/agent_workshop_service.py app/services/capability_index_service.py` passed after retrieval score threshold changes.
- A direct runtime recall probe could not be rerun while the backend holds local Qdrant storage lock (`./data/qdrant is already accessed by another instance`). This is an environment limitation of local Qdrant, not a Python compile/runtime syntax failure.
- Broad historical tests still have unrelated existing failures and a Qdrant storage lock conflict, so they are not used as the decisive verification for this patch.

## Related Issue: retry test reused old result

### E12. 15:59 retry with `test_symbol=科大讯飞` did not execute a new test
Intent classification was correct:
- `intent=retry`
- `test_symbol=科大讯飞`

But the active node was `wait_evaluation`. Existing route logic sent `retry` to `wait_test_request`, which is a terminal wait node. Because the previous `final_response` and `test_result` still contained the 600519/贵州茅台 result, the UI received the old result again instead of running `real_data_test` for 科大讯飞.

Fix applied:
- `core/embedded_nanobot/workflows/agent_builder_conditions.py`: `wait_evaluation` and `evaluate_or_publish` now route `retry` directly to `real_data_test` when `test_symbol` exists; otherwise they route to `wait_test_request`.
- `core/embedded_nanobot/workflows/agent_builder_nodes.py`: when `user_intent == retry`, clear old `test_result`, `official_acceptance_decision`, `final_response`, and `tool_events` before routing.

- `core/embedded_nanobot/workflows/agent_builder_conditions.py`: `evaluate_or_publish` now matches `wait_evaluation` for retry behavior. `confirmed/select_option` stays on publish/evaluate, while `retry` routes to `real_data_test` if `test_symbol` exists, otherwise `wait_test_request`.
- Route verification for both `wait_evaluation` and `evaluate_or_publish` passed:
  - 发布/上线当前版本 -> `evaluate_or_publish`
  - 重新测试 + 标的 -> `real_data_test`
  - 重新测试无标的 -> `wait_test_request`
  - 升级/修改需求 -> `iterate_agent_version`
  - 重新做缺口分析 -> `gap_analysis`
  - 重新生成解决方案 -> `plan_generation`
  - 新建其他 Agent -> `end`
  - 取消/结束 -> `end`

Verification:
- `python -m py_compile core/embedded_nanobot/workflows/agent_builder_conditions.py core/embedded_nanobot/workflows/agent_builder_nodes.py core/embedded_nanobot/workflows/agent_builder_graph.py` passed.
- Route check: `wait_evaluation + retry + test_symbol=002230 -> real_data_test`; without test_symbol -> `wait_test_request`.
- Stock resolver check: `科大讯飞 -> 002230`, `重测 科大讯飞 -> 002230`.
