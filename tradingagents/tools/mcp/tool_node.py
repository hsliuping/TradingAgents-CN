"""
ToolNode 错误处理和工厂函数

提供统一的 ToolNode 创建和错误处理机制。
使用中文错误消息，帮助 AI 理解错误并采取适当行动。
"""

import logging
import traceback
from datetime import datetime
from typing import List, Any, Callable, Optional, Union

logger = logging.getLogger(__name__)

# 检查 LangGraph 是否可用
try:
    from langgraph.prebuilt import ToolNode
    TOOLNODE_AVAILABLE = True
except ImportError:
    TOOLNODE_AVAILABLE = False
    logger.warning("langgraph 未安装，ToolNode 功能不可用")
    ToolNode = None


class MCPToolError(Exception):
    """MCP 工具错误基类"""
    pass


class DataSourceError(MCPToolError):
    """数据源错误"""
    pass


class InvalidArgumentError(MCPToolError):
    """参数无效错误"""
    pass


def create_error_handler(
    include_suggestions: bool = True,
    log_errors: bool = True
) -> Callable[[Exception], str]:
    """
    创建自定义错误处理器。
    
    Args:
        include_suggestions: 是否包含建议
        log_errors: 是否记录错误日志
    
    Returns:
        错误处理函数
    """
    def handle_tool_errors(e: Exception) -> str:
        """
        统一的错误处理器，返回中文错误信息。
        
        Args:
            e: 异常对象
        
        Returns:
            格式化的中文错误消息
        """
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        error_type = type(e).__name__
        error_msg = str(e)
        
        if log_errors:
            logger.error(f"[ToolNode错误] {error_type}: {error_msg}")
            logger.error(traceback.format_exc())
        
        # 根据错误类型生成不同的消息
        if isinstance(e, TimeoutError):
            message = "⏱️ 工具执行超时"
            suggestion = "可以安全重试，请稍后再试。"
        elif isinstance(e, ConnectionError):
            message = "🔌 网络连接失败"
            suggestion = "请检查网络连接后重试。"
        elif isinstance(e, (DataSourceError, KeyError)):
            message = "📊 数据源不可用"
            suggestion = "请尝试其他数据源或稍后重试。"
        elif isinstance(e, (InvalidArgumentError, ValueError, TypeError)):
            message = f"❌ 参数无效: {error_msg}"
            suggestion = "请检查参数格式是否正确。"
        elif isinstance(e, FileNotFoundError):
            message = "📁 文件或资源未找到"
            suggestion = "请检查路径或资源是否存在。"
        elif isinstance(e, PermissionError):
            message = "🔒 权限不足"
            suggestion = "请检查访问权限。"
        else:
            message = f"❌ 工具执行出错: {error_msg}"
            suggestion = "请尝试其他工具或方法。"
        
        # 构建返回消息
        result = f"""
=== ⚠️ 工具执行错误 ===
时间: {timestamp}
错误类型: {error_type}
错误信息: {message}
"""
        
        if include_suggestions:
            result += f"""
=== 💡 建议 ===
{suggestion}
"""
        
        return result.strip()
    
    return handle_tool_errors


def create_tool_node(
    tools: List[Any],
    handle_tool_errors: Union[bool, str, Callable] = True,
    include_suggestions: bool = True,
    log_errors: bool = True
) -> Optional[Any]:
    """
    创建配置好的 ToolNode。
    
    Args:
        tools: 工具列表
        handle_tool_errors: 错误处理配置
            - True: 使用默认错误处理器
            - False: 不处理错误（让异常传播）
            - str: 使用自定义错误消息
            - Callable: 使用自定义错误处理函数
        include_suggestions: 是否在错误消息中包含建议
        log_errors: 是否记录错误日志
    
    Returns:
        配置好的 ToolNode 实例，如果不可用则返回 None
    """
    if not TOOLNODE_AVAILABLE:
        logger.warning("[ToolNode] langgraph 不可用，无法创建 ToolNode")
        return None
    
    if not tools:
        logger.warning("[ToolNode] 工具列表为空")
        return None
    
    # 确定错误处理器
    if handle_tool_errors is True:
        error_handler = create_error_handler(include_suggestions, log_errors)
    elif handle_tool_errors is False:
        error_handler = False
    elif isinstance(handle_tool_errors, str):
        error_handler = handle_tool_errors
    elif callable(handle_tool_errors):
        error_handler = handle_tool_errors
    else:
        error_handler = create_error_handler(include_suggestions, log_errors)
    
    try:
        tool_node = ToolNode(
            tools=tools,
            handle_tool_errors=error_handler
        )
        
        logger.info(f"✅ [ToolNode] 创建成功，包含 {len(tools)} 个工具")
        return tool_node
    except Exception as e:
        logger.error(f"❌ [ToolNode] 创建失败: {e}")
        return None


def get_default_error_handler() -> Callable[[Exception], str]:
    """
    获取默认的错误处理器。
    
    Returns:
        默认错误处理函数
    """
    return create_error_handler(include_suggestions=True, log_errors=True)
