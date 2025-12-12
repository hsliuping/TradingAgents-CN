"""
操作日志API路由
"""

import logging
from typing import Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from fastapi.responses import StreamingResponse

from app.routers.auth_db import get_current_user
from app.services.operation_log_service import get_operation_log_service
from app.models.operation_log import (
    OperationLogQuery,
    OperationLogListResponse,
    OperationLogStatsResponse,
    ClearLogsRequest,
    ClearLogsResponse,
    OperationLogCreate
)

router = APIRouter(prefix="/logs", tags=["操作日志"])
logger = logging.getLogger("webapi")


@router.get("/list", response_model=OperationLogListResponse)
async def get_operation_logs(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    start_date: str = Query(None, description="开始日期"),
    end_date: str = Query(None, description="结束日期"),
    action_type: str = Query(None, description="操作类型"),
    success: bool = Query(None, description="是否成功"),
    keyword: str = Query(None, description="关键词搜索"),
    current_user: dict = Depends(get_current_user)
):
    """获取操作日志列表"""
    try:
        logger.info(f"🔍 用户 {current_user['username']} 获取操作日志列表")
        
        service = get_operation_log_service()
        query = OperationLogQuery(
            page=page,
            page_size=page_size,
            start_date=start_date,
            end_date=end_date,
            action_type=action_type,
            success=success,
            keyword=keyword
        )
        
        logs, total = await service.get_logs(query)
        
        return OperationLogListResponse(
            success=True,
            data={
                "logs": [log.dict() for log in logs],
                "total": total,
                "page": page,
                "page_size": page_size,
                "total_pages": (total + page_size - 1) // page_size
            },
            message="获取操作日志列表成功"
        )
        
    except Exception as e:
        logger.error(f"获取操作日志列表失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取操作日志列表失败: {str(e)}"
        )


@router.get("/stats", response_model=OperationLogStatsResponse)
async def get_operation_log_stats(
    days: int = Query(30, ge=1, le=365, description="统计天数"),
    current_user: dict = Depends(get_current_user)
):
    """获取操作日志统计"""
    try:
        logger.info(f"📊 用户 {current_user['username']} 获取操作日志统计")
        
        service = get_operation_log_service()
        stats = await service.get_stats(days)
        
        return OperationLogStatsResponse(
            success=True,
            data=stats,
            message="获取操作日志统计成功"
        )
        
    except Exception as e:
        logger.error(f"获取操作日志统计失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取操作日志统计失败: {str(e)}"
        )


@router.get("/{log_id}")
async def get_operation_log_detail(
    log_id: str,
    current_user: dict = Depends(get_current_user)
):
    """获取操作日志详情"""
    try:
        logger.info(f"🔍 用户 {current_user['username']} 获取操作日志详情: {log_id}")
        
        service = get_operation_log_service()
        log = await service.get_log_by_id(log_id)
        
        if not log:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="操作日志不存在"
            )
        
        return {
            "success": True,
            "data": log.dict(),
            "message": "获取操作日志详情成功"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取操作日志详情失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取操作日志详情失败: {str(e)}"
        )


@router.post("/clear", response_model=ClearLogsResponse)
async def clear_operation_logs(
    request: ClearLogsRequest,
    current_user: dict = Depends(get_current_user)
):
    """清空操作日志"""
    try:
        logger.info(f"🗑️ 用户 {current_user['username']} 清空操作日志")
        
        service = get_operation_log_service()
        result = await service.clear_logs(
            days=request.days,
            action_type=request.action_type
        )
        
        message = f"清空操作日志成功，删除了 {result['deleted_count']} 条记录"
        if request.days:
            message += f"（{request.days}天前的日志）"
        if request.action_type:
            message += f"（类型: {request.action_type}）"
        
        return ClearLogsResponse(
            success=True,
            data=result,
            message=message
        )
        
    except Exception as e:
        logger.error(f"清空操作日志失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"清空操作日志失败: {str(e)}"
        )


@router.post("/create")
async def create_operation_log(
    log_data: OperationLogCreate,
    request: Request,
    current_user: dict = Depends(get_current_user)
):
    """手动创建操作日志"""
    try:
        logger.info(f"📝 用户 {current_user['username']} 手动创建操作日志")
        
        service = get_operation_log_service()
        
        # 获取客户端信息
        ip_address = request.client.host if request.client else None
        user_agent = request.headers.get("user-agent")
        
        log_id = await service.create_log(
            user_id=current_user["id"],
            username=current_user["username"],
            log_data=log_data,
            ip_address=ip_address,
            user_agent=user_agent
        )
        
        return {
            "success": True,
            "data": {"log_id": log_id},
            "message": "创建操作日志成功"
        }
        
    except Exception as e:
        logger.error(f"创建操作日志失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"创建操作日志失败: {str(e)}"
        )


@router.get("/export/csv")
async def export_logs_csv(
    start_date: str = Query(None, description="开始日期"),
    end_date: str = Query(None, description="结束日期"),
    action_type: str = Query(None, description="操作类型"),
    current_user: dict = Depends(get_current_user)
):
    """导出操作日志为CSV"""
    try:
        logger.info(f"📤 用户 {current_user['username']} 导出操作日志CSV")
        
        service = get_operation_log_service()
        query = OperationLogQuery(
            page=1,
            page_size=10000,  # 导出时获取更多数据
            start_date=start_date,
            end_date=end_date,
            action_type=action_type
        )
        
        logs, _ = await service.get_logs(query)
        
        # 生成CSV内容
        import csv
        import io
        
        output = io.StringIO()
        writer = csv.writer(output)
        
        # 写入表头
        writer.writerow([
            "时间", "用户", "操作类型", "操作内容", "状态", "耗时(ms)", "IP地址", "错误信息"
        ])
        
        # 写入数据
        for log in logs:
            writer.writerow([
                log.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                log.username,
                log.action_type,
                log.action,
                "成功" if log.success else "失败",
                log.duration_ms or "",
                log.ip_address or "",
                log.error_message or ""
            ])
        
        output.seek(0)
        
        # 返回CSV文件
        from datetime import datetime
        filename = f"operation_logs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        
        return StreamingResponse(
            io.BytesIO(output.getvalue().encode('utf-8-sig')),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
        
    except Exception as e:
        logger.error(f"导出操作日志CSV失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"导出操作日志CSV失败: {str(e)}"
        )
