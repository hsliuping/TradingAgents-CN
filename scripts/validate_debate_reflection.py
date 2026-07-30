"""验证辩论结果回流记忆机制（v3.6.0 项8）。

测试场景：
1. 管理者节点（research_manager / risk_manager）执行后触发 _trigger_debate_reflection
2. _trigger_debate_reflection 正确提取 debate_history / conclusion，调用 run_reflection_sync
3. 反思写入 AGENT_EXPERIENCE scope，memory_kind=debate_lesson
4. 辩论历史和裁决均为空时早返回（不调用 run_reflection_sync）
5. 反思异常时不阻塞主流程（wrapper 仍返回 original_func 的结果）
6. ResearcherAgent._reflect_on_debate 可被独立调用并正确传参

运行方式：
    env\\Scripts\\python.exe scripts\\validate_debate_reflection.py
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock, patch


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))


def _make_state(
    *,
    ticker: str = "601012",
    debate_history: str = "Bull Analyst: 隆基绿能基本面良好\nBear Analyst: 光伏行业产能过剩",
    conclusion: str = "综合多空观点，隆基绿能短期承压但长期配置价值凸显",
    debate_state_field: str = "investment_debate_state",
    user_id: str = "test_user_001",
) -> Dict[str, Any]:
    """构造测试用 state。"""
    state: Dict[str, Any] = {
        "ticker": ticker,
        "user_id": user_id,
        debate_state_field: {
            "history": debate_history,
            "judge_decision": conclusion,
            "count": 2,
        },
    }
    if debate_state_field == "risk_debate_state":
        state["final_trade_decision"] = conclusion
    else:
        state["investment_plan"] = conclusion
    return state


async def test_case_1_manager_wrapper_triggers_reflection() -> bool:
    """测试1：管理者 wrapper 执行后触发 _trigger_debate_reflection。"""
    print("\n[测试1] 管理者 wrapper 触发 _trigger_debate_reflection")

    from core.workflow.builder import WorkflowBuilder
    from core.workflow.models import NodeDefinition, NodeType

    # 构造一个 research_manager 节点
    node = NodeDefinition(
        id="research_manager_node",
        type=NodeType.MANAGER,
        agent_id="research_manager",
        label="研究经理",
    )

    # 构造 builder 实例（跳过 __init__ 的复杂依赖）
    builder = WorkflowBuilder.__new__(WorkflowBuilder)

    # mock _create_agent_node 返回一个简单的 original_func
    original_called: List[bool] = []

    def fake_original_func(state):
        original_called.append(True)
        # 模拟管理者返回的结果
        return {
            "investment_debate_state": state.get("investment_debate_state", {}),
            "investment_plan": "综合多空观点，建议持有",
        }

    with patch.object(builder, "_create_agent_node", return_value=fake_original_func):
        wrapped = builder._create_manager_with_debate_reflection(
            node, debate_state_field="investment_debate_state"
        )

    state = _make_state()

    with patch("core.workflow.builder._trigger_debate_reflection") as mock_trigger:
        result = wrapped(state)

    # 断言1：original_func 被调用
    if not original_called:
        print("  ❌ 失败：original_func 未被调用")
        return False

    # 断言2：_trigger_debate_reflection 被调用
    if mock_trigger.call_count != 1:
        print(f"  ❌ 失败：期望 _trigger_debate_reflection 调用1次，实际 {mock_trigger.call_count} 次")
        return False

    # 断言3：调用参数包含正确的 debate_state_field
    call_kwargs = mock_trigger.call_args.kwargs
    if call_kwargs.get("debate_state_field") != "investment_debate_state":
        print(f"  ❌ 失败：期望 debate_state_field=investment_debate_state，实际 {call_kwargs.get('debate_state_field')}")
        return False
    if call_kwargs.get("debate_type") != "investment_debate_state":
        print(f"  ❌ 失败：期望 debate_type=investment_debate_state，实际 {call_kwargs.get('debate_type')}")
        return False
    if call_kwargs.get("agent_id") != "research_manager":
        print(f"  ❌ 失败：期望 agent_id=research_manager，实际 {call_kwargs.get('agent_id')}")
        return False

    # 断言4：返回值是 original_func 的结果（不被 wrapper 改变）
    if "investment_plan" not in result:
        print(f"  ❌ 失败：返回值缺失 investment_plan，实际 {result}")
        return False

    print("  ✅ 通过：管理者 wrapper 正确触发辩论反思")
    return True


async def test_case_2_trigger_reflection_calls_run_reflection_sync() -> bool:
    """测试2：_trigger_debate_reflection 正确调用 run_reflection_sync。"""
    print("\n[测试2] _trigger_debate_reflection 调用 run_reflection_sync")

    from core.workflow.builder import _trigger_debate_reflection

    state = _make_state()
    result = {
        "investment_debate_state": state["investment_debate_state"],
        "investment_plan": state["investment_plan"],
    }

    fake_db = MagicMock()

    with patch("core.agents.reflection_helper.run_reflection_sync") as mock_reflect:
        mock_reflect.return_value = True
        _trigger_debate_reflection(
            state=state,
            result=result,
            debate_state_field="investment_debate_state",
            debate_type="investment_debate_state",
            agent_id="research_manager",
            node_id="research_manager_node",
        )

    # 断言1：run_reflection_sync 被调用
    if mock_reflect.call_count != 1:
        print(f"  ❌ 失败：期望 run_reflection_sync 调用1次，实际 {mock_reflect.call_count} 次")
        return False

    call_kwargs = mock_reflect.call_args.kwargs

    # 断言2：scope 是 AGENT_EXPERIENCE
    scope_value = str(call_kwargs.get("scope"))
    if "agent_experience" not in scope_value.lower():
        print(f"  ❌ 失败：期望 scope=AGENT_EXPERIENCE，实际 {call_kwargs.get('scope')}")
        return False

    # 断言3：memory_kind 是 debate_lesson
    if call_kwargs.get("memory_kind") != "debate_lesson":
        print(f"  ❌ 失败：期望 memory_kind=debate_lesson，实际 {call_kwargs.get('memory_kind')}")
        return False

    # 断言4：user_prompt 包含辩论历史和裁决
    user_prompt = call_kwargs.get("user_prompt", "")
    if "Bull Analyst" not in user_prompt or "Bear Analyst" not in user_prompt:
        print(f"  ❌ 失败：user_prompt 缺失辩论历史，前200字: {user_prompt[:200]}")
        return False
    if "综合多空观点" not in user_prompt:
        print(f"  ❌ 失败：user_prompt 缺失裁决，前200字: {user_prompt[:200]}")
        return False

    # 断言5：fallback_metadata 含正确的字段
    fallback_meta = call_kwargs.get("fallback_metadata", {})
    if fallback_meta.get("symbol") != "601012":
        print(f"  ❌ 失败：期望 symbol=601012，实际 {fallback_meta.get('symbol')}")
        return False
    if fallback_meta.get("source") != "debate_reflection":
        print(f"  ❌ 失败：期望 source=debate_reflection，实际 {fallback_meta.get('source')}")
        return False
    if fallback_meta.get("debate_type") != "investment_debate_state":
        print(f"  ❌ 失败：期望 debate_type=investment_debate_state，实际 {fallback_meta.get('debate_type')}")
        return False

    print("  ✅ 通过：_trigger_debate_reflection 正确调用 run_reflection_sync")
    return True


async def test_case_3_empty_debate_skips_reflection() -> bool:
    """测试3：辩论历史和裁决均为空时跳过反思。"""
    print("\n[测试3] 辩论历史+裁决为空 → 跳过反思")

    from core.workflow.builder import _trigger_debate_reflection

    state = {
        "ticker": "601012",
        "user_id": "test_user_001",
        "investment_debate_state": {"history": "", "judge_decision": "", "count": 0},
    }

    with patch("core.agents.reflection_helper.run_reflection_sync") as mock_reflect:
        _trigger_debate_reflection(
            state=state,
            result={},
            debate_state_field="investment_debate_state",
            debate_type="investment_debate_state",
            agent_id="research_manager",
            node_id="research_manager_node",
        )

    if mock_reflect.call_count != 0:
        print(f"  ❌ 失败：期望 run_reflection_sync 不被调用，实际调用 {mock_reflect.call_count} 次")
        return False

    print("  ✅ 通过：空辩论历史+裁决时正确跳过反思")
    return True


async def test_case_4_reflection_exception_does_not_block() -> bool:
    """测试4：反思异常时不阻塞主流程。"""
    print("\n[测试4] 反思异常 → 不阻塞主流程")

    from core.workflow.builder import WorkflowBuilder
    from core.workflow.models import NodeDefinition, NodeType

    node = NodeDefinition(
        id="risk_manager_node",
        type=NodeType.MANAGER,
        agent_id="risk_manager",
        label="风险管理者",
    )

    builder = WorkflowBuilder.__new__(WorkflowBuilder)

    def fake_original_func(state):
        return {"final_trade_decision": "风险中性"}

    with patch.object(builder, "_create_agent_node", return_value=fake_original_func):
        wrapped = builder._create_manager_with_debate_reflection(
            node, debate_state_field="risk_debate_state"
        )

    state = _make_state(
        debate_state_field="risk_debate_state",
        debate_history="Risky: 高杠杆\nSafe: 现金流稳定",
        conclusion="风险可控",
    )

    # mock _trigger_debate_reflection 抛异常
    with patch("core.workflow.builder._trigger_debate_reflection") as mock_trigger:
        mock_trigger.side_effect = Exception("mem0 service unavailable")

        # 不应该抛异常
        try:
            result = wrapped(state)
        except Exception as e:
            print(f"  ❌ 失败：反思异常不应抛出，但抛了: {e}")
            return False

    # 断言：original_func 的结果仍然返回（不被 wrapper 改变）
    if result.get("final_trade_decision") != "风险中性":
        print(f"  ❌ 失败：期望返回 original_func 的结果 '风险中性'，实际 {result}")
        return False

    print("  ✅ 通过：反思异常时不阻塞主流程")
    return True


async def test_case_5_risk_manager_wrapper_uses_risk_debate_field() -> bool:
    """测试5：risk_manager wrapper 使用 risk_debate_state 字段。"""
    print("\n[测试5] risk_manager wrapper 使用 risk_debate_state")

    from core.workflow.builder import WorkflowBuilder
    from core.workflow.models import NodeDefinition, NodeType

    node = NodeDefinition(
        id="risk_manager_node",
        type=NodeType.MANAGER,
        agent_id="risk_manager",
        label="风险管理者",
    )

    builder = WorkflowBuilder.__new__(WorkflowBuilder)

    def fake_original_func(state):
        return {"final_trade_decision": "风险中性"}

    with patch.object(builder, "_create_agent_node", return_value=fake_original_func):
        wrapped = builder._create_manager_with_debate_reflection(
            node, debate_state_field="risk_debate_state"
        )

    state = _make_state(debate_state_field="risk_debate_state")

    with patch("core.workflow.builder._trigger_debate_reflection") as mock_trigger:
        wrapped(state)

    call_kwargs = mock_trigger.call_args.kwargs
    if call_kwargs.get("debate_state_field") != "risk_debate_state":
        print(f"  ❌ 失败：期望 debate_state_field=risk_debate_state，实际 {call_kwargs.get('debate_state_field')}")
        return False
    if call_kwargs.get("debate_type") != "risk_debate_state":
        print(f"  ❌ 失败：期望 debate_type=risk_debate_state，实际 {call_kwargs.get('debate_type')}")
        return False

    print("  ✅ 通过：risk_manager wrapper 正确使用 risk_debate_state 字段")
    return True


async def test_case_6_researcher_reflect_on_debate_method() -> bool:
    """测试6：ResearcherAgent._reflect_on_debate 可独立调用。"""
    print("\n[测试6] ResearcherAgent._reflect_on_debate 可独立调用")

    from core.agents.researcher import ResearcherAgent
    from core.agents.config import AgentConfig

    class _FakeResearcher(ResearcherAgent):
        researcher_type = "test"
        output_field = "test_report"
        stance = "bull"

        def _build_system_prompt(self, stance: str, state: Dict[str, Any] = None) -> str:
            return ""

        def _build_user_prompt(self, ticker, analysis_date, reports, historical_context, state) -> str:
            return ""

        def _get_required_reports(self) -> List[str]:
            return []

    researcher = _FakeResearcher(
        config=AgentConfig(),
        llm=MagicMock(),
        memory=MagicMock(),
    )

    state = {"user_id": "test_user_001", "analysis_date": "2026-07-26"}

    with patch("core.agents.reflection_helper.run_reflection_sync") as mock_reflect:
        mock_reflect.return_value = True
        with patch.object(researcher, "_get_db_handle", return_value=MagicMock()):
            researcher._reflect_on_debate(
                ticker="601012",
                debate_history="Bull: 基本面良好\nBear: 估值偏高",
                conclusion="综合多空观点，建议持有",
                debate_type="investment_debate_state",
                state=state,
            )

    if mock_reflect.call_count != 1:
        print(f"  ❌ 失败：期望 run_reflection_sync 调用1次，实际 {mock_reflect.call_count} 次")
        return False

    call_kwargs = mock_reflect.call_args.kwargs
    if call_kwargs.get("memory_kind") != "debate_lesson":
        print(f"  ❌ 失败：期望 memory_kind=debate_lesson，实际 {call_kwargs.get('memory_kind')}")
        return False

    scope_value = str(call_kwargs.get("scope"))
    if "agent_experience" not in scope_value.lower():
        print(f"  ❌ 失败：期望 scope=AGENT_EXPERIENCE，实际 {call_kwargs.get('scope')}")
        return False

    print("  ✅ 通过：ResearcherAgent._reflect_on_debate 可独立调用并正确传参")
    return True


async def test_case_7_risk_debate_conclusion_fallback() -> bool:
    """测试7：risk_debate 缺失 judge_decision 时从 final_trade_decision 兜底。"""
    print("\n[测试7] risk_debate 缺失 judge_decision → 从 final_trade_decision 兜底")

    from core.workflow.builder import _trigger_debate_reflection

    state = {
        "ticker": "601012",
        "user_id": "test_user_001",
        # 故意 missing judge_decision
        "risk_debate_state": {"history": "Risky: 高杠杆\nSafe: 现金流稳定", "count": 3},
    }
    result = {"final_trade_decision": "风险可控，可持有"}

    with patch("core.agents.reflection_helper.run_reflection_sync") as mock_reflect:
        mock_reflect.return_value = True
        _trigger_debate_reflection(
            state=state,
            result=result,
            debate_state_field="risk_debate_state",
            debate_type="risk_debate_state",
            agent_id="risk_manager",
            node_id="risk_manager_node",
        )

    if mock_reflect.call_count != 1:
        print(f"  ❌ 失败：期望 run_reflection_sync 调用1次，实际 {mock_reflect.call_count} 次")
        return False

    call_kwargs = mock_reflect.call_args.kwargs
    user_prompt = call_kwargs.get("user_prompt", "")
    if "风险可控" not in user_prompt:
        print(f"  ❌ 失败：user_prompt 缺失兜底裁决 final_trade_decision，前200字: {user_prompt[:200]}")
        return False

    print("  ✅ 通过：risk_debate 缺失 judge_decision 时正确兜底")
    return True


async def main() -> int:
    print("=" * 70)
    print("辩论结果回流记忆验证（v3.6.0 项8）")
    print("=" * 70)

    results = []
    results.append(await test_case_1_manager_wrapper_triggers_reflection())
    results.append(await test_case_2_trigger_reflection_calls_run_reflection_sync())
    results.append(await test_case_3_empty_debate_skips_reflection())
    results.append(await test_case_4_reflection_exception_does_not_block())
    results.append(await test_case_5_risk_manager_wrapper_uses_risk_debate_field())
    results.append(await test_case_6_researcher_reflect_on_debate_method())
    results.append(await test_case_7_risk_debate_conclusion_fallback())

    print("\n" + "=" * 70)
    passed = sum(1 for r in results if r)
    total = len(results)
    print(f"测试结果：{passed}/{total} 通过")
    print("=" * 70)

    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
