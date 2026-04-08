import pytest

from app.models.agent_growth import GrowthMemoryStatus, GrowthMemoryScope, GrowthReviewLevel
from app.models.analysis import AnalysisTaskType
from app.services.workflow_growth_service import WorkflowGrowthService
from core.memory.models import StoreResult


class _FakeUpdateResult:
    def __init__(self, modified_count: int):
        self.modified_count = modified_count


class _FakeMemoryCollection:
    def __init__(self, docs):
        self._docs = [dict(doc) for doc in docs]

    async def update_one(self, query, update):
        for doc in self._docs:
            if all(doc.get(key) == value for key, value in query.items()):
                for key, value in update.get("$set", {}).items():
                    doc[key] = value
                return _FakeUpdateResult(1)
        return _FakeUpdateResult(0)

    async def find_one(self, query):
        for doc in self._docs:
            if all(doc.get(key) == value for key, value in query.items()):
                return dict(doc)
        return None

    def find(self, query):
        matched = [dict(doc) for doc in self._docs if all(doc.get(key) == value for key, value in query.items())]
        return _FakeAsyncCursor(matched)


class _FakeAsyncCursor:
    def __init__(self, docs):
        self._docs = [dict(doc) for doc in docs]

    def sort(self, field, direction):
        reverse = direction < 0
        self._docs.sort(key=lambda doc: doc.get(field), reverse=reverse)
        return self

    def limit(self, size):
        self._docs = self._docs[:size]
        return self

    async def to_list(self, length):
        return [dict(doc) for doc in self._docs[:length]]


class _FakeMemoryService:
    def __init__(self, result: StoreResult):
        self.result = result
        self.calls = []

    async def store(self, messages, **kwargs):
        self.calls.append({"messages": messages, **kwargs})
        return self.result


def _build_service(memory_docs):
    service = WorkflowGrowthService.__new__(WorkflowGrowthService)
    service.db = object()
    service.memory_collection = _FakeMemoryCollection(memory_docs)
    service.suggestion_collection = None
    service._growth_field_profiles = {}
    return service


@pytest.mark.asyncio
async def test_approve_memory_item_bridges_approved_growth_memory_to_mem0(monkeypatch):
    memory_doc = {
        "memory_id": "mem-growth-001",
        "user_id": "user-1",
        "scope": GrowthMemoryScope.RESEARCH_ASSET.value,
        "status": GrowthMemoryStatus.PENDING.value,
        "review_level": GrowthReviewLevel.MANUAL_REQUIRED.value,
        "source_type": "unified_analysis_task",
        "source_id": "task-001",
        "task_type": str(AnalysisTaskType.STOCK_ANALYSIS),
        "workflow_id": "wf-001",
        "object_type": "stock",
        "object_key": "600519",
        "title": "贵州茅台 研究摘要候选",
        "summary": "高端白酒需求和渠道稳定性仍然较强。",
        "content": "贵州茅台在高端白酒需求和渠道稳定性方面维持优势。",
        "structured_payload": {"agent_name": "research_manager"},
        "confidence": 0.82,
        "evidence_refs": [{"type": "unified_analysis_task", "id": "task-001"}],
    }
    service = _build_service([memory_doc])
    fake_memory_service = _FakeMemoryService(StoreResult(memory_ids=["m1"], facts_extracted=1))

    monkeypatch.setattr("core.memory.service.get_memory_service", lambda db: fake_memory_service)

    ok = await service.approve_memory_item("user-1", "mem-growth-001")

    assert ok is True
    assert len(fake_memory_service.calls) == 1
    call = fake_memory_service.calls[0]
    assert call["user_id"] == "user-1"
    assert call["agent_id"] == "research_manager"
    assert call["session_id"] == "task-001"
    assert call["scope"] == "analysis_insight"
    assert call["metadata"]["symbol"] == "600519"
    assert call["metadata"]["growth_memory_id"] == "mem-growth-001"
    assert call["metadata"]["growth_scope"] == GrowthMemoryScope.RESEARCH_ASSET.value
    assert "贵州茅台 研究摘要候选" in call["messages"][0]["content"]


@pytest.mark.asyncio
async def test_approve_memory_item_keeps_success_when_mem0_bridge_fails(monkeypatch):
    memory_doc = {
        "memory_id": "mem-growth-002",
        "user_id": "user-2",
        "scope": GrowthMemoryScope.PATTERN.value,
        "status": GrowthMemoryStatus.PENDING.value,
        "review_level": GrowthReviewLevel.MANUAL_REQUIRED.value,
        "source_type": "unified_analysis_task",
        "source_id": "task-002",
        "task_type": str(AnalysisTaskType.TRADE_REVIEW),
        "workflow_id": "wf-002",
        "object_type": "trade_review",
        "object_key": "review-002",
        "title": "本次交易 复盘偏差模式",
        "summary": "存在追涨和纪律执行不一致问题。",
        "content": "复盘显示存在追涨和纪律执行不一致问题，应补充风控约束。",
        "structured_payload": {},
        "confidence": 0.8,
        "evidence_refs": [],
    }
    service = _build_service([memory_doc])
    fake_memory_service = _FakeMemoryService(StoreResult(success=False, error="mem0 unavailable"))

    monkeypatch.setattr("core.memory.service.get_memory_service", lambda db: fake_memory_service)

    ok = await service.approve_memory_item("user-2", "mem-growth-002")

    assert ok is True
    assert len(fake_memory_service.calls) == 1
    call = fake_memory_service.calls[0]
    assert call["scope"] == "trade_pattern"
    approved_doc = await service.memory_collection.find_one({"user_id": "user-2", "memory_id": "mem-growth-002"})
    assert approved_doc is not None
    assert approved_doc["status"] == GrowthMemoryStatus.APPROVED.value
    assert approved_doc["confirmed_by"] == "user-2"


@pytest.mark.asyncio
async def test_build_recall_context_uses_pattern_scope_and_workflow_id():
    pattern_doc = {
        "_id": "doc-pattern-1",
        "memory_id": "mem-growth-003",
        "user_id": "user-3",
        "scope": GrowthMemoryScope.PATTERN.value,
        "status": GrowthMemoryStatus.APPROVED.value,
        "workflow_id": "wf-pattern-1",
        "title": "研究流程复盘模式",
        "summary": "先收敛证据再下结论的流程更稳定。",
        "content": "复盘显示先收敛证据再输出结论，可以减少分析跳步和结论漂移。",
        "updated_at": 3,
    }
    research_doc = {
        "_id": "doc-research-1",
        "memory_id": "mem-growth-004",
        "user_id": "user-3",
        "scope": GrowthMemoryScope.RESEARCH_ASSET.value,
        "status": GrowthMemoryStatus.APPROVED.value,
        "title": "贵州茅台 研究摘要候选",
        "summary": "高端白酒需求和渠道稳定性维持优势。",
        "content": "贵州茅台在高端白酒需求和渠道稳定性方面维持优势。",
        "updated_at": 2,
    }
    service = _build_service([pattern_doc, research_doc])

    context = await service.build_recall_context(user_id="user-3", ticker="600519", workflow_id="wf-pattern-1")

    assert "研究流程复盘模式" in context
    assert "贵州茅台 研究摘要候选" in context
    assert context.index("研究流程复盘模式") < context.index("贵州茅台 研究摘要候选")