"""
持仓分析API路由
提供持仓管理和AI分析接口

[PRO功能] 此模块为专业版功能，需要专业版授权
"""

from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel
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
        result = {
            "task_id": task["task_id"],
            "code": task["task_params"].get("code"),
            "market": task["task_params"].get("market"),
            "status": task["status"].value if hasattr(task["status"], "value") else task["status"],
            "message": task.get("message"),
            "progress": task.get("progress", 0),
            "created_at": task["created_at"].isoformat() if task.get("created_at") else None,
            "started_at": task["started_at"].isoformat() if task.get("started_at") else None,
            "completed_at": task["completed_at"].isoformat() if task.get("completed_at") else None,
            "result": task.get("result"),
            "error_message": task.get("error_message"),
        }

        return ok(data=result)
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
    current_user: dict = Depends(get_current_user)
):
    """按股票代码获取最新的分析报告"""
    try:
        service = get_portfolio_service()
        report = await service.get_latest_position_analysis(
            user_id=current_user["id"],
            code=code,
            market=market
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
    current_user: dict = Depends(get_current_user)
):
    """获取单股分析历史"""
    try:
        service = get_portfolio_service()
        result = await service.get_position_analysis_history(
            user_id=current_user["id"],
            position_id=position_id,
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
        logger.error(f"获取单股分析历史失败: {e}")
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
