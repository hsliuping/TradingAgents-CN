import json

import pytest
from types import SimpleNamespace

from app.models.prompt_template import TemplateContent
from app.models.agent_workshop import (
    AgentEvaluationCandidateFinding,
    AgentEvaluationEvidenceBundle,
    AgentEvaluationEvidenceTask,
    AgentEvaluationFinding,
    AgentEvaluationReport,
    AgentEvaluationRuntimeSummary,
    AgentEvaluationWorkerResult,
    AgentWorkshopGapAnalysis,
    AgentSpec,
    AgentSpecStatus,
    AgentVersion,
    AgentVersionStatus,
    AgentWorkshopSession,
    AgentWorkshopStage,
)
from app.services.agent_workshop_service import (
    AgentWorkshopService,
    EVALUATION_COLLECTION,
    SESSION_COLLECTION,
    SPEC_COLLECTION,
    VERSION_COLLECTION,
)
from core.memory.models import MemoryScope


class _FakeCursor:
    def __init__(self, items):
        self._items = list(items)
        self._index = 0

    def sort(self, key, direction=None):
        if isinstance(key, list):
            for sort_key, sort_direction in reversed(key):
                self._items.sort(key=lambda item: item.get(sort_key), reverse=sort_direction == -1)
            return self

        reverse = direction == -1
        self._items.sort(key=lambda item: item.get(key), reverse=reverse)
        return self

    def skip(self, _count):
        return self

    def limit(self, count):
        self._items = self._items[:count]
        return self

    async def to_list(self, length=None):
        if length is None:
            return list(self._items)
        return list(self._items[:length])

    def __aiter__(self):
        self._index = 0
        return self

    async def __anext__(self):
        if self._index >= len(self._items):
            raise StopAsyncIteration
        item = self._items[self._index]
        self._index += 1
        return dict(item)


class _FakeUpdateResult:
    def __init__(self, modified_count=0):
        self.modified_count = modified_count


class _FakeCollection:
    def __init__(self, items):
        self._items = list(items)
        self._next_id = len(self._items) + 1

    def _match(self, item, query):
        query = query or {}
        for key, expected in query.items():
            value = item.get(key)
            if isinstance(expected, dict):
                if "$in" in expected and value not in expected["$in"]:
                    return False
                continue
            if value != expected:
                return False
        return True

    def find(self, query=None, projection=None):
        del projection
        return _FakeCursor([item for item in self._items if self._match(item, query)])

    async def count_documents(self, query=None):
        return len([item for item in self._items if self._match(item, query)])

    async def find_one(self, query=None, projection=None, sort=None):
        del projection
        items = [item for item in self._items if self._match(item, query)]
        if sort:
          for key, direction in reversed(sort):
              items.sort(key=lambda item: item.get(key), reverse=direction == -1)
        return dict(items[0]) if items else None

    async def update_one(self, query, update, upsert=False):
        target = None
        for item in self._items:
            if self._match(item, query):
                target = item
                break
        if target is None and upsert:
            target = dict(query)
            target.setdefault("_id", f"fake_{self._next_id}")
            self._next_id += 1
            self._items.append(target)
        if target is None:
            return _FakeUpdateResult(0)
        self._apply_update(target, update, is_insert=upsert)
        return _FakeUpdateResult(1)

    async def update_many(self, query, update):
        modified = 0
        for item in self._items:
            if self._match(item, query):
                self._apply_update(item, update, is_insert=False)
                modified += 1
        return _FakeUpdateResult(modified)

    def _apply_update(self, target, update, is_insert=False):
        if "$set" in update:
            for key, value in update["$set"].items():
                self._set_nested(target, key, value)
        if is_insert and "$setOnInsert" in update:
            for key, value in update["$setOnInsert"].items():
                if key not in target:
                    self._set_nested(target, key, value)
        if "$inc" in update:
            for key, value in update["$inc"].items():
                target[key] = int(target.get(key) or 0) + value

    def _set_nested(self, target, key, value):
        current = target
        parts = key.split(".")
        for part in parts[:-1]:
            current = current.setdefault(part, {})
        current[parts[-1]] = value


class _FakeDb:
    def __init__(self, collections):
        self._collections = collections

    def __getitem__(self, name):
        return self._collections[name]

    def __getattr__(self, name):
        try:
            return self._collections[name]
        except KeyError as exc:
            raise AttributeError(name) from exc


def _build_spec() -> AgentSpec:
    return AgentSpec(
        spec_id="spec_valuation_candidate_v1",
        name="A股估值分析师",
        domain="stock_analysis",
        primary_goal="输出A股估值结论",
        outputs=["valuation_report"],
        status=AgentSpecStatus.DRAFT,
        latest_session_id="session_valuation_001",
    )


def _build_session() -> AgentWorkshopSession:
    return AgentWorkshopSession(
        session_id="session_valuation_001",
        spec_id="spec_valuation_candidate_v1",
        user_id="user_001",
        stage=AgentWorkshopStage.BUILDING,
        current_round=1,
        current_spec_snapshot=_build_spec(),
    )


def _build_version(status: AgentVersionStatus, version_id: str, version: int) -> AgentVersion:
    return AgentVersion(
        version_id=version_id,
        spec_id="spec_valuation_candidate_v1",
        version=version,
        status=status,
        agent_metadata={
            "id": version_id,
            "name": f"A股估值分析师 v{version}",
            "description": "输出A股估值结论",
            "version": f"0.{version}.0",
            "output_field": "valuation_report",
        },
        prompt_template_ref={"template_id": f"tpl_{version_id}"},
        required_tools=["get_value_factor_bundle_tool", "get_peer_comparison"],
        required_capabilities=["valuation"],
        output_schema={"properties": {"valuation_report": {"type": "string"}}},
        evaluation_policy={"minimum_score": 0.75},
        published_from_session_id="session_valuation_001",
    )


def test_build_valuation_traceability_tolerates_none_tool_trace():
    service = AgentWorkshopService.__new__(AgentWorkshopService)
    spec = _build_spec()

    result = service._build_valuation_traceability(
        spec,
        {
            "debug_prompt": {"tool_trace": None},
            "output_payload": {},
        },
        "综合判断当前合理估值区间约为 18-22 倍 PE。",
    )

    assert result["enabled"] is True
    assert isinstance(result["items"], list)
    assert result["used_tools"] == []


def test_analyze_forbidden_keywords_ignores_negated_disclaimer_statement() -> None:
    service = AgentWorkshopService.__new__(AgentWorkshopService)

    result = service._analyze_forbidden_keywords(
        ["交易建议"],
        "声明：本报告仅提供研究结论、事实核验、风险识别和情景分析，不构成任何交易建议或操作性指令。",
        True,
    )

    assert result["matched"] == []
    assert result["missing"] == ["交易建议"]
    assert result["score"] == 0.0
    assert any("否定性声明或免责声明" in note for note in result["notes"])


def test_normalize_nanobot_output_field_rewrites_generic_analysis_report() -> None:
    service = AgentWorkshopService.__new__(AgentWorkshopService)

    assert service._normalize_nanobot_output_field("valuation_candidate_v1", "analysis_report") == "valuation_candidate_report"
    assert service._normalize_nanobot_output_field("risk_reviewer_v3", "") == "risk_reviewer_report"
    assert service._normalize_nanobot_output_field("valuation_candidate_v1", "valuation_report") == "valuation_report"


def test_normalize_generated_output_field_rewrites_generic_name_for_general_workshop() -> None:
    service = AgentWorkshopService.__new__(AgentWorkshopService)

    assert service._normalize_generated_output_field("a_share_valuation_workshop", "analysis_report") == "a_share_valuation_workshop_report"
    assert service._normalize_generated_output_field("spec_equity_risk_review", "summary") == "equity_risk_review_summary"
    assert service._normalize_generated_output_field("spec_equity_risk_review", "risk_report") == "risk_report"


def test_merge_llm_spec_data_rewrites_generic_outputs_for_general_workshop() -> None:
    service = AgentWorkshopService.__new__(AgentWorkshopService)
    fallback_spec = AgentSpec(
        spec_id="agent-workshop-temp",
        name="旧草案",
        domain="general",
        primary_goal="旧目标",
        outputs=["analysis_report"],
        status=AgentSpecStatus.DRAFT,
    )

    spec = service._merge_llm_spec_data(
        {
            "name": "A_share_valuation_assistant",
            "domain": "stock_analysis",
            "target_users": ["投研团队"],
            "primary_goal": "输出A股估值复核结果",
            "responsibilities": ["核对估值过程与结论"],
            "non_goals": ["不输出交易建议"],
            "inputs": ["symbol"],
            "outputs": ["analysis_report", "analysis_report"],
            "success_criteria": ["输出结构化复核结果"],
            "constraints": ["不得编造数据"],
            "preferred_methods": ["PE"],
            "capability_requirements": [],
            "sample_symbols": ["600519.SH"],
        },
        fallback_spec,
    )

    output_names = [item.name if hasattr(item, "name") else item for item in spec.outputs]
    assert output_names == ["a_share_valuation_assistant_report", "a_share_valuation_assistant_report_2"]


@pytest.mark.asyncio
async def test_create_nanobot_draft_rewrites_generic_output_field_for_spec() -> None:
    fake_db = _FakeDb({
        SPEC_COLLECTION: _FakeCollection([]),
        SESSION_COLLECTION: _FakeCollection([]),
        VERSION_COLLECTION: _FakeCollection([]),
    })
    service = AgentWorkshopService(fake_db)

    result = await service.create_nanobot_draft(
        agent_id="valuation_candidate_v1",
        agent_name="估值候选Agent",
        target_responsibility="输出A股估值结论",
        output_field="analysis_report",
        owner_user_id="user_001",
    )

    assert result["output_field"] == "valuation_candidate_report"
    stored_spec = fake_db[SPEC_COLLECTION]._items[0]
    assert stored_spec["outputs"] == ["valuation_candidate_report"]


@pytest.mark.asyncio
async def test_create_nanobot_draft_updates_existing_generic_output_field() -> None:
    existing_spec = AgentSpec(
        spec_id="spec_nanobot_risk_reviewer_v3",
        name="风险复核Agent",
        domain="risk_management",
        primary_goal="复核风险结论",
        outputs=["analysis_report"],
        status=AgentSpecStatus.DRAFT,
        latest_session_id="session_old",
    )
    fake_db = _FakeDb({
        SPEC_COLLECTION: _FakeCollection([existing_spec.model_dump(mode="json", by_alias=True)]),
        SESSION_COLLECTION: _FakeCollection([]),
        VERSION_COLLECTION: _FakeCollection([]),
    })
    service = AgentWorkshopService(fake_db)

    await service.create_nanobot_draft(
        agent_id="risk_reviewer_v3",
        agent_name="风险复核Agent",
        target_responsibility="复核风险结论",
        output_field="analysis_report",
        owner_user_id="user_001",
    )

    stored_spec = fake_db[SPEC_COLLECTION]._items[0]
    assert stored_spec["outputs"] == ["risk_reviewer_report"]


@pytest.mark.asyncio
async def test_create_nanobot_draft_reuses_existing_spec_for_version_id() -> None:
    existing_spec = AgentSpec(
        spec_id="spec_nanobot_industry_comparison_researcher_v1",
        name="行业比较研究员 v1",
        domain="stock_analysis",
        primary_goal="输出行业比较分析",
        outputs=["industry_comparison_report"],
        status=AgentSpecStatus.ACTIVE,
        latest_session_id="session_existing",
        current_version_id="spec_nanobot_industry_comparison_researcher_v1_v1",
    )
    fake_db = _FakeDb({
        SPEC_COLLECTION: _FakeCollection([existing_spec.model_dump(mode="json", by_alias=True)]),
        SESSION_COLLECTION: _FakeCollection([]),
        VERSION_COLLECTION: _FakeCollection([
            {
                "version_id": "spec_nanobot_industry_comparison_researcher_v1_v1",
                "spec_id": "spec_nanobot_industry_comparison_researcher_v1",
            }
        ]),
    })
    service = AgentWorkshopService(fake_db)

    result = await service.create_nanobot_draft(
        agent_id="spec_nanobot_industry_comparison_researcher_v1_v1",
        agent_name="行业比较研究员 v1",
        target_responsibility="输出行业比较分析",
        output_field="analysis_report",
        owner_user_id="user_001",
    )

    assert result["spec_id"] == "spec_nanobot_industry_comparison_researcher_v1"
    assert len(fake_db[SPEC_COLLECTION]._items) == 1
    assert fake_db[SPEC_COLLECTION]._items[0]["spec_id"] == "spec_nanobot_industry_comparison_researcher_v1"


@pytest.mark.asyncio
async def test_create_nanobot_draft_does_not_double_prefix_existing_spec_id() -> None:
    existing_spec = AgentSpec(
        spec_id="spec_nanobot_industry_comparison_researcher_v1",
        name="行业比较研究员 v1",
        domain="stock_analysis",
        primary_goal="输出行业比较分析",
        outputs=["industry_comparison_report"],
        status=AgentSpecStatus.ACTIVE,
        latest_session_id="session_existing",
        current_version_id="spec_nanobot_industry_comparison_researcher_v1_v1",
    )
    fake_db = _FakeDb({
        SPEC_COLLECTION: _FakeCollection([existing_spec.model_dump(mode="json", by_alias=True)]),
        SESSION_COLLECTION: _FakeCollection([]),
        VERSION_COLLECTION: _FakeCollection([]),
    })
    service = AgentWorkshopService(fake_db)

    result = await service.create_nanobot_draft(
        agent_id="spec_nanobot_industry_comparison_researcher_v1",
        agent_name="行业比较研究员 v1",
        target_responsibility="输出行业比较分析",
        output_field="analysis_report",
        owner_user_id="user_001",
    )

    assert result["spec_id"] == "spec_nanobot_industry_comparison_researcher_v1"
    assert len(fake_db[SPEC_COLLECTION]._items) == 1
    assert fake_db[SPEC_COLLECTION]._items[0]["spec_id"] == "spec_nanobot_industry_comparison_researcher_v1"


def test_analyze_forbidden_keywords_keeps_real_trading_advice_match() -> None:
    service = AgentWorkshopService.__new__(AgentWorkshopService)

    result = service._analyze_forbidden_keywords(
        ["交易建议"],
        "综合结论：建议明日开盘积极买入，并作为短线交易建议执行。",
        True,
    )

    assert result["matched"] == ["交易建议"]
    assert result["missing"] == []
    assert result["score"] == 1.0


def test_build_valuation_traceability_accepts_section_level_source_mapping_for_financial_report() -> None:
    service = AgentWorkshopService.__new__(AgentWorkshopService)
    spec = _build_spec()
    spec.primary_goal = "对A股个股进行财报多期跟踪分析，输出结构化风险提示报告并保留数据来源映射。"
    spec.constraints = [
        "所有数值必须来自工具返回，并保留来源工具与报告期映射。",
    ]

    output_text = """
## 一、核心风险指标总览
Altman Z-Score | 31.31 | 财务健康度极高
Piotroski F-Score | 6分 | 财务状况稳健

## 八、数据来源与可追溯性声明
| 分析模块 | 数据来源工具 | 关键数据点 | 报告期 |
|---------|-------------|-----------|--------|
| 质量因子 | get_quality_factor_bundle_tool | ROE、Z-Score、F-Score等 | 2025Q3 |
"""

    result = service._build_valuation_traceability(
        spec,
        {
            "debug_prompt": {
                "tool_trace": [{"tool_name": "get_quality_factor_bundle_tool", "success": True}],
            },
            "output_payload": {},
        },
        output_text,
    )

    assert result["enabled"] is True
    assert result["items"]
    assert all(item["source_type"] == "tool_or_data_backed" for item in result["items"])


def test_build_valuation_traceability_accepts_sector_drawdown_range_from_tool_context() -> None:
    service = AgentWorkshopService.__new__(AgentWorkshopService)
    spec = _build_spec()
    spec.primary_goal = "横向比较行业格局、盈利质量、估值水平和景气位置，输出结构化对比结论。"
    spec.constraints = [
        "所有数值必须来自工具返回，并保留来源工具与来源映射。",
    ]

    output_text = """
# 行业比较分析报告

**分析日期**：2026-04-07

## 四、景气位置分析
### 4.1 板块近期表现
板块代码  20日涨跌幅  今日涨跌幅
700005.TI  -5.80%  -1.28%
700031.TI  -7.73%  -1.56%
来源：get_sector_data

### 4.2 景气度判断
| 维度 | 状态 | 依据 |
|------|------|------|
| 景气位置 | 周期下行 | 板块近20日下跌5-8%，市场情绪偏弱 |
"""

    result = service._build_valuation_traceability(
        spec,
        {
            "debug_prompt": {
                "tool_trace": [{"tool_name": "get_sector_data", "success": True}],
            },
            "output_payload": {},
        },
        output_text,
    )

    assert result["enabled"] is True
    assert result["items"]
    assert any("5-8%" in str(item["value"]) for item in result["items"])
    matched_item = next(item for item in result["items"] if "5-8%" in str(item["value"]))
    assert matched_item["risk_level"] == "normal"
    assert matched_item["source_type"] == "tool_or_data_backed"


def test_build_valuation_traceability_accepts_report_derived_ranking_from_peer_table() -> None:
    service = AgentWorkshopService.__new__(AgentWorkshopService)
    spec = _build_spec()
    spec.primary_goal = "横向比较行业格局、盈利质量、估值水平和景气位置，输出结构化对比结论。"
    spec.constraints = [
        "所有数值必须来自工具返回，或基于原始数据的可追溯计算。",
    ]

    output_text = """
# 行业比较分析报告

**分析日期**：2026-04-07

## 一、行业格局分析
### 1.1 市值对比
| 公司 | 市值(亿) | 来源 |
|------|----------|------|
| 宁德时代 | 17638 | get_peer_comparison |
| 第二名公司 | 2556 | get_peer_comparison |

来源：get_peer_comparison

### 1.2 综合判断
行业格局优势显著：市值17,638亿排名第1，是第2名的6.9倍，龙头地位稳固。
"""

    result = service._build_valuation_traceability(
        spec,
        {
            "debug_prompt": {
                "tool_trace": [{"tool_name": "get_peer_comparison", "success": True}],
            },
            "output_payload": {},
        },
        output_text,
    )

    assert result["enabled"] is True
    ranking_item = next(item for item in result["items"] if "排名第1" in str(item["value"]))
    assert ranking_item["risk_level"] == "high"
    assert ranking_item["source_type"] == "tool_or_data_backed"
    assert ranking_item["evidence_tools"] == ["get_peer_comparison"]


def test_build_production_review_evidence_bundle_records_worker_orchestration():
    service = AgentWorkshopService.__new__(AgentWorkshopService)
    spec = _build_spec()
    version = _build_version(AgentVersionStatus.TESTING, "spec_valuation_candidate_v1_v1", 1)

    bundle = service._build_production_review_evidence_bundle(
        version,
        spec,
        {
            "output_text": "综合判断当前合理估值区间约为 18-22 倍 PE。",
            "output_payload": {"valuation_report": "估值结论"},
            "debug_prompt": {},
        },
        {
            "runtime_goal_alignment": 0.9,
            "runtime_output_coverage": 0.82,
            "runtime_explainability": 0.8,
            "runtime_execution_readiness": 0.55,
            "runtime_constraint_control": 0.92,
        },
        {
            "score_breakdown": {
                "runtime_output_coverage": {"missing": []},
                "runtime_explainability": {"missing": []},
                "runtime_constraint_control": {"missing": []},
            },
            "execution_plan_review": {
                "issues": ["execution_plan 验收未通过：这次运行还没有达到版本创建时定义的执行验证要求。"],
                "missing": ["未命中的 required_tools：get_value_factor_bundle_tool"],
                "missing_required_tools": ["get_value_factor_bundle_tool"],
            },
            "valuation_traceability": {
                "items": [
                    {"value": "18-22 倍 PE", "source_type": "unverified"},
                ],
            },
        },
    )

    assert bundle.orchestrator.worker_execution_mode == "rules-primary"
    assert bundle.orchestrator.nanobot_worker_enabled is False
    assert bundle.orchestrator.planned_task_count == len(bundle.evidence_tasks)
    assert len(bundle.candidate_findings) >= 1
    assert len(bundle.worker_results) == len(bundle.evidence_tasks)
    assert any(item.worker_name == "ToolUsageWorker" for item in bundle.worker_results)
    assert any(item.status == "insufficient_evidence" for item in bundle.worker_results)
    assert any(item.artifacts for item in bundle.worker_results)


def test_build_production_review_worker_artifacts_traceability_gap_includes_line_number() -> None:
    service = AgentWorkshopService.__new__(AgentWorkshopService)
    finding = AgentEvaluationCandidateFinding(
        finding_id="numeric_traceability_1",
        category="numeric_traceability",
        title="数值结果缺少可追溯依据",
    )
    task = AgentEvaluationEvidenceTask(
        task_id="task_1",
        finding_id="numeric_traceability_1",
        worker_name="NumericTraceabilityWorker",
        objective="查证数值结果缺口",
    )

    artifacts = service._build_production_review_worker_artifacts(
        finding,
        task,
        {
            "output_text": "第一行\n景气位置结论：电气设备板块当前处于周期下行，板块近20日下跌5-8%。\n第三行",
            "output_payload": {},
            "debug_prompt": {},
        },
        {
            "valuation_traceability": {
                "items": [
                    {"value": "板块近20日下跌5-8%", "source_type": "unverified", "risk_level": "high"},
                ],
            },
        },
    )

    traceability_artifact = next(item for item in artifacts if item["artifact_type"] == "traceability_gap")
    assert traceability_artifact["path"] == "rule_review.valuation_traceability.items[0]"
    assert traceability_artifact["metadata"]["line_number"] == 2
    assert "板块近20日下跌5-8%" in traceability_artifact["metadata"]["line_excerpt"]


@pytest.mark.asyncio
async def test_review_evaluation_artifact_can_approve_false_positive_and_flip_decision() -> None:
    spec = _build_spec()
    version = _build_version(AgentVersionStatus.TESTING, "spec_valuation_candidate_v1_v1", 1)
    evaluation = AgentEvaluationReport(
        evaluation_id="eval_manual_review_001",
        version_id=version.version_id,
        evaluation_type="production-review",
        scores={
            "runtime_goal_alignment": 0.92,
            "runtime_output_coverage": 0.91,
            "runtime_explainability": 0.86,
            "runtime_execution_readiness": 0.88,
            "runtime_constraint_control": 0.94,
            "overall": 0.71,
        },
        issues=["数值类结果违反可追溯硬约束：输出了精确数字或区间，但没有提供可追溯的数据源或工具计算依据。"],
        recommendations=[],
        decision="revise",
        details={
            "valuation_traceability": {
                "enabled": True,
                "items": [
                    {"value": "排名第1", "source_type": "unverified", "risk_level": "high", "judgement": "证据不足"},
                ],
            },
            "valuation_guardrail": {"severity": "blocker", "violation": True, "warnings": []},
            "execution_plan_review": {"score": 0.88, "blocker_issues": [], "warning_issues": [], "issues": [], "missing": []},
            "rule_review": {
                "scores": {
                    "runtime_goal_alignment": 0.92,
                    "runtime_output_coverage": 0.91,
                    "runtime_explainability": 0.86,
                    "runtime_execution_readiness": 0.88,
                    "runtime_constraint_control": 0.94,
                },
                "score_breakdown": {
                    "runtime_output_coverage": {"matched": ["analysis_report"], "missing": []},
                    "runtime_explainability": {"matched": ["风险"], "missing": []},
                    "runtime_constraint_control": {"matched": [], "missing": [], "notes": []},
                },
            },
            "layered_review": {
                "content_quality": {"score": 0.91, "decision": "pass", "warnings": [], "blockers": []},
                "publish_readiness": {"score": 0.71, "decision": "revise", "warnings": [], "blockers": ["高风险精确数值缺少可追溯依据：涉及估值区间、目标价、排序、权重或概率等发布敏感结论。"]},
                "blockers": ["高风险精确数值缺少可追溯依据：涉及估值区间、目标价、排序、权重或概率等发布敏感结论。"],
                "warnings": [],
            },
            "evidence_bundle": {
                "review_mode": "evidence-first",
                "evaluation_valid": True,
                "evaluation_status": "valid",
                "findings": [
                    {"category": "numeric_traceability", "severity": "blocker", "status": "confirmed_issue", "title": "数值结果缺少可追溯依据", "issue": "数值类结果违反可追溯硬约束：输出了精确数字或区间，但没有提供可追溯的数据源或工具计算依据。", "evidence": ["排名第1"]},
                ],
                "official_issues": ["数值类结果违反可追溯硬约束：输出了精确数字或区间，但没有提供可追溯的数据源或工具计算依据。"],
                "insufficient_evidence": [],
                "invalid_reasons": [],
                "runtime_summary": {"has_output_text": True, "has_output_payload": True, "has_debug_prompt": True, "tool_trace_observed": True, "required_tools": ["get_peer_comparison"], "spec_outputs": ["analysis_report"]},
                "candidate_findings": [
                    {"finding_id": "numeric_traceability_1", "category": "numeric_traceability", "severity": "blocker", "title": "数值结果缺少可追溯依据", "trigger": "valuation_traceability.items 中存在 unverified 项", "status": "confirmed"},
                ],
                "evidence_tasks": [
                    {"task_id": "task_1", "finding_id": "numeric_traceability_1", "worker_name": "NumericTraceabilityWorker", "objective": "查证候选问题：数值结果缺少可追溯依据", "evidence_targets": ["valuation_traceability"], "status": "done"},
                ],
                "worker_results": [
                    {"task_id": "task_1", "finding_id": "numeric_traceability_1", "worker_name": "NumericTraceabilityWorker", "status": "confirmed", "source": "rules", "summary": "数值结果中仍存在未验证来源的区间或精确数字。", "evidence": ["排名第1"], "artifacts": [{"artifact_type": "traceability_gap", "title": "未验证数值证据 1", "path": "rule_review.valuation_traceability.items[0]", "content": "{...}", "metadata": {"value": "排名第1", "source_type": "unverified"}}]},
                ],
                "manual_reviews": [],
                "orchestrator": {"mode": "evidence-first", "worker_execution_mode": "rules-primary", "nanobot_worker_enabled": False, "planned_task_count": 1, "completed_worker_count": 1},
            },
        },
    )

    fake_db = _FakeDb({
        SPEC_COLLECTION: _FakeCollection([spec.model_dump(mode="json", by_alias=True)]),
        VERSION_COLLECTION: _FakeCollection([version.model_dump(mode="json", by_alias=True)]),
        EVALUATION_COLLECTION: _FakeCollection([evaluation.model_dump(mode="json", by_alias=True)]),
    })
    svc = AgentWorkshopService(fake_db)

    result = await svc.review_evaluation_artifact(
        evaluation_id=evaluation.evaluation_id,
        target_path="rule_review.valuation_traceability.items[0]",
        target_title="未验证数值证据 1",
        artifact_type="traceability_gap",
        finding_id="numeric_traceability_1",
        worker_name="NumericTraceabilityWorker",
        approved=True,
        reason="该排名可由同报告内的来源标注表格直接复核，属于误报。",
        comment="人工审核通过",
    )

    assert result["publish_ready"] is True
    assert result["evaluation"].decision == "pass"
    assert result["evaluation"].issues == []
    assert result["evaluation"].details["manual_review_summary"]["approved_count"] == 1


@pytest.mark.asyncio
async def test_evaluate_version_pass_keeps_testing_and_records_result(monkeypatch):
    spec = _build_spec()
    spec.status = AgentSpecStatus.TESTING
    session = _build_session()
    session.stage = AgentWorkshopStage.EVALUATING
    version = _build_version(AgentVersionStatus.TESTING, "spec_valuation_candidate_v1_v1", 1)
    fake_db = _FakeDb({
        SPEC_COLLECTION: _FakeCollection([spec.model_dump(mode="json", by_alias=True)]),
        SESSION_COLLECTION: _FakeCollection([session.model_dump(mode="json", by_alias=True)]),
        VERSION_COLLECTION: _FakeCollection([version.model_dump(mode="json", by_alias=True)]),
        EVALUATION_COLLECTION: _FakeCollection([]),
    })
    svc = AgentWorkshopService(fake_db)

    async def _fake_evaluate_runtime_result(_version, _spec, _runtime_result, user_feedback=""):
        del user_feedback
        return ({"accuracy": 0.92}, [], ["可以进入测试态"], {})

    monkeypatch.setattr(svc, "_evaluate_runtime_result", _fake_evaluate_runtime_result)

    result = await svc.evaluate_version(
        version.version_id,
        evaluation_type="production-review",
        runtime_result={"output_text": "贵州茅台估值区间..."},
    )

    saved_version = await fake_db[VERSION_COLLECTION].find_one({"version_id": version.version_id})
    saved_session = await fake_db[SESSION_COLLECTION].find_one({"session_id": session.session_id})
    saved_evaluation = fake_db[EVALUATION_COLLECTION]._items[0]

    assert result["evaluation"].decision == "pass"
    assert saved_version["status"] == AgentVersionStatus.TESTING.value
    assert saved_version["version_id"] == version.version_id
    assert saved_session["stage"] == AgentWorkshopStage.EVALUATING.value
    assert saved_evaluation["decision"] == "pass"
    assert saved_evaluation["version_id"] == version.version_id


@pytest.mark.asyncio
async def test_evaluate_runtime_result_uses_evidence_bundle_as_official_review(monkeypatch):
    svc = AgentWorkshopService(_FakeDb({}))
    version = _build_version(AgentVersionStatus.TESTING, "spec_valuation_candidate_v1_v1", 1)
    spec = _build_spec()

    def _fake_rule_review(_version, _spec, _runtime_result, user_feedback=""):
        del _version, _spec, _runtime_result, user_feedback
        return (
            {
                "runtime_goal_alignment": 0.92,
                "runtime_output_coverage": 0.62,
                "runtime_explainability": 0.83,
                "runtime_execution_readiness": 0.9,
                "runtime_constraint_control": 0.94,
            },
            ["规则层确认：核心输出字段覆盖不足。"],
            ["规则层建议：补齐结构化输出字段。"],
            {
                "parsed_output_excerpt": "已生成估值结论。",
                "valuation_traceability": {"enabled": True, "items": [], "used_tools": ["get_value_factor_bundle_tool"]},
                "execution_plan_review": {
                    "score": 0.9,
                    "issues": [],
                    "missing": [],
                    "missing_required_tools": [],
                },
                "score_breakdown": {
                    "runtime_output_coverage": {"missing": ["valuation_report 摘要字段"]},
                    "runtime_explainability": {"missing": []},
                    "runtime_constraint_control": {"missing": []},
                },
            },
        )

    async def _fake_llm_review(_version, _spec, _runtime_result, user_feedback="", rule_details=None):
        del _version, _spec, _runtime_result, user_feedback, rule_details
        return {
            "summary": "LLM 认为总体可用。",
            "scores": {
                "runtime_goal_alignment": 0.99,
                "runtime_output_quality": 0.99,
                "runtime_reasoning_quality": 0.99,
                "runtime_tool_usage": 0.99,
                "runtime_prompt_quality": 0.99,
                "runtime_constraint_control": 0.99,
            },
            "issues": ["LLM 猜测：某个工具参数错误。"],
            "recommendations": ["LLM 建议：继续调 prompt。"],
        }

    monkeypatch.setattr(svc, "_evaluate_runtime_result_rules", _fake_rule_review)
    monkeypatch.setattr(svc, "_judge_runtime_result_with_llm", _fake_llm_review)

    scores, issues, recommendations, details = await svc._evaluate_runtime_result(
        version,
        spec,
        {
            "output_text": "已输出 valuation_report，并附带依据、假设与风险。",
            "output_payload": {"valuation_report": "ok"},
            "debug_prompt": {
                "system_prompt": "system",
                "user_prompt": "user",
                "tool_trace": [{"tool_name": "get_value_factor_bundle_tool", "success": True}],
            },
        },
    )

    assert scores["runtime_tool_usage"] == 0.9
    assert issues == []
    assert recommendations == ["规则层建议：补齐结构化输出字段。"]
    assert details["evaluation_engine"] == "evidence-first-primary"
    assert details["evaluation_valid"] is True
    assert details["evidence_bundle"]["official_issues"] == []
    assert "运行结果对部分核心输出字段覆盖不足，但主体输出已基本成型。" in details["warning_issues"]
    assert details["layered_review"]["publish_readiness"]["decision"] == "pass"
    assert details["llm_advisory"]["issues"] == ["LLM 猜测：某个工具参数错误。"]
    assert details["evidence_bundle"]["runtime_summary"]["tool_trace_observed"] is True
    assert details["evidence_bundle"]["orchestrator"]["worker_execution_mode"] == "rules-primary"
    assert len(details["evidence_bundle"]["candidate_findings"]) == 0
    assert len(details["evidence_bundle"]["evidence_tasks"]) == 0
    assert len(details["evidence_bundle"]["worker_results"]) == 0


@pytest.mark.asyncio
async def test_evaluate_runtime_result_separates_content_quality_and_publish_readiness(monkeypatch):
    svc = AgentWorkshopService(_FakeDb({}))
    version = _build_version(AgentVersionStatus.TESTING, "spec_valuation_candidate_v1_v1", 1)
    spec = _build_spec()
    spec.primary_goal = "对A股个股进行财报多期跟踪分析，输出结构化风险提示报告并保留来源映射。"
    spec.constraints = [
        "所有数值必须来自工具返回，并保留来源工具与报告期映射。",
    ]

    async def _fake_llm_review(_version, _spec, _runtime_result, user_feedback="", rule_details=None):
        del _version, _spec, _runtime_result, user_feedback, rule_details
        return {"summary": "advisory", "scores": {}, "issues": [], "recommendations": []}

    monkeypatch.setattr(svc, "_judge_runtime_result_with_llm", _fake_llm_review)

    scores, issues, _recommendations, details = await svc._evaluate_runtime_result(
        version,
        spec,
        {
            "symbol": "600519",
            "analysis_date": "2026-04-06",
            "output_text": """
## 一、核心风险指标总览
valuation_report：财报风险跟踪结论
关键假设：当前披露口径与历史财报口径保持一致。
Altman Z-Score | 31.31 | 财务健康度极高
Piotroski F-Score | 6分 | 财务状况稳健

## 六、风险识别与提示
当前主要风险为存货周转偏慢，但白酒行业属性具有一定缓释作用。

## 八、数据来源与可追溯性声明
| 分析模块 | 数据来源工具 | 关键数据点 | 报告期 |
|---------|-------------|-----------|--------|
| 质量因子 | get_quality_factor_bundle_tool | ROE、Z-Score、F-Score等 | 2025Q3 |
| 资产负债分析 | get_balance_sheet_analysis | 负债率、流动比率等 | 2023Q4-2025Q3 |
""",
            "output_payload": {"valuation_report": "财报风险跟踪结论"},
            "debug_prompt": {
                "system_prompt": "system",
                "user_prompt": "user",
                "tool_trace": [
                    {"tool_name": "get_value_factor_bundle_tool", "success": True},
                    {"tool_name": "get_peer_comparison", "success": True},
                    {"tool_name": "get_quality_factor_bundle_tool", "success": True},
                    {"tool_name": "get_balance_sheet_analysis", "success": True},
                ],
            },
        },
    )

    assert issues == []
    assert details["layered_review"]["content_quality"]["decision"] in {"pass", "pass_with_warnings", "revise"}
    assert details["layered_review"]["publish_readiness"]["decision"] == "pass"
    assert isinstance(details["warning_issues"], list)
    assert scores["runtime_tool_usage"] >= 0.8


@pytest.mark.asyncio
async def test_evaluate_runtime_result_can_switch_to_nanobot_assisted_workers(monkeypatch):
    svc = AgentWorkshopService(_FakeDb({}))
    version = _build_version(AgentVersionStatus.TESTING, "spec_valuation_candidate_v1_v1", 1)
    spec = _build_spec()

    def _fake_rule_review(_version, _spec, _runtime_result, user_feedback=""):
        del _version, _spec, _runtime_result, user_feedback
        return (
            {
                "runtime_goal_alignment": 0.9,
                "runtime_output_coverage": 0.8,
                "runtime_explainability": 0.82,
                "runtime_execution_readiness": 0.6,
                "runtime_constraint_control": 0.93,
            },
            [],
            [],
            {
                "parsed_output_excerpt": "估值结果已生成。",
                "valuation_traceability": {
                    "enabled": True,
                    "items": [{"value": "18-22 倍 PE", "source_type": "unverified", "risk_level": "high"}],
                    "used_tools": [],
                },
                "execution_plan_review": {
                    "score": 0.6,
                    "issues": ["execution_plan 验收未通过：这次运行还没有达到版本创建时定义的执行验证要求。"],
                    "blocker_issues": [],
                    "warning_issues": ["execution_plan 验收仍有未通过项，建议继续补强执行一致性。"],
                    "missing": ["未命中的 required_tools：get_value_factor_bundle_tool"],
                    "missing_required_tools": ["get_value_factor_bundle_tool"],
                },
                "score_breakdown": {
                    "runtime_output_coverage": {"missing": []},
                    "runtime_explainability": {"missing": []},
                    "runtime_constraint_control": {"missing": []},
                },
            },
        )

    async def _fake_llm_review(_version, _spec, _runtime_result, user_feedback="", rule_details=None):
        del _version, _spec, _runtime_result, user_feedback, rule_details
        return {"summary": "advisory", "scores": {}, "issues": [], "recommendations": []}

    async def _fake_nanobot_worker(task, finding, _version, _spec, _runtime_result, _rule_details, fallback_result=None):
        del _version, _spec, _runtime_result, _rule_details, fallback_result
        if task.worker_name == "RuntimeFailureWorker":
            return AgentEvaluationWorkerResult(
                task_id=task.task_id,
                finding_id=finding.finding_id if finding else task.finding_id,
                worker_name=task.worker_name,
                status="disproved",
                source="nanobot",
                summary="Nanobot 复核后认为 execution_plan 的告警不足以定案。",
                evidence=["Nanobot: 当前运行结果里没有足够证据支撑 execution_plan 失败结论"],
                artifacts=[{
                    "artifact_type": "execution_plan_review",
                    "title": "execution_plan 复核摘录",
                    "path": "rule_review.execution_plan_review.issues",
                    "content": "issues 当前不足以直接定案",
                    "metadata": {"worker": "RuntimeFailureWorker"},
                }],
            )
        if task.worker_name == "NumericTraceabilityWorker":
            return AgentEvaluationWorkerResult(
                task_id=task.task_id,
                finding_id=finding.finding_id if finding else task.finding_id,
                worker_name=task.worker_name,
                status="confirmed",
                source="nanobot",
                summary="Nanobot 确认当前数值区间没有直接可追溯来源。",
                evidence=["Nanobot: 输出中出现 18-22 倍 PE，但 tool_trace 为空且未附数据来源"],
                artifacts=[{
                    "artifact_type": "traceability_gap",
                    "title": "数值可追溯性缺口",
                    "path": "runtime_result.output_text",
                    "content": "18-22 倍 PE",
                    "metadata": {"worker": "NumericTraceabilityWorker"},
                }],
            )
        return AgentEvaluationWorkerResult(
            task_id=task.task_id,
            finding_id=finding.finding_id if finding else task.finding_id,
            worker_name=task.worker_name,
            status="insufficient_evidence",
            source="nanobot",
            summary="Nanobot 已核查，但当前缺少直接工具轨迹。",
            evidence=["Nanobot: debug_prompt.tool_trace 缺失"],
            artifacts=[{
                "artifact_type": "tool_trace_gap",
                "title": "缺少工具轨迹",
                "path": "runtime_result.debug_prompt.tool_trace",
                "content": "tool_trace 缺失",
                "metadata": {"worker": task.worker_name},
            }],
        )

    monkeypatch.setattr(svc, "_evaluate_runtime_result_rules", _fake_rule_review)
    monkeypatch.setattr(svc, "_judge_runtime_result_with_llm", _fake_llm_review)
    monkeypatch.setattr(svc, "_should_use_nanobot_evidence_workers", lambda _version, _runtime_result: True)
    monkeypatch.setattr(svc, "_run_nanobot_evidence_worker_task", _fake_nanobot_worker)

    _, _, _, details = await svc._evaluate_runtime_result(
        version,
        spec,
        {
            "output_text": "综合判断当前合理估值区间约为 18-22 倍 PE。",
            "output_payload": {"valuation_report": "ok"},
            "debug_prompt": {},
        },
    )

    assert details["evidence_bundle"]["orchestrator"]["worker_execution_mode"] == "nanobot-assisted"
    assert details["evidence_bundle"]["orchestrator"]["nanobot_worker_enabled"] is True
    assert details["evaluation_engine"] == "evidence-first-nanobot-assisted"
    assert any(item["source"] == "nanobot" for item in details["evidence_bundle"]["worker_results"])
    assert any(item.get("artifacts") for item in details["evidence_bundle"]["worker_results"])
    assert details["evidence_bundle"]["official_issues"] == [
        "数值类结果违反可追溯硬约束：输出了精确数字或区间，但没有提供可追溯的数据源或工具计算依据。",
    ]
    assert details["evidence_bundle"]["invalid_reasons"] == [
        "缺少 required_tools 的 tool_trace 证据，当前工具使用评估不能定案。",
    ]


@pytest.mark.asyncio
async def test_evaluate_runtime_result_nanobot_assisted_can_review_project_memory_binding(monkeypatch):
    svc = AgentWorkshopService(_FakeDb({}))
    version = _build_version(AgentVersionStatus.TESTING, "spec_valuation_candidate_v1_v1", 1)
    version.required_tools = ["get_value_factor_bundle_tool"]
    spec = _build_spec()

    async def _fake_build_project_memory_block():
        return "【项目长期记忆】\n- 项目规则\n  - 禁止直接投资建议：所有分析只提供研究与学习参考。"

    async def _fake_llm_review(_version, _spec, _runtime_result, user_feedback="", rule_details=None):
        del _version, _spec, _runtime_result, user_feedback, rule_details
        return {"summary": "advisory", "scores": {}, "issues": [], "recommendations": []}

    captured = {"tasks": []}

    async def _fake_nanobot_worker(task, finding, _version, _spec, _runtime_result, _rule_details, fallback_result=None):
        del _version, _spec, _runtime_result, fallback_result
        captured["tasks"].append({
            "worker_name": task.worker_name,
            "category": finding.category if finding else "",
            "project_memory_binding": dict(_rule_details.get("project_memory_binding") or {}),
        })
        if finding and finding.category == "project_memory_binding":
            return AgentEvaluationWorkerResult(
                task_id=task.task_id,
                finding_id=finding.finding_id,
                worker_name=task.worker_name,
                status="confirmed",
                source="nanobot",
                summary="Nanobot 确认当前运行时 prompt 没有带上所需项目长期记忆。",
                evidence=["Nanobot: system_prompt 未出现【项目长期记忆】标记与对应规则片段。"],
                artifacts=[{
                    "artifact_type": "runtime_system_prompt",
                    "title": "system_prompt 摘录",
                    "path": "runtime_result.debug_prompt.system_prompt",
                    "content": "你是估值分析师。请输出研究结论。",
                    "metadata": {"worker": task.worker_name},
                }],
            )
        raise AssertionError(f"unexpected worker: {task.worker_name}")

    monkeypatch.setattr(svc, "_build_project_memory_block_for_workshop", _fake_build_project_memory_block)
    monkeypatch.setattr(svc, "_judge_runtime_result_with_llm", _fake_llm_review)
    monkeypatch.setattr(svc, "_should_use_nanobot_evidence_workers", lambda _version, _runtime_result: True)
    monkeypatch.setattr(svc, "_run_nanobot_evidence_worker_task", _fake_nanobot_worker)

    _scores, issues, _recommendations, details = await svc._evaluate_runtime_result(
        version,
        spec,
        {
            "output_text": "已输出 valuation_report，并附带依据、假设与风险。",
            "output_payload": {"valuation_report": "ok"},
            "debug_prompt": {
                "system_prompt": "你是估值分析师。请输出研究结论。",
                "user_prompt": "user",
                "tool_trace": [{"tool_name": "get_value_factor_bundle_tool", "success": True}],
            },
            "review_worker_mode": "nanobot-assisted",
        },
    )

    assert details["evidence_bundle"]["orchestrator"]["worker_execution_mode"] == "nanobot-assisted"
    assert any(item["worker_name"] == "PromptEvidenceWorker" for item in captured["tasks"])
    assert any(item["category"] == "project_memory_binding" for item in captured["tasks"])
    assert captured["tasks"][0]["project_memory_binding"]["enabled"] is True
    assert any("system_prompt 没有完整包含当前 L4 项目长期记忆" in item for item in issues)


def test_build_nanobot_evidence_worker_prompt_includes_project_memory_binding_context():
    svc = AgentWorkshopService(_FakeDb({}))
    version = _build_version(AgentVersionStatus.TESTING, "spec_valuation_candidate_v1_v1", 1)
    spec = _build_spec()
    task = AgentEvaluationEvidenceTask(
        task_id="task_1",
        finding_id="project_memory_binding_1",
        worker_name="PromptEvidenceWorker",
        objective="查证候选问题：运行时 Prompt 缺少当前项目长期记忆",
        evidence_targets=["debug_prompt.system_prompt 未完整包含当前 L4 项目长期记忆"],
        status="planned",
    )
    finding = AgentEvaluationCandidateFinding(
        finding_id="project_memory_binding_1",
        category="project_memory_binding",
        severity="blocker",
        title="运行时 Prompt 缺少当前项目长期记忆",
        trigger="debug_prompt.system_prompt 未完整包含当前 L4 项目长期记忆",
        status="pending",
    )

    prompt = svc._build_nanobot_evidence_worker_prompt(
        task,
        finding,
        version,
        spec,
        {
            "output_text": "已输出 valuation_report。",
            "output_payload": {"valuation_report": "ok"},
            "debug_prompt": {
                "system_prompt": "你是估值分析师。请输出研究结论。",
                "user_prompt": "user",
                "tool_trace": [],
            },
        },
        {
            "score_breakdown": {},
            "execution_plan_review": {},
            "valuation_traceability": {},
            "project_memory_binding": {
                "enabled": True,
                "valid": False,
                "system_prompt_present": True,
                "marker_present": False,
                "expected_items": 2,
                "matched_items": 0,
                "missing_items": ["- 项目规则", "- 禁止直接投资建议：所有分析只提供研究与学习参考。"],
            },
        },
    )

    assert '"project_memory_binding"' in prompt
    assert "如果当前 finding.category 是 project_memory_binding" in prompt
    assert "缺少 runtime_result.debug_prompt.system_prompt" not in prompt


@pytest.mark.asyncio
async def test_run_nanobot_evidence_worker_task_passes_user_id_to_embedded_nanobot(monkeypatch):
    fake_db = _FakeDb({
        SESSION_COLLECTION: _FakeCollection([
            _build_session().model_dump(mode="json", by_alias=True),
        ]),
    })
    svc = AgentWorkshopService(fake_db)
    spec = _build_spec()
    version = _build_version(AgentVersionStatus.TESTING, "spec_valuation_candidate_v1_v2", 2)
    task = AgentEvaluationEvidenceTask(
        task_id="task_nanobot_001",
        finding_id="finding_nanobot_001",
        worker_name="PromptEvidenceWorker",
        objective="核查 prompt 证据",
    )
    finding = AgentEvaluationCandidateFinding(
        finding_id="finding_nanobot_001",
        category="prompt_evidence",
        title="提示词证据缺口",
    )
    captured = {}

    class _FakeEmbeddedNanobotService:
        def __init__(self, db, workspace, preferred_model=None):
            captured["init"] = {
                "db": db,
                "workspace": workspace,
                "preferred_model": preferred_model,
            }

        async def chat(self, **kwargs):
            captured["chat_kwargs"] = dict(kwargs)
            return {
                "content": json.dumps({
                    "status": "confirmed",
                    "summary": "nanobot 已确认",
                    "evidence": ["证据 1"],
                    "artifacts": [],
                }, ensure_ascii=False),
            }

    monkeypatch.setattr(
        "app.services.embedded_nanobot_service.EmbeddedNanobotService",
        _FakeEmbeddedNanobotService,
    )
    monkeypatch.setattr(svc, "_build_nanobot_evidence_worker_prompt", lambda *_args, **_kwargs: "worker prompt")

    result = await svc._run_nanobot_evidence_worker_task(
        task,
        finding,
        version,
        spec,
        {"output_text": "ok", "output_payload": {}, "debug_prompt": {}},
        {"project_memory_binding": {"enabled": True}},
    )

    assert result.status == "confirmed"
    assert result.source == "nanobot"
    assert result.summary == "nanobot 已确认"
    assert captured["chat_kwargs"]["user_id"] == "user_001"
    assert captured["chat_kwargs"]["channel"] == "agent_workshop_evaluation"
    assert captured["chat_kwargs"]["thread_context"]["spec_id"] == spec.spec_id
    assert captured["chat_kwargs"]["thread_context"]["version_id"] == version.version_id
    assert captured["chat_kwargs"]["thread_context"]["workshop_session_id"] == version.published_from_session_id


@pytest.mark.asyncio
async def test_evaluate_runtime_result_does_not_raise_constraint_candidate_from_missing_list(monkeypatch):
    svc = AgentWorkshopService(_FakeDb({}))
    version = _build_version(AgentVersionStatus.TESTING, "spec_valuation_candidate_v1_v1", 1)
    spec = _build_spec()

    def _fake_rule_review(_version, _spec, _runtime_result, user_feedback=""):
        del _version, _spec, _runtime_result, user_feedback
        return (
            {
                "runtime_goal_alignment": 0.92,
                "runtime_output_coverage": 0.9,
                "runtime_explainability": 0.82,
                "runtime_execution_readiness": 0.88,
                "runtime_constraint_control": 0.72,
            },
            [],
            [],
            {
                "parsed_output_excerpt": "已生成行业比较分析。",
                "valuation_guardrail": {"severity": "none", "violation": False, "warnings": []},
                "valuation_traceability": {"enabled": True, "items": [], "used_tools": ["get_peer_comparison"]},
                "execution_plan_review": {
                    "score": 0.88,
                    "issues": [],
                    "blocker_issues": [],
                    "warning_issues": [],
                    "missing": [],
                    "missing_required_tools": [],
                },
                "score_breakdown": {
                    "runtime_output_coverage": {"matched": ["analysis_report"], "missing": []},
                    "runtime_explainability": {"matched": ["风险"], "missing": ["失效条件"]},
                    "runtime_constraint_control": {
                        "matched": [],
                        "missing": ["交易建议", "高风险精确数值缺少可追溯的数据或工具依据。"],
                        "notes": ["matched 表示命中了非目标或越界词，命中越多扣分越多。"],
                    },
                },
            },
        )

    async def _fake_llm_review(_version, _spec, _runtime_result, user_feedback="", rule_details=None):
        del _version, _spec, _runtime_result, user_feedback, rule_details
        return {"summary": "advisory", "scores": {}, "issues": [], "recommendations": []}

    monkeypatch.setattr(svc, "_evaluate_runtime_result_rules", _fake_rule_review)
    monkeypatch.setattr(svc, "_judge_runtime_result_with_llm", _fake_llm_review)

    _, issues, _, details = await svc._evaluate_runtime_result(
        version,
        spec,
        {
            "output_text": "已输出行业比较分析，并说明主要风险。",
            "output_payload": {"analysis_report": "ok"},
            "debug_prompt": {"tool_trace": [{"tool_name": "get_peer_comparison", "success": True}]},
        },
    )

    assert details["evidence_bundle"]["official_issues"] == []
    assert details["blocker_issues"] == []
    assert "运行结果出现了越界表达，和规格中的非目标不一致。" not in issues
    assert details["layered_review"]["publish_readiness"]["decision"] == "pass"


@pytest.mark.asyncio
async def test_evaluate_runtime_result_removes_numeric_blocker_when_worker_disproves(monkeypatch):
    svc = AgentWorkshopService(_FakeDb({}))
    version = _build_version(AgentVersionStatus.TESTING, "spec_valuation_candidate_v1_v1", 1)
    spec = _build_spec()

    def _fake_rule_review(_version, _spec, _runtime_result, user_feedback=""):
        del _version, _spec, _runtime_result, user_feedback
        return (
            {
                "runtime_goal_alignment": 0.94,
                "runtime_output_coverage": 0.9,
                "runtime_explainability": 0.82,
                "runtime_execution_readiness": 0.84,
                "runtime_constraint_control": 0.91,
            },
            [],
            [],
            {
                "parsed_output_excerpt": "已生成行业比较分析。",
                "valuation_guardrail": {
                    "severity": "blocker",
                    "violation": True,
                    "warnings": [],
                    "missing": ["高风险精确数值缺少可追溯的数据或工具依据。"],
                },
                "valuation_traceability": {
                    "enabled": True,
                    "items": [{"value": "1,500-1", "source_type": "unverified", "risk_level": "high"}],
                    "used_tools": ["get_peer_comparison"],
                },
                "execution_plan_review": {
                    "score": 0.84,
                    "issues": [],
                    "blocker_issues": [],
                    "warning_issues": [],
                    "missing": [],
                    "missing_required_tools": [],
                },
                "score_breakdown": {
                    "runtime_output_coverage": {"matched": ["analysis_report"], "missing": []},
                    "runtime_explainability": {"matched": ["风险"], "missing": []},
                    "runtime_constraint_control": {"matched": [], "missing": [], "notes": []},
                },
            },
        )

    async def _fake_llm_review(_version, _spec, _runtime_result, user_feedback="", rule_details=None):
        del _version, _spec, _runtime_result, user_feedback, rule_details
        return {"summary": "advisory", "scores": {}, "issues": [], "recommendations": []}

    async def _fake_nanobot_worker(task, finding, _version, _spec, _runtime_result, _rule_details, fallback_result=None):
        del _version, _spec, _runtime_result, _rule_details, fallback_result
        return AgentEvaluationWorkerResult(
            task_id=task.task_id,
            finding_id=finding.finding_id if finding else task.finding_id,
            worker_name=task.worker_name,
            status="disproved",
            source="nanobot",
            summary="该数值告警由输出截断触发，原始工具结果可追溯。",
            evidence=["原始 get_peer_comparison 返回中包含完整数值，当前 unverified 来自截断。"],
            artifacts=[{
                "artifact_type": "tool_trace",
                "title": "get_peer_comparison 返回的同业市值数据",
                "path": "runtime_result.debug_prompt.tool_trace[0]",
                "content": "3. 山西汾酒: 市值1729亿 | 4. 泸州老窖: 市值1535亿",
                "metadata": {"tool_name": "get_peer_comparison", "success": True},
            }],
        )

    monkeypatch.setattr(svc, "_evaluate_runtime_result_rules", _fake_rule_review)
    monkeypatch.setattr(svc, "_judge_runtime_result_with_llm", _fake_llm_review)
    monkeypatch.setattr(svc, "_should_use_nanobot_evidence_workers", lambda _version, _runtime_result: True)
    monkeypatch.setattr(svc, "_run_nanobot_evidence_worker_task", _fake_nanobot_worker)

    _, issues, _, details = await svc._evaluate_runtime_result(
        version,
        spec,
        {
            "output_text": "第三梯队：山西汾酒、泸州老窖（1,500-1...）。",
            "output_payload": {"analysis_report": "ok"},
            "debug_prompt": {"tool_trace": [{"tool_name": "get_peer_comparison", "success": True}]},
        },
    )

    assert details["evidence_bundle"]["official_issues"] == []
    assert details["blocker_issues"] == []
    assert "数值类结果违反可追溯硬约束：输出了精确数字或区间，但没有提供可追溯的数据源或工具计算依据。" not in issues
    assert details["layered_review"]["publish_readiness"]["decision"] == "pass"


@pytest.mark.asyncio
async def test_evaluate_runtime_result_revises_when_runtime_prompt_missing_project_memory_binding(monkeypatch):
    svc = AgentWorkshopService(_FakeDb({}))
    version = _build_version(AgentVersionStatus.TESTING, "spec_valuation_candidate_v1_v1", 1)
    version.required_tools = ["get_value_factor_bundle_tool"]
    spec = _build_spec()

    async def _fake_llm_review(_version, _spec, _runtime_result, user_feedback="", rule_details=None):
        del _version, _spec, _runtime_result, user_feedback, rule_details
        return {"summary": "advisory", "scores": {}, "issues": [], "recommendations": []}

    async def _fake_build_project_memory_block():
        return "【项目长期记忆】\n- 项目规则\n  - 禁止直接投资建议：所有分析只提供研究与学习参考。"

    monkeypatch.setattr(svc, "_judge_runtime_result_with_llm", _fake_llm_review)
    monkeypatch.setattr(svc, "_build_project_memory_block_for_workshop", _fake_build_project_memory_block)

    _scores, issues, recommendations, details = await svc._evaluate_runtime_result(
        version,
        spec,
        {
            "output_text": "已输出 valuation_report，并附带依据、假设与风险。",
            "output_payload": {"valuation_report": "ok"},
            "debug_prompt": {
                "system_prompt": "你是估值分析师。请输出研究结论。",
                "user_prompt": "user",
                "tool_trace": [{"tool_name": "get_value_factor_bundle_tool", "success": True}],
            },
        },
    )

    assert any("system_prompt 没有完整包含当前 L4 项目长期记忆" in item for item in issues)
    assert details["project_memory_binding"]["enabled"] is True
    assert details["project_memory_binding"]["valid"] is False
    assert details["evidence_bundle"]["runtime_summary"]["project_memory_binding_enabled"] is True
    assert details["evidence_bundle"]["runtime_summary"]["project_memory_binding_valid"] is False
    assert details["layered_review"]["publish_readiness"]["decision"] == "revise"
    assert any("重新使用当前 L4 项目长期记忆刷新版本模板" in item for item in recommendations)


@pytest.mark.asyncio
async def test_evaluate_runtime_result_marks_evidence_incomplete_when_system_prompt_missing_for_project_memory_review(monkeypatch):
    svc = AgentWorkshopService(_FakeDb({}))
    version = _build_version(AgentVersionStatus.TESTING, "spec_valuation_candidate_v1_v1", 1)
    spec = _build_spec()

    async def _fake_llm_review(_version, _spec, _runtime_result, user_feedback="", rule_details=None):
        del _version, _spec, _runtime_result, user_feedback, rule_details
        return {"summary": "advisory", "scores": {}, "issues": [], "recommendations": []}

    async def _fake_build_project_memory_block():
        return "【项目长期记忆】\n- 项目规则\n  - 禁止直接投资建议：所有分析只提供研究与学习参考。"

    monkeypatch.setattr(svc, "_judge_runtime_result_with_llm", _fake_llm_review)
    monkeypatch.setattr(svc, "_build_project_memory_block_for_workshop", _fake_build_project_memory_block)

    _scores, _issues, recommendations, details = await svc._evaluate_runtime_result(
        version,
        spec,
        {
            "output_text": "已输出 valuation_report，并附带依据、假设与风险。",
            "output_payload": {"valuation_report": "ok"},
            "debug_prompt": {
                "user_prompt": "user",
                "tool_trace": [{"tool_name": "get_value_factor_bundle_tool", "success": True}],
            },
        },
    )

    assert details["project_memory_binding"]["enabled"] is True
    assert details["project_memory_binding"]["system_prompt_present"] is False
    assert details["evaluation_valid"] is False
    assert "缺少 runtime system_prompt 证据，无法确认当前 L4 项目长期记忆是否真实注入。" in details["evidence_bundle"]["invalid_reasons"]
    assert details["layered_review"]["publish_readiness"]["decision"] == "revise"
    assert any("补齐运行时 debug_prompt.system_prompt 证据" in item for item in recommendations)


@pytest.mark.asyncio
async def test_evaluate_version_production_review_revises_when_evidence_incomplete(monkeypatch):
    spec = _build_spec()
    session = _build_session()
    version = _build_version(AgentVersionStatus.DRAFT, "spec_valuation_candidate_v1_v1", 1)
    fake_db = _FakeDb({
        SPEC_COLLECTION: _FakeCollection([spec.model_dump(mode="json", by_alias=True)]),
        SESSION_COLLECTION: _FakeCollection([session.model_dump(mode="json", by_alias=True)]),
        VERSION_COLLECTION: _FakeCollection([version.model_dump(mode="json", by_alias=True)]),
        EVALUATION_COLLECTION: _FakeCollection([]),
    })
    svc = AgentWorkshopService(fake_db)

    async def _fake_evaluate_runtime_result(_version, _spec, _runtime_result, user_feedback=""):
        del _version, _spec, _runtime_result, user_feedback
        return (
            {
                "runtime_goal_alignment": 0.95,
                "runtime_output_quality": 0.94,
                "runtime_reasoning_quality": 0.93,
                "runtime_tool_usage": 0.96,
                "runtime_prompt_quality": 0.9,
                "runtime_constraint_control": 0.95,
            },
            [],
            ["先补齐 tool_trace。"],
            {
                "mode": "production-review",
                "evaluation_valid": False,
                "evaluation_status": "evidence_incomplete",
                    "layered_review": {
                        "content_quality": {"score": 0.92, "decision": "pass", "blockers": [], "warnings": []},
                        "publish_readiness": {
                            "score": 0.58,
                            "decision": "revise",
                            "blockers": ["缺少 required_tools 的 tool_trace 证据。"],
                            "warnings": [],
                        },
                        "blockers": ["缺少 required_tools 的 tool_trace 证据。"],
                        "warnings": [],
                    },
                "evidence_bundle": {
                    "invalid_reasons": ["缺少 required_tools 的 tool_trace 证据。"],
                },
            },
        )

    monkeypatch.setattr(svc, "_evaluate_runtime_result", _fake_evaluate_runtime_result)

    result = await svc.evaluate_version(
        version.version_id,
        evaluation_type="production-review",
        runtime_result={"output_text": "表面上看起来分数很高"},
    )

    saved_version = await fake_db[VERSION_COLLECTION].find_one({"version_id": version.version_id})
    saved_evaluation = fake_db[EVALUATION_COLLECTION]._items[0]

    assert result["evaluation"].decision == "revise"
    assert result["evaluation"].details["evaluation_valid"] is False
    assert result["evaluation"].evidence_bundle is not None
    assert result["evaluation"].evidence_bundle.evaluation_status == "evidence_incomplete"
    assert saved_evaluation["decision"] == "revise"
    assert saved_version["status"] == AgentVersionStatus.DRAFT.value


@pytest.mark.asyncio
async def test_evaluate_version_production_review_rejects_missing_runtime_evidence(monkeypatch):
    spec = _build_spec()
    session = _build_session()
    version = _build_version(AgentVersionStatus.DRAFT, "spec_valuation_candidate_v1_v1", 1)
    fake_db = _FakeDb({
        SPEC_COLLECTION: _FakeCollection([spec.model_dump(mode="json", by_alias=True)]),
        SESSION_COLLECTION: _FakeCollection([session.model_dump(mode="json", by_alias=True)]),
        VERSION_COLLECTION: _FakeCollection([version.model_dump(mode="json", by_alias=True)]),
        EVALUATION_COLLECTION: _FakeCollection([]),
    })
    svc = AgentWorkshopService(fake_db)

    async def _fake_evaluate_runtime_result(_version, _spec, _runtime_result, user_feedback=""):
        del _version, _spec, _runtime_result, user_feedback
        raise AssertionError("_evaluate_runtime_result should not be called when runtime evidence is missing")

    monkeypatch.setattr(svc, "_evaluate_runtime_result", _fake_evaluate_runtime_result)

    with pytest.raises(ValueError, match="production-review 缺少必要的 runtime_result 证据"):
        await svc.evaluate_version(
            version.version_id,
            evaluation_type="production-review",
            runtime_result={"symbol": "600519", "analysis_date": "2026-04-05"},
        )

    assert fake_db[EVALUATION_COLLECTION]._items == []


@pytest.mark.asyncio
async def test_evaluate_version_production_review_normalizes_debug_result_payload(monkeypatch):
    spec = _build_spec()
    session = _build_session()
    version = _build_version(AgentVersionStatus.DRAFT, "spec_valuation_candidate_v1_v1", 1)
    fake_db = _FakeDb({
        SPEC_COLLECTION: _FakeCollection([spec.model_dump(mode="json", by_alias=True)]),
        SESSION_COLLECTION: _FakeCollection([session.model_dump(mode="json", by_alias=True)]),
        VERSION_COLLECTION: _FakeCollection([version.model_dump(mode="json", by_alias=True)]),
        EVALUATION_COLLECTION: _FakeCollection([]),
    })
    svc = AgentWorkshopService(fake_db)
    captured = {}

    async def _fake_evaluate_runtime_result(_version, _spec, _runtime_result, user_feedback=""):
        del _version, _spec, user_feedback
        captured["runtime_result"] = _runtime_result
        return (
            {
                "runtime_goal_alignment": 0.8,
                "runtime_output_quality": 0.8,
                "runtime_reasoning_quality": 0.8,
                "runtime_tool_usage": 0.8,
                "runtime_prompt_quality": 0.8,
                "runtime_constraint_control": 0.8,
            },
            [],
            [],
            {"evaluation_valid": True},
        )

    monkeypatch.setattr(svc, "_evaluate_runtime_result", _fake_evaluate_runtime_result)

    await svc.evaluate_version(
        version.version_id,
        evaluation_type="production-review",
        runtime_result={
            "symbol": "600519",
            "analysis_date": "2026-04-05",
            "report": "调试报告正文",
            "raw_result": {
                "risk_report": "调试报告正文",
                "__debug_prompt__": {
                    "system_prompt": "system",
                    "user_prompt": "user",
                    "tool_trace": [{"tool_name": "get_quality_factor_bundle_tool", "success": True}],
                },
            },
            "metadata": {
                "user_goal": "验证财报风险跟踪结果",
            },
        },
    )

    normalized = captured["runtime_result"]
    assert normalized["output_text"] == "调试报告正文"
    assert normalized["output_payload"]["risk_report"] == "调试报告正文"
    assert normalized["debug_prompt"]["system_prompt"] == "system"
    assert normalized["tool_trace"][0]["tool_name"] == "get_quality_factor_bundle_tool"
    assert normalized["user_goal"] == "验证财报风险跟踪结果"


@pytest.mark.asyncio
async def test_evaluate_version_production_review_normalizes_raw_result_tool_trace(monkeypatch):
    spec = _build_spec()
    session = _build_session()
    version = _build_version(AgentVersionStatus.DRAFT, "spec_valuation_candidate_v1_v1", 1)
    fake_db = _FakeDb({
        SPEC_COLLECTION: _FakeCollection([spec.model_dump(mode="json", by_alias=True)]),
        SESSION_COLLECTION: _FakeCollection([session.model_dump(mode="json", by_alias=True)]),
        VERSION_COLLECTION: _FakeCollection([version.model_dump(mode="json", by_alias=True)]),
        EVALUATION_COLLECTION: _FakeCollection([]),
    })
    svc = AgentWorkshopService(fake_db)
    captured = {}

    async def _fake_evaluate_runtime_result(_version, _spec, _runtime_result, user_feedback=""):
        del _version, _spec, user_feedback
        captured["runtime_result"] = _runtime_result
        return (
            {
                "runtime_goal_alignment": 0.8,
                "runtime_output_quality": 0.8,
                "runtime_reasoning_quality": 0.8,
                "runtime_tool_usage": 0.8,
                "runtime_prompt_quality": 0.8,
                "runtime_constraint_control": 0.8,
            },
            [],
            [],
            {"evaluation_valid": True},
        )

    monkeypatch.setattr(svc, "_evaluate_runtime_result", _fake_evaluate_runtime_result)

    await svc.evaluate_version(
        version.version_id,
        evaluation_type="production-review",
        runtime_result={
            "report": "调试报告正文",
            "raw_result": {
                "risk_report": "调试报告正文",
                "tool_trace": [{"tool_name": "get_quality_factor_bundle_tool", "success": True}],
            },
        },
    )

    normalized = captured["runtime_result"]
    assert normalized["tool_trace"][0]["tool_name"] == "get_quality_factor_bundle_tool"


@pytest.mark.asyncio
async def test_evaluate_version_production_review_falls_back_to_saved_debug_result(monkeypatch):
    spec = _build_spec()
    session = _build_session()
    version = _build_version(AgentVersionStatus.TESTING, "spec_valuation_candidate_v1_v1", 1)
    version_doc = version.model_dump(mode="json", by_alias=True)
    version_doc["debug_result"] = {
        "report": "调试报告正文",
        "symbol": "600519",
        "analysis_date": "2026-04-05",
        "raw_result": {
            "risk_report": "调试报告正文",
            "tool_trace": [{"tool_name": "get_quality_factor_bundle_tool", "success": True}],
        },
        "debug_prompt": {
            "system_prompt": "system",
            "llm_final_response": "调试报告正文",
        },
        "metadata": {
            "user_goal": "验证财报风险跟踪结果",
        },
    }
    fake_db = _FakeDb({
        SPEC_COLLECTION: _FakeCollection([spec.model_dump(mode="json", by_alias=True)]),
        SESSION_COLLECTION: _FakeCollection([session.model_dump(mode="json", by_alias=True)]),
        VERSION_COLLECTION: _FakeCollection([version_doc]),
        EVALUATION_COLLECTION: _FakeCollection([]),
    })
    svc = AgentWorkshopService(fake_db)
    captured = {}

    async def _fake_evaluate_runtime_result(_version, _spec, _runtime_result, user_feedback=""):
        del _version, _spec, user_feedback
        captured["runtime_result"] = _runtime_result
        return (
            {
                "runtime_goal_alignment": 0.8,
                "runtime_output_quality": 0.8,
                "runtime_reasoning_quality": 0.8,
                "runtime_tool_usage": 0.8,
                "runtime_prompt_quality": 0.8,
                "runtime_constraint_control": 0.8,
            },
            [],
            [],
            {"evaluation_valid": True},
        )

    monkeypatch.setattr(svc, "_evaluate_runtime_result", _fake_evaluate_runtime_result)

    await svc.evaluate_version(
        version.version_id,
        evaluation_type="production-review",
        runtime_result=None,
    )

    normalized = captured["runtime_result"]
    assert normalized["output_text"] == "调试报告正文"
    assert normalized["tool_trace"][0]["tool_name"] == "get_quality_factor_bundle_tool"
    assert normalized["user_goal"] == "验证财报风险跟踪结果"


@pytest.mark.asyncio
async def test_evaluate_version_stores_agent_builder_lesson_after_production_review(monkeypatch):
    spec = _build_spec()
    session = _build_session()
    version = _build_version(AgentVersionStatus.TESTING, "spec_valuation_candidate_v1_v1", 1)
    fake_db = _FakeDb({
        SPEC_COLLECTION: _FakeCollection([spec.model_dump(mode="json", by_alias=True)]),
        SESSION_COLLECTION: _FakeCollection([session.model_dump(mode="json", by_alias=True)]),
        VERSION_COLLECTION: _FakeCollection([version.model_dump(mode="json", by_alias=True)]),
        EVALUATION_COLLECTION: _FakeCollection([]),
    })
    svc = AgentWorkshopService(fake_db)

    class _FakeMemoryService:
        def __init__(self):
            self.calls = []

        async def store(self, messages, **kwargs):
            self.calls.append({"messages": messages, **kwargs})
            return SimpleNamespace(memory_ids=["mem_001"], facts_extracted=1, success=True, error="")

    fake_memory_service = _FakeMemoryService()

    async def _fake_evaluate_runtime_result(_version, _spec, _runtime_result, user_feedback=""):
        del _version, _spec, _runtime_result, user_feedback
        return (
            {
                "runtime_goal_alignment": 0.92,
                "runtime_output_quality": 0.9,
                "runtime_reasoning_quality": 0.88,
                "runtime_tool_usage": 0.91,
                "runtime_prompt_quality": 0.89,
                "runtime_constraint_control": 0.93,
            },
            ["缺少 tool_trace 中的关键工具调用证据。"],
            ["补齐 tool_trace 并重新发起 production-review。"],
            {
                "mode": "production-review",
                "evaluation_valid": True,
                "evaluation_status": "valid",
                "layered_review": {
                    "content_quality": {"score": 0.9, "decision": "pass", "blockers": [], "warnings": []},
                    "publish_readiness": {
                        "score": 0.62,
                        "decision": "revise",
                        "blockers": ["缺少 tool_trace 中的关键工具调用证据。"],
                        "warnings": [],
                    },
                    "blockers": ["缺少 tool_trace 中的关键工具调用证据。"],
                    "warnings": [],
                },
            },
        )

    monkeypatch.setattr(svc, "_evaluate_runtime_result", _fake_evaluate_runtime_result)
    monkeypatch.setattr("core.memory.service.get_memory_service", lambda _db=None: fake_memory_service)

    result = await svc.evaluate_version(
        version.version_id,
        evaluation_type="production-review",
        runtime_result={
            "output_text": "表面上有结果",
            "debug_prompt": {"system_prompt": "system", "tool_trace": []},
        },
    )

    assert result["evaluation"].decision == "revise"
    assert len(fake_memory_service.calls) == 1
    call = fake_memory_service.calls[0]
    assert call["user_id"] == session.user_id
    assert call["agent_id"] == "agent_builder"
    assert call["session_id"] == session.session_id
    assert call["scope"] == MemoryScope.AGENT_BUILDER_LESSON.value
    assert call["metadata"]["project_id"] == "tradingagents-cn"
    assert call["metadata"]["source"] == "agent_workshop"
    assert call["metadata"]["lesson_type"] == "evaluation_failure"
    assert call["metadata"]["object_type"] == "agent_version"
    assert call["metadata"]["object_key"] == version.version_id
    assert call["metadata"]["spec_id"] == spec.spec_id
    assert call["metadata"]["version_id"] == version.version_id
    assert call["metadata"]["template_id"] == version.prompt_template_ref["template_id"]
    assert call["metadata"]["evaluation_type"] == "production-review"
    assert call["metadata"]["success"] is False
    assert "Agent Workshop 版本" in call["messages"][0]["content"]
    assert "主要问题：缺少 tool_trace 中的关键工具调用证据。" in call["messages"][0]["content"]
    assert "修正动作：补齐 tool_trace 并重新发起 production-review。" in call["messages"][0]["content"]


def test_agent_evaluation_report_hydrates_evidence_bundle_from_legacy_details() -> None:
    report = AgentEvaluationReport(
        evaluation_id="eval_legacy_001",
        version_id="spec_valuation_candidate_v1_v1",
        evaluation_type="production-review",
        scores={"overall": 0.7},
        issues=["运行结果没有覆盖足够的核心输出字段。"],
        recommendations=[],
        details={
            "evaluation_valid": False,
            "evaluation_status": "evidence_incomplete",
            "evidence_bundle": {
                "review_mode": "evidence-first",
                "evaluation_valid": False,
                "evaluation_status": "evidence_incomplete",
                "findings": [
                    {
                        "category": "tool_usage",
                        "status": "insufficient_evidence",
                        "title": "缺少工具轨迹证据",
                        "issue": "",
                        "evidence": ["缺少 debug_prompt.tool_trace"],
                    }
                ],
                "official_issues": [],
                "insufficient_evidence": [
                    {
                        "category": "tool_usage",
                        "status": "insufficient_evidence",
                        "title": "缺少工具轨迹证据",
                        "issue": "",
                        "evidence": ["缺少 debug_prompt.tool_trace"],
                    }
                ],
                "invalid_reasons": ["缺少 required_tools 的 tool_trace 证据。"],
                "runtime_summary": {
                    "has_output_text": True,
                    "has_output_payload": True,
                    "has_debug_prompt": False,
                    "tool_trace_observed": False,
                    "required_tools": ["get_value_factor_bundle_tool"],
                    "spec_outputs": ["valuation_report"],
                },
            },
        },
        decision="revise",
    )

    assert report.evidence_bundle is not None
    assert report.evidence_bundle.evaluation_valid is False
    assert report.evidence_bundle.runtime_summary.tool_trace_observed is False
    assert report.details["evidence_bundle"]["invalid_reasons"] == ["缺少 required_tools 的 tool_trace 证据。"]


def test_agent_evaluation_report_serializes_top_level_evidence_bundle_into_details() -> None:
    bundle = AgentEvaluationEvidenceBundle(
        review_mode="evidence-first",
        evaluation_valid=True,
        evaluation_status="valid",
        findings=[
            AgentEvaluationFinding(
                category="output_coverage",
                status="confirmed_issue",
                title="核心输出字段覆盖不足",
                issue="运行结果没有覆盖足够的核心输出字段。",
                evidence=["缺少 valuation_report 摘要字段"],
            )
        ],
        official_issues=["运行结果没有覆盖足够的核心输出字段。"],
        insufficient_evidence=[],
        invalid_reasons=[],
        runtime_summary=AgentEvaluationRuntimeSummary(
            has_output_text=True,
            has_output_payload=True,
            has_debug_prompt=True,
            tool_trace_observed=True,
            required_tools=["get_value_factor_bundle_tool"],
            spec_outputs=["valuation_report"],
        ),
    )

    report = AgentEvaluationReport(
        evaluation_id="eval_model_001",
        version_id="spec_valuation_candidate_v1_v1",
        evaluation_type="production-review",
        scores={"overall": 0.82},
        issues=["运行结果没有覆盖足够的核心输出字段。"],
        recommendations=[],
        details={},
        evidence_bundle=bundle,
        decision="revise",
    )

    dumped = report.model_dump(mode="json", by_alias=True)

    assert dumped["evidence_bundle"]["official_issues"] == ["运行结果没有覆盖足够的核心输出字段。"]
    assert dumped["details"]["evidence_bundle"]["runtime_summary"]["tool_trace_observed"] is True


@pytest.mark.asyncio
async def test_create_prompt_template_binds_required_tools_with_constraints(monkeypatch):
    spec = _build_spec()
    fake_db = _FakeDb({
        "prompt_templates": _FakeCollection([]),
        "template_history": _FakeCollection([]),
    })
    svc = AgentWorkshopService(fake_db)
    captured = {}

    async def _fake_create_template(_self, _payload):
        captured["payload"] = _payload
        return SimpleNamespace(id="tpl_test_001", template_name=_payload.template_name, status=_payload.status)

    monkeypatch.setattr(
        "app.services.agent_workshop_service.PromptTemplateService.create_template",
        _fake_create_template,
    )

    await svc._create_prompt_template(
        "spec_valuation_candidate_v1_v1",
        spec,
        [
            "get_quality_factor_bundle_tool",
            "get_stock_market_data_unified",
            "get_stock_fundamentals_unified",
            "get_stock_news_unified",
        ],
    )

    payload = captured["payload"]
    tool_guidance = payload.content.tool_guidance
    constraints = payload.content.constraints

    assert "get_quality_factor_bundle_tool" in tool_guidance
    assert "get_stock_market_data_unified" in tool_guidance
    assert "get_stock_fundamentals_unified" in tool_guidance
    assert "get_stock_news_unified" in tool_guidance
    assert "当前版本绑定工具与工具使用约束是绑定在一起的" in tool_guidance
    assert "当前版本绑定工具（也是本次工具约束生效范围）" in constraints
    assert "任何未出现在当前 required_tools 中的工具，都视为本次未绑定能力" in constraints


@pytest.mark.asyncio
async def test_create_prompt_template_includes_section_level_numeric_traceability_rules(monkeypatch):
    spec = _build_spec()
    spec.primary_goal = "对A股个股进行财报多期跟踪分析，并对关键评分数字标注来源。"
    spec.constraints = [
        "所有数值必须来自工具返回，需标注数据来源。必须展示多期趋势对比。",
    ]
    fake_db = _FakeDb({
        "prompt_templates": _FakeCollection([]),
        "template_history": _FakeCollection([]),
    })
    svc = AgentWorkshopService(fake_db)
    captured = {}

    async def _fake_create_template(_self, _payload):
        captured["payload"] = _payload
        return SimpleNamespace(id="tpl_test_002", template_name=_payload.template_name, status=_payload.status)

    monkeypatch.setattr(
        "app.services.agent_workshop_service.PromptTemplateService.create_template",
        _fake_create_template,
    )

    await svc._create_prompt_template(
        "spec_nanobot_financial_report_risk_tracker_v2_v1",
        spec,
        ["get_quality_factor_bundle_tool", "get_balance_sheet_analysis"],
    )

    constraints = captured["payload"].content.constraints

    assert "关键数值必须能够追溯到来源数据、来源工具、关键输入参数或引用的上游计算结果" in constraints
    assert "允许采用表级、节级或附录级来源映射" in constraints
    assert "目标价、估值区间、排序、权重、概率等高风险精确结论" in constraints


@pytest.mark.asyncio
async def test_create_prompt_template_includes_project_memory_block(monkeypatch):
    spec = _build_spec()
    fake_db = _FakeDb({
        "prompt_templates": _FakeCollection([]),
        "template_history": _FakeCollection([]),
    })
    svc = AgentWorkshopService(fake_db)
    captured = {}

    async def _fake_create_template(_self, _payload):
        captured["payload"] = _payload
        return SimpleNamespace(id="tpl_test_003", template_name=_payload.template_name, status=_payload.status)

    monkeypatch.setattr(
        "app.services.agent_workshop_service.PromptTemplateService.create_template",
        _fake_create_template,
    )

    async def _fake_build_project_memory_block():
        return "【项目长期记忆】\n- 项目规则\n  - 禁止直接投资建议：所有分析只提供研究与学习参考。\n- 输出约束\n  - 回答结构：先给结论，再给证据和风险。"

    monkeypatch.setattr(
        svc,
        "_build_project_memory_block_for_workshop",
        _fake_build_project_memory_block,
    )

    await svc._create_prompt_template(
        "spec_valuation_candidate_v1_v1",
        spec,
        ["get_quality_factor_bundle_tool"],
    )

    system_prompt = captured["payload"].content.system_prompt
    constraints = captured["payload"].content.constraints

    assert "【项目长期记忆】" in system_prompt
    assert "禁止直接投资建议" in system_prompt
    assert "回答结构：先给结论，再给证据和风险。" in system_prompt
    assert "必须同时遵守项目长期记忆中的稳定规则" in constraints
    assert "- 输出约束" in constraints


@pytest.mark.asyncio
async def test_sync_version_required_tools_refreshes_prompt_template_and_execution_plan():
    spec = _build_spec()
    session = _build_session()
    session.gap_report = AgentWorkshopGapAnalysis(
        existing_tools=["get_balance_sheet_analysis", "analyze_a_share_dupont"],
    )
    version = _build_version(AgentVersionStatus.TESTING, "spec_valuation_candidate_v1_v1", 1)
    version.prompt_template_ref = {
        "template_id": "tpl_sync_001",
        "template_name": "旧模板",
        "status": "draft",
    }
    fake_db = _FakeDb({
        SPEC_COLLECTION: _FakeCollection([spec.model_dump(mode="json", by_alias=True)]),
        SESSION_COLLECTION: _FakeCollection([session.model_dump(mode="json", by_alias=True)]),
        VERSION_COLLECTION: _FakeCollection([version.model_dump(mode="json", by_alias=True)]),
        EVALUATION_COLLECTION: _FakeCollection([]),
        "prompt_templates": _FakeCollection([
            {
                "_id": "tpl_sync_001",
                "template_name": "旧模板",
                "status": "draft",
                "version": 1,
                "content": {
                    "system_prompt": "old system",
                    "user_prompt": "old user",
                    "tool_guidance": "- get_stock_market_data_unified\n- get_stock_news_unified",
                    "analysis_requirements": "old analysis",
                    "output_format": "old output",
                    "constraints": "old constraints",
                },
            }
        ]),
        "template_history": _FakeCollection([]),
    })
    svc = AgentWorkshopService(fake_db)

    result = await svc.sync_version_required_tools(
        version_id=version.version_id,
        required_tools=["get_balance_sheet_analysis", "analyze_a_share_dupont"],
        default_tools=["get_balance_sheet_analysis"],
        max_tool_calls=6,
    )

    saved_version = await fake_db[VERSION_COLLECTION].find_one({"version_id": version.version_id})
    saved_template = await fake_db["prompt_templates"].find_one({"_id": "tpl_sync_001"})

    assert result["required_tools"] == ["get_balance_sheet_analysis", "analyze_a_share_dupont"]
    assert saved_version["required_tools"] == ["get_balance_sheet_analysis", "analyze_a_share_dupont"]
    assert saved_version["agent_metadata"]["default_tools"] == ["get_balance_sheet_analysis"]
    assert saved_version["agent_metadata"]["max_tool_calls"] == 6
    assert saved_version["execution_plan"]["execution_steps"][1]["suggested_tools"] == [
        "get_balance_sheet_analysis",
        "analyze_a_share_dupont",
    ]
    assert "get_balance_sheet_analysis" in saved_template["content"]["tool_guidance"]
    assert "analyze_a_share_dupont" in saved_template["content"]["tool_guidance"]
    assert "get_stock_market_data_unified" not in saved_template["content"]["tool_guidance"]
    assert saved_template["version"] == 2


@pytest.mark.asyncio
async def test_build_execution_validation_plan_keeps_all_required_tools_visible():
    svc = AgentWorkshopService(_FakeDb({}))
    spec = _build_spec()
    output_schema = {"properties": {"valuation_report": {"type": "string"}}}

    plan = svc._build_execution_validation_plan(
        spec,
        [
            "get_balance_sheet_analysis",
            "get_cashflow_analysis",
            "get_income_analysis",
            "get_quality_factor_bundle_tool",
            "analyze_a_share_dupont",
        ],
        output_schema,
    )

    assert plan.execution_steps[1].suggested_tools == [
        "get_balance_sheet_analysis",
        "get_cashflow_analysis",
        "get_income_analysis",
        "get_quality_factor_bundle_tool",
        "analyze_a_share_dupont",
    ]


@pytest.mark.asyncio
async def test_build_version_for_nanobot_draft_skips_gap_analysis(monkeypatch):
    spec = _build_spec()
    spec.source = "nanobot"
    session = _build_session()
    session.stage = AgentWorkshopStage.BUILDING
    session.current_spec_snapshot = spec
    session.gap_report = None
    session.feasibility_status = "feasible"
    session.completeness_score = 1.0

    fake_db = _FakeDb({
        SPEC_COLLECTION: _FakeCollection([spec.model_dump(mode="json", by_alias=True)]),
        SESSION_COLLECTION: _FakeCollection([session.model_dump(mode="json", by_alias=True)]),
        VERSION_COLLECTION: _FakeCollection([]),
        EVALUATION_COLLECTION: _FakeCollection([]),
        "prompt_templates": _FakeCollection([]),
    })
    svc = AgentWorkshopService(fake_db)

    async def _unexpected_gap_analysis(_spec):
        raise AssertionError("Nanobot draft build should not trigger gap analysis")

    async def _fake_collect_capability_snapshot(_text):
        return {"registered_capabilities": []}

    async def _fake_create_prompt_template(_version_id, _spec, _required_tools, gap_report=None, tooling_plan=None, agent_builder_lesson_block=""):
        del gap_report, tooling_plan, agent_builder_lesson_block
        return {"template_id": "tpl_nanobot_v1", "template_name": "Nanobot 模板"}

    monkeypatch.setattr(svc, "_build_gap_analysis", _unexpected_gap_analysis)
    monkeypatch.setattr(svc, "_collect_capability_snapshot", _fake_collect_capability_snapshot)
    monkeypatch.setattr(svc, "_create_prompt_template", _fake_create_prompt_template)

    result = await svc.build_version(session.session_id)

    assert result["version"].status == AgentVersionStatus.TESTING
    saved_session = await fake_db[SESSION_COLLECTION].find_one({"session_id": session.session_id})
    assert saved_session["gap_report"] is None


@pytest.mark.asyncio
async def test_build_version_includes_agent_builder_lessons_in_prompt_template(monkeypatch):
    spec = _build_spec()
    spec.owner_user_id = "user_001"
    session = _build_session()
    session.current_spec_snapshot = spec
    session.gap_report = AgentWorkshopGapAnalysis(existing_tools=["get_peer_comparison"])
    session.feasibility_status = "feasible"
    session.completeness_score = 1.0

    fake_db = _FakeDb({
        SPEC_COLLECTION: _FakeCollection([spec.model_dump(mode="json", by_alias=True)]),
        SESSION_COLLECTION: _FakeCollection([session.model_dump(mode="json", by_alias=True)]),
        VERSION_COLLECTION: _FakeCollection([]),
        EVALUATION_COLLECTION: _FakeCollection([]),
        "prompt_templates": _FakeCollection([]),
        "template_history": _FakeCollection([]),
    })
    svc = AgentWorkshopService(fake_db)
    captured = {}

    class _FakeMemoryService:
        def __init__(self):
            self.calls = []

        async def recall_formatted(self, **kwargs):
            self.calls.append(kwargs)
            return "【历史工坊教训】\n- 上一轮缺少行业横向比较\n- 修正动作：保留 peer comparison 证据链\n"

    fake_memory_service = _FakeMemoryService()

    async def _fake_collect_capability_snapshot(_text):
        return {"registered_capabilities": []}

    async def _fake_build_project_memory_block():
        return ""

    async def _fake_create_template(_self, payload):
        captured["payload"] = payload
        return SimpleNamespace(id="tpl_build_lesson_001", template_name=payload.template_name, status=payload.status)

    monkeypatch.setattr("core.memory.service.get_memory_service", lambda _db=None: fake_memory_service)
    monkeypatch.setattr(svc, "_collect_capability_snapshot", _fake_collect_capability_snapshot)
    monkeypatch.setattr(svc, "_build_project_memory_block_for_workshop", _fake_build_project_memory_block)
    monkeypatch.setattr("app.services.agent_workshop_service.PromptTemplateService.create_template", _fake_create_template)

    result = await svc.build_version(session.session_id)

    assert result["version"].version_id == "spec_valuation_candidate_v1_v1"
    assert len(fake_memory_service.calls) == 1
    recall_call = fake_memory_service.calls[0]
    assert recall_call["user_id"] == session.user_id
    assert recall_call["agent_id"] == "agent_builder"
    assert recall_call["scopes"] == [MemoryScope.AGENT_BUILDER_LESSON.value]
    assert recall_call["metadata_filters"] == {"spec_id": spec.spec_id}
    assert recall_call["ranking_profile"] == "agent_builder"
    payload = captured["payload"]
    assert "【Agent 工坊历史教训】" in payload.content.system_prompt
    assert "上一轮缺少行业横向比较" in payload.content.system_prompt
    assert "必须结合 Agent 工坊历史教训修正上一轮或同类版本已确认的问题。" in payload.content.constraints
    assert "修正动作：保留 peer comparison 证据链" in payload.content.constraints


@pytest.mark.asyncio
async def test_recall_agent_builder_lessons_for_spec_logs_hit_observation(monkeypatch):
    spec = _build_spec()
    spec.owner_user_id = "user_001"
    svc = AgentWorkshopService(_FakeDb({}))
    captured = {}

    class _FakeMemoryService:
        async def recall_formatted(self, **kwargs):
            captured["recall_kwargs"] = dict(kwargs)
            return "【历史工坊教训】\n- 上一轮缺少行业对比证据\n"

    def _fake_log_generated_result(stage, result, context=None):
        captured["log_stage"] = stage
        captured["log_result"] = result
        captured["log_context"] = context

    monkeypatch.setattr("core.memory.service.get_memory_service", lambda _db=None: _FakeMemoryService())
    monkeypatch.setattr(svc, "_log_generated_result", _fake_log_generated_result)

    result = await svc._recall_agent_builder_lessons_for_spec(
        spec,
        user_id="user_001",
        query_text="PE PB",
        source_stage="gap_analysis",
    )

    assert "【Agent 工坊历史教训】" in result
    assert captured["log_stage"] == "agent_builder_lesson_recall_observation"
    assert captured["log_result"]["status"] == "hit"
    assert captured["log_result"]["hit"] is True
    assert captured["log_result"]["source_stage"] == "gap_analysis"
    assert captured["log_result"]["scope"] == MemoryScope.AGENT_BUILDER_LESSON.value
    assert captured["log_result"]["query_chars"] > 0
    assert captured["log_result"]["result_chars"] > 0
    assert captured["log_context"] == {
        "spec_id": spec.spec_id,
        "spec_name": spec.name,
        "user_id": "user_001",
    }


@pytest.mark.asyncio
async def test_recall_agent_builder_lessons_for_spec_logs_miss_observation(monkeypatch):
    spec = _build_spec()
    spec.owner_user_id = "user_001"
    svc = AgentWorkshopService(_FakeDb({}))
    captured = {}

    class _FakeMemoryService:
        async def recall_formatted(self, **kwargs):
            captured["recall_kwargs"] = dict(kwargs)
            return ""

    def _fake_log_generated_result(stage, result, context=None):
        captured["log_stage"] = stage
        captured["log_result"] = result
        captured["log_context"] = context

    monkeypatch.setattr("core.memory.service.get_memory_service", lambda _db=None: _FakeMemoryService())
    monkeypatch.setattr(svc, "_log_generated_result", _fake_log_generated_result)

    result = await svc._recall_agent_builder_lessons_for_spec(
        spec,
        user_id="user_001",
        query_text="valuation_report",
        source_stage="requirement_clarification",
    )

    assert result == ""
    assert captured["log_stage"] == "agent_builder_lesson_recall_observation"
    assert captured["log_result"]["status"] == "miss"
    assert captured["log_result"]["hit"] is False
    assert captured["log_result"]["source_stage"] == "requirement_clarification"
    assert captured["log_result"]["result_chars"] == 0
    assert captured["log_result"]["error"] == ""


@pytest.mark.asyncio
async def test_publish_version_requires_passed_evaluation_and_writes_runtime_config():
    spec = _build_spec()
    spec.status = AgentSpecStatus.TESTING
    spec.current_version_id = "spec_valuation_candidate_v1_v0"
    session = _build_session()
    session.stage = AgentWorkshopStage.EVALUATING
    active_version = _build_version(AgentVersionStatus.ACTIVE, "spec_valuation_candidate_v1_v0", 0)
    target_version = _build_version(AgentVersionStatus.TESTING, "spec_valuation_candidate_v1_v1", 1)

    fake_db = _FakeDb({
        SPEC_COLLECTION: _FakeCollection([spec.model_dump(mode="json", by_alias=True)]),
        SESSION_COLLECTION: _FakeCollection([session.model_dump(mode="json", by_alias=True)]),
        VERSION_COLLECTION: _FakeCollection([
            active_version.model_dump(mode="json", by_alias=True),
            target_version.model_dump(mode="json", by_alias=True),
        ]),
        EVALUATION_COLLECTION: _FakeCollection([
            AgentEvaluationReport(
                evaluation_id="eval_001",
                version_id=target_version.version_id,
                evaluation_type="production-review",
                scores={"overall": 0.91},
                issues=[],
                recommendations=["可以发布"],
                details={},
                decision="pass",
            ).model_dump(mode="json", by_alias=True)
        ]),
        "prompt_templates": _FakeCollection([
            {
                "_id": f"tpl_{target_version.version_id}",
                "template_name": "测试模板",
                "status": "draft",
                "version": 1,
                "content": {
                    "system_prompt": "system\n【项目长期记忆】\n- 项目规则\n  - 禁止直接投资建议：所有分析只提供研究与学习参考。\n- 输出约束\n  - 回答结构：先给结论，再给证据和风险。",
                    "user_prompt": "user",
                    "tool_guidance": "guidance",
                    "analysis_requirements": "analysis",
                    "output_format": "output",
                    "constraints": "constraints\n- 必须同时遵守项目长期记忆中的稳定规则、治理约束、输出约束与研究模板。",
                },
            }
        ]),
        "agent_configs": _FakeCollection([]),
    })
    svc = AgentWorkshopService(fake_db)

    async def _fake_build_project_memory_block():
        return "【项目长期记忆】\n- 项目规则\n  - 禁止直接投资建议：所有分析只提供研究与学习参考。\n- 输出约束\n  - 回答结构：先给结论，再给证据和风险。"

    svc._build_project_memory_block_for_workshop = _fake_build_project_memory_block

    result = await svc.publish_version(target_version.version_id)

    saved_target = await fake_db[VERSION_COLLECTION].find_one({"version_id": target_version.version_id})
    saved_active = await fake_db[VERSION_COLLECTION].find_one({"version_id": active_version.version_id})
    saved_spec = await fake_db[SPEC_COLLECTION].find_one({"spec_id": spec.spec_id})
    saved_session = await fake_db[SESSION_COLLECTION].find_one({"session_id": session.session_id})
    agent_config = await fake_db["agent_configs"].find_one({"agent_id": target_version.version_id})

    assert result["status"] == AgentVersionStatus.ACTIVE.value
    assert saved_target["status"] == AgentVersionStatus.ACTIVE.value
    assert saved_active["status"] == AgentVersionStatus.ARCHIVED.value
    assert saved_spec["status"] == AgentSpecStatus.ACTIVE.value
    assert saved_spec["current_version_id"] == target_version.version_id
    assert saved_session["stage"] == AgentWorkshopStage.COMPLETED.value
    assert agent_config is not None
    assert agent_config["enabled"] is True
    assert agent_config["prompt_template_type"] == "custom_agent"
    assert agent_config["prompt_template_name"] == target_version.version_id
    assert agent_config["metadata"]["source"] == "agent_workshop"
    assert agent_config["metadata"]["version_id"] == target_version.version_id
    assert agent_config["metadata"]["template_status"] == "active"
    assert agent_config["metadata"]["project_memory_binding_active"] is True
    assert agent_config["metadata"]["project_memory_binding_valid"] is True
    assert agent_config["metadata"]["version_status"] == AgentVersionStatus.ACTIVE.value
    assert agent_config["output_field"] == "valuation_report"
    assert result["project_memory_binding"]["valid"] is True

    saved_template = await fake_db["prompt_templates"].find_one({"_id": f"tpl_{target_version.version_id}"})
    assert saved_template["status"] == "active"


@pytest.mark.asyncio
async def test_publish_version_rejects_when_latest_evaluation_not_passed():
    spec = _build_spec()
    spec.status = AgentSpecStatus.TESTING
    session = _build_session()
    target_version = _build_version(AgentVersionStatus.TESTING, "spec_valuation_candidate_v1_v1", 1)

    fake_db = _FakeDb({
        SPEC_COLLECTION: _FakeCollection([spec.model_dump(mode="json", by_alias=True)]),
        SESSION_COLLECTION: _FakeCollection([session.model_dump(mode="json", by_alias=True)]),
        VERSION_COLLECTION: _FakeCollection([
            target_version.model_dump(mode="json", by_alias=True),
        ]),
        EVALUATION_COLLECTION: _FakeCollection([
            AgentEvaluationReport(
                evaluation_id="eval_fail_001",
                version_id=target_version.version_id,
                evaluation_type="production-review",
                scores={"overall": 0.42},
                issues=["输出不稳定"],
                recommendations=["重新测试"],
                details={},
                decision="revise",
            ).model_dump(mode="json", by_alias=True)
        ]),
        "agent_configs": _FakeCollection([]),
    })
    svc = AgentWorkshopService(fake_db)

    with pytest.raises(ValueError, match="真数据测试评估"):
        await svc.publish_version(target_version.version_id)


@pytest.mark.asyncio
async def test_publish_version_rejects_when_prompt_template_missing_project_memory_binding():
    spec = _build_spec()
    spec.status = AgentSpecStatus.TESTING
    target_version = _build_version(AgentVersionStatus.TESTING, "spec_valuation_candidate_v1_v1", 1)

    fake_db = _FakeDb({
        SPEC_COLLECTION: _FakeCollection([spec.model_dump(mode="json", by_alias=True)]),
        SESSION_COLLECTION: _FakeCollection([]),
        VERSION_COLLECTION: _FakeCollection([
            target_version.model_dump(mode="json", by_alias=True),
        ]),
        EVALUATION_COLLECTION: _FakeCollection([
            AgentEvaluationReport(
                evaluation_id="eval_pass_001",
                version_id=target_version.version_id,
                evaluation_type="production-review",
                scores={"overall": 0.91},
                issues=[],
                recommendations=["可以发布"],
                details={},
                decision="pass",
            ).model_dump(mode="json", by_alias=True)
        ]),
        "prompt_templates": _FakeCollection([
            {
                "_id": f"tpl_{target_version.version_id}",
                "template_name": "测试模板",
                "status": "draft",
                "version": 1,
                "content": {
                    "system_prompt": "system",
                    "user_prompt": "user",
                    "tool_guidance": "guidance",
                    "analysis_requirements": "analysis",
                    "output_format": "output",
                    "constraints": "constraints",
                },
            }
        ]),
        "agent_configs": _FakeCollection([]),
    })
    svc = AgentWorkshopService(fake_db)

    async def _fake_build_project_memory_block():
        return "【项目长期记忆】\n- 项目规则\n  - 禁止直接投资建议：所有分析只提供研究与学习参考。"

    svc._build_project_memory_block_for_workshop = _fake_build_project_memory_block

    with pytest.raises(ValueError, match="Prompt Template 尚未绑定当前 L4 项目长期记忆"):
        await svc.publish_version(target_version.version_id)


@pytest.mark.asyncio
async def test_iterate_version_keeps_same_spec_and_creates_new_session() -> None:
    spec = _build_spec()
    spec.status = AgentSpecStatus.ACTIVE
    spec.current_version_id = "spec_valuation_candidate_v1_v1"
    version = _build_version(AgentVersionStatus.ACTIVE, "spec_valuation_candidate_v1_v1", 1)
    evaluation = AgentEvaluationReport(
        evaluation_id="eval_iterate_001",
        version_id=version.version_id,
        evaluation_type="production-review",
        scores={"overall": 0.81},
        issues=["需要补充行业对比依据"],
        recommendations=["补充行业横向比较和估值解释"],
        details={},
        decision="pass",
    )

    fake_db = _FakeDb({
        SPEC_COLLECTION: _FakeCollection([spec.model_dump(mode="json", by_alias=True)]),
        SESSION_COLLECTION: _FakeCollection([]),
        VERSION_COLLECTION: _FakeCollection([version.model_dump(mode="json", by_alias=True)]),
        EVALUATION_COLLECTION: _FakeCollection([evaluation.model_dump(mode="json", by_alias=True)]),
    })
    svc = AgentWorkshopService(fake_db)

    async def _fake_analyze_requirement_turn(messages, user_id="", fallback_spec_id=None, existing_spec=None):
        assert messages and "上一轮评估识别的问题" in messages[0]
        assert user_id == spec.owner_user_id
        assert fallback_spec_id == spec.spec_id
        assert existing_spec is not None
        next_spec = existing_spec.model_copy(deep=True)
        next_spec.primary_goal = "输出更完整的行业比较和估值解释"
        return {
            "spec": next_spec,
            "pending_questions": ["这轮优先补哪类对比证据？"],
            "completeness_score": 0.92,
            "ai_message": "已基于当前已发布版本开启下一轮迭代。",
            "feasibility_status": "feasible",
            "refusal_reason": "",
        }

    svc._analyze_requirement_turn = _fake_analyze_requirement_turn

    async def _fake_create_prompt_template(version_id, _spec, _required_tools, gap_report=None, tooling_plan=None, agent_builder_lesson_block=""):
        del _spec, _required_tools, gap_report, tooling_plan, agent_builder_lesson_block
        return {"template_id": f"tpl_{version_id}", "template_name": f"模板_{version_id}", "status": "draft"}

    svc._create_prompt_template = _fake_create_prompt_template

    result = await svc.iterate_version(version.version_id, feedback="请补足行业比较依据")

    assert result["spec_id"] == spec.spec_id
    assert result["session_id"]
    assert result["version_id"] == "spec_valuation_candidate_v1_v2"
    assert len(fake_db[SESSION_COLLECTION]._items) == 1
    assert len(fake_db[VERSION_COLLECTION]._items) == 2
    stored_session = fake_db[SESSION_COLLECTION]._items[0]
    assert stored_session["spec_id"] == spec.spec_id
    assert stored_session["session_id"] == result["session_id"]
    assert stored_session["proposed_version"]["version_id"] == "spec_valuation_candidate_v1_v2"
    stored_spec = fake_db[SPEC_COLLECTION]._items[0]
    assert stored_spec["spec_id"] == spec.spec_id
    assert stored_spec["latest_session_id"] == result["session_id"]
    assert stored_spec["current_version_id"] == "spec_valuation_candidate_v1_v2"
    assert stored_spec["status"] == AgentSpecStatus.DRAFT
    stored_version = next(item for item in fake_db[VERSION_COLLECTION]._items if item["version_id"] == "spec_valuation_candidate_v1_v2")
    assert stored_version["status"] == AgentVersionStatus.DRAFT
    assert stored_version["version"] == 2


@pytest.mark.asyncio
async def test_analyze_requirement_turn_includes_agent_builder_lessons_in_prompt(monkeypatch):
    spec = _build_spec()
    spec.owner_user_id = "user_001"
    svc = AgentWorkshopService(_FakeDb({}))
    captured = {}

    class _FakeClient:
        async def achat(self, messages):
            captured["messages"] = messages
            return SimpleNamespace(content=json.dumps({
                "feasibility_status": "feasible",
                "response_message": "我先按现有需求整理成一版可执行草案。",
                "refusal_reason": "",
                "pending_questions": [],
                "completeness_score": 0.95,
                "name": spec.name,
                "domain": "stock_analysis",
                "target_users": ["投研人员"],
                "primary_goal": "输出A股估值结论",
                "responsibilities": ["输出估值结论并解释关键依据"],
                "non_goals": ["不直接给买卖建议"],
                "inputs": [{"name": "symbol", "type": "string", "required": True, "description": "股票代码"}],
                "outputs": [{"name": "valuation_report", "type": "string", "required": True, "description": "估值报告"}],
                "success_criteria": ["结论可解释且有依据"],
                "constraints": ["不直接给买卖建议"],
                "preferred_methods": ["PE"],
                "capability_requirements": [{
                    "capability_key": "peer_comparison",
                    "capability_name": "同业比较",
                    "capability_type": "data",
                    "description": "获取同业估值与财务比较依据",
                    "delivery_requirement": "tool-or-prompt",
                    "acceptance_criteria": ["能给出至少一组可解释的同行比较依据"],
                }],
                "sample_symbols": ["600519.SH"],
            }, ensure_ascii=False))

    async def _fake_collect_capability_snapshot(_text, top_k=12):
        del top_k
        return {"registered_capabilities": []}

    async def _fake_recall_agent_builder_lessons_for_spec(_spec, *, user_id="", query_text="", source_stage=""):
        captured["lesson_request"] = {
            "spec_id": _spec.spec_id,
            "user_id": user_id,
            "query_text": query_text,
            "source_stage": source_stage,
        }
        return "【Agent 工坊历史教训】\n- 之前遗漏了禁止交易建议约束\n- 修正动作：明确保留 non_goals 和 constraints"

    async def _fake_ensure_llm_client():
        return _FakeClient()

    monkeypatch.setattr(svc, "_ensure_llm_client", _fake_ensure_llm_client)
    monkeypatch.setattr(svc, "_get_llm_runtime_config", lambda _client: {})
    monkeypatch.setattr(svc, "_collect_capability_snapshot", _fake_collect_capability_snapshot)
    monkeypatch.setattr(svc, "_recall_agent_builder_lessons_for_spec", _fake_recall_agent_builder_lessons_for_spec)

    result = await svc._analyze_requirement_turn(
        ["请帮我做一个A股估值 Agent，不能直接给买卖建议。"],
        user_id="user_001",
        existing_spec=spec,
    )

    assert result["spec"].name == spec.name
    assert captured["lesson_request"]["spec_id"] == spec.spec_id
    assert captured["lesson_request"]["user_id"] == "user_001"
    prompt = captured["messages"][1].content
    assert "【Agent 工坊历史教训】" in prompt
    assert "之前遗漏了禁止交易建议约束" in prompt
    assert "避免在规格确认阶段重复过去的问题" in prompt


@pytest.mark.asyncio
async def test_build_gap_analysis_with_llm_includes_agent_builder_lessons_in_prompt(monkeypatch):
    spec = _build_spec()
    spec.owner_user_id = "user_001"
    spec.capability_requirements = []
    svc = AgentWorkshopService(_FakeDb({}))
    captured = {}

    class _FakeClient:
        async def achat(self, messages):
            captured["messages"] = messages
            return SimpleNamespace(content=json.dumps({
                "existing_tools": [],
                "suggested_tools": [],
                "suggested_capabilities": [],
                "manual_dependencies": [],
                "blocking_gaps": ["需要补充更稳定的同行比较能力封装"],
                "fallback_strategy": ["先基于现有工具做保守降级"],
                "build_recommendations": ["优先补同行比较证据链"],
                "notes": ["已结合历史 lesson 做去重判断"],
            }, ensure_ascii=False))

    async def _fake_ensure_llm_client():
        return _FakeClient()

    async def _fake_recall_agent_builder_lessons_for_spec(_spec, *, user_id="", query_text="", source_stage=""):
        captured["lesson_request"] = {
            "spec_id": _spec.spec_id,
            "user_id": user_id,
            "query_text": query_text,
            "source_stage": source_stage,
        }
        return "【Agent 工坊历史教训】\n- 上一轮误把已有能力判成新缺口\n- 修正动作：先核对合法工具清单和能力覆盖映射"

    monkeypatch.setattr(svc, "_ensure_llm_client", _fake_ensure_llm_client)
    monkeypatch.setattr(svc, "_select_gap_analysis_tool_details", lambda _spec, _snapshot: [])
    monkeypatch.setattr(svc, "_build_valuation_reuse_guidance_lines", lambda _spec, _snapshot: [])
    monkeypatch.setattr(svc, "_build_capability_coverage_map_lines", lambda _spec, _details: [])
    monkeypatch.setattr(svc, "_recall_agent_builder_lessons_for_spec", _fake_recall_agent_builder_lessons_for_spec)
    svc._llm_client_meta = {"provider": "fake", "model": "fake-model", "timeout": 60}

    result = await svc._build_gap_analysis_with_llm(spec, {"registered_capabilities": []})

    assert result.generated_by == "llm"
    assert captured["lesson_request"]["spec_id"] == spec.spec_id
    assert captured["lesson_request"]["user_id"] == "user_001"
    prompt = captured["messages"][1].content
    assert "【Agent 工坊历史教训】" in prompt
    assert "上一轮误把已有能力判成新缺口" in prompt
    assert "不要在缺口分析阶段再次提出已经被证伪的补法" in prompt


@pytest.mark.asyncio
async def test_clone_prompt_template_for_iteration_includes_agent_builder_lessons(monkeypatch):
    spec = _build_spec()
    spec.owner_user_id = "user_001"
    session = _build_session()
    version = _build_version(AgentVersionStatus.TESTING, "spec_valuation_candidate_v1_v1", 1)
    fake_db = _FakeDb({
        SPEC_COLLECTION: _FakeCollection([spec.model_dump(mode="json", by_alias=True)]),
        SESSION_COLLECTION: _FakeCollection([session.model_dump(mode="json", by_alias=True)]),
        VERSION_COLLECTION: _FakeCollection([version.model_dump(mode="json", by_alias=True)]),
        EVALUATION_COLLECTION: _FakeCollection([
            AgentEvaluationReport(
                evaluation_id="eval_iter_lesson_001",
                version_id=version.version_id,
                evaluation_type="production-review",
                scores={"overall": 0.52},
                issues=["缺少行业对比证据"],
                recommendations=["补充行业横向比较和估值解释"],
                details={},
                decision="revise",
            ).model_dump(mode="json", by_alias=True)
        ]),
        "prompt_templates": _FakeCollection([]),
        "template_history": _FakeCollection([]),
    })
    svc = AgentWorkshopService(fake_db)
    captured = {}

    class _FakeMemoryService:
        def __init__(self):
            self.calls = []

        async def recall_formatted(self, **kwargs):
            self.calls.append(kwargs)
            return "【历史工坊教训】\n- 上一轮在行业对比证据上不足\n- 修正动作：补充行业横向比较和估值解释\n"

    fake_memory_service = _FakeMemoryService()

    async def _fake_get_template(_self, template_id):
        assert template_id == version.prompt_template_ref["template_id"]
        return SimpleNamespace(
            agent_type="custom_agent",
            content=TemplateContent(
                system_prompt="你是估值分析师。",
                user_prompt="user",
                tool_guidance="guidance",
                analysis_requirements="analysis",
                output_format="output",
                constraints="- 原始约束",
            ),
        )

    async def _fake_create_template(_self, payload):
        captured["payload"] = payload
        return SimpleNamespace(id="tpl_iter_clone_001", template_name=payload.template_name, status=payload.status)

    monkeypatch.setattr("core.memory.service.get_memory_service", lambda _db=None: fake_memory_service)
    monkeypatch.setattr("app.services.agent_workshop_service.PromptTemplateService.get_template", _fake_get_template)
    monkeypatch.setattr("app.services.agent_workshop_service.PromptTemplateService.create_template", _fake_create_template)

    result = await svc._clone_prompt_template_for_iteration(
        version,
        spec,
        "spec_valuation_candidate_v1_v2",
    )

    assert result["template_id"] == "tpl_iter_clone_001"
    assert len(fake_memory_service.calls) == 1
    recall_call = fake_memory_service.calls[0]
    assert recall_call["user_id"] == session.user_id
    assert recall_call["agent_id"] == "agent_builder"
    assert recall_call["scopes"] == [MemoryScope.AGENT_BUILDER_LESSON.value]
    assert recall_call["metadata_filters"] == {"spec_id": spec.spec_id}
    assert recall_call["ranking_profile"] == "agent_builder"
    assert "缺少行业对比证据" in recall_call["query"]
    payload = captured["payload"]
    assert "【Agent 工坊历史教训】" in payload.content.system_prompt
    assert "上一轮在行业对比证据上不足" in payload.content.system_prompt
    assert "必须结合 Agent 工坊历史教训修正上一轮或同类版本已确认的问题。" in payload.content.constraints
    assert "修正动作：补充行业横向比较和估值解释" in payload.content.constraints


@pytest.mark.asyncio
async def test_build_version_reuses_iterated_draft_version(monkeypatch):
    spec = _build_spec()
    spec.status = AgentSpecStatus.DRAFT
    spec.current_version_id = "spec_valuation_candidate_v1_v2"
    spec.version_count = 2

    draft_version = _build_version(AgentVersionStatus.DRAFT, "spec_valuation_candidate_v1_v2", 2)
    draft_version.published_from_session_id = "session_iter_001"
    session = _build_session()
    session.session_id = "session_iter_001"
    session.spec_id = spec.spec_id
    session.current_spec_snapshot = spec
    session.proposed_version = draft_version.model_dump(mode="json", by_alias=True)

    fake_db = _FakeDb({
        SPEC_COLLECTION: _FakeCollection([spec.model_dump(mode="json", by_alias=True)]),
        SESSION_COLLECTION: _FakeCollection([session.model_dump(mode="json", by_alias=True)]),
        VERSION_COLLECTION: _FakeCollection([draft_version.model_dump(mode="json", by_alias=True)]),
        EVALUATION_COLLECTION: _FakeCollection([]),
        "prompt_templates": _FakeCollection([]),
    })
    svc = AgentWorkshopService(fake_db)

    async def _unexpected_gap_analysis(_spec):
        raise AssertionError("Nanobot draft build should not trigger gap analysis")

    async def _fake_collect_capability_snapshot(_text):
        return {"registered_capabilities": []}

    async def _fake_upsert_version_prompt_template(_version, _spec, _content):
        return {"template_id": "tpl_iter_v2", "template_name": "迭代模板 v2", "status": "draft"}

    monkeypatch.setattr(svc, "_build_gap_analysis", _unexpected_gap_analysis)
    monkeypatch.setattr(svc, "_collect_capability_snapshot", _fake_collect_capability_snapshot)
    monkeypatch.setattr(svc, "_upsert_version_prompt_template", _fake_upsert_version_prompt_template)

    result = await svc.build_version(session.session_id)

    assert result["version"].version_id == "spec_valuation_candidate_v1_v2"
    assert result["version"].version == 2
    assert result["version"].status == AgentVersionStatus.TESTING
    assert len(fake_db[VERSION_COLLECTION]._items) == 1
    saved_version = fake_db[VERSION_COLLECTION]._items[0]
    assert saved_version["version_id"] == "spec_valuation_candidate_v1_v2"
    assert saved_version["status"] == AgentVersionStatus.TESTING


    def test_load_json_response_repairs_unescaped_quotes_in_llm_review() -> None:
        svc = AgentWorkshopService(_FakeDb({}))
        raw_content = '''{
      "summary": "用户反馈声称"已补充绑定"，但版本信息仍未体现。",
      "scores": {
        "runtime_goal_alignment": 0.25,
        "runtime_output_quality": 0.65,
        "runtime_reasoning_quality": 0.70,
        "runtime_tool_usage": 0.40,
        "runtime_prompt_quality": 0.70,
        "runtime_constraint_control": 0.85
      },
      "dimensions": {},
      "issues": [],
      "recommendations": []
    }'''

        data = svc._load_json_response(raw_content)

        assert data["summary"] == '用户反馈声称"已补充绑定"，但版本信息仍未体现。'


@pytest.mark.asyncio
async def test_evaluate_version_records_project_memory_binding_summary(monkeypatch):
    spec = _build_spec()
    session = _build_session()
    version = _build_version(AgentVersionStatus.DRAFT, "spec_valuation_candidate_v1_v1", 1)
    fake_db = _FakeDb({
        SPEC_COLLECTION: _FakeCollection([spec.model_dump(mode="json", by_alias=True)]),
        SESSION_COLLECTION: _FakeCollection([session.model_dump(mode="json", by_alias=True)]),
        VERSION_COLLECTION: _FakeCollection([version.model_dump(mode="json", by_alias=True)]),
        EVALUATION_COLLECTION: _FakeCollection([]),
    })
    svc = AgentWorkshopService(fake_db)

    async def _fake_evaluate_runtime_result(_version, _spec, _runtime_result, user_feedback=""):
        del _version, _spec, _runtime_result, user_feedback
        return (
            {
                "runtime_goal_alignment": 0.9,
                "runtime_output_quality": 0.85,
                "runtime_reasoning_quality": 0.84,
                "runtime_tool_usage": 0.86,
                "runtime_prompt_quality": 0.72,
                "runtime_constraint_control": 0.9,
            },
            [],
            ["补齐 runtime system_prompt 证据。"],
            {
                "evaluation_valid": False,
                "evaluation_status": "evidence_incomplete",
                "project_memory_binding": {
                    "enabled": True,
                    "valid": False,
                    "system_prompt_present": False,
                    "marker_present": False,
                    "expected_items": 2,
                    "matched_items": 0,
                    "missing_items": ["缺少 runtime_result.debug_prompt.system_prompt"],
                },
                "layered_review": {
                    "content_quality": {"score": 0.88, "decision": "pass", "blockers": [], "warnings": []},
                    "publish_readiness": {
                        "score": 0.56,
                        "decision": "revise",
                        "blockers": ["缺少 runtime system_prompt 证据，无法确认当前 L4 项目长期记忆是否真实注入。"],
                        "warnings": [],
                    },
                    "blockers": ["缺少 runtime system_prompt 证据，无法确认当前 L4 项目长期记忆是否真实注入。"],
                    "warnings": [],
                },
                "evidence_bundle": {
                    "review_mode": "evidence-first",
                    "evaluation_valid": False,
                    "evaluation_status": "evidence_incomplete",
                    "invalid_reasons": ["缺少 runtime system_prompt 证据，无法确认当前 L4 项目长期记忆是否真实注入。"],
                    "runtime_summary": {
                        "has_system_prompt": False,
                        "project_memory_binding_enabled": True,
                        "project_memory_binding_valid": False,
                    },
                    "orchestrator": {
                        "mode": "evidence-first",
                        "worker_execution_mode": "rules-primary",
                        "nanobot_worker_enabled": False,
                        "planned_task_count": 0,
                        "completed_worker_count": 0,
                    },
                },
            },
        )

    monkeypatch.setattr(svc, "_evaluate_runtime_result", _fake_evaluate_runtime_result)

    result = await svc.evaluate_version(
        version.version_id,
        evaluation_type="production-review",
        runtime_result={"output_text": "仅用于测试摘要写回。"},
    )

    saved_evaluation = fake_db[EVALUATION_COLLECTION]._items[0]
    summary = result["evaluation"].details["project_memory_binding_summary"]

    assert summary["review_status"] == "evidence_incomplete"
    assert summary["missing_item_count"] == 1
    assert saved_evaluation["details"]["project_memory_binding_summary"]["review_status"] == "evidence_incomplete"
    assert saved_evaluation["details"]["evaluation_summary"]["project_memory_binding"]["review_status"] == "evidence_incomplete"


@pytest.mark.asyncio
async def test_list_evaluations_exposes_project_memory_binding_summary():
    report = AgentEvaluationReport(
        evaluation_id="eval_l4_001",
        version_id="spec_valuation_candidate_v1_v1",
        evaluation_type="production-review",
        scores={"overall": 0.61},
        issues=["运行时 system_prompt 没有完整包含当前 L4 项目长期记忆。"],
        recommendations=["重新使用当前 L4 项目长期记忆刷新版本模板。"],
        details={
            "evaluation_valid": True,
            "evaluation_status": "valid",
            "project_memory_binding": {
                "enabled": True,
                "valid": False,
                "system_prompt_present": True,
                "marker_present": False,
                "expected_items": 3,
                "matched_items": 1,
                "missing_items": ["- 项目规则", "- 禁止直接投资建议：所有分析只提供研究与学习参考。"],
            },
            "layered_review": {
                "content_quality": {"score": 0.82, "decision": "pass_with_warnings"},
                "publish_readiness": {"score": 0.61, "decision": "revise"},
            },
            "evidence_bundle": {
                "review_mode": "evidence-first",
                "evaluation_valid": True,
                "evaluation_status": "valid",
                "runtime_summary": {
                    "has_system_prompt": True,
                    "project_memory_binding_enabled": True,
                    "project_memory_binding_valid": False,
                },
                "orchestrator": {
                    "mode": "evidence-first",
                    "worker_execution_mode": "nanobot-assisted",
                    "nanobot_worker_enabled": True,
                    "planned_task_count": 1,
                    "completed_worker_count": 1,
                },
            },
        },
        decision="revise",
    )
    fake_db = _FakeDb({
        EVALUATION_COLLECTION: _FakeCollection([report.model_dump(mode="json", by_alias=True)]),
    })
    svc = AgentWorkshopService(fake_db)

    result = await svc.list_evaluations("spec_valuation_candidate_v1_v1")

    item = result["items"][0]
    assert item["project_memory_binding_summary"]["review_status"] == "failed"
    assert item["project_memory_binding_summary"]["missing_item_count"] == 2
    assert item["evaluation_summary"]["worker_execution_mode"] == "nanobot-assisted"
    assert item["evaluation_summary"]["project_memory_binding"]["review_status"] == "failed"


@pytest.mark.asyncio
async def test_get_version_includes_project_memory_and_last_evaluation_summaries(monkeypatch):
    version = _build_version(AgentVersionStatus.TESTING, "spec_valuation_candidate_v1_v1", 1)
    report = AgentEvaluationReport(
        evaluation_id="eval_l4_latest",
        version_id=version.version_id,
        evaluation_type="production-review",
        scores={"overall": 0.93},
        issues=[],
        recommendations=["可以发布。"],
        details={
            "evaluation_valid": True,
            "evaluation_status": "valid",
            "project_memory_binding": {
                "enabled": True,
                "valid": True,
                "system_prompt_present": True,
                "marker_present": True,
                "expected_items": 2,
                "matched_items": 2,
                "missing_items": [],
            },
            "layered_review": {
                "content_quality": {"score": 0.9, "decision": "pass"},
                "publish_readiness": {"score": 0.94, "decision": "pass"},
            },
            "evidence_bundle": {
                "review_mode": "evidence-first",
                "evaluation_valid": True,
                "evaluation_status": "valid",
                "runtime_summary": {
                    "has_system_prompt": True,
                    "project_memory_binding_enabled": True,
                    "project_memory_binding_valid": True,
                },
                "orchestrator": {
                    "mode": "evidence-first",
                    "worker_execution_mode": "rules-primary",
                    "nanobot_worker_enabled": False,
                    "planned_task_count": 0,
                    "completed_worker_count": 0,
                },
            },
        },
        decision="pass",
    )
    fake_db = _FakeDb({
        VERSION_COLLECTION: _FakeCollection([version.model_dump(mode="json", by_alias=True)]),
        EVALUATION_COLLECTION: _FakeCollection([report.model_dump(mode="json", by_alias=True)]),
        "prompt_templates": _FakeCollection([
            {
                "_id": f"tpl_{version.version_id}",
                "template_name": "测试模板",
                "status": "draft",
                "content": {
                    "system_prompt": "你是估值分析师。\n【项目长期记忆】\n- 项目规则\n- 禁止直接投资建议：所有分析只提供研究与学习参考。",
                    "constraints": "- 必须同时遵守项目长期记忆中的稳定规则。\n- 项目规则\n- 禁止直接投资建议：所有分析只提供研究与学习参考。",
                },
            }
        ]),
    })
    svc = AgentWorkshopService(fake_db)

    async def _fake_build_project_memory_block():
        return "【项目长期记忆】\n- 项目规则\n- 禁止直接投资建议：所有分析只提供研究与学习参考。"

    monkeypatch.setattr(svc, "_build_project_memory_block_for_workshop", _fake_build_project_memory_block)

    result = await svc.get_version(version.version_id)

    assert result["prompt_template_project_memory_binding_summary"]["review_status"] == "pass"
    assert result["prompt_template_project_memory_binding_summary"]["matched_items"] == 2
    assert result["last_evaluation_summary"]["decision"] == "pass"
    assert result["last_evaluation_summary"]["project_memory_binding"]["review_status"] == "pass"


@pytest.mark.asyncio
async def test_list_versions_includes_project_memory_and_last_evaluation_summaries(monkeypatch):
    version = _build_version(AgentVersionStatus.TESTING, "spec_valuation_candidate_v1_v1", 1)
    report = AgentEvaluationReport(
        evaluation_id="eval_l4_versions_latest",
        version_id=version.version_id,
        evaluation_type="production-review",
        scores={"overall": 0.88},
        issues=[],
        recommendations=["继续观察。"],
        details={
            "evaluation_valid": True,
            "evaluation_status": "valid",
            "project_memory_binding": {
                "enabled": True,
                "valid": True,
                "system_prompt_present": True,
                "marker_present": True,
                "expected_items": 2,
                "matched_items": 2,
                "missing_items": [],
            },
            "layered_review": {
                "content_quality": {"score": 0.86, "decision": "pass"},
                "publish_readiness": {"score": 0.89, "decision": "pass"},
            },
            "evidence_bundle": {
                "review_mode": "evidence-first",
                "evaluation_valid": True,
                "evaluation_status": "valid",
                "runtime_summary": {
                    "has_system_prompt": True,
                    "project_memory_binding_enabled": True,
                    "project_memory_binding_valid": True,
                },
                "orchestrator": {
                    "mode": "evidence-first",
                    "worker_execution_mode": "rules-primary",
                    "nanobot_worker_enabled": False,
                    "planned_task_count": 0,
                    "completed_worker_count": 0,
                },
            },
        },
        decision="pass",
    )
    fake_db = _FakeDb({
        VERSION_COLLECTION: _FakeCollection([version.model_dump(mode="json", by_alias=True)]),
        EVALUATION_COLLECTION: _FakeCollection([report.model_dump(mode="json", by_alias=True)]),
        "prompt_templates": _FakeCollection([
            {
                "_id": f"tpl_{version.version_id}",
                "template_name": "测试模板",
                "status": "draft",
                "content": {
                    "system_prompt": "你是估值分析师。\n【项目长期记忆】\n- 项目规则\n- 禁止直接投资建议：所有分析只提供研究与学习参考。",
                    "constraints": "- 必须同时遵守项目长期记忆中的稳定规则。\n- 项目规则\n- 禁止直接投资建议：所有分析只提供研究与学习参考。",
                },
            }
        ]),
    })
    svc = AgentWorkshopService(fake_db)

    async def _fake_build_project_memory_block():
        return "【项目长期记忆】\n- 项目规则\n- 禁止直接投资建议：所有分析只提供研究与学习参考。"

    monkeypatch.setattr(svc, "_build_project_memory_block_for_workshop", _fake_build_project_memory_block)

    result = await svc.list_versions(spec_id=version.spec_id)

    item = result["items"][0]
    assert item["prompt_template_project_memory_binding_summary"]["review_status"] == "pass"
    assert item["prompt_template_project_memory_binding_summary"]["matched_items"] == 2
    assert item["last_evaluation_summary"]["decision"] == "pass"
    assert item["last_evaluation_summary"]["project_memory_binding"]["review_status"] == "pass"