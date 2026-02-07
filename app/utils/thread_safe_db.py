"""
线程安全的数据库操作工具

用于在线程池中安全地执行 MongoDB 操作，避免 event loop 冲突
"""
import threading
import asyncio
import logging
from typing import List, Any
from pymongo.results import BulkWriteResult

logger = logging.getLogger(__name__)


def is_in_thread_pool() -> bool:
    """
    检测当前是否在线程池中运行
    
    Returns:
        True 如果在线程池中，False 如果在主线程中
    """
    current_thread = threading.current_thread()
    return not isinstance(current_thread, threading._MainThread)


async def safe_bulk_write(
    collection_name: str,
    operations: List,
    ordered: bool = False,
    async_db=None,
    max_retries: int = 3
) -> BulkWriteResult:
    """
    线程安全的 bulk_write 操作
    
    自动检测运行环境：
    - 在主线程中：使用异步 MongoDB 客户端
    - 在线程池中：使用同步 MongoDB 客户端
    
    Args:
        collection_name: 集合名称
        operations: 批量操作列表
        ordered: 是否按顺序执行
        async_db: 异步数据库实例（主线程中使用）
        max_retries: 最大重试次数
        
    Returns:
        BulkWriteResult 对象
        
    Raises:
        Exception: 如果所有重试都失败
    """
    in_thread_pool = is_in_thread_pool()
    retry_count = 0
    
    while retry_count < max_retries:
        try:
            if in_thread_pool:
                # 🔥 在线程池中：使用同步 MongoDB 客户端
                logger.debug(f"🔍 [线程池] 使用同步 bulk_write: 集合={collection_name}, 操作数={len(operations)}, ordered={ordered}")
                from app.core.database import get_mongo_db_sync
                sync_db = get_mongo_db_sync()
                sync_collection = sync_db[collection_name]
                result = sync_collection.bulk_write(operations, ordered=ordered)
                return result
            else:
                # 🔥 在主线程中：使用异步 MongoDB 客户端
                if async_db is None:
                    from app.core.database import get_mongo_db
                    async_db = get_mongo_db()
                
                logger.debug(f"🔍 [主线程] 使用异步 bulk_write: 集合={collection_name}, 操作数={len(operations)}, ordered={ordered}")
                async_collection = async_db[collection_name]
                result = await async_collection.bulk_write(operations, ordered=ordered)
                return result
                
        except asyncio.TimeoutError as e:
            retry_count += 1
            if retry_count < max_retries:
                wait_time = 2 ** retry_count  # 指数退避：2秒、4秒、8秒
                logger.warning(f"⚠️ 批量写入超时 (第{retry_count}/{max_retries}次重试)，等待{wait_time}秒后重试...")
                
                # 🔥 根据运行环境选择 sleep 方式
                if in_thread_pool:
                    import time
                    time.sleep(wait_time)
                else:
                    await asyncio.sleep(wait_time)
            else:
                logger.error(f"❌ 批量写入失败，已重试{max_retries}次: {e}")
                raise
                
        except Exception as e:
            # 检查是否是超时相关的错误
            error_msg = str(e).lower()
            if 'timeout' in error_msg or 'timed out' in error_msg:
                retry_count += 1
                if retry_count < max_retries:
                    wait_time = 2 ** retry_count
                    logger.warning(f"⚠️ 批量写入超时 (第{retry_count}/{max_retries}次重试)，等待{wait_time}秒后重试... 错误: {e}")
                    
                    # 🔥 根据运行环境选择 sleep 方式
                    if in_thread_pool:
                        import time
                        time.sleep(wait_time)
                    else:
                        await asyncio.sleep(wait_time)
                else:
                    logger.error(f"❌ 批量写入失败，已重试{max_retries}次: {e}")
                    raise
            else:
                logger.error(f"❌ 批量写入失败: {e}")
                raise
    
    raise Exception(f"批量写入失败，已重试{max_retries}次")


async def safe_sleep(seconds: float):
    """
    线程安全的 sleep 操作
    
    自动检测运行环境：
    - 在主线程中：使用 asyncio.sleep
    - 在线程池中：使用 time.sleep
    
    Args:
        seconds: 睡眠秒数
    """
    if is_in_thread_pool():
        import time
        time.sleep(seconds)
    else:
        await asyncio.sleep(seconds)

