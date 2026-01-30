"""
重新加载自定义工具脚本

用于修复已注册的自定义工具，确保它们使用同步包装函数
"""

import asyncio
import logging
from motor.motor_asyncio import AsyncIOMotorClient
from core.tools.custom_tool import CustomToolDefinition, register_custom_tool
from core.tools.registry import get_tool_registry

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def reload_custom_tools_from_db():
    """从数据库重新加载所有自定义工具"""
    
    # 连接数据库
    import os
    from dotenv import load_dotenv
    load_dotenv()
    
    mongodb_uri = os.getenv("MONGODB_CONNECTION_STRING")
    if not mongodb_uri:
        logger.error("未找到 MONGODB_CONNECTION_STRING 环境变量")
        return
    
    client = AsyncIOMotorClient(mongodb_uri)
    db = client[os.getenv("MONGODB_DATABASE", "tradingagents")]
    
    # 获取所有自定义工具
    custom_tools_collection = db.custom_tools
    custom_tools = await custom_tools_collection.find({}).to_list(length=None)
    
    logger.info(f"找到 {len(custom_tools)} 个自定义工具")
    
    # 重新注册每个工具
    registry = get_tool_registry()
    reloaded_count = 0
    
    for tool_doc in custom_tools:
        try:
            tool_id = tool_doc.get("id")
            logger.info(f"重新注册工具: {tool_id}")
            
            # 创建工具定义
            tool_def = CustomToolDefinition(**tool_doc)
            
            # 重新注册（会使用新的同步包装函数）
            await register_custom_tool(tool_def)
            
            # 验证工具函数是否为同步的
            import inspect
            registered_func = registry.get_function(tool_id)
            if registered_func:
                if inspect.iscoroutinefunction(registered_func):
                    logger.error(f"❌ 工具 {tool_id} 重新注册后仍然是异步函数！")
                else:
                    logger.info(f"✅ 工具 {tool_id} 重新注册成功，函数类型: {type(registered_func)}")
                    reloaded_count += 1
            else:
                logger.warning(f"⚠️ 工具 {tool_id} 注册后未找到函数")
                
        except Exception as e:
            logger.error(f"❌ 重新注册工具失败 {tool_doc.get('id', 'unknown')}: {e}")
            import traceback
            traceback.print_exc()
    
    logger.info(f"✅ 成功重新注册 {reloaded_count}/{len(custom_tools)} 个工具")
    
    client.close()


if __name__ == "__main__":
    asyncio.run(reload_custom_tools_from_db())
