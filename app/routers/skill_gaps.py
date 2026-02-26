"""
Skill 缺口感知 API 路由

提供缺口报告的列表、详情、忽略、解决等操作接口。
端点前缀: /api/skill-gaps
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.routers.auth_db import get_current_user
from app.services.skill_gap_service import get_skill_gap_service

logger = logging.getLogger("webapi")

router = APIRouter(prefix="/api/skill-gaps", tags=["skill-gaps"])


# =============================================================================
# 请求模型
# =============================================================================


class DismissRequest(BaseModel):
    """忽略缺口请求"""
    pass


class ResolveRequest(BaseModel):
    """标记已解决请求"""
    skill_id: str = ""


# =============================================================================
# 端点
# =============================================================================


@router.get("", summary="获取缺口报告列表")
async def list_gaps(
    status: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
    user: dict = Depends(get_current_user),
):
    """分页获取当前用户的工具缺口报告列表"""
    svc = get_skill_gap_service()
    return await svc.list_gaps(user["id"], status, page, page_size)


@router.get("/stats", summary="缺口统计")
async def get_stats(user: dict = Depends(get_current_user)):
    """获取当前用户缺口报告的统计数据（按状态/类型分组）"""
    svc = get_skill_gap_service()
    return await svc.get_stats(user["id"])


@router.get("/{report_id}", summary="获取单个缺口报告")
async def get_gap(report_id: str, user: dict = Depends(get_current_user)):
    """获取指定缺口报告的详细信息"""
    svc = get_skill_gap_service()
    doc = await svc.get_gap(report_id)
    if not doc:
        raise HTTPException(status_code=404, detail="缺口报告不存在")
    if doc.get("user_id") != user["id"]:
        raise HTTPException(status_code=403, detail="无权访问该报告")
    return doc


@router.post("/{report_id}/dismiss", summary="忽略缺口")
async def dismiss_gap(report_id: str, user: dict = Depends(get_current_user)):
    """将缺口报告标记为已忽略，30天内不再重复上报同名工具"""
    svc = get_skill_gap_service()
    ok = await svc.dismiss_gap(report_id, user["id"])
    if not ok:
        raise HTTPException(status_code=404, detail="缺口报告不存在或无权操作")
    return {"success": True, "message": "已忽略"}


@router.post("/{report_id}/resolve", summary="标记已解决")
async def resolve_gap(
    report_id: str,
    body: ResolveRequest,
    user: dict = Depends(get_current_user),
):
    """将缺口报告标记为已解决，可关联创建的 Skill ID"""
    svc = get_skill_gap_service()
    ok = await svc.resolve_gap(report_id, user["id"], body.skill_id)
    if not ok:
        raise HTTPException(status_code=404, detail="缺口报告不存在或无权操作")
    return {"success": True, "message": "已标记为解决"}


@router.get("/{report_id}/create-skill-params", summary="获取创建 Skill 预填参数")
async def get_create_skill_params(
    report_id: str,
    user: dict = Depends(get_current_user),
):
    """
    根据缺口报告生成 Skill 工坊的预填参数，
    前端可直接跳转到 /workflow/skill-generation/create 并传入这些参数。
    """
    svc = get_skill_gap_service()
    doc = await svc.get_gap(report_id)
    if not doc:
        raise HTTPException(status_code=404, detail="缺口报告不存在")
    if doc.get("user_id") != user["id"]:
        raise HTTPException(status_code=403, detail="无权访问该报告")

    gap = doc.get("gap", {})
    tool_name = gap.get("tool_name", "")
    gap_type = gap.get("type", "")
    error_msg = gap.get("error_message", "")
    source = doc.get("source", {})

    # 构造预填参数
    description = f"为 Agent [{source.get('agent_id', '')}] 提供工具 `{tool_name}` 的功能。"
    if gap_type == "tool_execution_error" and error_msg:
        description += f"\n\n原始错误: {error_msg}"

    return {
        "prefill": {
            "name": tool_name,
            "description": description,
            "tags": ["auto-suggested", gap_type],
        },
        "report_id": report_id,
    }

