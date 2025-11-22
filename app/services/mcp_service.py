"""
MCP服务层 - 为API提供MCP功能接口
基于langchain-mcp-adapters实现

Copyright (c) 2025 TradingAgents-CN. All rights reserved.
"""

import asyncio
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional

from tradingagents.mcp import mcp_manager
from tradingagents.tools.mcp_config_helper import get_enabled_mcp_servers, validate_server_config

logger = logging.getLogger(__name__)


class MCPService:
    """MCP服务 - 提供配置管理和状态查询"""
    
    @staticmethod
    async def get_config() -> Dict[str, Any]:
        """
        获取MCP配置
        
        Returns:
            {"mcpServers": {...}}
        """
        try:
            config_path = Path("config/mcp.json")
            if not config_path.exists():
                return {"mcpServers": {}}
            
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            return config
            
        except Exception as e:
            logger.error(f"❌ [MCP服务] 读取配置失败: {e}")
            return {"mcpServers": {}}
    
    @staticmethod
    async def save_config(config: Dict[str, Any]) -> Dict[str, Any]:
        """
        保存MCP配置
        
        Args:
            config: {"mcpServers": {...}}
            
        Returns:
            {"success": bool, "message": str}
        """
        try:
            config_path = Path("config/mcp.json")
            config_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
            
            # 重新加载MCP管理器配置
            mcp_manager.reload_config()
            
            logger.info("✅ [MCP服务] 配置保存成功")
            return {
                "success": True,
                "message": "配置保存成功"
            }
            
        except Exception as e:
            logger.error(f"❌ [MCP服务] 保存配置失败: {e}")
            return {
                "success": False,
                "message": f"保存配置失败: {str(e)}"
            }
    
    @staticmethod
    async def validate_config(config: Dict[str, Any]) -> Dict[str, Any]:
        """
        验证MCP配置
        
        Args:
            config: {"mcpServers": {...}}
            
        Returns:
            {"valid": bool, "errors": List[str]}
        """
        errors = []
        
        try:
            if "mcpServers" not in config:
                return {
                    "valid": False,
                    "errors": ["配置中缺少mcpServers字段"]
                }
            
            mcp_servers = config["mcpServers"]
            if not isinstance(mcp_servers, dict):
                return {
                    "valid": False,
                    "errors": ["mcpServers必须是字典类型"]
                }
            
            # 验证每个服务器配置
            for name, server_config in mcp_servers.items():
                server_config_with_name = {"name": name, **server_config}
                
                if not validate_server_config(server_config_with_name):
                    errors.append(f"服务器 {name} 配置无效")
            
            if errors:
                return {
                    "valid": False,
                    "errors": errors
                }
            
            return {
                "valid": True,
                "errors": []
            }
            
        except Exception as e:
            logger.error(f"❌ [MCP服务] 验证配置失败: {e}")
            return {
                "valid": False,
                "errors": [f"验证失败: {str(e)}"]
            }
    
    @staticmethod
    async def get_servers_status() -> List[Dict[str, Any]]:
        """
        获取所有MCP服务器状态
        
        Returns:
            List[{"name": str, "status": str, "enabled": bool, ...}]
        """
        try:
            # 获取所有配置的服务器
            all_servers = get_enabled_mcp_servers(analyst=None)
            
            # 获取每个服务器的状态
            statuses = []
            for server_config in all_servers:
                server_name = server_config["name"]
                enabled = server_config.get("enabled", False)
                
                if enabled:
                    # 获取服务器状态
                    status_info = await mcp_manager.get_server_status(server_name)
                else:
                    status_info = {
                        "name": server_name,
                        "status": "offline",
                        "error": "服务器未启用"
                    }
                
                # 合并配置信息和状态信息
                server_status = {
                    "name": server_name,
                    "enabled": enabled,
                    "type": server_config.get("type", "stdio"),
                    "status": status_info.get("status", "offline"),
                    "lastCheck": datetime.now().isoformat(),
                    "framework": status_info.get("framework", "langchain-mcp-adapters"),
                    "tools_count": status_info.get("tools_count", 0),
                    "errorMessage": status_info.get("error")
                }
                
                statuses.append(server_status)
            
            return statuses
            
        except Exception as e:
            logger.error(f"❌ [MCP服务] 获取服务器状态失败: {e}")
            return []
    
    @staticmethod
    async def get_server_status(server_name: str) -> Dict[str, Any]:
        """
        获取单个服务器状态
        
        Args:
            server_name: 服务器名称
            
        Returns:
            {"name": str, "status": str, ...}
        """
        try:
            status_info = await mcp_manager.get_server_status(server_name)
            
            return {
                "name": server_name,
                "status": status_info.get("status", "offline"),
                "lastCheck": datetime.now().isoformat(),
                "framework": status_info.get("framework", "langchain-mcp-adapters"),
                "tools_count": status_info.get("tools_count", 0),
                "errorMessage": status_info.get("error")
            }
            
        except Exception as e:
            logger.error(f"❌ [MCP服务] 获取服务器 {server_name} 状态失败: {e}")
            return {
                "name": server_name,
                "status": "offline",
                "errorMessage": str(e)
            }
    
    @staticmethod
    async def toggle_server(server_name: str, enabled: bool) -> Dict[str, Any]:
        """
        启用/禁用服务器
        
        Args:
            server_name: 服务器名称
            enabled: 是否启用
            
        Returns:
            {"success": bool, "message": str, "data": {...}}
        """
        try:
            # 读取配置
            config = await MCPService.get_config()
            mcp_servers = config.get("mcpServers", {})
            
            if server_name not in mcp_servers:
                return {
                    "success": False,
                    "message": f"服务器 {server_name} 不存在"
                }
            
            # 更新enabled状态
            mcp_servers[server_name]["enabled"] = enabled
            
            # 保存配置
            save_result = await MCPService.save_config(config)
            
            if not save_result.get("success"):
                return save_result
            
            # 获取更新后的状态
            status = await MCPService.get_server_status(server_name)
            
            return {
                "success": True,
                "message": f"服务器 {server_name} 已{'启用' if enabled else '禁用'}",
                "data": status
            }
            
        except Exception as e:
            logger.error(f"❌ [MCP服务] 切换服务器状态失败: {e}")
            return {
                "success": False,
                "message": f"操作失败: {str(e)}"
            }
    
    @staticmethod
    async def refresh_all_status() -> Dict[str, Any]:
        """
        刷新所有服务器状态
        
        Returns:
            {"success": bool, "message": str, "data": List[...]}
        """
        try:
            statuses = await MCPService.get_servers_status()
            
            return {
                "success": True,
                "message": "状态刷新成功",
                "data": statuses
            }
            
        except Exception as e:
            logger.error(f"❌ [MCP服务] 刷新状态失败: {e}")
            return {
                "success": False,
                "message": f"刷新失败: {str(e)}",
                "data": []
            }


# 导出
mcp_service = MCPService()

__all__ = ["MCPService", "mcp_service"]
