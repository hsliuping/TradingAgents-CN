"""
数据库管理API路由
"""

import logging
import json
import os
from datetime import datetime
from typing import Dict, Any, List
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from fastapi.responses import FileResponse
from pydantic import BaseModel

from app.routers.auth_db import get_current_user
from app.core.database import get_mongo_db, get_redis_client
from app.services.database_service import DatabaseService

router = APIRouter(prefix="/database", tags=["数据库管理"])
logger = logging.getLogger("webapi")

# 请求模型
class BackupRequest(BaseModel):
    """备份请求"""
    name: str
    collections: List[str] = []  # 空列表表示备份所有集合

class ImportRequest(BaseModel):
    """导入请求"""
    collection: str
    format: str = "json"  # json, csv
    overwrite: bool = False

class ExportRequest(BaseModel):
    """导出请求"""
    collections: List[str] = []  # 空列表表示导出所有集合
    format: str = "json"  # json, csv
    sanitize: bool = False  # 是否脱敏（清空敏感字段，用于演示系统）

# 响应模型
class DatabaseStatusResponse(BaseModel):
    """数据库状态响应"""
    mongodb: Dict[str, Any]
    redis: Dict[str, Any]

class DatabaseStatsResponse(BaseModel):
    """数据库统计响应"""
    total_collections: int
    total_documents: int
    total_size: int
    collections: List[Dict[str, Any]]

class BackupResponse(BaseModel):
    """备份响应"""
    id: str
    name: str
    size: int
    created_at: str
    collections: List[str]

# 数据库服务实例
database_service = DatabaseService()

@router.get("/status")
async def get_database_status(
    current_user: dict = Depends(get_current_user)
):
    """获取数据库连接状态"""
    try:
        logger.info(f"🔍 用户 {current_user['username']} 请求数据库状态")
        status_info = await database_service.get_database_status()
        return {
            "success": True,
            "message": "获取数据库状态成功",
            "data": status_info
        }
    except Exception as e:
        logger.error(f"获取数据库状态失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取数据库状态失败: {str(e)}"
        )

@router.get("/stats")
async def get_database_stats(
    current_user: dict = Depends(get_current_user)
):
    """获取数据库统计信息"""
    try:
        logger.info(f"📊 用户 {current_user['username']} 请求数据库统计")
        stats = await database_service.get_database_stats()
        return {
            "success": True,
            "message": "获取数据库统计成功",
            "data": stats
        }
    except Exception as e:
        logger.error(f"获取数据库统计失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取数据库统计失败: {str(e)}"
        )

@router.post("/test")
async def test_database_connections(
    current_user: dict = Depends(get_current_user)
):
    """测试数据库连接"""
    try:
        logger.info(f"🧪 用户 {current_user['username']} 测试数据库连接")
        results = await database_service.test_connections()
        return {
            "success": True,
            "message": "数据库连接测试完成",
            "data": results
        }
    except Exception as e:
        logger.error(f"测试数据库连接失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"测试数据库连接失败: {str(e)}"
        )

@router.post("/backup")
async def create_backup(
    request: BackupRequest,
    current_user: dict = Depends(get_current_user)
):
    """创建数据库备份"""
    try:
        logger.info(f"💾 用户 {current_user['username']} 创建备份: {request.name}")
        backup_info = await database_service.create_backup(
            name=request.name,
            collections=request.collections,
            user_id=current_user['id']
        )
        return {
            "success": True,
            "message": "备份创建成功",
            "data": backup_info
        }
    except Exception as e:
        logger.error(f"创建备份失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"创建备份失败: {str(e)}"
        )

@router.get("/backups")
async def list_backups(
    current_user: dict = Depends(get_current_user)
):
    """获取备份列表"""
    try:
        logger.info(f"📋 用户 {current_user['username']} 获取备份列表")
        backups = await database_service.list_backups()
        return {
            "success": True,
            "data": backups
        }
    except Exception as e:
        logger.error(f"获取备份列表失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取备份列表失败: {str(e)}"
        )

@router.post("/import")
async def import_data(
    file: UploadFile = File(...),
    collection: str = "imported_data",
    format: str = "json",
    overwrite: bool = False,
    current_user: dict = Depends(get_current_user)
):
    """导入数据"""
    try:
        logger.info(f"📥 用户 {current_user['username']} 导入数据到集合: {collection}")
        logger.info(f"   文件名: {file.filename}")
        logger.info(f"   格式: {format}")
        logger.info(f"   覆盖模式: {overwrite}")

        # 读取文件内容
        content = await file.read()
        logger.info(f"   文件大小: {len(content)} 字节")

        result = await database_service.import_data(
            content=content,
            collection=collection,
            format=format,
            overwrite=overwrite,
            filename=file.filename
        )

        logger.info(f"✅ 导入成功: {result}")

        return {
            "success": True,
            "message": "数据导入成功",
            "data": result
        }
    except Exception as e:
        logger.error(f"❌ 导入数据失败: {e}")
        import traceback
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"导入数据失败: {str(e)}"
        )

@router.post("/export")
async def export_data(
    request: ExportRequest,
    current_user: dict = Depends(get_current_user)
):
    """导出数据"""
    try:
        sanitize_info = "（脱敏模式）" if request.sanitize else ""
        logger.info(f"📤 用户 {current_user['username']} 导出数据{sanitize_info}")

        file_path = await database_service.export_data(
            collections=request.collections,
            format=request.format,
            sanitize=request.sanitize
        )

        return FileResponse(
            path=file_path,
            filename=os.path.basename(file_path),
            media_type='application/octet-stream'
        )
    except Exception as e:
        logger.error(f"导出数据失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"导出数据失败: {str(e)}"
        )

@router.delete("/backups/{backup_id}")
async def delete_backup(
    backup_id: str,
    current_user: dict = Depends(get_current_user)
):
    """删除备份"""
    try:
        logger.info(f"🗑️ 用户 {current_user['username']} 删除备份: {backup_id}")
        await database_service.delete_backup(backup_id)
        return {
            "success": True,
            "message": "备份删除成功"
        }
    except Exception as e:
        logger.error(f"删除备份失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"删除备份失败: {str(e)}"
        )

@router.post("/cleanup")
async def cleanup_old_data(
    days: int = 30,
    current_user: dict = Depends(get_current_user)
):
    """清理旧数据"""
    try:
        logger.info(f"🧹 用户 {current_user['username']} 清理 {days} 天前的数据")
        result = await database_service.cleanup_old_data(days)
        return {
            "success": True,
            "message": f"清理完成，删除了 {result['deleted_count']} 条记录",
            "data": result
        }
    except Exception as e:
        logger.error(f"清理数据失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"清理数据失败: {str(e)}"
        )

@router.post("/cleanup/analysis")
async def cleanup_analysis_results(
    days: int = 30,
    current_user: dict = Depends(get_current_user)
):
    """清理过期分析结果"""
    try:
        logger.info(f"🧹 用户 {current_user['username']} 清理 {days} 天前的分析结果")
        result = await database_service.cleanup_analysis_results(days)
        return {
            "success": True,
            "message": f"分析结果清理完成，删除了 {result['deleted_count']} 条记录",
            "data": result
        }
    except Exception as e:
        logger.error(f"清理分析结果失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"清理分析结果失败: {str(e)}"
        )

@router.post("/cleanup/logs")
async def cleanup_operation_logs(
    days: int = 90,
    current_user: dict = Depends(get_current_user)
):
    """清理操作日志"""
    try:
        logger.info(f"🧹 用户 {current_user['username']} 清理 {days} 天前的操作日志")
        result = await database_service.cleanup_operation_logs(days)
        return {
            "success": True,
            "message": f"操作日志清理完成，删除了 {result['deleted_count']} 条记录",
            "data": result
        }
    except Exception as e:
        logger.error(f"清理操作日志失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"清理操作日志失败: {str(e)}"
        )
