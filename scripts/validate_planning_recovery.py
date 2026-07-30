"""验证规划失败后的修正重试机制（v3.6.0 项7）。

测试场景：
1. 正常 LLM 规划成功 → 不触发修正重试
2. LLM 规划失败（返回非 JSON）→ 触发修正重试 → 修正重试成功
3. LLM 规划失败 + 修正重试失败 → 降级 ReAct
4. 修正重试返回空步骤列表 → 降级 ReAct

通过 mock UnifiedLLMClient.achat 的返回值，注入不同的失败模式，
断言 _try_llm_plan_with_correction 被调用且行为正确。

运行方式：
    env\\Scripts\\python.exe scripts\\validate_planning_recovery.py
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import Any, List, Optional
from unittest.mock import AsyncMock, MagicMock, patch


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from core.agents.planner import Planner
from core.agents.planner_models import PlanSource
from core.llm.models import Message


class _FakeResponse:
    """模拟 LLM 响应"""

    def __init__(self, content: str):
        self.content = content


class _FakeParam:
    """模拟工具参数"""

    def __init__(self, name: str, description: str = "", required: bool = True):
        self.name = name
        self.description = description
        self.required = required


class _FakeToolMeta:
    """模拟工具元数据"""

    def __init__(self, tool_id: str, description: str, parameters: List[_FakeParam]):
        self.id = tool_id
        self.description = description
        self.parameters = parameters
        self.when_to_use = ""
        self.fc_enabled = True


def _make_fake_registry() -> MagicMock:
    """构建一个假的工具注册表，包含常用工具"""
    registry = MagicMock()
    registry.list_all.return_value = [
        _FakeToolMeta(
            "get_stock_fundamentals_unified",
            "获取股票基本面数据",
            [_FakeParam("ticker", "股票代码", True)],
        ),
        _FakeToolMeta(
            "get_stock_market_data_unified",
            "获取股票行情数据",
            [_FakeParam("ticker", "股票代码", True)],
        ),
    ]
    return registry


def _make_valid_plan_json() -> str:
    """生成一个合法的 LLM 规划 JSON"""
    return """```json
{
  "steps": [
    {
      "id": 1,
      "tool": "get_stock_fundamentals_unified",
      "args": {"ticker": "601012"},
      "intent": "获取基本面数据",
      "depends_on": []
    },
    {
      "id": 2,
      "tool": "get_stock_market_data_unified",
      "args": {"ticker": "601012"},
      "intent": "获取行情数据",
      "depends_on": []
    }
  ]
}
```"""


def _make_simplified_plan_json() -> str:
    """生成一个简化版的合法规划 JSON（用于修正重试）"""
    return """{
  "steps": [
    {
      "id": 1,
      "tool": "get_stock_fundamentals_unified",
      "args": {"ticker": "601012"},
      "intent": "基本面",
      "depends_on": []
    }
  ]
}"""


def _make_invalid_response() -> str:
    """生成一个非法的 LLM 返回（不是 JSON）"""
    return "抱歉，我无法生成分析计划。"


async def test_case_1_normal_plan_no_correction() -> bool:
    """测试1：正常 LLM 规划成功，不应触发修正重试"""
    print("\n[测试1] 正常 LLM 规划成功 → 不触发修正重试")

    fake_llm = MagicMock()
    # 第一次调用（_try_llm_plan）返回合法 JSON
    fake_llm.achat = AsyncMock(return_value=_FakeResponse(_make_valid_plan_json()))

    with patch("core.agents.planner.get_tool_registry", return_value=_make_fake_registry()):
        # 让种子匹配失败，确保走到 LLM 规划分支
        with patch.object(Planner, "_try_seed_match", new=AsyncMock(return_value=None)):
            planner = Planner(
                llm_client=fake_llm,
                curr_date="2026-07-26",
                trade_date="2026-07-25",
            )

            plan = await planner.plan("分析601012", context_messages=None)

    # 断言1：返回的是 LLM_PLAN 而非 REACT_FALLBACK
    if plan.source != PlanSource.LLM_PLAN:
        print(f"  ❌ 失败：期望 source=LLM_PLAN，实际 source={plan.source}")
        return False

    # 断言2：LLM 只被调用1次（没有触发修正重试）
    if fake_llm.achat.call_count != 1:
        print(f"  ❌ 失败：期望 achat 调用1次，实际调用 {fake_llm.achat.call_count} 次")
        return False

    print("  ✅ 通过：正常规划成功，未触发修正重试")
    return True


async def test_case_2_correction_retry_succeeds() -> bool:
    """测试2：LLM 规划失败 → 修正重试成功"""
    print("\n[测试2] LLM 规划失败（返回非 JSON）→ 修正重试成功")

    fake_llm = MagicMock()
    # 第一次调用（_try_llm_plan）返回非法内容
    # 第二次调用（_try_llm_plan_with_correction）返回合法 JSON
    fake_llm.achat = AsyncMock(
        side_effect=[
            _FakeResponse(_make_invalid_response()),
            _FakeResponse(_make_simplified_plan_json()),
        ]
    )

    with patch("core.agents.planner.get_tool_registry", return_value=_make_fake_registry()):
        with patch.object(Planner, "_try_seed_match", new=AsyncMock(return_value=None)):
            planner = Planner(
                llm_client=fake_llm,
                curr_date="2026-07-26",
                trade_date="2026-07-25",
            )

            plan = await planner.plan("分析601012", context_messages=None)

    # 断言1：返回的是 LLM_PLAN 而非 REACT_FALLBACK（修正重试成功）
    if plan.source != PlanSource.LLM_PLAN:
        print(f"  ❌ 失败：期望 source=LLM_PLAN（修正重试成功），实际 source={plan.source}")
        return False

    # 断言2：LLM 被调用2次（一次原规划，一次修正重试）
    if fake_llm.achat.call_count != 2:
        print(f"  ❌ 失败：期望 achat 调用2次（原规划+修正重试），实际调用 {fake_llm.achat.call_count} 次")
        return False

    # 断言3：返回的步骤数量 > 0
    if not plan.steps:
        print("  ❌ 失败：期望返回非空步骤列表")
        return False

    print(f"  ✅ 通过：修正重试成功，返回 {len(plan.steps)} 个步骤")
    return True


async def test_case_3_correction_retry_fails_fallback_react() -> bool:
    """测试3：LLM 规划失败 + 修正重试失败 → 降级 ReAct"""
    print("\n[测试3] LLM 规划失败 + 修正重试失败 → 降级 ReAct")

    fake_llm = MagicMock()
    # 两次调用都返回非法内容
    fake_llm.achat = AsyncMock(
        side_effect=[
            _FakeResponse(_make_invalid_response()),
            _FakeResponse(_make_invalid_response()),
        ]
    )

    with patch("core.agents.planner.get_tool_registry", return_value=_make_fake_registry()):
        with patch.object(Planner, "_try_seed_match", new=AsyncMock(return_value=None)):
            planner = Planner(
                llm_client=fake_llm,
                curr_date="2026-07-26",
                trade_date="2026-07-25",
            )

            plan = await planner.plan("分析601012", context_messages=None)

    # 断言1：返回的是 REACT_FALLBACK
    if plan.source != PlanSource.REACT_FALLBACK:
        print(f"  ❌ 失败：期望 source=REACT_FALLBACK，实际 source={plan.source}")
        return False

    # 断言2：LLM 被调用2次（原规划 + 修正重试）
    if fake_llm.achat.call_count != 2:
        print(f"  ❌ 失败：期望 achat 调用2次，实际调用 {fake_llm.achat.call_count} 次")
        return False

    print("  ✅ 通过：修正重试失败后正确降级 ReAct")
    return True


async def test_case_4_correction_retry_returns_empty_steps() -> bool:
    """测试4：修正重试返回空步骤列表 → 降级 ReAct"""
    print("\n[测试4] 修正重试返回空步骤列表 → 降级 ReAct")

    fake_llm = MagicMock()
    # 第一次返回非法内容，第二次返回空 steps
    fake_llm.achat = AsyncMock(
        side_effect=[
            _FakeResponse(_make_invalid_response()),
            _FakeResponse('{"steps": []}'),
        ]
    )

    with patch("core.agents.planner.get_tool_registry", return_value=_make_fake_registry()):
        with patch.object(Planner, "_try_seed_match", new=AsyncMock(return_value=None)):
            planner = Planner(
                llm_client=fake_llm,
                curr_date="2026-07-26",
                trade_date="2026-07-25",
            )

            plan = await planner.plan("分析601012", context_messages=None)

    if plan.source != PlanSource.REACT_FALLBACK:
        print(f"  ❌ 失败：期望 source=REACT_FALLBACK，实际 source={plan.source}")
        return False

    print("  ✅ 通过：修正重试返回空步骤后正确降级 ReAct")
    return True


async def main() -> int:
    print("=" * 70)
    print("规划失败修正重试验证（v3.6.0 项7）")
    print("=" * 70)

    results = []
    results.append(await test_case_1_normal_plan_no_correction())
    results.append(await test_case_2_correction_retry_succeeds())
    results.append(await test_case_3_correction_retry_fails_fallback_react())
    results.append(await test_case_4_correction_retry_returns_empty_steps())

    print("\n" + "=" * 70)
    passed = sum(1 for r in results if r)
    total = len(results)
    print(f"测试结果：{passed}/{total} 通过")
    print("=" * 70)

    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
