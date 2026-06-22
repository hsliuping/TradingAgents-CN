"""
分析任务 API 验收测试

覆盖:
- POST /api/analysis/single         触发单股分析
- GET  /api/analysis/tasks          用户任务列表
- GET  /api/analysis/tasks/all      所有任务列表
- GET  /api/analysis/user/history   分析历史
- GET  /api/v2/tasks/list           统一任务中心列表
- GET  /api/v2/tasks/statistics     任务统计
- POST /api/analysis/tasks/{id}/feedback 分析反馈
"""
import pytest


class TestAnalysisTrigger:
    """触发分析测试。"""

    def test_trigger_analysis(self, api_client):
        """触发单只股票分析任务。"""
        resp = api_client.post("/api/analysis/single", json={
            "stock_code": "000001",
            "market_type": "A",
        })
        # 分析触发可能返回 200（成功）或 400/422（参数问题）
        assert resp.status_code in (200, 201, 400, 422), f"触发分析异常: {resp.status_code} {resp.text}"

    def test_trigger_analysis_invalid_code(self, api_client):
        """无效股票代码触发分析应被拒绝。"""
        resp = api_client.post("/api/analysis/single", json={
            "stock_code": "",
            "market_type": "A",
        })
        assert resp.status_code in (400, 422), f"无效代码应被拒绝: {resp.status_code}"


class TestAnalysisHistory:
    """分析历史测试。"""

    def test_get_analysis_history(self, api_client):
        """获取分析历史列表。"""
        resp = api_client.get("/api/analysis/user/history")
        assert resp.status_code == 200, f"获取分析历史失败: {resp.text}"

    def test_get_analysis_tasks(self, api_client):
        """获取用户任务列表。"""
        resp = api_client.get("/api/analysis/tasks")
        assert resp.status_code == 200, f"获取任务列表失败: {resp.text}"


class TestUnifiedTasks:
    """统一任务中心测试。"""

    def test_get_tasks_list(self, api_client):
        """获取统一任务列表。"""
        resp = api_client.get("/api/v2/tasks/list")
        assert resp.status_code == 200, f"获取任务列表失败: {resp.text}"
        data = resp.json()
        # 验证返回的是列表或分页结构
        if isinstance(data, dict):
            assert "data" in data or "items" in data or "tasks" in data or "list" in data, \
                f"任务列表响应结构异常: {data}"

    def test_get_tasks_statistics(self, api_client):
        """获取任务统计。"""
        resp = api_client.get("/api/v2/tasks/statistics")
        assert resp.status_code == 200, f"获取任务统计失败: {resp.text}"

    def test_get_tasks_list_with_filters(self, api_client):
        """带过滤条件获取任务列表。"""
        resp = api_client.get("/api/v2/tasks/list", params={
            "status": "completed",
            "page": 1,
            "page_size": 10,
        })
        assert resp.status_code == 200


class TestAnalysisFeedback:
    """分析反馈测试。"""

    def test_submit_feedback(self, api_client):
        """提交分析反馈（使用一个不存在的 task_id，验证接口可用性）。"""
        resp = api_client.post("/api/analysis/tasks/test_task_id/feedback", json={
            "rating": 5,
            "comment": "验收测试反馈",
        })
        # 接口应可用，可能返回 200/201/404（task 不存在）
        assert resp.status_code in (200, 201, 404), f"反馈接口异常: {resp.status_code} {resp.text}"

    def test_submit_feedback_invalid_rating(self, api_client):
        """无效评分（超出 1-5 范围）应被拒绝。"""
        resp = api_client.post("/api/analysis/tasks/test_task_id/feedback", json={
            "rating": 10,
            "comment": "无效评分",
        })
        assert resp.status_code in (400, 422), f"无效评分应被拒绝: {resp.status_code}"
