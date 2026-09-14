# -*- coding: utf-8 -*-
"""业务验收器 list[dict] 输出支持的单测。

背景（dongchedi 事故现场）：生成的 Skill 按 spec.expected_output.type="list[dict]"
正确返回了记录列表（month/rank/manufacturer_name/model_name/sales_volume 全部非空），
但 DefaultBusinessVerifier 的两处 dict 假设把正确实现误杀：
① _resolve_target 对 list 输出直接返回 None → required_field 全部误判失败；
② status_success 只认 dict（output.get("status")）→ list 输出必然失败。
导致第 2/3 轮迭代在输出完全正确的情况下 business_score=3.0、passed=False。
"""
from core.tools.external.business_verifier import DefaultBusinessVerifier
from core.tools.external.skill_spec import (
    ExpectedOutput,
    SandboxResult,
    SkillSpec,
    ValidationCheck,
)


def _verifier() -> DefaultBusinessVerifier:
    # 不传 provider：LLM 业务验收跳过，聚焦纯规则行为
    return DefaultBusinessVerifier(llm_client=None, provider=None)


def _dongchedi_spec() -> SkillSpec:
    return SkillSpec(
        tool_id="dongchedi_manufacturer_model_monthly_sales",
        display_name="懂车帝厂商车型月度销量数据查询工具",
        description="调用懂车帝公开的全国汽车销量榜接口，获取指定厂商旗下车型的月度销量及排名信息",
        category="utility",
        data_source="dongchedi",
        expected_output=ExpectedOutput(
            type="list[dict]",
            fields=["month", "rank", "manufacturer_name", "model_name", "sales_volume", "raw_data"],
        ),
        validation_checks=[
            ValidationCheck(
                name="status_success",
                description="接口请求与数据处理必须成功，无异常抛出",
                check_type="status_success",
                rule_level="output",
                blocking=True,
                value_path="output",
                forbid_null=False,
            ),
            *[
                ValidationCheck(
                    name=f"required_field:{f}",
                    description=f"成功输出时每条记录的{f}字段不可缺失且非空",
                    check_type="required_field",
                    rule_level="data",
                    blocking=True,
                    field=f,
                    value_path="data",
                    forbid_null=True,
                )
                for f in ("month", "rank", "manufacturer_name", "model_name", "sales_volume", "raw_data")
            ],
        ],
    )


def _dongchedi_output():
    return [
        {
            "month": "202608", "rank": 1, "manufacturer_name": "吉利银河",
            "model_name": "星愿", "sales_volume": 39651,
            "raw_data": {"series_id": 20154, "count": 39651, "brand_name": "吉利银河"},
        },
        {
            "month": "202608", "rank": 2, "manufacturer_name": "零跑汽车",
            "model_name": "零跑A10", "sales_volume": 30652,
            "raw_data": {"series_id": 9267, "count": 30652, "brand_name": "零跑汽车"},
        },
    ]


class TestListDictOutput:
    """list[dict] 输出（本案例 spec.expected_output.type）的验收行为。"""

    def test_correct_list_output_passes_all_checks(self):
        """事故现场复刻：输出完全正确的 list[dict] 必须通过全部验收。"""
        result = _verifier().verify(
            SandboxResult(success=True, output=_dongchedi_output()),
            _dongchedi_spec(),
        )
        assert result.passed is True
        assert result.business_score == 10.0
        assert result.failures == []

    def test_empty_list_fails_field_checks(self):
        result = _verifier().verify(
            SandboxResult(success=True, output=[]),
            _dongchedi_spec(),
        )
        assert result.passed is False
        # 空列表：status 视为成功，但字段检查失败（无可检查的结构化对象）
        assert any(f.rule_id.startswith("required_field") for f in result.failures)

    def test_list_first_record_missing_field_fails(self):
        output = _dongchedi_output()
        output[0].pop("month")
        result = _verifier().verify(SandboxResult(success=True, output=output), _dongchedi_spec())
        assert result.passed is False
        assert any("month" in f.message for f in result.failures)

    def test_list_first_record_null_field_fails(self):
        output = _dongchedi_output()
        output[0]["sales_volume"] = None
        result = _verifier().verify(SandboxResult(success=True, output=output), _dongchedi_spec())
        assert result.passed is False
        assert any("sales_volume" in f.message for f in result.failures)


class TestPlausibilityRawDataExclusion:
    """raw_data 原始回显不参与数值合理性检查（dongchedi 第 2~6 轮误杀修复）。

    事故现场：raw_data 内的接口噪声字段（score/descender_price 榜单模式恒 0）
    被递归收集为"趋势序列"数值，触发'列表内数据全部为 0'误判。
    """

    @staticmethod
    def _spec() -> SkillSpec:
        return SkillSpec(
            tool_id="dongchedi_car_model_monthly_sales",
            display_name="t",
            description="懂车帝车型月度销量查询",
        )

    def test_raw_data_zero_noise_not_flagged(self):
        """raw_data 恒零噪声不得触发全零误判（真实业务数值非零即应通过）。"""
        output = {
            "status": "success", "query_period": "202608", "count": 10, "offset": 0,
            "data": [
                {"query_period": "202608", "rank": i + 1, "model_name": f"m{i}",
                 "manufacturer_name": "厂商", "sales": 30000 - i * 100,
                 "raw_data": {"score": 0, "descender_price": 0, "count": 30000 - i * 100}}
                for i in range(10)
            ],
        }
        result = _verifier().verify(SandboxResult(success=True, output=output), self._spec())
        assert result.passed is True
        assert not any(
            f.rule_id in ("trend_list_all_zeros", "all_zero_values") for f in result.failures
        )

    def test_top_level_all_zero_still_flagged(self):
        """顶层业务字段全零仍应拦截（合理性检查本体不失效）。"""
        output = {
            "status": "success",
            "data": [{"rank": 0, "sales": 0, "volume": 0} for _ in range(3)],
        }
        result = _verifier().verify(SandboxResult(success=True, output=output), self._spec())
        assert any(
            f.rule_id in ("trend_list_all_zeros", "all_zero_values") for f in result.failures
        )


class TestDictOutputRegression:
    """dict 输出的既有行为回归（修复不得改变）。"""

    def test_dict_with_status_and_data_passes(self):
        spec = _dongchedi_spec()
        spec.expected_output = ExpectedOutput(type="dict", fields=["month", "sales_volume"])
        spec.validation_checks = [
            ValidationCheck(name="status_success", check_type="status_success",
                            rule_level="output", value_path="output"),
            ValidationCheck(name="required_field:month", check_type="required_field",
                            rule_level="data", field="month", value_path="data", forbid_null=True),
        ]
        result = _verifier().verify(
            SandboxResult(success=True, output={"status": "success", "data": [{"month": "202608", "sales_volume": 1}]}),
            spec,
        )
        assert result.passed is True

    def test_dict_error_status_still_fails(self):
        spec = _dongchedi_spec()
        spec.validation_checks = [
            ValidationCheck(name="status_success", check_type="status_success",
                            rule_level="output", value_path="output"),
        ]
        result = _verifier().verify(
            SandboxResult(success=True, output={"status": "error", "message": "boom"}),
            spec,
        )
        assert result.passed is False
        assert any(f.rule_id == "status_success" for f in result.failures)

    def test_flat_dict_fallback_target_unchanged(self):
        """扁平 dict（无 value_path 嵌套 key）回退 output 自身的既有行为保持。"""
        spec = _dongchedi_spec()
        spec.validation_checks = [
            ValidationCheck(name="required_field:month", check_type="required_field",
                            rule_level="data", field="month", value_path="data", forbid_null=True),
        ]
        result = _verifier().verify(
            SandboxResult(success=True, output={"month": "202608", "sales_volume": 39651}),
            spec,
        )
        assert result.passed is True

    def test_sandbox_failure_short_circuits(self):
        result = _verifier().verify(
            SandboxResult(success=False, error="boom"),
            _dongchedi_spec(),
        )
        assert result.passed is False
        assert result.business_score == 0.0
