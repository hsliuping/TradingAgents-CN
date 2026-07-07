"""端到端测试：质押 skill 生成流程（agentic 模式）"""

import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.tools.external.skill_spec import (
    SkillSpec,
    SkillParameter,
    ExpectedOutput,
    ValidationCheck,
)
from core.tools.external.iteration_controller import IterationController


def build_pledge_spec() -> SkillSpec:
    return SkillSpec(
        tool_id="test_pledge_e2e",
        display_name="股票股权质押趋势与风险报告",
        description=(
            "获取指定股票最近三年的股权质押历史趋势，支持按年/季/月频率统计，"
            "自动评估质押比例趋势方向；同时结合当前风险快照输出风险等级和前几大质押股东。"
            "对于确实无质押数据的蓝筹股，正常返回空趋势序列和风险等级 none。"
        ),
        category="fundamentals",
        data_source="local_db",
        parameters=[
            SkillParameter(name="symbol", param_type="string", description="6位A股股票代码，如000002", required=True),
            SkillParameter(name="freq", param_type="string", description="统计频率，可选 year、quarter、month，默认 year", required=False, default="year"),
        ],
        expected_output=ExpectedOutput(
            type="dict",
            fields=["symbol", "name", "historical_trend", "trend_assessment", "risk_level", "top_pledge_shareholders"],
        ),
        validation_checks=[
            ValidationCheck(check_type="output", name="status_success", description="输出状态必须成功", blocking=True),
            ValidationCheck(check_type="data", name="required_field", field="symbol", description="返回结果中 symbol 不能缺失", blocking=True),
            ValidationCheck(check_type="data", name="required_field", field="risk_level", description="风险等级字段不能缺失，至少返回 none", blocking=True),
        ],
        constraints=[
            "不得在质押数据实际存在时返回空趋势或无质押结论",
            "必须通过 get_pledge_historical_series 和 get_pledge_risk_profile 两个 helper 串联获取",
            "freq 参数直接映射为 underlying helper 的 period 参数（year/quarter/month）",
            "当确无质押数据时，historical_trend 返回空列表，risk_level 返回 none",
        ],
        test_input={"symbol": "000002", "freq": "year"},
    )


def main():
    print("=" * 60)
    print("端到端测试：质押 skill 生成流程（agentic 模式）")
    print("=" * 60)

    spec = build_pledge_spec()
    print(f"\n📋 SkillSpec 构建完成: tool_id={spec.tool_id}")
    print(f"   测试输入: {spec.test_input}")

    print("\n🔧 初始化 IterationController (provider=deepseek)...")
    controller = IterationController(provider="deepseek", max_iterations=10)

    print("\n🚀 开始 run_agentic...")
    start_time = time.time()

    try:
        result = controller.run_agentic(spec)
        elapsed = time.time() - start_time
        print(f"\n✅ run_agentic 完成，耗时 {elapsed:.1f}s")
        print(f"   success: {result.success}")
        print(f"   stages: {len(getattr(result, 'stages', result.iterations) if hasattr(result, 'iterations') else [])}")
        if hasattr(result, 'final_score'):
            print(f"   final_score: {result.final_score}")
        elif hasattr(result, 'quality_score'):
            print(f"   quality_score: {result.quality_score}")
        failure_summary = getattr(result, 'failure_summary', '') or ''
        print(f"   failure_summary: {failure_summary[:300] if failure_summary else '(无)'}")

        iterations = getattr(result, 'iterations', getattr(result, 'stages', []))
        for i, iteration in enumerate(iterations):
            print(f"\n--- 第 {i+1} 轮 ---")
            if hasattr(iteration, "eval_score") and iteration.eval_score:
                print(f"   评分: total={iteration.eval_score.total:.2f} (exec={iteration.eval_score.executability} auth={iteration.eval_score.authenticity} compl={iteration.eval_score.completeness} rel={iteration.eval_score.relevance} fmt={iteration.eval_score.format_quality})")
            if hasattr(iteration, "reflection") and iteration.reflection:
                print(f"   根因: {iteration.reflection.root_cause[:150]}")
                print(f"   should_retry: {iteration.reflection.should_retry}")
            if hasattr(iteration, "decision"):
                print(f"   决策: {iteration.decision}")

    except Exception as e:
        elapsed = time.time() - start_time
        print(f"\n❌ run_agentic 异常，耗时 {elapsed:.1f}s")
        import traceback
        traceback.print_exc()

    print("\n" + "=" * 60)
    print("测试完成。请检查 logs/skill_workshop.log 排查详情")
    print("=" * 60)


if __name__ == "__main__":
    main()
