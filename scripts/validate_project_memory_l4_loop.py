"""Validate the minimal L4 project-memory write/read/injection loop."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import Any, Dict, List
from unittest.mock import patch


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.services import intelligent_assistant_service as assistant_module
from app.services.project_memory_service import ProjectMemoryService


class _FakeCursor:
    def __init__(self, docs: List[Dict[str, Any]]):
        self._docs = [dict(doc) for doc in docs]

    def sort(self, sort_spec):
        for field, direction in reversed(sort_spec):
            reverse = direction < 0
            self._docs.sort(key=lambda doc: doc.get(field), reverse=reverse)
        return self

    def limit(self, size: int):
        self._docs = self._docs[:size]
        return self

    async def to_list(self, length: int):
        return [dict(doc) for doc in self._docs[:length]]


class _FakeCollection:
    def __init__(self):
        self.docs: List[Dict[str, Any]] = []

    async def update_one(self, query, update, upsert=False):
        for doc in self.docs:
            if _matches(doc, query):
                doc.update(update.get("$set", {}))
                return

        if upsert:
            new_doc = dict(query)
            new_doc.update(update.get("$setOnInsert", {}))
            new_doc.update(update.get("$set", {}))
            self.docs.append(new_doc)

    async def find_one(self, query):
        for doc in self.docs:
            if _matches(doc, query):
                return dict(doc)
        return None

    def find(self, query):
        return _FakeCursor([doc for doc in self.docs if _matches(doc, query)])


class _FakeDB:
    def __init__(self):
        self._collections = {"project_memory_items": _FakeCollection()}

    def __getitem__(self, name: str):
        return self._collections[name]


class _FakeMemoryService:
    async def recall_formatted(self, **kwargs):
        del kwargs
        return "【历史偏好】\n- 你偏好先看结论，再看证据。"


def _matches(doc: Dict[str, Any], query: Dict[str, Any]) -> bool:
    for key, value in query.items():
        if isinstance(value, dict) and "$in" in value:
            if doc.get(key) not in value["$in"]:
                return False
            continue
        if doc.get(key) != value:
            return False
    return True


async def validate_all() -> Dict[str, Any]:
    db = _FakeDB()
    service = ProjectMemoryService(db)

    stored = await service.upsert_item(
        memory_key="assistant-output-constraint",
        title="回答结构",
        content="先给结论，再补证据、风险和不确定性。",
        category="analysis_output_constraint",
        priority=10,
        updated_by="validator",
    )
    items = await service.list_items(limit=10)
    prompt_block = await service.build_prompt_block(max_items=6, max_chars=600)

    with patch("app.services.project_memory_service.get_project_memory_service", return_value=service), patch(
        "core.memory.service.get_memory_service",
        return_value=_FakeMemoryService(),
    ):
        combined_block = await assistant_module._recall_memory_block(
            db=db,
            user_id="user-1",
            user_message="继续按平台规范总结一下",
            current_topic_title="宏观策略讨论",
        )

    checks = {
        "l4_write_success": stored.memory_key == "assistant-output-constraint",
        "l4_read_success": len(items) == 1 and items[0].title == "回答结构",
        "l4_prompt_block_built": "【项目长期记忆】" in prompt_block,
        "assistant_injection_contains_l4": "回答结构：先给结论，再补证据、风险和不确定性。" in combined_block,
        "assistant_injection_keeps_l5_l6": "【历史偏好】" in combined_block,
    }
    return {
        "ok": all(checks.values()),
        "checks": checks,
        "prompt_block": prompt_block,
        "combined_block": combined_block,
    }


def main() -> int:
    summary = asyncio.run(validate_all())
    status = "PASS" if summary["ok"] else "FAIL"
    print(f"[{status}] project memory L4 loop")
    for check, ok in summary["checks"].items():
        check_status = "PASS" if ok else "FAIL"
        print(f"- [{check_status}] {check}")
    print(summary)
    return 0 if summary["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())