import json
import os
from fastapi import APIRouter, HTTPException, Depends, Body
from pydantic import BaseModel
from typing import Dict, Any, List, Optional
from app.routers.auth_db import get_current_user

router = APIRouter(prefix="/api/mcp", tags=["mcp"])
CONFIG_FILE = "mcp_servers.json"

class UpdatePayload(BaseModel):
    mcpServers: Dict[str, Any]

def _load_config() -> Dict[str, Any]:
    if not os.path.exists(CONFIG_FILE):
        return {}
    try:
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading MCP config: {e}")
        return {}

def _save_config(config: Dict[str, Any]):
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=2, ensure_ascii=False)

@router.get("/connectors")
async def list_connectors(user: dict = Depends(get_current_user)) -> Dict[str, Any]:
    full_config = _load_config()
    servers_config = full_config.get("mcpServers", {})
    
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
            "status": "healthy" # Mock status for now
        })
    
    return {"success": True, "data": data}

@router.post("/connectors/update")
async def update_connectors(
    payload: UpdatePayload,
    user: dict = Depends(get_current_user)
) -> Dict[str, Any]:
    current_config = _load_config()
    if "mcpServers" not in current_config:
        current_config["mcpServers"] = {}
        
    # Merge new servers
    for name, config in payload.mcpServers.items():
        # Preserve enabled state if exists in current config
        existing = current_config["mcpServers"].get(name, {})
        
        # New config should not overwrite _enabled unless we want to reset it?
        # Let's keep existing _enabled state
        if "_enabled" in existing:
            config["_enabled"] = existing["_enabled"]
        else:
            # New server defaults to enabled
            config["_enabled"] = True
            
        current_config["mcpServers"][name] = config
        
    _save_config(current_config)
    return {"success": True, "message": "Configuration updated"}

@router.patch("/connectors/{name}/toggle")
async def toggle_connector(
    name: str,
    body: Dict[str, bool] = Body(...),
    user: dict = Depends(get_current_user)
) -> Dict[str, Any]:
    config = _load_config()
    if "mcpServers" not in config or name not in config["mcpServers"]:
        raise HTTPException(status_code=404, detail="Server not found")
        
    config["mcpServers"][name]["_enabled"] = body.get("enabled", True)
    _save_config(config)
    return {"success": True, "data": {"enabled": config["mcpServers"][name]["_enabled"]}}

@router.delete("/connectors/{name}")
async def delete_connector(
    name: str,
    user: dict = Depends(get_current_user)
) -> Dict[str, Any]:
    config = _load_config()
    if "mcpServers" in config and name in config["mcpServers"]:
        del config["mcpServers"][name]
        _save_config(config)
        
    return {"success": True}
