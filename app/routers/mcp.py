import asyncio
import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body, Depends, HTTPException
from pydantic import BaseModel, Field

from app.routers.auth_db import get_current_user
from tradingagents.tools.mcp import LANGCHAIN_MCP_AVAILABLE, get_mcp_loader_factory
from tradingagents.tools.mcp.config_utils import (
    MCPServerConfig,
    MCPServerType,
    HealthCheckConfig,
    get_config_path,
    load_mcp_config,
    merge_servers,
    write_mcp_config,
)
from tradingagents.tools.mcp.health_monitor import ServerStatus

router = APIRouter(prefix="/api/mcp", tags=["mcp"])
CONFIG_FILE = get_config_path()
logger = logging.getLogger("app.routers.mcp")

class UpdatePayload(BaseModel):
    mcpServers: Dict[str, MCPServerConfig] = Field(default_factory=dict)


class ServerConfigInput(BaseModel):
    """服务器配置输入模型"""
    type: str = Field(default="stdio", description="服务器类型: stdio 或 http")
    command: Optional[str] = Field(default=None, description="stdio 模式的命令")
    args: List[str] = Field(default_factory=list, description="命令参数")
    env: Dict[str, str] = Field(default_factory=dict, description="环境变量")
    url: Optional[str] = Field(default=None, description="HTTP 模式的 URL")
    headers: Dict[str, str] = Field(default_factory=dict, description="HTTP 请求头")
    description: Optional[str] = Field(default=None, description="服务器描述")
    healthCheck: Optional[Dict[str, Any]] = Field(default=None, description="健康检查配置")

@router.get("/connectors")
async def list_connectors(user: dict = Depends(get_current_user)) -> Dict[str, Any]:
    """
    列出所有 MCP 连接器，包含健康状态和服务器类型信息
    """
    full_config = load_mcp_config(CONFIG_FILE)
    servers_config = full_config.get("mcpServers", {})

    # 获取服务器健康状态
    server_status_map: Dict[str, str] = {}
    if LANGCHAIN_MCP_AVAILABLE and servers_config:
        try:
            factory = get_mcp_loader_factory()
            # 确保 MCP 连接已初始化，这样才能获取正确的健康状态
            if not factory._initialized:
                await factory.initialize_connections()
            all_status = factory.get_all_server_status()
            server_status_map = {name: info.get("status", "unknown") for name, info in all_status.items()}
        except Exception as exc:  # pragma: no cover - 运行时保护
            logger.warning("获取 MCP 健康状态失败: %s", exc)

    data = []
    for name, config in servers_config.items():
        # Check if enabled, default to True if not specified
        enabled = config.get("_enabled", True)
        server_type = config.get("type", "stdio")
        
        # Create a clean config copy for display
        display_config = config.copy()
        if "_enabled" in display_config:
            del display_config["_enabled"]

        # 确定状态
        if not enabled:
            status = "stopped"
        elif not LANGCHAIN_MCP_AVAILABLE:
            status = "unavailable"
        else:
            status = server_status_map.get(name, "unknown")

        # 获取健康检查信息
        health_info = None
        if name in server_status_map:
            try:
                factory = get_mcp_loader_factory()
                health_data = factory._health_monitor.get_server_health_info(name)
                if health_data:
                    health_info = health_data.to_dict()
            except Exception:
                pass

        data.append({
            "id": name,
            "name": name,
            "type": server_type,
            "config": display_config,
            "enabled": enabled,
            "status": status,
            "healthInfo": health_info,
        })
    
    return {"success": True, "data": data}

@router.post("/connectors/update")
async def update_connectors(
    payload: UpdatePayload,
    user: dict = Depends(get_current_user)
) -> Dict[str, Any]:
    current_config = load_mcp_config(CONFIG_FILE)
    incoming = {name: cfg.sanitized() for name, cfg in payload.mcpServers.items()}
    merged = merge_servers(current_config.get("mcpServers", {}), incoming, strict=True)
    write_mcp_config({"mcpServers": merged}, CONFIG_FILE)
    return {"success": True, "message": "Configuration updated"}

@router.patch("/connectors/{name}/toggle")
async def toggle_connector(
    name: str,
    body: Dict[str, bool] = Body(...),
    user: dict = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    切换 MCP 连接器的启用状态
    
    启用时会启动服务器进程（stdio）或建立连接（HTTP）
    禁用时会停止进程或断开连接
    """
    config = load_mcp_config(CONFIG_FILE)
    if "mcpServers" not in config or name not in config["mcpServers"]:
        raise HTTPException(status_code=404, detail="Server not found")
    
    enabled = body.get("enabled", True)
    
    try:
        # 更新配置文件
        config["mcpServers"][name]["_enabled"] = enabled
        write_mcp_config(config, CONFIG_FILE)
        
        # 通知加载器切换服务器状态
        if LANGCHAIN_MCP_AVAILABLE:
            factory = get_mcp_loader_factory()
            factory.toggle_server(name, enabled)
        
        return {
            "success": True, 
            "data": {
                "enabled": enabled,
                "status": "healthy" if enabled else "stopped"
            }
        }
    except Exception as e:
        logger.error(f"切换服务器 {name} 状态失败: {e}")
        raise HTTPException(status_code=500, detail=f"Toggle failed: {str(e)}")

@router.delete("/connectors/{name}")
async def delete_connector(
    name: str,
    user: dict = Depends(get_current_user)
) -> Dict[str, Any]:
    config = load_mcp_config(CONFIG_FILE)
    if "mcpServers" in config and name in config["mcpServers"]:
        del config["mcpServers"][name]
        write_mcp_config(config, CONFIG_FILE)
        
    return {"success": True}

@router.get("/tools")
async def list_all_mcp_tools(user: dict = Depends(get_current_user)) -> Dict[str, Any]:
    """
    列出所有已启用 MCP 服务器的可用工具
    
    返回的工具列表包含：
    - 工具名称、描述和输入模式
    - 所属服务器名称和 ID
    - 服务器健康状态
    - 工具是否可用
    """
    if not LANGCHAIN_MCP_AVAILABLE:
        return {"success": False, "message": "langchain-mcp 未安装", "data": []}

    if not CONFIG_FILE.exists():
        return {"success": True, "message": "未找到 MCP 配置文件", "data": []}

    factory = get_mcp_loader_factory()
    
    # 确保 MCP 连接已初始化
    if not factory._initialized:
        await factory.initialize_connections()

    try:
        tools = await asyncio.to_thread(factory.list_available_tools)
        
        # 按服务器分组统计
        server_stats: Dict[str, Dict[str, Any]] = {}
        for tool in tools:
            server_name = tool.get("serverName", "unknown")
            if server_name not in server_stats:
                server_stats[server_name] = {
                    "total": 0,
                    "available": 0,
                    "status": tool.get("status", "unknown")
                }
            server_stats[server_name]["total"] += 1
            if tool.get("available", True):
                server_stats[server_name]["available"] += 1
        
        return {
            "success": True, 
            "data": tools,
            "serverStats": server_stats,
        }
    except Exception as exc:
        logger.error(f"获取 MCP 工具列表失败: {exc}")
        return {"success": False, "message": str(exc), "data": []}


@router.get("/health")
async def get_health_status(user: dict = Depends(get_current_user)) -> Dict[str, Any]:
    """
    获取所有 MCP 服务器的健康状态
    """
    if not LANGCHAIN_MCP_AVAILABLE:
        return {"success": False, "message": "langchain-mcp 未安装", "data": {}}
    
    try:
        factory = get_mcp_loader_factory()
        # 确保 MCP 连接已初始化
        if not factory._initialized:
            await factory.initialize_connections()
        all_status = factory.get_all_server_status()
        return {"success": True, "data": all_status}
    except Exception as exc:
        logger.error(f"获取健康状态失败: {exc}")
        return {"success": False, "message": str(exc), "data": {}}
