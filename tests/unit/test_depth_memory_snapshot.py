"""C8（M5）单元测试：结论快照存取/解析 + 上期结论块 + 演化对照产出要求 + 记忆读注入退位。

对应实施文档 M5.1-M5.4 / 设计文档 §3.3：
- M5.1 快照四层结构（判断/依据/假设/失效条件）解析与落库，快速档不写
- M5.2 上期结论块（对比基线）文案组装
- M5.3 演化对照章节要求（snapshot_diff 档强制，其余档不强制）
- M5.4 per-agent 向量记忆读注入退位（写入链路保留）
"""

import asyncio

from core.workflow.depth_profiles import (
    EVOLUTION_SECTION_TITLE,
    PREV_SNAPSHOT_AGENTS,
    SNAPSHOT_SECTION_TITLE,
    build_contract_block,
    build_prev_snapshot_block,
    build_snapshot_requirements,
    get_profile,
)

_SAMPLE_REPORT = """
# 研究整合结论

正文论证略。

## 结论演化对照

与上期一致，无变化。

## 结论快照

- 判断：买入｜增持｜置信 80%
- 依据：PE 处历史 20% 分位（官方，2026-10-31）；出栏量环比 +5%（官方，2026-10-31）
- 假设：猪价四季度维持 18 元/公斤
- 失效条件：猪价跌破 15 元/公斤；能繁存栏环比转正
"""


class TestExtractSnapshot:
    """M5.1：从 trader/整合层输出提取四层快照。"""

    def test_parse_section_snapshot(self):
        from app.utils.conclusion_snapshot import extract_conclusion_snapshot

        snapshot = extract_conclusion_snapshot({"final_trade_decision": _SAMPLE_REPORT})

        assert snapshot["extract_source"] == "section"
        assert snapshot["judgment"]["direction"] == "买入"
        assert snapshot["judgment"]["rating"] == "增持"
        assert snapshot["judgment"]["confidence"] == "80%"
        assert len(snapshot["evidence"]) == 2
        assert "PE 处历史 20% 分位（官方，2026-10-31）" in snapshot["evidence"][0]
        assert snapshot["assumptions"] == ["猪价四季度维持 18 元/公斤"]
        assert len(snapshot["invalidations"]) == 2

    def test_parse_continuation_lines(self):
        from app.utils.conclusion_snapshot import extract_conclusion_snapshot

        text = (
            "## 结论快照\n"
            "- 判断：中性\n"
            "- 依据：读数 A（官方，2026-10-31）\n"
            "  补充读数 B（手工收集，2026-10-30）\n"
            "- 假设：暂无\n"
            "- 失效条件：暂无\n"
        )
        snapshot = extract_conclusion_snapshot({"final_trade_decision": text})

        assert snapshot["extract_source"] == "section"
        assert snapshot["judgment"]["direction"] == "中性"
        assert snapshot["evidence"] == [
            "读数 A（官方，2026-10-31）",
            "补充读数 B（手工收集，2026-10-30）",
        ]
        # 「暂无」如实保留，不编造条目
        assert snapshot["invalidations"] == ["暂无"]

    def test_evolution_section_before_snapshot(self):
        """演化对照章节在快照章节之前出现时，解析不受干扰。"""
        from app.utils.conclusion_snapshot import extract_conclusion_snapshot

        snapshot = extract_conclusion_snapshot({"final_trade_decision": _SAMPLE_REPORT})

        assert snapshot["extract_source"] == "section"
        assert snapshot["judgment"]["text"].startswith("买入")

    def test_heuristic_fallback_when_no_section(self):
        from app.utils.conclusion_snapshot import extract_conclusion_snapshot

        snapshot = extract_conclusion_snapshot(
            {"market_report": "普通报告内容"},
            decision={"analysis_view": "中性"},
            recommendation="分析观点：中性",
            confidence_score=0.7,
            key_points=["要点一", "要点二"],
        )

        assert snapshot["extract_source"] == "heuristic"
        assert snapshot["judgment"]["text"] == "分析观点：中性"
        assert snapshot["judgment"]["confidence"] == 0.7
        assert snapshot["evidence"] == ["要点一", "要点二"]
        # 缺失的层如实留空（宁缺勿造）
        assert snapshot["assumptions"] == []
        assert snapshot["invalidations"] == []


class TestSnapshotRequirements:
    """M5.3：快照/演化对照产出要求按档位与角色分发。"""

    def test_quick_tier_has_no_snapshot_requirement(self):
        block = build_contract_block(get_profile("快速"), "trader_v2")
        assert "结论快照要求" not in block

    def test_snapshot_tier_requires_snapshot_section_only(self):
        block = build_contract_block(get_profile("标准"), "trader_v2")
        assert "结论快照要求" in block
        assert "结论演化对照要求" not in block
        assert SNAPSHOT_SECTION_TITLE in block

    def test_snapshot_diff_tier_requires_evolution_section(self):
        for agent_name in ("trader_v2", "research_manager_v2"):
            block = build_contract_block(get_profile("深度"), agent_name)
            assert "结论快照要求" in block, agent_name
            assert "结论演化对照要求" in block, agent_name
            assert EVOLUTION_SECTION_TITLE in block

    def test_non_integration_roles_have_no_snapshot_requirement(self):
        block = build_contract_block(get_profile("深度"), "bull_researcher_v2")
        assert "结论快照要求" not in block

    def test_snapshot_requirements_direct(self):
        assert build_snapshot_requirements(get_profile("快速"), "trader_v2") == ""
        req = build_snapshot_requirements(get_profile("深度"), "trader_v2")
        assert "失效条件" in req
        assert "失效条件命中" in req


class TestPrevSnapshotBlock:
    """M5.2：上期结论块（对比基线）文案。"""

    def test_block_contains_four_layers_and_meta(self):
        block = build_prev_snapshot_block(
            {
                "judgment": {"text": "买入｜增持｜置信 80%"},
                "evidence": ["PE 20% 分位（官方，2026-10-31）"],
                "assumptions": ["猪价维持 18 元/公斤"],
                "invalidations": ["猪价跌破 15 元/公斤"],
                "depth": "深度",
                "data_as_of": "2026-10-31",
                "snapshot_date": "2026-11-01",
            }
        )

        assert "【上期结论（对比基线）｜数据基准日 2026-10-31｜深度档｜生成于 2026-11-01】" in block
        assert "- 判断：买入｜增持｜置信 80%" in block
        assert "- 依据：PE 20% 分位（官方，2026-10-31）" in block
        assert "- 假设：猪价维持 18 元/公斤" in block
        assert "- 失效条件：猪价跌破 15 元/公斤" in block
        assert "不要照抄上期结论" in block

    def test_missing_layers_render_as_absent(self):
        block = build_prev_snapshot_block({"judgment": {}})
        assert "暂无" in block

    def test_prev_snapshot_whitelist(self):
        assert "research_manager_v2" in PREV_SNAPSHOT_AGENTS
        assert "research_self_debate_v2" in PREV_SNAPSHOT_AGENTS
        assert "trader_v2" in PREV_SNAPSHOT_AGENTS
        assert "risk_manager_v2" not in PREV_SNAPSHOT_AGENTS


class _FakeInsertResult:
    inserted_id = "fake_object_id"


class _FakeCollection:
    def __init__(self):
        self.docs = []

    async def insert_one(self, document):
        self.docs.append(document)
        return _FakeInsertResult()

    async def find_one(self, filter=None, sort=None):
        candidates = [
            doc for doc in self.docs
            if all(doc.get(k) == v for k, v in (filter or {}).items())
        ]
        if sort:
            key, direction = sort[0]
            candidates.sort(key=lambda d: d.get(key), reverse=(direction == -1))
        return candidates[0] if candidates else None


class _FakeDB:
    def __init__(self):
        self.analysis_reports = _FakeCollection()
        self._collections = {}

    def __getitem__(self, name):
        return self._collections.setdefault(name, _FakeCollection())


class TestSnapshotStore:
    """M5.1：快照存取（多条存档取最新）。"""

    def test_save_and_load_latest(self):
        from app.utils.conclusion_snapshot import (
            CONCLUSION_SNAPSHOT_COLLECTION,
            load_latest_conclusion_snapshot,
            save_conclusion_snapshot,
        )

        db = _FakeDB()

        async def _run():
            for run_id in ("run_1", "run_2"):
                await save_conclusion_snapshot(
                    db,
                    user_id="u1",
                    ticker="000001",
                    stock_name="平安银行",
                    snapshot={
                        "judgment": {"text": f"判断 {run_id}"},
                        "evidence": [f"依据 {run_id}"],
                        "assumptions": [],
                        "invalidations": [],
                        "extract_source": "section",
                    },
                    data_as_of="2026-10-31",
                    depth="标准",
                    run_id=run_id,
                    analysis_date="2026-11-01",
                )
            # 固定时间戳，保证「取最新」断言确定性
            from datetime import datetime, timezone

            db[CONCLUSION_SNAPSHOT_COLLECTION].docs[0]["created_at"] = datetime(
                2026, 11, 1, 10, 0, tzinfo=timezone.utc
            )
            db[CONCLUSION_SNAPSHOT_COLLECTION].docs[1]["created_at"] = datetime(
                2026, 11, 2, 10, 0, tzinfo=timezone.utc
            )
            return await load_latest_conclusion_snapshot(db, "u1", "000001")

        latest = asyncio.run(_run())
        docs = db[CONCLUSION_SNAPSHOT_COLLECTION].docs
        assert len(docs) == 2  # 旧期不覆盖，多条存档
        assert docs[0]["run_id"] == "run_1"
        assert docs[0]["data_as_of"] == "2026-10-31"
        assert docs[0]["depth"] == "标准"
        assert docs[0]["evidence"] == ["依据 run_1"]
        assert docs[0]["extract_source"] == "section"
        assert latest["judgment"]["text"] == "判断 run_2"

    def test_load_returns_none_without_snapshot(self):
        from app.utils.conclusion_snapshot import load_latest_conclusion_snapshot

        db = _FakeDB()
        result = asyncio.run(load_latest_conclusion_snapshot(db, "u1", "000001"))
        assert result is None


class TestReportSaverSnapshotIntegration:
    """M5.1：report_saver 同事务区域落快照；快速档不写。"""

    def _save(self, research_depth):
        from app.utils.report_saver import save_analysis_report

        db = _FakeDB()
        asyncio.run(
            save_analysis_report(
                db,
                "000001",
                "平安银行",
                "A股",
                "test-model",
                reports={"final_trade_decision": _SAMPLE_REPORT},
                decision={"analysis_view": "买入"},
                recommendation="分析观点：买入",
                confidence_score=0.8,
                risk_level="中",
                research_depth=research_depth,
                user_id="u1",
            )
        )
        return db

    def test_standard_tier_writes_snapshot(self):
        from app.utils.conclusion_snapshot import CONCLUSION_SNAPSHOT_COLLECTION

        db = self._save("标准")
        docs = db[CONCLUSION_SNAPSHOT_COLLECTION].docs
        assert len(docs) == 1
        doc = docs[0]
        assert doc["user_id"] == "u1"
        assert doc["ticker"] == "000001"
        # run_id 与分析报告 ID 对齐，四层结构来自章节解析
        assert doc["run_id"] == db.analysis_reports.docs[0]["analysis_id"]
        assert doc["depth"] == "标准"
        assert doc["judgment"]["direction"] == "买入"
        assert doc["extract_source"] == "section"

    def test_quick_tier_does_not_write_snapshot(self):
        from app.utils.conclusion_snapshot import CONCLUSION_SNAPSHOT_COLLECTION

        db = self._save("快速")
        assert db[CONCLUSION_SNAPSHOT_COLLECTION].docs == []


class TestMemoryReadDemotion:
    """M5.4：per-agent 向量记忆读注入退位（写入链路保留）。"""

    def test_researcher_has_no_memory_recall(self):
        from core.agents.researcher import ResearcherAgent

        assert not hasattr(ResearcherAgent, "_get_memory_context")

    def test_trader_has_no_historical_trades_recall(self):
        from core.agents.trader import TraderAgent

        assert not hasattr(TraderAgent, "_get_historical_trades")

    def test_manager_has_no_memory_recall(self):
        from core.agents.manager import ManagerAgent

        assert not hasattr(ManagerAgent, "_get_memory_context")
        assert not hasattr(ManagerAgent, "_merge_memory_context")

    def test_write_paths_preserved(self):
        from core.agents.manager import ManagerAgent
        from core.agents.researcher import ResearcherAgent
        from core.agents.trader import TraderAgent

        assert hasattr(ResearcherAgent, "_save_to_memory")
        assert hasattr(TraderAgent, "_save_to_memory")
        assert hasattr(ManagerAgent, "_save_to_memory")
