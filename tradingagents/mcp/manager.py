"""
MCP客户端管理器 - 基于langchain-mcp-adapters
使用LangChain官方MCP适配器实现MCP服务器管理和工具调用

Copyright (c) 2025 TradingAgents-CN. All rights reserved.
"""

import asyncio
import json
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional

# MCP核心导入
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

# LangChain MCP适配器
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_mcp_adapters.tools import load_mcp_tools
from langchain_core.tools import StructuredTool

logger = logging.getLogger(__name__)


class MCPManager:
    """
    MCP管理器 - 基于langchain-mcp-adapters
    
    功能:
    1. 加载和管理多个MCP服务器配置
    2. 使用MultiServerMCPClient管理多服务器连接
    3. 提供工具列表获取和工具调用接口
    4. 支持stdio和streamable-http传输方式
    """
    
    def __init__(self, config_file: str = "config/mcp.json"):
        """
        初始化MCP管理器
        
        Args:
            config_file: MCP配置文件路径
        """
        self.config_file = config_file
        self.config: Dict[str, Any] = {}
        self.client: Optional[MultiServerMCPClient] = None
        self._started = False
        self._sessions: Dict[str, ClientSession] = {}
        
        logger.info("🔧 [MCP管理器] 初始化完成")
    
    async def start(self):
        """启动MCP管理器，加载配置"""
        if self._started:
            logger.debug("ℹ️ [MCP管理器] 已经启动，跳过")
            return
        
        try:
            # 加载配置
            await self._load_config()
            
            # 初始化MultiServerMCPClient
            if self.config.get("mcpServers"):
                server_configs = self._build_server_configs()
                if server_configs:
                    self.client = MultiServerMCPClient(server_configs)
                    logger.info(f"✅ [MCP管理器] 已初始化 {len(server_configs)} 个MCP服务器")
                else:
                    logger.info("ℹ️ [MCP管理器] 没有启用的MCP服务器")
            
            self._started = True
            logger.info("✅ [MCP管理器] 启动成功")
            
        except Exception as e:
            logger.error(f"❌ [MCP管理器] 启动失败: {e}", exc_info=True)
            raise
    
    async def _load_config(self):
        """加载MCP配置文件"""
        try:
            config_path = Path(self.config_file)
            if not config_path.exists():
                logger.warning(f"⚠️ [MCP管理器] 配置文件不存在: {self.config_file}")
                self.config = {"mcpServers": {}}
                return
            
            with open(config_path, 'r', encoding='utf-8') as f:
                self.config = json.load(f)
            
            logger.info(f"✅ [MCP管理器] 配置文件加载成功: {self.config_file}")
            
        except json.JSONDecodeError as e:
            logger.error(f"❌ [MCP管理器] 配置文件JSON格式错误: {e}")
            self.config = {"mcpServers": {}}
        except Exception as e:
            logger.error(f"❌ [MCP管理器] 加载配置失败: {e}")
            self.config = {"mcpServers": {}}
    
    def _build_server_configs(self) -> Dict[str, Dict[str, Any]]:
        """
        构建MultiServerMCPClient所需的服务器配置
        
        Returns:
            Dict[server_name, server_config]
        """
        server_configs = {}
        mcp_servers = self.config.get("mcpServers", {})
        
        for name, config in mcp_servers.items():
            # 只处理启用的服务器
            if not config.get("enabled", False):
                logger.debug(f"⏭️ [MCP管理器] 跳过未启用的服务器: {name}")
                continue
            
            server_type = config.get("type", "stdio")
            
            if server_type == "stdio":
                # STDIO传输配置
                server_configs[name] = {
                    "command": config.get("command"),
                    "args": config.get("args", []),
                    "transport": "stdio",
                    "env": config.get("env", {})
                }
            elif server_type in ["http", "streamable-http"]:
                # HTTP传输配置
                server_configs[name] = {
                    "url": config.get("url"),
                    "transport": "streamable_http",
                    "headers": config.get("headers", {})
                }
            else:
                logger.warning(f"⚠️ [MCP管理器] 不支持的传输类型: {server_type} (服务器: {name})")
                continue
            
            logger.debug(f"✅ [MCP管理器] 配置服务器: {name} ({server_type})")
        
        return server_configs
    
    async def get_server_tools(self, server_name: str) -> List[Dict[str, Any]]:
        """
        获取指定MCP服务器的工具列表
        
        Args:
            server_name: 服务器名称
            
        Returns:
            工具信息列表 [{"name": "tool_name", "description": "...", "inputSchema": {...}}]
        """
        if not self._started:
            await self.start()
        
        if not self.client:
            logger.warning("⚠️ [MCP管理器] 没有可用的MCP客户端")
            return []
        
        try:
            # 使用MultiServerMCPClient的session上下文
            async with self.client.session(server_name) as session:
                # 获取工具列表
                tools_response = await session.list_tools()
                
                # 转换为标准格式
                tools_info = []
                for tool in tools_response.tools:
                    tools_info.append({
                        "name": tool.name,
                        "description": tool.description or "",
                        "inputSchema": tool.inputSchema or {}
                    })
                
                logger.info(f"✅ [MCP管理器] 获取服务器 {server_name} 的 {len(tools_info)} 个工具")
                return tools_info
                
        except Exception as e:
            logger.error(f"❌ [MCP管理器] 获取服务器 {server_name} 工具失败: {e}", exc_info=True)
            return []
    
    async def call_tool(
        self,
        server_name: str,
        tool_name: str,
        arguments: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        调用MCP服务器的工具
        
        Args:
            server_name: 服务器名称
            tool_name: 工具名称
            arguments: 工具参数
            
        Returns:
            {"success": bool, "result": Any, "error": str}
        """
        if not self._started:
            await self.start()
        
        if not self.client:
            return {
                "success": False,
                "error": "没有可用的MCP客户端"
            }
        
        try:
            logger.info(f"📞 [MCP管理器] 调用工具: {server_name}.{tool_name}")
            logger.debug(f"📝 [MCP管理器] 参数: {arguments}")
            
            # 使用MultiServerMCPClient的session上下文
            async with self.client.session(server_name) as session:
                # 调用工具
                result = await session.call_tool(tool_name, arguments=arguments)
                
                logger.info(f"✅ [MCP管理器] 工具调用成功: {server_name}.{tool_name}")
                
                return {
                    "success": True,
                    "result": result.content if hasattr(result, 'content') else result
                }
                
        except Exception as e:
            error_msg = str(e)
            logger.error(f"❌ [MCP管理器] 工具调用失败: {server_name}.{tool_name} - {error_msg}", exc_info=True)
            return {
                "success": False,
                "error": error_msg
            }
    
    async def get_all_tools(self) -> List[StructuredTool]:
        """
        获取所有启用的MCP服务器的工具（LangChain格式）
        
        Returns:
            LangChain StructuredTool列表
        """
        if not self._started:
            await self.start()
        
        if not self.client:
            logger.warning("⚠️ [MCP管理器] 没有可用的MCP客户端")
            return []
        
        try:
            # 使用langchain-mcp-adapters的load_mcp_tools
            # 需要为每个服务器创建session并加载工具
            all_tools = []
            
            server_configs = self._build_server_configs()
            for server_name in server_configs.keys():
                try:
                    async with self.client.session(server_name) as session:
                        tools = await load_mcp_tools(session)
                        
                        # 为工具添加服务器标识
                        for tool in tools:
                            tool.metadata = tool.metadata or {}
                            tool.metadata["mcp_server"] = server_name
                            tool.metadata["mcp_native"] = True
                        
                        all_tools.extend(tools)
                        logger.info(f"✅ [MCP管理器] 从服务器 {server_name} 加载 {len(tools)} 个工具")
                        
                except Exception as e:
                    logger.error(f"❌ [MCP管理器] 从服务器 {server_name} 加载工具失败: {e}")
                    continue
            
            logger.info(f"✅ [MCP管理器] 总共加载 {len(all_tools)} 个MCP工具")
            return all_tools
            
        except Exception as e:
            logger.error(f"❌ [MCP管理器] 获取所有工具失败: {e}", exc_info=True)
            return []
    
    async def get_server_status(self, server_name: str) -> Dict[str, Any]:
        """
        获取服务器状态
        
        Args:
            server_name: 服务器名称
            
        Returns:
            状态信息字典
        """
        if not self._started:
            await self.start()
        
        # 检查服务器是否在配置中
        mcp_servers = self.config.get("mcpServers", {})
        if server_name not in mcp_servers:
            return {
                "name": server_name,
                "status": "offline",
                "error": "服务器不存在于配置中"
            }
        
        server_config = mcp_servers[server_name]
        if not server_config.get("enabled", False):
            return {
                "name": server_name,
                "status": "offline",
                "error": "服务器未启用"
            }
        
        # 尝试获取工具列表来测试连接
        try:
            tools = await self.get_server_tools(server_name)
            return {
                "name": server_name,
                "status": "online",
                "tools_count": len(tools),
                "framework": "langchain-mcp-adapters"
            }
        except Exception as e:
            return {
                "name": server_name,
                "status": "offline",
                "error": str(e)
            }
    
    async def disconnect(self):
        """断开所有MCP连接"""
        try:
            # 关闭所有会话
            for session_name, session in self._sessions.items():
                try:
                    await session.close()
                    logger.debug(f"✅ [MCP管理器] 关闭会话: {session_name}")
                except Exception as e:
                    logger.warning(f"⚠️ [MCP管理器] 关闭会话失败: {session_name} - {e}")
            
            self._sessions.clear()
            self.client = None
            self._started = False
            
            logger.info("✅ [MCP管理器] 所有连接已断开")
            
        except Exception as e:
            logger.error(f"❌ [MCP管理器] 断开连接失败: {e}", exc_info=True)
    
    def reload_config(self):
        """重新加载配置（先断开再重新启动）"""
        async def _reload():
            await self.disconnect()
            await self.start()
        
        # 在当前事件循环中运行
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.create_task(_reload())
            else:
                loop.run_until_complete(_reload())
        except RuntimeError:
            asyncio.run(_reload())


# 全局单例
mcp_manager = MCPManager()


__all__ = ["MCPManager", "mcp_manager"]
