import logging
from typing import Iterable, List

from langchain_core.tools import StructuredTool

from tradingagents.tools.unified_news_tool import create_unified_news_tool

logger = logging.getLogger(__name__)


def _wrap_unified_news_tool(tool_fn):
    """
    将普通函数包装为 LangChain StructuredTool，便于 bind_tools 和 invoke。
    """
    return StructuredTool.from_function(
        func=tool_fn,
        name=getattr(tool_fn, "name", "get_stock_news_unified"),
        description=getattr(tool_fn, "description", "统一新闻获取工具"),
    )


def create_project_news_tools(toolkit) -> List:
    """
    项目内新闻相关工具的集中创建入口。

    Args:
        toolkit: 上游注入的工具集合/依赖容器。

    Returns:
        list: 已实例化并命名好的新闻工具列表。
    """
    try:
        news_tool_fn = create_unified_news_tool(toolkit)
        news_tool = _wrap_unified_news_tool(news_tool_fn)
        logger.info(f"[工具管理] 已加载新闻工具: {getattr(news_tool, 'name', 'unamed')}")
        return [news_tool]
    except Exception as exc:
        logger.error(f"[工具管理] 创建新闻工具失败: {exc}")
        return []


def create_project_tools(toolkit) -> Iterable:
    """
    返回项目默认工具集（可按需扩展）。
    当前仅包含新闻工具。
    """
    return create_project_news_tools(toolkit)
