"""
设置与配置 API 验收测试

覆盖:
- GET  /api/config/system          系统配置
- GET  /api/config/llm             LLM配置
- GET  /api/config/datasource      数据源配置
- GET  /api/config/qmt-diagnosis   QMT诊断
- GET  /api/config/datasource-quality 数据源质量
- GET  /api/tags/                  标签列表
- GET  /api/cache                  缓存管理
- GET  /api/mcp/audit-logs         MCP审计日志
- GET  /api/mcp/servers            MCP服务器列表
"""
import pytest


class TestConfig:
    """配置管理测试。"""

    def test_get_system_config(self, api_client):
        """获取系统配置。"""
        resp = api_client.get("/api/config/system")
        assert resp.status_code == 200, f"获取系统配置失败: {resp.text}"

    def test_get_llm_config(self, api_client):
        """获取 LLM 配置。"""
        resp = api_client.get("/api/config/llm")
        assert resp.status_code == 200, f"获取LLM配置失败: {resp.text}"

    def test_get_datasource_config(self, api_client):
        """获取数据源配置。"""
        resp = api_client.get("/api/config/datasource")
        assert resp.status_code == 200, f"获取数据源配置失败: {resp.text}"

    def test_get_qmt_diagnosis(self, api_client):
        """QMT 连接诊断。"""
        resp = api_client.get("/api/config/qmt-diagnosis")
        assert resp.status_code == 200, f"QMT诊断失败: {resp.text}"
        data = resp.json()
        # 诊断结果应包含检查步骤
        assert isinstance(data, dict), f"诊断结果格式异常: {data}"

    def test_get_datasource_quality(self, api_client):
        """数据源质量统计。"""
        resp = api_client.get("/api/config/datasource-quality")
        assert resp.status_code == 200, f"获取数据源质量失败: {resp.text}"


class TestTags:
    """标签管理测试。"""

    def test_get_tags(self, api_client):
        """获取标签列表。"""
        resp = api_client.get("/api/tags/")
        assert resp.status_code == 200, f"获取标签列表失败: {resp.text}"


class TestCache:
    """缓存管理测试。"""

    def test_get_cache_info(self, api_client):
        """获取缓存信息。"""
        resp = api_client.get("/api/cache")
        assert resp.status_code in (200, 404), f"获取缓存信息异常: {resp.status_code}"


class TestMCPAuditLogs:
    """MCP 审计日志测试。"""

    def test_get_audit_logs(self, api_client):
        """查询 MCP 审计日志。"""
        resp = api_client.get("/api/mcp/audit-logs")
        assert resp.status_code == 200, f"获取MCP审计日志失败: {resp.status_code} {resp.text}"
        data = resp.json()
        assert "logs" in data or "data" in data or isinstance(data, list), \
            f"审计日志响应结构异常: {data}"

    def test_get_audit_logs_with_filters(self, api_client):
        """带过滤条件查询审计日志。"""
        resp = api_client.get("/api/mcp/audit-logs", params={
            "limit": 10,
            "offset": 0,
        })
        assert resp.status_code == 200, f"过滤查询审计日志失败: {resp.status_code}"

    def test_get_mcp_servers(self, api_client):
        """获取 MCP 服务器列表。"""
        resp = api_client.get("/api/mcp/servers")
        assert resp.status_code == 200, f"获取MCP服务器列表失败: {resp.status_code} {resp.text}"
