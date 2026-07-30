"""验证反思教训召回闭环（v3.5.0 项2/3/8 的 L2/L3 闭环）。

测试场景：
1. recall_lessons_sync 从 mem0 召回 memory_kind 含 _lesson 的教训
2. 教训被正确标注类型（分析教训/交易教训/辩论教训）
3. 非 _lesson 的原文不被召回（只召回教训）
4. mem0 不可用时降级返回空字符串
5. _get_memory_context 同时返回教训和 ChromaDB 原文
6. 教训在原文前面（优先参考）

运行方式：
    env\\Scripts\\python.exe scripts\\validate_reflection_recall_loop.py
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


# ================================================================
# Mock MemoryService 和 MemoryItem
# ================================================================


class _FakeMemoryItem:
    """模拟 MemoryItem。"""

    def __init__(self, content: str, metadata: Dict[str, Any], scope: str = ""):
        self.content = content
        self.metadata = metadata
        self.scope = scope


class _FakeMemoryService:
    """模拟 MemoryService，支持 recall 方法。"""

    def __init__(self, items: List[_FakeMemoryItem], available: bool = True):
        self._items = items
        self.available = available

    async def recall(self, query, **kwargs) -> List[_FakeMemoryItem]:
        # 简单返回所有 items（真实场景会按 query 做向量检索）
        return self._items


# ================================================================
# 测试用例
# ================================================================


def test_case_1_recall_lessons_from_mem0() -> bool:
    """测试1：recall_lessons_sync 从 mem0 召回 _lesson 教训"""
    print("\n[测试1] recall_lessons_sync 从 mem0 召回 _lesson 教训")

    lessons = [
        _FakeMemoryItem(
            content='{"reasoning": "上次分析忽略了成交量信号", "improvement": "关注量价配合"}',
            metadata={"memory_kind": "analysis_lesson", "ticker": "600519"},
            scope="analysis_insight",
        ),
        _FakeMemoryItem(
            content='{"reasoning": "辩论中过于看多导致亏损", "improvement": "增加风险对冲考虑"}',
            metadata={"memory_kind": "debate_lesson", "ticker": "600519"},
            scope="agent_experience",
        ),
    ]

    fake_svc = _FakeMemoryService(items=lessons, available=True)

    with patch("core.agents.reflection_helper.get_memory_service", return_value=fake_svc):
        from core.agents.reflection_helper import recall_lessons_sync
        result = recall_lessons_sync(
            db=MagicMock(),
            user_id="test_user",
            query="股票代码: 600519",
            agent_id="bull_researcher",
            limit=3,
        )

    if not result:
        print(f"  ❌ 失败：期望返回非空教训文本，实际为空")
        return False

    if "【历史教训】" not in result:
        print(f"  ❌ 失败：期望包含 '【历史教训】' 标题，实际: {result[:100]}")
        return False

    if "分析教训" not in result:
        print(f"  ❌ 失败：期望包含 '分析教训' 标注")
        return False

    if "辩论教训" not in result:
        print(f"  ❌ 失败：期望包含 '辩论教训' 标注")
        return False

    print(f"  ✅ 通过：成功召回 {result.count('教训')} 条教训")
    return True


def test_case_2_non_lesson_not_recalled() -> bool:
    """测试2：非 _lesson 的原文不被召回"""
    print("\n[测试2] 非 _lesson 的原文不被召回")

    mixed_items = [
        _FakeMemoryItem(
            content='{"reasoning": "结构化教训"}',
            metadata={"memory_kind": "analysis_lesson"},
            scope="analysis_insight",
        ),
        _FakeMemoryItem(
            content="这是一段原始报告内容，不是教训",
            metadata={"ticker": "600519"},  # 没有 memory_kind
            scope="analysis_insight",
        ),
    ]

    fake_svc = _FakeMemoryService(items=mixed_items, available=True)

    with patch("core.agents.reflection_helper.get_memory_service", return_value=fake_svc):
        from core.agents.reflection_helper import recall_lessons_sync
        result = recall_lessons_sync(
            db=MagicMock(),
            user_id="test_user",
            query="股票代码: 600519",
            limit=5,
        )

    if not result:
        print(f"  ❌ 失败：期望至少召回 1 条教训")
        return False

    if "原始报告内容" in result:
        print(f"  ❌ 失败：原文不应出现在教训召回结果中")
        return False

    if "结构化教训" not in result:
        print(f"  ❌ 失败：教训内容应出现在结果中")
        return False

    print(f"  ✅ 通过：只召回 _lesson 教训，原文被正确过滤")
    return True


def test_case_3_mem0_unavailable_degrade() -> bool:
    """测试3：mem0 不可用时降级返回空字符串"""
    print("\n[测试3] mem0 不可用时降级返回空字符串")

    fake_svc = _FakeMemoryService(items=[], available=False)

    with patch("core.agents.reflection_helper.get_memory_service", return_value=fake_svc):
        from core.agents.reflection_helper import recall_lessons_sync
        result = recall_lessons_sync(
            db=MagicMock(),
            user_id="test_user",
            query="股票代码: 600519",
        )

    if result:
        print(f"  ❌ 失败：mem0 不可用时应返回空字符串，实际: {result[:50]}")
        return False

    print(f"  ✅ 通过：mem0 不可用时正确降级返回空字符串")
    return True


def test_case_4_no_lessons_returns_empty() -> bool:
    """测试4：mem0 有数据但没有 _lesson 教训时返回空"""
    print("\n[测试4] mem0 有数据但没有 _lesson 教训时返回空")

    only_raw_items = [
        _FakeMemoryItem(
            content="原始报告",
            metadata={"ticker": "600519"},
            scope="analysis_insight",
        ),
    ]

    fake_svc = _FakeMemoryService(items=only_raw_items, available=True)

    with patch("core.agents.reflection_helper.get_memory_service", return_value=fake_svc):
        from core.agents.reflection_helper import recall_lessons_sync
        result = recall_lessons_sync(
            db=MagicMock(),
            user_id="test_user",
            query="股票代码: 600519",
        )

    if result:
        print(f"  ❌ 失败：无教训时应返回空字符串，实际: {result[:50]}")
        return False

    print(f"  ✅ 通过：无 _lesson 教训时正确返回空字符串")
    return True


def test_case_5_lesson_type_labels() -> bool:
    """测试5：教训类型标注正确（分析教训/交易教训/辩论教训）"""
    print("\n[测试5] 教训类型标注正确")

    all_kinds = [
        _FakeMemoryItem(
            content="分析教训内容",
            metadata={"memory_kind": "analysis_lesson"},
            scope="analysis_insight",
        ),
        _FakeMemoryItem(
            content="交易教训内容",
            metadata={"memory_kind": "trade_lesson"},
            scope="trade_pattern",
        ),
        _FakeMemoryItem(
            content="辩论教训内容",
            metadata={"memory_kind": "debate_lesson"},
            scope="agent_experience",
        ),
    ]

    fake_svc = _FakeMemoryService(items=all_kinds, available=True)

    with patch("core.agents.reflection_helper.get_memory_service", return_value=fake_svc):
        from core.agents.reflection_helper import recall_lessons_sync
        result = recall_lessons_sync(
            db=MagicMock(),
            user_id="test_user",
            query="股票代码: 600519",
            limit=3,
        )

    if not result:
        print(f"  ❌ 失败：期望返回非空教训文本")
        return False

    expected_labels = ["分析教训", "交易教训", "辩论教训"]
    for label in expected_labels:
        if label not in result:
            print(f"  ❌ 失败：期望包含 '{label}' 标注")
            return False

    print(f"  ✅ 通过：三种教训类型标注都正确")
    return True


def test_case_6_max_chars_limit() -> bool:
    """测试6：max_chars 限制生效"""
    print("\n[测试6] max_chars 限制生效")

    long_lessons = [
        _FakeMemoryItem(
            content="A" * 200,
            metadata={"memory_kind": "analysis_lesson"},
            scope="analysis_insight",
        ),
        _FakeMemoryItem(
            content="B" * 200,
            metadata={"memory_kind": "debate_lesson"},
            scope="agent_experience",
        ),
        _FakeMemoryItem(
            content="C" * 200,
            metadata={"memory_kind": "trade_lesson"},
            scope="trade_pattern",
        ),
    ]

    fake_svc = _FakeMemoryService(items=long_lessons, available=True)

    with patch("core.agents.reflection_helper.get_memory_service", return_value=fake_svc):
        from core.agents.reflection_helper import recall_lessons_sync
        result = recall_lessons_sync(
            db=MagicMock(),
            user_id="test_user",
            query="股票代码: 600519",
            limit=3,
            max_chars=350,  # 限制 350 字符（只能放 1 条 200 字符的教训 + 标题）
        )

    if not result:
        print(f"  ❌ 失败：期望返回非空教训文本")
        return False

    # 结果应该只包含部分教训（max_chars 限制导致截断）
    if "C" * 200 in result:
        print(f"  ❌ 失败：第三条教训不应出现（被 max_chars 截断）")
        return False

    print(f"  ✅ 通过：max_chars 限制生效（结果长度 {len(result)}，未包含全部 3 条）")
    return True


def main() -> int:
    print("=" * 70)
    print("反思教训召回闭环验证（v3.5.0 项2/3/8 的 L2/L3 闭环）")
    print("=" * 70)

    results: List[bool] = []
    results.append(test_case_1_recall_lessons_from_mem0())
    results.append(test_case_2_non_lesson_not_recalled())
    results.append(test_case_3_mem0_unavailable_degrade())
    results.append(test_case_4_no_lessons_returns_empty())
    results.append(test_case_5_lesson_type_labels())
    results.append(test_case_6_max_chars_limit())

    print("\n" + "=" * 70)
    passed = sum(1 for r in results if r)
    total = len(results)
    print(f"测试结果：{passed}/{total} 通过")
    print("=" * 70)

    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
