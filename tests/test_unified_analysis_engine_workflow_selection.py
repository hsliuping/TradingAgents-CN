from types import SimpleNamespace

from app.models.analysis import AnalysisTaskType, UnifiedAnalysisTask
from app.services.unified_analysis_engine import UnifiedAnalysisEngine


def _make_task(task_type=AnalysisTaskType.STOCK_ANALYSIS, task_params=None, workflow_id=None):
    return UnifiedAnalysisTask(
        task_id="task-1",
        user_id="6915d05ac52e760d74ed36a2",
        task_type=task_type,
        task_params=task_params or {},
        workflow_id=workflow_id,
    )


def test_resolve_workflow_id_prefers_explicit_task_workflow_id():
    engine = UnifiedAnalysisEngine()
    task = _make_task(workflow_id="custom-workflow")
    config = SimpleNamespace(workflow_id="v2_stock_analysis")

    workflow_id = engine._resolve_workflow_id(task, config)

    assert workflow_id == "custom-workflow"


def test_resolve_workflow_id_prefers_task_params_workflow_id():
    engine = UnifiedAnalysisEngine()
    task = _make_task(task_params={"workflow_id": "task-param-workflow"})
    config = SimpleNamespace(workflow_id="v2_stock_analysis")

    workflow_id = engine._resolve_workflow_id(task, config)

    assert workflow_id == "task-param-workflow"


def test_resolve_workflow_id_uses_active_stock_workflow(monkeypatch):
    engine = UnifiedAnalysisEngine()
    task = _make_task()
    config = SimpleNamespace(workflow_id="v2_stock_analysis")

    provider = SimpleNamespace(
        get_active_workflow_id=lambda: "540f497b-efcb-46e1-9f01-707c69396c93",
        load_workflow=lambda workflow_id: SimpleNamespace(id=workflow_id),
    )
    monkeypatch.setattr(
        "app.services.unified_analysis_engine.get_default_workflow_provider",
        lambda: provider,
    )

    workflow_id = engine._resolve_workflow_id(task, config)

    assert workflow_id == "540f497b-efcb-46e1-9f01-707c69396c93"


def test_resolve_workflow_id_falls_back_when_active_stock_workflow_is_missing(monkeypatch):
    engine = UnifiedAnalysisEngine()
    task = _make_task()
    config = SimpleNamespace(workflow_id="v2_stock_analysis")

    def _raise_missing(_workflow_id):
        raise ValueError("工作流不存在")

    provider = SimpleNamespace(
        get_active_workflow_id=lambda: "legacy-custom-uuid",
        load_workflow=_raise_missing,
    )
    monkeypatch.setattr(
        "app.services.unified_analysis_engine.get_default_workflow_provider",
        lambda: provider,
    )

    workflow_id = engine._resolve_workflow_id(task, config)

    assert workflow_id == "v2_stock_analysis"


def test_resolve_workflow_id_falls_back_to_registry_default_for_non_stock_tasks():
    engine = UnifiedAnalysisEngine()
    task = _make_task(task_type=AnalysisTaskType.TRADE_REVIEW)
    config = SimpleNamespace(workflow_id="trade_review")

    workflow_id = engine._resolve_workflow_id(task, config)

    assert workflow_id == "trade_review"