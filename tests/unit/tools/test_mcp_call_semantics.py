"""
P5：MCP 调用失败 vs 空数据语义测试

语义约定（docs/05-design/v4.0/data-architecture-problems-and-optimization.md §6）：
- 请求失败（DNS/超时/HTTP 非 200/连接异常）→ 上抛 McpTransportError（带 error_code），
  绝不伪装成空数据；
- 请求成功但结果为空 → 正常空数据结果，不报错，业务层只在此时按"无数据"处理。
"""

import asyncio
import logging
import socket
import types

import pytest

from core.tools.mcp.client_manager import MCPClientManager, get_mcp_client_manager
from core.tools.mcp.errors import (
    McpCallError,
    McpErrorCodes,
    McpTransportError,
    classify_transport_error,
)


# ---------------------------------------------------------------------------
# 分类器：底层异常 → 结构化错误码
# ---------------------------------------------------------------------------

class _FakeResponse:
    def __init__(self, status_code: int):
        self.status_code = status_code


class _FakeHttpError(Exception):
    def __init__(self, status_code: int):
        super().__init__(f"HTTP {status_code}")
        self.response = _FakeResponse(status_code)


class _FakeMcpError(Exception):
    """模拟 mcp.shared.exceptions.McpError（按类名识别）"""


def test_classify_dns_failure():
    assert classify_transport_error(socket.gaierror("getaddrinfo failed")) == McpErrorCodes.DNS_FAILURE


def test_classify_dns_failure_wrapped_in_cause():
    # 历史事故形态：DNS 失败被包装在外层异常里
    wrapped = RuntimeError("call failed")
    wrapped.__cause__ = socket.gaierror(11001, "getaddrinfo failed")
    assert classify_transport_error(wrapped) == McpErrorCodes.DNS_FAILURE


def test_classify_dns_failure_by_message():
    exc = Exception("failed to connect: getaddrinfo failed")
    assert classify_transport_error(exc) == McpErrorCodes.DNS_FAILURE


def test_classify_timeout():
    assert classify_transport_error(TimeoutError("deadline")) == McpErrorCodes.TIMEOUT
    assert classify_transport_error(asyncio.TimeoutError()) == McpErrorCodes.TIMEOUT


def test_classify_http_error():
    assert classify_transport_error(_FakeHttpError(500)) == McpErrorCodes.HTTP_ERROR
    assert classify_transport_error(_FakeHttpError(502)) == McpErrorCodes.HTTP_ERROR


def test_classify_connection_error():
    assert (
        classify_transport_error(ConnectionRefusedError(111, "refused"))
        == McpErrorCodes.CONNECTION_ERROR
    )


def test_classify_protocol_error():
    assert classify_transport_error(_FakeMcpError("jsonrpc error")) == McpErrorCodes.PROTOCOL_ERROR


# ---------------------------------------------------------------------------
# MCPClientManager 调用边界：失败上抛可识别错误，空数据不算失败
# ---------------------------------------------------------------------------

@pytest.fixture()
def manager(monkeypatch):
    mgr = get_mcp_client_manager()
    assert isinstance(mgr, MCPClientManager)
    return mgr


def _patch_with_session(monkeypatch, mgr, side_effect=None, return_value=None):
    """替换传输层 _with_session：side_effect=异常 → 模拟请求失败"""

    async def fake_with_session(config, action):
        if side_effect is not None:
            raise side_effect
        return return_value

    monkeypatch.setattr(mgr, "_with_session", fake_with_session)


_CONFIG = {"transport_type": "sse", "connection": {"url": "http://tdx-mcp.local/sse"}}


def test_call_tool_ex_dns_failure_raises_transport_error(manager, monkeypatch):
    _patch_with_session(monkeypatch, manager, side_effect=socket.gaierror("getaddrinfo failed"))
    with pytest.raises(McpTransportError) as excinfo:
        manager.call_tool_ex(_CONFIG, "get_stock_info", {"code": "000001"})
    err = excinfo.value
    assert err.error_code == McpErrorCodes.DNS_FAILURE
    # 失败必须打标可识别（错误信息含错误码标记）
    assert McpErrorCodes.DNS_FAILURE in str(err)
    assert "[MCP]" in str(err)


def test_call_tool_ex_timeout_raises_transport_error(manager, monkeypatch):
    # 模拟 future.result(timeout) 超时（concurrent.futures.TimeoutError）
    def fake_run_sync(coro, timeout=30):
        coro.close()
        raise TimeoutError("timed out")

    monkeypatch.setattr(manager, "_run_sync", fake_run_sync)
    with pytest.raises(McpTransportError) as excinfo:
        manager.call_tool_ex(_CONFIG, "get_stock_info", {})
    assert excinfo.value.error_code == McpErrorCodes.TIMEOUT


def test_call_tool_ex_http_500_raises_transport_error(manager, monkeypatch):
    _patch_with_session(monkeypatch, manager, side_effect=_FakeHttpError(500))
    with pytest.raises(McpTransportError) as excinfo:
        manager.call_tool_ex(_CONFIG, "get_stock_info", {})
    assert excinfo.value.error_code == McpErrorCodes.HTTP_ERROR


def test_call_tool_ex_failure_logs_error_tag(manager, monkeypatch, caplog):
    _patch_with_session(monkeypatch, manager, side_effect=ConnectionRefusedError("refused"))
    with caplog.at_level(logging.ERROR, logger="core.tools.mcp.client_manager"):
        with pytest.raises(McpTransportError):
            manager.call_tool_ex(_CONFIG, "get_stock_info", {})
    assert "[MCP][TRANSPORT_ERROR]" in caplog.text


def test_call_tool_ex_success_but_empty_is_not_error(manager, monkeypatch):
    """请求成功但结果为空：不抛异常，明确返回空数据语义"""
    _patch_with_session(monkeypatch, manager, return_value="")
    # 显式 status=empty，error_code 为 None
    outcome = manager.call_tool_ex(_CONFIG, "get_stock_info", {})
    assert outcome["status"] == "empty"
    assert outcome["error_code"] is None
    assert outcome["data"] == ""
    assert outcome["data_source"].startswith("mcp:")


def test_call_tool_ex_success_with_data(manager, monkeypatch):
    _patch_with_session(monkeypatch, manager, return_value='{"name": "平安银行"}')
    outcome = manager.call_tool_ex(_CONFIG, "get_stock_info", {})
    assert outcome["status"] == "ok"
    assert outcome["error_code"] is None
    assert "平安银行" in outcome["data"]


def test_call_tool_ex_tool_error_is_identifiable(manager, monkeypatch):
    """工具返回 isError=True 是失败（非空数据），必须可识别"""

    class _FakeResult:
        def __init__(self):
            self.content = [types.SimpleNamespace(text="内部错误")]
            self.isError = True

    class _FakeSession:
        async def call_tool(self, name, arguments=None):
            return _FakeResult()

    async def fake_with_session(config, action):
        return await action(_FakeSession())

    monkeypatch.setattr(manager, "_with_session", fake_with_session)
    with pytest.raises(McpCallError) as excinfo:
        manager.call_tool_ex(_CONFIG, "get_stock_info", {})
    assert excinfo.value.error_code == McpErrorCodes.TOOL_ERROR


def test_call_tool_ex_does_not_reclassify_mcp_call_error(manager, monkeypatch):
    """已带错误码的 McpCallError 原样透传，不被二次包装"""
    origin = McpCallError(McpErrorCodes.TOOL_ERROR, "boom", server="s", tool="t")
    _patch_with_session(monkeypatch, manager, side_effect=origin)
    with pytest.raises(McpCallError) as excinfo:
        manager.call_tool_ex(_CONFIG, "t", {})
    assert excinfo.value is origin


def test_test_connection_reports_error_code(manager, monkeypatch):
    _patch_with_session(monkeypatch, manager, side_effect=socket.gaierror("getaddrinfo failed"))
    result = manager.test_connection(_CONFIG)
    assert result["success"] is False
    assert result["error_code"] == McpErrorCodes.DNS_FAILURE


# ---------------------------------------------------------------------------
# 业务调用点：失败不得被当空数据静默吞掉
# ---------------------------------------------------------------------------

class _StubManager:
    def __init__(self, outcome=None, error=None):
        self._outcome = outcome
        self._error = error

    def call_tool_ex(self, config, tool_name, arguments, timeout=60):
        if self._error is not None:
            raise self._error
        return self._outcome


def _make_mcp_impl():
    from core.skills.models import McpImplementation

    return McpImplementation(
        server_url="http://tdx-mcp.local/sse",
        tool_name="get_stock_info",
        transport="sse",
    )


def test_skill_executor_preserves_transport_error(monkeypatch):
    """Skill 执行器不得把请求失败包装吞成普通错误/空数据"""
    import core.tools.mcp.client_manager as cm
    from core.skills.executor import SkillExecutor

    err = McpTransportError(McpErrorCodes.DNS_FAILURE, "dns", server="s", tool="t")
    monkeypatch.setattr(cm, "get_mcp_client_manager", lambda: _StubManager(error=err))

    with pytest.raises(McpTransportError) as excinfo:
        asyncio.run(SkillExecutor._execute_mcp(_make_mcp_impl(), code="000001"))
    assert excinfo.value is err
    assert excinfo.value.error_code == McpErrorCodes.DNS_FAILURE


def test_skill_executor_empty_data_is_explicit(monkeypatch):
    """成功但无数据 → 显式空数据结果（不报错、不与失败混淆）"""
    import core.tools.mcp.client_manager as cm
    from core.skills.executor import SkillExecutor

    monkeypatch.setattr(
        cm,
        "get_mcp_client_manager",
        lambda: _StubManager(
            outcome={
                "status": "empty",
                "data": "",
                "error_code": None,
                "data_source": "mcp:tdx-mcp",
            }
        ),
    )
    result = asyncio.run(SkillExecutor._execute_mcp(_make_mcp_impl(), code="000001"))
    assert isinstance(result, dict)
    assert result["status"] == "empty"
    assert result["error_code"] is None
    assert result["data_source"].startswith("mcp:")


def test_skill_executor_success_returns_data(monkeypatch):
    import core.tools.mcp.client_manager as cm
    from core.skills.executor import SkillExecutor

    monkeypatch.setattr(
        cm,
        "get_mcp_client_manager",
        lambda: _StubManager(
            outcome={
                "status": "ok",
                "data": '{"name": "平安银行"}',
                "error_code": None,
                "data_source": "mcp:tdx-mcp",
            }
        ),
    )
    result = asyncio.run(SkillExecutor._execute_mcp(_make_mcp_impl(), code="000001"))
    assert result == {"name": "平安银行"}


# ---------------------------------------------------------------------------
# 数据源适配器：空响应与解析失败不得混为一谈
# ---------------------------------------------------------------------------

def test_datasource_adapter_empty_response_logged_as_empty(caplog):
    from core.tools.mcp.datasource_adapter import MCPDatasourceAdapter

    adapter = MCPDatasourceAdapter()
    mapping = {"target_collection": "stock_basic_info"}
    with caplog.at_level(logging.INFO, logger="core.tools.mcp.datasource_adapter"):
        result = adapter.adapt_and_persist("", "get_stock_info", mapping, "tdx-mcp")
    assert result == "stock_basic_info"
    assert "无数据" in caplog.text
    assert "PARSE_ERROR" not in caplog.text


def test_datasource_adapter_parse_failure_not_treated_as_empty(caplog):
    from core.tools.mcp.datasource_adapter import MCPDatasourceAdapter

    adapter = MCPDatasourceAdapter()
    mapping = {"target_collection": "stock_basic_info"}
    with caplog.at_level(logging.WARNING, logger="core.tools.mcp.datasource_adapter"):
        result = adapter.adapt_and_persist("<<<not-json>>>", "get_stock_info", mapping, "tdx-mcp")
    assert result == "stock_basic_info"
    assert "PARSE_ERROR" in caplog.text
