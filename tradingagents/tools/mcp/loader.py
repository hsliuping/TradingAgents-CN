# pyright: reportMissingImports=false
import asyncio
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, TYPE_CHECKING

from tradingagents.tools.mcp.config_utils import (
    DEFAULT_CONFIG_FILE,
    get_config_path,
    load_mcp_config,
)

logger = logging.getLogger(__name__)

# 官方推荐：使用 langchain-mcp-adapters 适配器而非直接使用 mcp SDK
try:
    from langchain_mcp_adapters.tools import load_mcp_tools

    LANGCHAIN_MCP_AVAILABLE = True
except ImportError:  # pragma: no cover - 仅在未安装时执行
    load_mcp_tools = None  # type: ignore
    LANGCHAIN_MCP_AVAILABLE = False
    logger.warning("langchain-mcp-adapters 未安装，MCP 工具不可用")

# 检查 LangChain 工具是否可用
try:
    from langchain_core.tools import tool, StructuredTool
    LANGCHAIN_TOOLS_AVAILABLE = True
except ImportError:
    LANGCHAIN_TOOLS_AVAILABLE = False
    logger.warning("langchain-core 未安装，工具转换功能受限")

if TYPE_CHECKING:  # 仅用于类型检查，避免运行时依赖
    pass


def load_local_mcp_tools(toolkit: Optional[Dict] = None) -> List[Any]:
    """
    从本地 MCP 服务器加载工具并转换为 LangChain 工具格式。
    
    Args:
        toolkit: 工具配置字典
    
    Returns:
        LangChain 工具列表
    """
    start_time = datetime.now()
    logger.info("[MCP Loader] 开始加载本地 MCP 工具...")
    
    try:
        from tradingagents.tools.mcp.local_server import get_local_mcp_server
        from tradingagents.tools.mcp.tools import news, market, fundamentals, sentiment, china, reports
        
        # 设置工具配置
        config = toolkit or {}
        news.set_toolkit_config(config)
        market.set_toolkit_config(config)
        fundamentals.set_toolkit_config(config)
        sentiment.set_toolkit_config(config)
        china.set_toolkit_config(config)
        
        tools = []
        
        if LANGCHAIN_TOOLS_AVAILABLE:
            # 使用 @tool 装饰器创建 LangChain 工具
            from langchain_core.tools import tool as lc_tool
            
            @lc_tool
            def get_stock_news(stock_code: str, max_news: int = 10) -> str:
                """
                统一新闻获取工具 - 根据股票代码自动获取相应市场的新闻。
                
                自动识别股票类型（A股/港股/美股）并从最佳数据源获取新闻。
                
                Args:
                    stock_code: 股票代码（A股如600519，港股如0700.HK，美股如AAPL）
                    max_news: 获取新闻的最大数量，默认10条
                """
                return news.get_stock_news(stock_code, max_news)
            
            @lc_tool
            def get_stock_market_data(ticker: str, start_date: str, end_date: str) -> str:
                """
                统一股票市场数据工具 - 获取股票的历史价格、技术指标和市场表现。
                
                自动识别股票类型（A股/港股/美股）并调用最佳数据源。
                
                Args:
                    ticker: 股票代码
                    start_date: 开始日期，格式：YYYY-MM-DD
                    end_date: 结束日期，格式：YYYY-MM-DD
                """
                return market.get_stock_market_data(ticker, start_date, end_date)
            
            @lc_tool
            def get_stock_fundamentals(
                ticker: str,
                curr_date: str = None,
                start_date: str = None,
                end_date: str = None
            ) -> str:
                """
                统一股票基本面分析工具 - 获取股票的财务数据和估值指标。
                
                自动识别股票类型（A股/港股/美股）并调用最佳数据源。
                
                Args:
                    ticker: 股票代码
                    curr_date: 当前日期（可选）
                    start_date: 开始日期（可选）
                    end_date: 结束日期（可选）
                """
                return fundamentals.get_stock_fundamentals(ticker, curr_date, start_date, end_date)
            
            @lc_tool
            def get_stock_sentiment(
                ticker: str,
                curr_date: str,
                start_date: str = None,
                end_date: str = None,
                source_name: str = None
            ) -> str:
                """
                统一股票情绪分析工具 - 获取市场对股票的情绪倾向。
                
                自动识别股票类型并调用相应数据源。
                
                Args:
                    ticker: 股票代码
                    curr_date: 当前日期，格式：YYYY-MM-DD
                    start_date: 开始日期（可选）
                    end_date: 结束日期（可选）
                    source_name: 指定数据源名称（可选）
                """
                return sentiment.get_stock_sentiment(ticker, curr_date, start_date, end_date, source_name)
            
            @lc_tool
            def get_china_market_overview(
                date: str = None,
                include_indices: bool = True,
                include_sectors: bool = True
            ) -> str:
                """
                中国A股市场概览工具 - 获取中国A股市场的整体概况。
                
                提供市场指数、板块表现、资金流向等宏观市场数据。
                
                Args:
                    date: 查询日期（可选，默认为今天）
                    include_indices: 是否包含主要指数数据
                    include_sectors: 是否包含板块表现数据
                """
                return china.get_china_market_overview(date, include_indices, include_sectors)
            
            # 报告访问工具 - 供看涨/看跌研究员动态获取一阶段分析报告
            @lc_tool
            def list_analysis_reports() -> str:
                """
                列出当前可用的所有分析报告目录。
                
                此工具帮助你了解有哪些一阶段分析师生成的报告可供参考。
                返回每个报告的字段名、显示名称、内容长度和摘要。
                
                使用场景：
                - 在辩论开始前了解有哪些数据源
                - 查找特定类型的分析报告
                
                Returns:
                    格式化的报告目录字符串，包含所有可用报告的元信息
                """
                return reports.list_reports()
            
            @lc_tool
            def get_analysis_report(
                field_name: str,
                max_chars: int = None,
                summary: bool = False
            ) -> str:
                """
                获取指定分析报告的内容。
                
                此工具让你获取一阶段分析师生成的特定报告内容。
                
                Args:
                    field_name: 报告字段名（通过 list_analysis_reports 获取）
                    max_chars: 最大返回字符数（可选，用于截断长报告）
                    summary: 是否返回摘要而非原文（可选）
                
                常用字段名：
                - market_report: 市场分析报告
                - sentiment_report: 情绪分析报告
                - news_report: 新闻分析报告
                - fundamentals_report: 基本面分析报告
                - china_market_report: 中国市场分析报告
                
                Returns:
                    报告内容字符串，或错误信息
                """
                return reports.get_report_content(field_name, max_chars, summary)
            
            @lc_tool
            def get_analysis_reports_batch(
                field_names: list,
                max_chars_each: int = None
            ) -> str:
                """
                批量获取多个分析报告的内容。
                
                一次性获取多个报告，提高效率。
                
                Args:
                    field_names: 报告字段名列表，如 ["market_report", "news_report"]
                    max_chars_each: 每个报告的最大字符数（可选）
                
                Returns:
                    所有请求报告的内容，按字段名分隔
                
                Example:
                    get_analysis_reports_batch(["market_report", "fundamentals_report"])
                """
                return reports.get_reports_batch(field_names, max_chars_each)
            
            tools = [
                get_stock_news,
                get_stock_market_data,
                get_stock_fundamentals,
                get_stock_sentiment,
                get_china_market_overview,
                # 报告访问工具
                list_analysis_reports,
                get_analysis_report,
                get_analysis_reports_batch,
            ]
        else:
            logger.warning("[MCP Loader] LangChain 工具不可用，返回空列表")
        
        execution_time = (datetime.now() - start_time).total_seconds()
        logger.info(f"✅ [MCP Loader] 加载完成，共 {len(tools)} 个工具，耗时 {execution_time:.2f}秒")
        
        return tools
    
    except Exception as e:
        logger.error(f"❌ [MCP Loader] 加载本地 MCP 工具失败: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return []


def get_all_tools_mcp(toolkit: Optional[Dict] = None) -> List[Any]:
    """
    获取所有 MCP 格式的工具（同步接口）。
    
    这是主要的工具获取入口，返回所有可用的 MCP 工具。
    
    Args:
        toolkit: 工具配置字典
    
    Returns:
        LangChain 工具列表
    """
    return load_local_mcp_tools(toolkit)


class MCPToolLoaderFactory:
    """
    MCP 工具加载工厂，基于官方 langchain-mcp-adapters 适配器。
    负责按需创建连接、过滤用户选择的工具，并提供列表查询能力。
    """

    def __init__(self, config_file: str | Path | None = None):
        self.config_file = get_config_path(Path(config_file) if config_file else DEFAULT_CONFIG_FILE)
        self._clients: Dict[str, Any] = {}
        self._toolkits: Dict[str, Any] = {}

    # ------------------------------------------------------------------ #
    # 公共接口：供业务层/Tool Registry 调用
    # ------------------------------------------------------------------ #
    def create_loader(self, selected_tool_ids: List[str]) -> Callable[[], Iterable]:
        """返回同步 loader，兼容 registry 的调用方式。"""
        return lambda: self.load_tools(selected_tool_ids)

    async def get_tools(self, selected_tool_ids: List[str]) -> List[Any]:
        """
        异步获取 MCP 工具列表。
        """
        return await asyncio.to_thread(self.load_tools, selected_tool_ids)

    async def initialize_connections(self):
        """
        预热所有已启用的 MCP 服务器连接。
        """
        if not LANGCHAIN_MCP_AVAILABLE or not self.config_file.exists():
            return
        pass

    def load_tools(self, selected_tool_ids: List[str]) -> List[Any]:
        """按选择的 ID 列表加载 LangChain 工具对象。"""
        # 优先加载本地 MCP 工具
        local_tools = load_local_mcp_tools()
        
        if not selected_tool_ids:
            return local_tools
        
        # 过滤选择的工具
        selected_tools = []
        for tool in local_tools:
            tool_name = getattr(tool, 'name', '')
            if tool_name in selected_tool_ids or f"local:{tool_name}" in selected_tool_ids:
                selected_tools.append(tool)
        
        return selected_tools if selected_tools else local_tools

    def list_available_tools(self) -> List[Dict[str, Any]]:
        """
        列出所有启用服务器的工具元数据，供 API 返回给前端。
        """
        tools = load_local_mcp_tools()
        result = []
        
        for tool in tools:
            tool_name = getattr(tool, 'name', 'unknown')
            tool_desc = getattr(tool, 'description', '')
            
            result.append({
                "id": f"local:{tool_name}",
                "name": tool_name,
                "description": tool_desc,
                "serverName": "local",
                "serverId": "local",
                "status": "healthy",
            })
        
        return result

    def close_all(self):
        """关闭所有已创建的连接。"""
        self._clients.clear()
        self._toolkits.clear()

    # ------------------------------------------------------------------ #
    # 内部方法
    # ------------------------------------------------------------------ #
    def _group_tool_ids(self, selected_tool_ids: List[str]) -> Dict[str, List[str]]:
        server_tools_map: Dict[str, List[str]] = {}
        for tool_id in selected_tool_ids:
            if ":" not in tool_id:
                continue
            server_name, tool_name = tool_id.split(":", 1)
            server_tools_map.setdefault(server_name, []).append(tool_name)
        return server_tools_map

    def _is_server_enabled(self, server_name: str, server_config: Optional[Dict[str, Any]]) -> bool:
        if not server_config:
            logger.warning(f"[MCP] 未找到服务器配置: {server_name}")
            return False
        if "command" not in server_config:
            logger.warning(f"[MCP] 服务器 {server_name} 缺少 command 配置，已跳过")
            return False
        if not server_config.get("_enabled", True):
            logger.info(f"[MCP] 服务器 {server_name} 已被禁用，跳过加载")
            return False
        return True

    def _get_or_create_toolkit(self, server_name: str, server_config: Dict[str, Any]):
        if server_name in self._toolkits:
            return self._toolkits[server_name]

        if not LANGCHAIN_MCP_AVAILABLE:
            return None

        env = {**os.environ, **server_config.get("env", {})}
        try:
            toolkit = MCPToolkit(
                server_name=server_name,
                command=server_config["command"],
                args=server_config.get("args", []),
                env=env,
            )
            self._toolkits[server_name] = toolkit
            return toolkit
        except Exception as exc:  # pragma: no cover
            logger.error(f"[MCP] 创建 {server_name} MCPToolkit 失败: {exc}")
            return None

    def _filter_tools(self, server_name: str, tool_names: List[str], tools: Iterable[Any]) -> List[Any]:
        if not tool_names:
            return list(tools)

        selected = []
        for tool in tools:
            name = getattr(tool, "name", None)
            if not name:
                continue
            if name in tool_names or f"{server_name}:{name}" in tool_names:
                selected.append(tool)
        return selected

    def _format_tool_metadata(self, server_name: str, tool: Any) -> Dict[str, Any]:
        schema = None
        args_schema = getattr(tool, "args_schema", None)
        if args_schema:
            schema_fn = getattr(args_schema, "model_json_schema", None) or getattr(args_schema, "schema", None)
            if callable(schema_fn):
                try:
                    schema = schema_fn()
                except Exception:  # pragma: no cover
                    schema = None

        return {
            "id": f"{server_name}:{getattr(tool, 'name', 'unknown')}",
            "name": getattr(tool, "name", "unknown"),
            "description": getattr(tool, "description", "") or "No description",
            "serverName": server_name,
            "serverId": server_name,
            "status": "healthy",
            "schema": schema,
        }

    def _warmup_toolkits(self):
        """同步预热，便于在 async initialize_connections 中调用。"""
        config = load_mcp_config(self.config_file)
        servers = config.get("mcpServers", {})
        for server_name, server_config in servers.items():
            if not self._is_server_enabled(server_name, server_config):
                continue
            toolkit = self._get_or_create_toolkit(server_name, server_config)
            if not toolkit:
                continue
            try:
                toolkit.get_tools()
            except Exception as exc:  # pragma: no cover
                logger.error(f"[MCP] 预热 {server_name} 失败: {exc}")


# 全局单例
_global_loader_factory: Optional[MCPToolLoaderFactory] = None


def get_mcp_loader_factory() -> MCPToolLoaderFactory:
    global _global_loader_factory
    if _global_loader_factory is None:
        _global_loader_factory = MCPToolLoaderFactory()
    return _global_loader_factory
