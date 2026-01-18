"""
智能体 API 路由

提供智能体的查询和管理端点
"""

from fastapi import APIRouter, HTTPException, Depends, Header
from pydantic import BaseModel
from typing import Any, Dict, List, Optional
import logging

from app.core.response import ok, fail
from app.routers.auth_db import get_current_user
from app.core.database import get_mongo_db
from core.agents.config import BUILTIN_AGENTS
from core.tools import get_tool_registry
from motor.motor_asyncio import AsyncIOMotorDatabase

# ==================== 数据模型 ====================

class ToolResponse(BaseModel):
    """工具响应模型 (简版)"""
    id: str
    name: str
    description: str
    category: str
    data_source: str
    is_online: bool
    timeout: int
    rate_limit: Optional[int]
    icon: str
    color: str
    parameters: list

class AgentToolsResponse(BaseModel):
    """Agent 工具配置响应"""
    agent_id: str
    agent_name: str
    tools: List[str]
    default_tools: List[str]
    max_tool_calls: int
    available_tools: List[ToolResponse]


class AgentToolsUpdate(BaseModel):
    """Agent 工具配置更新"""
    tools: List[str]
    default_tools: Optional[List[str]] = None
    max_tool_calls: Optional[int] = None


class AgentMetadata(BaseModel):
    """智能体元数据"""
    id: str
    name: str
    description: str
    category: str
    license_tier: str
    inputs: List[str] = []
    outputs: List[str] = []
    icon: str = "📦"
    color: str = "#409EFF"
    tags: List[str] = []
    is_available: Optional[bool] = None
    is_implemented: Optional[bool] = None
    locked_reason: Optional[str] = None


class AgentCategory(BaseModel):
    """智能体类别"""
    id: str
    name: str
    count: int


from app.services.license_service import get_license_service

logger = logging.getLogger("webapi")

router = APIRouter(prefix="/api/agents", tags=["agents"])

# ==================== 辅助函数 ====================

async def _get_tool_overrides(db: AsyncIOMotorDatabase) -> Dict[str, Dict[str, Any]]:
    """获取所有工具的覆盖配置"""
    cursor = db.tool_configs.find({})
    overrides = {}
    async for doc in cursor:
        overrides[doc["tool_id"]] = doc
    return overrides

async def get_user_license_tier(
    user: dict = Depends(get_current_user),
    x_app_token: Optional[str] = Header(None, alias="X-App-Token")
) -> str:
    """
    获取当前用户的许可证级别

    优先使用远程验证的结果，如果没有 app-token 则默认为 free
    
    注意：设备ID由后端基于硬件信息自动生成，用户无法获取或复制
    """
    logger.info(f"🔍 检查用户许可证: user_id={user.get('id')}, has_x_app_token={bool(x_app_token)}")

    if not x_app_token:
        logger.info(f"📝 用户 {user.get('id')} 没有 X-App-Token，返回 free")
        return "free"

    try:
        license_service = get_license_service()
        license_info = await license_service.verify_app_token(x_app_token)
        logger.info(f"🎫 许可证验证结果: plan={license_info.plan}, is_valid={license_info.is_valid}")

        if license_info.is_valid:
            # 将 license plan 映射到 tier
            plan_to_tier = {
                "free": "free",
                "trial": "pro",  # 试用版也算 pro
                "pro": "pro",
                "enterprise": "enterprise"
            }
            tier = plan_to_tier.get(license_info.plan, "free")
            logger.info(f"✅ 用户 {user.get('id')} 许可证级别: {tier}")
            return tier
    except Exception as e:
        logger.warning(f"获取用户许可证失败: {e}")

    logger.info(f"❌ 用户 {user.get('id')} 许可证验证失败，返回 free")
    return "free"


# ==================== API 端点 ====================

@router.get("")
async def list_all_agents():
    """获取所有智能体"""
    try:
        from core.api import AgentAPI
        api = AgentAPI()
        agents = api.list_all()
        return ok(agents)
    except Exception as e:
        logger.error(f"获取智能体列表失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/available")
async def list_available_agents(
    user_tier: str = Depends(get_user_license_tier)
):
    """获取当前许可证可用的智能体"""
    try:
        from core.api import AgentAPI
        api = AgentAPI()
        agents = api.list_available_for_tier(user_tier)
        return ok(agents)
    except Exception as e:
        logger.error(f"获取可用智能体失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{agent_id}/tools")
async def update_agent_tools(
    agent_id: str,
    config: AgentToolsUpdate,
    db: AsyncIOMotorDatabase = Depends(get_mongo_db),
):
    """更新 Agent 的工具配置"""
    # 先从 BUILTIN_AGENTS 查找
    agent = BUILTIN_AGENTS.get(agent_id)

    # 如果不在 BUILTIN_AGENTS 中，从注册表查找
    if not agent:
        from core.agents import get_registry
        agent_registry = get_registry()
        agent = agent_registry.get_metadata(agent_id)

        if not agent:
            raise HTTPException(status_code=404, detail=f"Agent {agent_id} 不存在")

    # 验证所有工具ID是否存在
    registry = get_tool_registry()
    for tool_id in config.tools:
        if not registry.get(tool_id):
            raise HTTPException(status_code=400, detail=f"工具 {tool_id} 不存在")

    # 使用 v2.0 架构：保存到 tool_agent_bindings 集合
    from datetime import datetime

    # 1. 先删除该 agent 的所有现有绑定
    await db.tool_agent_bindings.delete_many({"agent_id": agent_id})

    # 2. 插入新的工具绑定
    if config.tools:
        bindings = []
        for i, tool_id in enumerate(config.tools):
            binding = {
                "agent_id": agent_id,
                "tool_id": tool_id,
                "priority": i + 1,  # 按顺序设置优先级
                "is_active": True,
                "created_at": datetime.utcnow().isoformat(),
                "updated_at": datetime.utcnow().isoformat(),
            }
            bindings.append(binding)

        await db.tool_agent_bindings.insert_many(bindings)

    # 3. 同时更新 agent_configs 以保持兼容性（可选）
    update_data = {
        "tools": config.tools,
        "updated_at": datetime.utcnow().isoformat(),
    }
    if config.default_tools is not None:
        update_data["default_tools"] = config.default_tools
    if config.max_tool_calls is not None:
        update_data["max_tool_calls"] = config.max_tool_calls

    await db.agent_configs.update_one(
        {"agent_id": agent_id},
        {"$set": update_data},
        upsert=True
    )

    return {"success": True, "message": "Agent 工具配置已更新"}


@router.get("/{agent_id}/tools", response_model=AgentToolsResponse)
async def get_agent_tools(
    agent_id: str,
    db: AsyncIOMotorDatabase = Depends(get_mongo_db),
):
    """获取指定 Agent 的工具配置"""
    # 先从 BUILTIN_AGENTS 查找
    agent = BUILTIN_AGENTS.get(agent_id)

    # 如果不在 BUILTIN_AGENTS 中，从注册表查找
    if not agent:
        from core.agents import get_registry
        agent_registry = get_registry()
        agent = agent_registry.get_metadata(agent_id)

        if not agent:
            raise HTTPException(status_code=404, detail=f"Agent {agent_id} 不存在")

    # 优先从 tool_agent_bindings 集合获取工具配置（v2.0 架构）
    bindings = await db.tool_agent_bindings.find(
        {"agent_id": agent_id, "is_active": {"$ne": False}},
        sort=[("priority", 1)]
    ).to_list(length=None)

    if bindings:
        # 从绑定中提取工具列表
        current_tools = [b["tool_id"] for b in bindings]
        current_default_tools = current_tools  # 绑定的工具即为默认工具
    else:
        # 降级：从 agent_configs 集合获取（兼容旧版）
        agent_override = await db.agent_configs.find_one({"agent_id": agent_id}) or {}
        current_tools = agent_override.get("tools", agent.tools or [])
        current_default_tools = agent_override.get("default_tools", agent.default_tools or [])

    # max_tool_calls 仍从 agent_configs 获取
    agent_override = await db.agent_configs.find_one({"agent_id": agent_id}) or {}
    current_max_tool_calls = agent_override.get("max_tool_calls", getattr(agent, "max_tool_calls", 3))

    registry = get_tool_registry()

    # 获取工具覆盖配置
    overrides = await _get_tool_overrides(db)

    # 获取该 Agent 可用的工具详情
    available_tools = []
    for tool_id in current_tools:
        tool = registry.get(tool_id)
        if tool:
            override = overrides.get(tool_id, {})
            available_tools.append(ToolResponse(
                id=tool.id,
                name=tool.name,
                description=override.get("description", tool.description),
                category=override.get("category", tool.category),
                data_source=tool.data_source,
                is_online=override.get("is_online", tool.is_online),
                timeout=override.get("timeout", tool.timeout),
                rate_limit=override.get("rate_limit", tool.rate_limit),
                icon=tool.icon,
                color=tool.color,
                parameters=[p.model_dump() for p in tool.parameters],
            ))

    return AgentToolsResponse(
        agent_id=agent.id,
        agent_name=agent.name,
        tools=current_tools,
        default_tools=current_default_tools,
        max_tool_calls=current_max_tool_calls,
        available_tools=available_tools,
    )


@router.get("/categories")
async def get_categories():
    """获取所有类别"""
    try:
        from core.api import AgentAPI
        api = AgentAPI()
        categories = api.get_categories()
        return ok(categories)
    except Exception as e:
        logger.error(f"获取类别失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/category/{category}")
async def list_by_category(category: str):
    """按类别获取智能体"""
    try:
        from core.api import AgentAPI
        api = AgentAPI()
        agents = api.list_by_category(category)
        return ok(agents)
    except Exception as e:
        logger.error(f"按类别获取智能体失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{agent_id}")
async def get_agent(agent_id: str):
    """获取智能体详情"""
    try:
        from core.api import AgentAPI
        api = AgentAPI()
        agent = api.get(agent_id)

        if agent is None:
            raise HTTPException(status_code=404, detail="智能体不存在")

        return ok(agent)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取智能体详情失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{agent_id}/execution-config")
async def get_agent_execution_config(
    agent_id: str,
    user: dict = Depends(get_current_user)
):
    """
    获取 Agent 的执行配置（temperature, max_iterations, timeout）
    """
    try:
        from core.config.agent_config_manager import AgentConfigManager
        from app.core.database import get_mongo_db_sync
        
        db = get_mongo_db_sync()
        config_manager = AgentConfigManager()
        config_manager.set_database(db)
        
        logger.info(f"[API] 📋 获取 Agent 执行配置: agent_id={agent_id}, user_id={user.get('id')}")
        
        agent_config = config_manager.get_agent_config(agent_id)
        if not agent_config:
            logger.warning(f"[API] ⚠️ Agent 配置不存在: {agent_id}")
            raise HTTPException(status_code=404, detail="智能体配置不存在")
        
        execution_config = agent_config.get("config", {})
        
        result = {
            "temperature": execution_config.get("temperature"),
            "max_iterations": execution_config.get("max_iterations"),
            "timeout": execution_config.get("timeout"),
        }
        
        logger.info(f"[API] ✅ 返回执行配置: {result}")
        
        return ok(result)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[API] ❌ 获取 Agent 执行配置失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{agent_id}/execution-config")
async def update_agent_execution_config(
    agent_id: str,
    config: dict,
    user: dict = Depends(get_current_user)
):
    """
    更新 Agent 的执行配置（temperature, max_iterations, timeout）
    
    Args:
        config: 执行配置字典，包含 temperature, max_iterations, timeout（可选）
    """
    try:
        from core.config.agent_config_manager import AgentConfigManager
        from app.core.database import get_mongo_db_sync
        
        db = get_mongo_db_sync()
        config_manager = AgentConfigManager()
        config_manager.set_database(db)
        
        logger.info(f"[API] 📝 更新 Agent 执行配置: agent_id={agent_id}, user_id={user.get('id')}")
        logger.info(f"[API]    - 接收到的配置: {config}")
        
        # 获取现有配置
        agent_config = config_manager.get_agent_config(agent_id)
        if not agent_config:
            logger.warning(f"[API] ⚠️ Agent 配置不存在: {agent_id}")
            raise HTTPException(status_code=404, detail="智能体配置不存在")
        
        # 记录更新前的配置
        old_execution_config = agent_config.get("config", {}).copy()
        logger.info(f"[API]    - 更新前的配置: {old_execution_config}")
        
        # 更新执行配置
        execution_config = agent_config.get("config", {})
        if "temperature" in config:
            old_temp = execution_config.get("temperature")
            execution_config["temperature"] = config["temperature"]
            logger.info(f"[API]    - 🌡️ Temperature: {old_temp} -> {config['temperature']}")
        if "max_iterations" in config:
            old_iter = execution_config.get("max_iterations")
            execution_config["max_iterations"] = config["max_iterations"]
            logger.info(f"[API]    - 🔄 Max Iterations: {old_iter} -> {config['max_iterations']}")
        if "timeout" in config:
            old_timeout = execution_config.get("timeout")
            execution_config["timeout"] = config["timeout"]
            logger.info(f"[API]    - ⏱️ Timeout: {old_timeout} -> {config['timeout']}")
        
        agent_config["config"] = execution_config
        
        # 保存配置
        logger.info(f"[API]    - 保存后的配置: {execution_config}")
        success = config_manager.save_agent_config(agent_config)
        if not success:
            logger.error(f"[API] ❌ 保存配置失败: {agent_id}")
            raise HTTPException(status_code=500, detail="保存配置失败")
        
        logger.info(f"[API] ✅ Agent {agent_id} 执行配置已更新成功")
        logger.info(f"[API]    - 最终配置: {execution_config}")
        
        return ok({
            "message": "配置更新成功",
            "config": execution_config
        })
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[API] ❌ 更新 Agent 执行配置失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

