"""
MCP 审计日志服务

所有 MCP 工具调用（数据源类和功能类）均记录到 mcp_audit_logs 集合。
使用同步接口，适合在 executor 闭包（同步上下文）中调用。
"""

import logging
import threading
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

COLLECTION = "mcp_audit_logs"


def _write_audit_log(doc: Dict) -> None:
    """同步写入审计日志到 MongoDB"""
    try:
        from app.core.database import get_mongo_db_sync
        db = get_mongo_db_sync()
        if db is not None:
            db[COLLECTION].insert_one(doc)
    except Exception as e:
        logger.warning(f"⚠️ MCP 审计日志写入失败: {e}")


def log_mcp_call_sync(
    server_name: str,
    tool_name: str,
    category: str,
    request_params: Dict,
    response_summary: str,
    persisted_to: Optional[str] = None,
    task_id: Optional[str] = None,
    user_id: Optional[str] = None,
) -> None:
    """
    异步（fire-and-forget）写入 MCP 调用审计日志。

    在后台线程中写入，不阻塞 MCP 工具调用链路。

    Args:
        server_name:      MCP 服务器名称
        tool_name:        工具名称
        category:         数据源类型 datasource | function
        request_params:   调用参数
        response_summary: 响应摘要（如 "OK, 10 records"）
        persisted_to:     数据源类写入的目标集合名（可为 None）
        task_id:          关联分析任务 ID（可选）
        user_id:          触发用户 ID（可选）
    """
    from app.utils.timezone import now_tz

    doc = {
        "task_id": task_id,
        "user_id": user_id,
        "server_name": server_name,
        "tool_name": tool_name,
        "category": category,
        "request_params": request_params,
        "response_summary": response_summary,
        "persisted_to": persisted_to,
        "created_at": now_tz(),
    }

    # fire-and-forget：后台线程写入，不阻塞 executor
    t = threading.Thread(target=_write_audit_log, args=(doc,), daemon=True)
    t.start()

