from __future__ import annotations

from datetime import datetime
from pathlib import Path

from app.core.database import get_mongo_db_sync


PROJECT_ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_PATH = PROJECT_ROOT / "scripts" / "external_skill_templates" / "dupont_analysis_skill.py"


def build_dupont_skill_doc() -> dict:
    code = TEMPLATE_PATH.read_text(encoding="utf-8")
    now = datetime.utcnow().isoformat()
    return {
        "tool_id": "analyze_a_share_dupont",
        "display_name": "A股杜邦分析",
        "description": "对 A 股个股执行可复用的杜邦分析，返回净利率、资产周转率、权益乘数及其趋势的结构化结果。",
        "category": "fundamentals",
        "data_source": "core.skill_runtime.data_access",
        "parameters": [
            {
                "name": "symbol",
                "type": "string",
                "description": "A 股股票代码，6 位数字，例如 600519",
                "required": True,
            },
            {
                "name": "periods",
                "type": "integer",
                "description": "返回最近多少个财务报告期，默认 8，最大 12",
                "required": False,
                "default": 8,
            },
        ],
        "expected_output": {
            "type": "object",
            "fields": [
                "symbol",
                "name",
                "industry",
                "status",
                "analysis_scope",
                "latest_dupont",
                "history",
                "summary",
                "warnings",
            ],
            "description": "A 股杜邦分析结构化结果，不包含任何交易建议。",
        },
        "code": code,
        "metadata": {
            "name": "A股杜邦分析",
            "description": "可复用的 A 股杜邦分析 external skill",
            "category": "fundamentals",
            "is_online": True,
            "generation_context": {
                "category_hint": "fundamentals",
                "data_source_hint": "core.skill_runtime.data_access",
                "notes": [
                    "这是从一次性杜邦脚本提升得到的可复用能力",
                    "仅提供财务结构拆解，不提供交易建议",
                ],
            },
            "seed_info": {
                "seed_script": "scripts/seed_dupont_external_skill.py",
                "seeded_at": now,
                "source_mode": "manual_seed",
            },
        },
        "test_input": {"symbol": "600519", "periods": 8},
        "generation_context": {
            "category_hint": "fundamentals",
            "data_source_hint": "core.skill_runtime.data_access",
            "capability_kind": "reusable_skill",
            "origin": "dupont_analysis_temp_script_promotion",
        },
        "status": "active",
        "source": "generated",
        "session_id": "manual-seed-dupont-analysis",
        "user_id": "manual-seed",
        "generation_rounds": 0,
        "generation_time": 0,
        "final_score": None,
        "created_at": now,
        "updated_at": now,
    }


def main() -> None:
    db = get_mongo_db_sync()
    doc = build_dupont_skill_doc()
    existing = db.external_skills.find_one({"tool_id": doc["tool_id"]}, {"_id": 1})
    created_at = doc["created_at"]
    update_doc = dict(doc)
    update_doc.pop("created_at", None)
    db.external_skills.update_one(
        {"tool_id": doc["tool_id"]},
        {
            "$set": {**update_doc, "updated_at": datetime.utcnow().isoformat()},
            "$setOnInsert": {"created_at": created_at},
        },
        upsert=True,
    )
    action = "updated" if existing else "inserted"
    print(f"dupont external skill {action}: {doc['tool_id']}")


if __name__ == "__main__":
    main()