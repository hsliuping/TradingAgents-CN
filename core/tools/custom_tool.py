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
    registry = get_tool_registry()
    
    # 创建执行器实例
    tool_instance = GenericHttpTool(definition)
    
    # 注册函数
    # 注意：这里我们注册的是一个 wrapper，因为 register_function 期望一个 callable
    # 并且我们需要保留 metadata
    
    async def wrapper(**kwargs):
        return await tool_instance.execute(**kwargs)
    
    # 设置 wrapper 的元数据，以便 inspect 可以看到
    wrapper.__name__ = definition.id
    wrapper.__doc__ = definition.description
    
    registry.register_function(
        tool_id=definition.id,
        func=wrapper,
        name=definition.name,
        category=definition.category,
        description=definition.description,
        is_online=definition.is_online,
        override=True
    )
    
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
