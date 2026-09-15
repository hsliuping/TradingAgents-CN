# -*- coding: utf-8 -*-
"""升级补丁模式（upgrade_patch）单元测试。

核心回归：升级会话曾把父版本多轮验证的 `rank_data_type: int = 11`
重写成字符串「月度销量榜」直接发给接口，接口静默回退热度榜，
业务校验判「月销 102 万辆」不合理，死循环 4 次尝试。
补丁模式下 LLM 只输出 delta，未提及的字段由 apply_upgrade_patch
从父契约原样继承——想重写都没有输出通道。
"""

import json

from core.tools.external.requirement_analyzer import RequirementAnalyzer
from core.tools.external.upgrade_patch import (
    apply_upgrade_patch,
    build_upgrade_patch_prompt,
)


def _parent_contract() -> dict:
    """父版本契约：真实场景（懂车帝月销榜 v1，多轮验证通过后落库的形态）"""
    return {
        "tool_id": "dongchedi_car_monthly_sales_rank",
        "root_tool_id": "dongchedi_car_monthly_sales_rank",
        "new_tool_id": "dongchedi_car_monthly_sales_rank_v2",
        "new_version": 2,
        "display_name": "懂车帝车型月销量查询",
        "description": "通过懂车帝PC端车型销量排行接口，获取全国车型月度销量数据",
        "category": "market",
        "data_source": "dongchedi",
        "parameters": [
            {"name": "month", "type": "string", "description": "月份 YYYYMM", "required": True, "default": None, "enum": None},
            {"name": "rank_data_type", "type": "integer", "description": "榜单类型，固定为 11 表示全国月度销量榜", "required": True, "default": None, "enum": None},
            {"name": "count", "type": "integer", "description": "单次返回条数，默认 100", "required": False, "default": None, "enum": None},
            {"name": "offset", "type": "integer", "description": "翻页偏移量", "required": False, "default": None, "enum": None},
        ],
        "expected_output": {
            "type": "list[dict]",
            "fields": ["rank", "model_name", "brand", "sales_volume", "month"],
            "description": "车型月度销量排行",
        },
        "constraints": [
            "【接口规格 — 必须原样使用】接口 URL: https://www.dongchedi.com/motor/pc/car/rank_data（路径严禁改写）",
            "请求需携带 User-Agent 和 Referer 请求头",
            "rank_data_type 需为 11 才能获取全国月度销量榜，缺省可能是关注度榜",
        ],
        "test_input": {"month": "202501", "rank_data_type": 11},
        "code": (
            "def dongchedi_car_monthly_sales_rank(month='202608', rank_data_type=11, ...):\n"
            "    if rank_data_type != 11:\n"
            "        return _error('INVALID_PARAM', 'rank_data_type 必须为整数 11')\n"
        ),
    }


# 真实升级需求的补丁：只加售价区间，其余不动
_PRICE_PATCH = {
    "upgrade_summary": "输出新增售价区间字段",
    "change_points": ["输出字段新增 price_range（厂商指导价区间）"],
    "output_field_changes": {"add": ["price_range"], "remove": []},
    "parameter_changes": {"add": [], "modify": [], "remove": []},
    "constraint_additions": ["若接口返回缺少售价区间，price_range 置为空字符串"],
}


class TestApplyUpgradePatch:
    def test_verified_param_contract_cannot_be_rewritten(self):
        """核心回归：补丁没提 rank_data_type → 新 spec 原样继承 int=11 契约。

        全量重生成模式曾把它重写成 string「月度销量榜」直接发给接口，
        接口静默回退热度榜导致死循环——补丁模式下该字段没有输出通道。
        """
        spec = apply_upgrade_patch(_parent_contract(), dict(_PRICE_PATCH))

        params = {p.name: p for p in spec.parameters}
        assert params["rank_data_type"].type == "integer"
        assert "固定为 11" in params["rank_data_type"].description
        # count/offset 等父版本参数不丢失
        assert set(params) == {"month", "rank_data_type", "count", "offset"}

    def test_parent_constraints_inherited_verbatim(self):
        """父版本接口约束（URL/请求头/取值要求）原样继承，不靠 LLM 转述"""
        spec = apply_upgrade_patch(_parent_contract(), dict(_PRICE_PATCH))

        joined = "\n".join(spec.constraints)
        assert "https://www.dongchedi.com/motor/pc/car/rank_data" in joined
        assert "rank_data_type 需为 11" in joined
        assert "User-Agent 和 Referer" in joined
        # 补丁新增约束在列
        assert "price_range 置为空字符串" in joined
        # 迭代版本说明自动追加
        assert "本 Skill 是 dongchedi_car_monthly_sales_rank 的迭代优化版本" in joined

    def test_output_fields_add_only(self):
        spec = apply_upgrade_patch(_parent_contract(), dict(_PRICE_PATCH))
        assert spec.expected_output.fields == [
            "rank", "model_name", "brand", "sales_volume", "month", "price_range",
        ]

    def test_version_naming_from_contract(self):
        """tool_id/display_name/版本号按服务层计算的值确定（与 _save_skill 一致）"""
        spec = apply_upgrade_patch(_parent_contract(), dict(_PRICE_PATCH))
        assert spec.tool_id == "dongchedi_car_monthly_sales_rank_v2"
        assert spec.display_name == "懂车帝车型月销量查询 v2"
        assert spec.parent_skill_id == "dongchedi_car_monthly_sales_rank"
        assert spec.version == 2

    def test_display_name_strips_old_suffix(self):
        """父版本显示名已带 v2 后缀时先剥离再加新后缀（v2 → v3 不叠加）"""
        contract = _parent_contract()
        contract["display_name"] = "懂车帝车型月销量查询 v2"
        contract["new_version"] = 3
        contract["new_tool_id"] = "dongchedi_car_monthly_sales_rank_v3"
        spec = apply_upgrade_patch(contract, dict(_PRICE_PATCH))
        assert spec.display_name == "懂车帝车型月销量查询 v3"

    def test_modify_param_only_touches_listed_fields(self):
        """modify 是部分更新：只改列出的字段，type/default/required 原样保留"""
        patch = {
            "upgrade_summary": "月份参数描述更新",
            "change_points": ["参数 month 描述更新"],
            "parameter_changes": {
                "add": [],
                "modify": [{"name": "month", "description": "统计月份，支持 500/1000 聚合值"}],
                "remove": [],
            },
        }
        spec = apply_upgrade_patch(_parent_contract(), patch)
        month = {p.name: p for p in spec.parameters}["month"]
        assert month.description == "统计月份，支持 500/1000 聚合值"
        assert month.type == "string"
        assert month.required is True

    def test_add_and_remove_params(self):
        patch = {
            "upgrade_summary": "参数调整",
            "change_points": ["新增 brand", "删除 count"],
            "parameter_changes": {
                "add": [{"name": "brand", "type": "string", "description": "品牌筛选", "required": False}],
                "modify": [],
                "remove": ["count"],
            },
        }
        spec = apply_upgrade_patch(_parent_contract(), patch)
        names = {p.name for p in spec.parameters}
        assert "brand" in names
        assert "count" not in names
        assert "rank_data_type" in names  # 未提及的不动

    def test_test_input_merge_and_validation_checks(self):
        """测试输入父+子合并；验收检查从最终输出字段推导（存在性检查）"""
        patch = {
            "upgrade_summary": "换测试月份",
            "change_points": [],
            "test_input_updates": {"month": "202608"},
        }
        spec = apply_upgrade_patch(_parent_contract(), patch)
        assert spec.test_input["month"] == "202608"
        assert spec.test_input["rank_data_type"] == 11  # 父版本值保留

        check_names = [c.name for c in spec.validation_checks]
        assert "status_success" in check_names
        assert "required_field:sales_volume" in check_names
        # 存在性检查（forbid_null=False）：允许合法空值（如 price_range 空字符串）
        sv_check = next(c for c in spec.validation_checks if c.name == "required_field:sales_volume")
        assert sv_check.forbid_null is False

    def test_change_points_fallback_to_applied_notes(self):
        """LLM 没给 change_points 时，用套用过程记录的实际变更兜底"""
        patch = {"upgrade_summary": "s", "output_field_changes": {"add": ["price_range"]}}
        spec = apply_upgrade_patch(_parent_contract(), patch)
        notes = spec.metadata["upgrade_change_points"]
        assert any("price_range" in n for n in notes)

    def test_change_points_metadata_for_confirm_page(self):
        spec = apply_upgrade_patch(_parent_contract(), dict(_PRICE_PATCH))
        assert spec.metadata["upgrade_mode"] == "patch"
        assert spec.metadata["upgrade_change_points"] == [
            "输出字段新增 price_range（厂商指导价区间）"
        ]
        assert spec.metadata["upgrade_parent_tool_id"] == "dongchedi_car_monthly_sales_rank"


class TestBuildUpgradePatchPrompt:
    def test_prompt_contains_full_code_and_constraints(self):
        """读后写：父版本完整代码（不截断）+ 契约全部进 prompt"""
        contract = _parent_contract()
        prompt = build_upgrade_patch_prompt(contract, "用户：增加售价区间")
        assert "rank_data_type != 11" in prompt  # 代码关键校验逻辑
        assert "固定为 11" in prompt               # 参数契约
        assert "rank_data_type 需为 11" in prompt  # 约束
        assert "增加售价区间" in prompt
        # 输出格式是补丁 JSON，不是全量 spec
        assert "parameter_changes" in prompt
        assert "没有权限重写父版本契约" in prompt

    def test_prompt_contract_json_parseable(self):
        contract = _parent_contract()
        prompt = build_upgrade_patch_prompt(contract, "升级")
        # prompt 中的契约 JSON 块可解析且包含参数定义
        block = prompt.split("```json\n")[1].split("\n```")[0]
        parsed = json.loads(block)
        assert any(p["name"] == "rank_data_type" for p in parsed["parameters"])


class TestAnalyzerRouting:
    def test_generate_spec_routes_to_patch_mode(self, monkeypatch):
        """传入 parent_contract 时 _generate_spec 优先走补丁模式，不碰全量路径"""
        analyzer = RequirementAnalyzer()

        def _fake_upgrade(conversation, parent_contract):
            return apply_upgrade_patch(parent_contract, dict(_PRICE_PATCH))

        def _forbid_full_path(*args, **kwargs):
            raise AssertionError("不应走到全量规格生成路径（补丁模式应短路返回）")

        monkeypatch.setattr(analyzer, "_generate_upgrade_spec", _fake_upgrade)
        monkeypatch.setattr(analyzer, "_chat_with_quick_fallback", _forbid_full_path)

        spec = analyzer._generate_spec(
            "对话内容", fact_report=None, session=None,
            parent_contract=_parent_contract(),
        )
        assert spec is not None
        assert spec.metadata["upgrade_mode"] == "patch"
        # 未提及的字段从父契约继承
        params = {p.name: p for p in spec.parameters}
        assert params["rank_data_type"].type == "integer"

    def test_generate_spec_falls_back_when_patch_fails(self, monkeypatch):
        """补丁生成失败时降级为全量生成（父契约注入 prompt）"""
        analyzer = RequirementAnalyzer()

        def _broken_upgrade(conversation, parent_contract):
            return None

        captured = {}

        def _fake_full_chat(messages, stage=""):
            captured["prompt"] = messages[0].content
            return "{}"  # 让全量路径解析失败 → _raise_analysis_error

        monkeypatch.setattr(analyzer, "_generate_upgrade_spec", _broken_upgrade)
        monkeypatch.setattr(analyzer, "_chat_with_quick_fallback", _fake_full_chat)

        session = type("S", (), {"iterate_skill_id": "dongchedi_car_monthly_sales_rank"})()
        try:
            analyzer._generate_spec(
                "对话内容", fact_report=None, session=session,
                parent_contract=_parent_contract(),
            )
            raised = False
        except Exception:
            raised = True
        # 全量路径被走到，且父契约注入了降级 prompt
        assert raised
        assert "父版本契约" in captured.get("prompt", "")
        assert "固定为 11" in captured.get("prompt", "")
