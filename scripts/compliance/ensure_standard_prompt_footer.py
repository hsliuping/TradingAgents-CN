"""为所有 prompt_templates 的 system_prompt 统一补齐中文/真实数据提示与免责声明。"""

from __future__ import annotations

import argparse
import json
import re
import sys
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List

from pymongo import MongoClient


PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from tradingagents.config.mongodb_utils import build_mongodb_connection_string, get_mongodb_database_name


EXPORT_FILES = [
    PROJECT_ROOT / "exports" / "current_db_templates.json",
    PROJECT_ROOT / "install" / "database_export_config_2026-02-10.json",
]
BACKUP_DIR = PROJECT_ROOT / "exports" / "compliance_backup"

LANGUAGE_AND_DATA_LINE = "请使用中文，基于真实数据进行分析。"
DISCLAIMER_BLOCK = (
    "**免责声明**：\n"
    "本分析报告仅供参考，不构成投资建议。所有价格区间、市场观点均为分析参考，\n"
    "不构成买卖操作建议。投资有风险，决策需谨慎。投资者应根据自身情况，结合\n"
    "专业投资顾问意见，独立做出投资决策。"
)
STANDARD_PROMPT_FOOTER = f"{LANGUAGE_AND_DATA_LINE}\n{DISCLAIMER_BLOCK}"
DISCLAIMER_PATTERN = re.compile(
    r"\*\*免责声明\*\*[：:]?\s*\n?本分析报告仅供参考.*?独立做出投资决策。",
    flags=re.DOTALL,
)


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


def build_backup_payload(documents: Iterable[Dict[str, Any]], description: str) -> Dict[str, Any]:
    items = [_json_safe(deepcopy(doc)) for doc in documents]
    return {
        "export_time": datetime.now(timezone.utc).isoformat(),
        "description": description,
        "count": len(items),
        "templates": items,
    }


def normalize_system_prompt(text: str) -> str:
    if not text:
        return STANDARD_PROMPT_FOOTER

    result = DISCLAIMER_PATTERN.sub("", text)
    result = result.replace(LANGUAGE_AND_DATA_LINE, "")
    result = re.sub(r"\n{3,}", "\n\n", result).strip()

    if result:
        return f"{result}\n\n{STANDARD_PROMPT_FOOTER}"
    return STANDARD_PROMPT_FOOTER


def update_export_file(path: Path) -> Dict[str, int]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    templates = extract_templates(payload)
    updated_count = 0
    scanned_count = 0

    for item in templates:
        content = item.get("content")
        if not isinstance(content, dict) or "system_prompt" not in content:
            continue

        scanned_count += 1
        old_text = str(content.get("system_prompt") or "")
        new_text = normalize_system_prompt(old_text)
        if old_text == new_text:
            continue

        content["system_prompt"] = new_text
        updated_count += 1

    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"scanned": scanned_count, "updated": updated_count}


def preview_export_updates(path: Path) -> Dict[str, int]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    templates = extract_templates(payload)
    updated_count = 0
    scanned_count = 0

    for item in templates:
        content = item.get("content")
        if not isinstance(content, dict) or "system_prompt" not in content:
            continue

        scanned_count += 1
        old_text = str(content.get("system_prompt") or "")
        if old_text != normalize_system_prompt(old_text):
            updated_count += 1

    return {"scanned": scanned_count, "updated": updated_count}


def extract_templates(payload: Any) -> List[Dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]

    if isinstance(payload, dict):
        data_section = payload.get("data")
        if isinstance(data_section, dict):
            prompt_templates = data_section.get("prompt_templates")
            if isinstance(prompt_templates, list):
                return [item for item in prompt_templates if isinstance(item, dict)]

    raise ValueError("不支持的导出文件结构，未找到 prompt_templates 列表")


def update_mongodb(apply_changes: bool) -> Dict[str, int]:
    client = MongoClient(build_mongodb_connection_string())
    db = client[get_mongodb_database_name()]
    collection = db.prompt_templates

    docs = list(collection.find({"content.system_prompt": {"$exists": True}}))
    updated_docs: List[Dict[str, Any]] = []

    for doc in docs:
        content = doc.get("content") or {}
        old_text = str(content.get("system_prompt") or "")
        new_text = normalize_system_prompt(old_text)
        if old_text == new_text:
            continue

        updated_docs.append({
            "_id": doc["_id"],
            "agent_name": doc.get("agent_name"),
            "template_name": doc.get("template_name"),
            "system_prompt": new_text,
        })

    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    backup_path = BACKUP_DIR / f"standard_prompt_footer_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    backup_path.write_text(
        json.dumps(build_backup_payload(docs, "全量补齐 system_prompt 标准尾段前备份"), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    if apply_changes:
        for item in updated_docs:
            collection.update_one(
                {"_id": item["_id"]},
                {
                    "$set": {
                        "content.system_prompt": item["system_prompt"],
                        "updated_at": datetime.utcnow(),
                    }
                },
            )

    client.close()
    return {
        "scanned": len(docs),
        "updated": len(updated_docs),
        "backup_path": str(backup_path),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="为所有模板统一补齐中文/真实数据提示与免责声明")
    parser.add_argument("--apply", action="store_true", help="执行实际写入（默认仅预览）")
    parser.add_argument("paths", nargs="*", type=Path, help="仅处理指定导出文件路径")
    args = parser.parse_args()

    target_files = args.paths or EXPORT_FILES

    print("=== 导出文件 ===")
    for path in target_files:
        stats = preview_export_updates(path) if not args.apply else update_export_file(path)
        print(f"{path}: scanned={stats['scanned']} updated={stats['updated']}")

    print("\n=== MongoDB ===")
    db_stats = update_mongodb(apply_changes=args.apply)
    print(f"prompt_templates: scanned={db_stats['scanned']} updated={db_stats['updated']}")
    print(f"backup: {db_stats['backup_path']}")

    if not args.apply:
        print("\n当前为预览模式，未写入导出文件或数据库。使用 --apply 执行更新。")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())