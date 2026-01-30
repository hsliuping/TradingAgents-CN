"""
自定义工具模块

支持动态创建和注册基于HTTP的自定义工具
"""

import logging
import aiohttp
import json
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
from core.tools.registry import get_tool_registry
from core.tools.config import ToolMetadata, ToolParameter, ToolCategory

logger = logging.getLogger(__name__)

class HttpToolConfig(BaseModel):
    """HTTP工具配置"""
    url: str
    method: str = "GET"
    headers: Optional[Dict[str, str]] = None
    
class CustomToolDefinition(BaseModel):
    """自定义工具定义"""
    id: str
    name: str
    description: str
    category: str
    parameters: List[ToolParameter]
    implementation: HttpToolConfig
    is_online: bool = True
    timeout: int = 30

class GenericHttpTool:
    """通用HTTP工具执行器"""
    def __init__(self, definition: CustomToolDefinition):
        self.definition = definition
        
    async def execute(self, **kwargs):
        """执行HTTP请求"""
        config = self.definition.implementation
        
        # URL 参数替换
        url = config.url
        for key, value in kwargs.items():
            placeholder = f"{{{key}}}"
            if placeholder in url:
                url = url.replace(placeholder, str(value))
        
        # 准备请求参数
        params = {}
        json_body = None
        
        # 排除已在URL中使用的参数
        remaining_kwargs = {k: v for k, v in kwargs.items() if f"{{{k}}}" not in config.url}
        
        if config.method.upper() == "GET":
            params = remaining_kwargs
        elif config.method.upper() in ["POST", "PUT", "PATCH"]:
            json_body = remaining_kwargs
            
        try:
            async with aiohttp.ClientSession() as session:
                async with session.request(
                    method=config.method,
                    url=url,
                    headers=config.headers,
                    params=params,
                    json=json_body,
                    timeout=self.definition.timeout
                ) as response:
                    # 尝试解析响应
                    try:
                        result = await response.json()
                    except:
                        result = await response.text()
                        
                    if response.status >= 400:
                        raise Exception(f"HTTP {response.status}: {result}")
                    
                    return result
        except Exception as e:
            logger.error(f"工具 {self.definition.id} 执行失败: {e}")
            raise

async def register_custom_tool(definition: CustomToolDefinition):
    """注册自定义工具到全局注册表"""
    import asyncio
    import threading
    
    registry = get_tool_registry()
    
    # 创建执行器实例
    tool_instance = GenericHttpTool(definition)
    
    # 🔥 创建同步包装函数（LangChain 工具需要同步函数）
    def sync_wrapper(**kwargs):
        """
        同步包装函数，用于 LangChain 工具调用
        
        注意：这个函数会在内部运行异步代码
        """
        try:
            # 尝试获取当前事件循环
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # 如果事件循环正在运行（例如在异步上下文中），
                # 需要在新线程中运行异步代码
                result_container = {}
                exception_container = {}
                
                def run_async():
                    """在新线程中运行异步代码"""
                    try:
                        new_loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(new_loop)
                        result_container['value'] = new_loop.run_until_complete(
                            tool_instance.execute(**kwargs)
                        )
                        new_loop.close()
                    except Exception as e:
                        exception_container['value'] = e
                
                thread = threading.Thread(target=run_async, daemon=True)
                thread.start()
                thread.join(timeout=definition.timeout + 10)  # 超时保护
                
                if thread.is_alive():
                    raise TimeoutError(f"工具执行超时（超过 {definition.timeout + 10} 秒）")
                
                if 'value' in exception_container:
                    raise exception_container['value']
                
                return result_container.get('value')
            else:
                # 事件循环存在但未运行，可以直接使用
                return loop.run_until_complete(tool_instance.execute(**kwargs))
        except RuntimeError:
            # 没有事件循环，创建新的（最常见的情况）
            return asyncio.run(tool_instance.execute(**kwargs))
    
    # 设置 wrapper 的元数据，以便 inspect 可以看到
    sync_wrapper.__name__ = definition.id
    sync_wrapper.__doc__ = definition.description
    
    # 🔥 验证 sync_wrapper 不是协程函数
    import inspect
    if inspect.iscoroutinefunction(sync_wrapper):
        raise ValueError(
            f"工具 {definition.id} 的同步包装函数仍然是异步函数！"
            f"这会导致工具调用返回协程对象。"
        )
    
    logger.debug(f"🔍 验证工具 {definition.id} 的包装函数类型: {type(sync_wrapper)}")
    logger.debug(f"🔍 是否为协程函数: {inspect.iscoroutinefunction(sync_wrapper)}")
    
    registry.register_function(
        tool_id=definition.id,
        func=sync_wrapper,  # 🔥 使用同步包装函数
        name=definition.name,
        category=definition.category,
        description=definition.description,
        is_online=definition.is_online,
        override=True
    )
    
    # 🔥 验证注册后的函数确实是同步的
    registered_func = registry.get_function(definition.id)
    if registered_func and inspect.iscoroutinefunction(registered_func):
        logger.error(
            f"❌ 工具 {definition.id} 注册后仍然是异步函数！"
            f"注册的函数类型: {type(registered_func)}"
        )
    else:
        logger.debug(f"✅ 工具 {definition.id} 注册成功，函数类型: {type(registered_func)}")
    
    # 手动更新参数定义
    # register_function 默认会分析函数签名，但 wrapper 是 (**kwargs)
    # 所以我们需要手动覆盖 metadata 中的 parameters
    metadata = registry.get(definition.id)
    if metadata:
        metadata.parameters = definition.parameters
        metadata.data_source = "custom_http"
        metadata.icon = "🌐"  # 自定义工具图标
        metadata.color = "#3498db"

    logger.info(f"✅ 自定义工具已注册: {definition.id}")
