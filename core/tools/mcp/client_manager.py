"""
MCP 客户端管理器

在后台线程中运行独立的 asyncio 事件循环，
提供同步接口供工具注册表和 Agent 调用。
支持 SSE、Streamable HTTP、stdio 三种传输方式。

通达信双通道职责划分（P5，见 docs/05-design/v4.0/data-architecture-problems-and-optimization.md §6）：
  - tqcenter HTTP（127.0.0.1:17709）= 行情实时数据通道（低延迟，ADR-001）
  - tdx-mcp MCP 工具（本模块承载）= 股票信息 / 基本面查询通道
  - QMT = xtquant SDK 直连，保持现状不 MCP 化

失败/空数据语义（🔴 强制）：
  - 请求失败（DNS/超时/HTTP 非 200/连接异常）→ 打日志标 + 上抛
    McpTransportError（带 error_code），绝不伪装成空数据
  - 请求成功但结果为空 → 正常返回空结果，业务层只在此时按"无数据"处理
"""

import asyncio
import json
import logging
import threading
from typing import Any, Dict, List, Optional

from .errors import (
    McpCallError,
    McpErrorCodes,
    McpTransportError,
    call_error_from_exception,
    to_transport_error,
)

logger = logging.getLogger(__name__)


def _data_source_label(config: Dict) -> str:
    """从连接配置推导数据源标签（用于 data_source 字段与日志打标）"""
    conn = config.get("connection", {}) or {}
    for key in ("name", "server_id"):
        if config.get(key):
            return str(config[key])
    url = conn.get("url")
    if url:
        return str(url)
    command = conn.get("command")
    if command:
        return str(command)
    return str(config.get("transport_type", "unknown"))


class MCPClientManager:
    """
    MCP 客户端管理器（单例）

    维护一个后台 asyncio 循环，所有 MCP 异步操作在此循环中执行，
    并通过 _run_sync() 暴露为同步接口。
    """

    _instance: Optional["MCPClientManager"] = None
    _lock = threading.Lock()

    def __new__(cls) -> "MCPClientManager":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(
            target=self._loop.run_forever,
            name="mcp-event-loop",
            daemon=True,
        )
        self._thread.start()
        self._initialized = True
        logger.info("✅ MCPClientManager 初始化完成（后台事件循环已启动）")

    # ------------------------------------------------------------------
    # 内部：同步执行异步协程
    # ------------------------------------------------------------------

    def _run_sync(self, coro, timeout: int = 30) -> Any:
        """在后台事件循环中同步执行协程"""
        future = asyncio.run_coroutine_threadsafe(coro, self._loop)
        return future.result(timeout=timeout)

    # ------------------------------------------------------------------
    # 内部：按传输类型建立连接并执行操作
    # ------------------------------------------------------------------

    async def _with_session(self, config: Dict, action):
        """
        根据 config 建立 MCP 会话，执行 action(session)，返回结果。
        action: async callable(session) -> Any
        """
        transport_type = config.get("transport_type", "sse")
        conn = config.get("connection", {})

        from mcp import ClientSession

        if transport_type in ("sse",):
            from mcp.client.sse import sse_client
            url = conn.get("url", "")
            headers = conn.get("headers", {})
            async with sse_client(url=url, headers=headers) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    return await action(session)

        elif transport_type == "streamable_http":
            from mcp.client.streamable_http import streamablehttp_client
            url = conn.get("url", "")
            headers = conn.get("headers", {})
            async with streamablehttp_client(url=url, headers=headers) as (read, write, _):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    return await action(session)

        elif transport_type == "stdio":
            from mcp.client.stdio import stdio_client
            from mcp import StdioServerParameters
            params = StdioServerParameters(
                command=conn.get("command", ""),
                args=conn.get("args", []),
                env=conn.get("env") or None,
            )
            async with stdio_client(params) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    return await action(session)

        else:
            raise ValueError(f"不支持的 MCP 传输类型: {transport_type}")

    # ------------------------------------------------------------------
    # 公开 API：工具发现
    # ------------------------------------------------------------------

    def discover_tools(self, config: Dict, timeout: int = 30) -> List[Dict]:
        """
        连接 MCP 服务器并返回可用工具列表。

        Returns:
            List of tool dicts with keys: name, description, inputSchema
        """
        async def _action(session):
            result = await session.list_tools()
            tools_out = []
            for t in result.tools:
                if t.inputSchema is None:
                    schema = {}
                elif isinstance(t.inputSchema, dict):
                    schema = t.inputSchema
                elif hasattr(t.inputSchema, "model_dump"):
                    schema = t.inputSchema.model_dump()
                else:
                    schema = dict(t.inputSchema) if t.inputSchema else {}
                tools_out.append({
                    "name": t.name,
                    "description": t.description or "",
                    "input_schema": schema,
                })
            return tools_out

        try:
            return self._run_sync(self._with_session(config, _action), timeout=timeout)
        except ValueError:
            raise
        except Exception as e:
            err = to_transport_error(
                e, server=_data_source_label(config), tool="discover_tools"
            )
            logger.error(
                f"[MCP][TRANSPORT_ERROR][{err.error_code}] 工具发现失败: "
                f"server={_data_source_label(config)} cause={type(e).__name__}: {e}",
                exc_info=True,
            )
            raise err from e

    # ------------------------------------------------------------------
    # 公开 API：工具调用
    # ------------------------------------------------------------------

    def call_tool_ex(
        self,
        config: Dict,
        tool_name: str,
        arguments: Dict,
        timeout: int = 60,
    ) -> Dict[str, Any]:
        """
        调用 MCP 工具并显式区分"失败"与"成功但无数据"。

        Returns:
            {
              "status": "ok" | "empty",   # ok=有数据；empty=请求成功但无数据
              "data": str,                # 工具原始返回（empty 时为空串）
              "error_code": None,         # 失败时不返回结果而是抛异常
              "data_source": "mcp:<server>",
            }

        Raises:
            McpTransportError / McpCallError: 请求失败，携带 error_code。
        """
        server_label = _data_source_label(config)

        async def _action(session):
            result = await session.call_tool(tool_name, arguments=arguments)
            # 将 content list 拼成字符串
            parts = []
            for c in result.content:
                if hasattr(c, "text"):
                    parts.append(c.text)
                else:
                    parts.append(json.dumps(c.model_dump(), ensure_ascii=False))
            text = "\n".join(parts)
            # MCP 协议约定 isError=True 表示工具执行失败（非"无数据"）
            if getattr(result, "isError", False):
                raise McpCallError(
                    McpErrorCodes.TOOL_ERROR,
                    f"工具返回 isError=True: {text[:200]}",
                    server=server_label,
                    tool=tool_name,
                )
            return text

        try:
            raw = self._run_sync(self._with_session(config, _action), timeout=timeout)
        except McpCallError:
            # 已带错误码（含 tool_error），只打日志标后原样上抛
            logger.error(
                f"[MCP][CALL_ERROR] 调用失败（非空数据）: server={server_label} "
                f"tool={tool_name}",
                exc_info=True,
            )
            raise
        except ValueError:
            # 配置错误（如不支持的传输类型），不属于传输失败
            raise
        except Exception as e:
            err = to_transport_error(e, server=server_label, tool=tool_name)
            logger.error(
                f"[MCP][TRANSPORT_ERROR][{err.error_code}] 请求失败（非空数据）: "
                f"server={server_label} tool={tool_name} cause={type(e).__name__}: {e}",
                exc_info=True,
            )
            raise err from e

        data = raw or ""
        status = "empty" if not data.strip() else "ok"
        if status == "empty":
            logger.info(
                f"[MCP][EMPTY_DATA] 请求成功但无数据: server={server_label} tool={tool_name}"
            )
        return {
            "status": status,
            "data": data,
            "error_code": None,
            "data_source": f"mcp:{server_label}",
        }

    # ------------------------------------------------------------------
    # 公开 API：测试连接
    # ------------------------------------------------------------------

    def test_connection(self, config: Dict, timeout: int = 15) -> Dict:
        """测试 MCP 服务器连接，返回 {success, tool_count, error, error_code}"""
        try:
            tools = self.discover_tools(config, timeout=timeout)
            return {"success": True, "tool_count": len(tools), "error": None, "error_code": None}
        except Exception as e:
            info = call_error_from_exception(e, server=_data_source_label(config))
            return {
                "success": False,
                "tool_count": 0,
                "error": info["error"],
                "error_code": info["error_code"],
            }


# ------------------------------------------------------------------
# 全局单例获取函数
# ------------------------------------------------------------------

_manager: Optional[MCPClientManager] = None


def get_mcp_client_manager() -> MCPClientManager:
    """获取 MCPClientManager 全局单例"""
    global _manager
    if _manager is None:
        _manager = MCPClientManager()
    return _manager

