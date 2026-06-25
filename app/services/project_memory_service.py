"""L4 项目长期记忆服务。"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional

from app.models.project_memory import (
    DEFAULT_PROJECT_MEMORY_PROJECT_ID,
    ProjectMemoryCategory,
    ProjectMemoryItem,
)
from app.services.project_memory_defaults import get_default_project_memory_items
from app.utils.timezone import now_tz


PROJECT_MEMORY_COLLECTION = "project_memory_items"

_CATEGORY_LABELS = {
    ProjectMemoryCategory.PROJECT_RULE.value: "项目规则",
    ProjectMemoryCategory.GOVERNANCE_CONSTRAINT.value: "治理约束",
    ProjectMemoryCategory.ANALYSIS_OUTPUT_CONSTRAINT.value: "输出约束",
    ProjectMemoryCategory.RESEARCH_TEMPLATE.value: "研究模板",
}

_CATEGORY_ORDER = [
    ProjectMemoryCategory.PROJECT_RULE.value,
    ProjectMemoryCategory.GOVERNANCE_CONSTRAINT.value,
    ProjectMemoryCategory.ANALYSIS_OUTPUT_CONSTRAINT.value,
    ProjectMemoryCategory.RESEARCH_TEMPLATE.value,
]


class ProjectMemoryService:
    def __init__(self, db: Any):
        self.db = db
        self.collection = db[PROJECT_MEMORY_COLLECTION]

    async def upsert_item(
        self,
        *,
        memory_key: str,
        title: str,
        content: str,
        category: str,
        project_id: str = DEFAULT_PROJECT_MEMORY_PROJECT_ID,
        priority: int = 100,
        active: bool = True,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        updated_by: str = "",
    ) -> ProjectMemoryItem:
        now = now_tz()
        query = {"project_id": project_id, "memory_key": memory_key}
        update = {
            "$set": {
                "title": title.strip(),
                "content": content.strip(),
                "category": category,
                "priority": priority,
                "active": active,
                "tags": self._normalize_tags(tags),
                "metadata": dict(metadata or {}),
                "updated_by": updated_by,
                "updated_at": now,
            },
            "$setOnInsert": {
                "memory_id": str(uuid.uuid4()),
                "project_id": project_id,
                "memory_key": memory_key,
                "created_at": now,
            },
        }
        await self.collection.update_one(query, update, upsert=True)
        doc = await self.collection.find_one(query)
        return self._to_item(doc or {**query, **update["$set"], **update["$setOnInsert"]})

    async def list_items(
        self,
        *,
        project_id: str = DEFAULT_PROJECT_MEMORY_PROJECT_ID,
        categories: Optional[Iterable[str]] = None,
        active_only: bool = True,
        limit: int = 50,
    ) -> List[ProjectMemoryItem]:
        query: Dict[str, Any] = {"project_id": project_id}
        category_list = [str(item) for item in (categories or []) if str(item).strip()]
        if category_list:
            query["category"] = {"$in": category_list}
        if active_only:
            query["active"] = True

        docs = await self.collection.find(query).sort([("priority", 1), ("updated_at", -1)]).limit(limit).to_list(length=limit)
        return [self._to_item(doc) for doc in docs]

    async def build_prompt_block(
        self,
        *,
        project_id: str = DEFAULT_PROJECT_MEMORY_PROJECT_ID,
        categories: Optional[Iterable[str]] = None,
        max_items: int = 6,
        max_chars: int = 1200,
    ) -> str:
        items = await self.list_items(project_id=project_id, categories=categories, active_only=True, limit=max_items)
        if not items:
            return ""

        grouped: Dict[str, List[ProjectMemoryItem]] = {}
        for item in items[:max_items]:
            grouped.setdefault(item.category, []).append(item)

        lines = ["【项目长期记忆】"]
        total_chars = len(lines[0])
        for category in _CATEGORY_ORDER:
            category_items = grouped.get(category) or []
            if not category_items:
                continue

            heading = f"- {_CATEGORY_LABELS.get(category, category)}"
            if total_chars + len(heading) > max_chars:
                break
            lines.append(heading)
            total_chars += len(heading)

            for item in category_items:
                entry = f"  - {item.title}：{item.content}"
                if total_chars + len(entry) > max_chars:
                    break
                lines.append(entry)
                total_chars += len(entry)

        return "\n".join(lines).strip()

    async def seed_default_items(self, *, updated_by: str = "system_seed") -> Dict[str, Any]:
        items = get_default_project_memory_items()
        inserted_or_updated: List[ProjectMemoryItem] = []
        for item in items:
            inserted_or_updated.append(
                await self.upsert_item(
                    memory_key=item["memory_key"],
                    title=item["title"],
                    content=item["content"],
                    category=item["category"],
                    project_id=item.get("project_id") or DEFAULT_PROJECT_MEMORY_PROJECT_ID,
                    priority=int(item.get("priority") or 100),
                    active=bool(item.get("active", True)),
                    tags=item.get("tags") or [],
                    metadata=item.get("metadata") or {},
                    updated_by=updated_by,
                )
            )

        return {
            "count": len(inserted_or_updated),
            "items": inserted_or_updated,
        }

    @staticmethod
    def _normalize_tags(tags: Optional[List[str]]) -> List[str]:
        result: List[str] = []
        seen = set()
        for raw in tags or []:
            value = str(raw or "").strip()
            if not value or value in seen:
                continue
            seen.add(value)
            result.append(value)
        return result

    @staticmethod
    def _to_item(doc: Dict[str, Any]) -> ProjectMemoryItem:
        payload = dict(doc or {})
        payload.pop("_id", None)
        return ProjectMemoryItem(**payload)


def get_project_memory_service(db: Any) -> ProjectMemoryService:
    return ProjectMemoryService(db)