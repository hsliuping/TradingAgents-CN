"""P2.1 回归测试脚本 — 在历史执行轨迹上重放断言，度量拦截效果

借鉴桥水 Pat「把错误转化为可执行验证用例并自动回归测试」：对最近 N 天的
agent_execution_traces 重放所有 enabled 断言，输出报告：
  - 各 agent 的断言通过率
  - 各 assertion 的命中率
  - 按 system_prompt_hash 分组的失败率对比（评估 prompt 改进效果）
  - 断言违规与 validation_status 的相关性

注意：轨迹只存 output_raw_preview（前 500 字符），field 类断言依赖 parsed dict。
脚本会尝试将 output_raw_preview 解析为 JSON 作为 parsed；解析失败（如 trader_v2
的 Markdown 或截断 JSON）时仅重放文本类断言（term_forbidden / section_required）。

用法：
    env\\Scripts\\python.exe scripts\\regression_test_assertions.py \\
        --agent-id risk_manager_v2 --days 30 --limit 200

    # 覆盖所有 agent
    env\\Scripts\\python.exe scripts\\regression_test_assertions.py --days 30

前置条件：
    - v3.0 MongoDB 容器运行中（端口 27019）
    - agent_assertions 集合中存在 enabled=true 的断言
    - agent_execution_traces 集合有历史轨迹
"""

import argparse
import json
import logging
import os
import sys
from collections import defaultdict
from typing import Any, Dict, List, Optional, Tuple

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

# 🔒 硬约束：必须使用 v3.0 专用数据库（端口 27019）。
os.environ["MONGODB_PORT"] = "27019"
os.environ["REDIS_PORT"] = "6381"

from app.models.agent_assertion import AgentAssertion, AssertionSeverity
from app.models.execution_trace import AgentExecutionTrace
from app.services.agent_assertion_service import agent_assertion_service
from app.services.execution_trace_service import execution_trace_service

logger = logging.getLogger("regression_test_assertions")


# ============================================================================
# 辅助：从轨迹重建 parsed dict
# ============================================================================

def _reparse_output(trace: AgentExecutionTrace) -> Tuple[str, Optional[Dict[str, Any]]]:
    """从轨迹重建 (raw_text, parsed_dict)。

    raw_text 取 output_raw_preview；尝试将其解析为 JSON 得到 parsed_dict，
    失败则 parsed=None（仅文本类断言可重放）。
    """
    raw_text = ""
    if trace.output:
        raw_text = trace.output.output_raw_preview or ""
    parsed: Optional[Dict[str, Any]] = None
    if raw_text:
        try:
            candidate = json.loads(raw_text)
            if isinstance(candidate, dict):
                parsed = candidate
        except (json.JSONDecodeError, ValueError):
            parsed = None
    return raw_text, parsed


# ============================================================================
# 重放断言
# ============================================================================

def replay_traces(
    agent_id: Optional[str],
    days: int,
    limit: int,
) -> List[Dict[str, Any]]:
    """对历史轨迹重放断言，返回每条轨迹的重放结果。"""
    from datetime import datetime, timedelta
    from app.utils.timezone import now_tz

    end_date = now_tz()
    start_date = end_date - timedelta(days=days)

    # 加载所有轨迹（不限 validation_status，用于计算通过率）
    traces = execution_trace_service.get_traces_sync(
        agent_id=agent_id,
        start_date=start_date,
        end_date=end_date,
        limit=limit,
    )
    logger.info(f"加载 {len(traces)} 条轨迹（agent={agent_id or '全部'}）")

    # 加载涉及的断言（按 agent 分组）
    # 由于 load_enabled_assertions_sync 按 agent 加载，先收集轨迹涉及的 agent
    involved_agents = sorted({t.agent_id for t in traces})
    assertions_by_agent: Dict[str, List[AgentAssertion]] = {}
    for a in involved_agents:
        assertions_by_agent[a] = agent_assertion_service.load_enabled_assertions_sync(a)
    total_assertions = sum(len(v) for v in assertions_by_agent.values())
    logger.info(f"加载 {total_assertions} 条 enabled 断言，覆盖 agent: {involved_agents}")

    # 用 AssertionExecutor 重放（直接调用单条检查，避免缓存干扰统计）
    from core.agents.assertion_executor import AssertionExecutor
    executor = AssertionExecutor()

    results: List[Dict[str, Any]] = []
    for trace in traces:
        raw_text, parsed = _reparse_output(trace)
        agent_assertions = assertions_by_agent.get(trace.agent_id, [])

        violations = []
        for assertion in agent_assertions:
            try:
                violation = executor._run_single_assertion(assertion, raw_text, parsed)
                if violation is not None:
                    violations.append({
                        "assertion_id": assertion.assertion_id,
                        "assertion_type": assertion.assertion_type.value,
                        "severity": assertion.severity.value,
                        "description": assertion.description,
                        "violation_detail": violation.violation_detail,
                    })
            except Exception as e:
                logger.warning(
                    f"⚠️ 重放断言失败（trace={trace.trace_id}, assertion={assertion.assertion_id}）: {e}"
                )

        prompt_hash = trace.prompts.system_prompt_hash if trace.prompts else None
        val_status = trace.validation.validation_status if trace.validation else None
        results.append({
            "trace_id": trace.trace_id,
            "agent_id": trace.agent_id,
            "started_at": trace.started_at.isoformat() if trace.started_at else None,
            "system_prompt_hash": prompt_hash,
            "validation_status": val_status,
            "raw_text_length": len(raw_text),
            "parsed_available": parsed is not None,
            "assertion_count": len(agent_assertions),
            "violation_count": len(violations),
            "has_error_violation": any(v["severity"] == AssertionSeverity.ERROR.value for v in violations),
            "violations": violations,
        })

    return results


# ============================================================================
# 报告生成
# ============================================================================

def build_report(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """汇总重放结果为结构化报告。"""
    if not results:
        return {"total_traces": 0}

    # 1. 按 agent 汇总
    by_agent: Dict[str, Dict[str, Any]] = defaultdict(lambda: {
        "total": 0, "with_violations": 0, "with_error": 0, "pass_rate": 0.0,
    })
    for r in results:
        a = by_agent[r["agent_id"]]
        a["total"] += 1
        if r["violation_count"] > 0:
            a["with_violations"] += 1
        if r["has_error_violation"]:
            a["with_error"] += 1
    for a in by_agent.values():
        a["pass_rate"] = round(1 - a["with_violations"] / a["total"], 4) if a["total"] else 0.0

    # 2. 按 assertion 汇总命中率
    by_assertion: Dict[str, Dict[str, Any]] = defaultdict(lambda: {
        "description": "", "assertion_type": "", "severity": "",
        "hits": 0, "applicable_traces": 0,
    })
    for r in results:
        for v in r["violations"]:
            a = by_assertion[v["assertion_id"]]
            a["description"] = v["description"]
            a["assertion_type"] = v["assertion_type"]
            a["severity"] = v["severity"]
            a["hits"] += 1

    # 3. 按 system_prompt_hash 分组失败率（评估 prompt 改进效果）
    by_prompt: Dict[str, Dict[str, Any]] = defaultdict(lambda: {
        "agent_id": "", "total": 0, "with_violations": 0, "violation_rate": 0.0,
    })
    for r in results:
        if not r["system_prompt_hash"]:
            continue
        key = f"{r['agent_id']}::{r['system_prompt_hash']}"
        p = by_prompt[key]
        p["agent_id"] = r["agent_id"]
        p["total"] += 1
        if r["violation_count"] > 0:
            p["with_violations"] += 1
    for p in by_prompt.values():
        p["violation_rate"] = round(p["with_violations"] / p["total"], 4) if p["total"] else 0.0

    # 4. 断言违规与 validation_status 相关性
    correlation = {
        "assertion_violation_and_validation_failed": 0,
        "assertion_violation_but_validation_passed": 0,
        "no_violation_and_validation_failed": 0,
        "no_violation_and_validation_passed": 0,
    }
    for r in results:
        vs = r["validation_status"]
        has_viol = r["violation_count"] > 0
        if has_viol and vs == "failed":
            correlation["assertion_violation_and_validation_failed"] += 1
        elif has_viol and vs == "passed":
            correlation["assertion_violation_but_validation_passed"] += 1
        elif not has_viol and vs == "failed":
            correlation["no_violation_and_validation_failed"] += 1
        elif not has_viol and vs == "passed":
            correlation["no_violation_and_validation_passed"] += 1

    return {
        "total_traces": len(results),
        "by_agent": dict(by_agent),
        "by_assertion": dict(by_assertion),
        "by_prompt_hash": dict(by_prompt),
        "correlation": correlation,
    }


def print_report(report: Dict[str, Any]) -> None:
    """打印人类可读报告。"""
    print("\n" + "=" * 80)
    print("📊 断言回归测试报告")
    print("=" * 80)

    total = report.get("total_traces", 0)
    print(f"\n总轨迹数: {total}")
    if total == 0:
        print("ℹ️ 无轨迹可重放。请先运行单股分析产生执行轨迹。")
        return

    # 按 agent
    print("\n── 按 Agent 汇总 ──")
    print(f"{'Agent':<28} {'总数':>6} {'有违规':>8} {'error违规':>10} {'通过率':>8}")
    for agent_id, a in sorted(report["by_agent"].items()):
        print(f"{agent_id:<28} {a['total']:>6} {a['with_violations']:>8} "
              f"{a['with_error']:>10} {a['pass_rate']*100:>7.1f}%")

    # 按 assertion
    print("\n── 按 Assertion 命中率 ──")
    if not report["by_assertion"]:
        print("（无断言命中，所有轨迹均合规）")
    else:
        print(f"{'AssertionID':<20} {'类型':<18} {'级别':<8} {'命中':>6} {'说明'}")
        for aid, a in sorted(report["by_assertion"].items(), key=lambda x: -x[1]["hits"]):
            desc = (a["description"] or "")[:40]
            print(f"{aid:<20} {a['assertion_type']:<18} {a['severity']:<8} "
                  f"{a['hits']:>6} {desc}")

    # 按 prompt_hash
    print("\n── 按 system_prompt_hash 失败率（评估 prompt 改进效果）──")
    if not report["by_prompt_hash"]:
        print("（无 prompt_hash 信息）")
    else:
        print(f"{'Agent::PromptHash':<48} {'总数':>6} {'有违规':>8} {'违规率':>8}")
        for key, p in sorted(report["by_prompt_hash"].items(), key=lambda x: -x[1]["violation_rate"]):
            print(f"{key:<48} {p['total']:>6} {p['with_violations']:>8} "
                  f"{p['violation_rate']*100:>7.1f}%")
        print("\n💡 解读：违规率较低的 prompt_hash 版本说明 prompt 改进有效；"
              "若新旧 hash 违规率相近，说明改进未触及失败根因。")

    # 相关性
    print("\n── 断言违规与 validation_status 相关性 ──")
    c = report["correlation"]
    print(f"  断言违规 & 校验失败:  {c['assertion_violation_and_validation_failed']}")
    print(f"  断言违规 & 校验通过:  {c['assertion_violation_but_validation_passed']}")
    print(f"  无违规   & 校验失败:  {c['no_violation_and_validation_failed']}")
    print(f"  无违规   & 校验通过:  {c['no_violation_and_validation_passed']}")
    print("\n💡 解读：「断言违规 & 校验通过」越多，说明断言捕获了 schema 校验漏掉的"
          "细粒度问题；「无违规 & 校验失败」多，说明断言覆盖不足，建议补充断言。")


# ============================================================================
# 主流程
# ============================================================================

def run_regression_sync(
    agent_id: Optional[str] = None,
    days: int = 30,
    limit: int = 200,
) -> Dict[str, Any]:
    """回归测试核心流程（同步，供 CLI 与管理 API 复用）。返回完整报告 dict。"""
    results = replay_traces(agent_id, days, limit)
    return build_report(results)


def main():
    parser = argparse.ArgumentParser(
        description="在历史轨迹上重放断言，度量拦截效果（P2.1 回归测试）"
    )
    parser.add_argument("--agent-id", default=None, help="目标 agent_id（不指定则覆盖所有）")
    parser.add_argument("--days", type=int, default=30, help="回溯天数（默认 30）")
    parser.add_argument("--limit", type=int, default=200, help="最多重放的轨迹数（默认 200）")
    parser.add_argument("--json", action="store_true", help="输出 JSON 格式报告（供程序化处理）")
    parser.add_argument("--verbose", "-v", action="store_true", help="详细日志")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s | %(name)s | %(levelname)-8s | %(message)s",
    )

    print("=" * 80)
    print("🧪 P2.1 断言回归测试 — 在历史轨迹上重放断言")
    print(f"   MongoDB: v3.0 (端口 27019)")
    print(f"   agent_id: {args.agent_id or '(全部)'}")
    print(f"   回溯: {args.days} 天 | 上限: {args.limit} 条")
    print("=" * 80)

    results = replay_traces(args.agent_id, args.days, args.limit)
    report = build_report(results)

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
    else:
        print_report(report)

    return 0


if __name__ == "__main__":
    sys.exit(main())
