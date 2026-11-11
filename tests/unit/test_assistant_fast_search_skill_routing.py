# -*- coding: utf-8 -*-
"""近期搜索快路径 vs 用户生成外部 Skill / 领域内置工具的路由让路测试。

背景（真实缺陷）：用户问「问界各车型最近半年销量变化」，被股票时代的
关键词快路径（"最近"+"变化"）在 LLM 工具选择之前劫持去网页搜索，
已安装的懂车帝销量 Skill 完全没有出场机会。

修复：快路径命中关键词后，先用注册表里 source=generated 的 Skill 元数据
做数据驱动的领域词匹配，能被专用 Skill 承接就让路。

背景 2（真实缺陷）：用户问「能繁母猪数据 3 个月前的，是否可推定已达到
政府限定数量」，被"现在+是否"劫持去网页搜索，猪周期世界模型证据工具
（capability_tags 含 pig_cycle）连出场机会都没有——修复同上，领域内置
工具元数据匹配让路；现已泛化为四行业标签组
（_matches_industry_cycle_tool：pig/insurance/battery/auto_cycle）。
"""

from types import SimpleNamespace
from unittest.mock import patch

from app.services.intelligent_assistant_service import (
    _domain_terms,
    _matches_generated_skill,
    _matches_industry_cycle_tool,
    _should_use_recent_search,
)


def _skill(tool_id, name, description, when_to_use="", fc_enabled=True):
    return SimpleNamespace(
        id=tool_id,
        name=name,
        description=description,
        when_to_use=when_to_use,
        fc_enabled=fc_enabled,
    )


_DCD_SKILL = _skill(
    "dongchedi_car_monthly_sales_rank",
    "懂车帝全国月度销量榜查询",
    "调用懂车帝全国月度销量榜接口，按月份、榜单类型等参数获取车型销量数据，"
    "并支持按品牌（如问界）筛选各车型月销量。",
)


class TestDomainTerms:
    def test_extracts_chinese_bigrams_and_english_tokens(self):
        terms = _domain_terms("问界M9车型销量")
        assert "问界" in terms
        assert "车型" in terms
        assert "销量" in terms
        assert "m9" in terms

    def test_stopgrams_removed(self):
        terms = _domain_terms("销量数据接口")
        assert "销量" in terms
        assert "数据" not in terms
        assert "接口" not in terms


class TestGeneratedSkillRouting:
    def _registry(self, skills):
        reg = SimpleNamespace(get_external_skills=lambda: skills)
        return patch("core.tools.get_tool_registry", lambda: reg)

    def test_dongchedi_sales_question_bypasses_fast_search(self):
        """真实事故句：必须命中懂车帝 Skill，快路径让路"""
        # 先确认这句话本身会命中旧快路径关键词（否则测试无意义）
        msg = "帮我查一下问界各车型最近半年的销量变化情况"
        assert _should_use_recent_search(msg)

        with self._registry([_DCD_SKILL]):
            hit = _matches_generated_skill(msg)
        assert hit is not None
        assert hit[0] == "dongchedi_car_monthly_sales_rank"

    def test_stock_holding_question_still_uses_fast_search(self):
        """股票原场景：与外部 Skill 无领域重合，不应让路"""
        msg = "伯克希尔哈撒韦最新持股变化"
        assert _should_use_recent_search(msg)
        with self._registry([_DCD_SKILL]):
            assert _matches_generated_skill(msg) is None

    def test_single_overlap_not_enough(self):
        """只有一个领域词共现不算命中（防止偶然共现误判）"""
        # 仅含「销量」一个领域交集词
        skill = _skill("x", "某榜", "统计某商品销量")
        with self._registry([skill]):
            # 「最近销量」——与该 skill 只有"销量"一个交集
            assert _matches_generated_skill("最近销量如何变化") is None

    def test_disabled_skill_ignored(self):
        disabled = _skill("x", "懂车帝销量", "问界车型销量", fc_enabled=False)
        with self._registry([disabled]):
            assert _matches_generated_skill("问界车型最近销量变化") is None

    def test_no_external_skills_returns_none(self):
        with self._registry([]):
            assert _matches_generated_skill("问界车型最近销量变化") is None

    def test_generic_non_sales_question_not_routed_to_dcd(self):
        """纯新闻/公告类问题即便提到最近，也不该被领域匹配误抓"""
        msg = "最近有没有什么新公告"
        with self._registry([_DCD_SKILL]):
            assert _matches_generated_skill(msg) is None


# 猪周期工具元数据节选（与真实注册元数据同构，capability_tags 驱动匹配）
_PIG_TOOL = SimpleNamespace(
    id="get_pig_cycle_state",
    name="猪周期六环节状态总览",
    description="只读获取生猪养殖板块猪周期当前状态快照：能繁母猪方向与去化、"
                "猪价、猪粮比、调控政策锚等。",
    when_to_use="当用户询问猪周期阶段、能繁母猪去化，或问能繁数据滞后两个月"
                "能不能推算现在到没到政府调控下限（红线）、政策会不会托底/收储时使用。",
    capability_tags=["pig_cycle", "hog_cycle", "l0_supply"],
    fc_enabled=True,
)


class TestIndustryCycleToolRouting:
    def _registry(self, tools):
        reg = SimpleNamespace(list_all=lambda: tools)
        return patch("core.tools.get_tool_registry", lambda: reg)

    def test_sow_floor_inference_question_bypasses_fast_search(self):
        """真实事故句：被"现在+是否"劫持前必须让路给世界模型工具"""
        msg = ("能繁母猪的数据还是3个月前的，是否可以推定，现在已经达到政府"
               "限定的数量了呢，这两个月数据还没有出，但是去化应该没有停吧，"
               "按原来的几个月的去化速度来看，这个推定成立吗？")
        assert _should_use_recent_search(msg)  # 复现劫持前提
        with self._registry([_PIG_TOOL]):
            hit = _matches_industry_cycle_tool(msg)
        assert hit is not None
        assert hit[0] == "get_pig_cycle_state"

    def test_battery_tool_also_bypasses_fast_search(self):
        """泛化验证：battery_cycle 标签的电池工具同样享受让路"""
        battery_tool = SimpleNamespace(
            id="query_battery_series",
            name="电池产业链原始数据序列查询（材料报价/电芯价格/装机月报）",
            description="只读查询电池产业链 Pro 库里的原始采集与人工台账数据："
                        "锂电材料报价、电芯价格、动力电池装机量。",
            when_to_use="当用户要看碳酸锂/正极材料最新报价、电芯多少钱、"
                        "这个月动力电池装了多少 GWh 时使用。",
            capability_tags=["battery_cycle", "raw_series", "lithium_price"],
            fc_enabled=True,
        )
        msg = "现在的碳酸锂价格是否已经跌到出清带了？后面还会不会继续跌？"
        assert _should_use_recent_search(msg)
        with self._registry([battery_tool]):
            hit = _matches_industry_cycle_tool(msg)
        assert hit is not None
        assert hit[0] == "query_battery_series"

    def test_stock_dividend_question_still_uses_fast_search(self):
        """股票原场景不得被通用虚词误让路（真实回归：描述里"没有"两字曾
        让「牧原分红」误命中；"持有/比例/多少"曾让持股问题误命中）"""
        for msg in ("牧原股份最近有没有分红？", "巴菲特还持有比亚迪吗？最新持股比例是多少？"):
            assert _should_use_recent_search(msg)
            with self._registry([_PIG_TOOL]):
                assert _matches_industry_cycle_tool(msg) is None

    def test_disabled_pig_tool_ignored(self):
        disabled = SimpleNamespace(**{**_PIG_TOOL.__dict__, "fc_enabled": False})
        with self._registry([disabled]):
            assert _matches_industry_cycle_tool("能繁母猪去化到什么程度了") is None

    def test_no_pig_tools_returns_none(self):
        with self._registry([]):
            assert _matches_industry_cycle_tool("能繁母猪去化到什么程度了") is None

    def test_single_overlap_not_enough_for_pig(self):
        """仅"牧原"一个词共现不算命中，普通养殖股问题走原路径"""
        with self._registry([_PIG_TOOL]):
            assert _matches_industry_cycle_tool("牧原股份最近有没有分红？") is None
