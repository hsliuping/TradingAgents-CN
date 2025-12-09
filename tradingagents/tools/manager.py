import logging
import warnings
from typing import Iterable, List

from langchain_core.tools import StructuredTool

from tradingagents.tools.local.news import create_unified_news_tool
from tradingagents.tools.local.market import create_unified_market_tool
from tradingagents.tools.local.fundamentals import create_unified_fundamentals_tool
from tradingagents.tools.local.sentiment import create_unified_sentiment_tool
from tradingagents.tools.local.china import create_china_market_overview_tool

logger = logging.getLogger(__name__)

# 弃用警告消息
_DEPRECATION_MSG = (
    "此函数已弃用，建议使用 MCP 格式的工具。"
    "请参考 tradingagents/tools/mcp/ 目录下的新实现。"
    "使用 from tradingagents.tools.mcp import load_local_mcp_tools 加载 MCP 工具。"
)


def _wrap_tool(tool_fn):
    """
    将普通函数包装为 LangChain StructuredTool，便于 bind_tools 和 invoke。
    """
    return StructuredTool.from_function(
        func=tool_fn,
        name=getattr(tool_fn, "name", tool_fn.__name__),
        description=getattr(tool_fn, "description", ""),
        args_schema=getattr(tool_fn, "args_schema", None),
    )


def create_project_news_tools(toolkit) -> List:
    """
    项目内新闻相关工具的集中创建入口。
    
    .. deprecated::
        此函数已弃用，建议使用 MCP 格式的工具。
        请使用 `from tradingagents.tools.mcp import load_local_mcp_tools`
    """
    warnings.warn(_DEPRECATION_MSG, DeprecationWarning, stacklevel=2)
    try:
        news_tool_fn = create_unified_news_tool(toolkit)
        news_tool = _wrap_tool(news_tool_fn)
        logger.info(f"[工具管理] 已加载新闻工具: {getattr(news_tool, 'name', 'unamed')}")
        return [news_tool]
    except Exception as exc:
        logger.error(f"[工具管理] 创建新闻工具失败: {exc}")
        return []

def create_project_market_tools(toolkit) -> List:
    """
    项目内市场数据相关工具的集中创建入口。
    
    .. deprecated::
        此函数已弃用，建议使用 MCP 格式的工具。
    """
    warnings.warn(_DEPRECATION_MSG, DeprecationWarning, stacklevel=2)
    try:
        market_tool_fn = create_unified_market_tool(toolkit)
        market_tool = _wrap_tool(market_tool_fn)
        logger.info(f"[工具管理] 已加载市场数据工具: {getattr(market_tool, 'name', 'unamed')}")
        return [market_tool]
    except Exception as exc:
        logger.error(f"[工具管理] 创建市场数据工具失败: {exc}")
        return []

def create_project_fundamentals_tools(toolkit) -> List:
    """
    项目内基本面分析相关工具的集中创建入口。
    
    .. deprecated::
        此函数已弃用，建议使用 MCP 格式的工具。
    """
    warnings.warn(_DEPRECATION_MSG, DeprecationWarning, stacklevel=2)
    try:
        fundamentals_tool_fn = create_unified_fundamentals_tool(toolkit)
        fundamentals_tool = _wrap_tool(fundamentals_tool_fn)
        logger.info(f"[工具管理] 已加载基本面工具: {getattr(fundamentals_tool, 'name', 'unamed')}")
        return [fundamentals_tool]
    except Exception as exc:
        logger.error(f"[工具管理] 创建基本面工具失败: {exc}")
        return []

def create_project_sentiment_tools(toolkit) -> List:
    """
    项目内情绪分析相关工具的集中创建入口。
    
    .. deprecated::
        此函数已弃用，建议使用 MCP 格式的工具。
    """
    warnings.warn(_DEPRECATION_MSG, DeprecationWarning, stacklevel=2)
    try:
        sentiment_tool_fn = create_unified_sentiment_tool(toolkit)
        sentiment_tool = _wrap_tool(sentiment_tool_fn)
        logger.info(f"[工具管理] 已加载情绪分析工具: {getattr(sentiment_tool, 'name', 'unamed')}")
        return [sentiment_tool]
    except Exception as exc:
        logger.error(f"[工具管理] 创建情绪分析工具失败: {exc}")
        return []

def create_project_china_market_tools(toolkit) -> List:
    """
    项目内中国市场特定工具的集中创建入口。
    
    .. deprecated::
        此函数已弃用，建议使用 MCP 格式的工具。
    """
    warnings.warn(_DEPRECATION_MSG, DeprecationWarning, stacklevel=2)
    tools = []
    try:
        # 中国市场概览
        overview_fn = create_china_market_overview_tool(toolkit)
        overview_tool = _wrap_tool(overview_fn)
        tools.append(overview_tool)
        
        # Yahoo Finance (备用) - 已禁用
        # yfin_fn = create_yfinance_tool(toolkit)
        # yfin_tool = _wrap_tool(yfin_fn)
        # tools.append(yfin_tool)
        
        # 这里还可以加入 get_china_stock_data 的封装，如果需要的话
        # 但我们建议使用 unified_market_tool
        
        logger.info(f"[工具管理] 已加载中国市场工具: {len(tools)} 个")
        return tools
    except Exception as exc:
        logger.error(f"[工具管理] 创建中国市场工具失败: {exc}")
        return tools


def create_project_tools(toolkit) -> Iterable:
    """
    返回项目默认工具集（可按需扩展）。
    当前仅包含新闻工具。
    """
    return create_project_news_tools(toolkit)
