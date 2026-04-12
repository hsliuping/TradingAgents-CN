"""从 MongoDB 重建 exports/current_db_templates.json。"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

from pymongo import MongoClient


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from tradingagents.config.mongodb_utils import build_mongodb_connection_string, get_mongodb_database_name


DEFAULT_OUTPUT = PROJECT_ROOT / "exports" / "current_db_templates.json"


def json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [json_safe(item) for item in value]
    if isinstance(value, tuple):
        return [json_safe(item) for item in value]
    if isinstance(value, datetime):
        return value.isoformat()
    if value.__class__.__name__ == "ObjectId":
        return str(value)
    return value


def build_query(include_inactive: bool, include_user_templates: bool) -> Dict[str, Any]:
    query: Dict[str, Any] = {}

    if not include_inactive:
        query["status"] = "active"

    if not include_user_templates:
        query["is_system"] = True
        query["created_by"] = None

    return query


def export_templates(
    output_path: Path,
    *,
    include_inactive: bool = False,
    include_user_templates: bool = False,
) -> int:
    client = MongoClient(build_mongodb_connection_string())

    try:
        database = client[get_mongodb_database_name()]
        query = build_query(include_inactive=include_inactive, include_user_templates=include_user_templates)
        cursor = database.prompt_templates.find(query).sort(
            [
                ("agent_type", 1),
                ("agent_name", 1),
                ("preference_type", 1),
                ("template_name", 1),
                ("_id", 1),
            ]
        )
        documents = [json_safe(doc) for doc in cursor]
    finally:
        client.close()

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(documents, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return len(documents)


def main() -> int:
    parser = argparse.ArgumentParser(description="从 MongoDB 重建 current_db_templates.json")
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"输出文件路径（默认：{DEFAULT_OUTPUT}）",
    )
    parser.add_argument(
        "--include-inactive",
        action="store_true",
        help="包含非 active 模板",
    )
    parser.add_argument(
        "--include-user-templates",
        action="store_true",
        help="包含用户模板和非系统模板",
    )
    args = parser.parse_args()

    count = export_templates(
        args.output,
        include_inactive=args.include_inactive,
        include_user_templates=args.include_user_templates,
    )
    print(f"exported {count} templates to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())