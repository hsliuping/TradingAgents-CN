"""DEPTH_PROFILES 三档分析画像注册表单元测试（C1，2026-11-04 五档简化为三档）。"""

import pytest

from core.workflow.depth_profiles import (
    CONTRACT_DISCIPLINE_LINE,
    DEPTH_NAMES,
    DEPTH_PROFILES,
    MODE_MULTI_AGENT,
    MODE_SELF_DEBATE,
    MEMORY_OFF,
    MEMORY_SNAPSHOT,
    MEMORY_SNAPSHOT_DIFF,
    NODE_SCENARIO_SIM,
    NODE_RISK_REVIEW,
    build_contract_block,
    build_depth_profile_meta,
    build_profile_summaries,
    get_profile,
    normalize_depth,
    resolve_role_section,
)


class TestNormalizeDepth:
    @pytest.mark.parametrize(
        "raw,expected",
        [
            (1, "快速"),
            (3, "标准"),
            (5, "深度"),
            ("1", "快速"),
            ("3", "标准"),
            ("5", "深度"),
            (3.0, "标准"),
            ("快速", "快速"),
            ("深度", "深度"),
            (" 标准 ", "标准"),
        ],
    )
    def test_valid_inputs(self, raw, expected):
        assert normalize_depth(raw) == expected

    @pytest.mark.parametrize(
        "raw,target_level,target_name",
        [
            (2, 3, "标准"),
            (4, 5, "深度"),
            ("2", 3, "标准"),
            ("4", 5, "深度"),
            ("基础", 3, "标准"),
            ("全面", 5, "深度"),
        ],
    )
    def test_retired_levels_raise(self, raw, target_level, target_name):
        """退役档位（五档时代 2/4、基础/全面）显式报错，禁止静默降档。"""
        with pytest.raises(ValueError) as exc_info:
            normalize_depth(raw)
        message = str(exc_info.value)
        assert f"「{target_name}」" in message
        assert "migrate_depth_three_levels" in message

    @pytest.mark.parametrize("raw", [None, 0, 6, 99, "0", "6", "xxx", "", True, 1.5])
    def test_unknown_fallback_to_standard(self, raw):
        assert normalize_depth(raw) == "标准"


class TestGetProfile:
    def test_returns_matching_profile(self):
        assert get_profile("深度").name == "深度"
        assert get_profile(5).level == 5

    def test_unknown_fallback_to_standard(self):
        assert get_profile("不存在的档").name == "标准"
        assert get_profile(None) is DEPTH_PROFILES["标准"]


class TestMatrixValues:
    """矩阵数值断言（三档简化定稿：快速1/标准3/深度5=原深度+全面并集）。"""

    def test_three_profiles_registered(self):
        assert tuple(DEPTH_PROFILES.keys()) == DEPTH_NAMES == ("快速", "标准", "深度")
        assert [DEPTH_PROFILES[n].level for n in DEPTH_NAMES] == [1, 3, 5]

    def test_debate_rounds_monotonic(self):
        rounds = [DEPTH_PROFILES[n].debate_rounds for n in DEPTH_NAMES]
        assert rounds == [1, 2, 3]
        assert rounds == sorted(rounds)

    def test_risk_rounds_all_one(self):
        assert [DEPTH_PROFILES[n].risk_rounds for n in DEPTH_NAMES] == [1] * 3

    def test_execution_modes(self):
        modes = [DEPTH_PROFILES[n].debate_mode for n in DEPTH_NAMES]
        assert modes == [MODE_MULTI_AGENT, MODE_SELF_DEBATE, MODE_SELF_DEBATE]
        risk_modes = [DEPTH_PROFILES[n].risk_mode for n in DEPTH_NAMES]
        assert risk_modes == modes

    def test_parallel_opening_all_on(self):
        assert all(DEPTH_PROFILES[n].parallel_opening for n in DEPTH_NAMES)

    def test_cache_ttl_monotonic(self):
        ttl = [DEPTH_PROFILES[n].cache_ttl_min for n in DEPTH_NAMES]
        assert ttl == [30, 120, 1440]
        assert ttl == sorted(ttl)

    def test_memory_modes(self):
        modes = [DEPTH_PROFILES[n].memory_mode for n in DEPTH_NAMES]
        assert modes == [MEMORY_OFF, MEMORY_SNAPSHOT, MEMORY_SNAPSHOT_DIFF]

    def test_memory_enabled_compat(self):
        enabled = [DEPTH_PROFILES[n].memory_enabled for n in DEPTH_NAMES]
        assert enabled == [False, True, True]

    def test_tool_budget_monotonic(self):
        budget = [DEPTH_PROFILES[n].tool_budget for n in DEPTH_NAMES]
        assert budget == [2, 6, 15]
        assert budget == sorted(budget)

    def test_data_scope(self):
        scopes = [DEPTH_PROFILES[n].data_scope for n in DEPTH_NAMES]
        assert scopes == ["basic", "standard", "comprehensive"]

    def test_model_tier(self):
        tiers = [DEPTH_PROFILES[n].model_tier for n in DEPTH_NAMES]
        assert tiers == ["quick", "mixed", "deep"]

    def test_nodes_progression(self):
        # 快速无风险会审/情景试算；标准起全流程；深度与标准同为全流程
        quick = DEPTH_PROFILES["快速"].nodes
        standard = DEPTH_PROFILES["标准"].nodes
        deep = DEPTH_PROFILES["深度"].nodes
        assert NODE_RISK_REVIEW not in quick
        assert NODE_SCENARIO_SIM not in quick
        assert NODE_SCENARIO_SIM in standard
        assert deep == standard

    def test_output_spec_distinct_and_nonempty(self):
        specs = [DEPTH_PROFILES[n].output_spec for n in DEPTH_NAMES]
        assert all(specs)
        assert len(set(specs)) == 3

    def test_deep_profile_merges_old_deep_and_full(self):
        """深度档 = 原深度(4) + 全面(5) 并集：成本取原全面档上限。"""
        deep = DEPTH_PROFILES["深度"]
        assert deep.tool_budget == 15
        assert deep.model_tier == "deep"
        assert deep.data_scope == "comprehensive"
        assert deep.cache_ttl_min == 1440
        assert deep.memory_mode == MEMORY_SNAPSHOT_DIFF
        # 产出规范含原深度档（证据链/反例/失效条件）与原全面档（信息缺口/观察建议/附录）要素
        assert "证据链" in deep.output_spec
        assert "反例" in deep.output_spec
        assert "失效条件" in deep.output_spec
        assert "信息缺口" in deep.output_spec
        assert "观察建议" in deep.output_spec
        assert "附录" in deep.output_spec


class TestContractBlock:
    """M2.1 档位契约块（build_contract_block / resolve_role_section）。"""

    def test_common_contract_lines(self):
        block = build_contract_block(DEPTH_PROFILES["标准"], "market_analyst_v2")
        assert "【本档分析契约：标准档】" in block
        assert DEPTH_PROFILES["标准"].output_spec in block
        assert CONTRACT_DISCIPLINE_LINE in block
        assert "本档不含环节：无" in block

    def test_skipped_nodes_listed(self):
        quick = build_contract_block(DEPTH_PROFILES["快速"], "market_analyst_v2")
        assert "本档不含环节：风险会审、情景试算（" in quick
        standard = build_contract_block(DEPTH_PROFILES["标准"], "market_analyst_v2")
        assert "本档不含环节：无" in standard

    def test_analyst_role_section_by_level(self):
        quick = build_contract_block(DEPTH_PROFILES["快速"], "market_analyst_v2")
        assert "读数密度" in quick
        assert "仅列核心读数" in quick
        standard = build_contract_block(DEPTH_PROFILES["标准"], "fundamentals_analyst_v2")
        assert "完整数据表" in standard
        deep = build_contract_block(DEPTH_PROFILES["深度"], "market_analyst_v2")
        assert "证据来源与强度" in deep

    def test_debate_role_section_by_level(self):
        quick = build_contract_block(DEPTH_PROFILES["快速"], "bull_researcher_v2")
        assert "单轮发言" in quick
        standard = build_contract_block(DEPTH_PROFILES["标准"], "bear_researcher_v2")
        assert "回应闭环" in standard
        assert "失效条件" not in standard
        deep = build_contract_block(DEPTH_PROFILES["深度"], "research_self_debate_v2")
        assert "回应闭环" in deep
        assert "失效条件" in deep

    def test_review_role_section(self):
        multi_path = build_contract_block(DEPTH_PROFILES["标准"], "risky_analyst_v2")
        assert "单轮质证" in multi_path
        self_path = build_contract_block(DEPTH_PROFILES["深度"], "risk_self_debate_v2")
        assert "单轮质证" in self_path

    def test_integration_role_section_by_level(self):
        standard = build_contract_block(DEPTH_PROFILES["标准"], "research_manager_v2")
        assert "整合要求" in standard
        assert "分歧与信息缺口（各至少 1 项）" in standard
        deep = build_contract_block(DEPTH_PROFILES["深度"], "research_manager_v2")
        assert "完整列出分歧清单" in deep

    def test_report_section_for_trader(self):
        block = build_contract_block(DEPTH_PROFILES["深度"], "trader_v2")
        assert "报告章节要求" in block
        assert "章节清单" in block

    def test_unregistered_agent_common_contract_only(self):
        block = build_contract_block(DEPTH_PROFILES["标准"], "risk_manager_v2")
        assert "【本档分析契约" in block
        assert "读数密度" not in block
        assert "交锋要求" not in block
        assert "审阅要求" not in block
        assert "整合要求" not in block

    def test_resolve_role_section_empty_for_unknown(self):
        assert resolve_role_section("some_agent_v3", 3) == ""
        assert resolve_role_section("", 3) == ""
        assert resolve_role_section(None, 3) == ""


class TestBuildDepthProfileMeta:
    """M4.2：报告元数据（档位/环节清单/执行形态/实际轮数）。"""

    @pytest.mark.parametrize(
        "raw,expected_depth,expected_level",
        [
            ("快速", "快速", 1),
            (3, "标准", 3),
            ("5", "深度", 5),
            (None, "标准", 3),  # 未知输入回退标准
        ],
    )
    def test_depth_and_level(self, raw, expected_depth, expected_level):
        meta = build_depth_profile_meta(raw)
        assert meta["depth"] == expected_depth
        assert meta["level"] == expected_level

    def test_manifest_matches_profile_nodes(self):
        meta = build_depth_profile_meta("快速")
        statuses = {entry["node_id"]: entry["status"] for entry in meta["manifest"]}
        # 快速档不含情景试算与风险会审，对应节点置 skipped 留痕
        assert statuses["scenario_simulator_v2"] == "skipped"
        assert statuses["risk_debate"] == "skipped"
        assert statuses["risky_analyst_v2"] == "skipped"
        # 启用环节照常 included
        assert statuses["trader_v2"] == "included"
        assert statuses["research_manager_v2"] == "included"

        deep_meta = build_depth_profile_meta("深度")
        assert all(e["status"] == "included" for e in deep_meta["manifest"])

    def test_execution_mode_and_rounds(self):
        quick = build_depth_profile_meta("快速")
        assert quick["debate_mode"] == MODE_MULTI_AGENT
        assert quick["risk_mode"] == MODE_MULTI_AGENT
        assert quick["debate_rounds"] == 1
        assert quick["risk_rounds"] == 1

        deep = build_depth_profile_meta("深度")
        assert deep["debate_mode"] == MODE_SELF_DEBATE
        assert deep["risk_mode"] == MODE_SELF_DEBATE
        assert deep["debate_rounds"] == 3
        assert deep["risk_rounds"] == 1


class TestBuildProfileSummaries:
    """M4.1：前端档位选择器差异说明数据源。"""

    def test_three_summaries_in_order(self):
        summaries = build_profile_summaries()
        assert [s["name"] for s in summaries] == list(DEPTH_NAMES)
        assert [s["level"] for s in summaries] == [1, 3, 5]

    def test_stage_partition_covers_all_labels(self):
        for summary in build_profile_summaries():
            profile = DEPTH_PROFILES[summary["name"]]
            assert summary["included_stages"] and summary["output_spec"] == profile.output_spec
            # 环节清单恰好切分全部环节展示名，无重复无遗漏
            combined = summary["included_stages"] + summary["skipped_stages"]
            assert sorted(combined) == sorted(set(combined))
            assert len(combined) == 5

    def test_quick_profile_declares_skipped_stages(self):
        quick = build_profile_summaries()[0]
        assert "风险会审" in quick["skipped_stages"]
        assert "情景试算" in quick["skipped_stages"]
        assert "多空辩论" in quick["included_stages"]

        deep = build_profile_summaries()[-1]
        assert deep["skipped_stages"] == []


class _FakeInsertResult:
    inserted_id = "fake_object_id"


class _FakeCollection:
    def __init__(self):
        self.docs = []

    async def insert_one(self, document):
        self.docs.append(document)
        return _FakeInsertResult()


class _FakeDB:
    def __init__(self):
        self.analysis_reports = _FakeCollection()
        self._collections = {}

    def __getitem__(self, name):
        return self._collections.setdefault(name, _FakeCollection())


class TestSaveReportDepthProfileMeta:
    """M4.2 落库：save_analysis_report 的 depth_profile 元数据。"""

    def _save(self, research_depth):
        import asyncio

        from app.utils.report_saver import save_analysis_report

        db = _FakeDB()
        analysis_id = asyncio.run(
            save_analysis_report(
                db,
                "000001",
                "平安银行",
                "A股",
                "test-model",
                reports={"market_report": "测试报告内容" * 5},
                decision={"analysis_view": "中性"},
                recommendation="测试结论",
                confidence_score=0.8,
                risk_level="中",
                research_depth=research_depth,
            )
        )
        assert analysis_id
        return db.analysis_reports.docs[0]

    def test_document_contains_depth_profile(self):
        doc = self._save(5)
        meta = doc["depth_profile"]
        assert meta["depth"] == "深度"
        assert meta["level"] == 5
        assert meta["debate_mode"] == MODE_SELF_DEBATE
        assert isinstance(meta["manifest"], list) and meta["manifest"]
        # 与 build_depth_profile_meta 同源
        assert meta == build_depth_profile_meta("深度")

    def test_legacy_default_depth_standard(self):
        doc = self._save("标准")
        assert doc["research_depth"] == "标准"
        assert doc["depth_profile"]["depth"] == "标准"
