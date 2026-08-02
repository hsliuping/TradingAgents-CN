"""验证智能助手 HITL 机制（v3.5.0 项4）。

测试场景：
1. 关键工具调用 → 保存 pending 操作，返回"需要确认"消息
2. 用户确认 → 执行真正的工作，pending 状态变为 confirmed
3. 用户拒绝 → pending 状态变为 rejected，不执行
4. 非关键工具调用 → 不触发 HITL，直接执行
5. 没有_pending 操作时，确认意图不会触发任何操作

运行方式：
    env\\Scripts\\python.exe scripts\\validate_assistant_hitl.py
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

from core.hitl.assistant_hitl import (
    CRITICAL_TOOL_IDS,
    build_pending_confirmation_reply,
    confirm_pending,
    is_critical_tool,
    is_user_confirming,
    is_user_rejecting,
    list_pending_for_user,
    reject_pending,
    save_pending_critical_action,
    try_resolve_pending_action,
)


class _FakeCollection:
    """模拟 MongoDB collection"""

    def __init__(self):
        self.docs: Dict[str, Dict[str, Any]] = {}

    async def update_one(self, query, update, upsert=False):
        pending_id = query.get("pending_id")
        if pending_id is None:
            # 没有指定 pending_id 的查询，找第一个匹配的
            for pid, doc in self.docs.items():
                if all(doc.get(k) == v for k, v in query.items()):
                    pending_id = pid
                    break

        if pending_id is None and upsert:
            pending_id = f"auto_{len(self.docs)}"

        if pending_id is None:
            result = MagicMock()
            result.modified_count = 0
            result.matched_count = 0
            return result

        # 检查查询条件是否匹配
        existing = self.docs.get(pending_id, {})
        matches = all(existing.get(k) == v for k, v in query.items())

        if not matches and not upsert:
            result = MagicMock()
            result.modified_count = 0
            result.matched_count = 1 if pending_id in self.docs else 0
            return result

        # 应用 $set（合并而非替换）
        if "$set" in update:
            if pending_id not in self.docs:
                self.docs[pending_id] = {}
            self.docs[pending_id].update(update["$set"])

        result = MagicMock()
        result.modified_count = 1
        result.matched_count = 1
        return result

    async def find_one(self, query):
        pending_id = query.get("pending_id")
        if pending_id:
            return self.docs.get(pending_id)
        # 其他查询条件
        for doc in self.docs.values():
            if all(doc.get(k) == v for k, v in query.items()):
                return doc
        return None

    def find(self, query):
        # 返回匹配的文档列表
        docs = [v for v in self.docs.values() if all(v.get(k) == val for k, val in query.items())]
        return _FakeCursor(docs)

    async def update_many(self, query, update):
        result = MagicMock()
        result.modified_count = 0
        return result


class _FakeCursor:
    def __init__(self, docs):
        self._docs = docs

    def sort(self, field, direction):
        return self

    def limit(self, n):
        return self

    async def to_list(self, length=None):
        return self._docs


class _FakeDB:
    """模拟 MongoDB 数据库"""

    def __init__(self):
        self._collections: Dict[str, _FakeCollection] = {}

    def __getitem__(self, name):
        if name not in self._collections:
            self._collections[name] = _FakeCollection()
        return self._collections[name]


async def test_case_1_critical_tool_saves_pending() -> bool:
    """测试1：关键工具调用 → 保存 pending 操作"""
    print("\n[测试1] 关键工具调用 → 保存 pending 操作")

    fake_db = _FakeDB()

    pending_id = await save_pending_critical_action(
        fake_db,
        user_id="test_user_001",
        conversation_id="conv_001",
        tool_id="trigger_stock_analysis",
        tool_arguments={"symbol": "601012", "depth": "deep"},
        display_message="即将分析 601012",
    )

    if not pending_id:
        print("  ❌ 失败：期望返回 pending_id，实际为空")
        return False

    # 断言1：pending_id 以 "hitl_" 开头
    if not pending_id.startswith("hitl_"):
        print(f"  ❌ 失败：期望 pending_id 以 hitl_ 开头，实际 {pending_id}")
        return False

    # 断言2：MongoDB 中有记录
    collection = fake_db._collections.get("hitl_pending_operations")
    if not collection or pending_id not in collection.docs:
        print(f"  ❌ 失败：MongoDB 中无记录")
        return False

    doc = collection.docs[pending_id]
    if doc.get("status") != "pending":
        print(f"  ❌ 失败：期望 status=pending，实际 {doc.get('status')}")
        return False

    if doc.get("operation_type") != "assistant_critical_action":
        print(f"  ❌ 失败：期望 operation_type=assistant_critical_action，实际 {doc.get('operation_type')}")
        return False

    print(f"  ✅ 通过：关键工具调用已保存 pending（id={pending_id}）")
    return True


async def test_case_2_user_confirms_executes() -> bool:
    """测试2：用户确认 → 执行操作，pending 状态变为 confirmed"""
    print("\n[测试2] 用户确认 → 执行操作")

    fake_db = _FakeDB()

    pending_id = await save_pending_critical_action(
        fake_db,
        user_id="test_user_001",
        conversation_id="conv_001",
        tool_id="trigger_stock_analysis",
        tool_arguments={"symbol": "601012"},
    )

    # mock 工具执行
    fake_registry = MagicMock()
    fake_func = MagicMock(return_value="分析任务已创建")
    fake_registry.get_function.return_value = fake_func

    with patch("core.tools.get_tool_registry", return_value=fake_registry):
        # 模拟用户确认
        resolution = await try_resolve_pending_action(
            fake_db,
            user_id="test_user_001",
            conversation_id="conv_001",
            user_message="确认",
        )

    if not resolution:
        print("  ❌ 失败：期望返回 resolution，实际为 None")
        return False

    if resolution.get("type") != "confirmed":
        print(f"  ❌ 失败：期望 type=confirmed，实际 {resolution.get('type')}")
        return False

    if "分析任务已创建" not in resolution.get("result", ""):
        print(f"  ❌ 失败：期望 result 含工具返回值，实际 {resolution.get('result')}")
        return False

    # 断言：工具被调用
    if not fake_func.called:
        print(f"  ❌ 失败：期望工具函数被调用")
        return False

    print("  ✅ 通过：用户确认后正确执行操作")
    return True


async def test_case_3_user_rejects_does_not_execute() -> bool:
    """测试3：用户拒绝 → 不执行操作"""
    print("\n[测试3] 用户拒绝 → 不执行操作")

    fake_db = _FakeDB()

    pending_id = await save_pending_critical_action(
        fake_db,
        user_id="test_user_001",
        conversation_id="conv_001",
        tool_id="trigger_stock_analysis",
        tool_arguments={"symbol": "601012"},
    )

    fake_registry = MagicMock()
    fake_func = MagicMock(return_value="should_not_be_called")
    fake_registry.get_function.return_value = fake_func

    with patch("core.tools.get_tool_registry", return_value=fake_registry):
        resolution = await try_resolve_pending_action(
            fake_db,
            user_id="test_user_001",
            conversation_id="conv_001",
            user_message="取消",
        )

    if not resolution:
        print("  ❌ 失败：期望返回 resolution")
        return False

    if resolution.get("type") != "rejected":
        print(f"  ❌ 失败：期望 type=rejected，实际 {resolution.get('type')}")
        return False

    if fake_func.called:
        print(f"  ❌ 失败：工具不应被调用")
        return False

    print("  ✅ 通过：用户拒绝后正确跳过执行")
    return True


async def test_case_4_non_critical_tool_not_intercepted() -> bool:
    """测试4：非关键工具不触发 HITL"""
    print("\n[测试4] 非关键工具 → 不触发 HITL")

    # 断言：is_critical_tool 对非关键工具返回 False
    if is_critical_tool("get_stock_fundamentals_unified"):
        print("  ❌ 失败：get_stock_fundamentals_unified 不应是关键工具")
        return False

    if is_critical_tool("get_stock_market_data_unified"):
        print("  ❌ 失败：get_stock_market_data_unified 不应是关键工具")
        return False

    # 断言：trigger_stock_analysis 是关键工具
    if not is_critical_tool("trigger_stock_analysis"):
        print("  ❌ 失败：trigger_stock_analysis 应是关键工具")
        return False

    print("  ✅ 通过：非关键工具不被拦截")
    return True


async def test_case_5_no_pending_confirmation_does_nothing() -> bool:
    """测试5：没有 pending 操作时，确认意图不触发任何操作"""
    print("\n[测试5] 无 pending 操作 → 确认意图不触发")

    fake_db = _FakeDB()

    resolution = await try_resolve_pending_action(
        fake_db,
        user_id="test_user_001",
        conversation_id="conv_001",
        user_message="确认",
    )

    if resolution is not None:
        print(f"  ❌ 失败：无 pending 操作时应返回 None，实际 {resolution}")
        return False

    print("  ✅ 通过：无 pending 操作时正确返回 None")
    return True


async def test_case_6_confirmation_reply_built_correctly() -> bool:
    """测试6：确认回复消息构建正确"""
    print("\n[测试6] 确认回复消息构建")

    reply = build_pending_confirmation_reply(
        tool_id="trigger_stock_analysis",
        tool_arguments={"symbol": "601012", "depth": "deep"},
        pending_id="hitl_abc123",
    )

    # 断言：回复包含关键信息
    if "触发股票分析" not in reply:
        print(f"  ❌ 失败：期望回复含工具名，实际: {reply[:100]}")
        return False

    if "601012" not in reply:
        print(f"  ❌ 失败：期望回复含股票代码，实际: {reply[:100]}")
        return False

    if "hitl_abc123" not in reply:
        print(f"  ❌ 失败：期望回复含 pending_id，实际: {reply[:100]}")
        return False

    if "确认" not in reply or "取消" not in reply:
        print(f"  ❌ 失败：期望回复含确认/取消提示")
        return False

    print("  ✅ 通过：确认回复消息正确")
    return True


async def main() -> int:
    print("=" * 70)
    print("智能助手 HITL 验证（v3.5.0 项4）")
    print("=" * 70)

    results = []
    results.append(await test_case_1_critical_tool_saves_pending())
    results.append(await test_case_2_user_confirms_executes())
    results.append(await test_case_3_user_rejects_does_not_execute())
    results.append(await test_case_4_non_critical_tool_not_intercepted())
    results.append(await test_case_5_no_pending_confirmation_does_nothing())
    results.append(await test_case_6_confirmation_reply_built_correctly())

    print("\n" + "=" * 70)
    passed = sum(1 for r in results if r)
    total = len(results)
    print(f"测试结果：{passed}/{total} 通过")
    print("=" * 70)

    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
