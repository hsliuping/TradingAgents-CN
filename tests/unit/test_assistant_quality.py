# -*- coding: utf-8 -*-
"""A11 智能助手质量架构 —— 阶段 0 回归测试集。

对应设计文档 §5.1 的 10 个历史踩坑案例。本文件覆盖其中**不依赖真实 LLM / DB**、
可在纯单元层固化的部分（路径契约、四道防线、降级、数据引用）；
涉及真实 LLM 行为的案例（合规话术、裸数字改写、预检查流程、风险辩论三观点）
属集成/手工验证层，在设计文档中单独标注。

运行：env/Scripts/python -m pytest tests/unit/test_assistant_quality.py -v
"""

import asyncio

import pytest

from core.assistant import (
    EVIDENCE_HISTORY_TOOL,
    EVIDENCE_MEMORY,
    EVIDENCE_SEARCH,
    EVIDENCE_TOOL,
    EVIDENCE_USER_MESSAGE,
    REGISTERED_PASSTHROUGH,
    ROUTE_TYPE_PASSTHROUGH,
    Evidence,
    ReplyCandidate,
    ReplyGate,
    extract_data_refs,
)
from core.assistant.reply_gate import build_fallback_candidate
from core.assistant.paths import (
    AssistantRequest,
    PathRegistry,
    PRIORITY_HITL,
    PRIORITY_UNSUPPORTED_ASSET,
    PRIORITY_FAST_SEARCH,
    PRIORITY_DATA_PRECHECK,
    PRIORITY_MAIN_LLM,
    ROUTE_HITL,
    ROUTE_FAST_SEARCH,
    ROUTE_MAIN_LLM,
)
from core.assistant.lexicon import (
    StockDirectory,
    detect_unsupported_asset,
    extract_a_share_code,
)
from core.assistant.metrics import AssistantQualityMetrics


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


# ─────────────────────────── 路径注册表（S5 显式优先级 / S1 不可绕过）───────────────────────────

class TestPathRegistry:
    @staticmethod
    def _req():
        return AssistantRequest(service=None, user_message="问题")

    @pytest.mark.asyncio
    async def test_resolve_picks_first_match_by_priority(self):
        calls = []

        async def hitl_handler(req):
            calls.append(ROUTE_HITL)
            return None

        async def fast_handler(req):
            calls.append(ROUTE_FAST_SEARCH)
            return None

        async def main_handler(req):
            calls.append(ROUTE_MAIN_LLM)
            return ReplyCandidate.answer("主路径", ROUTE_MAIN_LLM, llm_processed=True)

        registry = PathRegistry()
        registry.register(ROUTE_HITL, PRIORITY_HITL, hitl_handler,
                          route_type=ROUTE_TYPE_PASSTHROUGH)
        registry.register(ROUTE_FAST_SEARCH, PRIORITY_FAST_SEARCH, fast_handler)
        registry.register(ROUTE_MAIN_LLM, PRIORITY_MAIN_LLM, main_handler)

        cand = await registry.resolve(self._req())
        assert cand.route_id == ROUTE_MAIN_LLM
        assert calls == [ROUTE_HITL, ROUTE_FAST_SEARCH, ROUTE_MAIN_LLM]  # 严格按优先级
        assert cand.meta["route_priority"] == PRIORITY_MAIN_LLM

    @pytest.mark.asyncio
    async def test_higher_priority_match_short_circuits(self):
        async def hitl(req):
            return ReplyCandidate.passthrough("已确认", ROUTE_HITL)

        async def forbidden_main(req):
            raise AssertionError("HITL 命中后不应再执行主路径")

        registry = PathRegistry()
        registry.register(ROUTE_HITL, PRIORITY_HITL, hitl,
                          route_type=ROUTE_TYPE_PASSTHROUGH)
        registry.register(ROUTE_MAIN_LLM, PRIORITY_MAIN_LLM, forbidden_main)

        cand = await registry.resolve(self._req())
        assert cand.route_id == ROUTE_HITL
        assert cand.meta["route_priority"] == PRIORITY_HITL

    def test_priority_order_matches_legacy_precedence(self):
        """快路径(40) 必须先于 数据预检查(50)——保持重构前 chat() 的实际行为。"""
        assert PRIORITY_HITL < PRIORITY_UNSUPPORTED_ASSET
        assert PRIORITY_UNSUPPORTED_ASSET < PRIORITY_FAST_SEARCH
        assert PRIORITY_FAST_SEARCH < PRIORITY_DATA_PRECHECK
        assert PRIORITY_DATA_PRECHECK < PRIORITY_MAIN_LLM

    def test_duplicate_route_rejected(self):
        async def h(req):
            return None

        registry = PathRegistry().register(ROUTE_FAST_SEARCH, PRIORITY_FAST_SEARCH, h)
        with pytest.raises(ValueError):
            registry.register(ROUTE_FAST_SEARCH, PRIORITY_FAST_SEARCH + 1, h)

    @pytest.mark.asyncio
    async def test_no_match_raises(self):
        async def none_path(req):
            return None

        registry = PathRegistry().register("x", 1, none_path)
        with pytest.raises(RuntimeError):
            await registry.resolve(self._req())


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


# ─────────────────────────── 词典事实源（阶段 4：lexicon）───────────────────────────

class TestAShareCodeExtraction:
    def test_extract_from_plain_text(self):
        assert extract_a_share_code("600519 现在估值多少") == "600519"
        # \b 在中文与数字之间无边界（与历史 _STOCK_CODE_RE 行为一致），需空白/标点分隔
        assert extract_a_share_code("帮我分析一下 000858") == "000858"
        assert extract_a_share_code("300750 和 601127 哪个好") == "300750"  # 首个命中

    def test_no_code_returns_none(self):
        assert extract_a_share_code("") is None
        assert extract_a_share_code(None) is None  # type: ignore[arg-type]
        assert extract_a_share_code("分析一下贵州茅台") is None

    def test_word_boundaries_reject_longer_digits(self):
        """7 位数字串不应截出 6 位代码（\\b 边界与历史行为一致）。"""
        assert extract_a_share_code("订单号3007501请查收") is None


class TestUnsupportedAssetGate:
    """品种闸门检测（service 与 planned 共用同一事实源，此处验证词表行为）。"""

    def test_hk_keyword_hits_hk_message(self):
        msg = detect_unsupported_asset("腾讯控股最近怎么样")
        assert msg is not None
        assert "港股" in msg

    def test_us_keyword_hits_us_message(self):
        msg = detect_unsupported_asset("特斯拉还能买吗")
        assert msg is not None
        assert "美股" in msg

    def test_us_ticker_hits_us_code_message(self):
        msg = detect_unsupported_asset("TSLA 现在多少钱")
        assert msg is not None
        assert "美股代码" in msg

    def test_hk_code_hits_hk_code_message(self):
        msg = detect_unsupported_asset("00700.HK 值得关注吗")
        assert msg is not None
        assert "港股代码" in msg

    def test_a_share_question_not_blocked(self):
        assert detect_unsupported_asset("分析一下 600519 茅台") is None
        assert detect_unsupported_asset("") is None
        assert detect_unsupported_asset(None) is None  # type: ignore[arg-type]

    def test_hk_takes_precedence_over_us(self):
        """历史行为：港股词先于美股词检测。"""
        msg = detect_unsupported_asset("港股和美股哪个好")
        assert msg is not None
        assert "港股" in msg


class _FakeCursor:
    """最小异步游标桩：支持 async for。"""

    def __init__(self, docs):
        self._docs = docs

    def __aiter__(self):
        self._iter = iter(self._docs)
        return self

    async def __anext__(self):
        try:
            return next(self._iter)
        except StopIteration:
            raise StopAsyncIteration from None


class _FakeCollection:
    def __init__(self, docs, fail=False):
        self._docs = docs
        self._fail = fail
        self.find_calls = 0

    def find(self, *args, **kwargs):
        self.find_calls += 1
        if self._fail:
            raise RuntimeError("数据库暂时不可用")
        return _FakeCursor(self._docs)


class _FakeDB:
    def __init__(self, docs, fail=False):
        self.stock_basic_info = _FakeCollection(docs, fail=fail)

    def __getitem__(self, name):
        assert name == "stock_basic_info"
        return self.stock_basic_info


class _FakeClock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


def _basic_docs():
    return [
        {"symbol": "600519", "name": "贵州茅台"},
        {"symbol": "601127", "name": "赛力斯集团"},
        {"symbol": "688777", "name": "赛力斯"},
        {"symbol": "000001", "name": "平安银行"},
        {"symbol": "999999", "name": "超"},                        # 1 字名称应被过滤
        {"symbol": "888888", "name": "这是一个超过六个字的名称"},   # >6 字过滤
        {"symbol": "111111", "name": "同名重复"},                  # 同名保留先出现
        {"symbol": "222222", "name": "同名重复"},
    ]


class TestStockDirectory:
    @pytest.mark.asyncio
    async def test_full_load_with_name_filter(self):
        clock = _FakeClock()
        directory = StockDirectory(ttl_seconds=3600, clock=clock)
        name_map = await directory.get_name_map(_FakeDB(_basic_docs()))
        # 全量加载：2~6 字名称全部入库，1 字/超长被过滤
        assert name_map["贵州茅台"] == "600519"
        assert name_map["赛力斯"] == "688777"
        assert "超" not in name_map
        assert "这是一个超过六个字的名称" not in name_map
        assert name_map["同名重复"] == "111111"  # 同名保留先出现的代码

    @pytest.mark.asyncio
    async def test_ttl_cache_avoids_second_query(self):
        clock = _FakeClock()
        db = _FakeDB(_basic_docs())
        directory = StockDirectory(ttl_seconds=3600, clock=clock)
        await directory.get_name_map(db)
        clock.now += 1800  # TTL 内
        await directory.get_name_map(db)
        assert db.stock_basic_info.find_calls == 1  # TTL 内零查询

    @pytest.mark.asyncio
    async def test_expired_ttl_triggers_refresh(self):
        clock = _FakeClock()
        db = _FakeDB(_basic_docs())
        directory = StockDirectory(ttl_seconds=3600, clock=clock)
        await directory.get_name_map(db)
        clock.now += 3601  # 过期
        await directory.get_name_map(db)
        assert db.stock_basic_info.find_calls == 2

    @pytest.mark.asyncio
    async def test_refresh_failure_keeps_old_cache(self):
        """刷新失败沿用旧缓存——词典故障不阻断路由。"""
        clock = _FakeClock()
        db = _FakeDB(_basic_docs())
        directory = StockDirectory(ttl_seconds=3600, clock=clock)
        await directory.get_name_map(db)
        db.stock_basic_info._fail = True
        clock.now += 3601
        name_map = await directory.get_name_map(db)
        assert name_map["贵州茅台"] == "600519"  # 旧数据仍可用
        assert directory.is_fresh()  # 失败也刷新时间戳，避免每请求重试打库

    @pytest.mark.asyncio
    async def test_resolve_prefers_code_then_longest_name(self):
        db = _FakeDB(_basic_docs())
        directory = StockDirectory(ttl_seconds=3600, clock=_FakeClock())
        assert await directory.resolve_symbol("600519 的估值", db) == "600519"  # 代码优先
        assert await directory.resolve_symbol("赛力斯集团的业绩", db) == "601127"  # 长名优先
        assert await directory.resolve_symbol("赛力斯怎么样", db) == "688777"
        assert await directory.resolve_symbol("完全无关的闲聊内容", db) is None


# ─────────────────────────── 质量埋点（阶段 4：metrics）───────────────────────────

class _MetricsColl:
    def __init__(self, fail=False):
        self.inserted = []
        self._fail = fail

    async def insert_one(self, doc):
        if self._fail:
            raise RuntimeError("boom")
        self.inserted.append(doc)

    async def create_index(self, *args, **kwargs):
        return None


class _MetricsDB:
    def __init__(self, fail=False):
        self.events = _MetricsColl(fail=fail)

    def __getitem__(self, name):
        assert name == "assistant_quality_events"
        return self.events


class TestQualityMetrics:
    def test_record_without_loop_drops_silently(self):
        """同步上下文（无事件循环）静默丢弃——埋点不可阻断主链路。"""
        db = _MetricsDB()
        AssistantQualityMetrics().record(db=db, route_id="main_llm")  # 不应抛异常
        assert db.events.inserted == []

    @pytest.mark.asyncio
    async def test_record_persists_event(self):
        db = _MetricsDB()
        metrics = AssistantQualityMetrics()
        metrics.record(db=db, route_id="main_llm", streaming=False,
                       gate_passed=True, quality_signals=["fabricated_json"])
        await asyncio.sleep(0.01)  # 让 fire-and-forget 任务执行
        assert len(db.events.inserted) == 1
        event = db.events.inserted[0]
        assert event["route_id"] == "main_llm"
        assert event["quality_signals"] == ["fabricated_json"]
        assert event["created_at"] is not None

    @pytest.mark.asyncio
    async def test_insert_failure_never_raises(self):
        db = _MetricsDB(fail=True)
        AssistantQualityMetrics().record(db=db, route_id="x")
        await asyncio.sleep(0.01)  # 任务内部吞掉异常，不向外传播
        assert db.events.inserted == []

    @pytest.mark.asyncio
    async def test_record_without_db_drops(self):
        """有事件循环但无 db 句柄 → 静默丢弃。"""
        AssistantQualityMetrics().record(db=None, route_id="x")  # 不应抛异常
