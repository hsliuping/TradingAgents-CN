"""将新版社交分析师 v2 提示词推入 MongoDB。

用法：
    python scripts/push_social_analyst_v2_to_db.py          # 预览模式
    python scripts/push_social_analyst_v2_to_db.py --apply  # 执行写库
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv
load_dotenv(PROJECT_ROOT / ".env", override=False)

from pymongo import MongoClient
from tradingagents.config.mongodb_utils import build_mongodb_connection_string, get_mongodb_database_name

_builder_path = PROJECT_ROOT / "scripts" / "template_upgrades"
sys.path.insert(0, str(_builder_path))
from update_research_brief_v2_prompts import build_social_analyst_content

# 模板名称 → preference_type 映射
VARIANT_MAP = {
    "社交分析师 v2.0 - 激进型": "aggressive",
    "社交分析师 v2.0 - 中性型": "neutral",
    "社交分析师 v2.0 - 保守型": "conservative",
}


def main() -> int:
    parser = argparse.ArgumentParser(description="推送社交分析师 v2 新提示词到 MongoDB")
    parser.add_argument("--apply", action="store_true", help="执行实际写库更新（不加则为预览模式）")
    args = parser.parse_args()

    client = MongoClient(build_mongodb_connection_string())
    db = client[get_mongodb_database_name()]
    collection = db.prompt_templates

    docs = list(collection.find({
        "agent_name": "social_analyst_v2",
        "status": "active",
        "template_name": {"$in": list(VARIANT_MAP.keys())},
    }))

    if not docs:
        print("未找到 social_analyst_v2 的 active 模板，请检查数据库。")
        client.close()
        return 1

    print(f"找到 {len(docs)} 条模板：")
    for doc in docs:
        template_name = doc.get("template_name", "")
        current_version = doc.get("version", 1)
        preference_type = VARIANT_MAP.get(template_name, "unknown")
        print(f"  [{template_name}]  preference_type={preference_type}  当前 version={current_version}")

    if not args.apply:
        print("\n当前为预览模式，未写入数据库。使用 --apply 执行更新。")
        client.close()
        return 0

    updated = 0
    for doc in docs:
        template_name = doc.get("template_name", "")
        preference_type = VARIANT_MAP.get(template_name)
        if preference_type is None:
            print(f"  [SKIP] 未知 template_name: {template_name}")
            continue

        new_content = build_social_analyst_content(preference_type)
        current_version = int(doc.get("version") or 1)
        remark = (doc.get("remark") or "").strip()
        remark_suffix = "[2026-04-30] 社媒提示词深度优化：analysis_requirements / system_prompt / user_prompt 全面升级"
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
        print(f"  [OK] {template_name}  version {current_version} → {current_version + 1}")
        updated += 1

    print(f"\n已写入数据库：{updated} 条模板")
    client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
