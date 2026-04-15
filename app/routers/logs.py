"""
日志管理API路由
提供日志查询、过滤和导出功能
"""

import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from app.routers.auth_db import get_current_user
from app.services.log_export_service import get_log_export_service

router = APIRouter(prefix="/system-logs", tags=["系统日志"])
logger = logging.getLogger("webapi")


# 请求模型
class LogReadRequest(BaseModel):
    """日志读取请求"""
    filename: str = Field(..., description="日志文件名")
    lines: int = Field(default=1000, ge=1, le=10000, description="读取行数")
    level: Optional[str] = Field(default=None, description="日志级别过滤")
    keyword: Optional[str] = Field(default=None, description="关键词过滤")
    start_time: Optional[str] = Field(default=None, description="开始时间（ISO格式）")
    end_time: Optional[str] = Field(default=None, description="结束时间（ISO格式）")


class LogExportRequest(BaseModel):
    """日志导出请求"""
    filenames: Optional[List[str]] = Field(default=None, description="要导出的文件名列表（空表示全部）")
    level: Optional[str] = Field(default=None, description="日志级别过滤")
    start_time: Optional[str] = Field(default=None, description="开始时间（ISO格式）")
    end_time: Optional[str] = Field(default=None, description="结束时间（ISO格式）")
    format: str = Field(default="zip", description="导出格式：zip, txt")


# 响应模型
class LogFileInfo(BaseModel):
    """日志文件信息"""
    name: str
    path: str
    size: int
    size_mb: float
    modified_at: str
    type: str


class LogContentResponse(BaseModel):
    """日志内容响应"""
    filename: str
    lines: List[str]
    stats: dict


class LogStatisticsResponse(BaseModel):
    """日志统计响应"""
    total_files: int
    total_size_mb: float
    error_files: int
    recent_errors: List[str]
    log_types: dict


@router.get("/files", response_model=List[LogFileInfo])
async def list_log_files(
    current_user: dict = Depends(get_current_user)
):
    """
    获取所有日志文件列表
    
    返回日志文件的基本信息，包括文件名、大小、修改时间等
    """
    try:
        logger.info(f"📋 用户 {current_user['username']} 查询日志文件列表")
        
        service = get_log_export_service()
        files = service.list_log_files()
        
        return files
        
    except Exception as e:
        logger.error(f"❌ 获取日志文件列表失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取日志文件列表失败: {str(e)}")


@router.post("/read", response_model=LogContentResponse)
async def read_log_file(
    request: LogReadRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    读取日志文件内容
    
    支持过滤条件：
    - lines: 读取的行数（从末尾开始）
    - level: 日志级别（ERROR, WARNING, INFO, DEBUG）
    - keyword: 关键词搜索
    - start_time/end_time: 时间范围
    """
    try:
        logger.info(f"📖 用户 {current_user['username']} 读取日志文件: {request.filename}")
        
        service = get_log_export_service()
        content = service.read_log_file(
            filename=request.filename,
            lines=request.lines,
            level=request.level,
            keyword=request.keyword,
            start_time=request.start_time,
            end_time=request.end_time
        )
        
        return content
        
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"❌ 读取日志文件失败: {e}")
        raise HTTPException(status_code=500, detail=f"读取日志文件失败: {str(e)}")


@router.post("/export")
async def export_logs(
    request: LogExportRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    导出日志文件
    
    支持导出格式：
    - zip: 压缩包（推荐）
    - txt: 合并的文本文件
    
    支持过滤条件：
    - filenames: 指定要导出的文件
    - level: 日志级别过滤
    - start_time/end_time: 时间范围过滤
    """
    try:
        logger.info(f"📤 用户 {current_user['username']} 导出日志文件")
        
        service = get_log_export_service()
        export_path = service.export_logs(
            filenames=request.filenames,
            level=request.level,
            start_time=request.start_time,
            end_time=request.end_time,
            format=request.format
        )
        
        # 返回文件下载
        import os
        filename = os.path.basename(export_path)
        media_type = "application/zip" if request.format == "zip" else "text/plain"
        
        return FileResponse(
            path=export_path,
            filename=filename,
            media_type=media_type,
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"❌ 导出日志文件失败: {e}")
        raise HTTPException(status_code=500, detail=f"导出日志文件失败: {str(e)}")


@router.get("/statistics", response_model=LogStatisticsResponse)
async def get_log_statistics(
    days: int = Query(default=7, ge=1, le=30, description="统计最近几天的日志"),
    current_user: dict = Depends(get_current_user)
):
    """
    获取日志统计信息
    
    返回最近N天的日志统计，包括：
    - 文件数量和总大小
    - 错误日志数量
    - 最近的错误信息
    - 日志类型分布
    """
    try:
        logger.info(f"📊 用户 {current_user['username']} 查询日志统计信息")
        
        service = get_log_export_service()
        stats = service.get_log_statistics(days=days)
        
        return stats
        
    except Exception as e:
        logger.error(f"❌ 获取日志统计失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取日志统计失败: {str(e)}")


@router.delete("/files/{filename}")
async def delete_log_file(
    filename: str,
    current_user: dict = Depends(get_current_user)
):
    """
    删除日志文件
    
    注意：此操作不可恢复，请谨慎使用
    """
    try:
        logger.warning(f"🗑️ 用户 {current_user['username']} 删除日志文件: {filename}")
        
        service = get_log_export_service()

        # 路径安全检查：防止路径遍历
        file_path = service._validate_log_path(filename)
        
        if not file_path.exists():
            raise HTTPException(status_code=404, detail="日志文件不存在")
        
        # 安全检查：只允许删除 .log 文件
        if not filename.endswith('.log') and not '.log.' in filename:
            raise HTTPException(status_code=400, detail="只能删除日志文件")
        
        file_path.unlink()
        
        return {
            "success": True,
            "message": f"日志文件已删除: {filename}"
        }
        
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"❌ 删除日志文件失败: {e}")
        raise HTTPException(status_code=500, detail=f"删除日志文件失败: {str(e)}")
