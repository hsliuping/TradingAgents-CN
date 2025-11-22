"""
MCP服务器管理API路由
提供MCP配置管理、服务器状态控制等功能
基于langchain-mcp-adapters实现

Copyright (c) 2025 TradingAgents-CN. All rights reserved.
"""

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from typing import Dict, Any, Optional, List

from app.services.mcp_service import mcp_service

router = APIRouter(prefix="/mcp", tags=["MCP"])

@router.on_event("startup")
async def startup_event():
    """应用启动时初始化MCP管理器"""
    try:
        from tradingagents.mcp import mcp_manager
        await mcp_manager.start()
        print("✅ MCP服务器管理器已启动 (langchain-mcp-adapters)")
    except Exception as e:
        print(f"❌ MCP管理器启动失败: {e}")

@router.on_event("shutdown")
async def shutdown_event():
    """应用关闭时清理MCP管理器"""
    try:
        from tradingagents.mcp import mcp_manager
        await mcp_manager.disconnect()
        print("✅ MCP服务器管理器已停止")
    except Exception as e:
        print(f"❌ MCP管理器停止失败: {e}")


# 数据模型
class McpConfiguration(BaseModel):
    mcpServers: Dict[str, Any]


class McpServerStatus(BaseModel):
    name: str
    status: str  # 'online', 'offline', 'checking'
    lastCheck: str
    responseTime: Optional[int] = None
    errorMessage: Optional[str] = None


class ToggleServerRequest(BaseModel):
    enabled: bool


class ToolCallRequest(BaseModel):
    toolName: str
    arguments: Dict[str, Any]


# API端点
@router.get("/config", summary="获取MCP配置")
async def get_mcp_config():
    """
    获取当前的MCP配置

    Returns:
        MCP配置数据，包含所有服务器配置
    """
    try:
        config = await mcp_service.get_config()
        return {
            "success": True,
            "data": config,
            "message": "配置加载成功"
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"加载配置失败: {str(e)}"
        )


@router.post("/config", summary="保存MCP配置")
async def save_mcp_config(config: McpConfiguration):
    """
    保存MCP配置到文件

    Args:
        config: MCP配置数据

    Returns:
        操作结果
    """
    try:
        # 验证配置格式
        if not isinstance(config.mcpServers, dict):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="配置格式错误: mcpServers 必须是对象"
            )

        # 转换为字典格式保存
        config_dict = config.dict()

        # 保存配置
        result = await mcp_service.save_config(config_dict)
        
        if result.get("success"):
            return {
                "success": True,
                "message": result.get("message", "配置保存成功")
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result.get("message", "配置保存失败")
            )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"保存配置失败: {str(e)}"
        )


@router.post("/config/validate", summary="验证MCP配置")
async def validate_mcp_config(config: Dict[str, Any]):
    """
    验证MCP配置格式的正确性

    Args:
        config: 待验证的配置数据

    Returns:
        验证结果
    """
    try:
        result = await mcp_service.validate_config(config)
        
        return {
            "success": True,
            "data": result,
            "message": "配置验证完成"
        }
    except Exception as e:
        return {
            "success": True,
            "data": {
                "valid": False,
                "errors": [f"验证过程出错: {str(e)}"],
                "warnings": []
            },
            "message": "验证过程出错"
        }


@router.get("/servers", summary="获取服务器状态列表")
async def get_servers_status():
    """
    获取所有MCP服务器的状态

    Returns:
        服务器状态列表
    """
    try:
        servers_status = await mcp_service.get_servers_status()
        
        return {
            "success": True,
            "data": servers_status,
            "message": f"获取到 {len(servers_status)} 个服务器状态"
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取服务器状态失败: {str(e)}"
        )


@router.post("/servers/refresh", summary="刷新所有服务器状态")
async def refresh_servers_status():
    """
    刷新所有MCP服务器的状态

    Returns:
        刷新结果
    """
    try:
        result = await mcp_service.refresh_all_status()
        
        return result
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"刷新状态失败: {str(e)}"
        )


@router.get("/servers/{server_name}/status", summary="获取单个服务器状态")
async def get_server_status(server_name: str):
    """
    获取指定MCP服务器的状态

    Args:
        server_name: 服务器名称

    Returns:
        服务器状态信息
    """
    try:
        status_data = await mcp_service.get_server_status(server_name)
        
        return {
            "success": True,
            "data": status_data,
            "message": f"获取服务器 {server_name} 状态成功"
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取服务器状态失败: {str(e)}"
        )


@router.post("/servers/{server_name}/toggle", summary="切换MCP服务器启用状态")
async def toggle_server(server_name: str, request: ToggleServerRequest):
    """
    切换指定MCP服务器的启用/禁用状态

    Args:
        server_name: MCP服务器名称
        request: 包含启用状态的请求体

    Returns:
        操作结果
    """
    try:
        result = await mcp_service.toggle_server(server_name, request.enabled)
        
        if result.get("success"):
            return result
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result.get("message", "切换服务器状态失败")
            )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"切换MCP服务器状态失败: {str(e)}"
        )


@router.post("/servers/{server_name}/test", summary="测试服务器连接")
async def test_server_connection(server_name: str):
    """
    测试指定MCP服务器的连接

    Args:
        server_name: 服务器名称

    Returns:
        测试结果
    """
    try:
        # 通过获取服务器状态来测试连接
        status_data = await mcp_service.get_server_status(server_name)
        
        if status_data.get("status") == "online":
            return {
                "success": True,
                "data": {
                    "connectionSuccess": True,
                    **status_data
                },
                "message": f"服务器 {server_name} 连接测试成功"
            }
        else:
            return {
                "success": False,
                "data": {
                    "connectionSuccess": False,
                    **status_data
                },
                "message": f"服务器 {server_name} 连接测试失败: {status_data.get('errorMessage', '未知错误')}"
            }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"测试服务器连接失败: {str(e)}"
        )


@router.get("/servers/{server_name}/tools", summary="获取服务器工具列表")
async def get_server_tools(server_name: str):
    """
    获取指定MCP服务器提供的工具列表

    Args:
        server_name: 服务器名称

    Returns:
        工具列表
    """
    try:
        from tradingagents.mcp import mcp_manager
        
        # 获取配置检查服务器是否存在且启用
        config = await mcp_service.get_config()
        servers = config.get("mcpServers", {})

        if server_name not in servers:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"服务器 {server_name} 不存在"
            )

        server_config = servers[server_name]
        if not server_config.get('enabled', False):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"服务器 {server_name} 未启用"
            )

        # 获取工具列表
        tools = await mcp_manager.get_server_tools(server_name)

        return {
            "success": True,
            "data": tools,
            "message": f"获取服务器 {server_name} 工具列表成功"
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取工具列表失败: {str(e)}"
        )


@router.post("/servers/{server_name}/tools/{tool_name}/execute", summary="执行工具")
async def execute_tool(server_name: str, tool_name: str, request: ToolCallRequest):
    """
    执行指定MCP服务器的工具

    Args:
        server_name: 服务器名称
        tool_name: 工具名称
        request: 工具调用请求

    Returns:
        工具执行结果
    """
    try:
        from tradingagents.mcp import mcp_manager
        
        # 获取配置检查服务器是否存在且启用
        config = await mcp_service.get_config()
        servers = config.get("mcpServers", {})

        if server_name not in servers:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"服务器 {server_name} 不存在"
            )

        server_config = servers[server_name]
        if not server_config.get('enabled', False):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"服务器 {server_name} 未启用"
            )

        # 执行工具调用
        result = await mcp_manager.call_tool(server_name, tool_name, request.arguments)

        if result.get("success", False):
            return {
                "success": True,
                "data": result,
                "message": f"工具 {tool_name} 执行成功"
            }
        else:
            return {
                "success": False,
                "data": result,
                "message": f"工具 {tool_name} 执行失败: {result.get('error', '未知错误')}"
            }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"工具执行失败: {str(e)}"
        )