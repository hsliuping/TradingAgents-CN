"""Agent 执行轨迹查询 API（P1 机器可读执行轨迹 - 前端查看入口）

提供执行轨迹的列表查询和单条详情端点。轨迹存于 agent_execution_traces 集合，
每次 manager agent 执行时自动写入（输入快照 / Prompt 全文 / LLM 原始返回 /
解析结果 / 校验结果 / Token 用量）。

端点：
  GET /api/execution-traces                列表（支持 task_id/agent_id/validation_status/success/日期过滤 + 分页）
  GET /api/execution-traces/{trace_id}     单条详情（含 Prompt 全文、LLM 原始返回全文）

设计说明：
- 列表接口默认不返回 *_full 全文字段（控制返回体大小），详情接口返回全文
- 主要入口：任务中心按 task_id 跳转，查看某次分析的所有 Agent 执行轨迹
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from app.core.response import ok
from app.routers.auth_db import get_current_user
from app.services.execution_trace_service import execution_trace_service

logger = logging.getLogger("webapi")

router = APIRouter(
    prefix="/api/execution-traces",
    tags=["execution-traces"],
    dependencies=[Depends(get_current_user)],
)


def _strip_full_fields(d: Dict[str, Any]) -> Dict[str, Any]:
    """列表项剥离全文字段（控制返回体大小，全文只在详情接口返回）"""
    prompts = d.get("prompts")
    if isinstance(prompts, dict):
        prompts.pop("system_prompt_full", None)
        prompts.pop("user_prompt_full", None)
    output = d.get("output")
    if isinstance(output, dict):
        output.pop("output_raw_full", None)
    return d


def _parse_date(s: Optional[str]) -> Optional[datetime]:
    """解析 ISO 日期字符串（兼容 '2026-07-29' 和 '2026-07-29T00:00:00'）"""
    if not s:
        return None
    try:
        return datetime.fromisoformat(s)
    except ValueError:
        return None


@router.get("")
async def list_traces(
    task_id: Optional[str] = Query(None, description="按 task_id 过滤（任务中心跳转核心参数）"),
    agent_id: Optional[str] = Query(None, description="按 agent_id 过滤"),
    workflow_id: Optional[str] = Query(None, description="按 workflow_id 过滤"),
    validation_status: Optional[str] = Query(None, description="按校验状态过滤 (passed/failed)"),
    success: Optional[bool] = Query(None, description="按执行成功/失败过滤"),
    start_date: Optional[str] = Query(None, description="开始日期 (ISO 格式)"),
    end_date: Optional[str] = Query(None, description="结束日期 (ISO 格式)"),
    skip: int = Query(0, ge=0, description="分页偏移"),
    limit: int = Query(100, ge=1, le=500, description="每页数量"),
):
    """获取执行轨迹列表（支持多维过滤 + 分页）

    列表不返回 *_full 全文字段，点击单条详情时才返回全文。
    """
    try:
        sd = _parse_date(start_date)
        ed = _parse_date(end_date)

        traces = await execution_trace_service.get_traces(
            agent_id=agent_id,
            workflow_id=workflow_id,
            task_id=task_id,
            validation_status=validation_status,
            success=success,
            start_date=sd,
            end_date=ed,
            skip=skip,
            limit=limit,
        )
        total = await execution_trace_service.count_traces(
            agent_id=agent_id,
            workflow_id=workflow_id,
            task_id=task_id,
            validation_status=validation_status,
            success=success,
            start_date=sd,
            end_date=ed,
        )
        items: List[Dict[str, Any]] = [
            _strip_full_fields(t.model_dump(mode="json")) for t in traces
        ]
        return ok({"items": items, "total": total}, message=f"共 {total} 条轨迹")
    except Exception as e:
        logger.error(f"获取执行轨迹列表失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{trace_id}")
async def get_trace(trace_id: str):
    """获取单条执行轨迹详情（含 Prompt 全文、LLM 原始返回全文）"""
    trace = await execution_trace_service.get_trace_by_id(trace_id)
    if trace is None:
        raise HTTPException(status_code=404, detail=f"轨迹不存在: {trace_id}")
    return ok(trace.model_dump(mode="json"))
