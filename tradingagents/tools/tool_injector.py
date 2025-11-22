"""
统一工具注入模块
合并自定义工具和MCP工具，提供统一的工具列表

基于langchain-mcp-adapters实现MCP集成

Copyright (c) 2025 TradingAgents-CN. All rights reserved.
"""

import asyncio
import logging
from typing import List, Optional
from langchain_core.tools import StructuredTool

logger = logging.getLogger(__name__)


def inject_tools(
    custom_tools: List[StructuredTool],
    analyst: Optional[str] = None
) -> List[StructuredTool]:
    """
    统一工具注入函数
    
    功能：
    1. 保持自定义工具原样
    2. 从langchain-mcp-adapters加载MCP工具
    3. 根据analyst筛选MCP服务器
    4. 合并并返回完整工具列表
    
    参数：
        custom_tools: 自定义工具对象列表
                     例如：[create_unified_news_tool(toolkit)]
        
        analyst: Analyst名称，用于筛选MCP服务器
                例如："news", "market", "fundamentals"
                如果为None，加载所有启用的MCP服务器
    
    返回：
        List[StructuredTool]: 合并后的工具列表
        - 自定义工具（保持原样）
        - MCP工具（通过langchain-mcp-adapters）
    
    使用示例：
        # 新闻分析师
        unified_news_tool = create_unified_news_tool(toolkit)
        tools = inject_tools([unified_news_tool], analyst="news")
        
        # 返回：[unified_news_tool, mcp_tool1, mcp_tool2, ...]
    """
    logger.info(f"🔧 [工具注入] 开始注入工具 - Analyst: {analyst or 'all'}")
    logger.info(f"📦 [工具注入] 自定义工具数量: {len(custom_tools)}")
    
    # 步骤1：保持自定义工具原样
    final_tools = list(custom_tools)  # 创建副本
    
    # 步骤2：加载MCP工具
    try:
        mcp_tools = _load_mcp_tools(analyst)
        logger.info(f"🔧 [工具注入] MCP工具数量: {len(mcp_tools)}")
        
        # 步骤3：合并工具列表
        final_tools.extend(mcp_tools)
        
    except Exception as e:
        logger.warning(f"⚠️ [工具注入] 加载MCP工具失败: {e}")
        logger.debug(f"详细错误", exc_info=True)
        # MCP工具加载失败不影响自定义工具使用
    
    logger.info(f"✅ [工具注入] 工具注入完成 - 总工具数: {len(final_tools)}")
    logger.info(f"📋 [工具注入] 工具列表: {[tool.name for tool in final_tools]}")
    
    return final_tools


def _load_mcp_tools(analyst: Optional[str] = None) -> List[StructuredTool]:
    """
    从langchain-mcp-adapters加载MCP工具
    
    参数：
        analyst: Analyst名称，用于筛选服务器
    
    返回：
        List[StructuredTool]: MCP工具列表（LangChain格式）
    """
    from tradingagents.mcp import mcp_manager
    from tradingagents.tools.mcp_config_helper import get_enabled_mcp_servers
    
    # 1. 获取启用的MCP服务器配置
    enabled_servers = get_enabled_mcp_servers(analyst=analyst)
    
    if not enabled_servers:
        logger.debug(f"ℹ️ [MCP工具加载] 没有启用的MCP服务器")
        return []
    
    logger.info(f"📡 [MCP工具加载] 找到 {len(enabled_servers)} 个启用的服务器")
    
    # 2. 获取或创建事件循环
    try:
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            logger.debug(f"🔄 [MCP工具加载] 事件循环已关闭，创建新的事件循环")
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
    except RuntimeError:
        logger.debug(f"🔄 [MCP工具加载] 没有事件循环，创建新的事件循环")
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    # 3. 确保MCP管理器已启动
    if not mcp_manager._started:
        logger.info(f"🚀 [MCP工具加载] 启动MCP管理器...")
        loop.run_until_complete(mcp_manager.start())
    
    # 4. 获取所有MCP工具（langchain-mcp-adapters会自动处理工具格式）
    try:
        all_tools = loop.run_until_complete(mcp_manager.get_all_tools())
        
        # 5. 根据analyst筛选（如果MCP管理器已经筛选了服务器，这里可能不需要再筛选）
        # 但为了保持兼容性，我们仍然检查工具的metadata
        if analyst:
            filtered_tools = []
            for tool in all_tools:
                # 检查工具的metadata中的服务器名称
                server_name = tool.metadata.get("mcp_server") if tool.metadata else None
                
                # 检查该服务器是否适用于当前analyst
                server_match = False
                for server_config in enabled_servers:
                    if server_config["name"] == server_name:
                        for_analysts = server_config.get("for_analysts", [])
                        if not for_analysts or analyst in for_analysts:
                            server_match = True
                            break
                
                if server_match:
                    filtered_tools.append(tool)
            
            logger.info(f"🎯 [MCP工具加载] 为analyst '{analyst}' 筛选出 {len(filtered_tools)} 个工具")
            return filtered_tools
        
        logger.info(f"✅ [MCP工具加载] 成功加载 {len(all_tools)} 个MCP工具")
        return all_tools
        
    except Exception as e:
        logger.error(f"❌ [MCP工具加载] 加载工具失败: {e}", exc_info=True)
        return []


__all__ = ["inject_tools"]
