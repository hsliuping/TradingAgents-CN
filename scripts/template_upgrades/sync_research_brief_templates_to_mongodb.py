"""将研究简报相关模板从导出文件定向同步到 MongoDB。

默认预览，不写库；使用 --apply 执行实际更新。
默认同步研究简报链路模板，以及已确认需要一并更新的 fundamentals_analyst_v2。
避免误改其他在线自定义模板。
"""

from __future__ import annotations

import argparse
import json
import sys
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

from pymongo import MongoClient

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parents[1]
sys.path.insert(0, str(SCRIPT_DIR))
sys.path.insert(0, str(PROJECT_ROOT))

from update_research_brief_v2_prompts import ROOT, PREFERENCE_CONFIG, TEMPLATE_BUILDERS, get_template_name
from tradingagents.config.mongodb_utils import build_mongodb_connection_string, get_mongodb_database_name


EXPORT_PATH = ROOT / "exports" / "current_db_templates.json"
BACKUP_DIR = ROOT / "exports" / "compliance_backup"
EXTRA_SYNC_AGENT_NAMES = {"fundamentals_analyst_v2"}
SUPPORTED_AGENT_NAMES = set(TEMPLATE_BUILDERS.keys()) | EXTRA_SYNC_AGENT_NAMES
EXTRA_TEMPLATE_NAME_MAP = {
    "fundamentals_analyst_v2": {
        "aggressive": "基本面分析师 v2.0 - 激进型",
        "neutral": "基本面分析师 v2.0 - 中性型",
        "conservative": "基本面分析师 v2.0 - 保守型",
    }
}


def get_expected_template_label(agent_name: str, preference_type: str) -> str:
    if agent_name in TEMPLATE_BUILDERS:
        return get_template_name(agent_name, preference_type)
    if agent_name in EXTRA_TEMPLATE_NAME_MAP:
        return EXTRA_TEMPLATE_NAME_MAP[agent_name][preference_type]
    return f"{agent_name}/{preference_type}"


def select_export_template(candidates: List[Dict[str, Any]], agent_name: str, preference_type: str) -> Dict[str, Any]:
    expected_template_name = get_expected_template_label(agent_name, preference_type)
    active_candidates = [item for item in candidates if item.get("status") == "active"] or candidates
    exact_name_candidates = [item for item in active_candidates if item.get("template_name") == expected_template_name]

    if exact_name_candidates:
        system_exact_candidates = [item for item in exact_name_candidates if item.get("is_system") is True]
        if len(system_exact_candidates) == 1:
            return system_exact_candidates[0]
        if len(exact_name_candidates) == 1:
            return exact_name_candidates[0]

        filtered_exact_candidates = [
            item for item in exact_name_candidates if "副本" not in str(item.get("template_name") or "")
        ]
        if len(filtered_exact_candidates) == 1:
            return filtered_exact_candidates[0]

        raise ValueError(
            f"导出文件存在多个候选模板，无法确定正式模板: {agent_name}/{expected_template_name}"
        )

    system_non_copy_candidates = [
        item
        for item in active_candidates
        if item.get("is_system") is True and "副本" not in str(item.get("template_name") or "")
    ]
    if len(system_non_copy_candidates) == 1:
        return system_non_copy_candidates[0]

    raise ValueError(
        f"导出文件缺少正式系统模板，无法安全同步: {agent_name}/{expected_template_name}"
    )


def _select_db_doc_for_sync(
    candidates: List[Dict[str, Any]],
    export_doc: Dict[str, Any],
) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    if not candidates:
        raise ValueError("数据库候选模板为空")

    if len(candidates) == 1:
        return candidates[0], []

    expected_template_name = export_doc.get("template_name")
    canonical_candidates = [
        item
        for item in candidates
        if item.get("is_system") is True and item.get("template_name") == expected_template_name
    ]
    if len(canonical_candidates) == 1:
        duplicate_candidates = [item for item in candidates if item is not canonical_candidates[0]]
        if all(
            item.get("is_system") is not True and "副本" in str(item.get("template_name") or "")
            for item in duplicate_candidates
        ):
            return canonical_candidates[0], duplicate_candidates

    filtered_candidates = [
        item
        for item in candidates
        if item.get("is_system") is True and "副本" not in str(item.get("template_name") or "")
    ]
    if len(filtered_candidates) == 1:
        duplicate_candidates = [item for item in candidates if item is not filtered_candidates[0]]
        if all(
            item.get("is_system") is not True and "副本" in str(item.get("template_name") or "")
            for item in duplicate_candidates
        ):
            return filtered_candidates[0], duplicate_candidates

    agent_name = candidates[0].get("agent_name")
    preference_type = candidates[0].get("preference_type")
    raise ValueError(f"数据库存在重复激活模板，请先清理: {agent_name}/{preference_type}")


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, tuple):
        return [_json_safe(item) for item in value]
    if isinstance(value, datetime):
        return value.isoformat()
    if value.__class__.__name__ == "ObjectId":
        return str(value)
    return value


def build_backup_payload(documents: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    items = [_json_safe(deepcopy(doc)) for doc in documents]
    return {
        "export_time": datetime.now(timezone.utc).isoformat(),
        "description": "研究简报模板定向同步前备份",
        "count": len(items),
        "templates": items,
    }


def get_target_template_keys(agent_names: List[str]) -> List[Tuple[str, str]]:
    template_keys: List[Tuple[str, str]] = []
    for agent_name in agent_names:
        if agent_name not in SUPPORTED_AGENT_NAMES:
            raise ValueError(f"不支持的 agent_name: {agent_name}")
        for preference_type in PREFERENCE_CONFIG:
            template_keys.append((agent_name, preference_type))
    return template_keys


def load_export_templates(agent_names: List[str]) -> Dict[Tuple[str, str], Dict[str, Any]]:
    templates = json.loads(EXPORT_PATH.read_text(encoding="utf-8"))
    template_keys = set(get_target_template_keys(agent_names))
    export_candidates: Dict[Tuple[str, str], List[Dict[str, Any]]] = {key: [] for key in template_keys}

    for item in templates:
        key = (item.get("agent_name"), item.get("preference_type"))
        if key in template_keys:
            export_candidates[key].append(item)

    export_map: Dict[Tuple[str, str], Dict[str, Any]] = {}
    for agent_name, preference_type in sorted(template_keys):
        candidates = export_candidates.get((agent_name, preference_type)) or []
        if not candidates:
            continue
        export_map[(agent_name, preference_type)] = select_export_template(candidates, agent_name, preference_type)

    missing = template_keys.difference(export_map.keys())
    if missing:
        missing_text = ", ".join(
            f"{agent}/{get_expected_template_label(agent, preference)}" for agent, preference in sorted(missing)
        )
        raise ValueError(f"导出文件缺少目标模板: {missing_text}")

    return export_map


def build_changed_docs(collection, export_map: Dict[Tuple[str, str], Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
    query_filters = [
        {"agent_name": agent_name, "preference_type": preference_type, "status": "active"}
        for agent_name, preference_type in export_map.keys()
    ]
    db_docs = list(
        collection.find(
            {
                "$or": query_filters
            }
        )
    )

    grouped_docs: Dict[Tuple[str, str], List[Dict[str, Any]]] = {}
    for doc in db_docs:
        key = (doc.get("agent_name"), doc.get("preference_type"))
        grouped_docs.setdefault(key, []).append(doc)

    selected_docs: List[Dict[str, Any]] = []
    duplicate_docs_to_archive: List[Dict[str, Any]] = []
    for key, export_doc in export_map.items():
        candidates = grouped_docs.get(key) or []
        selected_doc, duplicates = _select_db_doc_for_sync(candidates, export_doc)
        selected_docs.append(selected_doc)
        duplicate_docs_to_archive.extend(duplicates)

    found_keys = {(doc.get("agent_name"), doc.get("preference_type")) for doc in selected_docs}
    missing_in_db = set(export_map.keys()).difference(found_keys)
    if missing_in_db:
        missing_text = ", ".join(
            f"{agent}/{export_map[(agent, preference)].get('template_name') or get_expected_template_label(agent, preference)}"
            for agent, preference in sorted(missing_in_db)
        )
        raise ValueError(f"数据库缺少目标模板: {missing_text}")

    changed_docs: List[Dict[str, Any]] = []
    for db_doc in selected_docs:
        key = (db_doc.get("agent_name"), db_doc.get("preference_type"))
        export_doc = export_map[key]
        export_content = export_doc.get("content") or {}
        db_content = db_doc.get("content") or {}

        if db_content == export_content:
            continue

        changed_docs.append(
            {
                "_id": db_doc["_id"],
                "agent_name": db_doc.get("agent_name"),
                "template_name": db_doc.get("template_name"),
                "version": int(db_doc.get("version") or 1),
                "remark": db_doc.get("remark") or "",
                "content": export_content,
                "changed_fields": [field for field in export_content.keys() if db_content.get(field) != export_content.get(field)],
            }
        )

    return db_docs, changed_docs, duplicate_docs_to_archive


def main() -> int:
    parser = argparse.ArgumentParser(description="将研究简报模板从导出文件定向同步到 MongoDB")
    parser.add_argument("--apply", action="store_true", help="执行实际写库更新")
    parser.add_argument(
        "--agents",
        type=str,
        default=",".join(sorted(set(TEMPLATE_BUILDERS.keys()) | EXTRA_SYNC_AGENT_NAMES)),
        help="逗号分隔的 agent_name 列表，仅同步这些模板",
    )
    args = parser.parse_args()

    agent_names = [item.strip() for item in args.agents.split(",") if item.strip()]
    export_map = load_export_templates(agent_names)

    client = MongoClient(build_mongodb_connection_string())
    db = client[get_mongodb_database_name()]
    collection = db.prompt_templates

    db_docs, changed_docs, duplicate_docs_to_archive = build_changed_docs(collection, export_map)

    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    backup_path = BACKUP_DIR / f"research_brief_targeted_sync_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    backup_path.write_text(json.dumps(build_backup_payload(db_docs), ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"目标模板: {len(export_map)} 条")
    print(f"数据库命中: {len(db_docs)} 条")
    print(f"需要更新: {len(changed_docs)} 条")
    print(f"待归档副本: {len(duplicate_docs_to_archive)} 条")
    print(f"备份文件: {backup_path}")

    for item in changed_docs[:30]:
        print(f"- {item['agent_name']} | {item['template_name']} | 字段: {', '.join(item['changed_fields'])}")

    for item in duplicate_docs_to_archive[:30]:
        print(f"- 归档副本 | {item.get('agent_name')} | {item.get('template_name')}")

    if not args.apply:
        print("\n当前为预览模式，未写入数据库。使用 --apply 执行更新。")
        client.close()
        return 0

    sync_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    updated_count = 0
    for item in changed_docs:
        remark = item["remark"].strip()
        remark_suffix = f"[{sync_date}] 定向同步研究简报模板"
        if remark_suffix not in remark:
            remark = f"{remark}\n{remark_suffix}".strip()

        collection.update_one(
            {"_id": item["_id"]},
            {
                "$set": {
                    "content": item["content"],
                    "updated_at": datetime.utcnow(),
                    "version": item["version"] + 1,
                    "remark": remark,
                }
            },
        )
        updated_count += 1

    archived_count = 0
    for item in duplicate_docs_to_archive:
        remark = (item.get("remark") or "").strip()
        remark_suffix = f"[{sync_date}] 同步时自动归档重复副本模板"
        if remark_suffix not in remark:
            remark = f"{remark}\n{remark_suffix}".strip()

        collection.update_one(
            {"_id": item["_id"]},
            {
                "$set": {
                    "status": "draft",
                    "updated_at": datetime.utcnow(),
                    "version": int(item.get("version") or 1) + 1,
                    "remark": remark,
                }
            },
        )
        archived_count += 1

    print(f"\n已写入数据库: {updated_count} 条模板")
    print(f"已归档重复副本: {archived_count} 条模板")
    client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())