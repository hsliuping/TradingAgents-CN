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
from core.backtest.iterative_optimizer import IterativeOptimizer
from core.backtest.result_evaluator import evaluate_backtest_result
from app.core.database import get_mongo_db

logger = logging.getLogger(__name__)


async def analyze(user_id: str, description: str) -> str:
    """分析策略可行性"""
    return await analyze_strategy_feasibility(description)


async def generate(user_id: str, description: str) -> Dict[str, Any]:
    """生成策略（Python 代码 + config，含 L2 语义校验、L3 执行校验与自修正）"""
    from app.services.config_provider import provider as config_provider

    settings = await config_provider.get_effective_system_settings()
    validate_on = settings.get("dsl_validate_on_generate", True)
    run_exec = settings.get("dsl_run_execution_check", True)
    result = await generate_strategy_dsl(
        description,
        validate_on_generate=validate_on,
        run_execution_check=run_exec,
    )
    return result


def _is_python_strategy(strategy: Dict[str, Any]) -> bool:
    """判断是否为 Python 策略（code + config）"""
    return "code" in strategy and "config" in strategy


async def _resolve_index_symbols(config: Dict[str, Any]) -> Dict[str, Any]:
    """
    当 config.universe.type=index 时，解析 index_code 获取 symbols
    若无现成工具，返回原 config（主平台可预填 symbols）
    """
    uni = config.get("universe") or {}
    if not isinstance(uni, dict) or uni.get("type") != "index":
        return config
    if uni.get("symbols"):
        return config  # 已预填
    index_code = uni.get("index_code", "")
    if not index_code:
        return config
    # 尝试从 MongoDB 或 Tushare 获取成分股（后续实现）
    # 暂时返回原 config，由 backtest-service 报错
    return config


async def run_backtest(
    user_id: str,
    strategy_input: Dict[str, Any],
    session_id: Optional[str] = None,
    description: Optional[str] = None,
    analysis: Optional[str] = None,
    refinement: Optional[str] = None,
    name: Optional[str] = None,
) -> Dict[str, Any]:
    """
    执行回测并存储结果
    支持两种输入：DSL（走 /run）或 {code, config}（走 /run_python）
    保存原始需求、AI 分析、策略、回测结果，便于后续优化
    Returns:
        { "session_id", "result_id", "success", "summary", "error" }
    """
    db = get_mongo_db()
    sid = session_id or str(uuid.uuid4())
    now = datetime.now(timezone.utc)

    session_doc = {
        "id": sid,
        "user_id": user_id,
        "strategy": strategy_input,
        "name": name or "",
        "description": description or "",
        "analysis": analysis or "",
        "refinement": refinement or "",
        "status": "running",
        "created_at": now,
        "updated_at": now,
    }
    await db.backtest_sessions.insert_one(session_doc)

    client = BacktestEngineClient()
    try:
        if _is_python_strategy(strategy_input):
            code = strategy_input["code"]
            config = await _resolve_index_symbols(strategy_input["config"])
            resp = await client.run_python(code, config)
        else:
            resp = await client.run(strategy_input)
        if resp.get("success"):
            summary = resp.get("summary", {})
            logger.info(
                "[backtest_service] backtest-service 返回 summary keys=%s trade_count=%s transactions len=%s",
                list(summary.keys()) if summary else [],
                summary.get("trade_count"),
                len(summary.get("transactions", [])),
            )
            result_doc = {
                "id": str(uuid.uuid4()),
                "session_id": sid,
                "user_id": user_id,
                "strategy": strategy_input,
                "description": session_doc.get("description", ""),
                "analysis": session_doc.get("analysis", ""),
                "refinement": session_doc.get("refinement", ""),
                "summary": summary,
                "created_at": now,
            }
            await db.backtest_results.insert_one(result_doc)
            await db.backtest_sessions.update_one(
                {"id": sid},
                {
                    "$set": {
                        "status": "completed",
                        "summary": summary,
                        "result_id": result_doc["id"],
                        "updated_at": now,
                    }
                },
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
    """列出用户回测会话（含 summary，便于展示）"""
    db = get_mongo_db()
    cursor = db.backtest_sessions.find(
        {"user_id": user_id},
        sort=[("created_at", -1)],
        limit=limit,
    )
    rows = []
    async for d in cursor:
        d.pop("_id", None)
        # 若 session 无 summary，从 result 补全（兼容旧数据）
        if not d.get("summary") and d.get("result_id"):
            r = await db.backtest_results.find_one({"id": d["result_id"], "user_id": user_id})
            if r and r.get("summary"):
                d["summary"] = r["summary"]
        elif not d.get("summary"):
            r = await db.backtest_results.find_one({"session_id": d["id"], "user_id": user_id}, sort=[("created_at", -1)])
            if r and r.get("summary"):
                d["summary"] = r["summary"]
        rows.append(d)
    return rows


async def get_session(session_id: str, user_id: str) -> Optional[Dict[str, Any]]:
    """获取单个会话详情（含策略、原始需求、分析、回测结果）"""
    db = get_mongo_db()
    d = await db.backtest_sessions.find_one({"id": session_id, "user_id": user_id})
    if not d:
        return None
    d.pop("_id", None)
    if not d.get("summary"):
        r = await db.backtest_results.find_one({"session_id": session_id, "user_id": user_id}, sort=[("created_at", -1)])
        if r:
            d["summary"] = r.get("summary")
            d["description"] = d.get("description") or r.get("description", "")
            d["analysis"] = d.get("analysis") or r.get("analysis", "")
    return d


async def update_session(
    session_id: str, user_id: str, name: Optional[str] = None
) -> bool:
    """更新会话（如策略名称）"""
    db = get_mongo_db()
    updates: Dict[str, Any] = {"updated_at": datetime.now(timezone.utc)}
    if name is not None:
        updates["name"] = name.strip()
    if len(updates) <= 1:
        return False
    r = await db.backtest_sessions.update_one(
        {"id": session_id, "user_id": user_id}, {"$set": updates}
    )
    return r.modified_count > 0


async def delete_session(session_id: str, user_id: str) -> bool:
    """删除回测会话"""
    db = get_mongo_db()
    r = await db.backtest_sessions.delete_one({"id": session_id, "user_id": user_id})
    await db.backtest_results.delete_many({"session_id": session_id, "user_id": user_id})
    return r.deleted_count > 0


async def run_iterative_optimization(
    user_id: str,
    user_description: str,
    initial_strategy: Dict[str, Any],
    max_iterations: int = 3,
    session_id: Optional[str] = None,
    name: Optional[str] = None,
) -> Dict[str, Any]:
    """
    运行迭代优化流程

    Args:
        user_id: 用户ID
        user_description: 用户原始需求描述
        initial_strategy: 初始策略（code + config）
        max_iterations: 最大迭代次数
        session_id: 可选的会话ID
        name: 策略名称

    Returns:
        {
            "session_id": str,
            "final_strategy": {...},
            "final_result": {...},
            "final_evaluation": {...},
            "iterations": [...],
            "optimization_summary": str,
            "success": bool,
            "error": str (if failed)
        }
    """
    db = get_mongo_db()
    sid = session_id or str(uuid.uuid4())
    now = datetime.now(timezone.utc)

    # 创建会话记录
    session_doc = {
        "id": sid,
        "user_id": user_id,
        "name": name or "迭代优化策略",
        "description": user_description,
        "status": "optimizing",
        "optimization_enabled": True,
        "created_at": now,
        "updated_at": now,
    }

    try:
        # 保存初始会话
        await db.backtest_sessions.replace_one(
            {"id": sid}, session_doc, upsert=True
        )

        # 运行迭代优化
        optimizer = IterativeOptimizer()
        optimization_result = await optimizer.optimize_strategy(
            user_description, initial_strategy, max_iterations
        )

        # 更新会话状态
        final_evaluation = optimization_result.get("final_evaluation", {})
        is_satisfactory = final_evaluation.get("is_satisfactory", False)

        session_doc.update({
            "status": "completed" if is_satisfactory else "needs_improvement",
            "strategy": optimization_result.get("final_strategy"),
            "summary": optimization_result.get("final_result", {}).get("summary"),
            "evaluation": final_evaluation,
            "iterations": optimization_result.get("iterations", []),
            "optimization_summary": optimization_result.get("optimization_summary", ""),
            "updated_at": now,
        })

        await db.backtest_sessions.replace_one(
            {"id": sid}, session_doc, upsert=True
        )

        # 保存最终回测结果
        if optimization_result.get("final_result", {}).get("success"):
            result_id = str(uuid.uuid4())
            result_doc = {
                "id": result_id,
                "session_id": sid,
                "user_id": user_id,
                "strategy": optimization_result.get("final_strategy"),
                "result": optimization_result.get("final_result"),
                "evaluation": final_evaluation,
                "created_at": now,
            }
            await db.backtest_results.insert_one(result_doc)
            optimization_result["result_id"] = result_id

        optimization_result.update({
            "session_id": sid,
            "success": True,
        })

        return optimization_result

    except Exception as e:
        logger.exception("迭代优化失败")

        # 更新会话状态为失败
        await db.backtest_sessions.update_one(
            {"id": sid},
            {
                "$set": {
                    "status": "failed",
                    "error": str(e),
                    "updated_at": now,
                }
            }
        )

        return {
            "session_id": sid,
            "success": False,
            "error": str(e),
            "optimization_summary": f"优化过程失败: {e}",
        }


async def evaluate_existing_result(
    user_id: str,
    session_id: str,
    user_description: str,
) -> Dict[str, Any]:
    """
    评估现有回测结果

    Args:
        user_id: 用户ID
        session_id: 会话ID
        user_description: 用户原始需求描述

    Returns:
        评估结果
    """
    db = get_mongo_db()

    # 获取会话信息
    session = await db.backtest_sessions.find_one({"id": session_id, "user_id": user_id})
    if not session:
        raise ValueError("会话不存在")

    strategy = session.get("strategy")
    if not strategy:
        raise ValueError("会话中没有策略信息")

    # 获取最新的回测结果
    result = await db.backtest_results.find_one(
        {"session_id": session_id, "user_id": user_id},
        sort=[("created_at", -1)]
    )
    if not result:
        raise ValueError("没有找到回测结果")

    # 执行评估
    evaluation = await evaluate_backtest_result(
        user_description, strategy, result.get("result", {})
    )

    # 保存评估结果到会话
    await db.backtest_sessions.update_one(
        {"id": session_id},
        {
            "$set": {
                "evaluation": evaluation,
                "updated_at": datetime.now(timezone.utc),
            }
        }
    )

    return evaluation
