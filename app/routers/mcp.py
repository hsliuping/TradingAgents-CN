import asyncio
import logging
from typing import Any, Dict, List

from fastapi import APIRouter, Body, Depends, HTTPException
from pydantic import BaseModel, Field

from app.routers.auth_db import get_current_user
from tradingagents.tools.mcp import LANGCHAIN_MCP_AVAILABLE, get_mcp_loader_factory
from tradingagents.tools.mcp.config_utils import (
    MCPServerConfig,
    get_config_path,
    load_mcp_config,
    merge_servers,
    write_mcp_config,
)

router = APIRouter(prefix="/api/mcp", tags=["mcp"])
CONFIG_FILE = get_config_path()
logger = logging.getLogger("app.routers.mcp")

class UpdatePayload(BaseModel):
    mcpServers: Dict[str, MCPServerConfig] = Field(default_factory=dict)

@router.get("/connectors")
async def list_connectors(user: dict = Depends(get_current_user)) -> Dict[str, Any]:
    full_config = load_mcp_config(CONFIG_FILE)
    servers_config = full_config.get("mcpServers", {})

    reachable_servers = set()
    if LANGCHAIN_MCP_AVAILABLE and servers_config:
        try:
            factory = get_mcp_loader_factory()
            tools_meta = await asyncio.to_thread(factory.list_available_tools)
            reachable_servers = {item.get("serverId") for item in tools_meta if item.get("serverId")}
        except Exception as exc:  # pragma: no cover - 运行时保护
            logger.warning("获取 MCP 健康状态失败: %s", exc)

    data = []
    for name, config in servers_config.items():
        # Check if enabled, default to True if not specified
        enabled = config.get("_enabled", True)
        
        # Create a clean config copy for display
        display_config = config.copy()
        if "_enabled" in display_config:
            del display_config["_enabled"]

        data.append({
            "id": name,
            "name": name,
            "config": display_config,
            "enabled": enabled,
            "status": (
                "disabled"
                if not enabled
                else ("unavailable" if not LANGCHAIN_MCP_AVAILABLE else ("healthy" if name in reachable_servers else "unknown"))
            ),
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
    config = load_mcp_config(CONFIG_FILE)
    if "mcpServers" not in config or name not in config["mcpServers"]:
        raise HTTPException(status_code=404, detail="Server not found")
        
    config["mcpServers"][name]["_enabled"] = body.get("enabled", True)
    write_mcp_config(config, CONFIG_FILE)
    return {"success": True, "data": {"enabled": config["mcpServers"][name]["_enabled"]}}

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
    列出所有已启用MCP服务器的可用工具
    """
    if not LANGCHAIN_MCP_AVAILABLE:
        return {"success": False, "message": "langchain-mcp 未安装", "data": []}

    if not CONFIG_FILE.exists():
        return {"success": True, "message": "未找到 MCP 配置文件", "data": []}

    factory = get_mcp_loader_factory()

    try:
        tools = await asyncio.to_thread(factory.list_available_tools)
        return {"success": True, "data": tools}
    except Exception as exc:
        logger.error(f"获取 MCP 工具列表失败: {exc}")
        return {"success": False, "message": str(exc), "data": []}
