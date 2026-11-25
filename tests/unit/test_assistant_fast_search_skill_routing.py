# -*- coding: utf-8 -*-
"""近期搜索快路径 vs 用户生成外部 Skill 的路由让路测试。

背景（真实缺陷）：用户问「问界各车型最近半年销量变化」，被股票时代的
关键词快路径（"最近"+"变化"）在 LLM 工具选择之前劫持去网页搜索，
已安装的懂车帝销量 Skill 完全没有出场机会。

修复：快路径命中关键词后，先用注册表里 source=generated 的 Skill 元数据
做数据驱动的领域词匹配，能被专用 Skill 承接就让路。
"""

from types import SimpleNamespace
from unittest.mock import patch

from app.services.intelligent_assistant_service import (
    _domain_terms,
    _matches_generated_skill,
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
