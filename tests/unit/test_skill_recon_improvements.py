# -*- coding: utf-8 -*-
"""Skill 生成器侦察层三个改进点的单测。

背景（dongchedi 车型销量案例复盘）：需求指定了目录外数据源"懂车帝"，
侦察层却——
① 把 7 个向量召回的无关股票工具当作"数据源已由 helper 覆盖"；
② 把目录外来源静默 fallback 成 AKShare/Tushare 推荐；
③ 规格臆造了接口不存在的 model_id/manufacturer_id 等验收字段且未告警。

本测试锁定三个改进点：
1. 需求类型分流（external_api vs local_data）；
2. 目录外数据源显式标注（unknown_data_source），不再 fallback 凑数；
3. 验收字段与命中资产能力一致性校验（低覆盖降置信度 + 澄清提示）。
"""
from types import SimpleNamespace

from core.tools.external.external_data_source_catalog import is_known_external_source
from core.tools.external.reconnaissance_controller import DefaultReconnaissanceController
from core.tools.external.requirement_analyzer import RequirementAnalyzer
from core.tools.external.skill_spec import (
    ExpectedOutput,
    ImplementationFactReport,
    SkillParameter,
    SkillSpec,
)


def _controller() -> DefaultReconnaissanceController:
    return DefaultReconnaissanceController()


def _dongchedi_spec() -> SkillSpec:
    """复刻事故现场：指定目录外数据源的车型销量需求。"""
    return SkillSpec(
        tool_id="dongchedi_manufacturer_monthly_model_sales",
        display_name="懂车帝厂商旗下车型月度销量查询",
        description=(
            "基于懂车帝公开的全国汽车销量榜单HTTP接口，支持指定单月、近半年、近一年统计维度，"
            "通过分页拉取、厂商过滤逻辑，获取指定厂商旗下所有车系对应车型的销量、全国排名等数据；"
            "接口无需身份认证，仅需构造合法请求头即可访问。"
        ),
        category="market",
        data_source="dongchedi",
        parameters=[
            SkillParameter(name="manufacturer", type="string", description="目标厂商名称或懂车帝平台厂商ID"),
            SkillParameter(name="month_dim", type="string", description="统计维度 YYYYMM / 500 / 1000"),
        ],
        expected_output=ExpectedOutput(
            type="list[dict]",
            fields=["month_dim", "rank", "series_id", "series_name", "sales_volume", "data_source"],
        ),
    )


def _news_spec() -> SkillSpec:
    """已知数据源 + 本地数据类需求（回归基线，行为不应改变）。"""
    return SkillSpec(
        tool_id="get_eastmoney_news",
        display_name="东方财富个股新闻",
        description="查询东方财富个股新闻列表，返回标题、链接、发布时间",
        category="news",
        data_source="akshare",
        expected_output=ExpectedOutput(
            type="list[dict]",
            fields=["title", "url", "publish_time"],
        ),
    )


class TestIsKnownExternalSource:
    """目录来源判定（改进点 1/2 的公共基础）。"""

    def test_known_sources(self):
        for name in ("akshare", "AKShare", "tushare", "东方财富", "eastmoney", "finnhub", "google news"):
            assert is_known_external_source(name) is True, name

    def test_unknown_sources(self):
        for name in ("dongchedi", "懂车帝", "amap", ""):
            assert is_known_external_source(name) is False, name


class TestRequirementModeClassification:
    """改进点 1：需求类型分流。"""

    def test_unknown_data_source_routes_to_external_api(self):
        assert _controller()._classify_requirement_mode(_dongchedi_spec()) == "external_api"

    def test_url_in_description_routes_to_external_api(self):
        spec = SkillSpec(
            tool_id="t_x", display_name="t", category="utility",
            description="调用 https://api.example.com/v1/data 接口获取数据",
        )
        assert _controller()._classify_requirement_mode(spec) == "external_api"

    def test_public_api_keyword_routes_to_external_api(self):
        spec = SkillSpec(
            tool_id="t_x", display_name="t", category="utility",
            description="通过公开接口获取汽车销量数据",
        )
        assert _controller()._classify_requirement_mode(spec) == "external_api"

    def test_known_source_stays_local(self):
        assert _controller()._classify_requirement_mode(_news_spec()) == "local_data"

    def test_plain_stock_spec_stays_local(self):
        spec = SkillSpec(
            tool_id="get_pledge_risk", display_name="股权质押风险",
            description="查询个股股权质押风险画像", category="fundamentals",
        )
        assert _controller()._classify_requirement_mode(spec) == "local_data"


class TestBuildRecommendationsUnknownSource:
    """改进点 2：目录外数据源显式标注，不 fallback 凑数。"""

    def test_unknown_source_returns_empty_and_flag(self):
        rec = RequirementAnalyzer().build_recommendations(spec=_dongchedi_spec())
        assert rec["unknown_data_source"] == "dongchedi"
        assert rec["stock_collections"] == []
        assert rec["external_sources"] == []
        # 需求模式下发给前端：external_api 模式不展示本地/目录资产
        assert rec["requirement_mode"] == "external_api"

    def test_known_source_keeps_recommendations(self):
        rec = RequirementAnalyzer().build_recommendations(spec=_news_spec())
        assert rec["unknown_data_source"] == ""
        assert "akshare" in rec["external_sources"]
        assert rec["requirement_mode"] == "local_data"


class TestExternalApiModeRecon:
    """改进点 1+2+3 在规则侦察主流程的端到端效果。"""

    def test_dongchedi_flow(self):
        # 伪向量召回（模拟事故现场的无关股票工具）
        fake_hits = [
            SimpleNamespace(
                capability={"source_type": "builtin_tool", "bindable": True,
                            "registry_tool_id": f"tool_{i}", "name": f"tool_{i}",
                            "description": "股票工具"},
                score=0.42,
            )
            for i in range(3)
        ]
        report = _controller()._rule_based_analyze(_dongchedi_spec(), capability_hits=fake_hits)

        # 改进点 1：策略切换为外部 API 集成话术；向量召回的本地工具不被采纳
        assert "外部 HTTP API 集成" in report.recommended_strategy
        assert "dongchedi" in report.recommended_strategy
        assert report.available_helpers == []
        assert any("未采纳" in f.fact for f in report.schema_facts)

        # 改进点 2：目录外来源显式登记运行时缺口与备注，而非静默 fallback
        assert any(g.path == "external_data_source:dongchedi" for g in report.runtime_gaps)
        assert any("不在系统已知外部数据源目录" in n for n in report.notes)
        # 推荐集合/外部源不再出现股票资产凑数
        assert not any("market_quotes" in f.fact for f in report.schema_facts)

        # 改进点 3：验收字段提示"以接口实际响应为准"
        assert any("以外部接口实际响应为准" in n for n in report.notes)

        # 置信度不再因本地集合样本虚高（本地集合已被清空）
        assert report.confidence <= 0.45

    def test_local_mode_behavior_unchanged(self, monkeypatch):
        """回归：已知来源 + 本地数据类需求的侦察行为不变。"""
        import core.skill_runtime.project_access as pa

        monkeypatch.setattr(
            pa, "inspect_stock_collection_schema",
            lambda *a, **k: {"sample_count": 3, "top_level_fields": ["title", "url", "publish_time"]},
        )
        report = _controller()._rule_based_analyze(_news_spec(), capability_hits=None)
        assert report.recommended_strategy.startswith("优先使用 skill_runtime")
        # 集合样本字段照常注入（用于字段覆盖池）
        assert report.sample_fields.get("stock_news") == ["title", "url", "publish_time"]
        # 验收字段全部可由集合产出 → 无覆盖告警
        assert not any("验收字段覆盖不足" in n for n in report.notes)


class TestFieldCoverageValidation:
    """改进点 3：验收字段一致性校验的单元行为。"""

    def _spec_with_fields(self, fields):
        return SkillSpec(
            tool_id="t_c", display_name="t", description="测试字段覆盖",
            expected_output=ExpectedOutput(fields=fields),
        )

    def test_low_coverage_flags_and_lowers_confidence(self):
        report = ImplementationFactReport(confidence=0.65)
        report.sample_fields = {"stock_news": ["title", "url", "publish_time"]}
        _controller()._validate_expected_field_coverage(
            self._spec_with_fields(["title", "sentiment_score_xyz", "importance_level_xyz"]),
            report, "local_data",
        )
        assert any("验收字段覆盖不足" in n for n in report.notes)
        assert any("sentiment_score_xyz" in n for n in report.notes)
        assert report.confidence <= 0.45

    def test_full_coverage_no_warning(self):
        report = ImplementationFactReport(confidence=0.65)
        report.sample_fields = {"stock_news": ["title", "url"]}
        _controller()._validate_expected_field_coverage(
            self._spec_with_fields(["title", "url"]), report, "local_data",
        )
        assert not any("验收字段覆盖不足" in n for n in report.notes)
        assert report.confidence == 0.65

    def test_external_mode_advises_without_local_check(self):
        """external_api 模式：字段来自外部接口，只提示核对、不按本地覆盖压分。"""
        report = ImplementationFactReport(confidence=0.65)
        _controller()._validate_expected_field_coverage(
            self._spec_with_fields(["model_id", "model_name", "manufacturer_id"]),
            report, "external_api",
        )
        assert any("以外部接口实际响应为准" in n for n in report.notes)
        assert report.confidence == 0.65

    def test_no_expected_fields_is_noop(self):
        report = ImplementationFactReport(confidence=0.65)
        _controller()._validate_expected_field_coverage(
            self._spec_with_fields([]), report, "local_data",
        )
        assert report.notes == []
        assert report.confidence == 0.65
