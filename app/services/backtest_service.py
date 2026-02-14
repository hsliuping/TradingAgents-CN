"""
回测业务服务层
策略分析、DSL 生成、执行回测、结果存储
"""
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from motor.motor_asyncio import AsyncIOMotorDatabase

from core.backtest import (
    BacktestEngineClient,
    analyze_strategy_feasibility,
    generate_strategy_dsl,
)
from app.core.database import get_mongo_db

logger = logging.getLogger(__name__)


async def analyze(user_id: str, description: str) -> str:
    """分析策略可行性"""
    return await analyze_strategy_feasibility(description)


async def generate(user_id: str, description: str) -> Dict[str, Any]:
    """生成策略 DSL（含 L2 语义校验、L3 执行校验与自修正）"""
    from app.services.config_provider import provider as config_provider

    settings = await config_provider.get_effective_system_settings()
    validate_on = settings.get("dsl_validate_on_generate", True)
    run_exec = settings.get("dsl_run_execution_check", True)
    dsl = await generate_strategy_dsl(
        description,
        validate_on_generate=validate_on,
        run_execution_check=run_exec,
    )
    return dsl


async def run_backtest(
    user_id: str,
    strategy_dsl: Dict[str, Any],
    session_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    执行回测并存储结果
    Returns:
        { "session_id", "result_id", "success", "summary", "error" }
    """
    db = get_mongo_db()
    sid = session_id or str(uuid.uuid4())
    now = datetime.now(timezone.utc)

    session_doc = {
        "id": sid,
        "user_id": user_id,
        "strategy": strategy_dsl,
        "status": "running",
        "created_at": now,
        "updated_at": now,
    }
    await db.backtest_sessions.insert_one(session_doc)

    client = BacktestEngineClient()
    try:
        resp = await client.run(strategy_dsl)
        if resp.get("success"):
            summary = resp.get("summary", {})
            result_doc = {
                "id": str(uuid.uuid4()),
                "session_id": sid,
                "user_id": user_id,
                "strategy": strategy_dsl,
                "summary": summary,
                "created_at": now,
            }
            await db.backtest_results.insert_one(result_doc)
            await db.backtest_sessions.update_one(
                {"id": sid},
                {"$set": {"status": "completed", "updated_at": now}},
            )
            return {
                "session_id": sid,
                "result_id": result_doc["id"],
                "success": True,
                "summary": summary,
            }
        else:
            err = resp.get("error", "未知错误")
            await db.backtest_sessions.update_one(
                {"id": sid},
                {"$set": {"status": "failed", "error": err, "updated_at": now}},
            )
            return {
                "session_id": sid,
                "success": False,
                "error": err,
            }
    except Exception as e:
        logger.exception("回测执行失败")
        await db.backtest_sessions.update_one(
            {"id": sid},
            {"$set": {"status": "failed", "error": str(e), "updated_at": now}},
        )
        return {
            "session_id": sid,
            "success": False,
            "error": str(e),
        }


async def get_result(result_id: str, user_id: str) -> Optional[Dict[str, Any]]:
    """获取回测结果"""
    db = get_mongo_db()
    doc = await db.backtest_results.find_one({"id": result_id, "user_id": user_id})
    if not doc:
        return None
    doc.pop("_id", None)
    return doc


async def list_sessions(user_id: str, limit: int = 50) -> List[Dict[str, Any]]:
    """列出用户回测会话"""
    db = get_mongo_db()
    cursor = db.backtest_sessions.find(
        {"user_id": user_id},
        sort=[("created_at", -1)],
        limit=limit,
    )
    rows = []
    async for d in cursor:
        d.pop("_id", None)
        rows.append(d)
    return rows


async def delete_session(session_id: str, user_id: str) -> bool:
    """删除回测会话"""
    db = get_mongo_db()
    r = await db.backtest_sessions.delete_one({"id": session_id, "user_id": user_id})
    await db.backtest_results.delete_many({"session_id": session_id, "user_id": user_id})
    return r.deleted_count > 0
