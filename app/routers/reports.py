"""
分析报告管理API路由
"""
import os
import json
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel

from .auth_db import get_current_user
from ..core.database import get_mongo_db
import logging

logger = logging.getLogger("webapi")

# 股票名称缓存
_stock_name_cache = {}

def get_stock_name(stock_code: str) -> str:
    """
    获取股票名称
    优先级：缓存 -> MongoDB -> 默认返回股票代码
    """
    global _stock_name_cache

    # 检查缓存
    if stock_code in _stock_name_cache:
        return _stock_name_cache[stock_code]

    try:
        # 从 MongoDB 获取股票名称
        from ..core.database import get_mongo_db_sync
        db = get_mongo_db_sync()

        # 查询 stock_basic_info 集合
        stock_info = db.stock_basic_info.find_one({"symbol": stock_code})

        if stock_info and stock_info.get("name"):
            stock_name = stock_info["name"]
            _stock_name_cache[stock_code] = stock_name
            return stock_name

        # 如果没有找到，返回股票代码
        _stock_name_cache[stock_code] = stock_code
        return stock_code

    except Exception as e:
        logger.warning(f"⚠️ 获取股票名称失败 {stock_code}: {e}")
        return stock_code


# 统一构建报告查询：支持 _id(ObjectId) / analysis_id / task_id 三种
def _build_report_query(report_id: str) -> Dict[str, Any]:
    ors = [
        {"analysis_id": report_id},
        {"task_id": report_id},
    ]
    try:
        from bson import ObjectId
        ors.append({"_id": ObjectId(report_id)})
    except Exception:
        pass
    return {"$or": ors}

router = APIRouter(prefix="/api/reports", tags=["reports"])

class ReportFilter(BaseModel):
    """报告筛选参数"""
    search_keyword: Optional[str] = None
    market_filter: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    stock_code: Optional[str] = None
    report_type: Optional[str] = None

class ReportListResponse(BaseModel):
    """报告列表响应"""
    reports: List[Dict[str, Any]]
    total: int
    page: int
    page_size: int

@router.get("/list", response_model=Dict[str, Any])
async def get_reports_list(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    search_keyword: Optional[str] = Query(None, description="搜索关键词"),
    market_filter: Optional[str] = Query(None, description="市场筛选（A股/港股/美股）"),
    start_date: Optional[str] = Query(None, description="开始日期"),
    end_date: Optional[str] = Query(None, description="结束日期"),
    stock_code: Optional[str] = Query(None, description="股票代码"),
    user: dict = Depends(get_current_user)
):
    """获取分析报告列表"""
    try:
        logger.info(f"🔍 获取报告列表: 用户={user['id']}, 页码={page}, 每页={page_size}, 市场={market_filter}")

        db = get_mongo_db()

        # 构建查询条件
        query = {}

        # 搜索关键词
        if search_keyword:
            query["$or"] = [
                {"stock_symbol": {"$regex": search_keyword, "$options": "i"}},
                {"analysis_id": {"$regex": search_keyword, "$options": "i"}},
                {"summary": {"$regex": search_keyword, "$options": "i"}}
            ]

        # 市场筛选
        if market_filter:
            query["market_type"] = market_filter

        # 股票代码筛选
        if stock_code:
            query["stock_symbol"] = stock_code

        # 日期范围筛选
        if start_date or end_date:
            date_query = {}
            if start_date:
                date_query["$gte"] = start_date
            if end_date:
                date_query["$lte"] = end_date
            query["analysis_date"] = date_query

        logger.info(f"📊 查询条件: {query}")

        # 计算总数
        total = await db.analysis_reports.count_documents(query)

        # 分页查询
        skip = (page - 1) * page_size
        cursor = db.analysis_reports.find(query).sort("created_at", -1).skip(skip).limit(page_size)

        reports = []
        async for doc in cursor:
            # 转换为前端需要的格式
            stock_code = doc.get("stock_symbol", "")
            # 🔥 优先使用MongoDB中保存的股票名称，如果没有则查询
            stock_name = doc.get("stock_name")
            if not stock_name:
                stock_name = get_stock_name(stock_code)

            # 🔥 获取市场类型，如果没有则根据股票代码推断
            market_type = doc.get("market_type")
            if not market_type:
                from tradingagents.utils.stock_utils import StockUtils
                market_info = StockUtils.get_market_info(stock_code)
                market_type_map = {
                    "china_a": "A股",
                    "hong_kong": "港股",
                    "us": "美股",
                    "unknown": "A股"
                }
                market_type = market_type_map.get(market_info.get("market", "unknown"), "A股")

            report = {
                "id": str(doc["_id"]),
                "analysis_id": doc.get("analysis_id", ""),
                "title": f"{stock_name}({stock_code}) 分析报告",
                "stock_code": stock_code,
                "stock_name": stock_name,
                "market_type": market_type,  # 🔥 添加市场类型字段
                "model_info": doc.get("model_info", "Unknown"),  # 🔥 添加模型信息字段
                "type": "single",  # 目前主要是单股分析
                "format": "markdown",  # 主要格式
                "status": doc.get("status", "completed"),
                "created_at": doc.get("created_at", datetime.now()).isoformat(),
                "analysis_date": doc.get("analysis_date", ""),
                "analysts": doc.get("analysts", []),
                "research_depth": doc.get("research_depth", 1),
                "summary": doc.get("summary", ""),
                "file_size": len(str(doc.get("reports", {}))),  # 估算大小
                "source": doc.get("source", "unknown"),
                "task_id": doc.get("task_id", "")
            }
            reports.append(report)

        logger.info(f"✅ 查询完成: 总数={total}, 返回={len(reports)}")

        return {
            "success": True,
            "data": {
                "reports": reports,
                "total": total,
                "page": page,
                "page_size": page_size
            },
            "message": "报告列表获取成功"
        }

    except Exception as e:
        logger.error(f"❌ 获取报告列表失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{report_id}/detail")
async def get_report_detail(
    report_id: str,
    user: dict = Depends(get_current_user)
):
    """获取报告详情"""
    try:
        logger.info(f"🔍 获取报告详情: {report_id}")

        db = get_mongo_db()

        # 支持 ObjectId / analysis_id / task_id
        query = _build_report_query(report_id)
        doc = await db.analysis_reports.find_one(query)

        if not doc:
            # 兜底：从 analysis_tasks.result 中还原报告详情
            logger.info(f"⚠️ 未在analysis_reports找到，尝试从analysis_tasks还原: {report_id}")
            tasks_doc = await db.analysis_tasks.find_one(
                {"$or": [{"task_id": report_id}, {"result.analysis_id": report_id}]},
                {"result": 1, "task_id": 1, "stock_code": 1, "created_at": 1, "completed_at": 1}
            )
            if not tasks_doc or not tasks_doc.get("result"):
                raise HTTPException(status_code=404, detail="报告不存在")

            r = tasks_doc["result"] or {}
            created_at = tasks_doc.get("created_at")
            updated_at = tasks_doc.get("completed_at") or created_at
            def to_iso(x):
                return x.isoformat() if hasattr(x, "isoformat") else (x or "")

            stock_symbol = r.get("stock_symbol", r.get("stock_code", tasks_doc.get("stock_code", "")))
            stock_name = r.get("stock_name")
            if not stock_name:
                stock_name = get_stock_name(stock_symbol)

            report = {
                "id": tasks_doc.get("task_id", report_id),
                "analysis_id": r.get("analysis_id", ""),
                "stock_symbol": stock_symbol,
                "stock_name": stock_name,  # 🔥 添加股票名称字段
                "model_info": r.get("model_info", "Unknown"),  # 🔥 添加模型信息字段
                "analysis_date": r.get("analysis_date", ""),
                "status": r.get("status", "completed"),
                "created_at": to_iso(created_at),
                "updated_at": to_iso(updated_at),
                "analysts": r.get("analysts", []),
                "research_depth": r.get("research_depth", 1),
                "summary": r.get("summary", ""),
                "reports": r.get("reports", {}),
                "source": "analysis_tasks",
                "task_id": tasks_doc.get("task_id", report_id),
                "recommendation": r.get("recommendation", ""),
                "confidence_score": r.get("confidence_score", 0.0),
                "risk_level": r.get("risk_level", "中等"),
                "key_points": r.get("key_points", []),
                "execution_time": r.get("execution_time", 0),
                "tokens_used": r.get("tokens_used", 0)
            }
        else:
            # 转换为详细格式（analysis_reports 命中）
            stock_symbol = doc.get("stock_symbol", "")
            stock_name = doc.get("stock_name")
            if not stock_name:
                stock_name = get_stock_name(stock_symbol)

            report = {
                "id": str(doc["_id"]),
                "analysis_id": doc.get("analysis_id", ""),
                "stock_symbol": stock_symbol,
                "stock_name": stock_name,  # 🔥 添加股票名称字段
                "model_info": doc.get("model_info", "Unknown"),  # 🔥 添加模型信息字段
                "analysis_date": doc.get("analysis_date", ""),
                "status": doc.get("status", "completed"),
                "created_at": doc.get("created_at", datetime.now()).isoformat(),
                "updated_at": doc.get("updated_at", datetime.now()).isoformat(),
                "analysts": doc.get("analysts", []),
                "research_depth": doc.get("research_depth", 1),
                "summary": doc.get("summary", ""),
                "reports": doc.get("reports", {}),
                "source": doc.get("source", "unknown"),
                "task_id": doc.get("task_id", ""),
                "recommendation": doc.get("recommendation", ""),
                "confidence_score": doc.get("confidence_score", 0.0),
                "risk_level": doc.get("risk_level", "中等"),
                "key_points": doc.get("key_points", []),
                "execution_time": doc.get("execution_time", 0),
                "tokens_used": doc.get("tokens_used", 0)
            }

        return {
            "success": True,
            "data": report,
            "message": "报告详情获取成功"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ 获取报告详情失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{report_id}/content/{module}")
async def get_report_module_content(
    report_id: str,
    module: str,
    user: dict = Depends(get_current_user)
):
    """获取报告特定模块的内容"""
    try:
        logger.info(f"🔍 获取报告模块内容: {report_id}/{module}")

        db = get_mongo_db()

        # 查询报告（支持多种ID）
        query = _build_report_query(report_id)
        doc = await db.analysis_reports.find_one(query)

        if not doc:
            raise HTTPException(status_code=404, detail="报告不存在")

        reports = doc.get("reports", {})

        if module not in reports:
            raise HTTPException(status_code=404, detail=f"模块 {module} 不存在")

        content = reports[module]

        return {
            "success": True,
            "data": {
                "module": module,
                "content": content,
                "content_type": "markdown" if isinstance(content, str) else "json"
            },
            "message": "模块内容获取成功"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ 获取报告模块内容失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/{report_id}")
async def delete_report(
    report_id: str,
    user: dict = Depends(get_current_user)
):
    """删除报告"""
    try:
        logger.info(f"🗑️ 删除报告: {report_id}")

        db = get_mongo_db()

        # 查询报告（支持多种ID）
        query = _build_report_query(report_id)
        result = await db.analysis_reports.delete_one(query)

        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="报告不存在")

        logger.info(f"✅ 报告删除成功: {report_id}")

        return {
            "success": True,
            "message": "报告删除成功"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ 删除报告失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{report_id}/download")
async def download_report(
    report_id: str,
    format: str = Query("markdown", description="下载格式: markdown, json, pdf"),
    user: dict = Depends(get_current_user)
):
    """下载报告"""
    try:
        logger.info(f"📥 下载报告: {report_id}, 格式: {format}")

        db = get_mongo_db()

        # 查询报告（支持多种ID）
        query = _build_report_query(report_id)
        doc = await db.analysis_reports.find_one(query)

        if not doc:
            raise HTTPException(status_code=404, detail="报告不存在")

        stock_symbol = doc.get("stock_symbol", "unknown")
        analysis_date = doc.get("analysis_date", datetime.now().strftime("%Y-%m-%d"))

        if format == "json":
            # JSON格式下载
            content = json.dumps(doc, ensure_ascii=False, indent=2, default=str)
            filename = f"{stock_symbol}_{analysis_date}_report.json"
            media_type = "application/json"

        elif format == "markdown":
            # Markdown格式下载
            reports = doc.get("reports", {})
            content_parts = []

            # 添加标题
            content_parts.append(f"# {stock_symbol} 分析报告")
            content_parts.append(f"**分析日期**: {analysis_date}")
            content_parts.append(f"**分析师**: {', '.join(doc.get('analysts', []))}")
            content_parts.append(f"**研究深度**: {doc.get('research_depth', 1)}")
            content_parts.append("")

            # 添加摘要
            if doc.get("summary"):
                content_parts.append("## 执行摘要")
                content_parts.append(doc["summary"])
                content_parts.append("")

            # 添加各模块内容
            for module_name, module_content in reports.items():
                if isinstance(module_content, str) and module_content.strip():
                    content_parts.append(f"## {module_name}")
                    content_parts.append(module_content)
                    content_parts.append("")

            content = "\n".join(content_parts)
            filename = f"{stock_symbol}_{analysis_date}_report.md"
            media_type = "text/markdown"

        else:
            raise HTTPException(status_code=400, detail="不支持的下载格式")

        # 返回文件流
        def generate():
            yield content.encode('utf-8')

        return StreamingResponse(
            generate(),
            media_type=media_type,
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ 下载报告失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))
