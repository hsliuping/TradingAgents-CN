"""
Database status and connection checks, extracted from DatabaseService.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict

from app.core.database import get_mongo_db, get_redis_client
from app.core.config import settings


async def get_mongodb_status() -> Dict[str, Any]:
    try:
        db = get_mongo_db()
        await db.command("ping")
        server_info = await db.command("buildInfo")
        server_status = await db.command("serverStatus")
        return {
            "connected": True,
            "host": settings.MONGODB_HOST,
            "port": settings.MONGODB_PORT,
            "database": settings.MONGODB_DATABASE,
            "version": server_info.get("version", "Unknown"),
            "uptime": server_status.get("uptime", 0),
            "connections": server_status.get("connections", {}),
            "memory": server_status.get("mem", {}),
            "connected_at": datetime.utcnow().isoformat(),
        }
    except Exception as e:
        return {
            "connected": False,
            "error": str(e),
            "host": settings.MONGODB_HOST,
            "port": settings.MONGODB_PORT,
            "database": settings.MONGODB_DATABASE,
        }


async def get_redis_status() -> Dict[str, Any]:
    try:
        redis_client = get_redis_client()
        await redis_client.ping()
        info = await redis_client.info()
        return {
            "connected": True,
            "host": settings.REDIS_HOST,
            "port": settings.REDIS_PORT,
            "database": settings.REDIS_DB,
            "version": info.get("redis_version", "Unknown"),
            "uptime": info.get("uptime_in_seconds", 0),
            "memory_used": info.get("used_memory", 0),
            "memory_peak": info.get("used_memory_peak", 0),
            "connected_clients": info.get("connected_clients", 0),
            "total_commands": info.get("total_commands_processed", 0),
        }
    except Exception as e:
        return {
            "connected": False,
            "error": str(e),
            "host": settings.REDIS_HOST,
            "port": settings.REDIS_PORT,
            "database": settings.REDIS_DB,
        }


async def get_database_status() -> Dict[str, Any]:
    mongodb_status = await get_mongodb_status()
    redis_status = await get_redis_status()
    return {"mongodb": mongodb_status, "redis": redis_status}


async def test_mongodb_connection() -> Dict[str, Any]:
    try:
        db = get_mongo_db()
        start = datetime.utcnow()
        await db.command("ping")
        took_ms = (datetime.utcnow() - start).total_seconds() * 1000
        return {"success": True, "response_time_ms": round(took_ms, 2), "message": "MongoDB连接正常"}
    except Exception as e:
        return {"success": False, "error": str(e), "message": "MongoDB连接失败"}


async def test_redis_connection() -> Dict[str, Any]:
    try:
        redis_client = get_redis_client()
        start = datetime.utcnow()
        await redis_client.ping()
        took_ms = (datetime.utcnow() - start).total_seconds() * 1000
        return {"success": True, "response_time_ms": round(took_ms, 2), "message": "Redis连接正常"}
    except Exception as e:
        return {"success": False, "error": str(e), "message": "Redis连接失败"}


async def test_connections() -> Dict[str, Any]:
    mongodb = await test_mongodb_connection()
    redis = await test_redis_connection()
    return {"mongodb": mongodb, "redis": redis, "overall": mongodb["success"] and redis["success"]}

