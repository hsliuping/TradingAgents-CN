"""
Agent 工坊与工作流 API 验收测试

覆盖:
- GET  /api/agents                 Agent列表
- GET  /api/tools                  工具列表
- GET  /api/workflows              工作流列表
- GET  /api/agent-workshop/specs   Agent工坊规格列表
- POST /api/agent-workshop/specs/{id}/rollback Agent版本回滚
"""
import pytest


class TestAgents:
    """Agent 测试。"""

    def test_get_agents(self, api_client):
        """获取 Agent 列表。"""
        resp = api_client.get("/api/agents")
        assert resp.status_code == 200, f"获取Agent列表失败: {resp.text}"

    def test_get_available_agents(self, api_client):
        """获取可用 Agent 列表。"""
        resp = api_client.get("/api/agents/available")
        assert resp.status_code == 200, f"获取可用Agent列表失败: {resp.text}"

    def test_get_agent_categories(self, api_client):
        """获取 Agent 分类。"""
        resp = api_client.get("/api/agents/categories")
        assert resp.status_code == 200, f"获取Agent分类失败: {resp.text}"


class TestTools:
    """工具测试。"""

    def test_get_tools(self, api_client):
        """获取工具列表。"""
        resp = api_client.get("/api/tools")
        assert resp.status_code == 200, f"获取工具列表失败: {resp.text}"

    def test_get_tool_categories(self, api_client):
        """获取工具分类。"""
        resp = api_client.get("/api/tools/categories")
        assert resp.status_code == 200, f"获取工具分类失败: {resp.text}"


class TestWorkflows:
    """工作流测试。"""

    def test_get_workflows(self, api_client):
        """获取工作流列表。"""
        resp = api_client.get("/api/workflows")
        assert resp.status_code == 200, f"获取工作流列表失败: {resp.text}"

    def test_get_workflow_templates(self, api_client):
        """获取工作流模板。"""
        resp = api_client.get("/api/workflows/templates")
        assert resp.status_code == 200, f"获取工作流模板失败: {resp.text}"


class TestAgentWorkshop:
    """Agent 工坊测试。"""

    def test_get_specs(self, api_client):
        """获取 Agent 工坊规格列表。"""
        resp = api_client.get("/api/agent-workshop/specs")
        assert resp.status_code in (200, 404), f"获取Agent规格列表异常: {resp.status_code} {resp.text}"

    def test_rollback_spec(self, api_client):
        """版本回滚接口可用性测试（使用不存在的ID）。"""
        resp = api_client.post("/api/agent-workshop/specs/nonexistent_spec_id/rollback")
        assert resp.status_code in (200, 404, 400), f"版本回滚接口异常: {resp.status_code} {resp.text}"
