# -*- coding: utf-8 -*-
"""估值测算规格生成层单测（A10-D1 件①）

用桩 LLM 覆盖：一次通过、围栏+重试、PE 亏损期修正、垃圾输出、端到端。
"""

import json
import os

import pytest

from core.deliverables.valuation_spec_generator import (
    build_spec_user_prompt,
    extract_json_block,
    generate_valuation_deliverable,
    generate_valuation_spec,
    merge_spec,
)


class StubLLM:
    """按预设顺序返回回复的桩 LLM"""

    def __init__(self, replies):
        self.replies = list(replies)
        self.calls = []

    def chat(self, messages):
        self.calls.append(messages)
        reply = self.replies.pop(0)

        class _R:
            content = reply

        return _R()


BUNDLE = {
    "ticker": "601127",
    "stock_name": "赛力斯",
    "analysis_date": "2026-09-10",
    "current_price": 56.82,
    "share_count": 15.1,
    "financial_history": [
        {"period": "TTM", "revenue": 1716.5, "net_profit": 59.63},
    ],
    "investment_plan": '{"analysis_view": "中性", "summary": "渠道调整与盈利修复待验证，多空证据均衡"}',
    "fundamentals_report": "ROE 回升，毛利率稳定，费用率下降。",
    "bull_report": "新车型放量，2026 年营收有望高增。",
    "bear_report": "利润基数低，竞争加剧压制净利率。",
}

GOOD_OUTPUT = {
    "earnings_forecast": {
        "assumptions": [
            {"period": "2026E", "revenue_growth": 0.22, "net_margin": 0.05,
             "rationale": "新车型放量（乐观研究员），但净利率受竞争压制（审慎研究员）"},
            {"period": "2027E", "revenue_growth": 0.15, "net_margin": 0.055,
             "rationale": "规模效应摊薄费用，净利率温和改善"},
        ]
    },
    "valuation": {
        "scenarios": [
            {"name": "悲观", "method": "PE", "multiple": 12, "eps_period": "2026E",
             "benchmark_basis": "可比整车企业低端约 12 倍",
             "applicability_check": {"passed": True, "notes": ["归母净利润为正"]}},
            {"name": "中性", "method": "PE", "multiple": 18, "eps_period": "2026E",
             "benchmark_basis": "可比整车企业 15-20 倍区间中枢",
             "applicability_check": {"passed": True, "notes": ["归母净利润为正"]}},
            {"name": "乐观", "method": "PE", "multiple": 22, "eps_period": "2027E",
             "benchmark_basis": "可比整车企业区间上沿",
             "applicability_check": {"passed": True, "notes": ["归母净利润为正"]}},
        ],
        "risk_notes": ["测算为情景假设，不构成投资建议"],
    },
}


def test_extract_json_block_variants():
    obj = {"a": 1}
    assert extract_json_block(json.dumps(obj)) == obj
    assert extract_json_block("```json\n" + json.dumps(obj, ensure_ascii=False) + "\n```") == obj
    assert extract_json_block("好的，以下是规格：\n" + json.dumps(obj) + "\n以上。") == obj
    assert extract_json_block("完全不是 JSON") is None
    assert extract_json_block("") is None


def test_merge_spec_injects_bundle_data():
    model_out = json.loads(json.dumps(GOOD_OUTPUT))
    # 模型即使输出了错误的历史/价格，也以 bundle 为准
    model_out["current_price"] = 999.0
    model_out["share_count"] = 1.0
    spec = merge_spec(model_out, BUNDLE)
    assert spec["current_price"] == 56.82
    assert spec["share_count"] == 15.1
    assert spec["earnings_forecast"]["history"] == BUNDLE["financial_history"]
    assert spec["earnings_forecast"]["assumptions"] == model_out["earnings_forecast"]["assumptions"]


def test_user_prompt_contains_data_anchors():
    prompt = build_spec_user_prompt(BUNDLE)
    assert "56.82" in prompt and "15.1" in prompt
    assert "1716.5" in prompt
    assert "禁止改动" in prompt


def test_first_pass_success():
    llm = StubLLM([json.dumps(GOOD_OUTPUT, ensure_ascii=False)])
    result = generate_valuation_spec(BUNDLE, llm)
    assert result["passed"], result["errors"]
    assert result["attempts"] == 1
    assert result["spec"]["current_price"] == 56.82


def test_fenced_and_invalid_then_retry():
    bad = json.loads(json.dumps(GOOD_OUTPUT))
    bad["valuation"]["scenarios"][0]["multiple"] = 0  # 触发"倍数为零"
    llm = StubLLM([
        "```json\n" + json.dumps(bad, ensure_ascii=False) + "\n```",  # 围栏 + 非法
        json.dumps(GOOD_OUTPUT, ensure_ascii=False),                   # 修正
    ])
    result = generate_valuation_spec(BUNDLE, llm)
    assert result["passed"]
    assert result["attempts"] == 2
    # 第二次调用的反馈消息包含错误说明
    feedback = llm.calls[1][-1].content
    assert "倍数为零" in feedback


def test_pe_on_loss_year_corrected_by_retry():
    bundle = json.loads(json.dumps(BUNDLE))
    bundle["financial_history"] = [
        {"period": "TTM", "revenue": 1716.5, "net_profit": -12.0},  # 亏损期
    ]
    bad = json.loads(json.dumps(GOOD_OUTPUT))
    bad["valuation"]["scenarios"][0]["eps_period"] = "TTM"  # PE 落在亏损期
    llm = StubLLM([
        json.dumps(bad, ensure_ascii=False),
        json.dumps(GOOD_OUTPUT, ensure_ascii=False),  # 换回盈利预测期
    ])
    result = generate_valuation_spec(bundle, llm)
    assert result["passed"], result["errors"]
    assert "PE" in llm.calls[1][-1].content  # 反馈中说明了 PE 适用性问题


def test_garbage_output_exhausts_attempts():
    llm = StubLLM(["我认为无法完成", "还是不行", "第三次失败"])
    result = generate_valuation_spec(BUNDLE, llm, max_attempts=3)
    assert not result["passed"]
    assert result["attempts"] == 3
    assert any("JSON" in e for e in result["errors"])


def test_end_to_end_deliverable(tmp_path):
    llm = StubLLM([json.dumps(GOOD_OUTPUT, ensure_ascii=False)])
    out = generate_valuation_deliverable(
        BUNDLE, llm, output_path=str(tmp_path / "e2e.xlsx"))
    assert out["success"], out.get("validation")
    assert os.path.exists(out["path"])
    assert out["attempts"] == 1
    # TTM 营收 1716.5 × 1.22 × 0.05 = 104.71 亿净利；EPS = 104.71/15.1
    eps = 1716.5 * 1.22 * 0.05 / 15.1
    assert out["validation"]["summary"]["scenarios"]["中性"]["eps"] == pytest.approx(eps, abs=1e-3)


def test_end_to_end_spec_failure(tmp_path):
    llm = StubLLM(["完全不是 JSON 的回复"])
    out = generate_valuation_deliverable(BUNDLE, llm, output_path=str(tmp_path / "x.xlsx"),
                                         max_attempts=1)
    assert not out["success"]
    assert out["stage"] == "spec_generation"
    assert not os.path.exists(str(tmp_path / "x.xlsx"))
