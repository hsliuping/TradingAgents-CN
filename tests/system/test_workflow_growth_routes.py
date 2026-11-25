from app.main import app


def test_workflow_growth_task_route_registered() -> None:
    target_path = "/api/workflow-growth/tasks/{task_id}"
    paths = {getattr(route, "path", "") for route in app.routes}
    assert target_path in paths
