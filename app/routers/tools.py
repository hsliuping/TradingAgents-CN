"""
工具管理 API

提供工具列表查询、Agent 工具配置等接口
"""

from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Query, Body, HTTPException, Depends
from pydantic import BaseModel
from motor.motor_asyncio import AsyncIOMotorDatabase

from core.tools import get_tool_registry, ToolMetadata, ToolCategory, BUILTIN_TOOLS
from core.agents.config import BUILTIN_AGENTS
from core.tools.custom_tool import CustomToolDefinition, register_custom_tool
from app.core.database import get_mongo_db

router = APIRouter(prefix="/api/tools", tags=["tools"])


class ToolResponse(BaseModel):
    """工具响应模型"""
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


class ToolConfigUpdate(BaseModel):
    """工具配置更新"""
    is_online: Optional[bool] = None
    timeout: Optional[int] = None
    rate_limit: Optional[int] = None
    description: Optional[str] = None
    category: Optional[str] = None


class CategoryCreate(BaseModel):
    """创建分类"""
    id: str
    name: str


class CategoryUpdate(BaseModel):
    """更新分类"""
    name: str


async def _get_tool_overrides(db: AsyncIOMotorDatabase) -> Dict[str, Dict[str, Any]]:
    """获取所有工具的配置覆盖"""
    overrides = {}
    async for doc in db.tool_configs.find():
        tool_id = doc.pop("tool_id", None)
        if tool_id:
            doc.pop("_id", None)
            overrides[tool_id] = doc
    return overrides


async def _get_custom_categories(db: AsyncIOMotorDatabase) -> Dict[str, str]:
    """获取自定义分类"""
    categories = {}
    async for doc in db.tool_categories.find():
        categories[doc["id"]] = doc["name"]
    return categories


def get_category_name(category: str) -> str:
    """获取类别显示名称"""
    names = {
        "market": "市场数据",
        "fundamentals": "基本面数据",
        "news": "新闻数据",
        "social": "社交媒体",
        "technical": "技术分析",
        "china": "中国市场",
    }
    return names.get(category, category)


@router.get("", response_model=List[ToolResponse])
async def list_tools(
    category: Optional[str] = Query(None, description="工具类别筛选"),
    is_online: Optional[bool] = Query(None, description="是否在线工具"),
    db: AsyncIOMotorDatabase = Depends(get_mongo_db),
):
    """获取所有可用工具列表"""
    registry = get_tool_registry()
    tools = registry.list_all()
    
    # 获取数据库中的覆盖配置
    overrides = await _get_tool_overrides(db)
    
    response_tools = []
    for t in tools:
        # 应用覆盖配置
        override = overrides.get(t.id, {})
        
        tool_data = ToolResponse(
            id=t.id,
            name=t.name,
            description=override.get("description", t.description),
            category=override.get("category", t.category),
            data_source=t.data_source,
            is_online=override.get("is_online", t.is_online),
            timeout=override.get("timeout", t.timeout),
            rate_limit=override.get("rate_limit", t.rate_limit),
            icon=t.icon,
            color=t.color,
            parameters=[p.model_dump() for p in t.parameters],
        )
        response_tools.append(tool_data)
    
    # 筛选
    if category:
        response_tools = [t for t in response_tools if t.category == category]
    if is_online is not None:
        response_tools = [t for t in response_tools if t.is_online == is_online]
    
    return response_tools


@router.get("/categories")
async def list_categories(
    db: AsyncIOMotorDatabase = Depends(get_mongo_db),
):
    """获取所有工具类别（内置 + 自定义）"""
    # 1. 内置分类
    categories = [
        {"id": c.value, "name": get_category_name(c.value), "is_builtin": True}
        for c in ToolCategory
    ]
    
    # 2. 自定义分类
    custom_categories = await _get_custom_categories(db)
    for cid, cname in custom_categories.items():
        # 如果ID冲突，优先显示自定义名称（或者作为覆盖）
        existing = next((c for c in categories if c["id"] == cid), None)
        if existing:
            existing["name"] = cname
        else:
            categories.append({"id": cid, "name": cname, "is_builtin": False})
            
    return categories


@router.post("/categories")
async def create_category(
    category: CategoryCreate,
    db: AsyncIOMotorDatabase = Depends(get_mongo_db),
):
    """创建自定义分类"""
    # 检查是否存在
    existing = await db.tool_categories.find_one({"id": category.id})
    if existing:
        raise HTTPException(status_code=400, detail=f"分类ID {category.id} 已存在")
    
    await db.tool_categories.insert_one(category.model_dump())
    return {"success": True, "message": "分类创建成功"}


@router.put("/categories/{category_id}")
async def update_category(
    category_id: str,
    update: CategoryUpdate,
    db: AsyncIOMotorDatabase = Depends(get_mongo_db),
):
    """更新自定义分类"""
    result = await db.tool_categories.update_one(
        {"id": category_id},
        {"$set": {"name": update.name}}
    )
    if result.matched_count == 0:
        # 也许是想覆盖内置分类的名称？
        # 允许创建一个同名的记录来覆盖显示名称
        await db.tool_categories.update_one(
            {"id": category_id},
            {"$set": {"name": update.name}},
            upsert=True
        )
        
    return {"success": True, "message": "分类更新成功"}


@router.delete("/categories/{category_id}")
async def delete_category(
    category_id: str,
    db: AsyncIOMotorDatabase = Depends(get_mongo_db),
):
    """删除自定义分类"""
    # 不允许删除内置分类（但如果之前覆盖了名称，删掉覆盖记录即可）
    # 内置分类ID在代码里，这里只删数据库记录
    result = await db.tool_categories.delete_one({"id": category_id})
    if result.deleted_count == 0:
         # 检查是否是内置分类
        is_builtin = any(c.value == category_id for c in ToolCategory)
        if is_builtin:
             raise HTTPException(status_code=400, detail="无法删除内置分类")
        raise HTTPException(status_code=404, detail="分类不存在")
        
    return {"success": True, "message": "分类删除成功"}


@router.post("/custom")
async def create_custom_tool(
    definition: CustomToolDefinition,
    db: AsyncIOMotorDatabase = Depends(get_mongo_db),
):
    """创建自定义工具"""
    registry = get_tool_registry()
    if registry.get(definition.id):
        raise HTTPException(status_code=400, detail=f"工具ID {definition.id} 已存在")
    
    # 保存到数据库
    await db.custom_tools.insert_one(definition.model_dump())
    
    # 注册到内存
    await register_custom_tool(definition)
    
    return {"success": True, "message": "工具创建成功"}


@router.get("/custom/{tool_id}", response_model=CustomToolDefinition)
async def get_custom_tool(
    tool_id: str,
    db: AsyncIOMotorDatabase = Depends(get_mongo_db),
):
    """获取自定义工具定义"""
    tool = await db.custom_tools.find_one({"id": tool_id})
    if not tool:
        raise HTTPException(status_code=404, detail="自定义工具不存在")
    return tool


@router.put("/custom/{tool_id}")
async def update_custom_tool(
    tool_id: str,
    definition: CustomToolDefinition,
    db: AsyncIOMotorDatabase = Depends(get_mongo_db),
):
    """更新自定义工具"""
    if tool_id != definition.id:
        raise HTTPException(status_code=400, detail="URL中的ID与请求体中的ID不匹配")
        
    existing = await db.custom_tools.find_one({"id": tool_id})
    if not existing:
        raise HTTPException(status_code=404, detail="自定义工具不存在")
        
    # 更新数据库
    await db.custom_tools.replace_one({"id": tool_id}, definition.model_dump())
    
    # 更新内存注册
    await register_custom_tool(definition)
    
    return {"success": True, "message": "工具更新成功"}


@router.delete("/custom/{tool_id}")
async def delete_custom_tool(
    tool_id: str,
    db: AsyncIOMotorDatabase = Depends(get_mongo_db),
):
    """删除自定义工具"""
    result = await db.custom_tools.delete_one({"id": tool_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="自定义工具不存在")
        
    # 从内存注销
    registry = get_tool_registry()
    registry.unregister(tool_id)
    
    return {"success": True, "message": "工具删除成功"}


@router.put("/{tool_id}")
async def update_tool_config(
    tool_id: str,
    config: ToolConfigUpdate,
    db: AsyncIOMotorDatabase = Depends(get_mongo_db),
):
    """更新工具配置"""
    registry = get_tool_registry()
    if not registry.get(tool_id):
        raise HTTPException(status_code=404, detail=f"工具 {tool_id} 不存在")
    
    update_data = config.model_dump(exclude_unset=True)
    if not update_data:
        return {"success": True, "message": "无变更"}
        
    await db.tool_configs.update_one(
        {"tool_id": tool_id},
        {"$set": update_data},
        upsert=True
    )
    return {"success": True, "message": "配置更新成功"}


@router.get("/{tool_id}", response_model=ToolResponse)
async def get_tool(
    tool_id: str,
    db: AsyncIOMotorDatabase = Depends(get_mongo_db),
):
    """获取单个工具详情"""
    registry = get_tool_registry()
    tool = registry.get(tool_id)
    
    if not tool:
        raise HTTPException(status_code=404, detail=f"工具 {tool_id} 不存在")
    
    # 获取覆盖配置
    override_doc = await db.tool_configs.find_one({"tool_id": tool_id})
    override = override_doc if override_doc else {}
    if "_id" in override:
        del override["_id"]
        
    return ToolResponse(
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
    )


@router.get("/agent/{agent_id}", response_model=AgentToolsResponse)
async def get_agent_tools(
    agent_id: str,
    db: AsyncIOMotorDatabase = Depends(get_mongo_db),
):
    """获取指定 Agent 的工具配置"""
    if agent_id not in BUILTIN_AGENTS:
        raise HTTPException(status_code=404, detail=f"Agent {agent_id} 不存在")
    
    agent = BUILTIN_AGENTS[agent_id]
    registry = get_tool_registry()
    
    # 获取覆盖配置
    overrides = await _get_tool_overrides(db)
    
    # 获取该 Agent 可用的工具详情
    available_tools = []
    for tool_id in agent.tools:
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
        tools=agent.tools,
        default_tools=agent.default_tools,
        max_tool_calls=agent.max_tool_calls,
        available_tools=available_tools,
    )


