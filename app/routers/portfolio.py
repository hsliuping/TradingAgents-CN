"""
持仓分析API路由
提供持仓管理和AI分析接口

[PRO功能] 此模块为专业版功能，需要专业版授权
"""

from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel, Field
import logging

from app.routers.auth_db import get_current_user
from app.core.permissions import require_pro
from app.services.portfolio_service import get_portfolio_service
from app.models.portfolio import (
    PositionCreate, PositionUpdate, PositionImport, PositionOperationRequest,
    PortfolioAnalysisRequest, PositionResponse,
    PortfolioStatsResponse, PortfolioAnalysisResponse,
    PositionAnalysisRequest, PositionAnalysisByCodeRequest,
    AccountInitRequest, AccountTransactionRequest,
    AccountSettingsRequest, CapitalTransactionType, PositionChangeType,
    PortfolioAnalysisStatus
)
from app.core.response import ok

logger = logging.getLogger("webapi")

# 整个路由器都需要 PRO 权限
router = APIRouter(
    prefix="/portfolio",
    tags=["持仓分析"],
    dependencies=[Depends(require_pro)]
)


# ==================== 持仓管理接口 ====================

@router.get("/positions", response_model=dict)
async def get_positions(
    source: str = Query("all", description="数据来源: all/real/paper"),
    current_user: dict = Depends(get_current_user)
):
    """获取持仓列表"""
    try:
        service = get_portfolio_service()
        positions = await service.get_positions(
            user_id=current_user["id"],
            source=source
        )

        # 转换为字典列表
        items = [pos.model_dump() for pos in positions]

        return ok(data={
            "items": items,
            "total": len(items)
        })
    except Exception as e:
        logger.error(f"获取持仓失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/positions/history", response_model=dict)
async def get_history_positions(
    source: str = Query("real", description="数据来源: real/paper"),
    limit: int = Query(50, ge=1, le=100, description="每页数量"),
    skip: int = Query(0, ge=0, description="跳过数量"),
    current_user: dict = Depends(get_current_user)
):
    """获取历史持仓（已清仓的记录）"""
    try:
        service = get_portfolio_service()
        result = await service.get_history_positions(
            user_id=current_user["id"],
            source=source,
            limit=limit,
            skip=skip
        )
        return ok(data=result)
    except Exception as e:
        logger.error(f"获取历史持仓失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/positions", response_model=dict)
async def add_position(
    data: PositionCreate,
    current_user: dict = Depends(get_current_user)
):
    """添加持仓"""
    try:
        service = get_portfolio_service()
        position = await service.add_position(
            user_id=current_user["id"],
            data=data
        )
        return ok(data=position.model_dump(), message="添加成功")
    except Exception as e:
        logger.error(f"添加持仓失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.put("/positions/{position_id}", response_model=dict)
async def update_position(
    position_id: str,
    data: PositionUpdate,
    current_user: dict = Depends(get_current_user)
):
    """更新持仓"""
    try:
        service = get_portfolio_service()
        position = await service.update_position(
            user_id=current_user["id"],
            position_id=position_id,
            data=data
        )
        if not position:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="持仓不存在"
            )
        return ok(data=position.model_dump(), message="更新成功")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"更新持仓失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.delete("/positions/{position_id}", response_model=dict)
async def delete_position(
    position_id: str,
    current_user: dict = Depends(get_current_user)
):
    """删除持仓"""
    try:
        service = get_portfolio_service()
        success = await service.delete_position(
            user_id=current_user["id"],
            position_id=position_id
        )
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="持仓不存在"
            )
        return ok(message="删除成功")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"删除持仓失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/positions/import", response_model=dict)
async def import_positions(
    data: PositionImport,
    current_user: dict = Depends(get_current_user)
):
    """批量导入持仓"""
    try:
        service = get_portfolio_service()
        result = await service.import_positions(
            user_id=current_user["id"],
            positions=data.positions
        )
        return ok(data=result, message=f"导入完成: 成功 {result['success_count']}, 失败 {result['failed_count']}")
    except Exception as e:
        logger.error(f"导入持仓失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/positions/operate", response_model=dict)
async def operate_position(
    data: PositionOperationRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    执行持仓操作（加仓、减仓、分红、拆股、合股、调整成本）

    操作类型:
    - add: 加仓（需要 quantity, price）
    - reduce: 减仓（需要 quantity, price）
    - dividend: 分红（需要 dividend_amount）
    - split: 拆股（需要 ratio，如 "2:1"）
    - merge: 合股（需要 ratio，如 "1:10"）
    - adjust: 调整成本价（需要 new_cost_price）
    """
    try:
        service = get_portfolio_service()
        result = await service.operate_position(
            user_id=current_user["id"],
            data=data
        )
        return ok(data=result, message=result.get("message", "操作成功"))
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"持仓操作失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


# ==================== 持仓统计接口 ====================

@router.get("/statistics", response_model=dict)
async def get_portfolio_statistics(
    current_user: dict = Depends(get_current_user)
):
    """获取持仓统计"""
    try:
        service = get_portfolio_service()
        stats = await service.get_portfolio_statistics(current_user["id"])
        return ok(data=stats.model_dump())
    except Exception as e:
        logger.error(f"获取持仓统计失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


# ==================== 持仓分析接口 ====================

@router.post("/analysis", response_model=dict)
async def analyze_portfolio(
    data: PortfolioAnalysisRequest = PortfolioAnalysisRequest(),
    current_user: dict = Depends(get_current_user)
):
    """发起持仓分析"""
    try:
        service = get_portfolio_service()
        report = await service.analyze_portfolio(
            user_id=current_user["id"],
            include_paper=data.include_paper,
            research_depth=data.research_depth
        )

        # 转换为响应格式
        response_data = {
            "analysis_id": report.analysis_id,
            "status": report.status.value,
            "health_score": report.health_score,
            "risk_level": report.risk_level,
            "portfolio_snapshot": report.portfolio_snapshot.model_dump(),
            "industry_distribution": [d.model_dump() for d in report.industry_distribution],
            "concentration_analysis": report.concentration_analysis.model_dump(),
            "ai_analysis": report.ai_analysis.model_dump(),
            "execution_time": report.execution_time,
            "error_message": report.error_message,
            "created_at": report.created_at.isoformat()
        }

        return ok(data=response_data)
    except Exception as e:
        logger.error(f"持仓分析失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/analysis/history", response_model=dict)
async def get_analysis_history(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=50),
    current_user: dict = Depends(get_current_user)
):
    """获取分析历史"""
    try:
        service = get_portfolio_service()
        result = await service.get_analysis_history(
            user_id=current_user["id"],
            page=page,
            page_size=page_size
        )

        # 转换ObjectId
        items = []
        for item in result["items"]:
            item["_id"] = str(item["_id"]) if "_id" in item else None
            items.append(item)

        return ok(data={
            "items": items,
            "total": result["total"],
            "page": result["page"],
            "page_size": result["page_size"]
        })
    except Exception as e:
        logger.error(f"获取分析历史失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/analysis/{analysis_id}", response_model=dict)
async def get_analysis_detail(
    analysis_id: str,
    current_user: dict = Depends(get_current_user)
):
    """获取分析报告详情"""
    try:
        service = get_portfolio_service()
        report = await service.get_analysis_detail(analysis_id)

        if not report:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="分析报告不存在"
            )

        # 验证用户权限
        if report.get("user_id") != current_user["id"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="无权访问该报告"
            )

        # 如果报告包含ai_analysis，检查并转换action_reason
        if report.get("ai_analysis") and report["ai_analysis"].get("action_reason"):
            action_reason_raw = report["ai_analysis"]["action_reason"]
            logger.info(f"📊 [分析详情接口] 原始action_reason类型: {type(action_reason_raw)}, 长度: {len(str(action_reason_raw)) if action_reason_raw else 0}")
            
            import json
            advice_json = None
            
            if isinstance(action_reason_raw, str):
                action_reason_str = action_reason_raw.strip()
                if "```json" in action_reason_str or (action_reason_str.startswith("{") and ("analysis_summary" in action_reason_str or "neutral_operation" in action_reason_str)):
                    try:
                        if "```json" in action_reason_str:
                            json_start = action_reason_str.find("```json") + 7
                            json_end = action_reason_str.find("```", json_start)
                            if json_end > json_start:
                                json_str = action_reason_str[json_start:json_end].strip()
                                advice_json = json.loads(json_str)
                        elif action_reason_str.strip().startswith("{"):
                            advice_json = json.loads(action_reason_str)
                        
                        if advice_json:
                            logger.info(f"📊 [分析详情接口] JSON解析成功，转换为Markdown")
                            report["ai_analysis"]["action_reason"] = service._convert_action_advice_json_to_markdown(advice_json)
                    except Exception as e:
                        logger.warning(f"⚠️ [分析详情接口] JSON解析失败: {e}")
            elif isinstance(action_reason_raw, dict):
                logger.info(f"📊 [分析详情接口] action_reason是字典格式，转换为Markdown")
                report["ai_analysis"]["action_reason"] = service._convert_action_advice_json_to_markdown(action_reason_raw)

        # 转换ObjectId
        report["_id"] = str(report["_id"]) if "_id" in report else None

        return ok(data=report)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取分析详情失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


# ==================== 单股持仓分析接口 ====================

@router.get("/positions/{position_id}", response_model=dict)
async def get_position_detail(
    position_id: str,
    current_user: dict = Depends(get_current_user)
):
    """获取单个持仓详情"""
    try:
        service = get_portfolio_service()
        position = await service.get_position_by_id(current_user["id"], position_id)
        if not position:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="持仓不存在"
            )
        return ok(data=position.model_dump())
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取持仓详情失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/positions/{position_id}/analysis", response_model=dict)
async def analyze_position(
    position_id: str,
    data: PositionAnalysisRequest = PositionAnalysisRequest(),
    current_user: dict = Depends(get_current_user)
):
    """发起单股持仓分析"""
    try:
        service = get_portfolio_service()
        report = await service.analyze_position(
            user_id=current_user["id"],
            position_id=position_id,
            params=data
        )

        # 检查分析是否失败
        if report.status == PortfolioAnalysisStatus.FAILED:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=report.error_message or "分析失败"
            )

        # 转换为响应格式
        response_data = {
            "analysis_id": report.analysis_id,
            "position_id": report.position_id,
            "code": report.position_snapshot.code if report.position_snapshot else None,
            "name": report.position_snapshot.name if report.position_snapshot else None,
            "status": report.status.value,
            "action": report.ai_analysis.action.value if report.ai_analysis else None,
            "action_reason": report.ai_analysis.action_reason if report.ai_analysis else None,
            "confidence": report.ai_analysis.confidence if report.ai_analysis else None,
            "price_targets": report.ai_analysis.price_targets.model_dump() if report.ai_analysis and report.ai_analysis.price_targets else None,
            "risk_assessment": report.ai_analysis.risk_assessment if report.ai_analysis else None,
            "opportunity_assessment": report.ai_analysis.opportunity_assessment if report.ai_analysis else None,
            "detailed_analysis": report.ai_analysis.detailed_analysis if report.ai_analysis else None,
            "execution_time": report.execution_time,
            "error_message": report.error_message,
            "created_at": report.created_at.isoformat()
        }

        return ok(data=response_data)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"单股持仓分析失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


class CheckCacheRequest(BaseModel):
    """检查缓存请求"""
    code: str = Field(..., description="股票代码")
    market: str = Field("CN", description="市场类型（CN/HK/US）")


@router.post("/positions/check-cache", response_model=dict)
async def check_stock_analysis_cache(
    data: CheckCacheRequest,
    current_user: dict = Depends(get_current_user)
):
    """检查单股分析报告缓存状态
    
    在开始持仓分析前，先检查是否有可用的单股分析报告缓存。
    如果没有缓存，前端可以提示用户选择：
    1. 继续分析（不使用单股分析报告）
    2. 先去单股分析页面进行分析
    
    Args:
        data: 检查缓存请求，包含股票代码和市场类型
        
    Returns:
        缓存状态信息，包含：
        - has_cache: 是否有缓存
        - cache_age_hours: 缓存时间（小时）
        - cache_age_minutes: 缓存时间（分钟）
        - source: 缓存来源
        - task_id: 任务ID（如果有）
        - created_at: 缓存创建时间
    """
    try:
        from app.services.portfolio_service import get_portfolio_service, convert_market_code_to_name
        
        portfolio_service = get_portfolio_service()
        
        # 将市场代码转换为中文名称（A股/港股/美股）
        market_name = convert_market_code_to_name(data.market)
        
        logger.info(f"🔍 [检查缓存] 检查单股分析报告缓存: code={data.code}, market={data.market} -> {market_name}")
        
        cache_status = await portfolio_service.check_stock_analysis_cache(
            stock_code=data.code,
            market=market_name
        )
        
        logger.info(f"✅ [检查缓存] 缓存状态: has_cache={cache_status.get('has_cache')}, "
                   f"age={cache_status.get('cache_age_minutes')}分钟")
        
        return ok(data=cache_status, message="缓存状态查询成功")
        
    except Exception as e:
        logger.error(f"❌ [检查缓存] 查询失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"查询缓存状态失败: {str(e)}"
        )


@router.post("/positions/analyze-by-code", response_model=dict)
async def analyze_position_by_code(
    data: PositionAnalysisByCodeRequest,
    current_user: dict = Depends(get_current_user)
):
    """按股票代码分析持仓（异步模式）

    立即返回任务ID，后台执行分析。
    前端可通过 GET /api/analysis/tasks/{task_id}/status 查询分析状态和结果。

    使用新的统一任务中心进行管理。
    """
    import asyncio

    try:
        logger.info(f"📥 [持仓分析路由] 收到请求: code={data.code}, market={data.market}, user_id={current_user['id']}")
        
        from app.services.unified_analysis_service import get_unified_analysis_service

        unified_service = get_unified_analysis_service()
        logger.info(f"✅ [持仓分析路由] 获取到 UnifiedAnalysisService 实例")

        # 准备任务参数
        task_params = {
            "research_depth": data.research_depth,
            "include_add_position": data.include_add_position,
            "target_profit_pct": data.target_profit_pct,
            "total_capital": data.total_capital,
            "max_position_pct": data.max_position_pct,
            "max_loss_pct": data.max_loss_pct,
            "risk_tolerance": data.risk_tolerance,
            "investment_horizon": data.investment_horizon,
            "analysis_focus": data.analysis_focus,
            "position_type": data.position_type,
        }
        logger.info(f"📋 [持仓分析路由] 任务参数准备完成: {list(task_params.keys())}")

        # 创建统一分析任务
        logger.info(f"🔄 [持仓分析路由] 开始创建任务...")
        result = await unified_service.create_position_analysis_task(
            user_id=current_user["id"],
            code=data.code,
            market=data.market,
            task_params=task_params
        )
        logger.info(f"✅ [持仓分析路由] 任务创建成功: task_id={result['task_id']}")
        
        # 为了兼容前端，同时返回analysis_id字段（等于task_id）
        result["analysis_id"] = result["task_id"]

        # 后台执行分析
        logger.info(f"🚀 [持仓分析路由] 启动后台任务执行...")
        asyncio.create_task(
            unified_service.execute_position_analysis(
                task_id=result["task_id"],
                user_id=current_user["id"],
                code=data.code,
                market=data.market,
                task_params=task_params
            )
        )
        logger.info(f"✅ [持仓分析路由] 后台任务已启动")

        return ok(data=result, message="持仓分析任务已提交，预计需要2-5分钟完成")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ [持仓分析路由] 创建任务失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/positions/analysis/{task_id}", response_model=dict)
async def get_position_analysis_status(
    task_id: str,
    current_user: dict = Depends(get_current_user)
):
    """获取持仓分析任务状态和结果

    注意：此接口已改为使用统一任务中心，task_id 即为任务ID。
    也可以使用 GET /api/analysis/tasks/{task_id}/status 接口查询。
    """
    try:
        from app.core.database import get_mongo_db
        from bson import ObjectId

        db = get_mongo_db()

        # 从统一任务中心获取任务
        task = await db.unified_analysis_tasks.find_one({
            "task_id": task_id,
            "user_id": ObjectId(current_user["id"])
        })

        if not task:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="分析任务不存在"
            )

        # 格式化返回数据
        task_status = task["status"]
        if hasattr(task_status, "value"):
            task_status = task_status.value
        elif isinstance(task_status, str):
            task_status = task_status
        else:
            task_status = str(task_status)
        
        # 辅助函数：将datetime或字符串转换为ISO格式字符串
        def to_iso_string(value):
            if value is None:
                return None
            if isinstance(value, str):
                return value
            if hasattr(value, "isoformat"):
                return value.isoformat()
            return str(value)
        
        result_data = {
            "task_id": task["task_id"],
            "code": task["task_params"].get("code"),
            "market": task["task_params"].get("market"),
            "status": task_status,
            "message": task.get("message"),
            "progress": task.get("progress", 0),
            "created_at": to_iso_string(task.get("created_at")),
            "started_at": to_iso_string(task.get("started_at")),
            "completed_at": to_iso_string(task.get("completed_at")),
            "error_message": task.get("error_message"),
        }
        
        # 如果任务已完成且有结果，将result中的字段展平到顶层，以匹配前端期望的数据结构
        task_result = task.get("result")
        if task_result and isinstance(task_result, dict):
            # 提取analysis_id（如果有）
            if "analysis_id" in task_result:
                result_data["analysis_id"] = task_result["analysis_id"]
            
            # 提取position_snapshot中的字段
            position_snapshot = task_result.get("position_snapshot")
            if position_snapshot:
                result_data["code"] = position_snapshot.get("code") or result_data.get("code")
                result_data["name"] = position_snapshot.get("name")
                # 构建position_id
                if position_snapshot.get("code") and position_snapshot.get("market"):
                    result_data["position_id"] = f"{position_snapshot['code']}_{position_snapshot['market']}"
            elif result_data.get("code") and result_data.get("market"):
                # 如果没有snapshot，使用code和market构建position_id
                result_data["position_id"] = f"{result_data['code']}_{result_data['market']}"
            
            # 提取ai_analysis中的字段并展平到顶层
            ai_analysis = task_result.get("ai_analysis")
            if ai_analysis:
                # action可能是枚举类型，需要转换为字符串
                action_value = ai_analysis.get("action")
                if hasattr(action_value, "value"):
                    action_value = action_value.value
                result_data["action"] = action_value
                
                # 处理action_reason：如果是JSON格式，转换为Markdown
                action_reason_raw = ai_analysis.get("action_reason")
                logger.info(f"📊 [持仓分析接口] 原始action_reason类型: {type(action_reason_raw)}, 长度: {len(str(action_reason_raw)) if action_reason_raw else 0}")
                
                if action_reason_raw:
                    # 检查是否是JSON格式（可能是字符串形式的JSON或字典）
                    import json
                    advice_json = None
                    
                    # 如果是字符串，尝试解析JSON
                    if isinstance(action_reason_raw, str):
                        action_reason_str = action_reason_raw.strip()
                        logger.info(f"📊 [持仓分析接口] action_reason前100字符: {action_reason_str[:100]}")
                        
                        # 检查是否包含JSON代码块
                        if "```json" in action_reason_str or (action_reason_str.startswith("{") and "analysis_summary" in action_reason_str):
                            try:
                                # 提取JSON
                                if "```json" in action_reason_str:
                                    json_start = action_reason_str.find("```json") + 7
                                    json_end = action_reason_str.find("```", json_start)
                                    if json_end > json_start:
                                        json_str = action_reason_str[json_start:json_end].strip()
                                        logger.info(f"📊 [持仓分析接口] 从代码块提取JSON，长度: {len(json_str)}")
                                        advice_json = json.loads(json_str)
                                elif action_reason_str.strip().startswith("{"):
                                    logger.info(f"📊 [持仓分析接口] 直接解析JSON格式")
                                    advice_json = json.loads(action_reason_str)
                                
                                if advice_json:
                                    logger.info(f"📊 [持仓分析接口] JSON解析成功，字段: {list(advice_json.keys())}")
                                    # 使用portfolio_service的转换方法
                                    service = get_portfolio_service()
                                    action_reason_markdown = service._convert_action_advice_json_to_markdown(advice_json)
                                    logger.info(f"📊 [持仓分析接口] JSON转换为Markdown成功，长度: {len(action_reason_markdown)}")
                                    result_data["action_reason"] = action_reason_markdown
                                else:
                                    logger.warning(f"⚠️ [持仓分析接口] JSON解析后为空，使用原始值")
                                    result_data["action_reason"] = action_reason_raw
                            except Exception as e:
                                logger.warning(f"⚠️ [持仓分析接口] JSON解析失败，使用原始值: {e}", exc_info=True)
                                result_data["action_reason"] = action_reason_raw
                        else:
                            # 不是JSON格式，直接使用
                            logger.info(f"📊 [持仓分析接口] action_reason不是JSON格式，直接使用")
                            result_data["action_reason"] = action_reason_raw
                    elif isinstance(action_reason_raw, dict):
                        # 如果已经是字典格式，直接转换
                        logger.info(f"📊 [持仓分析接口] action_reason是字典格式，字段: {list(action_reason_raw.keys())}")
                        service = get_portfolio_service()
                        action_reason_markdown = service._convert_action_advice_json_to_markdown(action_reason_raw)
                        logger.info(f"📊 [持仓分析接口] 字典转换为Markdown成功，长度: {len(action_reason_markdown)}")
                        result_data["action_reason"] = action_reason_markdown
                    else:
                        # 其他类型，直接使用
                        logger.info(f"📊 [持仓分析接口] action_reason是其他类型: {type(action_reason_raw)}")
                        result_data["action_reason"] = str(action_reason_raw) if action_reason_raw else ""
                else:
                    result_data["action_reason"] = ""
                
                # 处理recommendation字段：如果是JSON格式，转换为Markdown（与action_reason保持一致）
                recommendation_raw = ai_analysis.get("recommendation")
                logger.info(f"📊 [持仓分析接口] 原始recommendation类型: {type(recommendation_raw)}, 长度: {len(str(recommendation_raw)) if recommendation_raw else 0}")
                
                if recommendation_raw:
                    # 如果recommendation和action_reason相同（都是转换后的Markdown），直接使用
                    if recommendation_raw == result_data.get("action_reason"):
                        logger.info(f"📊 [持仓分析接口] recommendation与action_reason相同，直接使用转换后的Markdown")
                        result_data["recommendation"] = result_data["action_reason"]
                    else:
                        # 检查是否是JSON格式
                        import json
                        advice_json = None
                        
                        if isinstance(recommendation_raw, str):
                            recommendation_str = recommendation_raw.strip()
                            logger.info(f"📊 [持仓分析接口] recommendation前100字符: {recommendation_str[:100]}")
                            
                            if "```json" in recommendation_str or (recommendation_str.startswith("{") and ("analysis_summary" in recommendation_str or "neutral_operation" in recommendation_str)):
                                try:
                                    if "```json" in recommendation_str:
                                        json_start = recommendation_str.find("```json") + 7
                                        json_end = recommendation_str.find("```", json_start)
                                        if json_end > json_start:
                                            json_str = recommendation_str[json_start:json_end].strip()
                                            logger.info(f"📊 [持仓分析接口] 从代码块提取recommendation JSON，长度: {len(json_str)}")
                                            advice_json = json.loads(json_str)
                                    elif recommendation_str.strip().startswith("{"):
                                        logger.info(f"📊 [持仓分析接口] 直接解析recommendation JSON格式")
                                        advice_json = json.loads(recommendation_str)
                                    
                                    if advice_json:
                                        logger.info(f"📊 [持仓分析接口] recommendation JSON解析成功，转换为Markdown")
                                        service = get_portfolio_service()
                                        recommendation_markdown = service._convert_action_advice_json_to_markdown(advice_json)
                                        logger.info(f"📊 [持仓分析接口] recommendation转换为Markdown成功，长度: {len(recommendation_markdown)}")
                                        result_data["recommendation"] = recommendation_markdown
                                    else:
                                        logger.warning(f"⚠️ [持仓分析接口] recommendation JSON解析后为空，使用原始值")
                                        result_data["recommendation"] = recommendation_raw
                                except Exception as e:
                                    logger.warning(f"⚠️ [持仓分析接口] recommendation JSON解析失败，使用原始值: {e}", exc_info=True)
                                    result_data["recommendation"] = recommendation_raw
                            else:
                                # 不是JSON格式，直接使用
                                logger.info(f"📊 [持仓分析接口] recommendation不是JSON格式，直接使用")
                                result_data["recommendation"] = recommendation_raw
                        elif isinstance(recommendation_raw, dict):
                            # 如果已经是字典格式，直接转换
                            logger.info(f"📊 [持仓分析接口] recommendation是字典格式，字段: {list(recommendation_raw.keys())}")
                            service = get_portfolio_service()
                            recommendation_markdown = service._convert_action_advice_json_to_markdown(recommendation_raw)
                            logger.info(f"📊 [持仓分析接口] recommendation字典转换为Markdown成功，长度: {len(recommendation_markdown)}")
                            result_data["recommendation"] = recommendation_markdown
                        else:
                            logger.info(f"📊 [持仓分析接口] recommendation是其他类型: {type(recommendation_raw)}")
                            result_data["recommendation"] = str(recommendation_raw) if recommendation_raw else ""
                else:
                    result_data["recommendation"] = ""
                
                result_data["confidence"] = ai_analysis.get("confidence")
                result_data["price_targets"] = ai_analysis.get("price_targets")
                result_data["risk_assessment"] = ai_analysis.get("risk_assessment")
                result_data["opportunity_assessment"] = ai_analysis.get("opportunity_assessment")
                
                # 处理detailed_analysis字段：如果里面包含JSON格式的操作建议，需要转换
                detailed_analysis_raw = ai_analysis.get("detailed_analysis")
                if detailed_analysis_raw and isinstance(detailed_analysis_raw, str):
                    # 检查是否包含JSON格式的操作建议
                    if "```json" in detailed_analysis_raw and "【操作建议】" in detailed_analysis_raw:
                        logger.info(f"📊 [持仓分析接口] detailed_analysis包含JSON格式的操作建议，需要转换")
                        try:
                            import json
                            # 找到【操作建议】后面的JSON部分
                            op_advice_start = detailed_analysis_raw.find("【操作建议】")
                            if op_advice_start >= 0:
                                op_advice_section = detailed_analysis_raw[op_advice_start:]
                                # 提取JSON部分
                                json_start = op_advice_section.find("```json")
                                if json_start >= 0:
                                    json_start_pos = json_start + 7
                                    json_end = op_advice_section.find("```", json_start_pos)
                                    if json_end > json_start_pos:
                                        json_str = op_advice_section[json_start_pos:json_end].strip()
                                        advice_json = json.loads(json_str)
                                        # 转换为Markdown
                                        service = get_portfolio_service()
                                        op_advice_markdown = service._convert_action_advice_json_to_markdown(advice_json)
                                        # 替换原来的JSON部分
                                        before_op_advice = detailed_analysis_raw[:op_advice_start + len("【操作建议】\n")]
                                        after_json = op_advice_section[json_end + 3:].lstrip()
                                        detailed_analysis_converted = before_op_advice + op_advice_markdown + (f"\n{after_json}" if after_json else "")
                                        logger.info(f"📊 [持仓分析接口] detailed_analysis转换成功，长度: {len(detailed_analysis_converted)}")
                                        result_data["detailed_analysis"] = detailed_analysis_converted
                                    else:
                                        result_data["detailed_analysis"] = detailed_analysis_raw
                                else:
                                    result_data["detailed_analysis"] = detailed_analysis_raw
                            else:
                                result_data["detailed_analysis"] = detailed_analysis_raw
                        except Exception as e:
                            logger.warning(f"⚠️ [持仓分析接口] detailed_analysis转换失败，使用原始值: {e}", exc_info=True)
                            result_data["detailed_analysis"] = detailed_analysis_raw
                    else:
                        result_data["detailed_analysis"] = detailed_analysis_raw
                else:
                    result_data["detailed_analysis"] = detailed_analysis_raw
                result_data["suggested_quantity"] = ai_analysis.get("suggested_quantity")
                result_data["suggested_amount"] = ai_analysis.get("suggested_amount")
                result_data["risk_metrics"] = ai_analysis.get("risk_metrics")
            
            # 保留result字段，但需要确保内部的recommendation也被转换
            # 创建一个副本，避免修改原始数据
            result_copy = task_result.copy() if isinstance(task_result, dict) else task_result
            if isinstance(result_copy, dict) and "ai_analysis" in result_copy:
                ai_analysis_copy = result_copy["ai_analysis"].copy() if isinstance(result_copy["ai_analysis"], dict) else result_copy["ai_analysis"]
                if isinstance(ai_analysis_copy, dict):
                    # 如果顶层的recommendation已经转换，同步到result内部
                    if "recommendation" in result_data:
                        ai_analysis_copy["recommendation"] = result_data["recommendation"]
                        logger.info(f"📊 [持仓分析接口] 同步转换后的recommendation到result.ai_analysis")
                    # 如果顶层的action_reason已经转换，也同步到result内部
                    if "action_reason" in result_data:
                        ai_analysis_copy["action_reason"] = result_data["action_reason"]
                        logger.info(f"📊 [持仓分析接口] 同步转换后的action_reason到result.ai_analysis")
                    result_copy["ai_analysis"] = ai_analysis_copy
            result_data["result"] = result_copy
            
            # 提取execution_time
            if "execution_time" in task_result:
                result_data["execution_time"] = task_result["execution_time"]
        else:
            # 如果没有result，保持原样
            result_data["result"] = task_result

        return ok(data=result_data)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取分析状态失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/positions/analysis-by-code/{code}", response_model=dict)
async def get_position_analysis_by_code(
    code: str,
    market: str = Query("CN", description="市场: CN/HK/US"),
    source: str = Query("real", description="数据来源: real(真实持仓)/paper(模拟持仓)"),
    current_user: dict = Depends(get_current_user)
):
    """按股票代码获取最新的分析报告"""
    try:
        service = get_portfolio_service()
        # 🔥 将 source 转换为 position_type
        position_type = "simulated" if source == "paper" else "real"
        report = await service.get_latest_position_analysis(
            user_id=current_user["id"],
            code=code,
            market=market,
            position_type=position_type
        )

        if not report:
            return ok(data=None, message="暂无分析报告")

        return ok(data=report)
    except Exception as e:
        logger.error(f"获取分析报告失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/positions/{position_id}/analysis/history", response_model=dict)
async def get_position_analysis_history(
    position_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=50),
    source: str = Query("real", description="数据来源: real(真实持仓)/paper(模拟持仓)"),
    current_user: dict = Depends(get_current_user)
):
    """获取单股分析历史"""
    try:
        service = get_portfolio_service()
        # 🔥 将 source 转换为 position_type
        position_type = "simulated" if source == "paper" else "real"
        result = await service.get_position_analysis_history(
            user_id=current_user["id"],
            position_id=position_id,
            page=page,
            page_size=page_size,
            position_type=position_type
        )

        # 转换ObjectId
        items = []
        for item in result["items"]:
            item["_id"] = str(item["_id"]) if "_id" in item else None
            items.append(item)

        return ok(data={
            "items": items,
            "total": result["total"],
            "page": result["page"],
            "page_size": result["page_size"]
        })
    except Exception as e:
        logger.error(f"获取单股分析历史失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.delete("/positions/analysis/{analysis_id}", response_model=dict)
async def delete_position_analysis(
    analysis_id: str,
    current_user: dict = Depends(get_current_user)
):
    """删除持仓分析报告"""
    try:
        from app.core.database import get_mongo_db
        from bson import ObjectId
        
        db = get_mongo_db()
        
        # 查找分析报告
        report = await db["position_analysis_reports"].find_one({
            "analysis_id": analysis_id,
            "user_id": current_user["id"]
        })
        
        if not report:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="分析报告不存在"
            )
        
        # 删除分析报告
        result = await db["position_analysis_reports"].delete_one({
            "analysis_id": analysis_id,
            "user_id": current_user["id"]
        })
        
        if result.deleted_count > 0:
            logger.info(f"✅ 删除持仓分析报告成功: {analysis_id}")
            return ok(message="删除成功")
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="删除失败"
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"删除持仓分析报告失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


# ==================== 资金账户接口 ====================

@router.get("/account", response_model=dict)
async def get_account(current_user: dict = Depends(get_current_user)):
    """获取资金账户信息"""
    try:
        service = get_portfolio_service()
        acc = await service.get_or_create_account(current_user["id"])
        # 移除 _id
        acc.pop("_id", None)
        return ok(data=acc)
    except Exception as e:
        logger.error(f"获取资金账户失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/account/summary", response_model=dict)
async def get_account_summary(current_user: dict = Depends(get_current_user)):
    """获取账户摘要（含持仓市值和收益计算）"""
    try:
        service = get_portfolio_service()
        summary = await service.get_account_summary(current_user["id"])
        return ok(data=summary.model_dump())
    except Exception as e:
        logger.error(f"获取账户摘要失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/account/initialize", response_model=dict)
async def initialize_account(
    request: AccountInitRequest,
    current_user: dict = Depends(get_current_user)
):
    """初始化资金账户（设置初始资金）"""
    try:
        service = get_portfolio_service()
        acc = await service.initialize_account(
            user_id=current_user["id"],
            initial_capital=request.initial_capital,
            currency=request.currency
        )
        acc.pop("_id", None)
        return ok(data=acc, message=f"已设置初始资金 {request.initial_capital:,.2f} {request.currency}")
    except Exception as e:
        logger.error(f"初始化资金账户失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/account/deposit", response_model=dict)
async def deposit(
    request: AccountTransactionRequest,
    current_user: dict = Depends(get_current_user)
):
    """入金"""
    if request.transaction_type != CapitalTransactionType.DEPOSIT:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="交易类型必须为 deposit"
        )
    try:
        service = get_portfolio_service()
        acc = await service.deposit(
            user_id=current_user["id"],
            amount=request.amount,
            currency=request.currency,
            description=request.description
        )
        acc.pop("_id", None)
        return ok(data=acc, message=f"入金成功 {request.amount:,.2f} {request.currency}")
    except Exception as e:
        logger.error(f"入金失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/account/withdraw", response_model=dict)
async def withdraw(
    request: AccountTransactionRequest,
    current_user: dict = Depends(get_current_user)
):
    """出金"""
    if request.transaction_type != CapitalTransactionType.WITHDRAW:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="交易类型必须为 withdraw"
        )
    try:
        service = get_portfolio_service()
        acc = await service.withdraw(
            user_id=current_user["id"],
            amount=request.amount,
            currency=request.currency,
            description=request.description
        )
        acc.pop("_id", None)
        return ok(data=acc, message=f"出金成功 {request.amount:,.2f} {request.currency}")
    except ValueError as ve:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(ve)
        )
    except Exception as e:
        logger.error(f"出金失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.put("/account/settings", response_model=dict)
async def update_account_settings(
    request: AccountSettingsRequest,
    current_user: dict = Depends(get_current_user)
):
    """更新账户设置"""
    try:
        service = get_portfolio_service()
        acc = await service.update_account_settings(
            user_id=current_user["id"],
            settings=request
        )
        acc.pop("_id", None)
        return ok(data=acc, message="账户设置已更新")
    except Exception as e:
        logger.error(f"更新账户设置失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/account/transactions", response_model=dict)
async def get_transactions(
    currency: str = Query(None, description="货币类型过滤"),
    limit: int = Query(50, description="返回数量限制"),
    current_user: dict = Depends(get_current_user)
):
    """获取资金交易记录"""
    try:
        service = get_portfolio_service()
        transactions = await service.get_transactions(
            user_id=current_user["id"],
            currency=currency,
            limit=limit
        )
        return ok(data={"items": transactions, "total": len(transactions)})
    except Exception as e:
        logger.error(f"获取资金交易记录失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


# ==================== 持仓变动记录接口 ====================

@router.get("/position-changes", response_model=dict)
async def get_position_changes(
    code: str = Query(None, description="股票代码过滤"),
    market: str = Query(None, description="市场过滤: CN/HK/US"),
    change_type: str = Query(None, description="变动类型: buy/add/reduce/sell/adjust"),
    limit: int = Query(100, description="返回数量限制"),
    skip: int = Query(0, description="跳过数量"),
    current_user: dict = Depends(get_current_user)
):
    """获取持仓变动记录"""
    try:
        service = get_portfolio_service()
        changes = await service.get_position_changes(
            user_id=current_user["id"],
            code=code,
            market=market,
            change_type=change_type,
            limit=limit,
            skip=skip
        )
        total = await service.get_position_changes_count(
            user_id=current_user["id"],
            code=code,
            market=market,
            change_type=change_type
        )
        return ok(data={
            "items": [c.model_dump() for c in changes],
            "total": total,
            "limit": limit,
            "skip": skip
        })
    except Exception as e:
        logger.error(f"获取持仓变动记录失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )
