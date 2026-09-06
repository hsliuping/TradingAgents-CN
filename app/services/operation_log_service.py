"""
操作日志服务
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
from bson import ObjectId

from app.core.database import get_mongo_db
from app.models.operation_log import (
    OperationLogCreate,
    OperationLogResponse,
    OperationLogQuery,
    OperationLogStats,
    convert_objectid_to_str,
    ActionType
)
from app.utils.timezone import now_tz

logger = logging.getLogger("webapi")


class OperationLogService:
    """操作日志服务"""
    
    def __init__(self):
        self.collection_name = "operation_logs"
    
    async def create_log(
        self,
        user_id: str,
        username: str,
        log_data: OperationLogCreate,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> str:
        """创建操作日志"""
        try:
            db = get_mongo_db()

            # 构建日志文档
            # 🔥 使用 naive datetime（不带时区信息），MongoDB 会按原样存储，不会转换为 UTC
            current_time = now_tz().replace(tzinfo=None)  # 移除时区信息，保留本地时间值
            log_doc = {
                "user_id": user_id,
                "username": username,
                "action_type": log_data.action_type,
                "action": log_data.action,
                "details": log_data.details or {},
                "success": log_data.success,
                "error_message": log_data.error_message,
                "duration_ms": log_data.duration_ms,
                "ip_address": ip_address or log_data.ip_address,
                "user_agent": user_agent or log_data.user_agent,
                "session_id": log_data.session_id,
                "timestamp": current_time,  # naive datetime，MongoDB 按原样存储
                "created_at": current_time  # naive datetime，MongoDB 按原样存储
            }
            
            # 插入数据库
            result = await db[self.collection_name].insert_one(log_doc)
            
            logger.info(f"📝 操作日志已记录: {username} - {log_data.action}")
            return str(result.inserted_id)
            
        except Exception as e:
            logger.error(f"创建操作日志失败: {e}")
            return ""
    
    async def get_logs(self, query: OperationLogQuery) -> Tuple[List[OperationLogResponse], int]:
        """获取操作日志列表"""
        try:
            db = get_mongo_db()
            
            # 构建查询条件
            filter_query = {}
            
            # 时间范围筛选
            if query.start_date or query.end_date:
                time_filter = {}
                if query.start_date:
                    # 处理时区，移除Z后缀并直接解析
                    start_str = query.start_date.replace('Z', '')
                    time_filter["$gte"] = datetime.fromisoformat(start_str)
                if query.end_date:
                    # 处理时区，移除Z后缀并直接解析
                    end_str = query.end_date.replace('Z', '')
                    time_filter["$lte"] = datetime.fromisoformat(end_str)
                filter_query["timestamp"] = time_filter
            
            # 操作类型筛选
            if query.action_type:
                filter_query["action_type"] = query.action_type
            
            # 成功状态筛选
            if query.success is not None:
                filter_query["success"] = query.success
            
            # 用户筛选
            if query.user_id:
                filter_query["user_id"] = query.user_id
            
            # 关键词搜索
            if query.keyword:
                filter_query["$or"] = [
                    {"action": {"$regex": query.keyword, "$options": "i"}},
                    {"username": {"$regex": query.keyword, "$options": "i"}},
                    {"details.stock_symbol": {"$regex": query.keyword, "$options": "i"}}
                ]
            
            # 获取总数
            total = await db[self.collection_name].count_documents(filter_query)
            
            # 分页查询
            skip = (query.page - 1) * query.page_size
            cursor = db[self.collection_name].find(filter_query).sort("timestamp", -1).skip(skip).limit(query.page_size)
            
            logs = []
            async for doc in cursor:
                doc = convert_objectid_to_str(doc)
                logs.append(OperationLogResponse(**doc))

            logger.info(f"📋 获取操作日志: 总数={total}, 返回={len(logs)}")
            return logs, total
            
        except Exception as e:
            logger.error(f"获取操作日志失败: {e}")
            raise Exception(f"获取操作日志失败: {str(e)}")
    
    async def get_stats(self, days: int = 30) -> OperationLogStats:
        """获取操作日志统计"""
        try:
            db = get_mongo_db()
            
            # 时间范围（使用中国时区）
            start_date = now_tz() - timedelta(days=days)
            time_filter = {"timestamp": {"$gte": start_date}}
            
            # 基础统计
            total_logs = await db[self.collection_name].count_documents(time_filter)
            success_logs = await db[self.collection_name].count_documents({**time_filter, "success": True})
            failed_logs = total_logs - success_logs
            success_rate = (success_logs / total_logs * 100) if total_logs > 0 else 0
            
            # 操作类型分布
            action_type_pipeline = [
                {"$match": time_filter},
                {"$group": {"_id": "$action_type", "count": {"$sum": 1}}},
                {"$sort": {"count": -1}}
            ]
            action_type_cursor = db[self.collection_name].aggregate(action_type_pipeline)
            action_type_distribution = {}
            async for doc in action_type_cursor:
                action_type_distribution[doc["_id"]] = doc["count"]
            
            # 小时分布统计
            hourly_pipeline = [
                {"$match": time_filter},
                {
                    "$group": {
                        "_id": {"$hour": "$timestamp"},
                        "count": {"$sum": 1}
                    }
                },
                {"$sort": {"_id": 1}}
            ]
            hourly_cursor = db[self.collection_name].aggregate(hourly_pipeline)
            hourly_distribution = []
            hourly_data = {i: 0 for i in range(24)}  # 初始化24小时
            
            async for doc in hourly_cursor:
                hourly_data[doc["_id"]] = doc["count"]
            
            for hour, count in hourly_data.items():
                hourly_distribution.append({
                    "hour": f"{hour:02d}:00",
                    "count": count
                })
            
            stats = OperationLogStats(
                total_logs=total_logs,
                success_logs=success_logs,
                failed_logs=failed_logs,
                success_rate=round(success_rate, 2),
                action_type_distribution=action_type_distribution,
                hourly_distribution=hourly_distribution
            )
            
            logger.info(f"📊 操作日志统计: 总数={total_logs}, 成功率={success_rate:.1f}%")
            return stats
            
        except Exception as e:
            logger.error(f"获取操作日志统计失败: {e}")
            raise Exception(f"获取操作日志统计失败: {str(e)}")
    
    async def clear_logs(self, days: Optional[int] = None, action_type: Optional[str] = None) -> Dict[str, Any]:
        """清空操作日志"""
        try:
            db = get_mongo_db()
            
            # 构建删除条件
            delete_filter = {}
            
            if days is not None:
                # 只删除N天前的日志
                cutoff_date = datetime.now() - timedelta(days=days)
                delete_filter["timestamp"] = {"$lt": cutoff_date}
            
            if action_type:
                # 只删除指定类型的日志
                delete_filter["action_type"] = action_type
            
            # 执行删除
            result = await db[self.collection_name].delete_many(delete_filter)
            
            logger.info(f"🗑️ 清空操作日志: 删除了 {result.deleted_count} 条记录")
            
            return {
                "deleted_count": result.deleted_count,
                "filter": delete_filter
            }
            
        except Exception as e:
            logger.error(f"清空操作日志失败: {e}")
            raise Exception(f"清空操作日志失败: {str(e)}")
    
    async def get_log_by_id(self, log_id: str) -> Optional[OperationLogResponse]:
        """根据ID获取操作日志"""
        try:
            db = get_mongo_db()

            doc = await db[self.collection_name].find_one({"_id": ObjectId(log_id)})
            if not doc:
                return None

            doc = convert_objectid_to_str(doc)
            return OperationLogResponse(**doc)

        except Exception as e:
            logger.error(f"获取操作日志详情失败: {e}")
            return None


# 全局服务实例
_operation_log_service: Optional[OperationLogService] = None


def get_operation_log_service() -> OperationLogService:
    """获取操作日志服务实例"""
    global _operation_log_service
    if _operation_log_service is None:
        _operation_log_service = OperationLogService()
    return _operation_log_service


# 便捷函数
async def log_operation(
    user_id: str,
    username: str,
    action_type: str,
    action: str,
    details: Optional[Dict[str, Any]] = None,
    success: bool = True,
    error_message: Optional[str] = None,
    duration_ms: Optional[int] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    session_id: Optional[str] = None
) -> str:
    """记录操作日志的便捷函数"""
    service = get_operation_log_service()
    log_data = OperationLogCreate(
        action_type=action_type,
        action=action,
        details=details,
        success=success,
        error_message=error_message,
        duration_ms=duration_ms,
        ip_address=ip_address,
        user_agent=user_agent,
        session_id=session_id
    )
    return await service.create_log(user_id, username, log_data, ip_address, user_agent)
