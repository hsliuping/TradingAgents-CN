"""
超短行情分析API路由
专门用于分析A股股票的超短期行情，预测明日涨停、上涨、下跌的概率
"""

from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
import logging

from app.routers.auth_db import get_current_user
from app.services.short_term_analysis_service import get_short_term_analysis_service
from app.services.config_service import ConfigService

router = APIRouter()
logger = logging.getLogger("webapi")
config_service = ConfigService()


class ShortTermAnalysisRequest(BaseModel):
    """超短行情分析请求"""
    ticker: str = Field(..., description="股票代码（A股6位数字）", example="000001")
    analysis_date: str = Field(..., description="分析日期（格式：YYYY-MM-DD）", example="2025-01-17")
    llm_provider: Optional[str] = Field(None, description="LLM提供商（可选，默认从配置获取）")
    llm_model: Optional[str] = Field(None, description="LLM模型名称（可选，默认从配置获取）")


class ShortTermAnalysisResponse(BaseModel):
    """超短行情分析响应"""
    success: bool
    ticker: str
    analysis_date: str
    report: Optional[str] = None
    probabilities: Optional[Dict[str, Optional[float]]] = None
    error: Optional[str] = None
    timestamp: str


@router.post("/analyze", response_model=ShortTermAnalysisResponse)
async def analyze_short_term(
    request: ShortTermAnalysisRequest,
    user: dict = Depends(get_current_user)
):
    """
    执行超短行情分析
    
    分析A股股票的超短期行情，预测明日涨停、上涨、下跌的概率
    
    需要的数据包括：
    1. 股票基本信息
    2. 历史K线数据（最近30天）
    3. 财务数据
    4. 新闻数据
    5. 打板相关数据（龙虎榜、涨跌停历史、热度数据、板块数据）
    """
    try:
        logger.info(f"🎯 [超短行情分析] 收到分析请求: ticker={request.ticker}, date={request.analysis_date}")
        logger.info(f"👤 [超短行情分析] 用户: {user.get('id', 'unknown')}")
        
        # 获取默认LLM配置（如果用户未指定）
        if not request.llm_provider or not request.llm_model:
            system_config = await config_service.get_system_config()
            if system_config and system_config.llm_configs:
                # 使用第一个可用的LLM配置
                default_llm = system_config.llm_configs[0]
                llm_provider = request.llm_provider or (default_llm.provider.value if hasattr(default_llm.provider, 'value') else str(default_llm.provider))
                llm_model = request.llm_model or default_llm.model_name
            else:
                # 使用默认值
                llm_provider = request.llm_provider or "dashscope"
                llm_model = request.llm_model or "qwen-max"
        else:
            llm_provider = request.llm_provider
            llm_model = request.llm_model
        
        logger.info(f"🤖 [超短行情分析] 使用LLM: {llm_provider}/{llm_model}")
        
        # 获取服务实例
        service = get_short_term_analysis_service()
        
        # 执行分析
        result = await service.analyze_short_term(
            ticker=request.ticker,
            analysis_date=request.analysis_date,
            llm_provider=llm_provider,
            llm_model=llm_model,
            user_id=user.get("id")
        )
        
        logger.info(f"✅ [超短行情分析] 分析完成: ticker={request.ticker}, success={result.get('success')}")
        
        return result
        
    except Exception as e:
        logger.error(f"❌ [超短行情分析] 分析失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"分析失败: {str(e)}")


@router.get("/analyze", response_model=ShortTermAnalysisResponse)
async def analyze_short_term_get(
    ticker: str = Query(..., description="股票代码（A股6位数字）"),
    analysis_date: str = Query(..., description="分析日期（格式：YYYY-MM-DD）"),
    llm_provider: Optional[str] = Query(None, description="LLM提供商（可选）"),
    llm_model: Optional[str] = Query(None, description="LLM模型名称（可选）"),
    user: dict = Depends(get_current_user)
):
    """
    GET方式执行超短行情分析（方便测试）
    """
    request = ShortTermAnalysisRequest(
        ticker=ticker,
        analysis_date=analysis_date,
        llm_provider=llm_provider,
        llm_model=llm_model
    )
    return await analyze_short_term(request, user)


class BatchShortTermAnalysisRequest(BaseModel):
    """批量超短行情分析请求"""
    title: str = Field(..., description="批次标题")
    description: Optional[str] = Field(None, description="批次描述")
    symbols: List[str] = Field(..., description="股票代码列表（A股6位数字）")
    analysis_date: str = Field(..., description="分析日期（格式：YYYY-MM-DD）")
    llm_provider: Optional[str] = Field(None, description="LLM提供商（可选）")
    llm_model: Optional[str] = Field(None, description="LLM模型名称（可选）")


class BatchShortTermAnalysisResponse(BaseModel):
    """批量超短行情分析响应"""
    success: bool
    data: Dict[str, Any]
    message: Optional[str] = None


@router.post("/batch", response_model=BatchShortTermAnalysisResponse)
async def analyze_short_term_batch(
    request: BatchShortTermAnalysisRequest,
    user: dict = Depends(get_current_user)
):
    """
    批量超短行情分析
    
    对多只A股股票进行超短行情分析，预测明日涨停、上涨、下跌的概率
    """
    try:
        logger.info(f"🎯 [批量超短行情分析] 收到批量分析请求: title={request.title}, symbols={len(request.symbols)}只")
        logger.info(f"👤 [批量超短行情分析] 用户: {user.get('id', 'unknown')}")
        
        # 验证股票代码（仅支持A股6位数字）
        import re
        invalid_symbols = []
        for symbol in request.symbols:
            clean_symbol = symbol.split('.')[0].strip()
            if not re.match(r'^\d{6}$', clean_symbol):
                invalid_symbols.append(symbol)
        
        if invalid_symbols:
            raise HTTPException(
                status_code=400,
                detail=f"以下股票代码格式无效（仅支持A股6位数字）：{', '.join(invalid_symbols)}"
            )
        
        # 获取默认LLM配置（如果用户未指定）
        if not request.llm_provider or not request.llm_model:
            system_config = await config_service.get_system_config()
            if system_config and system_config.llm_configs:
                default_llm = system_config.llm_configs[0]
                llm_provider = request.llm_provider or (default_llm.provider.value if hasattr(default_llm.provider, 'value') else str(default_llm.provider))
                llm_model = request.llm_model or default_llm.model_name
            else:
                llm_provider = request.llm_provider or "dashscope"
                llm_model = request.llm_model or "qwen-max"
        else:
            llm_provider = request.llm_provider
            llm_model = request.llm_model
        
        logger.info(f"🤖 [批量超短行情分析] 使用LLM: {llm_provider}/{llm_model}")
        
        # 创建批量分析任务
        import uuid
        from datetime import datetime
        from app.core.database import get_mongo_db
        
        db = get_mongo_db()
        batch_id = str(uuid.uuid4())
        task_ids = []
        
        # 为每只股票创建分析任务
        for symbol in request.symbols:
            task_id = str(uuid.uuid4())
            task_ids.append(task_id)
            
            # 创建任务记录
            task_doc = {
                "task_id": task_id,
                "batch_id": batch_id,
                "user_id": user.get("id"),
                "symbol": symbol,
                "analysis_date": request.analysis_date,
                "analysis_type": "short_term",
                "status": "pending",
                "llm_provider": llm_provider,
                "llm_model": llm_model,
                "created_at": datetime.now(),
                "updated_at": datetime.now()
            }
            
            await db["analysis_tasks"].insert_one(task_doc)
        
        # 创建批次记录
        batch_doc = {
            "batch_id": batch_id,
            "user_id": user.get("id"),
            "title": request.title,
            "description": request.description,
            "analysis_type": "short_term",
            "symbols": request.symbols,
            "analysis_date": request.analysis_date,
            "total_tasks": len(request.symbols),
            "completed_tasks": 0,
            "failed_tasks": 0,
            "status": "pending",
            "llm_provider": llm_provider,
            "llm_model": llm_model,
            "created_at": datetime.now(),
            "updated_at": datetime.now()
        }
        
        await db["analysis_batches"].insert_one(batch_doc)
        
        # 异步执行批量分析任务
        from app.services.short_term_analysis_service import get_short_term_analysis_service
        service = get_short_term_analysis_service()
        
        # 使用后台任务执行分析
        import asyncio
        asyncio.create_task(execute_batch_short_term_analysis(
            batch_id, task_ids, request.symbols, request.analysis_date,
            llm_provider, llm_model, user.get("id")
        ))
        
        logger.info(f"✅ [批量超短行情分析] 批量分析任务已创建: batch_id={batch_id}, total_tasks={len(request.symbols)}")
        
        return {
            "success": True,
            "data": {
                "batch_id": batch_id,
                "total_tasks": len(request.symbols),
                "task_ids": task_ids
            },
            "message": "批量分析任务已提交"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ [批量超短行情分析] 批量分析失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"批量分析失败: {str(e)}")


async def execute_batch_short_term_analysis(
    batch_id: str,
    task_ids: List[str],
    symbols: List[str],
    analysis_date: str,
    llm_provider: str,
    llm_model: str,
    user_id: str
):
    """执行批量超短行情分析（后台任务）"""
    from app.core.database import get_mongo_db
    from app.services.short_term_analysis_service import get_short_term_analysis_service
    from datetime import datetime
    
    db = get_mongo_db()
    service = get_short_term_analysis_service()
    
    completed = 0
    failed = 0
    
    try:
        # 更新批次状态为运行中
        await db["analysis_batches"].update_one(
            {"batch_id": batch_id},
            {"$set": {"status": "running", "updated_at": datetime.now()}}
        )
        
        # 逐个执行分析任务
        for i, (task_id, symbol) in enumerate(zip(task_ids, symbols)):
            try:
                # 更新任务状态为运行中
                await db["analysis_tasks"].update_one(
                    {"task_id": task_id},
                    {"$set": {"status": "running", "updated_at": datetime.now()}}
                )
                
                # 执行分析
                result = await service.analyze_short_term(
                    ticker=symbol,
                    analysis_date=analysis_date,
                    llm_provider=llm_provider,
                    llm_model=llm_model,
                    user_id=user_id
                )
                
                # 更新任务状态和结果
                await db["analysis_tasks"].update_one(
                    {"task_id": task_id},
                    {
                        "$set": {
                            "status": "completed" if result.get("success") else "failed",
                            "result": result,
                            "updated_at": datetime.now()
                        }
                    }
                )
                
                if result.get("success"):
                    completed += 1
                else:
                    failed += 1
                    
            except Exception as e:
                logger.error(f"❌ [批量超短行情分析] 任务 {task_id} 执行失败: {e}")
                failed += 1
                
                # 更新任务状态为失败
                await db["analysis_tasks"].update_one(
                    {"task_id": task_id},
                    {
                        "$set": {
                            "status": "failed",
                            "error": str(e),
                            "updated_at": datetime.now()
                        }
                    }
                )
        
        # 更新批次状态
        final_status = "completed" if failed == 0 else ("partial" if completed > 0 else "failed")
        await db["analysis_batches"].update_one(
            {"batch_id": batch_id},
            {
                "$set": {
                    "status": final_status,
                    "completed_tasks": completed,
                    "failed_tasks": failed,
                    "updated_at": datetime.now()
                }
            }
        )
        
        logger.info(f"✅ [批量超短行情分析] 批次 {batch_id} 完成: completed={completed}, failed={failed}")
        
    except Exception as e:
        logger.error(f"❌ [批量超短行情分析] 批次 {batch_id} 执行失败: {e}", exc_info=True)
        await db["analysis_batches"].update_one(
            {"batch_id": batch_id},
            {
                "$set": {
                    "status": "failed",
                    "error": str(e),
                    "updated_at": datetime.now()
                }
            }
        )

