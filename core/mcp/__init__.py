"""
MCP Server 模块

将 TradingAgents-CN 的多智能体分析能力暴露为 MCP 工具，
供 Claude Desktop、Cursor、OpenClaw 等 MCP Client 调用。

暴露的是"分析能力（成品）"，而非原始数据工具（零件）。

目录说明:
- server.py   — FastMCP 实例 + MCP 工具定义
- auth.py     — API Key 认证与用户映射
- __main__.py — 独立进程启动入口
"""

from core.mcp.auth import MCPApiKeyVerifier, mcp_auth
from core.mcp.server import mcp

__all__ = ["mcp", "mcp_auth", "MCPApiKeyVerifier"]

