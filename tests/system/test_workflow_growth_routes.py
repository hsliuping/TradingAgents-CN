from app.main import app


def test_workflow_growth_task_route_registered() -> None:
    target_path = "/api/workflow-growth/tasks/{task_id}"
    # 新版 FastAPI（>=0.13x）include_router 为懒挂载：app.routes 中是 _IncludedRouter，
    # 枚举不到展开后的路径，须经 app.openapi()["paths"] 断言路由注册
    paths = set(app.openapi()["paths"].keys())
    assert target_path in paths
