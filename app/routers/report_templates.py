"""
报告模板 API 路由

提供报告模板的 CRUD 接口和工作流报告生成接口。
"""
import logging
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query

from app.core.database import get_mongo_db
from app.routers.auth_db import get_current_user
from app.models.report_template import (
    ReportTemplateCreate,
    ReportTemplateUpdate,
    ReportTemplateResponse
)
from app.services.report_template_service import ReportTemplateService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/report-templates", tags=["报告模板"])


def get_service():
    """获取报告模板服务实例"""
    db = get_mongo_db()
    return ReportTemplateService(db)


@router.post("", response_model=ReportTemplateResponse)
async def create_template(
    data: ReportTemplateCreate,
    user: dict = Depends(get_current_user),
    service: ReportTemplateService = Depends(get_service)
):
    """创建报告模板"""
    try:
        user_id = str(user.get("_id")) if user else None
        return await service.create_template(data, user_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"❌ 创建报告模板失败: {e}")
        raise HTTPException(status_code=500, detail=f"创建失败: {str(e)}")


@router.get("", response_model=List[ReportTemplateResponse])
async def list_templates(
    workflow_id: Optional[str] = Query(None, description="工作流ID筛选"),
    status: Optional[str] = Query(None, description="状态筛选: active, inactive"),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    user: dict = Depends(get_current_user),
    service: ReportTemplateService = Depends(get_service)
):
    """列出报告模板"""
    return await service.list_templates(
        workflow_id=workflow_id,
        status=status,
        skip=skip,
        limit=limit
    )


@router.get("/{template_id}", response_model=ReportTemplateResponse)
async def get_template(
    template_id: str,
    user: dict = Depends(get_current_user),
    service: ReportTemplateService = Depends(get_service)
):
    """获取报告模板详情"""
    template = await service.get_template(template_id)
    if not template:
        raise HTTPException(status_code=404, detail="模板不存在")
    return template


@router.get("/workflow/{workflow_id}", response_model=ReportTemplateResponse)
async def get_template_by_workflow(
    workflow_id: str,
    user: dict = Depends(get_current_user),
    service: ReportTemplateService = Depends(get_service)
):
    """根据工作流ID获取报告模板"""
    template = await service.get_template_by_workflow(workflow_id)
    if not template:
        raise HTTPException(status_code=404, detail=f"工作流 {workflow_id} 没有关联的报告模板")
    return template


@router.put("/{template_id}", response_model=ReportTemplateResponse)
async def update_template(
    template_id: str,
    data: ReportTemplateUpdate,
    user: dict = Depends(get_current_user),
    service: ReportTemplateService = Depends(get_service)
):
    """更新报告模板"""
    result = await service.update_template(template_id, data)
    if not result:
        raise HTTPException(status_code=404, detail="模板不存在")
    return result


@router.delete("/{template_id}")
async def delete_template(
    template_id: str,
    user: dict = Depends(get_current_user),
    service: ReportTemplateService = Depends(get_service)
):
    """删除报告模板"""
    success = await service.delete_template(template_id)
    if not success:
        raise HTTPException(status_code=404, detail="模板不存在")
    return {"message": "删除成功", "template_id": template_id}


@router.post("/generate")
async def generate_report(
    workflow_id: str = Query(..., description="工作流ID"),
    agent_outputs: Dict[str, Any] = None,
    use_llm: bool = Query(True, description="是否使用 LLM 生成报告"),
    user: dict = Depends(get_current_user)
):
    """
    根据工作流和 Agent 输出生成报告
    
    通常由工作流执行完成后自动调用，也可手动调用测试。
    """
    from core.workflow.report_generator import ReportGenerator
    
    db = get_mongo_db()
    generator = ReportGenerator(db)
    
    try:
        report = await generator.generate_report(
            workflow_id=workflow_id,
            agent_outputs=agent_outputs or {},
            use_llm=use_llm
        )
        return {
            "success": True,
            "report": report
        }
    except Exception as e:
        logger.error(f"❌ 报告生成失败: {e}")
        raise HTTPException(status_code=500, detail=f"报告生成失败: {str(e)}")

