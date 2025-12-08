"""
工具管理 API

提供工具列表查询、Agent 工具配置等接口
"""

from typing import List, Optional
from fastapi import APIRouter, Query
from pydantic import BaseModel

from core.tools import get_tool_registry, ToolMetadata, ToolCategory, BUILTIN_TOOLS
from core.agents.config import BUILTIN_AGENTS

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


@router.get("", response_model=List[ToolResponse])
async def list_tools(
    category: Optional[str] = Query(None, description="工具类别筛选"),
    is_online: Optional[bool] = Query(None, description="是否在线工具"),
):
    """获取所有可用工具列表"""
    registry = get_tool_registry()
    tools = registry.list_all()
    
    # 筛选
    if category:
        tools = [t for t in tools if t.category == category]
    if is_online is not None:
        tools = [t for t in tools if t.is_online == is_online]
    
    return [
        ToolResponse(
            id=t.id,
            name=t.name,
            description=t.description,
            category=t.category,
            data_source=t.data_source,
            is_online=t.is_online,
            timeout=t.timeout,
            rate_limit=t.rate_limit,
            icon=t.icon,
            color=t.color,
            parameters=[p.model_dump() for p in t.parameters],
        )
        for t in tools
    ]


@router.get("/categories")
async def list_categories():
    """获取所有工具类别"""
    return [
        {"id": c.value, "name": get_category_name(c.value)}
        for c in ToolCategory
    ]


@router.get("/{tool_id}", response_model=ToolResponse)
async def get_tool(tool_id: str):
    """获取单个工具详情"""
    registry = get_tool_registry()
    tool = registry.get(tool_id)
    
    if not tool:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail=f"工具 {tool_id} 不存在")
    
    return ToolResponse(
        id=tool.id,
        name=tool.name,
        description=tool.description,
        category=tool.category,
        data_source=tool.data_source,
        is_online=tool.is_online,
        timeout=tool.timeout,
        rate_limit=tool.rate_limit,
        icon=tool.icon,
        color=tool.color,
        parameters=[p.model_dump() for p in tool.parameters],
    )


@router.get("/agent/{agent_id}", response_model=AgentToolsResponse)
async def get_agent_tools(agent_id: str):
    """获取指定 Agent 的工具配置"""
    if agent_id not in BUILTIN_AGENTS:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail=f"Agent {agent_id} 不存在")
    
    agent = BUILTIN_AGENTS[agent_id]
    registry = get_tool_registry()
    
    # 获取该 Agent 可用的工具详情
    available_tools = []
    for tool_id in agent.tools:
        tool = registry.get(tool_id)
        if tool:
            available_tools.append(ToolResponse(
                id=tool.id,
                name=tool.name,
                description=tool.description,
                category=tool.category,
                data_source=tool.data_source,
                is_online=tool.is_online,
                timeout=tool.timeout,
                rate_limit=tool.rate_limit,
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

