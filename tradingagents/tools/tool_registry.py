import logging
from typing import Callable, Iterable, List

from tradingagents.tools.project_tool_manager import create_project_news_tools

logger = logging.getLogger(__name__)


def _load_mcp_tools(loader: Callable[[], Iterable] | None) -> List:
    """
    预留的 MCP 工具加载入口；目前返回空列表或 loader 结果。
    """
    if not loader:
        return []
    try:
        tools = list(loader())
        logger.info(f"[工具注册] MCP 工具加载成功: {len(tools)} 个")
        return tools
    except Exception as exc:
        logger.warning(f"[工具注册] MCP 工具加载失败: {exc}")
        return []


def get_news_toolset(
    toolkit,
    enable_mcp: bool = False,
    mcp_tool_loader: Callable[[], Iterable] | None = None,
) -> List:
    """
    统一新闻分析工具集装配。

    Args:
        toolkit: 上游注入的工具集合/依赖容器。
        enable_mcp: 是否合并 MCP 工具。
        mcp_tool_loader: 可选的 MCP 工具加载函数。

    Returns:
        list: 已装配的工具列表。
    """
    tools: List = []

    project_tools = create_project_news_tools(toolkit)
    logger.info(f"[工具注册] 项目新闻工具: {len(project_tools)} 个")
    tools.extend(project_tools)

    if enable_mcp:
        mcp_tools = _load_mcp_tools(mcp_tool_loader)
        logger.info(f"[工具注册] MCP 工具: {len(mcp_tools)} 个")
        tools.extend(mcp_tools)

    return tools
