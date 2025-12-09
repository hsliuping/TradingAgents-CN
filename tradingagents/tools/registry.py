import logging
import warnings
from typing import Callable, Iterable, List, Optional

from tradingagents.tools.manager import (
    create_project_news_tools,
    create_project_market_tools,
    create_project_fundamentals_tools,
    create_project_sentiment_tools,
    create_project_china_market_tools
)

logger = logging.getLogger(__name__)

# MCP 工具加载标志
_USE_MCP_TOOLS = True  # 默认使用 MCP 工具


def _tool_names(tools: Iterable) -> set:
    return {
        getattr(t, "name", None)
        for t in tools
        if getattr(t, "name", None)
    }


def _load_mcp_tools(loader: Callable[[], Iterable] | None, existing_names: set | None = None) -> List:
    """
    预留的 MCP 工具加载入口；目前返回空列表或 loader 结果。
    """
    if not loader:
        return []
    try:
        tools = list(loader())
        if existing_names:
            filtered = []
            for t in tools:
                t_name = getattr(t, "name", None)
                if t_name and t_name in existing_names:
                    logger.warning(f"[工具注册] MCP 工具名称冲突，已跳过: {t_name}")
                    continue
                filtered.append(t)
            tools = filtered

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
    """统一新闻分析工具集装配。"""
    tools: List = []

    project_tools = create_project_news_tools(toolkit)
    logger.info(f"[工具注册] 项目新闻工具: {len(project_tools)} 个")
    tools.extend(project_tools)

    if enable_mcp:
        mcp_tools = _load_mcp_tools(mcp_tool_loader, existing_names=_tool_names(project_tools))
        logger.info(f"[工具注册] MCP 工具: {len(mcp_tools)} 个")
        tools.extend(mcp_tools)

    return tools

def get_market_toolset(
    toolkit,
    enable_mcp: bool = False,
    mcp_tool_loader: Callable[[], Iterable] | None = None,
) -> List:
    """统一市场数据工具集装配。"""
    tools: List = []

    project_tools = create_project_market_tools(toolkit)
    logger.info(f"[工具注册] 项目市场数据工具: {len(project_tools)} 个")
    tools.extend(project_tools)

    if enable_mcp:
        mcp_tools = _load_mcp_tools(mcp_tool_loader, existing_names=_tool_names(project_tools))
        tools.extend(mcp_tools)

    return tools

def get_fundamentals_toolset(
    toolkit,
    enable_mcp: bool = False,
    mcp_tool_loader: Callable[[], Iterable] | None = None,
) -> List:
    """统一基本面分析工具集装配。"""
    tools: List = []

    project_tools = create_project_fundamentals_tools(toolkit)
    logger.info(f"[工具注册] 项目基本面工具: {len(project_tools)} 个")
    tools.extend(project_tools)

    if enable_mcp:
        mcp_tools = _load_mcp_tools(mcp_tool_loader, existing_names=_tool_names(project_tools))
        tools.extend(mcp_tools)

    return tools

def get_sentiment_toolset(
    toolkit,
    enable_mcp: bool = False,
    mcp_tool_loader: Callable[[], Iterable] | None = None,
) -> List:
    """统一情绪分析工具集装配。"""
    tools: List = []

    project_tools = create_project_sentiment_tools(toolkit)
    logger.info(f"[工具注册] 项目情绪分析工具: {len(project_tools)} 个")
    tools.extend(project_tools)

    if enable_mcp:
        mcp_tools = _load_mcp_tools(mcp_tool_loader, existing_names=_tool_names(project_tools))
        tools.extend(mcp_tools)

    return tools

def get_china_market_toolset(
    toolkit,
    enable_mcp: bool = False,
    mcp_tool_loader: Callable[[], Iterable] | None = None,
) -> List:
    """中国市场特定工具集装配。"""
    tools: List = []

    project_tools = list(create_project_china_market_tools(toolkit))
    market_tools = list(create_project_market_tools(toolkit))

    # 基于 name 去重，避免重复注册同名工具
    existing_names = _tool_names(project_tools)
    for tool in market_tools:
        t_name = getattr(tool, "name", None)
        if t_name and t_name in existing_names:
            logger.info(f"[工具注册] 跳过重复的市场工具: {t_name}")
            continue
        project_tools.append(tool)
        if t_name:
            existing_names.add(t_name)

    logger.info(f"[工具注册] 项目中国市场工具: {len(project_tools)} 个 (已去重)")
    tools.extend(project_tools)

    if enable_mcp:
        mcp_tools = _load_mcp_tools(mcp_tool_loader, existing_names=_tool_names(project_tools))
        tools.extend(mcp_tools)

    return tools

def get_all_tools(
    toolkit,
    enable_mcp: bool = False,
    mcp_tool_loader: Callable[[], Iterable] | None = None,
    use_mcp_format: bool = True,
) -> List:
    """
    统一获取全量工具集，供所有分析师使用。
    
    Args:
        toolkit: 工具配置
        enable_mcp: 是否启用外部 MCP 工具
        mcp_tool_loader: 外部 MCP 工具加载器
        use_mcp_format: 是否使用 MCP 格式的本地工具（推荐）
    
    Returns:
        工具列表
    """
    all_tools: List = []
    tool_map = {}
    
    def _merge_tools(tools: List):
        for t in tools:
            t_name = getattr(t, "name", None)
            if t_name:
                tool_map[t_name] = t
            else:
                all_tools.append(t)

    # 优先使用 MCP 格式的本地工具
    if use_mcp_format and _USE_MCP_TOOLS:
        try:
            from tradingagents.tools.mcp import load_local_mcp_tools
            
            # 转换 toolkit 为字典格式
            if isinstance(toolkit, dict):
                toolkit_config = toolkit
            elif hasattr(toolkit, 'config'):
                toolkit_config = toolkit.config
            else:
                toolkit_config = {}
            
            mcp_local_tools = load_local_mcp_tools(toolkit_config)
            _merge_tools(mcp_local_tools)
            logger.info(f"[工具注册] MCP 格式本地工具加载完成: {len(mcp_local_tools)} 个")
        except Exception as e:
            logger.warning(f"[工具注册] MCP 格式工具加载失败，回退到旧格式: {e}")
            use_mcp_format = False
    
    # 如果 MCP 格式不可用，使用旧格式
    if not use_mcp_format or not tool_map:
        warnings.warn(
            "使用旧格式工具，建议迁移到 MCP 格式。"
            "参考: tradingagents/tools/mcp/",
            DeprecationWarning,
            stacklevel=2
        )
        
        _merge_tools(create_project_news_tools(toolkit))
        _merge_tools(create_project_market_tools(toolkit))
        _merge_tools(create_project_fundamentals_tools(toolkit))
        _merge_tools(create_project_sentiment_tools(toolkit))
        _merge_tools(create_project_china_market_tools(toolkit))
        
        logger.info(f"[工具注册] 旧格式项目工具加载完成: {len(tool_map)} 个 (已去重)")

    # 将 map 转回 list
    unique_project_tools = list(tool_map.values())
    all_tools.extend(unique_project_tools)
    
    # 加载外部 MCP 工具 (如果启用)
    if enable_mcp:
        mcp_tools = _load_mcp_tools(mcp_tool_loader, existing_names=set(tool_map.keys()))
        all_tools.extend(mcp_tools)
        logger.info(f"[工具注册] 外部 MCP 工具追加完成: {len(mcp_tools)} 个")

    return all_tools


def get_all_tools_mcp(toolkit_config: Optional[dict] = None) -> List:
    """
    获取所有 MCP 格式的工具（新接口）。
    
    这是推荐的工具获取方式，返回标准 MCP 格式的工具。
    
    Args:
        toolkit_config: 工具配置字典
    
    Returns:
        MCP 格式的工具列表
    """
    try:
        from tradingagents.tools.mcp import load_local_mcp_tools
        return load_local_mcp_tools(toolkit_config)
    except Exception as e:
        logger.error(f"[工具注册] MCP 工具加载失败: {e}")
        return []
