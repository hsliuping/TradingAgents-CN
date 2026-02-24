"""
MCP 客户端管理器

在后台线程中运行独立的 asyncio 事件循环，
提供同步接口供工具注册表和 Agent 调用。
支持 SSE、Streamable HTTP、stdio 三种传输方式。
"""

import asyncio
import json
import logging
import threading
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


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

        return self._run_sync(self._with_session(config, _action), timeout=timeout)

    # ------------------------------------------------------------------
    # 公开 API：工具调用
    # ------------------------------------------------------------------

    def call_tool(
        self,
        config: Dict,
        tool_name: str,
        arguments: Dict,
        timeout: int = 60,
    ) -> str:
        """
        连接 MCP 服务器并调用指定工具。

        Returns:
            工具返回结果（字符串形式）
        """
        async def _action(session):
            result = await session.call_tool(tool_name, arguments=arguments)
            # 将 content list 拼成字符串
            parts = []
            for c in result.content:
                if hasattr(c, "text"):
                    parts.append(c.text)
                else:
                    parts.append(json.dumps(c.model_dump(), ensure_ascii=False))
            return "\n".join(parts)

        return self._run_sync(self._with_session(config, _action), timeout=timeout)

    # ------------------------------------------------------------------
    # 公开 API：测试连接
    # ------------------------------------------------------------------

    def test_connection(self, config: Dict, timeout: int = 15) -> Dict:
        """测试 MCP 服务器连接，返回 {success, tool_count, error}"""
        try:
            tools = self.discover_tools(config, timeout=timeout)
            return {"success": True, "tool_count": len(tools), "error": None}
        except Exception as e:
            return {"success": False, "tool_count": 0, "error": str(e)}


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

