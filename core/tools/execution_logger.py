"""
工具执行日志记录器

记录 Agent 工具调用的入参、出参、耗时等信息，便于事后审查和调试。
"""

import asyncio
import logging
from datetime import datetime
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class ToolExecutionLogger:
    """工具执行日志记录器（单例）

    支持同步/异步两种数据库（pymongo / motor）。
    在异步上下文中通过 create_task 提交，在同步上下文中使用 get_mongo_db_sync 回退。
    """

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._db = None
            cls._instance._collection_name = "tool_execution_logs"
        return cls._instance

    def set_db(self, db):
        """设置数据库连接（可以是 AsyncIOMotorDatabase 或 pymongo Database）"""
        self._db = db

    def log(
        self,
        tool_id: str,
        agent_id: str,
        tool_args: Dict[str, Any],
        result: Any,
        success: bool,
        execution_time_ms: int,
        analysis_id: Optional[str] = None,
        error: Optional[str] = None,
    ):
        """记录一次工具执行（自动适配同步/异步数据库）"""
        try:
            # 结果序列化（截断过长的结果）
            result_str = str(result) if result is not None else None
            if result_str and len(result_str) > 5000:
                result_str = result_str[:5000] + "...[truncated]"

            doc = {
                "tool_id": tool_id,
                "agent_id": agent_id,
                "tool_args": tool_args,
                "result": result_str,
                "success": success,
                "execution_time_ms": execution_time_ms,
                "analysis_id": analysis_id,
                "error": error,
                "created_at": datetime.utcnow().isoformat(),
            }

            # 优先：在异步上下文中使用注入的 motor db
            if self._db is not None and self._is_async_db(self._db):
                try:
                    loop = asyncio.get_running_loop()
                    loop.create_task(self._async_insert(doc))
                    return
                except RuntimeError:
                    # 不在事件循环中，回退到同步写入
                    pass

            # 同步写入（pymongo 或回退路径）
            self._sync_insert(doc)
        except Exception as e:
            logger.warning(f"记录工具执行日志失败: {e}")

    @staticmethod
    def _is_async_db(db) -> bool:
        cls_name = type(db).__name__
        return "AsyncIOMotor" in cls_name or cls_name.endswith("Proxy")

    async def _async_insert(self, doc: Dict[str, Any]) -> None:
        try:
            await self._db[self._collection_name].insert_one(doc)
        except Exception as e:
            logger.warning(f"异步写入工具执行日志失败: {e}")

    def _sync_insert(self, doc: Dict[str, Any]) -> None:
        try:
            from app.core.database import get_mongo_db_sync
            sync_db = get_mongo_db_sync()
            if sync_db is not None:
                sync_db[self._collection_name].insert_one(doc)
        except Exception as e:
            logger.warning(f"同步写入工具执行日志失败: {e}")


# 全局实例
_global_logger: Optional[ToolExecutionLogger] = None


def get_tool_execution_logger() -> ToolExecutionLogger:
    """获取全局工具执行日志记录器"""
    global _global_logger
    if _global_logger is None:
        _global_logger = ToolExecutionLogger()
    return _global_logger
