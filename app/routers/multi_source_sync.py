"""
Multi-source synchronization API routes
Provides endpoints for multi-source stock data synchronization
"""
import asyncio
import logging
from typing import Dict, List, Optional, Any, Union
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from app.routers.auth_db import get_current_user
from app.services.multi_source_basics_sync_service import get_multi_source_sync_service
from app.services.data_sources.manager import DataSourceManager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/sync/multi-source", tags=["Multi-Source Sync"])


class SyncRequest(BaseModel):
    """同步请求模型"""
    force: bool = False
    preferred_sources: Optional[List[str]] = None


class SyncResponse(BaseModel):
    """同步响应模型"""
    success: bool
    message: str
    data: Union[Dict[str, Any], List[Any], Any]


class DataSourceStatus(BaseModel):
    """数据源状态模型"""
    name: str
    priority: int
    available: bool
    description: str


@router.get("/sources/status")
async def get_data_sources_status(current_user: dict = Depends(get_current_user)):
    """获取所有数据源的状态"""
    try:
        manager = DataSourceManager()
        available_adapters = manager.get_available_adapters()
        all_adapters = manager.adapters

        status_list = []
        for adapter in all_adapters:
            is_available = adapter in available_adapters

            # 根据数据源类型提供描述
            descriptions = {
                "tushare": "专业金融数据API，提供高质量的A股数据和财务指标",
                "akshare": "开源金融数据库，提供基础的股票信息",
                "baostock": "免费开源的证券数据平台，提供历史数据"
            }

            status_item = {
                "name": adapter.name,
                "priority": adapter.priority,
                "available": is_available,
                "description": descriptions.get(adapter.name, f"{adapter.name}数据源")
            }

            # 添加 Token 来源信息（仅 Tushare）
            if adapter.name == "tushare" and is_available and hasattr(adapter, 'get_token_source'):
                token_source = adapter.get_token_source()
                if token_source:
                    status_item["token_source"] = token_source
                    if token_source == 'database':
                        status_item["description"] += " (Token来源: 数据库)"
                    elif token_source == 'env':
                        status_item["description"] += " (Token来源: .env)"

            status_list.append(status_item)

        return SyncResponse(
            success=True,
            message="Data sources status retrieved successfully",
            data=status_list
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get data sources status: {str(e)}")


@router.get("/sources/current")
async def get_current_data_source(current_user: dict = Depends(get_current_user)):
    """获取当前正在使用的数据源（优先级最高且可用的）"""
    try:
        manager = DataSourceManager()
        available_adapters = manager.get_available_adapters()

        if not available_adapters:
            return SyncResponse(
                success=False,
                message="No available data sources",
                data={"name": None, "priority": None}
            )

        # 获取优先级最高的可用数据源（优先级数字越大越高）
        current_adapter = max(available_adapters, key=lambda x: x.priority)

        # 根据数据源类型提供描述
        descriptions = {
            "tushare": "专业金融数据API",
            "akshare": "开源金融数据库",
            "baostock": "免费证券数据平台"
        }

        result = {
            "name": current_adapter.name,
            "priority": current_adapter.priority,
            "description": descriptions.get(current_adapter.name, current_adapter.name)
        }

        # 添加 Token 来源信息（仅 Tushare）
        if current_adapter.name == "tushare" and hasattr(current_adapter, 'get_token_source'):
            token_source = current_adapter.get_token_source()
            if token_source:
                result["token_source"] = token_source
                if token_source == 'database':
                    result["token_source_display"] = "数据库配置"
                elif token_source == 'env':
                    result["token_source_display"] = ".env 配置"

        return SyncResponse(
            success=True,
            message="Current data source retrieved successfully",
            data=result
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get current data source: {str(e)}")


@router.get("/status")
async def get_sync_status(current_user: dict = Depends(get_current_user)):
    """获取多数据源同步状态"""
    try:
        service = get_multi_source_sync_service()
        status = await service.get_status()
        
        return SyncResponse(
            success=True,
            message="Status retrieved successfully",
            data=status
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get sync status: {str(e)}")


@router.post("/stock_basics/run")
async def run_stock_basics_sync(
    force: bool = Query(False, description="是否强制运行同步"),
    preferred_sources: Optional[str] = Query(None, description="优先使用的数据源，用逗号分隔"),
    current_user: dict = Depends(get_current_user)
):
    """运行多数据源股票基础信息同步"""
    try:
        service = get_multi_source_sync_service()

        # 解析优先数据源
        sources_list = None
        if preferred_sources and isinstance(preferred_sources, str):
            sources_list = [s.strip() for s in preferred_sources.split(",") if s.strip()]

        # 运行同步（同步执行，前端已设置10分钟超时）
        result = await service.run_full_sync(force=force, preferred_sources=sources_list)

        # 判断是否成功
        success = result.get("status") in ["success", "success_with_errors"]
        message = "Synchronization completed successfully"

        if result.get("status") == "success_with_errors":
            message = f"Synchronization completed with {result.get('errors', 0)} errors"
        elif result.get("status") == "failed":
            message = f"Synchronization failed: {result.get('message', 'Unknown error')}"
            success = False
        elif result.get("status") == "running":
            message = "Synchronization is already running"

        return SyncResponse(
            success=success,
            message=message,
            data=result
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to run synchronization: {str(e)}")


async def _test_single_adapter(adapter) -> dict:
    """
    测试单个数据源适配器的连通性
    只做轻量级连通性测试，不获取完整数据
    """
    result = {
        "name": adapter.name,
        "priority": adapter.priority,
        "available": False,
        "message": "连接失败"
    }

    # 连通性测试超时时间（秒）
    test_timeout = 10

    try:
        # 测试连通性 - 强制重新连接以使用最新配置
        logger.info(f"🧪 测试 {adapter.name} 连通性 (超时: {test_timeout}秒)...")

        try:
            # 对于 Tushare，强制重新连接以使用最新的数据库配置
            if adapter.name == "tushare" and hasattr(adapter, '_provider'):
                logger.info(f"🔄 强制 {adapter.name} 重新连接以使用最新配置...")
                provider = adapter._provider
                if provider:
                    # 重置连接状态
                    provider.connected = False
                    provider.token_source = None
                    # 重新连接
                    await asyncio.wait_for(
                        asyncio.to_thread(provider.connect_sync),
                        timeout=test_timeout
                    )

            # 在线程池中运行 is_available() 检查
            is_available = await asyncio.wait_for(
                asyncio.to_thread(adapter.is_available),
                timeout=test_timeout
            )

            if is_available:
                result["available"] = True

                # 获取 Token 来源（仅 Tushare）
                token_source = None
                if adapter.name == "tushare" and hasattr(adapter, 'get_token_source'):
                    token_source = adapter.get_token_source()

                if token_source == 'database':
                    result["message"] = "✅ 连接成功 (Token来源: 数据库)"
                    result["token_source"] = "database"
                elif token_source == 'env':
                    result["message"] = "✅ 连接成功 (Token来源: .env)"
                    result["token_source"] = "env"
                else:
                    result["message"] = "✅ 连接成功"

                logger.info(f"✅ {adapter.name} 连通性测试成功，Token来源: {token_source}")
            else:
                result["available"] = False
                result["message"] = "❌ 数据源不可用"
                logger.warning(f"⚠️ {adapter.name} 不可用")
        except asyncio.TimeoutError:
            result["available"] = False
            result["message"] = f"❌ 连接超时 ({test_timeout}秒)"
            logger.warning(f"⚠️ {adapter.name} 连接超时")
        except Exception as e:
            result["available"] = False
            result["message"] = f"❌ 连接失败: {str(e)}"
            logger.error(f"❌ {adapter.name} 连接失败: {e}")

    except Exception as e:
        result["available"] = False
        result["message"] = f"❌ 测试异常: {str(e)}"
        logger.error(f"❌ 测试 {adapter.name} 时出错: {e}")

    return result


class TestSourceRequest(BaseModel):
    """测试数据源请求"""
    source_name: str | None = None


@router.post("/test-sources")
async def test_data_sources(
    request: TestSourceRequest = TestSourceRequest(),
    current_user: dict = Depends(get_current_user)
):
    """
    测试数据源的连通性

    参数:
    - source_name: 可选，指定要测试的数据源名称。如果不指定，则测试所有数据源

    只做轻量级连通性测试，不获取完整数据
    - 测试超时: 10秒
    - 只获取1条数据验证连接
    - 快速返回结果
    """
    try:
        manager = DataSourceManager()
        all_adapters = manager.adapters

        # 从请求体中获取数据源名称
        source_name = request.source_name
        logger.info(f"📥 接收到测试请求，source_name={source_name}")

        # 如果指定了数据源名称，只测试该数据源
        if source_name:
            adapters_to_test = [a for a in all_adapters if a.name.lower() == source_name.lower()]
            if not adapters_to_test:
                raise HTTPException(
                    status_code=400,
                    detail=f"Data source '{source_name}' not found"
                )
            logger.info(f"🧪 开始测试数据源: {source_name}")
        else:
            adapters_to_test = all_adapters
            logger.info(f"🧪 开始测试 {len(all_adapters)} 个数据源的连通性...")

        # 并发测试适配器（在后台线程中执行）
        test_tasks = [_test_single_adapter(adapter) for adapter in adapters_to_test]
        test_results = await asyncio.gather(*test_tasks, return_exceptions=True)

        # 处理异常结果
        final_results = []
        for i, result in enumerate(test_results):
            if isinstance(result, Exception):
                logger.error(f"❌ 测试适配器 {adapters_to_test[i].name} 时出错: {result}")
                final_results.append({
                    "name": adapters_to_test[i].name,
                    "priority": adapters_to_test[i].priority,
                    "available": False,
                    "message": f"❌ 测试异常: {str(result)}"
                })
            else:
                final_results.append(result)

        # 统计结果
        available_count = sum(1 for r in final_results if r.get("available"))
        if source_name:
            logger.info(f"✅ 数据源 {source_name} 测试完成: {'可用' if available_count > 0 else '不可用'}")
        else:
            logger.info(f"✅ 数据源连通性测试完成: {available_count}/{len(final_results)} 可用")

        return SyncResponse(
            success=True,
            message=f"Tested {len(final_results)} data sources, {available_count} available",
            data={"test_results": final_results}
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ 测试数据源时出错: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to test data sources: {str(e)}")


@router.get("/recommendations")
async def get_sync_recommendations(current_user: dict = Depends(get_current_user)):
    """获取数据源使用建议"""
    try:
        manager = DataSourceManager()
        available_adapters = manager.get_available_adapters()
        
        recommendations = {
            "primary_source": None,
            "fallback_sources": [],
            "suggestions": [],
            "warnings": []
        }
        
        if available_adapters:
            # 推荐优先级最高的可用数据源作为主数据源
            primary = available_adapters[0]
            recommendations["primary_source"] = {
                "name": primary.name,
                "priority": primary.priority,
                "reason": "Highest priority available data source"
            }
            
            # 其他可用数据源作为备用
            for adapter in available_adapters[1:]:
                recommendations["fallback_sources"].append({
                    "name": adapter.name,
                    "priority": adapter.priority
                })
        
        # 生成建议
        if not available_adapters:
            recommendations["warnings"].append("No data sources are available. Please check your configuration.")
        elif len(available_adapters) == 1:
            recommendations["suggestions"].append("Consider configuring additional data sources for redundancy.")
        else:
            recommendations["suggestions"].append(f"You have {len(available_adapters)} data sources available, which provides good redundancy.")
        
        # 特定数据源的建议
        tushare_available = any(a.name == "tushare" for a in available_adapters)
        if not tushare_available:
            recommendations["suggestions"].append("Consider configuring Tushare for the most comprehensive financial data.")
        
        return SyncResponse(
            success=True,
            message="Recommendations generated successfully",
            data=recommendations
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate recommendations: {str(e)}")


@router.get("/history")
async def get_sync_history(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(10, ge=1, le=50, description="每页大小"),
    status: Optional[str] = Query(None, description="状态筛选"),
    current_user: dict = Depends(get_current_user)
):
    """获取同步历史记录"""
    try:
        from app.core.database import get_mongo_db
        db = get_mongo_db()

        # 构建查询条件
        query = {"job": "stock_basics_multi_source"}
        if status:
            query["status"] = status

        # 计算跳过的记录数
        skip = (page - 1) * page_size

        # 查询历史记录
        cursor = db.sync_status.find(query).sort("started_at", -1).skip(skip).limit(page_size)
        history_records = await cursor.to_list(length=page_size)

        # 获取总数
        total = await db.sync_status.count_documents(query)

        # 清理记录中的 _id 字段
        for record in history_records:
            record.pop("_id", None)

        return SyncResponse(
            success=True,
            message="History retrieved successfully",
            data={
                "records": history_records,
                "total": total,
                "page": page,
                "page_size": page_size,
                "has_more": skip + len(history_records) < total
            }
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get sync history: {str(e)}")


@router.delete("/cache")
async def clear_sync_cache(current_user: dict = Depends(get_current_user)):
    """清空同步相关的缓存"""
    try:
        service = get_multi_source_sync_service()

        # 清空同步状态缓存
        cleared_items = 0

        # 1. 清空同步状态
        try:
            from app.core.database import get_mongo_db
            db = get_mongo_db()

            # 删除同步状态记录
            result = await db.sync_status.delete_many({"job": "stock_basics_multi_source"})
            cleared_items += result.deleted_count

            # 重置服务状态
            service._running = False

        except Exception as e:
            logger.warning(f"Failed to clear sync status cache: {e}")

        # 2. 清空数据源缓存（如果有的话）
        try:
            manager = DataSourceManager()
            # 这里可以添加数据源特定的缓存清理逻辑
            # 目前数据源适配器没有持久化缓存，所以跳过
        except Exception as e:
            logger.warning(f"Failed to clear data source cache: {e}")

        return SyncResponse(
            success=True,
            message=f"Cache cleared successfully, {cleared_items} items removed",
            data={"cleared": True, "items_cleared": cleared_items}
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to clear cache: {str(e)}")
