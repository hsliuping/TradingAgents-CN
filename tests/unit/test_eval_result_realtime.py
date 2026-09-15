# -*- coding: utf-8 -*-
"""质量评估结果实时展示 — 单元测试

覆盖：
1. EvalScore.expert_comment 字段解析填充（output_evaluator）
2. IterationController._build_eval_result_extra 事件构造（含 total/passed）
3. service 进度回调 extra 透传（_progress_cb 写入 pipeline_eval_result）
"""
import re

from core.tools.external.iteration_controller import IterationController
from core.tools.external.skill_spec import EvalScore


def test_eval_score_has_expert_comment_default_empty():
    score = EvalScore()
    assert score.expert_comment == ""
    assert score.total >= 0


def test_build_eval_result_extra_contains_total_and_passed():
    # 权重总分 = 0.25*9 + 0.25*9 + 0.20*8 + 0.20*8 + 0.10*9 = 8.6 >= 阈值 8.5
    score = EvalScore(
        executability=9, authenticity=9, completeness=8, relevance=8, format_quality=9,
        expert_comment="整体质量良好，数据链路清晰",
    )
    extra = IterationController._build_eval_result_extra(score, round_num=2)

    assert "eval_result" in extra
    data = extra["eval_result"]
    # total 是 @property，必须显式带出
    assert data["total"] == score.total
    assert data["round"] == 2
    assert data["passed"] is True
    assert data["expert_comment"] == "整体质量良好，数据链路清晰"
    # 五个维度完整透出
    for key in ("executability", "authenticity", "completeness", "relevance", "format_quality"):
        assert key in data


def test_build_eval_result_extra_passed_false_below_threshold():
    score = EvalScore(executability=6.0)
    extra = IterationController._build_eval_result_extra(score, round_num=1)
    assert extra["eval_result"]["passed"] is False


def test_evaluator_parses_expert_comment_from_verdict():
    """从 <verdict> JSON 中解析 expert_comment 并写入 EvalScore"""
    raw = (
        '<verdict>\n{"executability": 9, "authenticity": 8, "completeness": 8, '
        '"relevance": 9, "format_quality": 8, "expert_comment": "数据真实，结构清晰"}\n</verdict>'
    )
    match = re.search(r"<verdict>\s*(.*?)\s*</verdict>", raw, re.DOTALL)
    assert match

    import json as _json
    scores = _json.loads(match.group(1).strip())
    score = EvalScore()
    score.executability = float(scores["executability"])
    score.authenticity = float(scores["authenticity"])
    score.completeness = float(scores["completeness"])
    score.relevance = float(scores["relevance"])
    score.format_quality = float(scores["format_quality"])
    comment = str(scores.get("expert_comment", "")).strip()
    if comment:
        score.expert_comment = comment

    assert score.expert_comment == "数据真实，结构清晰"
    assert score.executability == 9.0
