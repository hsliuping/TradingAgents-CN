"""
用户自定义标签服务
"""
from __future__ import annotations
from typing import List, Optional, Dict, Any
from datetime import datetime
from bson import ObjectId

from app.core.database import get_mongo_db


class TagsService:
    def __init__(self) -> None:
        self.db = None
        self._indexes_ensured = False

    async def _get_db(self):
        if self.db is None:
            self.db = get_mongo_db()
        return self.db

    async def ensure_indexes(self) -> None:
        if self._indexes_ensured:
            return
        db = await self._get_db()
        # 每个用户的标签名唯一
        await db.user_tags.create_index([("user_id", 1), ("name", 1)], unique=True, name="uniq_user_tag_name")
        await db.user_tags.create_index([("user_id", 1), ("sort_order", 1)], name="idx_user_tag_sort")
        self._indexes_ensured = True

    def _normalize_user_id(self, user_id: str) -> str:
        # 统一为字符串存储，便于兼容开源版(admin)与未来ObjectId
        return str(user_id)

    def _format_doc(self, doc: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "id": str(doc.get("_id")),
            "name": doc.get("name"),
            "color": doc.get("color") or "#409EFF",
            "sort_order": doc.get("sort_order", 0),
            "created_at": (doc.get("created_at") or datetime.utcnow()).isoformat(),
            "updated_at": (doc.get("updated_at") or datetime.utcnow()).isoformat(),
        }

    async def list_tags(self, user_id: str) -> List[Dict[str, Any]]:
        db = await self._get_db()
        await self.ensure_indexes()
        cursor = db.user_tags.find({"user_id": self._normalize_user_id(user_id)}).sort([
            ("sort_order", 1), ("name", 1)
        ])
        docs = await cursor.to_list(length=None)
        return [self._format_doc(d) for d in docs]

    async def create_tag(self, user_id: str, name: str, color: Optional[str] = None, sort_order: int = 0) -> Dict[str, Any]:
        db = await self._get_db()
        await self.ensure_indexes()
        now = datetime.utcnow()
        doc = {
            "user_id": self._normalize_user_id(user_id),
            "name": name.strip(),
            "color": color or "#409EFF",
            "sort_order": int(sort_order or 0),
            "created_at": now,
            "updated_at": now,
        }
        result = await db.user_tags.insert_one(doc)
        doc["_id"] = result.inserted_id
        return self._format_doc(doc)

    async def update_tag(self, user_id: str, tag_id: str, *, name: Optional[str] = None, color: Optional[str] = None, sort_order: Optional[int] = None) -> bool:
        db = await self._get_db()
        await self.ensure_indexes()
        update: Dict[str, Any] = {"updated_at": datetime.utcnow()}
        if name is not None:
            update["name"] = name.strip()
        if color is not None:
            update["color"] = color
        if sort_order is not None:
            update["sort_order"] = int(sort_order)
        if len(update) == 1:  # 只有updated_at
            return True
        result = await db.user_tags.update_one(
            {"_id": ObjectId(tag_id), "user_id": self._normalize_user_id(user_id)},
            {"$set": update}
        )
        return result.matched_count > 0

    async def delete_tag(self, user_id: str, tag_id: str) -> bool:
        db = await self._get_db()
        await self.ensure_indexes()
        result = await db.user_tags.delete_one({"_id": ObjectId(tag_id), "user_id": self._normalize_user_id(user_id)})
        return result.deleted_count > 0


# 全局实例
tags_service = TagsService()

