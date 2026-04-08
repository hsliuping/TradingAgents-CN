"""Validate L4 project-memory injection into Agent Workshop prompt templates."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict
from unittest.mock import patch


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.models.agent_workshop import AgentSpec, AgentSpecStatus
from app.services.agent_workshop_service import AgentWorkshopService


class _FakeUpdateResult:
    def __init__(self, modified_count: int = 1):
        self.modified_count = modified_count


class _FakeCursor:
    def __init__(self, items):
        self._items = list(items)

    def sort(self, key, direction):
        reverse = direction == -1
        self._items.sort(key=lambda item: item.get(key), reverse=reverse)
        return self

    def skip(self, _count):
        return self

    def limit(self, count):
        self._items = self._items[:count]
        return self

    async def to_list(self, length=None):
        if length is None:
            return list(self._items)
        return list(self._items[:length])


class _FakeCollection:
    def __init__(self, items):
        self._items = list(items)

    def find(self, query=None, projection=None):
        del query, projection
        return _FakeCursor(self._items)

    async def find_one(self, query=None, projection=None, sort=None):
        del query, projection, sort
        return dict(self._items[0]) if self._items else None

    async def update_one(self, query, update, upsert=False):
        del query, update, upsert
        return _FakeUpdateResult(1)


class _FakeDb:
    def __init__(self):
        self._collections = {
            "prompt_templates": _FakeCollection([]),
            "template_history": _FakeCollection([]),
        }

    def __getitem__(self, name):
        return self._collections[name]

    def __getattr__(self, name):
        try:
            return self._collections[name]
        except KeyError as exc:
            raise AttributeError(name) from exc


def _build_spec() -> AgentSpec:
    return AgentSpec(
        spec_id="spec_valuation_candidate_v1",
        name="A股估值分析师",
        domain="stock_analysis",
        primary_goal="输出A股估值结论",
        outputs=["valuation_report"],
        status=AgentSpecStatus.DRAFT,
        latest_session_id="session_valuation_001",
    )


async def validate_all() -> Dict[str, Any]:
    svc = AgentWorkshopService(_FakeDb())
    captured: Dict[str, Any] = {}

    async def _fake_create_template(_self, payload):
        captured["payload"] = payload
        return SimpleNamespace(id="tpl_test_003", template_name=payload.template_name, status=payload.status)

    async def _fake_build_project_memory_block():
        return "【项目长期记忆】\n- 项目规则\n  - 禁止直接投资建议：所有分析只提供研究与学习参考。\n- 输出约束\n  - 回答结构：先给结论，再给证据和风险。"

    with patch("app.services.agent_workshop_service.PromptTemplateService.create_template", _fake_create_template):
        svc._build_project_memory_block_for_workshop = _fake_build_project_memory_block
        await svc._create_prompt_template(
            "spec_valuation_candidate_v1_v1",
            _build_spec(),
            ["get_quality_factor_bundle_tool"],
        )

    payload = captured["payload"]
    checks = {
        "template_created": payload.template_name.endswith("草案"),
        "system_prompt_contains_l4": "【项目长期记忆】" in payload.content.system_prompt,
        "system_prompt_contains_rule": "禁止直接投资建议" in payload.content.system_prompt,
        "constraints_contains_l4_guard": "必须同时遵守项目长期记忆中的稳定规则" in payload.content.constraints,
        "constraints_contains_output_constraint": "回答结构：先给结论，再给证据和风险。" in payload.content.constraints,
    }
    return {
        "ok": all(checks.values()),
        "checks": checks,
        "system_prompt": payload.content.system_prompt,
        "constraints": payload.content.constraints,
    }


def main() -> int:
    summary = asyncio.run(validate_all())
    status = "PASS" if summary["ok"] else "FAIL"
    print(f"[{status}] agent workshop prompt template project memory loop")
    for check, ok in summary["checks"].items():
        check_status = "PASS" if ok else "FAIL"
        print(f"- [{check_status}] {check}")
    print(summary)
    return 0 if summary["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())