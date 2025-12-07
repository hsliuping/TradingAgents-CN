"""
自选股分组管理 API

[PRO功能] 此模块为专业版功能，需要专业版授权
- 支持将自选股按策略分组
- 每个分组可配置独立的分析参数
- 与定时分析配置配合使用
"""

from fastapi import APIRouter, Depends, HTTPException
from typing import List
from bson import ObjectId

from app.core.database import get_mongo_db
from app.core.response import ok, fail
from app.core.permissions import require_pro, LicenseInfo
from app.routers.auth_db import get_current_user
from app.models.watchlist_group import (
    WatchlistGroup,
    WatchlistGroupCreate,
    WatchlistGroupUpdate,
    AddStocksToGroupRequest,
    RemoveStocksFromGroupRequest,
    MoveStocksRequest
)
from app.utils.timezone import now_tz
import logging

logger = logging.getLogger("app.routers.watchlist_groups")

# 整个路由器都需要 PRO 权限
router = APIRouter(
    prefix="/api/watchlist-groups",
    tags=["自选股分组"],
    dependencies=[Depends(require_pro)]
)


@router.get("")
async def list_groups(user: dict = Depends(get_current_user)):
    """获取用户的所有自选股分组 [PRO]"""
    db = get_mongo_db()
    user_id = str(user["id"])
    
    cursor = db.watchlist_groups.find({"user_id": user_id}).sort("sort_order", 1)
    groups = []
    
    async for doc in cursor:
        doc["id"] = str(doc.pop("_id"))
        groups.append(WatchlistGroup(**doc))
    
    return ok({"groups": [g.model_dump() for g in groups]})


@router.post("")
async def create_group(
    group_data: WatchlistGroupCreate,
    user: dict = Depends(get_current_user)
):
    """创建新的自选股分组 [PRO]"""
    db = get_mongo_db()
    user_id = str(user["id"])
    
    # 检查分组名称是否已存在
    existing = await db.watchlist_groups.find_one({
        "user_id": user_id,
        "name": group_data.name
    })
    
    if existing:
        return fail("分组名称已存在")
    
    # 获取当前最大排序值
    max_sort = await db.watchlist_groups.find_one(
        {"user_id": user_id},
        sort=[("sort_order", -1)]
    )
    next_sort = (max_sort["sort_order"] + 1) if max_sort else 0
    
    # 创建分组
    group_doc = {
        "user_id": user_id,
        "name": group_data.name,
        "description": group_data.description,
        "color": group_data.color,
        "icon": group_data.icon,
        "stock_codes": [],
        "analysis_depth": group_data.analysis_depth,
        "quick_analysis_model": group_data.quick_analysis_model,
        "deep_analysis_model": group_data.deep_analysis_model,
        "prompt_template_id": group_data.prompt_template_id,
        "sort_order": next_sort,
        "is_active": True,
        "created_at": now_tz(),
        "updated_at": now_tz()
    }
    
    result = await db.watchlist_groups.insert_one(group_doc)
    group_doc["id"] = str(result.inserted_id)
    group_doc.pop("_id", None)
    
    logger.info(f"✅ 创建自选股分组: {group_data.name} (用户: {user_id})")
    return ok({"group": group_doc, "message": "分组创建成功"})


@router.get("/{group_id}")
async def get_group(group_id: str, user: dict = Depends(get_current_user)):
    """获取分组详情"""
    db = get_mongo_db()
    user_id = str(user["id"])
    
    try:
        group = await db.watchlist_groups.find_one({
            "_id": ObjectId(group_id),
            "user_id": user_id
        })
    except Exception:
        return fail("无效的分组ID")
    
    if not group:
        return fail("分组不存在")
    
    group["id"] = str(group.pop("_id"))
    return ok({"group": group})


@router.put("/{group_id}")
async def update_group(
    group_id: str,
    group_data: WatchlistGroupUpdate,
    user: dict = Depends(get_current_user)
):
    """更新分组信息"""
    db = get_mongo_db()
    user_id = str(user["id"])
    
    try:
        oid = ObjectId(group_id)
    except Exception:
        return fail("无效的分组ID")
    
    # 检查分组是否存在
    group = await db.watchlist_groups.find_one({"_id": oid, "user_id": user_id})
    if not group:
        return fail("分组不存在")
    
    # 如果修改了名称，检查新名称是否已存在
    if group_data.name and group_data.name != group["name"]:
        existing = await db.watchlist_groups.find_one({
            "user_id": user_id,
            "name": group_data.name,
            "_id": {"$ne": oid}
        })
        if existing:
            return fail("分组名称已存在")
    
    # 构建更新数据
    update_data = group_data.model_dump(exclude_unset=True)
    update_data["updated_at"] = now_tz()
    
    await db.watchlist_groups.update_one(
        {"_id": oid},
        {"$set": update_data}
    )
    
    logger.info(f"✅ 更新自选股分组: {group_id} (用户: {user_id})")
    return ok({"message": "分组更新成功"})


@router.delete("/{group_id}")
async def delete_group(group_id: str, user: dict = Depends(get_current_user)):
    """删除分组"""
    db = get_mongo_db()
    user_id = str(user["id"])
    
    try:
        oid = ObjectId(group_id)
    except Exception:
        return fail("无效的分组ID")
    
    result = await db.watchlist_groups.delete_one({
        "_id": oid,
        "user_id": user_id
    })
    
    if result.deleted_count == 0:
        return fail("分组不存在")
    
    logger.info(f"✅ 删除自选股分组: {group_id} (用户: {user_id})")
    return ok({"message": "分组删除成功"})


@router.post("/{group_id}/stocks")
async def add_stocks_to_group(
    group_id: str,
    request: AddStocksToGroupRequest,
    user: dict = Depends(get_current_user)
):
    """添加股票到分组"""
    db = get_mongo_db()
    user_id = str(user["id"])

    try:
        oid = ObjectId(group_id)
    except Exception:
        return fail("无效的分组ID")

    # 检查分组是否存在
    group = await db.watchlist_groups.find_one({"_id": oid, "user_id": user_id})
    if not group:
        return fail("分组不存在")

    # 添加股票（去重）
    current_stocks = set(group.get("stock_codes", []))
    new_stocks = set(request.stock_codes)
    updated_stocks = list(current_stocks | new_stocks)

    await db.watchlist_groups.update_one(
        {"_id": oid},
        {
            "$set": {
                "stock_codes": updated_stocks,
                "updated_at": now_tz()
            }
        }
    )

    added_count = len(updated_stocks) - len(current_stocks)
    logger.info(f"✅ 添加 {added_count} 只股票到分组: {group_id} (用户: {user_id})")
    return ok({
        "message": f"成功添加 {added_count} 只股票",
        "total": len(updated_stocks)
    })


@router.delete("/{group_id}/stocks")
async def remove_stocks_from_group(
    group_id: str,
    request: RemoveStocksFromGroupRequest,
    user: dict = Depends(get_current_user)
):
    """从分组移除股票"""
    db = get_mongo_db()
    user_id = str(user["id"])

    try:
        oid = ObjectId(group_id)
    except Exception:
        return fail("无效的分组ID")

    # 检查分组是否存在
    group = await db.watchlist_groups.find_one({"_id": oid, "user_id": user_id})
    if not group:
        return fail("分组不存在")

    # 移除股票
    current_stocks = set(group.get("stock_codes", []))
    remove_stocks = set(request.stock_codes)
    updated_stocks = list(current_stocks - remove_stocks)

    await db.watchlist_groups.update_one(
        {"_id": oid},
        {
            "$set": {
                "stock_codes": updated_stocks,
                "updated_at": now_tz()
            }
        }
    )

    removed_count = len(current_stocks) - len(updated_stocks)
    logger.info(f"✅ 从分组移除 {removed_count} 只股票: {group_id} (用户: {user_id})")
    return ok({
        "message": f"成功移除 {removed_count} 只股票",
        "total": len(updated_stocks)
    })


@router.post("/{group_id}/stocks/move")
async def move_stocks_to_group(
    group_id: str,
    request: MoveStocksRequest,
    user: dict = Depends(get_current_user)
):
    """将股票从当前分组移动到其他分组"""
    db = get_mongo_db()
    user_id = str(user["id"])

    try:
        source_oid = ObjectId(group_id)
        target_oid = ObjectId(request.target_group_id)
    except Exception:
        return fail("无效的分组ID")

    # 检查两个分组是否都存在
    source_group = await db.watchlist_groups.find_one({"_id": source_oid, "user_id": user_id})
    target_group = await db.watchlist_groups.find_one({"_id": target_oid, "user_id": user_id})

    if not source_group:
        return fail("源分组不存在")
    if not target_group:
        return fail("目标分组不存在")

    # 从源分组移除
    source_stocks = set(source_group.get("stock_codes", []))
    move_stocks = set(request.stock_codes)
    updated_source_stocks = list(source_stocks - move_stocks)

    # 添加到目标分组
    target_stocks = set(target_group.get("stock_codes", []))
    updated_target_stocks = list(target_stocks | move_stocks)

    # 更新两个分组
    await db.watchlist_groups.update_one(
        {"_id": source_oid},
        {"$set": {"stock_codes": updated_source_stocks, "updated_at": now_tz()}}
    )
    await db.watchlist_groups.update_one(
        {"_id": target_oid},
        {"$set": {"stock_codes": updated_target_stocks, "updated_at": now_tz()}}
    )

    moved_count = len(source_stocks) - len(updated_source_stocks)
    logger.info(f"✅ 移动 {moved_count} 只股票: {group_id} -> {request.target_group_id} (用户: {user_id})")
    return ok({
        "message": f"成功移动 {moved_count} 只股票",
        "source_total": len(updated_source_stocks),
        "target_total": len(updated_target_stocks)
    })

