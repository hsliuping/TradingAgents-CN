"""
MCP (Model Context Protocol) 集成模块

提供客户端管理和工具包装，支持用户自定义 MCP 服务器接入。
传输类型：
  - sse              — Server-Sent Events (HTTP)
  - streamable_http  — Streamable HTTP (新版 MCP 标准)
  - stdio            — 子进程标准输入输出

失败/空数据语义：请求失败抛 McpTransportError（带 error_code），
请求成功但无数据返回空结果，两者严格区分（见 errors 模块）。
"""

from .client_manager import MCPClientManager, get_mcp_client_manager
from .errors import (
    McpCallError,
    McpErrorCodes,
    McpTransportError,
    classify_transport_error,
)

__all__ = [
    "MCPClientManager",
    "get_mcp_client_manager",
    "McpCallError",
    "McpErrorCodes",
    "McpTransportError",
    "classify_transport_error",
]

