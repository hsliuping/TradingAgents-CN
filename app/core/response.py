"""
统一API响应格式工具
"""
from datetime import datetime
from typing import Any, Dict

from bson import ObjectId

from app.services.database.serialization import serialize_document
from app.utils.timezone import now_tz


def _serialize_response_data(data: Any) -> Any:
    """将常见 Mongo/Pydantic 对象转换为 JSON 安全结构。"""
    if data is None or isinstance(data, (str, int, float, bool)):
        return data

    if isinstance(data, ObjectId):
        return str(data)

    if isinstance(data, datetime):
        return data.isoformat()

    if hasattr(data, "model_dump") and callable(data.model_dump):
        return _serialize_response_data(data.model_dump())

    if isinstance(data, dict):
        normalized = {
            key: _serialize_response_data(value)
            for key, value in data.items()
        }
        return serialize_document(normalized)

    if isinstance(data, (list, tuple, set)):
        return [_serialize_response_data(item) for item in data]

    return data


def ok(data: Any = None, message: str = "ok") -> Dict[str, Any]:
    """标准成功响应
    返回结构：{"success": True, "data": data, "message": message, "timestamp": ...}
    """
    return {
        "success": True,
        "data": _serialize_response_data(data),
        "message": message,
        "timestamp": now_tz().isoformat()
    }


def fail(message: str = "error", code: int = 500, data: Any = None) -> Dict[str, Any]:
    """标准失败响应（一般错误仍建议用 HTTPException 抛出，此函数用于业务失败场景）"""
    return {
        "success": False,
        "data": _serialize_response_data(data),
        "message": message,
        "code": code,
        "timestamp": now_tz().isoformat()
    }

