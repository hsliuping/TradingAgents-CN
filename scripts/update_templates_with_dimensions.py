"""
更新提示词模板：在 analyst 模板的 analysis_requirements 中添加行业/个股维度变量

这个脚本会在 fundamentals_analyst、market_analyst、news_analyst、social_media_analyst
的 analysis_requirements 末尾追加行业/个股维度注入块。

用法:
    python scripts/update_templates_with_dimensions.py
    python scripts/update_templates_with_dimensions.py --dry-run  # 只预览不修改
"""

import sys, os, argparse
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pymongo import MongoClient
from app.core.config import settings

# 需要注入维度的 analyst 模板
TARGET_AGENTS = [
    "fundamentals_analyst",
    "market_analyst",
    "news_analyst",
    "social_media_analyst",
]

# 要追加到 analysis_requirements 末尾的内容
DIMENSION_BLOCK = """
🏭 行业专项分析维度：
{industry_dimensions}
{industry_focus}

📊 个股专项分析维度：
{stock_dimensions}
{stock_special_notes}
"""

# 标记，用于检测是否已经添加过
MARKER = "🏭 行业专项分析维度："


def main():
    parser = argparse.ArgumentParser(description="更新提示词模板，添加行业/个股维度变量")
    parser.add_argument("--dry-run", action="store_true", help="只预览不修改")
    args = parser.parse_args()

    client = MongoClient(settings.MONGO_URI)
    db = client[settings.MONGO_DB]
    collection = db["prompt_templates"]

    updated, skipped = 0, 0

    for agent_name in TARGET_AGENTS:
        # 查找该 agent 的所有模板（系统 + 用户）
        templates = list(collection.find({"agent_name": agent_name}))
        print(f"\n{'='*60}")
        print(f"Agent: {agent_name} ({len(templates)} templates)")

        for t in templates:
            tid = t["_id"]
            is_sys = t.get("is_system", False)
            tname = t.get("template_name", "?")
            content = t.get("content", {})

            if not isinstance(content, dict):
                print(f"  [{tid}] {tname} - content 不是字典，跳过")
                skipped += 1
                continue

            ar = content.get("analysis_requirements", "")
            if not ar:
                print(f"  [{tid}] {tname} - analysis_requirements 为空，跳过")
                skipped += 1
                continue

            if MARKER in ar:
                print(f"  [{tid}] {tname} - 已包含维度块，跳过")
                skipped += 1
                continue

            # 追加维度块
            new_ar = ar.rstrip() + "\n" + DIMENSION_BLOCK
            print(f"  [{tid}] {tname} (sys={is_sys})")
            print(f"    原 analysis_requirements: {len(ar)} chars")
            print(f"    新 analysis_requirements: {len(new_ar)} chars (+{len(new_ar)-len(ar)})")

            if not args.dry_run:
                collection.update_one(
                    {"_id": tid},
                    {"$set": {"content.analysis_requirements": new_ar}}
                )
                print(f"    ✅ 已更新")
            else:
                print(f"    🔍 [dry-run] 将会更新")
            updated += 1

    client.close()

    print(f"\n{'='*60}")
    print(f"📊 完成: 更新 {updated} 个, 跳过 {skipped} 个")
    if args.dry_run:
        print(f"💡 这是 dry-run 模式，实际未修改数据库。去掉 --dry-run 执行真正更新。")


if __name__ == "__main__":
    main()

