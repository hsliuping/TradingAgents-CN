"""
用户自定义标签服务
"""
from __future__ import annotations
import logging
from typing import List, Optional, Dict, Any
from datetime import datetime
from bson import ObjectId

from app.core.database import get_mongo_db


logger = logging.getLogger(__name__)


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

    def _parse_tag_object_id(self, tag_id: str) -> Optional[ObjectId]:
        """安全解析标签 ObjectId，避免无效输入直接抛异常。"""
        return ObjectId(tag_id) if ObjectId.is_valid(tag_id) else None

    def _format_doc(self, doc: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "id": str(doc.get("_id")),
            "name": doc.get("name"),
            "color": doc.get("color") or "#409EFF",
            "sort_order": doc.get("sort_order", 0),
            "created_at": (doc.get("created_at") or datetime.utcnow()).isoformat(),
            "updated_at": (doc.get("updated_at") or datetime.utcnow()).isoformat(),
        }

    def _normalize_tag_list(self, tags: Optional[List[Any]]) -> List[str]:
        normalized: List[str] = []
        seen = set()

        for raw_tag in tags or []:
            tag = str(raw_tag or "").strip()
            if not tag or tag in seen:
                continue
            seen.add(tag)
            normalized.append(tag)

        return normalized

    def _replace_tag_name_in_favorites(
        self,
        favorites: Optional[List[Dict[str, Any]]],
        *,
        old_name: str,
        new_name: str,
    ) -> tuple[List[Dict[str, Any]], bool]:
        updated = False
        normalized_old = str(old_name or "").strip()
        normalized_new = str(new_name or "").strip()
        updated_favorites: List[Dict[str, Any]] = []

        for favorite in favorites or []:
            favorite_doc = dict(favorite)
            original_tags = favorite_doc.get("tags") or []
            replaced_tags = [
                normalized_new if str(tag or "").strip() == normalized_old else str(tag or "").strip()
                for tag in original_tags
            ]
            deduplicated_tags = self._normalize_tag_list(replaced_tags)
            if deduplicated_tags != original_tags:
                favorite_doc["tags"] = deduplicated_tags
                updated = True
            updated_favorites.append(favorite_doc)

        return updated_favorites, updated

    async def _sync_tag_rename_to_favorites(
        self,
        db,
        *,
        normalized_user_id: str,
        old_name: str,
        new_name: str,
    ) -> None:
        user_favorites_doc = await db.user_favorites.find_one({"user_id": normalized_user_id})
        if user_favorites_doc:
            updated_favorites, changed = self._replace_tag_name_in_favorites(
                user_favorites_doc.get("favorites"),
                old_name=old_name,
                new_name=new_name,
            )
            if changed:
                await db.user_favorites.update_one(
                    {"_id": user_favorites_doc["_id"]},
                    {"$set": {"favorites": updated_favorites, "updated_at": datetime.utcnow()}},
                )

        try:
            user_query = {"_id": ObjectId(normalized_user_id)} if ObjectId.is_valid(normalized_user_id) else {"_id": normalized_user_id}
            user_doc = await db.users.find_one(user_query)
            if user_doc:
                updated_favorites, changed = self._replace_tag_name_in_favorites(
                    user_doc.get("favorite_stocks"),
                    old_name=old_name,
                    new_name=new_name,
                )
                if changed:
                    await db.users.update_one(
                        user_query,
                        {"$set": {"favorite_stocks": updated_favorites}},
                    )
        except Exception as exc:
            logger.debug("同步 users 集合标签重命名失败 user_id=%s: %s", normalized_user_id, exc)

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
        tag_object_id = self._parse_tag_object_id(tag_id)
        if tag_object_id is None:
            return False

        db = await self._get_db()
        await self.ensure_indexes()
        normalized_user_id = self._normalize_user_id(user_id)

        existing_tag = await db.user_tags.find_one({"_id": tag_object_id, "user_id": normalized_user_id})
        if not existing_tag:
            return False

        old_name = str(existing_tag.get("name") or "").strip()
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
            {"_id": tag_object_id, "user_id": normalized_user_id},
            {"$set": update}
        )
        if result.matched_count <= 0:
            return False

        new_name = str(update.get("name") or old_name).strip()
        if new_name and old_name and new_name != old_name:
            await self._sync_tag_rename_to_favorites(
                db,
                normalized_user_id=normalized_user_id,
                old_name=old_name,
                new_name=new_name,
            )

        return True

    async def delete_tag(self, user_id: str, tag_id: str) -> bool:
        tag_object_id = self._parse_tag_object_id(tag_id)
        if tag_object_id is None:
            return False

        db = await self._get_db()
        await self.ensure_indexes()
        normalized_user_id = self._normalize_user_id(user_id)

        tag_doc = await db.user_tags.find_one({"_id": tag_object_id, "user_id": normalized_user_id})
        if not tag_doc:
            return False

        tag_name = (tag_doc.get("name") or "").strip()
        result = await db.user_tags.delete_one({"_id": tag_object_id, "user_id": normalized_user_id})
        if result.deleted_count <= 0:
            return False

        if tag_name:
            # 同步从字符串 user_id 版本的自选股记录中移除该标签
            await db.user_favorites.update_many(
                {"user_id": normalized_user_id},
                {
                    "$pull": {"favorites.$[].tags": tag_name},
                    "$set": {"updated_at": datetime.utcnow()}
                }
            )

            # 同步从 users 集合（ObjectId 或字符串 _id）中的自选股记录移除该标签
            try:
                if ObjectId.is_valid(normalized_user_id):
                    await db.users.update_one(
                        {"_id": ObjectId(normalized_user_id)},
                        {"$pull": {"favorite_stocks.$[].tags": tag_name}}
                    )
                else:
                    await db.users.update_one(
                        {"_id": normalized_user_id},
                        {"$pull": {"favorite_stocks.$[].tags": tag_name}}
                    )
            except Exception as exc:
                # 某些部署下用户数据不在 users 集合，忽略即可
                logger.debug("同步 users 集合标签删除失败 user_id=%s: %s", normalized_user_id, exc)

        return True


# 全局实例
tags_service = TagsService()
