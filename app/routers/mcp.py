"""
MCP 服务器管理 API

允许用户配置自己的 MCP 服务器，系统将自动发现工具并注册到 ToolRegistry，
供 Skill 和 Agent 调用。

端点前缀: /api/mcp
"""

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body, Depends, HTTPException
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel, Field

from app.core.database import get_mongo_db
from app.services.mcp_service import MCPService

logger = logging.getLogger("webapi")

router = APIRouter(prefix="/api/mcp", tags=["mcp"])


# =============================================================================
# 请求 / 响应模型
# =============================================================================


class MCPConnectionConfig(BaseModel):
    """连接参数（SSE/HTTP 用 url；stdio 用 command+args）"""

    url: Optional[str] = Field(None, description="SSE / Streamable HTTP 服务器地址")
    headers: Optional[Dict[str, str]] = Field(default_factory=dict, description="HTTP 请求头")
    command: Optional[str] = Field(None, description="stdio 模式：可执行命令")
    args: Optional[List[str]] = Field(default_factory=list, description="stdio 模式：命令参数")
    env: Optional[Dict[str, str]] = Field(None, description="stdio 模式：环境变量")


class MCPServerCreateRequest(BaseModel):
    """创建 MCP 服务器请求"""

    server_id: Optional[str] = Field(None, description="可选，留空自动生成")
    name: str = Field(..., description="显示名称")
    description: str = Field("", description="描述")
    transport_type: str = Field("sse", description="传输类型: sse | streamable_http | stdio")
    connection: MCPConnectionConfig = Field(..., description="连接参数")
    is_enabled: bool = Field(False, description="创建后立即启用")
    category: str = Field("function", description="服务器分类: datasource | function")
    data_mappings: List[Dict[str, Any]] = Field(default_factory=list, description="数据源类字段映射配置")


class MCPServerUpdateRequest(BaseModel):
    """更新 MCP 服务器请求"""

    name: Optional[str] = None
    description: Optional[str] = None
    transport_type: Optional[str] = None
    connection: Optional[MCPConnectionConfig] = None
    is_enabled: Optional[bool] = None
    category: Optional[str] = None
    data_mappings: Optional[List[Dict[str, Any]]] = None


class MCPToggleRequest(BaseModel):
    enabled: bool


# =============================================================================
# 依赖
# =============================================================================


async def get_service(db: AsyncIOMotorDatabase = Depends(get_mongo_db)) -> MCPService:
    return MCPService(db)


# =============================================================================
# 端点
# =============================================================================


@router.get("/servers", summary="列出所有 MCP 服务器")
async def list_mcp_servers(svc: MCPService = Depends(get_service)):
    """返回用户配置的所有 MCP 服务器列表"""
    servers = await svc.list_servers()
    return {"servers": servers, "total": len(servers)}


@router.post("/servers", summary="创建 MCP 服务器配置")
async def create_mcp_server(
    body: MCPServerCreateRequest,
    svc: MCPService = Depends(get_service),
):
    """添加一个新的 MCP 服务器配置"""
    data = body.model_dump()
    # 将嵌套模型转为 dict
    data["connection"] = body.connection.model_dump(exclude_none=True)
    doc = await svc.create_server(data)
    return {"server": doc}


@router.get("/servers/{server_id}", summary="获取单个 MCP 服务器")
async def get_mcp_server(server_id: str, svc: MCPService = Depends(get_service)):
    doc = await svc.get_server(server_id)
    if doc is None:
        raise HTTPException(status_code=404, detail=f"MCP 服务器不存在: {server_id}")
    return {"server": doc}


@router.put("/servers/{server_id}", summary="更新 MCP 服务器配置")
async def update_mcp_server(
    server_id: str,
    body: MCPServerUpdateRequest,
    svc: MCPService = Depends(get_service),
):
    data = body.model_dump(exclude_none=True)
    if "connection" in data:
        data["connection"] = body.connection.model_dump(exclude_none=True)
    doc = await svc.update_server(server_id, data)
    if doc is None:
        raise HTTPException(status_code=404, detail=f"MCP 服务器不存在: {server_id}")
    return {"server": doc}


@router.delete("/servers/{server_id}", summary="删除 MCP 服务器配置")
async def delete_mcp_server(server_id: str, svc: MCPService = Depends(get_service)):
    ok = await svc.delete_server(server_id)
    if not ok:
        raise HTTPException(status_code=404, detail=f"MCP 服务器不存在: {server_id}")
    return {"success": True, "message": f"已删除 MCP 服务器: {server_id}"}


@router.post("/servers/{server_id}/test", summary="测试 MCP 服务器连接")
async def test_mcp_connection(server_id: str, svc: MCPService = Depends(get_service)):
    """测试与 MCP 服务器的连通性，并更新 status 字段"""
    result = await svc.test_connection(server_id)
    return result


@router.post("/servers/{server_id}/discover", summary="发现并同步 MCP 工具")
async def discover_mcp_tools(server_id: str, svc: MCPService = Depends(get_service)):
    """
    连接 MCP 服务器，获取工具列表并缓存到数据库。
    若服务器已启用，工具将同步注册到 ToolRegistry。
    """
    result = await svc.discover_tools(server_id)
    if not result["success"]:
        raise HTTPException(status_code=502, detail=result.get("error", "工具发现失败"))
    return result


@router.post("/servers/{server_id}/toggle", summary="启用或禁用 MCP 服务器")
async def toggle_mcp_server(
    server_id: str,
    body: MCPToggleRequest,
    svc: MCPService = Depends(get_service),
):
    """
    启用服务器时，已发现的工具会注册到 ToolRegistry；
    禁用时，工具从 ToolRegistry 注销。
    """
    doc = await svc.toggle_server(server_id, body.enabled)
    if doc is None:
        raise HTTPException(status_code=404, detail=f"MCP 服务器不存在: {server_id}")
    action = "启用" if body.enabled else "禁用"
    return {"server": doc, "message": f"已{action} MCP 服务器: {server_id}"}


@router.get("/tools", summary="列出所有已注册的 MCP 工具")
async def list_mcp_tools():
    """返回当前注册到 ToolRegistry 的所有 MCP 工具"""
    from core.tools.registry import get_tool_registry

    registry = get_tool_registry()
    mcp_tools = [t for t in registry.list_all() if t.category == "mcp"]
    return {
        "tools": [
            {"tool_id": t.id, "name": t.name, "description": t.description}
            for t in mcp_tools
        ],
        "total": len(mcp_tools),
    }

