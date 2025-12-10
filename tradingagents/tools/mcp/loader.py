# pyright: reportMissingImports=false
"""
MCP 工具加载器

基于官方 langchain-mcp-adapters 实现，支持 stdio 和 SSE 两种传输模式。
参考文档: https://docs.langchain.com/oss/python/langchain/mcp
"""
import asyncio
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, TYPE_CHECKING

from tradingagents.tools.mcp.config_utils import (
    DEFAULT_CONFIG_FILE,
    MCPServerConfig,
    MCPServerType,
    get_config_path,
    load_mcp_config,
)
from tradingagents.tools.mcp.config_watcher import AsyncConfigWatcher
from tradingagents.tools.mcp.health_monitor import HealthMonitor, ServerStatus

logger = logging.getLogger(__name__)

# 检查 langchain-mcp-adapters 是否可用
try:
    from langchain_mcp_adapters.client import MultiServerMCPClient
    LANGCHAIN_MCP_AVAILABLE = True
except ImportError:
    MultiServerMCPClient = None  # type: ignore
    LANGCHAIN_MCP_AVAILABLE = False
    logger.warning("langchain-mcp-adapters 未安装，外部 MCP 服务器不可用")

# 检查 LangChain 工具是否可用
try:
    from langchain_core.tools import tool, StructuredTool, BaseTool
    LANGCHAIN_TOOLS_AVAILABLE = True
except ImportError:
    LANGCHAIN_TOOLS_AVAILABLE = False
    StructuredTool = None  # type: ignore
    BaseTool = None  # type: ignore
    tool = None  # type: ignore
    logger.warning("langchain-core 未安装，工具转换功能受限")

# 可选：用于识别并展开 RunnableBinding（langchain-mcp-adapters 输出常见类型）
try:
    from langchain_core.runnables import RunnableBinding
    LANGCHAIN_RUNNABLE_AVAILABLE = True
except ImportError:
    RunnableBinding = None  # type: ignore
    LANGCHAIN_RUNNABLE_AVAILABLE = False
if TYPE_CHECKING:
    pass


def load_local_mcp_tools(toolkit: Optional[Dict] = None) -> List[Any]:
    """
    从本地 MCP 服务器加载工具并转换为 LangChain 工具格式。
    
    这些是内置的本地工具，不依赖外部 MCP 服务器。
    
    Args:
        toolkit: 工具配置字典
    
    Returns:
        LangChain 工具列表
    """
    start_time = datetime.now()
    logger.info("[MCP Loader] 开始加载本地 MCP 工具...")
    
    try:
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
            from langchain_core.tools import tool as lc_tool
            
            @lc_tool
            def get_stock_news(stock_code: str, max_news: int = 10) -> str:
                """
                统一新闻获取工具 - 根据股票代码自动获取相应市场的新闻。
                
                Args:
                    stock_code: 股票代码（A股如600519，港股如0700.HK，美股如AAPL）
                    max_news: 获取新闻的最大数量，默认10条
                """
                return news.get_stock_news(stock_code, max_news)
            
            @lc_tool
            def get_stock_market_data(ticker: str, start_date: str, end_date: str) -> str:
                """
                统一股票市场数据工具 - 获取股票的历史价格、技术指标和市场表现。
                
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
                
                Args:
                    date: 查询日期（可选，默认为今天）
                    include_indices: 是否包含主要指数数据
                    include_sectors: 是否包含板块表现数据
                """
                return china.get_china_market_overview(date, include_indices, include_sectors)
            
            @lc_tool
            def list_analysis_reports() -> str:
                """列出当前可用的所有分析报告目录。"""
                return reports.list_reports()
            
            @lc_tool
            def get_analysis_report(
                field_name: str,
                max_chars: int = None,
                summary: bool = False
            ) -> str:
                """
                获取指定分析报告的内容。
                
                Args:
                    field_name: 报告字段名
                    max_chars: 最大返回字符数（可选）
                    summary: 是否返回摘要（可选）
                """
                return reports.get_report_content(field_name, max_chars, summary)
            
            @lc_tool
            def get_analysis_reports_batch(
                field_names: list,
                max_chars_each: int = None
            ) -> str:
                """
                批量获取多个分析报告的内容。
                
                Args:
                    field_names: 报告字段名列表
                    max_chars_each: 每个报告的最大字符数（可选）
                """
                return reports.get_reports_batch(field_names, max_chars_each)
            
            tools = [
                get_stock_news,
                get_stock_market_data,
                get_stock_fundamentals,
                get_stock_sentiment,
                get_china_market_overview,
                list_analysis_reports,
                get_analysis_report,
                get_analysis_reports_batch,
            ]
        
        execution_time = (datetime.now() - start_time).total_seconds()
        logger.info(f"✅ [MCP Loader] 加载完成，共 {len(tools)} 个本地工具，耗时 {execution_time:.2f}秒")
        
        return tools
    
    except Exception as e:
        logger.error(f"❌ [MCP Loader] 加载本地 MCP 工具失败: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return []


def get_all_tools_mcp(toolkit: Optional[Dict] = None) -> List[Any]:
    """获取所有 MCP 格式的工具（同步接口）。"""
    return load_local_mcp_tools(toolkit)



class MCPToolLoaderFactory:
    """
    MCP 工具加载工厂，基于官方 langchain-mcp-adapters 的 MultiServerMCPClient。
    
    支持两种传输模式（符合官方文档）：
    - stdio: 通过子进程通信的本地服务器
    - sse: 通过 Server-Sent Events 通信的远程服务器
    
    参考: https://docs.langchain.com/oss/python/langchain/mcp
    """

    def __init__(self, config_file: str | Path | None = None):
        self.config_file = get_config_path(Path(config_file) if config_file else DEFAULT_CONFIG_FILE)
        # 官方 MultiServerMCPClient 实例
        self._mcp_client: Optional[Any] = None
        # 从 MCP 服务器加载的工具
        self._mcp_tools: List[Any] = []
        # 健康监控
        self._health_monitor = HealthMonitor()
        # 服务器配置缓存
        self._server_configs: Dict[str, MCPServerConfig] = {}
        # 配置文件监视器
        self._async_config_watcher: Optional[AsyncConfigWatcher] = None
        # 是否已初始化
        self._initialized = False

    # ------------------------------------------------------------------
    # 工具兼容处理：展开 RunnableBinding，补齐 __name__ / name 以兼容
    # langchain_core.tools.tool 装饰器以及 LangGraph ToolNode。
    # ------------------------------------------------------------------
    def _unwrap_runnable_binding(self, tool: Any) -> Any:
        """
        将 RunnableBinding 解包为原始工具，确保具备 __name__/name 属性。

        langchain-mcp-adapters 返回的工具常常是 RunnableBinding；
        在传递给 langgraph.prebuilt.ToolNode 之前必须提供可用的 __name__，
        否则 LangChain 的 @tool 装饰器会抛出
        "The first argument must be a string or a callable with a __name__ for tool decorator."
        """
        if not LANGCHAIN_RUNNABLE_AVAILABLE or RunnableBinding is None:
            return tool

        # 仅处理 RunnableBinding
        if not isinstance(tool, RunnableBinding):
            return tool

        bound = getattr(tool, "bound", None)
        base = bound or tool

        # 尝试补齐 __name__，工具名优先级：已有 name -> __name__ -> 类名
        name = getattr(base, "name", None) or getattr(base, "__name__", None) or base.__class__.__name__
        try:
            if not hasattr(base, "__name__"):
                base.__name__ = name  # type: ignore[attr-defined]
        except Exception:
            pass

        tool_obj = tool
        try:
            tool_classes = tuple(
                cls for cls in (BaseTool, StructuredTool) if cls is not None  # type: ignore[arg-type]
            )
            if tool_classes and isinstance(base, tool_classes):
                tool_obj = base
        except Exception:
            pass

        # 附加/合并 metadata，保留服务器信息
        metadata: Dict[str, Any] = {}
        for candidate in (getattr(tool, "metadata", None), getattr(base, "metadata", None)):
            if isinstance(candidate, dict):
                metadata.update(candidate)
        if metadata:
            try:
                existing = getattr(tool_obj, "metadata", {}) or {}
                if isinstance(existing, dict):
                    metadata = {**existing, **metadata}
                setattr(tool_obj, "metadata", metadata)
            except Exception:
                pass

        # 确保 name 属性存在
        try:
            if not getattr(tool_obj, "name", None):
                setattr(tool_obj, "name", name)
        except Exception:
            pass

        return tool_obj

    def _attach_server_metadata(self, tool: Any, server_name: str) -> Any:
        """
        为工具安全地附加服务器元数据。
        StructuredTool/BaseTool 使用 __slots__，直接 setattr 会抛异常，这里采用 metadata。
        """
        tool = self._unwrap_runnable_binding(tool)

        if tool is None:
            return tool

        metadata = {}
        try:
            existing = getattr(tool, "metadata", {}) or {}
            if isinstance(existing, dict):
                metadata.update(existing)
        except Exception:
            pass

        metadata.setdefault("server_name", server_name)
        metadata.setdefault("server_id", server_name)

        # 优先使用 with_config（LangChain 推荐）
        try:
            if hasattr(tool, "with_config"):
                return tool.with_config({"metadata": metadata})
        except Exception as e:
            logger.debug(f"[MCP] with_config 附加元数据失败: {e}")

        # 退化写入 metadata
        try:
            setattr(tool, "metadata", metadata)
        except Exception:
            pass

        # 尝试写入可选属性（若未使用 __slots__）
        for attr in ("server_name", "_server_name"):
            try:
                setattr(tool, attr, server_name)
            except Exception:
                continue

        return tool

    def _build_server_params(self) -> Dict[str, Dict[str, Any]]:
        """
        构建符合官方 MultiServerMCPClient 格式的服务器参数。
        
        官方格式 (langchain-mcp-adapters):
        {
            "server_name": {
                "command": "uvx",
                "args": ["mcp-server-package"],
                "env": {"KEY": "value"},
                "transport": "stdio",
            },
            "remote_server": {
                "url": "http://localhost:8000/mcp",
                "transport": "streamable_http",  # 新标准，替代 sse
                "headers": {"Authorization": "Bearer xxx"},
            }
        }
        
        注意：langchain-mcp-adapters 使用下划线 "streamable_http"
        """
        server_params = {}
        
        for name, config in self._server_configs.items():
            if not config.enabled:
                continue
            
            if config.is_stdio():
                # stdio 模式 - 本地子进程
                server_params[name] = {
                    "command": config.command,
                    "args": config.args or [],
                    "env": {**os.environ, **config.env} if config.env else None,
                    "transport": "stdio",
                }
            elif config.is_http():
                # HTTP 模式 - 远程服务器
                # 根据配置类型选择传输协议
                if config.is_streamable_http():
                    # streamable-http 是 MCP 官方新标准
                    # langchain-mcp-adapters 使用下划线格式
                    transport = "streamable_http"
                else:
                    # 旧的 http 类型，使用 sse 传输（向后兼容）
                    transport = "sse"
                
                server_params[name] = {
                    "url": config.url,
                    "transport": transport,
                }
                # 如果有自定义 headers，添加到配置中
                if config.headers:
                    server_params[name]["headers"] = config.headers
        
        return server_params

    async def initialize_connections(self):
        """
        使用官方 MultiServerMCPClient 初始化所有 MCP 服务器连接。
        """
        if self._initialized:
            return
        
        if not self.config_file.exists():
            logger.info(f"[MCP] 配置文件不存在: {self.config_file}")
            self._initialized = True
            return
        
        # 加载配置
        config = load_mcp_config(self.config_file)
        servers = config.get("mcpServers", {})
        
        for server_name, server_config_dict in servers.items():
            try:
                server_config = MCPServerConfig(**server_config_dict)
                self._server_configs[server_name] = server_config
                
                if not server_config.enabled:
                    self._health_monitor.mark_server_stopped(server_name)
                else:
                    # 先注册为未知状态，等待连接结果
                    self._health_monitor.register_server(
                        server_name,
                        lambda: True,
                        initial_status=ServerStatus.UNKNOWN
                    )
                    
            except Exception as e:
                logger.error(f"[MCP] 解析服务器配置 {server_name} 失败: {e}")
        
        # 使用官方 MultiServerMCPClient
        if LANGCHAIN_MCP_AVAILABLE and self._server_configs:
            server_params = self._build_server_params()
            
            if server_params:
                # 逐个服务器尝试连接，避免一个失败导致全部失败
                for name, params in server_params.items():
                    try:
                        logger.info(f"[MCP] 正在连接服务器 {name}...")
                        single_client = MultiServerMCPClient({name: params})
                        raw_tools = await single_client.get_tools()

                        # 为每个工具设置服务器名称元数据（兼容 StructuredTool）
                        annotated_tools = [
                            self._attach_server_metadata(tool, name)
                            for tool in raw_tools
                        ]

                        self._mcp_tools.extend(annotated_tools)
                        logger.info(f"[MCP] 服务器 {name} 连接成功，加载了 {len(annotated_tools)} 个工具")
                        
                        # 更新健康状态为健康
                        self._health_monitor._update_status(
                            name,
                            ServerStatus.HEALTHY,
                            latency_ms=0
                        )
                        
                    except Exception as e:
                        logger.warning(f"[MCP] 服务器 {name} 连接失败: {e}")
                        # 标记为不可达，但不影响其他服务器
                        self._health_monitor._update_status(
                            name,
                            ServerStatus.UNREACHABLE,
                            error=str(e)
                        )
                
                logger.info(f"[MCP] 共加载了 {len(self._mcp_tools)} 个工具")
        
        # 启动配置文件监视
        await self._start_config_watching()
        
        self._initialized = True

    def create_loader(self, selected_tool_ids: List[str], include_local: bool = False) -> Callable[[], Iterable]:
        """返回同步 loader，兼容 registry 的调用方式。"""
        return lambda: self.load_tools(selected_tool_ids, include_local=include_local)

    async def get_tools(self, selected_tool_ids: List[str]) -> List[Any]:
        """异步获取 MCP 工具列表。"""
        if not self._initialized:
            await self.initialize_connections()
        return self.load_tools(selected_tool_ids)

    def load_tools(self, selected_tool_ids: List[str], include_local: bool = True) -> List[Any]:
        """
        加载工具列表。
        
        合并本地工具和从 MCP 服务器加载的工具。
        """
        # 本地工具
        local_tools = load_local_mcp_tools() if include_local else []
        
        # MCP 服务器工具
        raw_tools = local_tools + self._mcp_tools
        # 展开 RunnableBinding，避免 LangGraph/ToolNode 包装时报 __name__ 错误
        all_tools = [self._unwrap_runnable_binding(t) for t in raw_tools]
        
        if not selected_tool_ids:
            return all_tools
        
        # 过滤选择的工具
        selected_tools = []
        for tool in all_tools:
            tool_name = getattr(tool, 'name', '')
            if tool_name in selected_tool_ids or f"local:{tool_name}" in selected_tool_ids:
                selected_tools.append(tool)
        
        return selected_tools if selected_tools else all_tools

    def list_available_tools(self) -> List[Dict[str, Any]]:
        """列出所有可用工具的元数据。"""
        result = []
        
        # 本地工具
        local_tools = load_local_mcp_tools()
        for tool in local_tools:
            tool_name = getattr(tool, 'name', 'unknown')
            tool_desc = getattr(tool, 'description', '')
            
            result.append({
                "id": f"local:{tool_name}",
                "name": tool_name,
                "description": tool_desc,
                "serverName": "local",
                "serverId": "local",
                "status": "healthy",
                "available": True,
            })
        
        # MCP 服务器工具 - 尝试从工具属性中获取服务器名称
        for tool in self._mcp_tools:
            tool_name = getattr(tool, 'name', 'unknown')
            tool_desc = getattr(tool, 'description', '')
            
            # 尝试从多个属性获取服务器名称
            server_name = (
                getattr(tool, 'server_name', None) or
                getattr(tool, 'server', None) or
                getattr(tool, '_server_name', None) or
                "mcp"
            )
            
            # 如果工具有 metadata 属性，尝试从中获取服务器信息
            metadata = getattr(tool, 'metadata', {}) or {}
            if isinstance(metadata, dict):
                server_name = metadata.get('server_name', server_name)
            
            result.append({
                "id": f"{server_name}:{tool_name}",
                "name": tool_name,
                "description": tool_desc,
                "serverName": server_name,
                "serverId": server_name,
                "status": "healthy",
                "available": True,
            })
        
        logger.info(f"[MCP] list_available_tools: 本地工具 {len(local_tools)} 个, 外部 MCP 工具 {len(self._mcp_tools)} 个")
        
        return result

    def get_server_status(self, name: str) -> ServerStatus:
        """获取服务器状态。"""
        return self._health_monitor.get_server_status(name)

    def get_all_server_status(self) -> Dict[str, Dict[str, Any]]:
        """获取所有服务器状态。"""
        return self._health_monitor.get_all_server_status()

    def toggle_server(self, server_name: str, enabled: bool) -> bool:
        """
        切换服务器启用状态。
        
        注意：使用官方 MultiServerMCPClient 时，需要重新初始化连接。
        """
        if server_name not in self._server_configs:
            logger.warning(f"[MCP] 服务器 {server_name} 不存在")
            return False
        
        # 更新配置
        self._server_configs[server_name].enabled = enabled
        
        if enabled:
            self._health_monitor.register_server(
                server_name,
                lambda: True,
                initial_status=ServerStatus.UNKNOWN
            )
            logger.info(f"[MCP] 服务器 {server_name} 已启用（需要重新初始化连接）")
        else:
            self._health_monitor.mark_server_stopped(server_name)
            logger.info(f"[MCP] 服务器 {server_name} 已禁用")
        
        return True

    async def reload_config(self):
        """重新加载配置并重新初始化连接。"""
        # 关闭现有连接
        await self.close_all_async()
        
        # 重置状态
        self._initialized = False
        self._server_configs.clear()
        self._mcp_tools.clear()
        
        # 重新初始化
        await self.initialize_connections()

    def close_all(self):
        """同步关闭所有连接。"""
        self._mcp_tools.clear()
        self._server_configs.clear()

    async def close_all_async(self):
        """异步关闭所有连接。"""
        # 停止配置监视
        await self._stop_config_watching()
        
        # 清理 MultiServerMCPClient
        # langchain-mcp-adapters 0.1.0+ 不再需要显式关闭
        self._mcp_client = None
        
        self.close_all()
        self._initialized = False

    async def _start_config_watching(self):
        """启动配置文件监视。"""
        if self._async_config_watcher is not None:
            return
        
        self._async_config_watcher = AsyncConfigWatcher(
            self.config_file,
            self._on_config_change,
            poll_interval=5.0,
        )
        await self._async_config_watcher.start()
        logger.info(f"[MCP] 配置文件监视已启动: {self.config_file}")

    async def _stop_config_watching(self):
        """停止配置文件监视。"""
        if self._async_config_watcher is not None:
            await self._async_config_watcher.stop()
            self._async_config_watcher = None

    async def _on_config_change(self):
        """配置文件变更回调。"""
        logger.info("[MCP] 检测到配置文件变更，正在重新加载...")
        try:
            await self.reload_config()
            logger.info("[MCP] 配置重新加载完成")
        except Exception as e:
            logger.error(f"[MCP] 配置重新加载失败: {e}")


# 全局单例
_global_loader_factory: Optional[MCPToolLoaderFactory] = None


def get_mcp_loader_factory() -> MCPToolLoaderFactory:
    global _global_loader_factory
    if _global_loader_factory is None:
        _global_loader_factory = MCPToolLoaderFactory()
    return _global_loader_factory
