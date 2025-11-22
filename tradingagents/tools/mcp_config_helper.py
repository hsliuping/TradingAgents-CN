"""
MCP配置辅助模块
用于读取和筛选MCP服务器配置

Copyright (c) 2025 TradingAgents-CN. All rights reserved.
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)


def get_enabled_mcp_servers(analyst: Optional[str] = None, config_file: str = "config/mcp.json") -> List[Dict[str, Any]]:
    """
    获取启用的MCP服务器配置
    
    参数：
        analyst: Analyst名称，用于筛选（如："news", "market", "fundamentals"）
                如果为None，返回所有启用的服务器
        config_file: MCP配置文件路径
    
    返回：
        List[Dict]: 服务器配置列表
        [
            {
                "name": "filesystem",
                "description": "文件系统操作工具",
                "enabled": true,
                "for_analysts": ["news", "market"],
                "type": "stdio",
                "command": "node",
                "args": [...],
                ...
            }
        ]
    """
    try:
        # 1. 读取配置文件
        config_path = Path(config_file)
        if not config_path.exists():
            logger.warning(f"⚠️ [MCP配置] 配置文件不存在: {config_file}")
            return []
        
        with open(config_path, 'r', encoding='utf-8') as f:
            mcp_config = json.load(f)
        
        # 2. 提取服务器配置
        # 支持两种格式：{"servers": {...}} 或 {"mcpServers": {...}}
        servers_dict = mcp_config.get("mcpServers", mcp_config.get("servers", {}))
        
        if not servers_dict:
            logger.debug(f"ℹ️ [MCP配置] 配置文件中没有服务器配置")
            return []
        
        # 3. 筛选启用的服务器
        enabled_servers = []
        for name, config in servers_dict.items():
            if not config.get("enabled", False):
                logger.debug(f"⏭️ [MCP配置] 跳过未启用的服务器: {name}")
                continue
            
            # 构建服务器配置对象
            server_config = {
                "name": name,
                **config  # 包含所有原始配置
            }
            
            enabled_servers.append(server_config)
        
        logger.info(f"✅ [MCP配置] 从配置文件加载了 {len(enabled_servers)} 个启用的服务器")
        
        # 4. 根据analyst筛选
        if analyst:
            filtered_servers = []
            for server in enabled_servers:
                for_analysts = server.get("for_analysts", [])
                
                # 如果未指定for_analysts，或者analyst在列表中，则包含该服务器
                if not for_analysts or analyst in for_analysts:
                    filtered_servers.append(server)
                else:
                    logger.debug(f"⏭️ [MCP配置] 服务器 {server['name']} 不适用于 analyst '{analyst}'")
            
            logger.info(f"🎯 [MCP配置] 为 analyst '{analyst}' 筛选出 {len(filtered_servers)} 个服务器")
            return filtered_servers
        
        return enabled_servers
    
    except json.JSONDecodeError as e:
        logger.error(f"❌ [MCP配置] 配置文件JSON格式错误: {e}")
        return []
    except Exception as e:
        logger.error(f"❌ [MCP配置] 读取配置文件失败: {e}")
        return []


def get_server_description(server_config: Dict[str, Any]) -> str:
    """
    获取服务器描述
    
    参数：
        server_config: 服务器配置字典
    
    返回：
        str: 服务器描述文本
    """
    return server_config.get("description", "")


def validate_server_config(server_config: Dict[str, Any]) -> bool:
    """
    验证服务器配置是否有效
    
    参数：
        server_config: 服务器配置字典
    
    返回：
        bool: 配置是否有效
    """
    # 检查必需字段
    if "name" not in server_config:
        logger.warning(f"⚠️ [MCP配置] 服务器配置缺少name字段")
        return False
    
    server_type = server_config.get("type")
    
    # STDIO类型需要command字段
    if server_type == "stdio":
        if "command" not in server_config:
            logger.warning(f"⚠️ [MCP配置] STDIO服务器 {server_config['name']} 缺少command字段")
            return False
    
    # HTTP类型需要url字段
    elif server_type in ["http", "streamable-http"]:
        if "url" not in server_config:
            logger.warning(f"⚠️ [MCP配置] HTTP服务器 {server_config['name']} 缺少url字段")
            return False
    
    # 未指定类型，尝试自动推断
    elif not server_type:
        if "command" not in server_config and "url" not in server_config:
            logger.warning(f"⚠️ [MCP配置] 服务器 {server_config['name']} 缺少command或url字段")
            return False
    
    return True
