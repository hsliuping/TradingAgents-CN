"""
MCP 服务器管理 API

允许用户配置自己的 MCP 服务器，系统将自动发现工具并注册到 ToolRegistry，
供 Skill 和 Agent 调用。

端点前缀: /api/mcp
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body, Depends, HTTPException
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel, Field

from app.core.database import get_mongo_db
from app.services.capability_index_service import CapabilityIndexService
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


class MCPProbeToolRequest(BaseModel):
    tool_name: str = Field(..., description="要探测的工具名称")
    arguments: Dict[str, Any] = Field(default_factory=dict, description="调用工具时传入的参数")


class AISuggestMappingRequest(BaseModel):
    tool_name: str = Field(..., description="MCP 工具名称")
    target_collection: str = Field("", description="目标 MongoDB 集合名（可为空）")


# =============================================================================
# 依赖
# =============================================================================


async def get_service(db: AsyncIOMotorDatabase = Depends(get_mongo_db)) -> MCPService:
    return MCPService(db)


async def _sync_capability_index(db: AsyncIOMotorDatabase):
    try:
        await CapabilityIndexService(db).ensure_index()
    except Exception as e:
        logger.warning(f"⚠️ CapabilityIndex 同步失败: {e}")


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
    db: AsyncIOMotorDatabase = Depends(get_mongo_db),
):
    """添加一个新的 MCP 服务器配置"""
    data = body.model_dump()
    # 将嵌套模型转为 dict
    data["connection"] = body.connection.model_dump(exclude_none=True)
    doc = await svc.create_server(data)
    await _sync_capability_index(db)
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
    db: AsyncIOMotorDatabase = Depends(get_mongo_db),
):
    data = body.model_dump(exclude_none=True)
    if "connection" in data:
        data["connection"] = body.connection.model_dump(exclude_none=True)
    doc = await svc.update_server(server_id, data)
    if doc is None:
        raise HTTPException(status_code=404, detail=f"MCP 服务器不存在: {server_id}")
    await _sync_capability_index(db)
    return {"server": doc}


@router.delete("/servers/{server_id}", summary="删除 MCP 服务器配置")
async def delete_mcp_server(
    server_id: str,
    svc: MCPService = Depends(get_service),
    db: AsyncIOMotorDatabase = Depends(get_mongo_db),
):
    ok = await svc.delete_server(server_id)
    if not ok:
        raise HTTPException(status_code=404, detail=f"MCP 服务器不存在: {server_id}")
    await _sync_capability_index(db)
    return {"success": True, "message": f"已删除 MCP 服务器: {server_id}"}


@router.post("/servers/{server_id}/test", summary="测试 MCP 服务器连接")
async def test_mcp_connection(server_id: str, svc: MCPService = Depends(get_service)):
    """测试与 MCP 服务器的连通性，并更新 status 字段"""
    result = await svc.test_connection(server_id)
    return result


@router.post("/servers/{server_id}/discover", summary="发现并同步 MCP 工具")
async def discover_mcp_tools(
    server_id: str,
    svc: MCPService = Depends(get_service),
    db: AsyncIOMotorDatabase = Depends(get_mongo_db),
):
    """
    连接 MCP 服务器，获取工具列表并缓存到数据库。
    若服务器已启用，工具将同步注册到 ToolRegistry。
    """
    result = await svc.discover_tools(server_id)
    if not result["success"]:
        raise HTTPException(status_code=502, detail=result.get("error", "工具发现失败"))
    await _sync_capability_index(db)
    return result


@router.post("/servers/{server_id}/toggle", summary="启用或禁用 MCP 服务器")
async def toggle_mcp_server(
    server_id: str,
    body: MCPToggleRequest,
    svc: MCPService = Depends(get_service),
    db: AsyncIOMotorDatabase = Depends(get_mongo_db),
):
    """
    启用服务器时，已发现的工具会注册到 ToolRegistry；
    禁用时，工具从 ToolRegistry 注销。
    """
    doc = await svc.toggle_server(server_id, body.enabled)
    if doc is None:
        raise HTTPException(status_code=404, detail=f"MCP 服务器不存在: {server_id}")
    action = "启用" if body.enabled else "禁用"
    await _sync_capability_index(db)
    return {"server": doc, "message": f"已{action} MCP 服务器: {server_id}"}


@router.get("/servers/{server_id}/tools-list", summary="获取服务器已发现工具列表")
async def list_server_tools(server_id: str, svc: MCPService = Depends(get_service)):
    """返回服务器的 discovered_tools（从数据库缓存读取，不重新连接服务器）"""
    tools = await svc.list_server_tools(server_id)
    return {"tools": tools, "total": len(tools)}


@router.post("/servers/{server_id}/probe-tool", summary="探测工具输出字段")
async def probe_mcp_tool(
    server_id: str,
    body: MCPProbeToolRequest,
    svc: MCPService = Depends(get_service),
):
    """调用指定工具，返回原始结果及自动提取的输出字段列表"""
    result = await svc.probe_tool(server_id, body.tool_name, body.arguments)
    if not result["success"]:
        raise HTTPException(status_code=502, detail=result.get("error", "探测失败"))
    return result


@router.post("/servers/{server_id}/ai-suggest-mapping", summary="AI 智能字段映射建议")
async def ai_suggest_mapping(
    server_id: str,
    body: AISuggestMappingRequest,
    svc: MCPService = Depends(get_service),
):
    """使用 LLM 自动探测 MCP 工具输出字段并与目标 MongoDB 集合字段对比，生成字段映射建议"""
    result = await svc.ai_suggest_mapping(server_id, body.tool_name, body.target_collection)
    if not result["success"]:
        raise HTTPException(status_code=502, detail=result.get("error", "AI 推断失败"))
    return result


@router.get("/collections", summary="列出 MongoDB 数据库中的所有集合名称")
async def list_mongo_collections(db: AsyncIOMotorDatabase = Depends(get_mongo_db)):
    """返回当前数据库中所有集合的名称列表（过滤系统集合），供目标集合下拉选择使用"""
    try:
        names: List[str] = await db.list_collection_names()
        names = sorted(n for n in names if not n.startswith("system."))
        return {"collections": names, "total": len(names)}
    except Exception as e:
        logger.warning(f"获取集合列表失败: {e}")
        return {"collections": [], "total": 0}


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


@router.get("/audit-logs", summary="查询 MCP 审计日志")
async def get_audit_logs(
    server_name: Optional[str] = None,
    tool_name: Optional[str] = None,
    category: Optional[str] = None,
    user_id: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
):
    """查询 MCP 工具调用审计日志"""
    db = get_mongo_db()
    query = {}
    if server_name:
        query["server_name"] = server_name
    if tool_name:
        query["tool_name"] = tool_name
    if category:
        query["category"] = category
    if user_id:
        query["user_id"] = user_id

    total = await db.mcp_audit_logs.count_documents(query)
    cursor = db.mcp_audit_logs.find(query).sort("created_at", -1).skip(offset).limit(limit)
    logs = []
    async for doc in cursor:
        doc["_id"] = str(doc["_id"])
        if "created_at" in doc and doc["created_at"]:
            doc["created_at"] = str(doc["created_at"])
        logs.append(doc)

    return {"logs": logs, "total": total, "limit": limit, "offset": offset}


# =============================================================================
# 凭证保险箱 — 加密存储 MCP Server 所需的 API Key
# =============================================================================

import hashlib
import base64
import os


CREDENTIALS_COLLECTION = "mcp_credentials"


def _get_encryption_key() -> bytes:
    """获取加密密钥（基于 JWT_SECRET 或固定 fallback）"""
    secret = os.getenv("JWT_SECRET", "trading-agents-default-secret")
    return hashlib.sha256(secret.encode()).digest()


def _get_fernet() -> "Fernet":
    """获取 Fernet 实例（AES-128-CBC + HMAC-SHA256）"""
    from cryptography.fernet import Fernet
    # Fernet 密钥需要 urlsafe base64 编码的 32 字节
    key = base64.urlsafe_b64encode(_get_encryption_key())
    return Fernet(key)


def _encrypt_value(plain: str) -> str:
    """加密凭证（使用 Fernet，AES-128-CBC + HMAC）

    输出格式：v2:<fernet_token>
    加 v2: 前缀便于解密时区分新旧格式。
    """
    f = _get_fernet()
    token = f.encrypt(plain.encode("utf-8")).decode("ascii")
    return f"v2:{token}"


def _decrypt_value(cipher: str) -> str:
    """解密凭证

    支持两种格式：
    - v2:<fernet_token>：新格式，Fernet 解密
    - <base64>：旧格式，XOR + base64 解密（向后兼容）
    """
    if cipher.startswith("v2:"):
        # 新格式：Fernet 解密
        f = _get_fernet()
        token = cipher[3:].encode("ascii")
        return f.decrypt(token).decode("utf-8")
    else:
        # 旧格式：XOR + base64 解密（向后兼容已存的凭证）
        key = _get_encryption_key()
        data = base64.b64decode(cipher)
        decrypted = bytes(b ^ key[i % len(key)] for i, b in enumerate(data))
        return decrypted.decode("utf-8")


def _mask_value(value: str) -> str:
    """遮蔽显示：只显示前4位和后4位"""
    if len(value) <= 8:
        return "****"
    return value[:4] + "****" + value[-4:]


class CredentialCreateRequest(BaseModel):
    """创建凭证请求"""
    name: str = Field(..., description="凭证名称，如 Tushare API Key")
    key_name: str = Field(..., description="环境变量名或 Header 名，如 TUSHARE_TOKEN")
    key_value: str = Field(..., description="密钥值（将被加密存储）")
    server_id: Optional[str] = Field(None, description="关联的 MCP Server ID")
    description: str = Field("", description="说明")


class CredentialResponse(BaseModel):
    """凭证响应（密钥遮蔽显示）"""
    id: str
    name: str
    key_name: str
    key_value_masked: str
    server_id: Optional[str] = None
    description: str
    created_at: str = ""
    updated_at: str = ""


class CredentialTestRequest(BaseModel):
    """测试凭证请求"""
    credential_id: str = Field(..., description="凭证 ID")
    test_url: str = Field("", description="测试 URL（可选）")


@router.post("/credentials", response_model=CredentialResponse)
async def create_credential(
    req: CredentialCreateRequest,
    db: AsyncIOMotorDatabase = Depends(get_mongo_db),
):
    """创建凭证（加密存储 API Key）"""
    encrypted = _encrypt_value(req.key_value)
    doc = {
        "name": req.name,
        "key_name": req.key_name,
        "key_value_encrypted": encrypted,
        "server_id": req.server_id,
        "description": req.description,
        "created_at": datetime.utcnow().isoformat(),
        "updated_at": datetime.utcnow().isoformat(),
    }
    result = await db[CREDENTIALS_COLLECTION].insert_one(doc)
    doc["_id"] = str(result.inserted_id)

    return CredentialResponse(
        id=doc["_id"],
        name=doc["name"],
        key_name=doc["key_name"],
        key_value_masked=_mask_value(req.key_value),
        server_id=doc.get("server_id"),
        description=doc.get("description", ""),
        created_at=doc.get("created_at", ""),
        updated_at=doc.get("updated_at", ""),
    )


@router.get("/credentials", response_model=List[CredentialResponse])
async def list_credentials(
    db: AsyncIOMotorDatabase = Depends(get_mongo_db),
):
    """列出所有凭证（密钥遮蔽显示）"""
    docs = await db[CREDENTIALS_COLLECTION].find().to_list(100)
    result = []
    for doc in docs:
        doc["_id"] = str(doc["_id"])
        # 解密后遮蔽，确保显示的是真实密钥的前后 4 位
        try:
            key_value = _decrypt_value(doc.get("key_value_encrypted", ""))
            masked = _mask_value(key_value)
        except Exception:
            masked = "****"
        result.append(CredentialResponse(
            id=doc["_id"],
            name=doc.get("name", ""),
            key_name=doc.get("key_name", ""),
            key_value_masked=masked,
            server_id=doc.get("server_id"),
            description=doc.get("description", ""),
            created_at=doc.get("created_at", ""),
            updated_at=doc.get("updated_at", ""),
        ))
    return result


@router.delete("/credentials/{credential_id}")
async def delete_credential(
    credential_id: str,
    db: AsyncIOMotorDatabase = Depends(get_mongo_db),
):
    """删除凭证"""
    from bson import ObjectId
    try:
        await db[CREDENTIALS_COLLECTION].delete_one({"_id": ObjectId(credential_id)})
    except Exception:
        raise HTTPException(status_code=400, detail="无效的凭证 ID")
    return {"message": "已删除"}


@router.post("/credentials/{credential_id}/apply/{server_id}")
async def apply_credential_to_server(
    credential_id: str,
    server_id: str,
    db: AsyncIOMotorDatabase = Depends(get_mongo_db),
):
    """将凭证应用到 MCP Server（自动填入 connection.env 或 connection.headers）"""
    from bson import ObjectId

    # 获取凭证
    cred_doc = await db[CREDENTIALS_COLLECTION].find_one({"_id": ObjectId(credential_id)})
    if not cred_doc:
        raise HTTPException(status_code=404, detail="凭证不存在")

    # 解密
    key_value = _decrypt_value(cred_doc["key_value_encrypted"])
    key_name = cred_doc["key_name"]

    # 获取 MCP Server
    server_doc = await db["mcp_server_configs"].find_one({"server_id": server_id})
    if not server_doc:
        raise HTTPException(status_code=404, detail="MCP Server 不存在")

    # 根据传输类型决定放在 env 还是 headers
    connection = server_doc.get("connection", {})
    transport_type = server_doc.get("transport_type", "stdio")

    if transport_type == "stdio":
        env = connection.get("env") or {}
        env[key_name] = key_value
        connection["env"] = env
    else:
        headers = connection.get("headers") or {}
        headers[key_name] = key_value
        connection["headers"] = headers

    await db["mcp_server_configs"].update_one(
        {"server_id": server_id},
        {"$set": {"connection": connection, "updated_at": datetime.utcnow().isoformat()}}
    )

    return {"message": f"已将凭证 {cred_doc['name']} 应用到 MCP Server {server_id}"}

