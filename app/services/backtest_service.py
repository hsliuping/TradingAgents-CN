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
from core.backtest.result_evaluator import evaluate_backtest_result, optimize_strategy_based_on_evaluation
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
    使用 Tushare 获取指数成分股
    """
    uni = config.get("universe") or {}
    if not isinstance(uni, dict) or uni.get("type") != "index":
        return config
    if uni.get("symbols"):
        return config  # 已预填
    index_code = uni.get("index_code", "")
    if not index_code:
        return config

    try:
        from tradingagents.dataflows.providers.china.tushare import get_tushare_provider

        provider = get_tushare_provider()
        if not provider or not provider.is_available():
            logger.warning("[_resolve_index_symbols] Tushare 不可用，无法获取指数成分股")
            return config

        # 获取指数成分股权重（最新）
        df = await provider.get_index_weight(index_code)
        if df is None or df.empty:
            logger.warning(f"[_resolve_index_symbols] 未获取到指数 {index_code} 的成分股")
            return config

        # 提取股票代码（去掉后缀 .SZ/.SH）
        symbols = []
        for code in df['con_code'].unique():
            # 000001.SZ -> 000001
            clean_code = code.split('.')[0] if '.' in code else code
            symbols.append(clean_code)

        # 限制数量（避免股票池过大）
        max_symbols = 30
        if len(symbols) > max_symbols:
            # 按权重排序，取前N只
            df_sorted = df.sort_values('weight', ascending=False)
            top_codes = df_sorted.head(max_symbols)['con_code'].unique()
            symbols = [c.split('.')[0] for c in top_codes]

        logger.info(f"[_resolve_index_symbols] 指数 {index_code} 成分股: {len(symbols)} 只")

        # 更新 config
        new_config = config.copy()
        new_config["universe"] = {
            "type": "index",
            "index_code": index_code,
            "symbols": symbols  # 预填成分股
        }
        return new_config

    except Exception as e:
        logger.warning(f"[_resolve_index_symbols] 获取指数成分股失败: {e}")
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
            logs = resp.get("logs", [])
            warnings = resp.get("warnings", [])
            logger.info(
                "[backtest_service] backtest-service 返回 summary keys=%s trade_count=%s transactions len=%s logs=%d warnings=%d",
                list(summary.keys()) if summary else [],
                summary.get("trade_count"),
                len(summary.get("transactions", [])),
                len(logs),
                len(warnings),
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
                "logs": logs,
                "warnings": warnings,
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

    # 调试日志：打印从数据库获取的结果
    logger.info(
        "[evaluate_existing_result] 从数据库获取回测结果: session_id=%s, result_id=%s, result_keys=%s",
        session_id,
        result.get("id"),
        list(result.keys()),
    )

    summary = result.get("summary", {})
    logs = result.get("logs", [])
    warnings = result.get("warnings", [])

    logger.info(
        "[evaluate_existing_result] summary=%s, logs_count=%d, warnings_count=%d",
        {k: summary.get(k) for k in ["total_return", "win_rate", "max_drawdown_pct", "trade_count", "final_value"]},
        len(logs),
        len(warnings),
    )

    # 构建回测结果数据（包含 summary、logs、warnings）
    backtest_data = {
        "summary": summary,
        "logs": logs,
        "warnings": warnings,
    }

    # 执行评估
    evaluation = await evaluate_backtest_result(
        user_description, strategy, backtest_data
    )

    logger.info(
        "[evaluate_existing_result] 评估完成: score=%s, is_satisfactory=%s, issues_count=%d",
        evaluation.get("overall_score"),
        evaluation.get("is_satisfactory"),
        len(evaluation.get("issues", [])),
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


async def generate_optimized_strategy(
    user_description: str,
    current_strategy: Dict[str, Any],
    evaluation_result: Dict[str, Any],
    backtest_result: Dict[str, Any],
    user_feedback: str = "",
) -> Dict[str, Any]:
    """
    生成优化后的策略（人在回路模式，单次优化）

    Args:
        user_description: 用户原始需求描述
        current_strategy: 当前策略（code + config）
        evaluation_result: 评估结果
        backtest_result: 回测结果
        user_feedback: 用户补充的优化意见（可选）

    Returns:
        {"success": True, "strategy": {...}, "optimization_summary": "..."}
        或 {"success": False, "error": "..."}
    """
    try:
        logger.info(
            "[generate_optimized_strategy] 开始生成优化策略: user_description_len=%d, strategy_keys=%s, eval_score=%s, user_feedback_len=%d",
            len(user_description),
            list(current_strategy.keys()),
            evaluation_result.get("overall_score"),
            len(user_feedback),
        )

        # 如果用户提供了反馈，需要增强评估结果的 next_steps
        enhanced_evaluation = evaluation_result.copy()
        if user_feedback:
            original_steps = enhanced_evaluation.get("next_steps", "")
            enhanced_evaluation["next_steps"] = f"{original_steps}\n\n【用户补充意见】\n{user_feedback}"

        # 调用优化策略生成器
        logger.info("[generate_optimized_strategy] 调用 optimize_strategy_based_on_evaluation...")
        optimized_strategy = await optimize_strategy_based_on_evaluation(
            user_description=user_description,
            current_strategy=current_strategy,
            evaluation_result=enhanced_evaluation,
            backtest_result=backtest_result,
        )
        logger.info(
            "[generate_optimized_strategy] 优化策略生成完成: keys=%s, code_len=%d",
            list(optimized_strategy.keys()),
            len(optimized_strategy.get("code", "")),
        )

        # 验证优化后的策略（L2 + L3）
        from core.backtest.dsl_evaluator import evaluate_strategy_python_full

        code = optimized_strategy.get("code", "")
        config = optimized_strategy.get("config", {})
        logger.info("[generate_optimized_strategy] 开始验证策略 (L2+L3)...")
        passed, errors = await evaluate_strategy_python_full(code, config)
        if not passed:
            logger.warning("[generate_optimized_strategy] 策略验证失败: %s", errors)
            return {
                "success": False,
                "error": f"优化后的策略验证失败: {'; '.join(errors)}"
            }
        logger.info("[generate_optimized_strategy] 策略验证通过")

        # 提取优化总结
        optimization_summary = optimized_strategy.get("optimization_summary", "已根据评估结果优化策略")

        return {
            "success": True,
            "strategy": optimized_strategy,
            "optimization_summary": optimization_summary,
        }

    except Exception as e:
        logger.exception("生成优化策略失败")
        return {
            "success": False,
            "error": str(e)
        }
