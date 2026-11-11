"""可靠性达标专项防退化锚点（reliability-standards.md §6 验收 1-4）。

锚定 R1（LLM 重试一致）/ R2+R4（失败形态统一、占位不混入）/ R3（降级跳过判定）
/ U3（报告降级声明段）/ U4（占位文本不判成功）五组行为，防再次静默退化。
"""

from types import SimpleNamespace

import pytest

from core.agents.base import GENERIC_REPORT_FALLBACK, BaseAgent
from core.agents.config import AgentCategory, AgentConfig, AgentMetadata
from core.agents.adapters.flow_context import (
    all_degraded,
    is_degraded_placeholder,
    safe_extract,
)
from core.workflow.engine import WorkflowEngine


# ---------------------------------------------------------------------------
# R1：_invoke_llm_with_trace 与 invoke_with_tools 重试行为一致（3 次指数退避）
# ---------------------------------------------------------------------------

class _FakeLLM:
    """前 fail_times 次抛可重试错误，之后返回响应。"""

    def __init__(self, fail_times: int, error: Exception):
        self.fail_times = fail_times
        self.error = error
        self.calls = 0

    def invoke(self, messages):
        self.calls += 1
        if self.calls <= self.fail_times:
            raise self.error
        return SimpleNamespace(content="ok")


class _DummyAgent(BaseAgent):
    metadata = AgentMetadata(
        id="reliability_dummy",
        name="可靠性锚点假人",
        description="测试用",
        category=AgentCategory.ANALYST,
    )

    def execute(self, state):
        return state


def _make_agent(llm, max_retries: int = 3) -> _DummyAgent:
    return _DummyAgent(config=AgentConfig(max_retries=max_retries), llm=llm)


@pytest.fixture(autouse=True)
def _no_sleep(monkeypatch):
    monkeypatch.setattr("core.agents.base.time.sleep", lambda *_: None)


def test_r1_retryable_error_retries_then_succeeds():
    llm = _FakeLLM(fail_times=2, error=ConnectionError("connection reset by peer"))
    agent = _make_agent(llm)
    response = agent._invoke_llm_with_trace([])
    assert response.content == "ok"
    assert llm.calls == 3  # 2 次失败 + 1 次成功


def test_r1_retry_exhausted_raises_after_max_retries():
    llm = _FakeLLM(fail_times=99, error=TimeoutError("request timed out"))
    agent = _make_agent(llm, max_retries=3)
    with pytest.raises(TimeoutError):
        agent._invoke_llm_with_trace([])
    assert llm.calls == 4  # 首次 + 3 次重试


def test_r1_non_retryable_error_raises_immediately():
    llm = _FakeLLM(fail_times=99, error=ValueError("invalid model name"))
    agent = _make_agent(llm)
    with pytest.raises(ValueError):
        agent._invoke_llm_with_trace([])
    assert llm.calls == 1  # 不可重试错误不消耗重试


# ---------------------------------------------------------------------------
# R2 + R4：失败形态统一，占位/error dict 不混入下游推理
# ---------------------------------------------------------------------------

def test_r2_placeholder_forms_recognized_as_degraded():
    assert is_degraded_placeholder(None) is True
    assert is_degraded_placeholder("") is True
    assert is_degraded_placeholder(GENERIC_REPORT_FALLBACK) is True
    assert is_degraded_placeholder({"error": "boom"}) is True
    assert is_degraded_placeholder({"content": GENERIC_REPORT_FALLBACK}) is True
    assert is_degraded_placeholder("工具执行未完成，无法给出结论") is True


def test_r2_real_report_not_treated_as_degraded():
    assert is_degraded_placeholder("牧原股份 2026Q3 出栏量环比 +5%（来源：公司公告）") is False
    assert is_degraded_placeholder({"content": "真实报告内容"}) is False
    # 长报告正文含「待验证/未完成」等词不得误判为降级（占位关键词仅匹配短文本）
    long_report = "产能去化尚未完成，能繁存栏去化仍待验证。" * 10
    assert is_degraded_placeholder(long_report) is False


def test_r4_safe_extract_never_leaks_placeholder_or_error_dict():
    assert safe_extract(GENERIC_REPORT_FALLBACK) == ""
    assert safe_extract({"error": "connection refused"}) == ""
    assert safe_extract(None) == ""
    assert safe_extract({"content": "真实内容"}) == "真实内容"
    assert safe_extract("真实内容") == "真实内容"
    # error dict 的 str() 形态绝不出现在返回值里
    assert "error" not in safe_extract({"error": "connection refused"})


# ---------------------------------------------------------------------------
# R3：关键产出全部降级 → 下游跳过判定
# ---------------------------------------------------------------------------

def test_r3_all_degraded_requires_every_field_degraded():
    state = {"bull_report": GENERIC_REPORT_FALLBACK, "bear_report": "有效观点"}
    assert all_degraded(state, ["bull_report", "bear_report"]) is False

    state = {"bull_report": GENERIC_REPORT_FALLBACK, "bear_report": {"error": "x"}}
    assert all_degraded(state, ["bull_report", "bear_report"]) is True

    assert all_degraded(None, ["a"]) is True


# ---------------------------------------------------------------------------
# U4：降级占位不判 success（engine 结构化产出）
# ---------------------------------------------------------------------------

def _field_info(field: str) -> dict:
    return {
        "field": field,
        "display_name": field,
        "category": "analysis",
        "order": 1,
        "is_primary": True,
        "format_hint": "markdown",
    }


def test_u4_degraded_placeholder_marked_success_false():
    engine = WorkflowEngine(use_dynamic_state=False)
    state = {
        "market_report": GENERIC_REPORT_FALLBACK,
        "news_report": "真实新闻分析",
    }
    structured, manifest = engine._extract_from_state(
        state, [_field_info("market_report"), _field_info("news_report")]
    )
    assert structured["market_report"]["success"] is False
    assert structured["news_report"]["success"] is True
    by_field = {m["field"]: m for m in manifest}
    assert by_field["market_report"]["has_content"] is False
    assert by_field["news_report"]["has_content"] is True


# ---------------------------------------------------------------------------
# U3：报告末尾统一降级声明段
# ---------------------------------------------------------------------------

def test_u3_degradation_notice_lists_nodes_and_appends_to_report():
    engine = WorkflowEngine(use_dynamic_state=False)
    node_errors = {"risk_manager_v2": "LLM 调用失败（已重试 3 次）"}
    notice = engine._build_degradation_notice(node_errors)
    assert "数据可靠性声明" in notice
    assert "risk_manager_v2" in notice
    assert "1 个节点降级" in notice

    result = {"final_trade_decision": "# 投资简报正文", "_node_errors": node_errors}
    engine._append_degradation_notice(result)
    assert "数据可靠性声明" in result["final_trade_decision"]
    assert result["final_trade_decision"].startswith("# 投资简报正文")


def test_u3_no_node_errors_no_notice():
    engine = WorkflowEngine(use_dynamic_state=False)
    result = {"final_trade_decision": "# 投资简报正文"}
    engine._append_degradation_notice(result)
    assert result["final_trade_decision"] == "# 投资简报正文"
    assert engine._build_degradation_notice({}) == ""


# ---------------------------------------------------------------------------
# R3 配套：_node_errors 合并不被后节点覆盖（曾 4 连修的退化簇）
# ---------------------------------------------------------------------------

def test_merge_node_errors_merges_and_writes_back():
    final_state = {"_node_errors": {"node_a": "降级A"}}
    node_update = {"_node_errors": {"node_b": "降级B"}, "other": 1}
    WorkflowEngine._merge_node_errors(final_state, node_update)
    assert final_state["_node_errors"] == {"node_a": "降级A", "node_b": "降级B"}
    # 写回 node_update，防止 final_state.update(node_update) 覆盖合并结果
    assert node_update["_node_errors"] == {"node_a": "降级A", "node_b": "降级B"}
