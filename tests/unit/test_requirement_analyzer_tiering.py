# -*- coding: utf-8 -*-
"""需求对话模型分级与回退逻辑测试。

背景：Skill 需求沟通阶段的清晰度评估/边界检测/多轮对话回复/规格生成
原全部走深度推理模型（思考型，单次分钟级），导致首轮响应 20+ 分钟、
规格预览 10+ 分钟。分级后：轻推理环节（对话回复/规格生成）优先走快速
模型，快速模型不可用时回退主模型；侦察无字段级实证事实时跳过二次
规格生成（external_api 模式侦察不探测外部接口，二次生成无增量）。
"""
import asyncio
import json
from types import SimpleNamespace

from core.llm import Message
from core.tools.external.requirement_analyzer import (
    ClarityLevel,
    RequirementAnalyzer,
)
from core.tools.external.skill_spec import (
    ImplementationFactReport,
    ImplementationHelper,
    SkillSpec,
)


class _FakeClient:
    """记录调用次数的假 LLM 客户端"""

    def __init__(self, content: str = "ok", raise_exc: Exception | None = None):
        self._content = content
        self._raise = raise_exc
        self.calls = 0

    def chat(self, messages):
        self.calls += 1
        if self._raise:
            raise self._raise
        return SimpleNamespace(content=self._content)


def _analyzer(main=None, quick=None) -> RequirementAnalyzer:
    return RequirementAnalyzer(
        llm_client=main if main is not None else _FakeClient("main-reply"),
        quick_llm_client=quick,
    )


# ---------- _chat_with_quick_fallback ----------

def test_quick_fallback_uses_quick_when_ok():
    quick, main = _FakeClient("quick-reply"), _FakeClient("main-reply")
    analyzer = _analyzer(main, quick)

    out = analyzer._chat_with_quick_fallback(
        [Message(role="user", content="hi")], stage="测试"
    )

    assert out == "quick-reply"
    assert quick.calls == 1
    assert main.calls == 0


def test_quick_fallback_on_exception():
    quick = _FakeClient(raise_exc=RuntimeError("Error code: 403 - AccountOverdueError"))
    main = _FakeClient("main-reply")
    analyzer = _analyzer(main, quick)

    out = analyzer._chat_with_quick_fallback(
        [Message(role="user", content="hi")], stage="测试"
    )

    assert out == "main-reply"
    assert main.calls == 1


def test_quick_fallback_on_empty_content():
    quick, main = _FakeClient("   "), _FakeClient("main-reply")
    analyzer = _analyzer(main, quick)

    out = analyzer._chat_with_quick_fallback(
        [Message(role="user", content="hi")], stage="测试"
    )

    assert out == "main-reply"
    assert main.calls == 1


def test_quick_fallback_without_quick_client():
    main = _FakeClient("main-reply")
    analyzer = _analyzer(main, quick=None)

    assert analyzer._get_quick_client() is None
    out = analyzer._chat_with_quick_fallback(
        [Message(role="user", content="hi")], stage="测试"
    )

    assert out == "main-reply"
    assert main.calls == 1


# ---------- 轻判断路由 ----------

def test_assess_clarity_uses_quick_model():
    quick, main = _FakeClient("5"), _FakeClient("3")
    analyzer = _analyzer(main, quick)

    level = analyzer._assess_clarity("获取懂车帝月度销量数据")

    assert level == ClarityLevel.HIGH
    assert quick.calls == 1
    assert main.calls == 0


def test_assess_clarity_degrades_to_medium_on_quick_failure():
    quick = _FakeClient(raise_exc=RuntimeError("Error code: 403"))
    main = _FakeClient("3")
    analyzer = _analyzer(main, quick)

    level = analyzer._assess_clarity("获取数据")

    # 快模型失败时快速降级为 MEDIUM，不回退主模型（避免又等几分钟）
    assert level == ClarityLevel.MEDIUM
    assert main.calls == 0


def test_check_boundary_uses_quick_model():
    quick = _FakeClient(
        '{"within_boundary": true, "complexity_score": 1,'
        ' "concerns": [], "decomposition_suggestions": []}'
    )
    main = _FakeClient("{}")
    analyzer = _analyzer(main, quick)

    check = analyzer._check_boundary("获取懂车帝销量")

    assert check.within_boundary is True
    assert quick.calls == 1
    assert main.calls == 0


# ---------- 对话回复路由 ----------

def test_round1_response_uses_quick_model():
    quick, main = _FakeClient("第1轮快速回复"), _FakeClient("第1轮主模型回复")
    analyzer = _analyzer(main, quick)
    session = analyzer.create_session()

    out = analyzer._build_round1_response(session, "获取懂车帝月度销量")

    assert out == "第1轮快速回复"
    assert quick.calls == 1
    assert main.calls == 0


def test_round1_response_falls_back_to_main():
    quick = _FakeClient(raise_exc=TimeoutError("Request timed out."))
    main = _FakeClient("第1轮主模型回复")
    analyzer = _analyzer(main, quick)
    session = analyzer.create_session()

    out = analyzer._build_round1_response(session, "获取懂车帝月度销量")

    assert out == "第1轮主模型回复"
    assert quick.calls == 1
    assert main.calls == 1


def test_spec_confirmation_uses_quick_model():
    quick, main = _FakeClient("规格确认快速回复"), _FakeClient("主模型")
    analyzer = _analyzer(main, quick)
    session = analyzer.create_session()

    out = analyzer._build_spec_confirmation(session, "确认")

    assert out == "规格确认快速回复"
    assert quick.calls == 1
    assert main.calls == 0


# ---------- 规格生成路由 ----------

_SPEC_JSON = json.dumps({
    "tool_id": "get_dongchedi_sales",
    "display_name": "懂车帝销量",
    "description": "获取懂车帝车型月销量",
    "category": "utility",
    "data_source": "dongchedi",
    "parameters": [],
    "expected_output": {
        "type": "list[dict]", "fields": ["rank", "model_name"], "description": "销量列表",
    },
    "validation_checks": [],
    "constraints": [],
    "test_input": {},
}, ensure_ascii=False)


def test_generate_spec_uses_quick_model():
    quick, main = _FakeClient(_SPEC_JSON), _FakeClient(_SPEC_JSON)
    analyzer = _analyzer(main, quick)

    spec = analyzer._generate_spec("用户想获取懂车帝月度销量数据")

    assert spec is not None
    assert spec.tool_id == "get_dongchedi_sales"
    assert quick.calls == 1
    assert main.calls == 0


def test_generate_spec_falls_back_to_main_on_quick_failure():
    quick = _FakeClient(raise_exc=RuntimeError("Error code: 403 - AccountOverdueError"))
    main = _FakeClient(_SPEC_JSON)
    analyzer = _analyzer(main, quick)

    spec = analyzer._generate_spec("用户想获取懂车帝月度销量数据")

    assert spec is not None
    assert spec.tool_id == "get_dongchedi_sales"
    assert main.calls == 1


# ---------- 侦察事实判断与二次生成跳过 ----------

def test_fact_report_grounding_flag():
    assert ImplementationFactReport().has_spec_grounding_facts is False
    report = ImplementationFactReport(
        available_helpers=[ImplementationHelper(name="get_stock_news")]
    )
    assert report.has_spec_grounding_facts is True


class _StubAnalyzer:
    """记录 preview_spec 调用（含 fact_report 入参）的桩"""

    def __init__(self, spec):
        self._spec = spec
        self.preview_calls = []

    def preview_spec(self, session, user_message, fact_report=None, parent_contract=None):
        self.preview_calls.append(fact_report)
        return self._spec


class _StubRecon:
    def __init__(self, report):
        self._report = report

    def analyze(self, spec, capability_hits):
        return self._report


def _make_preview_service(draft_spec, fact_report):
    """构造只挂载 preview_spec 依赖桩的服务（绕过重量级构造器）"""
    from app.services.skill_generation_service import SkillGenerationService

    service = SkillGenerationService.__new__(SkillGenerationService)
    stub = _StubAnalyzer(draft_spec)
    service._analyzer = stub
    service._reconnaissance = _StubRecon(fact_report)

    session = RequirementAnalyzer().create_session()

    async def _load(session_id):
        return session

    async def _save(s):
        pass

    async def _search(spec):
        return []

    service._load_session = _load
    service._save_session = _save
    service._search_capability_index = _search
    service._apply_handoff_context_to_spec = lambda spec, ctx: None
    service._build_session_recommendations = lambda **kw: {}
    return service, stub


def test_preview_spec_skips_second_pass_in_external_mode():
    draft = SkillSpec(
        tool_id="get_dongchedi_sales",
        display_name="懂车帝销量",
        description="通过公开接口获取懂车帝车型月销量",
        data_source="dongchedi",
    )
    # 即便报告带 helper 条目，external_api 模式侦察不探测外部接口，也应跳过
    report = ImplementationFactReport(
        available_helpers=[ImplementationHelper(name="x")],
        recommended_strategy="外部API集成",
        confidence=0.45,
    )
    service, stub = _make_preview_service(draft, report)

    result = asyncio.run(service.preview_spec("s1", "确认"))

    assert len(stub.preview_calls) == 1
    assert stub.preview_calls[0] is None  # 草稿遍无 fact_report
    assert result["spec"]["tool_id"] == "get_dongchedi_sales"


def test_preview_spec_runs_second_pass_with_grounding_facts():
    draft = SkillSpec(
        tool_id="get_stock_news",
        display_name="个股新闻",
        description="获取个股新闻列表",
        data_source="akshare",
    )
    report = ImplementationFactReport(
        available_helpers=[ImplementationHelper(name="get_stock_news")]
    )
    service, stub = _make_preview_service(draft, report)

    asyncio.run(service.preview_spec("s1", "确认"))

    assert len(stub.preview_calls) == 2
    assert stub.preview_calls[1] is report


def test_preview_spec_skips_second_pass_without_grounding_facts():
    draft = SkillSpec(
        tool_id="get_stock_news",
        display_name="个股新闻",
        description="获取个股新闻列表",
        data_source="akshare",
    )
    report = ImplementationFactReport(recommended_strategy="本地集合优先", confidence=0.3)
    service, stub = _make_preview_service(draft, report)

    asyncio.run(service.preview_spec("s1", "确认"))

    assert len(stub.preview_calls) == 1
