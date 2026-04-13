"""将新版风险管理者 v2 提示词推入 MongoDB。

用法：
    python scripts/push_risk_manager_v2_to_db.py          # 预览模式
    python scripts/push_risk_manager_v2_to_db.py --apply  # 执行写库
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from pymongo import MongoClient

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
load_dotenv(PROJECT_ROOT / ".env", override=False)

from tradingagents.config.mongodb_utils import build_mongodb_connection_string, get_mongodb_database_name

_builder_path = PROJECT_ROOT / "scripts" / "template_upgrades"
sys.path.insert(0, str(_builder_path))
from update_research_brief_v2_prompts import PREFERENCE_CONFIG, build_risk_manager_content, get_template_name


def build_expected_template_map() -> dict[str, str]:
    return {
        preference_type: get_template_name("risk_manager_v2", preference_type)
        for preference_type in PREFERENCE_CONFIG
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="推送风险管理者 v2 新提示词到 MongoDB")
    parser.add_argument("--apply", action="store_true", help="执行实际写库更新（不加则为预览模式）")
    args = parser.parse_args()

    expected_templates = build_expected_template_map()
    client = MongoClient(build_mongodb_connection_string())
    db = client[get_mongodb_database_name()]
    collection = db.prompt_templates

    docs = list(
        collection.find(
            {
                "agent_name": "risk_manager_v2",
                "status": "active",
            }
        )
    )

    docs_by_key = {
        (doc.get("preference_type"), doc.get("template_name")): doc
        for doc in docs
    }

    selected_docs = []
    missing_keys = []
    for preference_type, template_name in expected_templates.items():
        doc = docs_by_key.get((preference_type, template_name))
        if doc is None:
            missing_keys.append((preference_type, template_name))
            continue
        selected_docs.append(doc)

    if missing_keys:
        print("以下模板未在数据库中找到：")
        for preference_type, template_name in missing_keys:
            print(f"  - {preference_type} / {template_name}")
        client.close()
        return 1

    print(f"找到 {len(selected_docs)} 条模板：")
    for doc in selected_docs:
        template_name = doc.get("template_name", "")
        current_version = doc.get("version", 1)
        preference_type = doc.get("preference_type", "unknown")
        print(f"  [{template_name}] preference_type={preference_type} 当前 version={current_version}")

    if not args.apply:
        print("\n当前为预览模式，未写入数据库。使用 --apply 执行更新。")
        client.close()
        return 0

    updated = 0
    for doc in selected_docs:
        preference_type = doc.get("preference_type")
        if preference_type not in PREFERENCE_CONFIG:
            print(f"  [SKIP] 未知 preference_type: {preference_type}")
            continue

        new_content = build_risk_manager_content(preference_type)
        current_version = int(doc.get("version") or 1)
        remark = (doc.get("remark") or "").strip()
        remark_suffix = "[2026-04-13] 风险管理者提示词优化：改为可用资源清单 user_prompt，补充缺失材料处理约束，并去掉人民币硬编码"
        if remark_suffix not in remark:
            remark = f"{remark}\n{remark_suffix}".strip()

        collection.update_one(
            {"_id": doc["_id"]},
            {
                "$set": {
                    "content": new_content,
                    "version": current_version + 1,
                    "updated_at": datetime.now(timezone.utc),
                    "remark": remark,
                }
            },
        )
        print(f"  [OK] {doc.get('template_name', '')} version {current_version} -> {current_version + 1}")
        updated += 1

    print(f"\n已写入数据库：{updated} 条模板")
    client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())