"""
标签管理 API
"""
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.routers.auth_db import get_current_user
from app.core.response import ok
from app.services.tags_service import tags_service

router = APIRouter(prefix="/tags", tags=["标签管理"])


class TagCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=30)
    color: Optional[str] = Field(default="#409EFF", max_length=20)
    sort_order: int = 0


class TagUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=30)
    color: Optional[str] = Field(default=None, max_length=20)
    sort_order: Optional[int] = None


class TagResponse(BaseModel):
    id: str
    name: str
    color: str
    sort_order: int
    created_at: str
    updated_at: str


@router.get("/", response_model=dict)
async def list_tags(current_user: dict = Depends(get_current_user)):
    try:
        tags = await tags_service.list_tags(current_user["id"])
        return ok(tags)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"获取标签失败: {e}")


@router.post("/", response_model=dict)
async def create_tag(payload: TagCreate, current_user: dict = Depends(get_current_user)):
    try:
        tag = await tags_service.create_tag(
            user_id=current_user["id"],
            name=payload.name,
            color=payload.color,
            sort_order=payload.sort_order,
        )
        return ok(tag, "创建成功")
    except Exception as e:
        # 可能违反唯一索引（同名），返回400
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"创建标签失败: {e}")


@router.put("/{tag_id}", response_model=dict)
async def update_tag(tag_id: str, payload: TagUpdate, current_user: dict = Depends(get_current_user)):
    try:
        success = await tags_service.update_tag(
            user_id=current_user["id"],
            tag_id=tag_id,
            name=payload.name,
            color=payload.color,
            sort_order=payload.sort_order,
        )
        if not success:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="标签不存在")
        return ok({"id": tag_id}, "更新成功")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"更新标签失败: {e}")


@router.delete("/{tag_id}", response_model=dict)
async def delete_tag(tag_id: str, current_user: dict = Depends(get_current_user)):
    try:
        success = await tags_service.delete_tag(current_user["id"], tag_id)
        if not success:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="标签不存在")
        return ok({"id": tag_id}, "删除成功")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"删除标签失败: {e}")

