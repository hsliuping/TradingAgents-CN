# -*- coding: utf-8 -*-
"""A11 智能助手质量架构 —— 阶段 0 回归测试集。

对应设计文档 §5.1 的 10 个历史踩坑案例。本文件覆盖其中**不依赖真实 LLM / DB**、
可在纯单元层固化的部分（路径契约、四道防线、降级、数据引用）；
涉及真实 LLM 行为的案例（合规话术、裸数字改写、预检查流程、风险辩论三观点）
属集成/手工验证层，在设计文档中单独标注。

运行：env/Scripts/python -m pytest tests/unit/test_assistant_quality.py -v
"""

import pytest

from core.assistant import (
    EVIDENCE_HISTORY_TOOL,
    EVIDENCE_MEMORY,
    EVIDENCE_SEARCH,
    EVIDENCE_TOOL,
    EVIDENCE_USER_MESSAGE,
    REGISTERED_PASSTHROUGH,
    Evidence,
    ReplyCandidate,
    ReplyGate,
    extract_data_refs,
)
from core.assistant.reply_gate import build_fallback_candidate


@pytest.fixture
def gate():
    return ReplyGate()


def _ev(source_type, source_id, content, locator=None):
    return Evidence(source_type=source_type, source_id=source_id, content=content, locator=locator)


# ─────────────────────────── 路径类型契约（治 B 类裸透传）───────────────────────────

class TestRouteContract:
    def test_clean_answer_passes(self, gate):
        c = ReplyCandidate.answer("这是经过分析的回答。", "main_llm", llm_processed=True)
        r = gate.run(c, "问题")
        assert r.passed, r.failures

    def test_answer_without_llm_blocked(self, gate):
        """案例1：快路径若未经 LLM 直接返回，契约层必须拦截（不靠文本启发式）。"""
        c = ReplyCandidate.answer("十条裸搜索标题链接列表……", "fast_search", llm_processed=False)
        r = gate.run(c, "最近赛力斯有什么新车")
        assert not r.passed
        assert "llm_processed_contract" in r.failed_checks

    def test_registered_passthrough_passes(self, gate):
        for route_id in ("hitl", "unsupported_asset", "data_precheck",
                         "llm_unavailable", "timeout", "error", "fallback_evidence"):
            assert route_id in REGISTERED_PASSTHROUGH
            c = ReplyCandidate.passthrough("系统提示", route_id)
            assert gate.run(c).passed, route_id

    def test_unregistered_passthrough_blocked(self, gate):
        c = ReplyCandidate.passthrough("偷偷直出", "rogue_new_bypass")
        r = gate.run(c)
        assert not r.passed
        assert "passthrough_registration" in r.failed_checks

    def test_answer_requires_explicit_llm_flag(self):
        """answer 工厂必传 llm_processed，禁止默认当作已过 LLM。"""
        with pytest.raises(TypeError):
            ReplyCandidate.answer("x", "main_llm")  # type: ignore[call-arg]


# ─────────────────────────── A 类：四道数字/痕迹溯源防线 ───────────────────────────

class TestFabricationDefenses:
    def test_unsourced_numbers_blocked(self, gate):
        """案例7：未调任何工具却堆砌大量精确数字 → 拦截。"""
        reply = "公司营收1亿元，净利2亿元，销量3万辆，成本4元，增长5%，负债率6%，毛利7亿元。"
        c = ReplyCandidate.answer(
            reply, "main_llm", llm_processed=True, tools_used=[]
        )
        r = gate.run(c, "这家公司业绩如何")
        assert not r.passed
        assert "unsourced_numbers" in r.failed_checks

    def test_fabricated_tool_json_blocked(self, gate):
        reply = 'get_stock_data(600519) → {"price": 1688.0, "pe": 25.3} 这是工具结果'
        c = ReplyCandidate.answer(
            reply, "main_llm", llm_processed=True,
            tools_used=["get_stock_data"],
            evidence=[_ev(EVIDENCE_TOOL, "get_stock_data", "真实返回是 Markdown 文本")],
        )
        r = gate.run(c, "查一下")
        assert not r.passed
        assert "fabricated_tool_json" in r.failed_checks

    def test_fabricated_tool_ref_blocked(self, gate):
        reply = "数据来源：get_fake_nonexistent_tool，显示市占率 30%。"
        c = ReplyCandidate.answer(
            reply, "main_llm", llm_processed=True,
            tools_used=["some_other_tool"],
        )
        r = gate.run(c, "市占率多少")
        assert not r.passed
        assert "fabricated_tool_refs" in r.failed_checks

    def test_untraced_risky_numbers_blocked(self, gate):
        """案例3：调了工具，但工具无任何数字，回复却塞 6 个高风险数字 → 拦截。"""
        reply = ("估值分别为 11.1亿元、22.2亿元、33.3亿元、"
                 "44.4亿元、55.5亿元、66.6亿元。")
        c = ReplyCandidate.answer(
            reply, "main_llm", llm_processed=True,
            tools_used=["get_x"],
            evidence=[_ev(EVIDENCE_TOOL, "get_x", "工具返回：近期公告以定性描述为主。")],
        )
        r = gate.run(c, "估值多少")
        assert not r.passed
        assert "untraced_risky_numbers" in r.failed_checks

    def test_number_traceable_to_tool_passes(self, gate):
        """回复数字能在工具返回中溯源 → 放行。"""
        content = "赛力斯中性情景目标价 46.28 元，对应市值 806.2 亿元。"
        reply = "根据工具测算，中性情景目标价为 46.28 元。"
        c = ReplyCandidate.answer(
            reply, "main_llm", llm_processed=True,
            tools_used=["get_valuation"],
            evidence=[_ev(EVIDENCE_TOOL, "get_valuation", content)],
        )
        r = gate.run(c, "目标价")
        assert r.passed, r.failures

    def test_number_traceable_to_history_passes(self, gate):
        """案例8：多轮引用上一轮工具的数字，不应误判为编造。"""
        reply = "上一轮工具显示目标价 69.14 元，本轮沿用该结论。"
        c = ReplyCandidate.answer(
            reply, "main_llm", llm_processed=True,
            tools_used=["get_valuation"],
            evidence=[
                _ev(EVIDENCE_TOOL, "get_valuation", "本轮仅返回文字说明。"),
                _ev(EVIDENCE_HISTORY_TOOL, "get_valuation", "历史工具结果：乐观目标价 69.14 元"),
            ],
        )
        r = gate.run(c, "继续说")
        assert r.passed, r.failures

    def test_number_traceable_to_memory_passes(self, gate):
        """引用注入的事实记忆数字不应误判。"""
        reply = "据此前记录，行业完全成本约 15.8 元/公斤。"
        c = ReplyCandidate.answer(
            reply, "main_llm", llm_processed=True,
            tools_used=["ask"],
            evidence=[
                _ev(EVIDENCE_TOOL, "ask", "好的。"),
                _ev(EVIDENCE_MEMORY, "mem0", "行业完全成本约 15.8 元/公斤（采集于近期）"),
            ],
        )
        r = gate.run(c, "成本多少")
        assert r.passed, r.failures

    def test_number_from_user_message_passes(self, gate):
        """用户自己给出的数字，助手引用不算编造。"""
        c = ReplyCandidate.answer(
            reply="您提到的成本 12.3 元/公斤已记录，基于此……",
            route_id="main_llm", llm_processed=True, tools_used=["chat"],
            evidence=[_ev(EVIDENCE_TOOL, "chat", "好的，我来分析。")],
        )
        r = gate.run(c, "如果成本是12.3元/公斤怎么样")
        assert r.passed, r.failures

    def test_valuation_excel_verbatim_presentation_passes(self, gate):
        """案例2：估值 Excel 工具结果要求原样呈现（含数字+下载链接），
        answer 型契约下无需任何豁免即可通过（数字全部可溯源、无 JSON 伪造）。"""
        content = (
            "估值测算已生成：\n"
            "| 情景 | 目标价（元） |\n|---|---|\n"
            "| 悲观 | 29.01 |\n| 中性 | 40.61 |\n| 乐观 | 69.14 |\n"
            "下载：/api/assistant/deliverables/valuation_601127.xlsx"
        )
        reply = content  # LLM 按工具契约原样呈现
        c = ReplyCandidate.answer(
            reply, "main_llm", llm_processed=True,
            tools_used=["generate_valuation_excel_tool"],
            evidence=[_ev(EVIDENCE_TOOL, "generate_valuation_excel_tool", content,
                          locator="/api/assistant/deliverables/valuation_601127.xlsx")],
        )
        r = gate.run(c, "生成估值表")
        assert r.passed, r.failures


# ─────────────────────────── 两级降级：回退证据 ───────────────────────────

class TestFallback:
    def test_contract_failure_degrades_to_registered_evidence(self, gate):
        raw = "搜索引擎：十条标题与链接（无正文）……" * 3
        c = ReplyCandidate.answer(
            raw, "fast_search", llm_processed=False,
            tools_used=["search_recent_information"],
            evidence=[_ev(EVIDENCE_SEARCH, "search_recent_information", raw)],
        )
        result = gate.run(c, "最近有什么新车")
        assert not result.passed

        fb = build_fallback_candidate(c, result.failures)
        assert fb.route_id == "fallback_evidence"
        assert fb.route_type == "passthrough_allowed"
        assert fb.route_id in REGISTERED_PASSTHROUGH
        # 降级回复不是裸列表：含局限说明，且附真实资料来源
        assert "数据质量校验" in fb.reply
        assert "search_recent_information" in fb.reply
        # 降级产物本身合法，能过 gate（白名单）
        assert gate.run(fb).passed

    def test_fallback_without_evidence_is_honest(self, gate):
        c = ReplyCandidate.answer(
            "回答", "main_llm", llm_processed=False, tools_used=[], evidence=[]
        )
        result = gate.run(c, "问题")
        fb = build_fallback_candidate(c, result.failures)
        assert "未获取到可引用的原始资料" in fb.reply


# ─────────────────────────── data_refs 真实现 ───────────────────────────

class TestDataRefs:
    def test_only_tool_and_search_presented_dedup(self):
        evidence = [
            _ev(EVIDENCE_TOOL, "get_a", "内容1"),
            _ev(EVIDENCE_TOOL, "get_a", "内容1重复"),                # 去重
            _ev(EVIDENCE_SEARCH, "searxng", "内容2", locator="http://x"),
            _ev(EVIDENCE_USER_MESSAGE, "user", "用户的话"),          # 不展示
            _ev(EVIDENCE_MEMORY, "mem0", "记忆"),                    # 不展示
            _ev(EVIDENCE_HISTORY_TOOL, "get_old", "历史"),           # 不展示
        ]
        refs = extract_data_refs(evidence)
        assert len(refs) == 2
        kinds = {(r["source_type"], r["source_id"]) for r in refs}
        assert kinds == {("tool", "get_a"), ("search", "searxng")}
        search_ref = next(r for r in refs if r["source_type"] == "search")
        assert search_ref["locator"] == "http://x"

    def test_empty_evidence_returns_empty_refs(self):
        assert extract_data_refs(None) == []
        assert extract_data_refs([]) == []
