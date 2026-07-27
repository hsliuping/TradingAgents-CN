"""检查数据库中 risk_assessment 字段的实际数据结构。"""
import os
import sys
import json
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))


def find_field(obj, target, path=""):
    """递归查找字段，返回 (路径, 值) 或 None"""
    if isinstance(obj, dict):
        for k, v in obj.items():
            cur = f"{path}.{k}" if path else k
            if k == target:
                return cur, v
            if isinstance(v, (dict, list)):
                r = find_field(v, target, cur)
                if r:
                    return r
    elif isinstance(obj, list):
        for i, item in enumerate(obj[:5]):
            r = find_field(item, target, f"{path}[{i}]")
            if r:
                return r
    return None


def describe_value(label, value):
    """描述一个值的类型和内容"""
    print(f"  [{label}] type={type(value).__name__}")
    if isinstance(value, str):
        print(f"    len={len(value)}")
        preview = value[:300].replace("\n", "\\n")
        print(f"    预览: {preview}")
        stripped = value.strip()
        if stripped.startswith("{") or stripped.startswith("["):
            try:
                parsed = json.loads(stripped)
                if isinstance(parsed, dict):
                    print(f"    ✅ JSON 字符串，keys={list(parsed.keys())}")
            except Exception as e:
                print(f"    ❌ 非合法 JSON: {e}")
        elif "```json" in value:
            print(f"    包含 ```json 代码块")
    elif isinstance(value, dict):
        print(f"    keys={list(value.keys())}")
        print(f"    预览: {json.dumps(value, ensure_ascii=False)[:400]}")
    elif isinstance(value, list):
        print(f"    len={len(value)}")
        if value:
            print(f"    [0] type={type(value[0]).__name__}")
    elif value is None:
        print(f"    (None)")
    else:
        print(f"    值: {value}")


def main() -> int:
    from app.core.database import get_mongo_db_sync

    db = get_mongo_db_sync()

    print("=== 数据库相关集合 ===")
    for name in db.list_collection_names():
        if any(x in name.lower() for x in ("analy", "report", "task")):
            print(f"  {name}: {db[name].count_documents({})} 条")

    # 在 analysis_reports 和 unified_analysis_tasks 中找 risk_assessment
    print("\n=== 查找 risk_assessment 字段 ===")
    for coll_name in ["analysis_reports", "unified_analysis_tasks"]:
        coll = db[coll_name]
        # 最近的 5 条文档
        docs = list(coll.find({}).sort("_id", -1).limit(5))
        print(f"\n--- {coll_name}（最近 {len(docs)} 条）---")
        for i, doc in enumerate(docs, 1):
            print(f"\n[文档 {i}] _id={doc.get('_id')} ticker={doc.get('ticker', '?')}")
            print(f"  顶层 keys: {list(doc.keys())[:30]}")

            # 找 risk_assessment
            for target in ("risk_assessment", "risk_management_decision", "final_trade_decision"):
                found = find_field(doc, target)
                if found:
                    path, value = found
                    print(f"\n  >> 字段 {target} 在路径: {path}")
                    describe_value(target, value)
                else:
                    print(f"\n  >> 字段 {target} 不存在")

            # 只看第一条文档就够了
            break

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
