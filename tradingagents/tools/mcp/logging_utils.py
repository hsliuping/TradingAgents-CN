"""
MCP 工具日志工具

提供统一的日志记录功能，用于记录工具调用、结果和错误。
"""

import logging
import functools
import traceback
from datetime import datetime
from typing import Any, Callable

logger = logging.getLogger(__name__)


def log_mcp_tool_call(
    tool_name: str = None,
    log_args: bool = True,
    log_result_length: bool = True,
    log_execution_time: bool = True
):
    """
    MCP 工具调用日志装饰器。
    
    Args:
        tool_name: 工具名称（可选，默认使用函数名）
        log_args: 是否记录参数
        log_result_length: 是否记录结果长度
        log_execution_time: 是否记录执行时间
    
    Returns:
        装饰器函数
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            name = tool_name or func.__name__
            start_time = datetime.now()
            timestamp = start_time.strftime("%Y-%m-%d %H:%M:%S")
            
            # 记录调用开始
            log_msg = f"[MCP工具调用] {name} 开始执行"
            if log_args:
                # 过滤敏感参数
                safe_kwargs = {k: v for k, v in kwargs.items() if 'password' not in k.lower() and 'token' not in k.lower()}
                log_msg += f" | 参数: args={args}, kwargs={safe_kwargs}"
            log_msg += f" | 时间: {timestamp}"
            logger.info(log_msg)
            
            try:
                result = func(*args, **kwargs)
                
                # 记录成功结果
                execution_time = (datetime.now() - start_time).total_seconds()
                success_msg = f"[MCP工具调用] {name} 执行成功"
                
                if log_result_length and isinstance(result, str):
                    success_msg += f" | 结果长度: {len(result)} 字符"
                
                if log_execution_time:
                    success_msg += f" | 耗时: {execution_time:.2f}秒"
                
                logger.info(success_msg)
                return result
                
            except Exception as e:
                # 记录错误
                execution_time = (datetime.now() - start_time).total_seconds()
                error_msg = f"[MCP工具调用] {name} 执行失败"
                error_msg += f" | 错误类型: {type(e).__name__}"
                error_msg += f" | 错误信息: {str(e)}"
                error_msg += f" | 耗时: {execution_time:.2f}秒"
                
                logger.error(error_msg)
                logger.error(f"[MCP工具调用] {name} 堆栈跟踪:\n{traceback.format_exc()}")
                
                raise
        
        return wrapper
    return decorator


def log_mcp_server_startup(server_name: str, tool_names: list):
    """
    记录 MCP 服务器启动日志。
    
    Args:
        server_name: 服务器名称
        tool_names: 注册的工具名称列表
    """
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    logger.info(f"[MCP服务器] {server_name} 启动")
    logger.info(f"[MCP服务器] 启动时间: {timestamp}")
    logger.info(f"[MCP服务器] 注册工具数量: {len(tool_names)}")
    logger.info(f"[MCP服务器] 注册工具列表: {', '.join(tool_names)}")


def log_mcp_server_shutdown(server_name: str):
    """
    记录 MCP 服务器关闭日志。
    
    Args:
        server_name: 服务器名称
    """
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    logger.info(f"[MCP服务器] {server_name} 关闭 | 时间: {timestamp}")
