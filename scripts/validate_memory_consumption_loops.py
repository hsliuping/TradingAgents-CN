"""Validate that recalled memories are actually injected into downstream consumption paths."""

from __future__ import annotations

import asyncio
import sys
from contextlib import ExitStack
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, List, Optional
from unittest.mock import patch


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.services import intelligent_assistant_service as assistant_module
from app.services import skill_generation_service as skill_module
from app.services import unified_analysis_service as analysis_module
from app.services import workflow_growth_service as workflow_growth_module
from core.tools.external import PipelineResult, SkillCreationSession, SkillSpec


class _AsyncCollection:
    def __init__(self, find_one_result: Dict[str, Any] | None = None):
        self.find_one_result = find_one_result
        self.update_calls: List[Dict[str, Any]] = []

    async def find_one(self, *args: Any, **kwargs: Any) -> Dict[str, Any] | None:
        del args, kwargs
        return self.find_one_result

    async def update_one(self, *args: Any, **kwargs: Any) -> None:
        self.update_calls.append({"args": args, "kwargs": kwargs})


class _UpdateResult:
    def __init__(self, modified_count: int):
        self.modified_count = modified_count


class _AsyncCursor:
    def __init__(self, docs: List[Dict[str, Any]]):
        self._docs = [dict(doc) for doc in docs]

    def sort(self, field: str, direction: int) -> "_AsyncCursor":
        reverse = direction < 0
        self._docs.sort(key=lambda doc: doc.get(field) or datetime.min, reverse=reverse)
        return self

    def limit(self, size: int) -> "_AsyncCursor":
        self._docs = self._docs[:size]
        return self

    async def to_list(self, length: int) -> List[Dict[str, Any]]:
        return [dict(doc) for doc in self._docs[:length]]


class _GrowthMemoryCollection:
    def __init__(self, docs: List[Dict[str, Any]]):
        self._docs = [dict(doc) for doc in docs]

    async def update_one(self, query: Dict[str, Any], update: Dict[str, Any]) -> _UpdateResult:
        for doc in self._docs:
            if _matches_query(doc, query):
                for key, value in (update.get("$set") or {}).items():
                    doc[key] = value
                return _UpdateResult(1)
        return _UpdateResult(0)

    async def find_one(self, query: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        for doc in self._docs:
            if _matches_query(doc, query):
                return dict(doc)
        return None

    def find(self, query: Dict[str, Any]) -> _AsyncCursor:
        matched = [doc for doc in self._docs if _matches_query(doc, query)]
        return _AsyncCursor(matched)


class _AssistantFakeDB:
    def __init__(self):
        self.assistant_threads = _AsyncCollection(
            {
                "title": "贵州茅台(600519) 分析报告",
                "report_refs": [{"symbol": "600519"}],
            }
        )


class _FakeAssistantService:
    last_chat_kwargs: Dict[str, Any] | None = None
    last_prompt: str = ""

    def __init__(self, db: Any, preferred_models: Dict[str, Any] | None = None):
        self.db = db
        self.preferred_models = preferred_models or {}

    async def chat(self, user_message: str, conversation_id: str | None = None, assistant_settings: Dict[str, Any] | None = None, is_im: bool = False, history_messages: List[Any] | None = None, user_profile: Dict[str, Any] | None = None, current_topic_title: str | None = None, memory_block: str = "") -> Dict[str, Any]:
        del user_message, conversation_id, assistant_settings, is_im, history_messages
        self.__class__.last_chat_kwargs = {
            "user_profile": user_profile,
            "current_topic_title": current_topic_title,
            "memory_block": memory_block,
        }
        self.__class__.last_prompt = assistant_module._get_system_prompt(
            knowledge_snippets="",
            assistant_settings=None,
            is_im=False,
            user_profile=user_profile,
            current_topic_title=current_topic_title,
            memory_block=memory_block,
        )
        return {"reply": "assistant ok", "tools_used": []}


async def _noop_async(*args: Any, **kwargs: Any) -> None:
    del args, kwargs


async def _run_assistant_consumption_smoke() -> Dict[str, Any]:
    fake_db = _AssistantFakeDB()
    memory_block = "【历史偏好】\n- 你偏好先看基本面。\n"
    _FakeAssistantService.last_chat_kwargs = None
    _FakeAssistantService.last_prompt = ""

    with ExitStack() as stack:
        stack.enter_context(patch.object(assistant_module, "IntelligentAssistantService", _FakeAssistantService))
        stack.enter_context(patch.object(assistant_module, "_recall_memory_block", _return_async(memory_block)))
        stack.enter_context(patch.object(assistant_module, "_load_assistant_settings", _return_async(None)))
        stack.enter_context(patch.object(assistant_module, "load_user_profile", _return_async(None)))
        stack.enter_context(patch.object(assistant_module, "get_assistant_conversation", _return_async([])))
        stack.enter_context(patch.object(assistant_module, "save_assistant_message", _noop_async))
        stack.enter_context(patch.object(assistant_module, "get_or_create_assistant_thread", _return_async({"thread_id": "thread-1"})))
        stack.enter_context(patch.object(assistant_module, "_store_conversation_memory", _noop_async))

        await assistant_module.chat_with_assistant(
            fake_db,
            user_message="继续这个主题，帮我总结一下",
            user_id="user-1",
            conversation_id="thread-1",
            current_thread_id="thread-1",
        )

    captured = _FakeAssistantService.last_chat_kwargs or {}
    prompt = _FakeAssistantService.last_prompt
    return {
        "memory_block": captured.get("memory_block", ""),
        "prompt_contains_memory": memory_block in prompt,
        "prompt_contains_topic": "贵州茅台(600519) 分析报告" in prompt,
    }


class _FakeWorkflowProvider:
    def load_workflow(self, workflow_id: str | None) -> Any:
        return SimpleNamespace(id=workflow_id or "wf-default", name="Fake Workflow")


class _FakeWorkflowEngine:
    last_inputs: Dict[str, Any] | None = None

    def __init__(self, legacy_config: Dict[str, Any], task_id: str):
        self.legacy_config = legacy_config
        self.task_id = task_id

    def load(self, workflow: Any) -> None:
        self.workflow = workflow

    async def execute_async(self, inputs: Dict[str, Any], progress_callback=None) -> Dict[str, Any]:
        del progress_callback
        type(self).last_inputs = dict(inputs)
        return {"ok": True}


class _FakeGrowthService:
    async def build_recall_context(self, user_id: str, ticker: str, workflow_id: str) -> str:
        del user_id, ticker, workflow_id
        return "【成长记忆】\n- 已批准的历史复盘经验"


class _FakeMem0MemoryService:
    def __init__(self):
        self.calls: List[Dict[str, Any]] = []

    async def store(self, messages: List[Dict[str, Any]], **kwargs: Any) -> Any:
        self.calls.append({"messages": messages, **kwargs})
        return SimpleNamespace(success=True, facts_extracted=1, error=None)


async def _run_analysis_consumption_smoke() -> Dict[str, Any]:
    service = analysis_module.UnifiedAnalysisService()
    service._workflow_provider = _FakeWorkflowProvider()
    service._build_workflow_inputs = lambda **kwargs: {"memory_enabled": True, "symbol": kwargs["stock_code"]}
    service._format_result = lambda raw_result, stock_code, analysis_date, task_id, parameters=None: {
        "success": True,
        "raw_result": raw_result,
        "stock_code": stock_code,
        "analysis_date": analysis_date,
        "task_id": task_id,
    }
    service._get_db = lambda: object()
    _FakeWorkflowEngine.last_inputs = None

    with ExitStack() as stack:
        stack.enter_context(patch.object(analysis_module, "WorkflowEngine", _FakeWorkflowEngine))
        stack.enter_context(patch("app.services.workflow_growth_service.get_workflow_growth_service", return_value=_FakeGrowthService()))
        stack.enter_context(patch.object(analysis_module, "_recall_analysis_memory", _return_async("【历史分析】\n- 贵州茅台历史结论：等待估值切换")))

        await service.analyze(stock_code="600519", workflow_id="wf-memory", user_id="user-1")

    injected = (_FakeWorkflowEngine.last_inputs or {}).get("growth_memory_recall", "")
    return {
        "injected_growth_memory": "【成长记忆】" in injected,
        "injected_mem0_memory": "【历史分析】" in injected,
        "combined_block": injected,
    }


async def _run_growth_approval_consumption_smoke() -> Dict[str, Any]:
    fake_mem0 = _FakeMem0MemoryService()
    service = workflow_growth_module.WorkflowGrowthService.__new__(workflow_growth_module.WorkflowGrowthService)
    service.db = object()
    service.memory_collection = _GrowthMemoryCollection(
        [
            {
                "_id": "growth-1",
                "memory_id": "growth-1",
                "user_id": "user-1",
                "status": "pending",
                "scope": "pattern",
                "source_type": "unified_analysis_task",
                "source_id": "task-growth-1",
                "task_type": "stock_analysis",
                "workflow_id": "wf-growth",
                "object_type": "workflow",
                "object_key": "workflow-growth",
                "title": "研究流程复盘模式",
                "summary": "先收敛证据再下结论的流程更稳定。",
                "content": "复盘显示先收敛证据再输出结论，可以减少分析跳步和结论漂移。",
                "review_level": "manual_required",
                "confidence": 0.82,
                "structured_payload": {"agent_name": "research_manager"},
                "updated_at": datetime(2026, 4, 8, 9, 30, 0),
            }
        ]
    )
    service.suggestion_collection = _AsyncCollection()
    service._growth_field_profiles = {}

    with ExitStack() as stack:
        stack.enter_context(patch("core.memory.service.get_memory_service", lambda db: fake_mem0))

        approved = await service.approve_memory_item("user-1", "growth-1")
        context = await service.build_recall_context("user-1", ticker="600519", workflow_id="wf-growth")

    return {
        "approved": approved,
        "bridged_to_mem0": len(fake_mem0.calls) == 1,
        "bridge_scope": fake_mem0.calls[0]["scope"] if fake_mem0.calls else "",
        "context_contains_header": "## 历史研究记忆（已审核批准）" in context,
        "context_contains_title": "研究流程复盘模式" in context,
        "context_contains_summary": "先收敛证据再下结论的流程更稳定。" in context,
        "recall_context": context,
    }


class _FakeLoop:
    async def run_in_executor(self, executor: Any, func: Any):
        del executor
        return func()


class _FakeController:
    last_initial_feedback: str = ""

    def run(self, spec: SkillSpec, initial_feedback: str = "", initial_code: str = "", progress_callback=None, fact_report=None):
        del spec, initial_code, progress_callback, fact_report
        type(self).last_initial_feedback = initial_feedback
        return PipelineResult(success=True, tool_id="get_stock_news", final_code="def ok():\n    return 1\n", total_rounds=1)


class _FakeDB:
    def __init__(self):
        self._collections = {skill_module.SESSION_COLLECTION: _AsyncCollection()}

    def __getitem__(self, name: str) -> _AsyncCollection:
        return self._collections.setdefault(name, _AsyncCollection())


async def _run_skill_consumption_smoke() -> Dict[str, Any]:
    fake_db = _FakeDB()
    service = skill_module.SkillGenerationService(fake_db)
    service._controller = _FakeController()
    service._save_session = _noop_async
    service._save_skill = _noop_async
    service._persist_generated_code_snapshots = lambda **kwargs: []

    session = SkillCreationSession(session_id="skill-session-1", user_id="user-1")
    spec = SkillSpec(
        tool_id="get_stock_news",
        display_name="个股新闻",
        description="获取个股新闻列表",
        category="news",
        data_source="eastmoney",
    )

    scheduled: Dict[str, Any] = {}

    def _capture_task(coro):
        scheduled["coro"] = coro
        return object()

    with ExitStack() as stack:
        stack.enter_context(patch.object(skill_module.asyncio, "create_task", _capture_task))
        stack.enter_context(patch.object(skill_module.asyncio, "get_event_loop", return_value=_FakeLoop()))
        stack.enter_context(patch("app.core.database.get_mongo_db_sync", return_value=fake_db))
        stack.enter_context(patch.object(skill_module, "_recall_skill_lessons", _return_async("【历史教训】\n- 统一 news 输出字段")))
        stack.enter_context(patch.object(skill_module, "_store_skill_lessons", _noop_async))

        await service._launch_pipeline_task(
            session=session,
            spec=spec,
            initial_feedback="【用户反馈】\n- 需要统一 JSON 字段",
        )
        await scheduled["coro"]

    feedback = _FakeController.last_initial_feedback
    return {
        "feedback_contains_mem0_lessons": "【历史教训】" in feedback,
        "feedback_contains_original_feedback": "【用户反馈】" in feedback,
        "final_initial_feedback": feedback,
    }


def _return_async(value: Any):
    async def _inner(*args: Any, **kwargs: Any) -> Any:
        del args, kwargs
        return value

    return _inner


def _matches_query(doc: Dict[str, Any], query: Dict[str, Any]) -> bool:
    return all(doc.get(key) == value for key, value in query.items())


async def validate_all() -> Dict[str, Any]:
    assistant = await _run_assistant_consumption_smoke()
    analysis = await _run_analysis_consumption_smoke()
    growth = await _run_growth_approval_consumption_smoke()
    skill = await _run_skill_consumption_smoke()

    checks = {
        "assistant_prompt_injection": bool(assistant["memory_block"]) and assistant["prompt_contains_memory"],
        "analysis_input_injection": analysis["injected_growth_memory"] and analysis["injected_mem0_memory"],
        "growth_approved_memory_consumption": growth["approved"] and growth["bridged_to_mem0"] and growth["context_contains_title"],
        "skill_feedback_injection": skill["feedback_contains_mem0_lessons"] and skill["feedback_contains_original_feedback"],
    }

    return {
        "ok": all(checks.values()),
        "checks": checks,
        "assistant": assistant,
        "analysis": analysis,
        "growth": growth,
        "skill": skill,
    }


def _print_report(summary: Dict[str, Any]) -> None:
    status = "PASS" if summary["ok"] else "FAIL"
    print(f"[{status}] memory consumption loops")
    for check, ok in summary["checks"].items():
        check_status = "PASS" if ok else "FAIL"
        print(f"- [{check_status}] {check}")


def main() -> int:
    summary = asyncio.run(validate_all())
    _print_report(summary)
    print(summary)
    return 0 if summary["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())