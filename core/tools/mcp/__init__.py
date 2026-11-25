"""
MCP (Model Context Protocol) 集成模块

提供客户端管理和工具包装，支持用户自定义 MCP 服务器接入。
传输类型：
  - sse              — Server-Sent Events (HTTP)
  - streamable_http  — Streamable HTTP (新版 MCP 标准)
  - stdio            — 子进程标准输入输出
"""

from .client_manager import MCPClientManager, get_mcp_client_manager

__all__ = ["MCPClientManager", "get_mcp_client_manager"]

