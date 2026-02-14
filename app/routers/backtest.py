"""
回测 API 路由
POST /api/backtest/analyze  - AI 分析策略可行性
POST /api/backtest/generate - 生成策略 DSL
POST /api/backtest/run      - 执行回测
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
    list_sessions,
    delete_session,
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
    """生成策略 DSL"""
    desc = body.get("description") or body.get("text") or ""
    if not desc:
        raise HTTPException(400, "请提供策略描述 description")
    try:
        dsl = await generate(user_id, desc)
        return {"strategy": dsl}
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.post("/run")
async def api_run(
    body: Dict[str, Any],
    user_id: str = Depends(get_current_user_id),
):
    """执行回测"""
    strategy = body.get("strategy")
    if not strategy:
        raise HTTPException(400, "请提供 strategy DSL")
    session_id = body.get("session_id")
    result = await run_backtest(user_id, strategy, session_id)
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
    """列出回测会话"""
    return await list_sessions(user_id, limit)


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
