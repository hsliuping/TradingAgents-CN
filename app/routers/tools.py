"""
工具清单接口
- 返回统一工具注册表中的可用工具名称（含本地项目工具，可选启用 MCP）
- 仅用于配置界面选择工具白名单
"""

import logging
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, Query

from app.routers.auth_db import get_current_user
from tradingagents.agents import Toolkit
from tradingagents.tools.registry import get_all_tools
from tradingagents.tools.mcp import LANGCHAIN_MCP_AVAILABLE, get_mcp_loader_factory

router = APIRouter(prefix="/api/tools", tags=["tools"])
logger = logging.getLogger(__name__)


def _tool_info(tool: Any, source: str = "project", external_metadata: Dict[str, Any] = None) -> Dict[str, Any]:
    name = getattr(tool, "name", None)
    description = getattr(tool, "description", None) or getattr(tool, "__doc__", "") or ""
    
    # 尝试从 metadata 获取 source (MCP 工具通常存储在这里)
    metadata = getattr(tool, "metadata", {}) or {}
    if not isinstance(metadata, dict):
        metadata = {}
    
    # 合并外部元数据 (例如来自 wrapper)
    if external_metadata:
        metadata.update(external_metadata)

    metadata_server = metadata.get("server_name")
    
    tool_source = (
        getattr(tool, "server_name", None) or 
        getattr(tool, "server", None) or 
        metadata_server or
        source
    )
    
    return {
        "name": name,
        "description": description.strip() if isinstance(description, str) else "",
        "source": tool_source,
    }


@router.get("/available")
async def list_available_tools(
    include_mcp: bool = Query(True, description="是否包含 MCP 工具"),
    user: dict = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    返回统一工具清单（默认包含项目内工具，按需包含 MCP 工具）。
    include_mcp=True 时总是尝试加载 MCP，未配置则自动忽略。
    """
    toolkit = Toolkit()
    
    # 获取 MCP 工具加载器
    mcp_tool_loader = None
    if include_mcp and LANGCHAIN_MCP_AVAILABLE:
        try:
            factory = get_mcp_loader_factory()
            # 确保 MCP 连接已初始化
            if not factory._initialized:
                await factory.initialize_connections()
            # 创建工具加载器（仅外部 MCP 工具，避免与本地重复）
            mcp_tool_loader = factory.create_loader([], include_local=False)
        except Exception as e:
            logger.warning(f"获取 MCP 工具加载器失败: {e}")
    
    tools = get_all_tools(
        toolkit=toolkit,
        enable_mcp=include_mcp,
        mcp_tool_loader=mcp_tool_loader,
    )

    # 去重并序列化
    seen = set()
    items: List[Dict[str, Any]] = []
    for tool in tools:
        # 尝试从 wrapper 获取 metadata (针对 RunnableBinding)
        external_metadata = {}
        
        # 1. 检查 config 中的 metadata (RunnableBinding 常用)
        if hasattr(tool, "config") and isinstance(tool.config, dict):
            if "metadata" in tool.config:
                external_metadata.update(tool.config["metadata"])
        
        # 2. 检查直接的 metadata 属性
        if hasattr(tool, "metadata") and isinstance(tool.metadata, dict):
             external_metadata.update(tool.metadata)

        # 特殊处理 RunnableBinding (MCP 工具可能被 wrap)
        if hasattr(tool, "bound") and not getattr(tool, "name", None):
            try:
                # 尝试从 bound 对象获取 name
                tool = tool.bound
            except Exception:
                pass

        name = getattr(tool, "name", None)
        
        if not name or name in seen:
            continue
        seen.add(name)
        items.append(_tool_info(tool, external_metadata=external_metadata))
    
    # 如果启用了 MCP，还需要添加外部 MCP 服务器的工具（非 local 的）
    if include_mcp and LANGCHAIN_MCP_AVAILABLE:
        try:
            factory = get_mcp_loader_factory()
            mcp_tools_info = factory.list_available_tools()
            for tool_info in mcp_tools_info:
                tool_name = tool_info.get("name")
                server_name = tool_info.get("serverName", "mcp")
                # 只添加外部 MCP 工具（非 local）
                if tool_name and tool_name not in seen and server_name != "local":
                    seen.add(tool_name)
                    items.append({
                        "name": tool_name,
                        "description": tool_info.get("description", ""),
                        "source": server_name,
                    })
                    logger.info(f"添加外部 MCP 工具: {tool_name} (来源: {server_name})")
        except Exception as e:
            logger.warning(f"获取外部 MCP 工具列表失败: {e}")

    return {"success": True, "data": items, "count": len(items)}

