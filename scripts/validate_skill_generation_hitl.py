"""验证 Skill 生成 HITL 机制（v3.6.0 项6 三种路径）。

测试场景：
1. 路径A：iteration_controller 失败后写入 skill_iteration_alerts 集合
2. 路径B：resolve_agent_workshop_blocking_gaps 不再直接调用 build_version（源码静态检查）
3. 路径C：confirm_and_create 不再直接调用 bind_skills_to_agents（源码静态检查）
4. 路径B：SkillReviewService.create_pending_reviews_for_workshop 正确写入 skill_review_queue
5. 路径C：SkillReviewService.create_pending_reviews_for_workflow 正确写入 skill_review_queue
6. confirm：SkillReviewService.confirm 触发绑定，状态变为 confirmed_bound
7. reject：SkillReviewService.reject 标记为 unbound，external_skills 状态变为 unbound
8. list_pending：列出指定会话的待审核记录

运行方式：
    env\\Scripts\\python.exe scripts\\validate_skill_generation_hitl.py
"""

from __future__ import annotations

import asyncio
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List
from unittest.mock import AsyncMock, MagicMock, patch


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))


# ================================================================
# 测试辅助：模拟 motor MongoDB
# ================================================================


class _FakeCollection:
    """模拟 motor MongoDB collection（同时支持 sync pymongo 和 async motor 调用）。"""

    def __init__(self, name: str, store: Dict[str, Dict[str, Any]]):
        self.name = name
        self._store = store  # 共享存储：{doc_id: doc}

    async def find_one(self, query: Dict[str, Any], projection: Dict[str, Any] = None):
        for doc in self._store.values():
            if self._match(doc, query):
                result = dict(doc)
                if projection:
                    # 简化处理：只保留 projection 中字段值为 1 的字段
                    result = {k: v for k, v in result.items() if projection.get(k, 0) == 1}
                return result
        return None

    def find(self, query: Dict[str, Any]):
        """同步返回 cursor 对象（模拟 motor 的链式调用）。

        motor 的 find() 不需要 await，返回一个可以 .sort() 链式调用的 cursor，
        cursor 本身是 async iterable。
        """
        matching = [dict(doc) for doc in self._store.values() if self._match(doc, query)]

        class _Cursor:
            def __init__(self, items):
                self._items = items

            def sort(self, field: str, direction: int = 1):
                self._items.sort(key=lambda x: x.get(field, ""), reverse=(direction == -1))
                return self

            def __aiter__(self):
                self._idx = 0
                return self

            async def __anext__(self):
                if self._idx >= len(self._items):
                    raise StopAsyncIteration
                item = self._items[self._idx]
                self._idx += 1
                return item

        return _Cursor(matching)

    def update_one(self, query: Dict[str, Any], update: Dict[str, Any], upsert: bool = False):
        """同步执行 update_one，返回 _AwaitableResult。

        同时支持两种调用方式：
        - sync（pymongo 风格）：result = collection.update_one(...) → result.matched_count
        - async（motor 风格）：result = await collection.update_one(...) → result.matched_count

        这是必要的，因为：
        - iteration_controller._write_iteration_alert 使用 get_mongo_db_sync（pymongo 同步）
        - SkillReviewService 使用 motor async（await collection.update_one(...)）
        """
        for doc in self._store.values():
            if self._match(doc, query):
                self._apply_update(doc, update)
                return _AwaitableResult(matched_count=1, modified_count=1, upserted_id=None)
        if upsert:
            new_doc: Dict[str, Any] = {}
            # 从 query 中提取等值条件作为新文档基础
            for k, v in query.items():
                if not isinstance(v, dict) and k != "_id":
                    new_doc[k] = v
            self._apply_update(new_doc, update)
            doc_id = new_doc.get("review_id") or new_doc.get("tool_id") or new_doc.get("alert_id") or str(len(self._store))
            self._store[doc_id] = new_doc
            return _AwaitableResult(matched_count=0, modified_count=0, upserted_id=doc_id)
        return _AwaitableResult(matched_count=0, modified_count=0, upserted_id=None)

    def update_many(self, query: Dict[str, Any], update: Dict[str, Any]):
        """同步执行 update_many，返回 _AwaitableResult（同时支持 sync/async 调用）。"""
        modified = 0
        for doc in self._store.values():
            if self._match(doc, query):
                self._apply_update(doc, update)
                modified += 1
        return _AwaitableResult(matched_count=modified, modified_count=modified)

    @staticmethod
    def _match(doc: Dict[str, Any], query: Dict[str, Any]) -> bool:
        for key, value in query.items():
            if key == "$or":
                if not any(_FakeCollection._match(doc, sub) for sub in value):
                    return False
            elif key == "_id":
                continue  # 跳过 _id 检查
            elif isinstance(value, dict):
                if "$in" in value:
                    if doc.get(key) not in value["$in"]:
                        return False
                else:
                    return False  # 简化：不支持其他操作符
            else:
                if doc.get(key) != value:
                    return False
        return True

    @staticmethod
    def _apply_update(doc: Dict[str, Any], update: Dict[str, Any]) -> None:
        for op, fields in update.items():
            if op == "$set":
                for k, v in fields.items():
                    doc[k] = v
            elif op == "$setOnInsert":
                for k, v in fields.items():
                    if k not in doc:
                        doc[k] = v


class _AwaitableResult:
    """可同时被 await 和直接访问属性的结果对象。

    - sync 调用：result = collection.update_one(...) → 直接访问 result.matched_count
    - async 调用：result = await collection.update_one(...) → 同样访问 result.matched_count

    实现 __await__ 让 `await result` 返回自身，sync 调用则跳过 await 直接用。
    """

    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)

    def __await__(self):
        async def _coro():
            return self
        return _coro().__await__()


class _FakeDB:
    """模拟 motor MongoDB 数据库（同时支持 db[col] 和 db.col 访问）。"""

    def __init__(self):
        self._collections: Dict[str, _FakeCollection] = {}
        self._stores: Dict[str, Dict[str, Dict[str, Any]]] = {}

    def _ensure_collection(self, name: str) -> _FakeCollection:
        # 关键：不要覆盖已存在的 store（避免 get_store 预置的数据丢失）
        if name not in self._stores:
            self._stores[name] = {}
        if name not in self._collections:
            self._collections[name] = _FakeCollection(name, self._stores[name])
        return self._collections[name]

    def __getitem__(self, name: str) -> _FakeCollection:
        return self._ensure_collection(name)

    def __getattr__(self, name: str) -> _FakeCollection:
        # 支持 db.skill_iteration_alerts 这样的属性访问（motor 同时支持 [] 和 .）
        # 注意：只对未知属性生效，已知属性（_ 开头）走默认行为
        if name.startswith("_"):
            raise AttributeError(name)
        return self._ensure_collection(name)

    def get_store(self, name: str) -> Dict[str, Dict[str, Any]]:
        if name not in self._stores:
            self._stores[name] = {}
        return self._stores[name]


# ================================================================
# 测试用例
# ================================================================


async def test_case_1_path_a_iteration_alert() -> bool:
    """测试1：路径A - iteration_controller._write_iteration_alert 写入 skill_iteration_alerts"""
    print("\n[测试1] 路径A：iteration_controller 失败后写入 skill_iteration_alerts 集合")

    from core.tools.external.iteration_controller import IterationController
    from core.tools.external.skill_spec import SkillSpec

    fake_db = _FakeDB()

    # 构造一个最小 spec（仅必填字段 tool_id/display_name/description）
    spec = SkillSpec(
        tool_id="test_skill_path_a",
        display_name="测试Skill路径A",
        description="用于验证路径A的测试Skill",
        category="test",
        data_source="local_only",
        metadata={"session_id": "sess_path_a", "user_id": "test_user"},
    )

    # 构造一个最小 IterationRound 列表
    fake_iterations = []
    for i in range(3):
        it = MagicMock()
        it.round_number = i + 1
        it.decision = "RETRY"
        it.validation = MagicMock(passed=False)
        it.sandbox = MagicMock(success=False)
        it.eval_score = MagicMock(total=4.0)
        it.business_verification = MagicMock(passed=False)
        it.reflection = MagicMock(root_cause="测试失败原因")
        fake_iterations.append(it)

    controller = IterationController()

    # mock get_mongo_db_sync 返回 fake_db
    with patch("app.core.database.get_mongo_db_sync", return_value=fake_db):
        controller._write_iteration_alert(
            spec=spec,
            run_id="test_run_001",
            iterations=fake_iterations,
            failure_summary="测试失败摘要：所有迭代均未通过",
            total_time=99.5,
            engine="legacy_pipeline",
        )

    # 断言：skill_iteration_alerts 集合有记录
    store = fake_db.get_store("skill_iteration_alerts")
    if len(store) == 0:
        print("  ❌ 失败：skill_iteration_alerts 集合无记录")
        return False

    # 取出记录验证字段
    doc = list(store.values())[0]
    if doc.get("tool_id") != "test_skill_path_a":
        print(f"  ❌ 失败：tool_id 不匹配，期望 test_skill_path_a，实际 {doc.get('tool_id')}")
        return False
    if doc.get("status") != "pending_human_review":
        print(f"  ❌ 失败：status 应为 pending_human_review，实际 {doc.get('status')}")
        return False
    if doc.get("alert_id") != "alert_test_run_001_test_skill_path_a":
        print(f"  ❌ 失败：alert_id 不匹配，实际 {doc.get('alert_id')}")
        return False
    if doc.get("total_rounds") != 3:
        print(f"  ❌ 失败：total_rounds 应为 3，实际 {doc.get('total_rounds')}")
        return False

    print("  ✅ 通过：skill_iteration_alerts 集合有正确的待审核记录")
    return True


async def test_case_2_path_b_no_direct_build_version() -> bool:
    """测试2：路径B - resolve_agent_workshop_blocking_gaps 源码中不再直接调用 build_version"""
    print("\n[测试2] 路径B：源码静态检查 - 不再直接调用 ws_service.build_version")

    target_file = ROOT_DIR / "core" / "tools" / "implementations" / "agent_builder" / "nanobot_agent_builder_tools.py"
    if not target_file.exists():
        print(f"  ❌ 失败：文件不存在 {target_file}")
        return False

    content = target_file.read_text(encoding="utf-8")

    # 提取 resolve_agent_workshop_blocking_gaps 函数体（从 def 到下一个 @tool）
    start_marker = "async def resolve_agent_workshop_blocking_gaps("
    end_marker = "\n@tool\n"

    start_idx = content.find(start_marker)
    if start_idx < 0:
        print("  ❌ 失败：找不到 resolve_agent_workshop_blocking_gaps 函数定义")
        return False

    end_idx = content.find(end_marker, start_idx)
    if end_idx < 0:
        end_idx = len(content)

    func_body = content[start_idx:end_idx]

    # 断言1：函数体内不再包含 ws_service.build_version 调用
    if "ws_service.build_version(" in func_body:
        print("  ❌ 失败：resolve_agent_workshop_blocking_gaps 仍直接调用 ws_service.build_version")
        return False

    # 断言2：函数体内不再包含 ws_service.sync_version_required_tools 调用
    if "ws_service.sync_version_required_tools(" in func_body:
        print("  ❌ 失败：resolve_agent_workshop_blocking_gaps 仍直接调用 ws_service.sync_version_required_tools")
        return False

    # 断言3：函数体内包含 SkillReviewService.create_pending_reviews_for_workshop 调用
    if "create_pending_reviews_for_workshop" not in func_body:
        print("  ❌ 失败：resolve_agent_workshop_blocking_gaps 未调用 create_pending_reviews_for_workshop")
        return False

    # 断言4：函数体内包含 pending_user_review 字段
    if "pending_user_review" not in func_body:
        print("  ❌ 失败：resolve_agent_workshop_blocking_gaps 返回值未包含 pending_user_review")
        return False

    print("  ✅ 通过：路径B 源码不再直接调用 build_version，改为写入待审核记录")
    return True


async def test_case_3_path_c_no_direct_bind() -> bool:
    """测试3：路径C - confirm_and_create 源码中不再直接调用 bind_skills_to_agents"""
    print("\n[测试3] 路径C：源码静态检查 - 不再直接调用 bind_skills_to_agents")

    target_file = ROOT_DIR / "app" / "services" / "workflow_generation_service.py"
    if not target_file.exists():
        print(f"  ❌ 失败：文件不存在 {target_file}")
        return False

    content = target_file.read_text(encoding="utf-8")

    # 提取 confirm_and_create 函数体
    start_marker = "async def confirm_and_create("
    start_idx = content.find(start_marker)
    if start_idx < 0:
        print("  ❌ 失败：找不到 confirm_and_create 函数定义")
        return False

    # 找下一个 async def（同级别）
    next_def = content.find("\n    async def ", start_idx + 10)
    end_idx = next_def if next_def > 0 else len(content)
    func_body = content[start_idx:end_idx]

    # 断言1：函数体内不再包含 _skill_orch.bind_skills_to_agents 调用
    if "_skill_orch.bind_skills_to_agents(" in func_body:
        print("  ❌ 失败：confirm_and_create 仍直接调用 _skill_orch.bind_skills_to_agents")
        return False

    # 断言2：函数体内包含 create_pending_reviews_for_workflow 调用
    if "create_pending_reviews_for_workflow" not in func_body:
        print("  ❌ 失败：confirm_and_create 未调用 create_pending_reviews_for_workflow")
        return False

    # 断言3：函数体内包含 skip_skill_publishing 参数传递
    if "skip_skill_publishing" not in func_body:
        print("  ❌ 失败：confirm_and_create 未使用 skip_skill_publishing 参数")
        return False

    # 断言4：返回值包含 pending_user_review
    if "pending_user_review" not in func_body:
        print("  ❌ 失败：confirm_and_create 返回值未包含 pending_user_review")
        return False

    print("  ✅ 通过：路径C 源码不再直接调用 bind_skills_to_agents，改为写入待审核记录")
    return True


async def test_case_4_path_b_write_review_queue() -> bool:
    """测试4：路径B - SkillReviewService.create_pending_reviews_for_workshop 正确写入 skill_review_queue"""
    print("\n[测试4] 路径B：SkillReviewService.create_pending_reviews_for_workshop 写入 skill_review_queue")

    from app.services.skill_review_service import SkillReviewService, REVIEW_COLLECTION, SKILL_COLLECTION

    fake_db = _FakeDB()

    # 预置 external_skills 集合数据（用于拉取代码片段）
    skill_store = fake_db.get_store(SKILL_COLLECTION)
    skill_store["skill_b_001"] = {
        "tool_id": "skill_b_001",
        "display_name": "龙虎榜数据查询",
        "code": "def fetch_dragon_tiger():\n    return []\n",
        "final_score": 8.5,
        "generation_rounds": 2,
        "generation_time": 45.3,
        "metadata": {"generation_context": {"test_pass_rate": 1.0}},
    }

    successful_items = [
        {
            "skill_tool_id": "skill_b_001",
            "skill_display_name": "龙虎榜数据查询",
            "gap_description": "需要查询龙虎榜数据",
            "gap_id": "gap_1",
            "session_id": "skill_sess_001",
            "status": "completed",
            "elapsed_seconds": 45,
            "pipeline_stage": "completed",
        },
    ]

    svc = SkillReviewService(db=fake_db)
    reviews = await svc.create_pending_reviews_for_workshop(
        workshop_session_id="ws_session_001",
        agent_spec_id="spec_001",
        agent_name="测试Agent",
        user_id="test_user_001",
        successful_items=successful_items,
    )

    # 断言1：返回 1 条审核记录
    if len(reviews) != 1:
        print(f"  ❌ 失败：期望返回 1 条审核记录，实际 {len(reviews)}")
        return False

    # 断言2：skill_review_queue 集合有记录
    review_store = fake_db.get_store(REVIEW_COLLECTION)
    if len(review_store) != 1:
        print(f"  ❌ 失败：skill_review_queue 集合应有 1 条记录，实际 {len(review_store)}")
        return False

    # 断言3：记录字段正确
    review = list(review_store.values())[0]
    if review.get("source_path") != "agent_workshop":
        print(f"  ❌ 失败：source_path 应为 agent_workshop，实际 {review.get('source_path')}")
        return False
    if review.get("status") != "pending_user_review":
        print(f"  ❌ 失败：status 应为 pending_user_review，实际 {review.get('status')}")
        return False
    if review.get("workshop_session_id") != "ws_session_001":
        print(f"  ❌ 失败：workshop_session_id 不匹配")
        return False
    if review.get("agent_name") != "测试Agent":
        print(f"  ❌ 失败：agent_name 不匹配")
        return False
    if not review.get("code_preview"):
        print("  ❌ 失败：code_preview 为空")
        return False
    if not review.get("test_result_summary"):
        print("  ❌ 失败：test_result_summary 为空")
        return False

    print("  ✅ 通过：路径B 正确写入 skill_review_queue，含代码片段和测试摘要")
    return True


async def test_case_5_path_c_write_review_queue() -> bool:
    """测试5：路径C - SkillReviewService.create_pending_reviews_for_workflow 正确写入 skill_review_queue"""
    print("\n[测试5] 路径C：SkillReviewService.create_pending_reviews_for_workflow 写入 skill_review_queue")

    from app.services.skill_review_service import SkillReviewService, REVIEW_COLLECTION, SKILL_COLLECTION

    fake_db = _FakeDB()

    # 预置 external_skills 集合数据
    skill_store = fake_db.get_store(SKILL_COLLECTION)
    skill_store["skill_c_001"] = {
        "tool_id": "skill_c_001",
        "display_name": "财报数据提取",
        "code": "def extract_financial():\n    return {}\n",
        "final_score": 7.8,
        "generation_rounds": 3,
        "generation_time": 60.0,
        "metadata": {},
    }
    skill_store["skill_c_002"] = {
        "tool_id": "skill_c_002",
        "display_name": "行业对标分析",
        "code": "def industry_benchmark():\n    return []\n",
        "final_score": 8.2,
        "generation_rounds": 2,
        "generation_time": 50.0,
        "metadata": {},
    }

    skill_results = [
        {"skill_name": "财报数据提取", "status": "completed", "skill_id": "skill_c_001"},
        {"skill_name": "行业对标分析", "status": "completed", "skill_id": "skill_c_002"},
        {"skill_name": "失败Skill", "status": "failed", "error": "生成超时"},
    ]

    # 构造一个模拟蓝图（带 gap_analysis.missing_skills）
    blueprint = MagicMock()
    blueprint.gap_analysis = MagicMock()
    blueprint.gap_analysis.missing_skills = [
        MagicMock(skill_name="财报数据提取", target_agent_id="fundamentals_analyst"),
        MagicMock(skill_name="行业对标分析", target_agent_id="sector_analyst"),
    ]

    svc = SkillReviewService(db=fake_db)
    reviews = await svc.create_pending_reviews_for_workflow(
        workflow_session_id="wf_session_001",
        workflow_id="wf_001",
        user_id="test_user_002",
        skill_results=skill_results,
        blueprint=blueprint,
    )

    # 断言1：返回 2 条审核记录（失败的 skill 不写入）
    if len(reviews) != 2:
        print(f"  ❌ 失败：期望返回 2 条审核记录（排除 failed），实际 {len(reviews)}")
        return False

    # 断言2：skill_review_queue 集合有 2 条记录
    review_store = fake_db.get_store(REVIEW_COLLECTION)
    if len(review_store) != 2:
        print(f"  ❌ 失败：skill_review_queue 集合应有 2 条记录，实际 {len(review_store)}")
        return False

    # 断言3：所有记录都是 ai_workflow 来源
    for review in review_store.values():
        if review.get("source_path") != "ai_workflow":
            print(f"  ❌ 失败：source_path 应为 ai_workflow，实际 {review.get('source_path')}")
            return False
        if review.get("workflow_session_id") != "wf_session_001":
            print(f"  ❌ 失败：workflow_session_id 不匹配")
            return False

    # 断言4：target_agent_id 从蓝图映射正确
    fundamentals_review = next((r for r in review_store.values() if r.get("tool_id") == "skill_c_001"), None)
    if not fundamentals_review:
        print("  ❌ 失败：未找到 skill_c_001 的审核记录")
        return False
    if fundamentals_review.get("target_agent_id") != "fundamentals_analyst":
        print(f"  ❌ 失败：target_agent_id 应为 fundamentals_analyst，实际 {fundamentals_review.get('target_agent_id')}")
        return False

    print("  ✅ 通过：路径C 正确写入 skill_review_queue，target_agent_id 从蓝图映射")
    return True


async def test_case_6_confirm_triggers_binding() -> bool:
    """测试6：confirm 触发绑定，状态变为 confirmed_bound"""
    print("\n[测试6] confirm：调用后触发绑定，状态变为 confirmed_bound")

    from app.services.skill_review_service import (
        SkillReviewService,
        REVIEW_COLLECTION,
        SKILL_COLLECTION,
        STATUS_PENDING,
        STATUS_CONFIRMED,
        SOURCE_AI_WORKFLOW,
    )

    fake_db = _FakeDB()

    # 预置 external_skills（路径C，draft 状态）
    skill_store = fake_db.get_store(SKILL_COLLECTION)
    skill_store["skill_confirm_001"] = {
        "tool_id": "skill_confirm_001",
        "display_name": "测试确认Skill",
        "code": "def test(): pass",
        "status": "draft",
    }

    # 预置 skill_review_queue（pending 状态，路径C）
    review_store = fake_db.get_store(REVIEW_COLLECTION)
    review_store["review_confirm_001"] = {
        "review_id": "review_confirm_001",
        "tool_id": "skill_confirm_001",
        "display_name": "测试确认Skill",
        "source_path": SOURCE_AI_WORKFLOW,
        "workflow_session_id": "wf_session_confirm",
        "workshop_session_id": "",
        "target_agent_id": "fundamentals_analyst",
        "status": STATUS_PENDING,
        "code_preview": "def test(): pass",
        "test_result_summary": "评估分数: 8.0",
    }

    svc = SkillReviewService(db=fake_db)

    # mock SkillOrchestrator._bind_one 避免真实数据库操作
    with patch("core.workflow.generator.skill_orchestrator.SkillOrchestrator._bind_one", new_callable=AsyncMock) as mock_bind:
        result = await svc.confirm(
            session_id="wf_session_confirm",
            tool_id="skill_confirm_001",
            user_id="test_user_confirm",
            note="代码审核通过",
        )

    # 断言1：返回状态为 confirmed_bound
    if result.get("status") != STATUS_CONFIRMED:
        print(f"  ❌ 失败：返回 status 应为 {STATUS_CONFIRMED}，实际 {result.get('status')}")
        return False

    # 断言2：_bind_one 被调用（路径C 绑定逻辑）
    if mock_bind.call_count != 1:
        print(f"  ❌ 失败：_bind_one 应被调用 1 次，实际 {mock_bind.call_count}")
        return False

    # 断言3：_bind_one 参数正确
    call_args = mock_bind.call_args
    if call_args.args[0] != "fundamentals_analyst":
        print(f"  ❌ 失败：_bind_one 第一个参数应为 fundamentals_analyst，实际 {call_args.args[0]}")
        return False
    if call_args.args[1] != "skill_confirm_001":
        print(f"  ❌ 失败：_bind_one 第二个参数应为 skill_confirm_001，实际 {call_args.args[1]}")
        return False

    # 断言4：审核记录状态已更新为 confirmed_bound
    updated_review = review_store["review_confirm_001"]
    if updated_review.get("status") != STATUS_CONFIRMED:
        print(f"  ❌ 失败：审核记录状态应为 {STATUS_CONFIRMED}，实际 {updated_review.get('status')}")
        return False
    if updated_review.get("reviewer_user_id") != "test_user_confirm":
        print(f"  ❌ 失败：reviewer_user_id 未更新")
        return False

    # 断言5：external_skills 中 skill 状态从 draft 切换为 active
    updated_skill = skill_store["skill_confirm_001"]
    if updated_skill.get("status") != "active":
        print(f"  ❌ 失败：external_skills 中 skill 状态应为 active，实际 {updated_skill.get('status')}")
        return False

    print("  ✅ 通过：confirm 触发绑定，审核状态和 skill 状态正确更新")
    return True


async def test_case_7_reject_marks_unbound() -> bool:
    """测试7：reject 标记为 unbound，external_skills 状态变为 unbound"""
    print("\n[测试7] reject：调用后 Skill 留在工坊（status=unbound），不绑定")

    from app.services.skill_review_service import (
        SkillReviewService,
        REVIEW_COLLECTION,
        SKILL_COLLECTION,
        STATUS_PENDING,
        STATUS_REJECTED,
        SOURCE_AGENT_WORKSHOP,
    )

    fake_db = _FakeDB()

    # 预置 external_skills（draft 状态）
    skill_store = fake_db.get_store(SKILL_COLLECTION)
    skill_store["skill_reject_001"] = {
        "tool_id": "skill_reject_001",
        "display_name": "测试拒绝Skill",
        "code": "def test(): pass",
        "status": "draft",
    }

    # 预置 skill_review_queue（pending 状态，路径B）
    review_store = fake_db.get_store(REVIEW_COLLECTION)
    review_store["review_reject_001"] = {
        "review_id": "review_reject_001",
        "tool_id": "skill_reject_001",
        "display_name": "测试拒绝Skill",
        "source_path": SOURCE_AGENT_WORKSHOP,
        "workshop_session_id": "ws_session_reject",
        "workflow_session_id": "",
        "agent_spec_id": "spec_reject",
        "target_agent_id": "",
        "status": STATUS_PENDING,
    }

    # 预置 agent_workshop_sessions（含 gap_report.resolved_gaps）
    session_store = fake_db.get_store("agent_workshop_sessions")
    session_store["ws_session_reject"] = {
        "session_id": "ws_session_reject",
        "gap_report": {
            "resolved_gaps": [
                {
                    "skill_tool_id": "skill_reject_001",
                    "skill_display_name": "测试拒绝Skill",
                    "status": "completed",
                },
            ],
        },
    }

    svc = SkillReviewService(db=fake_db)
    result = await svc.reject(
        session_id="ws_session_reject",
        tool_id="skill_reject_001",
        user_id="test_user_reject",
        note="代码不符合预期",
    )

    # 断言1：返回状态为 rejected_unbound
    if result.get("status") != STATUS_REJECTED:
        print(f"  ❌ 失败：返回 status 应为 {STATUS_REJECTED}，实际 {result.get('status')}")
        return False

    # 断言2：审核记录状态已更新
    updated_review = review_store["review_reject_001"]
    if updated_review.get("status") != STATUS_REJECTED:
        print(f"  ❌ 失败：审核记录状态应为 {STATUS_REJECTED}，实际 {updated_review.get('status')}")
        return False
    if updated_review.get("review_action_note") != "代码不符合预期":
        print(f"  ❌ 失败：review_action_note 未更新")
        return False

    # 断言3：external_skills 中 skill 状态变为 unbound（不删除）
    updated_skill = skill_store["skill_reject_001"]
    if updated_skill.get("status") != "unbound":
        print(f"  ❌ 失败：external_skills 中 skill 状态应为 unbound，实际 {updated_skill.get('status')}")
        return False
    if updated_skill.get("rejection_reason") != "代码不符合预期":
        print(f"  ❌ 失败：rejection_reason 未设置")
        return False

    # 断言4：workshop_session 的 gap_report.resolved_gaps 中对应 skill 已被清理
    updated_session = session_store["ws_session_reject"]
    resolved_gaps = updated_session.get("gap_report", {}).get("resolved_gaps", [])
    if resolved_gaps and resolved_gaps[0].get("skill_tool_id") is not None:
        print(f"  ❌ 失败：workshop gap_report 中 generated_skill_id 未被清理")
        return False

    # 断言5：skill 仍在 external_skills 集合（未被删除）
    if "skill_reject_001" not in skill_store:
        print("  ❌ 失败：skill 已从 external_skills 删除（应保留为 unbound）")
        return False

    print("  ✅ 通过：reject 标记为 unbound，Skill 留在工坊，gap_report 已清理")
    return True


async def test_case_8_list_pending() -> bool:
    """测试8：list_pending 列出指定会话的待审核记录"""
    print("\n[测试8] list_pending：按会话 ID 列出待审核记录")

    from app.services.skill_review_service import (
        SkillReviewService,
        REVIEW_COLLECTION,
        STATUS_PENDING,
        SOURCE_AGENT_WORKSHOP,
        SOURCE_AI_WORKFLOW,
    )

    fake_db = _FakeDB()
    review_store = fake_db.get_store(REVIEW_COLLECTION)

    # 写入 3 条记录：2 条路径B（同一会话），1 条路径C
    review_store["r1"] = {
        "review_id": "r1",
        "tool_id": "t1",
        "workshop_session_id": "ws_list_test",
        "workflow_session_id": "",
        "source_path": SOURCE_AGENT_WORKSHOP,
        "status": STATUS_PENDING,
        "created_at": "2026-07-26T10:00:00",
    }
    review_store["r2"] = {
        "review_id": "r2",
        "tool_id": "t2",
        "workshop_session_id": "ws_list_test",
        "workflow_session_id": "",
        "source_path": SOURCE_AGENT_WORKSHOP,
        "status": STATUS_PENDING,
        "created_at": "2026-07-26T11:00:00",
    }
    review_store["r3"] = {
        "review_id": "r3",
        "tool_id": "t3",
        "workshop_session_id": "",
        "workflow_session_id": "wf_list_test",
        "source_path": SOURCE_AI_WORKFLOW,
        "status": STATUS_PENDING,
        "created_at": "2026-07-26T12:00:00",
    }
    review_store["r4"] = {
        "review_id": "r4",
        "tool_id": "t4",
        "workshop_session_id": "ws_other",
        "workflow_session_id": "",
        "source_path": SOURCE_AGENT_WORKSHOP,
        "status": "confirmed_bound",  # 非待审核
        "created_at": "2026-07-26T09:00:00",
    }

    svc = SkillReviewService(db=fake_db)

    # 测试1：列出路径B 会话的待审核（应返回 2 条）
    items_b = await svc.list_pending("ws_list_test", source_path=SOURCE_AGENT_WORKSHOP)
    if len(items_b) != 2:
        print(f"  ❌ 失败：路径B 会话应返回 2 条待审核，实际 {len(items_b)}")
        return False

    # 测试2：列出路径C 会话的待审核（应返回 1 条）
    items_c = await svc.list_pending("wf_list_test", source_path=SOURCE_AI_WORKFLOW)
    if len(items_c) != 1:
        print(f"  ❌ 失败：路径C 会话应返回 1 条待审核，实际 {len(items_c)}")
        return False

    # 测试3：不指定 source_path，应同时支持两种会话
    items_all_b = await svc.list_pending("ws_list_test")
    if len(items_all_b) != 2:
        print(f"  ❌ 失败：不指定 source_path 时路径B 会话应返回 2 条，实际 {len(items_all_b)}")
        return False

    print("  ✅ 通过：list_pending 正确按会话和 source_path 过滤")
    return True


# ================================================================
# 主入口
# ================================================================


async def main() -> int:
    print("=" * 70)
    print("Skill 生成 HITL 验证（v3.6.0 项6 三种路径）")
    print("=" * 70)

    results = []
    results.append(await test_case_1_path_a_iteration_alert())
    results.append(await test_case_2_path_b_no_direct_build_version())
    results.append(await test_case_3_path_c_no_direct_bind())
    results.append(await test_case_4_path_b_write_review_queue())
    results.append(await test_case_5_path_c_write_review_queue())
    results.append(await test_case_6_confirm_triggers_binding())
    results.append(await test_case_7_reject_marks_unbound())
    results.append(await test_case_8_list_pending())

    print("\n" + "=" * 70)
    passed = sum(1 for r in results if r)
    total = len(results)
    print(f"测试结果：{passed}/{total} 通过")
    print("=" * 70)

    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
