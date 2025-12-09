"""
本地 MCP 服务器

使用 FastMCP 框架创建本地 MCP 服务器，托管所有转换后的工具。
提供统一的工具注册和加载接口。
"""

import logging
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)

# 检查 MCP 库是否可用
try:
    from mcp.server.fastmcp import FastMCP
    MCP_AVAILABLE = True
except ImportError:
    MCP_AVAILABLE = False
    logger.warning("mcp 库未安装，MCP 服务器功能不可用")
    FastMCP = None


class LocalMCPServer:
    """
    本地 MCP 服务器，托管所有本地工具。
    
    使用 FastMCP 框架创建，支持 stdio 和 HTTP 传输模式。
    """
    
    def __init__(self, toolkit: Optional[Dict] = None, name: str = "TradingAgents Local Tools"):
        """
        初始化本地 MCP 服务器。
        
        Args:
            toolkit: 工具配置字典，包含数据源配置等
            name: 服务器名称
        """
        self.toolkit = toolkit or {}
        self.name = name
        self._tools: Dict[str, Any] = {}
        self._mcp: Optional[Any] = None
        
        if MCP_AVAILABLE:
            self._mcp = FastMCP(name)
            self._register_tools()
            logger.info(f"🚀 [LocalMCPServer] 初始化完成，服务器名称: {name}")
        else:
            logger.warning("[LocalMCPServer] MCP 库不可用，使用降级模式")
    
    def _register_tools(self):
        """注册所有本地工具到 MCP 服务器"""
        if not MCP_AVAILABLE or not self._mcp:
            return
        
        # 设置工具配置
        from tradingagents.tools.mcp.tools import news, market, fundamentals, sentiment, china
        
        news.set_toolkit_config(self.toolkit)
        market.set_toolkit_config(self.toolkit)
        fundamentals.set_toolkit_config(self.toolkit)
        sentiment.set_toolkit_config(self.toolkit)
        china.set_toolkit_config(self.toolkit)
        
        # 注册新闻工具
        @self._mcp.tool()
        def get_stock_news(stock_code: str, max_news: int = 10) -> str:
            """
            统一新闻获取工具 - 根据股票代码自动获取相应市场的新闻。
            
            自动识别股票类型（A股/港股/美股）并从最佳数据源获取新闻。
            
            Args:
                stock_code: 股票代码（A股如600519，港股如0700.HK，美股如AAPL）
                max_news: 获取新闻的最大数量，默认10条
            
            Returns:
                格式化的新闻内容
            """
            return news.get_stock_news(stock_code, max_news)
        
        self._tools['get_stock_news'] = get_stock_news
        
        # 注册市场数据工具
        @self._mcp.tool()
        def get_stock_market_data(ticker: str, start_date: str, end_date: str) -> str:
            """
            统一股票市场数据工具 - 获取股票的历史价格、技术指标和市场表现。
            
            自动识别股票类型（A股/港股/美股）并调用最佳数据源。
            
            Args:
                ticker: 股票代码
                start_date: 开始日期，格式：YYYY-MM-DD
                end_date: 结束日期，格式：YYYY-MM-DD
            
            Returns:
                格式化的市场数据
            """
            return market.get_stock_market_data(ticker, start_date, end_date)
        
        self._tools['get_stock_market_data'] = get_stock_market_data
        
        # 注册基本面工具
        @self._mcp.tool()
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
            
            Returns:
                格式化的基本面分析数据
            """
            return fundamentals.get_stock_fundamentals(ticker, curr_date, start_date, end_date)
        
        self._tools['get_stock_fundamentals'] = get_stock_fundamentals
        
        # 注册情绪分析工具
        @self._mcp.tool()
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
            
            Returns:
                格式化的情绪分析数据
            """
            return sentiment.get_stock_sentiment(ticker, curr_date, start_date, end_date, source_name)
        
        self._tools['get_stock_sentiment'] = get_stock_sentiment
        
        # 注册中国市场工具
        @self._mcp.tool()
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
            
            Returns:
                格式化的市场概览数据
            """
            return china.get_china_market_overview(date, include_indices, include_sectors)
        
        self._tools['get_china_market_overview'] = get_china_market_overview
        
        logger.info(f"📦 [LocalMCPServer] 已注册 {len(self._tools)} 个工具: {list(self._tools.keys())}")
    
    def get_tools(self) -> List[Any]:
        """
        获取所有注册的工具。
        
        Returns:
            工具列表
        """
        return list(self._tools.values())
    
    def get_tool_names(self) -> List[str]:
        """
        获取所有注册的工具名称。
        
        Returns:
            工具名称列表
        """
        return list(self._tools.keys())
    
    def get_mcp_instance(self) -> Optional[Any]:
        """
        获取 FastMCP 实例。
        
        Returns:
            FastMCP 实例，如果不可用则返回 None
        """
        return self._mcp
    
    def run(self, transport: str = "stdio"):
        """
        运行 MCP 服务器。
        
        Args:
            transport: 传输模式，支持 "stdio" 或 "streamable-http"
        """
        if not MCP_AVAILABLE or not self._mcp:
            logger.error("[LocalMCPServer] MCP 库不可用，无法运行服务器")
            return
        
        logger.info(f"🚀 [LocalMCPServer] 启动服务器，传输模式: {transport}")
        self._mcp.run(transport=transport)


# 全局单例
_global_server: Optional[LocalMCPServer] = None


def get_local_mcp_server(toolkit: Optional[Dict] = None) -> LocalMCPServer:
    """
    获取本地 MCP 服务器单例。
    
    Args:
        toolkit: 工具配置字典
    
    Returns:
        LocalMCPServer 实例
    """
    global _global_server
    if _global_server is None:
        _global_server = LocalMCPServer(toolkit)
    return _global_server


def reset_local_mcp_server():
    """重置本地 MCP 服务器单例"""
    global _global_server
    _global_server = None
