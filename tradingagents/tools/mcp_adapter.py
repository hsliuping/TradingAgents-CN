"""
MCP工具适配器 - 基于langchain-mcp-adapters
提供MCP工具的快速获取接口

Copyright (c) 2025 TradingAgents-CN. All rights reserved.
"""

import asyncio
import json
import logging
from pathlib import Path
from typing import List

from langchain_core.tools import StructuredTool

logger = logging.getLogger(__name__)


class MCPToolAdapter:
    """MCP工具适配器 - 简化接口"""
    
    @classmethod
    async def get_enabled_mcp_tools(
        cls, 
        config_file: str = "config/mcp.json",
        force_reload: bool = False
    ) -> List[StructuredTool]:
        """
        加载所有enabled=true的MCP服务器工具
        
        Args:
            config_file: MCP配置文件路径
            force_reload: 是否强制重新加载
            
        Returns:
            LangChain StructuredTool对象列表
        """
        from tradingagents.mcp import mcp_manager
        
        try:
            # 如果强制重载，重新启动管理器
            if force_reload:
                logger.info("🔧 [MCP适配器] 强制重新加载MCP工具")
                await mcp_manager.disconnect()
                await mcp_manager.start()
            
            # 确保管理器已启动
            if not mcp_manager._started:
                await mcp_manager.start()
            
            # 获取所有工具
            tools = await mcp_manager.get_all_tools()
            
            logger.info(f"✅ [MCP适配器] 成功加载 {len(tools)} 个MCP工具")
            return tools
            
        except Exception as e:
            logger.error(f"❌ [MCP适配器] 加载MCP工具失败: {e}", exc_info=True)
            return []


__all__ = ["MCPToolAdapter"]
