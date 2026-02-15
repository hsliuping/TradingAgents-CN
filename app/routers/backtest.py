"""
回测 API 路由
POST /api/backtest/analyze  - AI 分析策略可行性
POST /api/backtest/generate - 生成策略 DSL
POST /api/backtest/run      - 执行回测
POST /api/backtest/optimize - 迭代优化策略（OpenClaw 风格）
POST /api/backtest/evaluate - 评估现有回测结果
GET  /api/backtest/results/:id - 获取回测结果
GET  /api/backtest/sessions   - 列出回测会话
DELETE /api/backtest/sessions/:id - 删除会话
"""
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException

from app.services.backtest_service import (
    analyze,
    generate,
    run_backtest,
    get_result,
    get_session,
    list_sessions,
    update_session,
    delete_session,
    run_iterative_optimization,
    evaluate_existing_result,
    generate_optimized_strategy,
)
from app.routers.auth_db import get_current_user_id

router = APIRouter(prefix="/api/backtest", tags=["backtest"])


@router.post("/analyze")
async def api_analyze(
    body: Dict[str, Any],
    user_id: str = Depends(get_current_user_id),
):
    """分析策略可行性"""
    desc = body.get("description") or body.get("text") or ""
    if not desc:
        raise HTTPException(400, "请提供策略描述 description")
    analysis_text = await analyze(user_id, desc)
    return {"analysis": analysis_text}


@router.post("/generate")
async def api_generate(
    body: Dict[str, Any],
    user_id: str = Depends(get_current_user_id),
):
    """生成策略（Python 代码 + config）"""
    desc = body.get("description") or body.get("text") or ""
    if not desc:
        raise HTTPException(400, "请提供策略描述 description")
    try:
        result = await generate(user_id, desc)
        # 返回 {code, config}，兼容前端期望的 strategy 字段
        return {"strategy": result, "code": result.get("code"), "config": result.get("config")}
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.post("/run")
async def api_run(
    body: Dict[str, Any],
    user_id: str = Depends(get_current_user_id),
):
    """执行回测（支持 DSL 或 {code, config}），保存原始需求、分析、策略、结果"""
    strategy = body.get("strategy")
    if not strategy:
        # 支持直接传 code + config
        code = body.get("code")
        config = body.get("config")
        if code and config:
            strategy = {"code": code, "config": config}
    if not strategy:
        raise HTTPException(400, "请提供 strategy（DSL 或 {code, config}）")
    session_id = body.get("session_id")
    description = body.get("description")
    analysis = body.get("analysis")
    refinement = body.get("refinement")
    name = body.get("name")
    result = await run_backtest(
        user_id, strategy, session_id,
        description=description, analysis=analysis, refinement=refinement, name=name,
    )
    return result


@router.get("/results/{result_id}")
async def api_get_result(
    result_id: str,
    user_id: str = Depends(get_current_user_id),
):
    """获取回测结果"""
    doc = await get_result(result_id, user_id)
    if not doc:
        raise HTTPException(404, "结果不存在")
    return doc


@router.get("/sessions")
async def api_list_sessions(
    limit: int = 50,
    user_id: str = Depends(get_current_user_id),
):
    """列出回测会话（含原始需求、策略、回测结果摘要）"""
    return await list_sessions(user_id, limit)


@router.get("/sessions/{session_id}")
async def api_get_session(
    session_id: str,
    user_id: str = Depends(get_current_user_id),
):
    """获取单个会话详情（含策略、原始需求、AI 分析、回测结果）"""
    doc = await get_session(session_id, user_id)
    if not doc:
        raise HTTPException(404, "会话不存在")
    return doc


@router.patch("/sessions/{session_id}")
async def api_update_session(
    session_id: str,
    body: Dict[str, Any],
    user_id: str = Depends(get_current_user_id),
):
    """更新会话（如策略名称）"""
    name = body.get("name")
    if name is None:
        raise HTTPException(400, "请提供 name")
    ok = await update_session(session_id, user_id, name=name)
    if not ok:
        raise HTTPException(404, "会话不存在或未修改")
    return {"success": True}


@router.delete("/sessions/{session_id}")
async def api_delete_session(
    session_id: str,
    user_id: str = Depends(get_current_user_id),
):
    """删除回测会话"""
    ok = await delete_session(session_id, user_id)
    if not ok:
        raise HTTPException(404, "会话不存在")
    return {"success": True}


@router.post("/optimize")
async def api_optimize(
    request: Dict[str, Any],
    user_id: str = Depends(get_current_user_id),
):
    """运行迭代优化流程"""
    user_description = request.get("description", "")
    if not user_description:
        raise HTTPException(400, "缺少策略描述")

    initial_strategy = request.get("strategy")
    if not initial_strategy:
        raise HTTPException(400, "缺少初始策略")

    max_iterations = request.get("max_iterations", 3)
    session_id = request.get("session_id")
    name = request.get("name")

    try:
        result = await run_iterative_optimization(
            user_id=user_id,
            user_description=user_description,
            initial_strategy=initial_strategy,
            max_iterations=max_iterations,
            session_id=session_id,
            name=name,
        )
        return result
    except Exception as e:
        raise HTTPException(500, f"迭代优化失败: {e}")


@router.post("/evaluate")
async def api_evaluate(
    request: Dict[str, Any],
    user_id: str = Depends(get_current_user_id),
):
    """评估现有回测结果"""
    session_id = request.get("session_id")
    if not session_id:
        raise HTTPException(400, "缺少会话ID")

    user_description = request.get("description", "")
    if not user_description:
        raise HTTPException(400, "缺少策略描述")

    try:
        evaluation = await evaluate_existing_result(
            user_id=user_id,
            session_id=session_id,
            user_description=user_description,
        )
        return evaluation
    except ValueError as e:
        raise HTTPException(404, str(e))
    except Exception as e:
        raise HTTPException(500, f"评估失败: {e}")


@router.post("/generate-optimized")
async def api_generate_optimized(
    request: Dict[str, Any],
    user_id: str = Depends(get_current_user_id),
):
    """
    生成优化后的策略（人在回路模式）
    基于评估结果和用户反馈生成优化策略，不自动执行回测
    """
    description = request.get("description", "")
    current_strategy = request.get("current_strategy")
    evaluation = request.get("evaluation")
    backtest_result = request.get("backtest_result", {})
    user_feedback = request.get("user_feedback", "")

    if not current_strategy:
        raise HTTPException(400, "缺少当前策略")
    if not evaluation:
        raise HTTPException(400, "缺少评估结果")

    try:
        result = await generate_optimized_strategy(
            user_description=description,
            current_strategy=current_strategy,
            evaluation_result=evaluation,
            backtest_result=backtest_result,
            user_feedback=user_feedback,
        )
        return result
    except Exception as e:
        raise HTTPException(500, f"生成优化策略失败: {e}")
