"""验证研究员报告反思提炼机制（v3.5.0 项3）。

测试场景：
1. _save_to_memory 调用后触发 _reflect_on_analysis，断言 run_reflection_sync 被调用
2. 反思成功时写入 ANALYSIS_INSIGHT scope，memory_kind=analysis_lesson
3. memory 为 None 时不触发反思（早返回）
4. _reflect_on_analysis 异常时不阻塞主流程

运行方式：
    env\\Scripts\\python.exe scripts\\validate_researcher_reflection.py
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock, patch


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from core.agents.researcher import ResearcherAgent


class _FakeMemory:
    """模拟旧版 memory 实例（支持 add_memory）"""

    def __init__(self):
        self.add_memory_calls: List[Dict[str, Any]] = []

    def add_memory(self, content: str, metadata: Dict[str, Any]) -> bool:
        self.add_memory_calls.append({"content": content, "metadata": metadata})
        return True


class _FakeResearcherAgent(ResearcherAgent):
    """可实例化的 ResearcherAgent（绕过 abstract 方法）"""

    researcher_type = "test_researcher"
    output_field = "test_report"
    stance = "bull"

    def _build_system_prompt(self, stance: str, state: Dict[str, Any] = None) -> str:
        return "test system prompt"

    def _build_user_prompt(self, ticker, analysis_date, reports, historical_context, state) -> str:
        return "test user prompt"

    def _get_required_reports(self) -> List[str]:
        return []


def _make_researcher(memory=None, config=None) -> _FakeResearcherAgent:
    """构建一个测试用的 researcher 实例"""
    if config is None:
        from core.agents.config import AgentConfig
        config = AgentConfig()
    researcher = _FakeResearcherAgent(
        config=config,
        llm=MagicMock(),
        memory=memory,
    )
    return researcher


async def test_case_1_reflection_triggered_after_save() -> bool:
    """测试1：_save_to_memory 后触发反思，run_reflection_sync 被调用"""
    print("\n[测试1] _save_to_memory 后触发 _reflect_on_analysis")

    fake_memory = _FakeMemory()
    researcher = _make_researcher(memory=fake_memory)
    state = {"user_id": "test_user_001", "analysis_date": "2026-07-26"}

    # mock run_reflection_sync 避免真正调 LLM
    with patch("core.agents.reflection_helper.run_reflection_sync") as mock_reflect:
        mock_reflect.return_value = True

        # mock db 句柄获取
        with patch.object(researcher, "_get_db_handle", return_value=MagicMock()):
            researcher._save_to_memory(
                ticker="601012",
                report={"content": "隆基绿能基本面良好，建议买入", "stance": "bull"},
                state=state,
            )

    # 断言1：旧版 add_memory 被调用（原文写入）
    if len(fake_memory.add_memory_calls) != 1:
        print(f"  ❌ 失败：期望 add_memory 调用1次，实际 {len(fake_memory.add_memory_calls)} 次")
        return False

    # 断言2：run_reflection_sync 被调用1次（反思触发）
    if mock_reflect.call_count != 1:
        print(f"  ❌ 失败：期望 run_reflection_sync 调用1次，实际 {mock_reflect.call_count} 次")
        return False

    # 断言3：反思参数正确
    call_kwargs = mock_reflect.call_args.kwargs
    if call_kwargs.get("memory_kind") != "analysis_lesson":
        print(f"  ❌ 失败：期望 memory_kind=analysis_lesson，实际 {call_kwargs.get('memory_kind')}")
        return False

    # 断言4：scope 是 ANALYSIS_INSIGHT
    scope_value = str(call_kwargs.get("scope"))
    if "analysis_insight" not in scope_value.lower():
        print(f"  ❌ 失败：期望 scope=ANALYSIS_INSIGHT，实际 {call_kwargs.get('scope')}")
        return False

    print("  ✅ 通过：_save_to_memory 后正确触发反思")
    return True


async def test_case_2_memory_none_skips_reflection() -> bool:
    """测试2：memory 为 None 时不触发反思"""
    print("\n[测试2] memory 为 None → 不触发反思")

    researcher = _make_researcher(memory=None)
    state = {"user_id": "test_user_001"}

    with patch("core.agents.reflection_helper.run_reflection_sync") as mock_reflect:
        researcher._save_to_memory(
            ticker="601012",
            report={"content": "test", "stance": "bull"},
            state=state,
        )

    # 断言：run_reflection_sync 没被调用（因为 memory=None 早返回）
    if mock_reflect.call_count != 0:
        print(f"  ❌ 失败：期望 run_reflection_sync 不被调用，实际调用 {mock_reflect.call_count} 次")
        return False

    print("  ✅ 通过：memory 为 None 时正确跳过反思")
    return True


async def test_case_3_reflection_exception_does_not_block() -> bool:
    """测试3：反思异常时不阻塞主流程"""
    print("\n[测试3] 反思异常 → 不阻塞主流程")

    fake_memory = _FakeMemory()
    researcher = _make_researcher(memory=fake_memory)
    state = {"user_id": "test_user_001"}

    # mock run_reflection_sync 抛异常
    with patch("core.agents.reflection_helper.run_reflection_sync") as mock_reflect:
        mock_reflect.side_effect = Exception("LLM service unavailable")

        # 不应该抛异常
        try:
            researcher._save_to_memory(
                ticker="601012",
                report={"content": "test report", "stance": "bull"},
                state=state,
            )
        except Exception as e:
            print(f"  ❌ 失败：反思异常不应抛出，但抛了: {e}")
            return False

    # 断言：原文仍然写入成功（即使反思失败）
    if len(fake_memory.add_memory_calls) != 1:
        print(f"  ❌ 失败：期望原文 add_memory 仍调用1次，实际 {len(fake_memory.add_memory_calls)} 次")
        return False

    print("  ✅ 通过：反思异常时不阻塞主流程")
    return True


async def test_case_4_reflection_success_writes_structured_lesson() -> bool:
    """测试4：反思成功时调用参数包含结构化教训的元数据"""
    print("\n[测试4] 反思成功 → 调用参数包含正确的 metadata")

    fake_memory = _FakeMemory()
    researcher = _make_researcher(memory=fake_memory)
    state = {"user_id": "test_user_001", "analysis_date": "2026-07-26"}

    with patch("core.agents.reflection_helper.run_reflection_sync") as mock_reflect:
        mock_reflect.return_value = True
        with patch.object(researcher, "_get_db_handle", return_value=MagicMock()):
            researcher._save_to_memory(
                ticker="601012",
                report={"content": "隆基绿能财务数据良好", "stance": "bull"},
                state=state,
            )

    call_kwargs = mock_reflect.call_args.kwargs

    # 断言1：fallback_metadata 含正确的字段
    fallback_meta = call_kwargs.get("fallback_metadata", {})
    if fallback_meta.get("symbol") != "601012":
        print(f"  ❌ 失败：期望 symbol=601012，实际 {fallback_meta.get('symbol')}")
        return False
    if fallback_meta.get("stance") != "bull":
        print(f"  ❌ 失败：期望 stance=bull，实际 {fallback_meta.get('stance')}")
        return False
    if fallback_meta.get("source") != "researcher_reflection":
        print(f"  ❌ 失败：期望 source=researcher_reflection，实际 {fallback_meta.get('source')}")
        return False

    # 断言2：user_id 来自 state
    if call_kwargs.get("user_id") != "test_user_001":
        print(f"  ❌ 失败：期望 user_id=test_user_001，实际 {call_kwargs.get('user_id')}")
        return False

    # 断言3：agent_id 来自 researcher
    if not call_kwargs.get("agent_id"):
        print(f"  ❌ 失败：期望 agent_id 非空")
        return False

    print("  ✅ 通过：反思调用参数包含正确 metadata")
    return True


async def main() -> int:
    print("=" * 70)
    print("研究员报告反思提炼验证（v3.5.0 项3）")
    print("=" * 70)

    results = []
    results.append(await test_case_1_reflection_triggered_after_save())
    results.append(await test_case_2_memory_none_skips_reflection())
    results.append(await test_case_3_reflection_exception_does_not_block())
    results.append(await test_case_4_reflection_success_writes_structured_lesson())

    print("\n" + "=" * 70)
    passed = sum(1 for r in results if r)
    total = len(results)
    print(f"测试结果：{passed}/{total} 通过")
    print("=" * 70)

    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
