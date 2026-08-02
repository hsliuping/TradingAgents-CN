"""验证复盘反思提炼机制（v3.5.0 项2）。

测试场景：
1. 复盘完成后调用 _reflect_trade_review_lesson，断言 run_reflection 被调用
2. 反思成功时写入结构化教训（memory_kind=trade_lesson, source=reflection）
3. 反思失败时降级写入原文（reflection_success=False）
4. mem0 不可用时跳过，不抛异常

运行方式：
    env\\Scripts\\python.exe scripts\\validate_trade_review_reflection.py
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock, patch


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.services.trade_review_service import _reflect_trade_review_lesson


class _FakeAITradeReview:
    """模拟 AITradeReview 对象"""

    def __init__(self):
        self.summary = "本次交易逻辑正确，但止盈时机偏晚"
        self.strengths = ["止盈点设置合理", "仓位控制得当"]
        self.weaknesses = ["止盈偏晚", "对市场情绪判断不足"]
        self.suggestions = ["下次结合市场情绪指标", "止盈分批执行"]
        self.plan_deviation = "实际止盈比计划晚2天"


class _FakeTradeInfo:
    """模拟 TradeInfo 对象"""

    def __init__(self):
        self.code = "601012"
        self.name = "隆基绿能"
        self.first_buy_date = "2026-06-01"


class _FakeMemoryService:
    """模拟 MemoryService"""

    def __init__(self, available: bool = True):
        self.available = available
        self.store_calls: List[Dict[str, Any]] = []

    async def store(self, messages, *, user_id, agent_id, scope, metadata, infer=False):
        self.store_calls.append({
            "messages": messages,
            "user_id": user_id,
            "agent_id": agent_id,
            "scope": scope,
            "metadata": metadata,
            "infer": infer,
        })
        result = MagicMock()
        result.success = True
        result.error = None
        return result


class _FakeLLMResponse:
    """模拟 LLM 响应"""

    def __init__(self, content: str):
        self.content = content


def _make_valid_lessons_json() -> str:
    """生成合法的反思 JSON"""
    return """{
  "reasoning": "本次交易基于基本面买入隆基绿能，止盈点设置合理但执行偏晚，错失部分利润",
  "improvement": "下次应结合市场情绪指标，止盈分批执行避免贪心",
  "summary": "止盈时机偏晚导致利润回撤，需结合情绪指标优化",
  "query": "隆基绿能,止盈时机,市场情绪,分批止盈"
}"""


def _make_invalid_response() -> str:
    return "这不是 JSON"


async def test_case_1_reflection_success() -> bool:
    """测试1：反思成功，写入结构化教训"""
    print("\n[测试1] 反思成功 → 写入结构化教训（memory_kind=trade_lesson）")

    fake_svc = _FakeMemoryService(available=True)
    fake_llm = MagicMock()
    fake_llm.achat = AsyncMock(return_value=_FakeLLMResponse(_make_valid_lessons_json()))

    trade_info = _FakeTradeInfo()
    ai_review = _FakeAITradeReview()

    with patch("core.agents.reflection_helper.get_memory_service", return_value=fake_svc):
        with patch("core.llm.UnifiedLLMClient") as mock_llm_cls:
            mock_llm_cls.from_provider.return_value = fake_llm

            await _reflect_trade_review_lesson(
                db=MagicMock(),
                user_id="test_user_001",
                trade_info=trade_info,
                ai_review=ai_review,
                review_id="review_001",
            )

    # 断言1：MemoryService.store 被调用1次
    if len(fake_svc.store_calls) != 1:
        print(f"  ❌ 失败：期望 store 调用1次，实际 {len(fake_svc.store_calls)} 次")
        return False

    call = fake_svc.store_calls[0]

    # 断言2：memory_kind=trade_lesson
    if call["metadata"].get("memory_kind") != "trade_lesson":
        print(f"  ❌ 失败：期望 memory_kind=trade_lesson，实际 {call['metadata'].get('memory_kind')}")
        return False

    # 断言3：source=reflection
    if call["metadata"].get("source") != "reflection":
        print(f"  ❌ 失败：期望 source=reflection，实际 {call['metadata'].get('source')}")
        return False

    # 断言4：reflection_success=True
    if not call["metadata"].get("reflection_success"):
        print(f"  ❌ 失败：期望 reflection_success=True")
        return False

    # 断言5：写入的内容是 JSON
    content = call["messages"][0]["content"]
    if "reasoning" not in content or "improvement" not in content:
        print(f"  ❌ 失败：期望写入结构化 JSON，实际内容: {content[:100]}")
        return False

    # 断言6：infer=False
    if call["infer"]:
        print(f"  ❌ 失败：期望 infer=False")
        return False

    print("  ✅ 通过：反思成功写入结构化教训")
    return True


async def test_case_2_reflection_fallback_to_raw() -> bool:
    """测试2：LLM 返回非 JSON，降级写入原文"""
    print("\n[测试2] LLM 返回非 JSON → 降级写入原文（reflection_success=False）")

    fake_svc = _FakeMemoryService(available=True)
    fake_llm = MagicMock()
    fake_llm.achat = AsyncMock(return_value=_FakeLLMResponse(_make_invalid_response()))

    trade_info = _FakeTradeInfo()
    ai_review = _FakeAITradeReview()

    with patch("core.agents.reflection_helper.get_memory_service", return_value=fake_svc):
        with patch("core.llm.UnifiedLLMClient") as mock_llm_cls:
            mock_llm_cls.from_provider.return_value = fake_llm

            await _reflect_trade_review_lesson(
                db=MagicMock(),
                user_id="test_user_001",
                trade_info=trade_info,
                ai_review=ai_review,
                review_id="review_002",
            )

    if len(fake_svc.store_calls) != 1:
        print(f"  ❌ 失败：期望 store 调用1次，实际 {len(fake_svc.store_calls)} 次")
        return False

    call = fake_svc.store_calls[0]

    # 断言：reflection_success=False（降级）
    if call["metadata"].get("reflection_success"):
        print(f"  ❌ 失败：期望 reflection_success=False（降级）")
        return False

    # 断言：memory_kind 仍然是 trade_lesson
    if call["metadata"].get("memory_kind") != "trade_lesson":
        print(f"  ❌ 失败：期望 memory_kind=trade_lesson，实际 {call['metadata'].get('memory_kind')}")
        return False

    # 断言：写入的是 fallback 原文
    content = call["messages"][0]["content"]
    if "隆基绿能" not in content:
        print(f"  ❌ 失败：期望 fallback 内容含股票名，实际: {content[:100]}")
        return False

    print("  ✅ 通过：LLM 返回非 JSON 时降级写入原文")
    return True


async def test_case_3_mem0_unavailable_skips() -> bool:
    """测试3：mem0 不可用时跳过"""
    print("\n[测试3] mem0 不可用 → 跳过，不抛异常")

    fake_svc = _FakeMemoryService(available=False)
    trade_info = _FakeTradeInfo()
    ai_review = _FakeAITradeReview()

    with patch("core.agents.reflection_helper.get_memory_service", return_value=fake_svc):
        # 不应该抛异常
        try:
            await _reflect_trade_review_lesson(
                db=MagicMock(),
                user_id="test_user_001",
                trade_info=trade_info,
                ai_review=ai_review,
                review_id="review_003",
            )
        except Exception as e:
            print(f"  ❌ 失败：mem0 不可用时不应抛异常，但抛了: {e}")
            return False

    # 断言：store 没被调用
    if len(fake_svc.store_calls) != 0:
        print(f"  ❌ 失败：期望 store 不被调用，实际调用 {len(fake_svc.store_calls)} 次")
        return False

    print("  ✅ 通过：mem0 不可用时正确跳过")
    return True


async def test_case_4_llm_timeout_fallback() -> bool:
    """测试4：LLM 超时，降级写入原文"""
    print("\n[测试4] LLM 超时 → 降级写入原文")

    fake_svc = _FakeMemoryService(available=True)
    fake_llm = MagicMock()
    fake_llm.achat = AsyncMock(side_effect=asyncio.TimeoutError())

    trade_info = _FakeTradeInfo()
    ai_review = _FakeAITradeReview()

    with patch("core.agents.reflection_helper.get_memory_service", return_value=fake_svc):
        with patch("core.llm.UnifiedLLMClient") as mock_llm_cls:
            mock_llm_cls.from_provider.return_value = fake_llm

            await _reflect_trade_review_lesson(
                db=MagicMock(),
                user_id="test_user_001",
                trade_info=trade_info,
                ai_review=ai_review,
                review_id="review_004",
            )

    if len(fake_svc.store_calls) != 1:
        print(f"  ❌ 失败：期望 store 调用1次（降级），实际 {len(fake_svc.store_calls)} 次")
        return False

    call = fake_svc.store_calls[0]
    if call["metadata"].get("reflection_success"):
        print(f"  ❌ 失败：期望 reflection_success=False（超时降级）")
        return False

    print("  ✅ 通过：LLM 超时时正确降级")
    return True


async def main() -> int:
    print("=" * 70)
    print("复盘反思提炼验证（v3.5.0 项2）")
    print("=" * 70)

    results = []
    results.append(await test_case_1_reflection_success())
    results.append(await test_case_2_reflection_fallback_to_raw())
    results.append(await test_case_3_mem0_unavailable_skips())
    results.append(await test_case_4_llm_timeout_fallback())

    print("\n" + "=" * 70)
    passed = sum(1 for r in results if r)
    total = len(results)
    print(f"测试结果：{passed}/{total} 通过")
    print("=" * 70)

    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
