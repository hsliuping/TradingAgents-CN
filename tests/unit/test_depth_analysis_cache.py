"""短周期分析缓存（M6）单元测试

覆盖：
1. 参数指纹稳定性与敏感性（分析师顺序/集合变化/模型变化）
2. 缓存资格判定（任务类型/匿名/断点续跑/debug/强制刷新）
3. 索引读写与 TTL/键失效
4. 缓存命中标注文案
5. 引擎侧缓存键上下文与读写钩子
6. 结果格式化时的缓存命中标注（报告头部）
"""

import asyncio
import logging
from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest

from app.services.unified_analysis_engine import UnifiedAnalysisEngine
from app.utils.analysis_cache import (
    ANALYSIS_CACHE_COLLECTION,
    build_cache_key,
    build_cache_notice,
    build_param_fingerprint,
    find_cache_hit,
    is_cache_eligible,
    normalize_data_as_of,
    save_cache_entry,
)
from app.utils.timezone import now_tz


class _FakeCacheCollection:
    """最小缓存集合：支持 find_one(sort) / replace_one(upsert)。"""

    def __init__(self):
        self.docs = []

    async def find_one(self, query, sort=None, **kwargs):
        matches = [doc for doc in self.docs if all(doc.get(k) == v for k, v in query.items())]
        if not matches:
            return None
        if sort:
            field, direction = sort[0]
            matches.sort(key=lambda doc: doc.get(field), reverse=direction < 0)
        return matches[0]

    async def replace_one(self, query, doc, upsert=False):
        for index, existing in enumerate(self.docs):
            if all(existing.get(k) == v for k, v in query.items()):
                self.docs[index] = doc
                return
        self.docs.append(doc)


class _FakeDB:
    def __init__(self):
        self._collections = {}

    def __getitem__(self, name):
        return self._collections.setdefault(name, _FakeCacheCollection())

    @property
    def cache_collection(self):
        return self.__getitem__(ANALYSIS_CACHE_COLLECTION)


class TestParamFingerprint:
    def test_same_inputs_same_fingerprint(self):
        inputs = {"selected_analysts": ["market", "news"], "quick_analysis_model": "qwen-turbo"}
        assert build_param_fingerprint(inputs) == build_param_fingerprint(dict(inputs))

    def test_analyst_order_insensitive(self):
        first = {"selected_analysts": ["market", "news", "fundamentals"]}
        second = {"selected_analysts": ["fundamentals", "news", "market"]}
        assert build_param_fingerprint(first) == build_param_fingerprint(second)

    def test_analyst_change_changes_fingerprint(self):
        first = {"selected_analysts": ["market", "news"]}
        second = {"selected_analysts": ["market"]}
        assert build_param_fingerprint(first) != build_param_fingerprint(second)

    def test_custom_prompt_change_changes_fingerprint(self):
        assert build_param_fingerprint({"custom_prompt": "A"}) != build_param_fingerprint({"custom_prompt": "B"})

    def test_model_change_changes_fingerprint(self):
        first = {"quick_analysis_model": "qwen-turbo"}
        second = {"quick_analysis_model": "deepseek-chat"}
        assert build_param_fingerprint(first) != build_param_fingerprint(second)

    def test_empty_inputs_stable(self):
        assert build_param_fingerprint({}) == build_param_fingerprint({})


class TestNormalizeDataAsOf:
    def test_datetime(self):
        assert normalize_data_as_of(datetime(2026, 11, 1, 8, 30)) == "2026-11-01"

    def test_iso_string(self):
        assert normalize_data_as_of("2026-11-01T00:00:00") == "2026-11-01"
        assert normalize_data_as_of("2026-11-01 00:00:00") == "2026-11-01"

    def test_unknown(self):
        assert normalize_data_as_of(None) == ""
        assert normalize_data_as_of("") == ""


class TestCacheEligibility:
    def test_stock_analysis_eligible(self):
        assert is_cache_eligible("stock_analysis", {"symbol": "600519"}, "user-1") is True

    def test_enum_task_type_eligible(self):
        assert is_cache_eligible(SimpleNamespace(value="etf_analysis"), {}, "user-1") is True

    def test_other_task_type_not_eligible(self):
        assert is_cache_eligible("trade_review", {}, "user-1") is False

    def test_anonymous_not_eligible(self):
        assert is_cache_eligible("stock_analysis", {}, "") is False

    @pytest.mark.parametrize("flag", ["resume", "debug_mode"])
    def test_bypass_flags_not_eligible(self, flag):
        assert is_cache_eligible("stock_analysis", {flag: True}, "user-1") is False

    def test_force_refresh_still_eligible_for_write(self):
        """M6.2：force_refresh 只跳过读，仍参与缓存体系（跑完覆盖写索引）。"""
        assert is_cache_eligible("stock_analysis", {"force_refresh": True}, "user-1") is True


class TestCacheKey:
    def test_key_fields_normalized(self):
        key = build_cache_key(" user-1 ", " 600519 ", "标准", "2026-11-01", "abc")
        assert key == {
            "user_id": "user-1",
            "ticker": "600519",
            "depth": "标准",
            "data_as_of": "2026-11-01",
            "param_fingerprint": "abc",
        }


class TestCacheStore:
    def test_save_then_hit(self):
        db = _FakeDB()

        async def _run():
            await save_cache_entry(
                db,
                user_id="user-1",
                ticker="600519",
                stock_name="贵州茅台",
                depth="标准",
                data_as_of="2026-11-01",
                param_fingerprint="fp",
                ttl_min=120,
                run_id="task-1",
                result={"market_report": "报告正文", "context": "不可序列化对象"},
            )
            return await find_cache_hit(
                db,
                user_id="user-1",
                ticker="600519",
                depth="标准",
                data_as_of="2026-11-01",
                param_fingerprint="fp",
                ttl_min=120,
            )

        hit = asyncio.run(_run())
        assert hit is not None
        assert hit["result"]["market_report"] == "报告正文"
        # 运行时对象不入缓存 payload
        assert "context" not in hit["result"]
        assert hit["cache_meta"]["data_as_of"] == "2026-11-01"
        assert hit["cache_meta"]["depth"] == "标准"

    def test_expired_not_hit(self):
        db = _FakeDB()

        async def _run():
            await save_cache_entry(
                db,
                user_id="user-1",
                ticker="600519",
                stock_name="贵州茅台",
                depth="快速",
                data_as_of="2026-11-01",
                param_fingerprint="fp",
                ttl_min=30,
                run_id="task-1",
                result={"market_report": "报告正文"},
            )
            # 把索引时间戳改到 TTL 之外（快速档 31 分钟前）
            db.cache_collection.docs[0]["created_at"] = now_tz() - timedelta(minutes=31)
            return await find_cache_hit(
                db,
                user_id="user-1",
                ticker="600519",
                depth="快速",
                data_as_of="2026-11-01",
                param_fingerprint="fp",
                ttl_min=30,
            )

        assert asyncio.run(_run()) is None

    @pytest.mark.parametrize(
        "mismatch",
        [
            {"depth": "深度"},
            {"data_as_of": "2026-10-31"},
            {"param_fingerprint": "fp-other"},
            {"ticker": "000858"},
            {"user_id": "user-2"},
        ],
    )
    def test_key_mismatch_not_hit(self, mismatch):
        db = _FakeDB()

        async def _run():
            await save_cache_entry(
                db,
                user_id="user-1",
                ticker="600519",
                stock_name="贵州茅台",
                depth="标准",
                data_as_of="2026-11-01",
                param_fingerprint="fp",
                ttl_min=120,
                run_id="task-1",
                result={"market_report": "报告正文"},
            )
            query = {
                "user_id": "user-1",
                "ticker": "600519",
                "depth": "标准",
                "data_as_of": "2026-11-01",
                "param_fingerprint": "fp",
            }
            query.update(mismatch)
            return await find_cache_hit(db, ttl_min=120, **query)

        assert asyncio.run(_run()) is None

    def test_same_key_overwrites_single_record(self):
        db = _FakeDB()

        async def _run():
            for report in ("第一版", "第二版"):
                await save_cache_entry(
                    db,
                    user_id="user-1",
                    ticker="600519",
                    stock_name="贵州茅台",
                    depth="标准",
                    data_as_of="2026-11-01",
                    param_fingerprint="fp",
                    ttl_min=120,
                    run_id="task-1",
                    result={"market_report": report},
                )
            return await find_cache_hit(
                db,
                user_id="user-1",
                ticker="600519",
                depth="标准",
                data_as_of="2026-11-01",
                param_fingerprint="fp",
                ttl_min=120,
            )

        hit = asyncio.run(_run())
        assert len(db.cache_collection.docs) == 1
        assert hit["result"]["market_report"] == "第二版"

    def test_empty_result_not_saved(self):
        db = _FakeDB()

        async def _run():
            return await save_cache_entry(
                db,
                user_id="user-1",
                ticker="600519",
                stock_name="贵州茅台",
                depth="标准",
                data_as_of="2026-11-01",
                param_fingerprint="fp",
                ttl_min=120,
                run_id="task-1",
                result={},
            )

        assert asyncio.run(_run()) is False
        assert db.cache_collection.docs == []


class TestCacheNotice:
    def test_notice_content(self):
        notice = build_cache_notice(
            {"generated_at": "2026-11-01T09:30:00+08:00", "data_as_of": "2026-11-01"}
        )
        assert "缓存命中" in notice
        assert "2026-11-01 09:30" in notice
        assert "数据基准日 2026-11-01" in notice
        assert "TTL 内直接复用" in notice
        assert "强制刷新" in notice

    def test_notice_unknown_time(self):
        notice = build_cache_notice({"data_as_of": "2026-11-01"})
        assert "分析于 未知" in notice


class TestEngineCacheContext:
    def _make_task(self, task_params):
        return SimpleNamespace(
            task_id="task-1",
            user_id="user-1",
            task_type="stock_analysis",
            task_params=task_params,
        )

    def test_standard_depth_context(self):
        engine = UnifiedAnalysisEngine()
        task = self._make_task({"symbol": "600519", "research_depth": "标准"})
        ctx = engine._build_cache_context(
            task, {"ticker": "600519", "research_depth": "标准", "analysis_date": "2026-11-01"}
        )
        assert ctx is not None
        assert ctx["depth"] == "标准"
        assert ctx["ttl_min"] == 120
        assert ctx["data_as_of"] == "2026-11-01"
        assert ctx["param_fingerprint"]

    def test_quick_depth_ttl(self):
        engine = UnifiedAnalysisEngine()
        task = self._make_task({"symbol": "600519", "research_depth": "快速"})
        ctx = engine._build_cache_context(
            task, {"ticker": "600519", "research_depth": "快速", "analysis_date": "2026-11-01"}
        )
        assert ctx["ttl_min"] == 30

    def test_force_refresh_keeps_context_for_write(self):
        """M6.2：force_refresh 不再把缓存上下文判 None——跑完仍覆盖写索引。"""
        engine = UnifiedAnalysisEngine()
        task = self._make_task({"symbol": "600519", "force_refresh": True})
        ctx = engine._build_cache_context(task, {"ticker": "600519", "research_depth": "标准"})
        assert ctx is not None
        assert ctx["depth"] == "标准"

    def test_force_refresh_skips_cache_read(self):
        """M6.2：force_refresh 跳过读（强制真跑），无标记时正常读。"""
        engine = UnifiedAnalysisEngine()
        ctx = {"user_id": "user-1", "ticker": "600519"}
        assert engine._should_read_cache(self._make_task({"force_refresh": True}), ctx) is False
        assert engine._should_read_cache(self._make_task({}), ctx) is True
        assert engine._should_read_cache(self._make_task({}), None) is False

    def test_trade_review_returns_none(self):
        engine = UnifiedAnalysisEngine()
        task = SimpleNamespace(
            task_id="task-1", user_id="user-1", task_type="trade_review", task_params={}
        )
        ctx = engine._build_cache_context(task, {"ticker": "600519", "research_depth": "标准"})
        assert ctx is None

    def test_missing_ticker_returns_none(self):
        engine = UnifiedAnalysisEngine()
        task = self._make_task({"symbol": "600519"})
        assert engine._build_cache_context(task, {"research_depth": "标准"}) is None


class TestEngineCacheHooks:
    def _ctx(self):
        return {
            "user_id": "user-1",
            "ticker": "600519",
            "stock_name": "贵州茅台",
            "depth": "标准",
            "data_as_of": "2026-11-01",
            "param_fingerprint": "fp",
            "ttl_min": 120,
            "run_id": "task-1",
        }

    def test_load_cache_hit_passes_key(self, monkeypatch):
        captured = {}

        async def _fake_find(db, **kwargs):
            captured.update(kwargs)
            return {"result": {"market_report": "报告正文"}, "cache_meta": {"data_as_of": "2026-11-01"}}

        monkeypatch.setattr("app.utils.analysis_cache.find_cache_hit", _fake_find)
        engine = UnifiedAnalysisEngine()
        hit = asyncio.run(engine._load_cache_hit(self._ctx()))
        assert hit["result"]["market_report"] == "报告正文"
        assert captured["ticker"] == "600519"
        assert captured["depth"] == "标准"
        assert captured["ttl_min"] == 120

    def test_load_cache_hit_swallows_failure(self, monkeypatch):
        async def _boom(db, **kwargs):
            raise RuntimeError("db down")

        monkeypatch.setattr("app.utils.analysis_cache.find_cache_hit", _boom)
        engine = UnifiedAnalysisEngine()
        assert asyncio.run(engine._load_cache_hit(self._ctx())) is None

    def test_save_cache_entry_passes_key(self, monkeypatch):
        captured = {}

        async def _fake_save(db, **kwargs):
            captured.update(kwargs)
            return True

        monkeypatch.setattr("app.utils.analysis_cache.save_cache_entry", _fake_save)
        engine = UnifiedAnalysisEngine()
        asyncio.run(engine._save_cache_entry(self._ctx(), {"market_report": "报告正文"}))
        assert captured["run_id"] == "task-1"
        assert captured["ttl_min"] == 120
        assert captured["result"]["market_report"] == "报告正文"


class TestFormattedCacheAnnotation:
    def _make_service(self):
        from app.services.task_analysis_service import TaskAnalysisService

        service = TaskAnalysisService.__new__(TaskAnalysisService)
        service.logger = logging.getLogger("test_analysis_cache")
        return service

    def _make_task(self):
        return SimpleNamespace(
            task_params={"symbol": "600519", "research_depth": "标准"},
            execution_time=1.0,
            task_type=SimpleNamespace(value="stock_analysis"),
        )

    def test_cache_hit_annotates_summary_and_reports(self):
        service = self._make_service()
        raw_result = {
            "final_decision": {"action": "中性"},
            "summary": "基础结论",
            "is_cached": True,
            "cache_meta": {"generated_at": "2026-11-01T09:30:00+08:00", "data_as_of": "2026-11-01"},
            "structured_reports": {
                "market_report": {"success": True, "content": "市场分析正文内容足够长"},
            },
        }
        formatted = service._format_analysis_result(raw_result, self._make_task())
        assert formatted["cache_hit"] is True
        assert formatted["summary"].startswith("缓存命中")
        assert formatted["reports"]["market_report"].startswith("缓存命中")

    def test_non_cache_result_not_annotated(self):
        service = self._make_service()
        raw_result = {
            "final_decision": {"action": "中性"},
            "summary": "基础结论",
            "structured_reports": {
                "market_report": {"success": True, "content": "市场分析正文内容足够长"},
            },
        }
        formatted = service._format_analysis_result(raw_result, self._make_task())
        assert "cache_hit" not in formatted
        assert "缓存命中" not in formatted["summary"]
